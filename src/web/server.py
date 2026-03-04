"""
IA-CAM-SERVICE — Servidor Web Flask

Streaming de video via MJPEG y API REST para control del sistema.
El patrón MJPEG es el mismo que usan cámaras IP profesionales:
  cv2.imencode('.jpg') → bytes → multipart HTTP stream → <img> en el navegador

Endpoints:
  /                    → Página principal (SPA)
  /video_feed          → Stream MJPEG en tiempo real
  /api/camera/start    → Iniciar cámara
  /api/camera/stop     → Detener cámara
  /api/camera/status   → Estado de la cámara (JSON)
  /api/settings        → GET/POST configuración
  /api/detections      → Últimas detecciones (JSON)
  /api/captures        → Capturas recientes con imágenes base64
"""

from __future__ import annotations

import base64
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import yaml
from flask import Flask, Response, jsonify, render_template, request

from src.capture.frame_buffer import FrameBuffer
from src.core.container import ServiceContainer
from src.core.events import EventBus
from src.core.interfaces import Detection, DetectionType
from src.pipeline.detection_pipeline import DetectionPipeline
from src.web.state import WebState

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Capture Thread (captura de cámara en background)
# ═══════════════════════════════════════════════════════════════

def _capture_loop(
    container: ServiceContainer,
    state: WebState,
    frame_buffer: FrameBuffer,
) -> None:
    """
    Lee frames de la cámara en un thread dedicado.
    Almacena el último frame para MJPEG y envía al FrameBuffer para IA.
    """
    video_source = container.video_source
    frame_count = 0
    loop_start = time.time()

    while state.camera_active and video_source and video_source.is_active():
        frame = video_source.read_frame()

        if frame is not None:
            frame_count += 1

            # Guardar frame para el stream MJPEG
            state.set_frame(frame)

            # Escribir al video si se está grabando (atómico y thread-safe)
            state.write_frame(frame)

            # Enviar al detection pipeline cada 3 frames
            if frame_count % 3 == 0:
                frame_buffer.put(frame)

            # FPS
            elapsed = time.time() - loop_start
            if elapsed > 0:
                state.set_fps(frame_count / elapsed)

        elif not video_source.is_active():
            logger.warning("Cámara desconectada en capture thread.")
            break

        # Pequeña pausa para no saturar el CPU
        time.sleep(0.001)

    state.camera_active = False
    logger.info(f"Capture thread finalizado. Frames: {frame_count}")


# ═══════════════════════════════════════════════════════════════
#  MJPEG Generator
# ═══════════════════════════════════════════════════════════════

def _generate_mjpeg(state: WebState) -> bytes:
    """
    Generador MJPEG: encode a JPEG y yield como multipart stream.
    Este es el patrón estándar de streaming que usan las cámaras IP.
    """
    while True:
        frame = state.get_frame()

        if frame is None:
            time.sleep(0.03)
            continue

        # Dibujar detecciones sobre el frame
        display = frame.copy()
        dets = state.get_detections()

        if dets:
            display = _draw_detections(display, dets)

        # Overlay de FPS
        camera_status = state.get_camera_status()
        cv2.putText(
            display,
            f"FPS: {camera_status['fps']:.0f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 100),
            2,
            cv2.LINE_AA,
        )

        # Encode a JPEG (muy rápido, nativo C++)
        _, jpeg = cv2.imencode(
            '.jpg', display,
            [cv2.IMWRITE_JPEG_QUALITY, 85]
        )

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n'
            + jpeg.tobytes()
            + b'\r\n'
        )

        # ~30 FPS target
        time.sleep(0.033)


