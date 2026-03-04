"""
Backend de almacenamiento SQLite con modo WAL.

Persiste detecciones, imágenes cifradas y logs del sistema.
Soporta lectura/escritura concurrente y rotación automática.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from src.core.events import EventBus
from src.core.interfaces import Detection, DetectionType, IStorageBackend

logger = logging.getLogger(__name__)

# Esquema de la base de datos
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS detections (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    confidence  REAL NOT NULL,
    bbox_x1     REAL NOT NULL,
    bbox_y1     REAL NOT NULL,
    bbox_x2     REAL NOT NULL,
    bbox_y2     REAL NOT NULL,
    track_id    INTEGER,
    image_path  TEXT,
    context_image_path TEXT,
    metadata    TEXT,
    session_id  TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    created_at  TEXT DEFAULT (datetime('now')),
    closed_at   TEXT,
    camera_info TEXT
);

CREATE TABLE IF NOT EXISTS system_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    level       TEXT NOT NULL,
    message     TEXT NOT NULL,
    timestamp   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_detections_type ON detections(type);
CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp);
CREATE INDEX IF NOT EXISTS idx_detections_session ON detections(session_id);
"""


class SQLiteStorage(IStorageBackend):
    """
    Almacenamiento local con SQLite en modo WAL.

    WAL (Write-Ahead Logging) permite lecturas concurrentes
    mientras se realizan escrituras — ideal para tiempo real.
    """

    def __init__(
        self,
        db_path: str = "data/detections.db",
        images_path: str = "data/captures",
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._images_path = Path(images_path)
        self._event_bus = event_bus
        self._session_id: Optional[str] = None
        self._conn: Optional[sqlite3.Connection] = None
        self._write_lock = threading.Lock()  # Serializa escrituras entre threads

        # Crear directorios
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._images_path.mkdir(parents=True, exist_ok=True)

        self._initialize_db()

    def _initialize_db(self) -> None:
        """Inicializa la base de datos con el esquema."""
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row

        # Activar modo WAL para concurrencia
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA temp_store=MEMORY")

        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

        # Migrar esquema: agregar columna context_image_path si no existe
        try:
            self._conn.execute("SELECT context_image_path FROM detections LIMIT 1")
        except sqlite3.OperationalError:
            self._conn.execute(
                "ALTER TABLE detections ADD COLUMN context_image_path TEXT"
            )
            self._conn.commit()
            logger.info("Migración: columna context_image_path agregada.")

        # Migrar esquema: agregar columna session_id si no existe
        try:
            self._conn.execute("SELECT session_id FROM detections LIMIT 1")
        except sqlite3.OperationalError:
            self._conn.execute(
                "ALTER TABLE detections ADD COLUMN session_id TEXT"
            )
            self._conn.commit()
            logger.info("Migración: columna session_id agregada.")

        logger.info(f"Base de datos inicializada: {self._db_path}")

    def save_detection(self, detection: Detection, context_image: np.ndarray = None) -> str:
        """
        Persiste una detección con su imagen y opcionalmente imagen de contexto.

        Thread-safe: usa _write_lock para serializar escrituras concurrentes.
        """
        if not self._conn:
            raise RuntimeError("Base de datos no inicializada.")

        detection_id = str(uuid.uuid4())[:12]

        with self._write_lock:
            # Guardar imagen principal (crop del rostro/placa)
            image_path: Optional[str] = None
            if detection.crop_image is not None:
                image_path = self._save_image(
                    detection_id, detection.crop_image, detection.detection_type,
                )

            # Guardar imagen de contexto (cuerpo completo / vehículo completo)
            context_path: Optional[str] = None
            if context_image is not None:
                context_path = self._save_image(
                    f"{detection_id}_ctx", context_image, detection.detection_type,
                )

            # Serializar metadata (excluir crop images del JSON)
            meta_clean = {
                k: v for k, v in detection.metadata.items()
                if not isinstance(v, np.ndarray)
            }
            metadata_json = json.dumps(meta_clean, ensure_ascii=False)

            self._conn.execute(
                """
                INSERT INTO detections
                    (id, type, timestamp, confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                     track_id, image_path, context_image_path, metadata, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    detection_id,
                    detection.detection_type.name,
                    detection.timestamp.isoformat(),
                    detection.confidence,
                    detection.bbox.x1,
                    detection.bbox.y1,
                    detection.bbox.x2,
                    detection.bbox.y2,
                    detection.track_id,
                    image_path,
                    context_path,
                    metadata_json,
                    self._session_id,
                ),
            )
            self._conn.commit()

        # Emitir evento fuera del lock (evita deadlocks con listeners)
        if self._event_bus:
            self._event_bus.emit(EventBus.DETECTION_SAVED, {
                "id": detection_id,
                "type": detection.detection_type.name,
            })

        logger.debug(f"Detección guardada: {detection_id} ({detection.detection_type.name})")
        return detection_id

    def get_detections(
        self,
        detection_type: Optional[DetectionType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Recupera detecciones con filtros opcionales."""
        if not self._conn:
            return []

        query = "SELECT * FROM detections"
        params: list[Any] = []

        if detection_type:
            query += " WHERE type = ?"
            params.append(detection_type.name)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self._conn.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del almacenamiento."""
        if not self._conn:
            return {}

        stats: dict[str, Any] = {}

        # Conteo por tipo
        cursor = self._conn.execute(
            "SELECT type, COUNT(*) as count FROM detections GROUP BY type"
        )
        counts = {row["type"]: row["count"] for row in cursor.fetchall()}
        stats["counts"] = counts
        stats["total"] = sum(counts.values())

        # Espacio en disco
        db_size = self._db_path.stat().st_size if self._db_path.exists() else 0
        images_size = sum(
            f.stat().st_size for f in self._images_path.rglob("*") if f.is_file()
        )
        stats["db_size_mb"] = round(db_size / (1024 * 1024), 2)
        stats["images_size_mb"] = round(images_size / (1024 * 1024), 2)
        stats["total_size_mb"] = stats["db_size_mb"] + stats["images_size_mb"]

        return stats

    def close(self) -> None:
        """Cierra la conexión a la base de datos."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Conexión a base de datos cerrada.")

    # ═══ Eliminación ═══

    def delete_detection(self, detection_id: str) -> bool:
        """
        Elimina una detección y sus imágenes asociadas del disco.
        Thread-safe: usa _write_lock.
        """
        if not self._conn:
            return False

        with self._write_lock:
            try:
                cursor = self._conn.execute(
                    "SELECT image_path, context_image_path FROM detections WHERE id = ?",
                    (detection_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return False

                # Eliminar registro
                self._conn.execute("DELETE FROM detections WHERE id = ?", (detection_id,))
                self._conn.commit()

                # Eliminar archivos de imagen
                for path_str in (row["image_path"], row["context_image_path"]):
                    if path_str:
                        p = Path(path_str)
                        if p.exists():
                            p.unlink()

                logger.info(f"Detección eliminada: {detection_id}")
                return True

            except Exception as e:
                logger.error(f"Error eliminando detección {detection_id}: {e}")
                return False

    # ═══ Sesiones ═══

    def set_session_id(self, session_id: str) -> None:
        """Establece la sesión activa y redirige las imágenes a su carpeta."""
        self._session_id = session_id
        self._images_path = Path("data/sessions") / session_id / "capturas"
        self._images_path.mkdir(parents=True, exist_ok=True)
        # Pre-crear subcarpetas por tipo
        (self._images_path / "personas").mkdir(exist_ok=True)
        (self._images_path / "vehiculos").mkdir(exist_ok=True)

    def create_session(self, session_id: str, camera_info: dict) -> bool:
        """Crea un registro de sesión nueva."""
        if not self._conn:
            return False
        try:
            camera_json = json.dumps(camera_info, ensure_ascii=False)
            with self._write_lock:
                self._conn.execute(
                    "INSERT OR IGNORE INTO sessions (id, camera_info) VALUES (?, ?)",
                    (session_id, camera_json),
                )
                self._conn.commit()
            self.set_session_id(session_id)
            logger.info(f"Sesión creada: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error creando sesión: {e}")
            return False

    def close_session(self, session_id: str) -> bool:
        """Marca una sesión como cerrada."""
        if not self._conn:
            return False
        try:
            with self._write_lock:
                self._conn.execute(
                    "UPDATE sessions SET closed_at = datetime('now') WHERE id = ?",
                    (session_id,),
                )
                self._conn.commit()
            self._session_id = None
            logger.info(f"Sesión cerrada: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error cerrando sesión: {e}")
            return False

    def get_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna todas las sesiones ordenadas por fecha, con conteos de capturas."""
        if not self._conn:
            return []
        cursor = self._conn.execute(
            """
            SELECT s.id, s.created_at, s.closed_at, s.camera_info,
                   COALESCE(d.total, 0) as capture_count,
                   COALESCE(d.faces, 0) as face_count,
                   COALESCE(d.plates, 0) as plate_count
            FROM sessions s
            LEFT JOIN (
                SELECT session_id,
                       COUNT(*) as total,
                       SUM(CASE WHEN type IN ('FACE','PERSON') THEN 1 ELSE 0 END) as faces,
                       SUM(CASE WHEN type IN ('PLATE','VEHICLE') THEN 1 ELSE 0 END) as plates
                FROM detections
                GROUP BY session_id
            ) d ON s.id = d.session_id
            ORDER BY s.created_at DESC LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_session_detections(
        self, session_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Retorna detecciones de una sesión específica."""
        if not self._conn:
            return []
        cursor = self._conn.execute(
            "SELECT * FROM detections WHERE session_id = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def delete_session(self, session_id: str) -> bool:
        """
        Elimina una sesión completa: registro en sessions, sus detecciones,
        y toda la carpeta de archivos en disco (capturas, videos, etc.).
        """
        if not self._conn:
            return False

        with self._write_lock:
            try:
                # 1) Eliminar detecciones asociadas (y sus archivos de imagen)
                cursor = self._conn.execute(
                    "SELECT id, image_path, context_image_path FROM detections WHERE session_id = ?",
                    (session_id,),
                )
                for row in cursor.fetchall():
                    for path_str in (row["image_path"], row["context_image_path"]):
                        if path_str:
                            p = Path(path_str)
                            if p.exists():
                                p.unlink()

                self._conn.execute(
                    "DELETE FROM detections WHERE session_id = ?", (session_id,)
                )

                # 2) Eliminar registro de sesión
                self._conn.execute(
                    "DELETE FROM sessions WHERE id = ?", (session_id,)
                )
                self._conn.commit()

                # 3) Eliminar carpeta completa de la sesión en disco
                import shutil
                session_dir = Path("data/sessions") / session_id
                if session_dir.exists():
                    shutil.rmtree(session_dir)

                logger.info(f"Sesión eliminada completamente: {session_id}")
                return True

            except Exception as e:
                logger.error(f"Error eliminando sesión {session_id}: {e}")
                return False

    # ═══ Imágenes ═══

    def _save_image(
        self,
        detection_id: str,
        image: np.ndarray,
        detection_type: Optional[DetectionType] = None,
    ) -> str:
        """
        Guarda una imagen de detección en disco.

        Organiza en subcarpetas por tipo:
          capturas/personas/  — rostros y detecciones de persona
          capturas/vehiculos/ — placas y detecciones de vehículo
        """
        # Subcarpeta según tipo de detección
        if detection_type in (DetectionType.FACE, DetectionType.PERSON):
            type_dir = self._images_path / "personas"
        elif detection_type in (DetectionType.PLATE, DetectionType.VEHICLE):
            type_dir = self._images_path / "vehiculos"
        else:
            type_dir = self._images_path / "otros"

        type_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{detection_id}.jpg"
        filepath = type_dir / filename

        cv2.imwrite(str(filepath), image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return str(filepath)
