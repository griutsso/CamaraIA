"""
Backend de almacenamiento SQLite con modo WAL.

Persiste detecciones, imágenes cifradas y logs del sistema.
Soporta lectura/escritura concurrente y rotación automática.
"""

from __future__ import annotations

import json
import logging
import sqlite3
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
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS system_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    level       TEXT NOT NULL,
    message     TEXT NOT NULL,
    timestamp   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_detections_type ON detections(type);
CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp);
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
        self._conn: Optional[sqlite3.Connection] = None

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

        logger.info(f"Base de datos inicializada: {self._db_path}")

    def save_detection(self, detection: Detection, context_image: np.ndarray = None) -> str:
        """Persiste una detección con su imagen y opcionalmente imagen de contexto."""
        if not self._conn:
            raise RuntimeError("Base de datos no inicializada.")

        detection_id = str(uuid.uuid4())[:12]

        # Guardar imagen principal (crop del rostro/placa)
        image_path: Optional[str] = None
        if detection.crop_image is not None:
            image_path = self._save_image(detection_id, detection.crop_image)

        # Guardar imagen de contexto (cuerpo completo / vehículo completo)
        context_path: Optional[str] = None
        if context_image is not None:
            context_path = self._save_image(f"{detection_id}_ctx", context_image)

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
                 track_id, image_path, context_image_path, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        self._conn.commit()

        # Emitir evento
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

    def _save_image(self, detection_id: str, image: np.ndarray) -> str:
        """
        Guarda una imagen de detección en disco.

        TODO: Implementar cifrado AES-256 en Fase 4.
        """
        # Organizar por fecha para facilitar rotación
        date_dir = self._images_path / datetime.now().strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{detection_id}.jpg"
        filepath = date_dir / filename

        cv2.imwrite(str(filepath), image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return str(filepath)