def _draw_detections(frame: np.ndarray, detections: list[Detection]) -> np.ndarray:
    """Dibuja bounding boxes sobre el frame."""
    h, w = frame.shape[:2]
    colors_map = {
        DetectionType.FACE: (191, 90, 242),    # Púrpura
        DetectionType.PLATE: (255, 210, 100),   # Amarillo
        DetectionType.PERSON: (48, 209, 88),    # Verde
        DetectionType.VEHICLE: (100, 210, 255), # Cyan
    }

    for det in detections:
        x1, y1, x2, y2 = det.bbox.to_absolute(w, h)
        color = colors_map.get(det.detection_type, (255, 255, 255))

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

        label = det.label
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 8, y1), color, -1)
        cv2.putText(
            frame, label, (x1 + 4, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA,
        )

    return frame


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def _get_session_folder(session_id: str) -> Path:
    """Retorna la carpeta base de una sesión."""
    return Path("data/sessions") / session_id


def _create_video_writer(
    width: int,
    height: int,
    fps: float,
    output_path: str,
) -> cv2.VideoWriter:
    """Crea un cv2.VideoWriter para MP4."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"No se pudo crear el video writer: {output_path}")
    return writer


# ═══════════════════════════════════════════════════════════════
#  Flask App Factory
# ═══════════════════════════════════════════════════════════════

def create_app(container: ServiceContainer) -> Flask:
    """Crea y configura la aplicación Flask."""

    # Estado centralizado (reemplaza todas las variables globales)
    state = WebState()
    frame_buffer = FrameBuffer(max_size=5)
    pipeline = DetectionPipeline(
        container, frame_buffer, encode_base64=True,
    )

    # Referencia mutable para el capture thread
    capture_thread: dict[str, Optional[threading.Thread]] = {"ref": None}

    # ── Conectar pipeline → state (detecciones para el stream MJPEG) ──
    def on_frame_processed(event_name, data):
        if data and "detections" in data:
            state.set_detections(data["detections"])

    container.event_bus.subscribe(EventBus.FRAME_PROCESSED, on_frame_processed)

    # ── Flask ──
    template_dir = Path(__file__).parent / "templates"

    app = Flask(
        __name__,
        template_folder=str(template_dir),
    )
    app.config["SECRET_KEY"] = "ia-cam-service-local"

    # ── Rutas ──

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/video_feed")
    def video_feed():
        """Stream MJPEG — se conecta con <img src="/video_feed">"""
        return Response(
            _generate_mjpeg(state),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/api/camera/start", methods=["POST"])
    def camera_start():
        if state.camera_active:
            return jsonify({"status": "already_active"})

        try:
            # Iniciar pipeline (carga modelos en background)
            if not pipeline.is_running:
                pipeline.start()

            # Iniciar cámara
            video_source = container.video_source
            video_source.start()

            camera_info = {
                "resolution": f"{video_source.resolution[0]}x{video_source.resolution[1]}",
                "fps": video_source.fps,
                "device": str(container.config.camera.source),
            }

            # ── Crear sesión ──
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_folder = _get_session_folder(session_id)
            (session_folder / "capturas").mkdir(parents=True, exist_ok=True)
            (session_folder / "video").mkdir(parents=True, exist_ok=True)

            state.session_id = session_id
            state.session_folder = str(session_folder)

            storage = container.storage
            if storage:
                storage.create_session(session_id, camera_info)

            state.camera_active = True
            state.set_camera_info(camera_info, start_time=time.time())

            # Lanzar capture thread
            t = threading.Thread(
                target=_capture_loop,
                args=(container, state, frame_buffer),
                name="CaptureThread",
                daemon=True,
            )
            t.start()
            capture_thread["ref"] = t

            # ── Iniciar grabación automáticamente ──
            try:
                video_dir = session_folder / "video"
                video_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%H%M%S")
                video_path = str(video_dir / f"recording_{timestamp}.mp4")

                w, h = video_source.resolution
                fps = video_source.fps or 20.0
                writer = _create_video_writer(w, h, fps, video_path)
                state.set_recording(active=True, path=video_path, writer=writer)
                logger.info(f"Grabación automática iniciada: {video_path}")
            except Exception as rec_err:
                logger.error(f"Error iniciando grabación automática: {rec_err}")

            logger.info(f"Cámara iniciada — Sesión: {session_id}")
            return jsonify({
                "status": "started",
                "camera": camera_info,
                "session_id": session_id,
                "recording": state.recording_active,
            })

        except Exception as e:
            state.camera_active = False
            logger.error(f"Error iniciando cámara: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/camera/stop", methods=["POST"])
    def camera_stop():
        if not state.camera_active:
            return jsonify({"status": "already_stopped"})

        # 1) Detener el capture thread PRIMERO (deja de escribir al writer)
        state.camera_active = False

        t = capture_thread.get("ref")
        if t and t.is_alive():
            t.join(timeout=3.0)

        # 2) AHORA es seguro cerrar el writer (ningún thread escribe)
        if state.recording_active:
            state.close_video_writer()
            logger.info("Grabación detenida automáticamente al parar cámara.")

        # 3) Cerrar sesión en la BD
        session_id = state.session_id
        if session_id:
            storage = container.storage
            if storage:
                storage.close_session(session_id)

        # 4) Detener cámara
        video_source = container.video_source
        if video_source:
            video_source.stop()

        frame_buffer.clear()
        pipeline.reset_tracking()
        state.reset()

        logger.info("Cámara detenida.")
        return jsonify({"status": "stopped"})

    @app.route("/api/camera/status")
    def camera_status():
        status = state.get_camera_status()
        stats = pipeline.get_stats()
        status["unique_faces"] = stats["unique_faces"]
        status["unique_plates"] = stats["unique_plates"]
        return jsonify(status)

    @app.route("/api/detections")
    def get_detections():
        stats = pipeline.get_stats()
        return jsonify({
            "detections": pipeline.get_detection_history(limit=20),
            "unique_faces": stats["unique_faces"],
            "unique_plates": stats["unique_plates"],
        })

    @app.route("/api/captures")
    def get_captures():
        """Retorna las capturas recientes con pares de imágenes (base64)."""
        return jsonify({"captures": pipeline.get_recent_captures(limit=20)})

    # ── Eliminar captura ──

    @app.route("/api/captures/<capture_id>", methods=["DELETE"])
    def delete_capture(capture_id: str):
        """Elimina una captura (registro + archivos de imagen)."""
        storage = container.storage
        db_deleted = False
        if storage:
            db_deleted = storage.delete_detection(capture_id)

        pipeline.remove_capture(capture_id)

        if db_deleted:
            logger.info(f"Captura eliminada: {capture_id}")
            return jsonify({"status": "deleted", "id": capture_id})
        else:
            return jsonify({"status": "not_found", "id": capture_id}), 404

    # ── Grabación de video ──

    @app.route("/api/recording/start", methods=["POST"])
    def recording_start():
        if not state.camera_active:
            return jsonify({"status": "error", "message": "Cámara no activa"}), 400

        if state.recording_active:
            return jsonify({"status": "already_recording"})

        try:
            session_id = state.session_id
            if not session_id:
                return jsonify({"status": "error", "message": "No hay sesión activa"}), 400

            session_folder = _get_session_folder(session_id)
            video_dir = session_folder / "video"
            video_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%H%M%S")
            video_path = str(video_dir / f"recording_{timestamp}.mp4")

            # Obtener resolución de la cámara
            video_source = container.video_source
            w, h = video_source.resolution
            fps = video_source.fps or 20.0

            writer = _create_video_writer(w, h, fps, video_path)
            state.set_recording(active=True, path=video_path, writer=writer)

            logger.info(f"Grabación iniciada: {video_path}")
            return jsonify({"status": "recording", "path": video_path})

        except Exception as e:
            logger.error(f"Error iniciando grabación: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/recording/stop", methods=["POST"])
    def recording_stop():
        if not state.recording_active:
            return jsonify({"status": "not_recording"})

        info = state.get_recording_info()
        state.close_video_writer()

        logger.info(f"Grabación detenida: {info['path']}")
        return jsonify({
            "status": "stopped",
            "path": info["path"],
            "duration": info.get("duration", 0),
        })

    @app.route("/api/recording/status")
    def recording_status():
        return jsonify(state.get_recording_info())

    # ── Sesiones ──

    @app.route("/api/sessions")
    def get_sessions():
        storage = container.storage
        if not storage:
            return jsonify({"sessions": []})

        sessions = storage.get_sessions(limit=50)
        # Marcar la sesión activa
        active_id = state.session_id
        for s in sessions:
            s["active"] = (s["id"] == active_id)
        return jsonify({"sessions": sessions})

    @app.route("/api/sessions/<session_id>", methods=["DELETE"])
    def delete_session(session_id: str):
        """Elimina una sesión completa (BD + archivos). No permite borrar la sesión activa."""
        # No permitir borrar la sesión activa
        if session_id == state.session_id:
            return jsonify({"status": "error", "message": "No se puede eliminar la sesión activa"}), 400

        storage = container.storage
        if not storage:
            return jsonify({"status": "error", "message": "Storage no disponible"}), 500

        ok = storage.delete_session(session_id)
        if ok:
            return jsonify({"status": "deleted"})
        return jsonify({"status": "error", "message": "Error al eliminar sesión"}), 500

    @app.route("/api/sessions/<session_id>/captures")
    def get_session_captures(session_id: str):
        """Retorna capturas de una sesión específica (desde el pipeline en memoria + DB)."""
        # Primero intentar las capturas en memoria (sesión activa)
        if session_id == state.session_id:
            return jsonify({"captures": pipeline.get_recent_captures(limit=50)})

        # Para sesiones cerradas, usar la BD
        storage = container.storage
        if not storage:
            return jsonify({"captures": []})

        detections = storage.get_session_detections(session_id, limit=50)
        # Convertir a formato compatible con el frontend
        captures = []
        for det in detections:
            cap = {
                "id": det["id"],
                "type": "face" if det["type"] in ("FACE", "PERSON") else "plate",
                "label": det.get("type", ""),
                "timestamp": det.get("timestamp", ""),
                "confidence": det.get("confidence", 0),
            }
            # Cargar imágenes como base64
            if det.get("image_path"):
                img_path = Path(det["image_path"])
                if img_path.exists():
                    with open(img_path, "rb") as f:
                        cap["close_up"] = base64.b64encode(f.read()).decode()
            if det.get("context_image_path"):
                ctx_path = Path(det["context_image_path"])
                if ctx_path.exists():
                    with open(ctx_path, "rb") as f:
                        cap["context"] = base64.b64encode(f.read()).decode()
            captures.append(cap)

        return jsonify({"captures": captures})

    @app.route("/api/sessions/<session_id>/videos")
    def get_session_videos(session_id: str):
        """Lista los archivos de video de una sesión (excluye los en grabación)."""
        video_dir = _get_session_folder(session_id) / "video"
        videos = []
        # Path del video que se está grabando activamente
        rec_info = state.get_recording_info()
        recording_path = rec_info.get("path", "") if rec_info.get("active") else ""

        if video_dir.exists():
            for vf in sorted(video_dir.glob("*.mp4"), reverse=True):
                # No listar el video que se está grabando (aún no se puede reproducir)
                if recording_path and str(vf) == recording_path:
                    continue
                stat = vf.stat()
                if stat.st_size == 0:
                    continue  # Ignorar archivos vacíos
                size_mb = round(stat.st_size / (1024 * 1024), 2)
                videos.append({
                    "filename": vf.name,
                    "path": f"/api/sessions/{session_id}/video/{vf.name}",
                    "size_mb": size_mb,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                })
        return jsonify({"videos": videos})

    @app.route("/api/sessions/<session_id>/video/<filename>")
    def serve_session_video(session_id: str, filename: str):
        """Sirve un archivo de video para reproducción en el navegador."""
        from flask import send_from_directory
        # Seguridad: solo permitir nombres de archivo simples
        if "/" in filename or "\\" in filename or ".." in filename:
            return jsonify({"error": "invalid filename"}), 400
        video_dir = (_get_session_folder(session_id) / "video").resolve()
        video_path = video_dir / filename
        if not video_path.exists():
            logger.warning(f"Video no encontrado: {video_path}")
            return jsonify({"error": "not found"}), 404
        return send_from_directory(str(video_dir), filename, mimetype="video/mp4")

    # ── Settings ──

    @app.route("/api/settings", methods=["GET"])
    def get_settings():
        config = container.config
        return jsonify({
            "camera": {
                "source": config.camera.source,
                "width": config.camera.width,
                "height": config.camera.height,
                "fps": config.camera.fps,
            },
            "detection": {
                "face_enabled": config.detection.face_enabled,
                "plate_enabled": config.detection.plate_enabled,
                "person_enabled": config.detection.person_enabled,
                "vehicle_enabled": config.detection.vehicle_enabled,
                "confidence_threshold": config.detection.confidence_threshold,
            },
            "storage": {
                "encryption_enabled": config.storage.encryption_enabled,
                "max_storage_mb": config.storage.max_storage_mb,
            },
            "ui": {
                "show_fps": config.ui.show_fps,
                "show_bounding_boxes": config.ui.show_bounding_boxes,
            },
        })

    @app.route("/api/settings", methods=["POST"])
    def save_settings():
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "No data"}), 400

            config = container.config

            # Actualizar config en memoria
            if "camera" in data:
                cam = data["camera"]
                config.camera.source = cam.get("source", config.camera.source)
                config.camera.width = cam.get("width", config.camera.width)
                config.camera.height = cam.get("height", config.camera.height)
                config.camera.fps = cam.get("fps", config.camera.fps)

            if "detection" in data:
                det = data["detection"]
                config.detection.face_enabled = det.get("face_enabled", config.detection.face_enabled)
                config.detection.plate_enabled = det.get("plate_enabled", config.detection.plate_enabled)
                config.detection.person_enabled = det.get("person_enabled", config.detection.person_enabled)
                config.detection.vehicle_enabled = det.get("vehicle_enabled", config.detection.vehicle_enabled)
                config.detection.confidence_threshold = det.get(
                    "confidence_threshold", config.detection.confidence_threshold
                )

            if "storage" in data:
                sto = data["storage"]
                config.storage.encryption_enabled = sto.get("encryption_enabled", config.storage.encryption_enabled)
                config.storage.max_storage_mb = sto.get("max_storage_mb", config.storage.max_storage_mb)

            # Escribir a YAML
            config_path = Path(__file__).resolve().parent.parent.parent / "configs" / "settings.yaml"
            yaml_data = {
                "log_level": config.log_level,
                "camera": {
                    "source": config.camera.source,
                    "width": config.camera.width,
                    "height": config.camera.height,
                    "fps": config.camera.fps,
                    "buffer_size": config.camera.buffer_size,
                    "reconnect_attempts": config.camera.reconnect_attempts,
                    "reconnect_delay": config.camera.reconnect_delay,
                },
                "detection": {
                    "face_enabled": config.detection.face_enabled,
                    "plate_enabled": config.detection.plate_enabled,
                    "person_enabled": config.detection.person_enabled,
                    "vehicle_enabled": config.detection.vehicle_enabled,
                    "face_model": config.detection.face_model,
                    "plate_model": config.detection.plate_model,
                    "confidence_threshold": config.detection.confidence_threshold,
                    "face_min_size": config.detection.face_min_size,
                    "plate_min_size": config.detection.plate_min_size,
                    "tracking_iou_threshold": config.detection.tracking_iou_threshold,
                    "duplicate_cooldown": config.detection.duplicate_cooldown,
                },
                "storage": {
                    "database_path": config.storage.database_path,
                    "images_path": config.storage.images_path,
                    "encryption_enabled": config.storage.encryption_enabled,
                    "max_storage_mb": config.storage.max_storage_mb,
                    "rotation_threshold": config.storage.rotation_threshold,
                },
                "ui": {
                    "accent_color": config.ui.accent_color,
                    "show_fps": config.ui.show_fps,
                    "show_bounding_boxes": config.ui.show_bounding_boxes,
                },
            }

            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            logger.info(f"Configuración guardada en {config_path}")
            return jsonify({"status": "saved"})

        except Exception as e:
            logger.error(f"Error guardando settings: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    return app
