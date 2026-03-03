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
"""

from __future__ import annotations

import base64
import json
import logging
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import yaml
from flask import Flask, Response, jsonify, render_template, request

from src.core.config import AppConfig, load_config
from src.core.container import ServiceContainer
from src.core.events import EventBus
from src.core.interfaces import BoundingBox, Detection, DetectionType
from src.capture.frame_buffer import FrameBuffer

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  Globals compartidos entre threads
# ═══════════════════════════════════════════════════════════════

_latest_frame: Optional[np.ndarray] = None
_latest_frame_lock = threading.Lock()
_latest_detections: list[Detection] = []
_detections_lock = threading.Lock()
_detection_history: deque = deque(maxlen=50)
_known_person_ids: set = set()     # IDs de personas ya registradas en el historial
_unique_faces: int = 0             # Contador de personas únicas
_unique_plates: int = 0            # Contador de placas únicas
_recent_captures: deque = deque(maxlen=30)  # Capturas recientes con pares de imágenes
_camera_active = False
_camera_info: dict = {}
_capture_thread: Optional[threading.Thread] = None
_detection_worker = None  # DetectionWorkerWeb, set in create_app()
_frame_buffer: Optional[FrameBuffer] = None
_container: Optional[ServiceContainer] = None
_fps_counter: float = 0.0
_start_time: float = 0.0


# ═══════════════════════════════════════════════════════════════
#  Detection Worker (thread secundario de IA)
# ═══════════════════════════════════════════════════════════════

class DetectionWorkerWeb:
    """Ejecuta detección de IA en thread secundario."""

    def __init__(self, container: ServiceContainer, frame_buffer: FrameBuffer) -> None:
        self._container = container
        self._frame_buffer = frame_buffer
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._loop, name="DetectionWorkerWeb", daemon=True
        )
        self._thread.start()
        logger.info("DetectionWorkerWeb iniciado (modelos se cargan en background).")

    def _load_models(self) -> None:
        """Carga modelos en el thread de detección (no bloquea el request HTTP)."""
        for detector in self._container.detectors:
            try:
                detector.load_model()
                logger.info(f"  ✓ {detector.name} cargado")
            except Exception as e:
                logger.error(f"  ✗ {detector.name}: {e}")

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    @property
    def is_running(self) -> bool:
        return self._running

    def _loop(self) -> None:
        global _latest_detections, _detection_history, _recent_captures
        global _known_person_ids, _unique_faces, _unique_plates

        # Cargar modelos en este thread (no bloquea el request HTTP)
        logger.info("Cargando modelos de detección en background...")
        self._load_models()
        logger.info("Modelos listos. Iniciando detección.")

        detectors = self._container.detectors
        storage = self._container.storage

        while self._running:
            frame = self._frame_buffer.get(timeout=0.1)
            if frame is None:
                continue

            h, w = frame.shape[:2]

            # ── Paso 1: Ejecutar detectores ──
            faces = []
            plates = []
            vehicles = []

            for det in detectors:
                if not det.is_loaded:
                    continue
                try:
                    results = det.detect(frame)
                    for d in results:
                        if d.detection_type == DetectionType.FACE:
                            faces.append(d)
                        elif d.detection_type == DetectionType.PLATE:
                            plates.append(d)
                        elif d.detection_type == DetectionType.VEHICLE:
                            vehicles.append(d)
                except Exception as e:
                    logger.error(f"Error en {det.name}: {e}")

            all_dets = faces + plates + vehicles

            # ── Paso 2: Emparejar plate↔vehicle ──
            plate_vehicle_pairs = []
            for plate_det in plates:
                vehicle_crop = None
                best_vehicle = _find_best_overlap(plate_det.bbox, vehicles)

                if best_vehicle is not None:
                    vehicle_crop = best_vehicle.crop_image
                else:
                    # Sin vehículo detectado → vista amplia como contexto
                    vehicle_crop = _crop_wide_context(frame, plate_det.bbox, h, w, expand=5.0)

                plate_vehicle_pairs.append((plate_det, vehicle_crop))

            # ── Paso 3: Actualizar estado global ──
            with _detections_lock:
                _latest_detections = all_dets

                # Rostros: captura directa (solo el close-up)
                for face_det in faces:
                    person_id = face_det.metadata.get("person_id")
                    is_new_person = face_det.metadata.get("is_new_person", False)
                    should_capture = is_new_person  # PersonTracker ya decide cuándo capturar

                    # Registrar persona única si es nueva
                    if person_id is not None and person_id not in _known_person_ids:
                        _known_person_ids.add(person_id)
                        _unique_faces += 1

                    if should_capture:
                        _detection_history.appendleft({
                            "type": "face",
                            "label": face_det.label,
                            "confidence": round(face_det.confidence, 2),
                            "timestamp": time.strftime("%H:%M:%S"),
                        })

                        if storage:
                            try:
                                storage.save_detection(face_det)
                            except Exception as e:
                                logger.debug(f"Error guardando detección: {e}")

                        _add_capture(face_det, None, "face")

                # Placas: con imagen del vehículo como contexto
                for plate_det, vehicle_crop in plate_vehicle_pairs:
                    plate_text = plate_det.metadata.get("plate_text", "???")

                    # Solo descartar si no hay texto alguno (???)
                    if plate_text == "???" or not plate_text:
                        continue

                    # Para placas con texto real (OCR exitoso), usar texto como clave
                    # Para "DETECTADA" (YOLO sin OCR), usar timestamp para no agrupar
                    if plate_text == "DETECTADA":
                        plate_key = f"plate_detected_{time.time():.0f}"
                    else:
                        plate_key = f"plate_{plate_text}"

                    is_new = False
                    if plate_key not in _known_person_ids:
                        _known_person_ids.add(plate_key)
                        _unique_plates += 1
                        is_new = True

                    if is_new:
                        _detection_history.appendleft({
                            "type": "plate",
                            "label": plate_det.label,
                            "confidence": round(plate_det.confidence, 2),
                            "timestamp": time.strftime("%H:%M:%S"),
                        })

                        if storage:
                            try:
                                storage.save_detection(plate_det, context_image=vehicle_crop)
                            except Exception as e:
                                logger.debug(f"Error guardando detección: {e}")

                        _add_capture(plate_det, vehicle_crop, "plate")


# ═══════════════════════════════════════════════════════════════
#  Helpers de emparejamiento y captura
# ═══════════════════════════════════════════════════════════════

def _find_best_overlap(
    target_bbox: BoundingBox,
    candidates: list[Detection],
    min_overlap: float = 0.1,
) -> Optional[Detection]:
    """
    Encuentra la detección candidata que mejor contiene al target.

    Usa IoU para medir overlap. Para face→person, el face bbox
    debería estar contenido dentro del person bbox.
    """
    best = None
    best_score = min_overlap

    for cand in candidates:
        # Calcular qué fracción del target está dentro del candidato
        ix1 = max(target_bbox.x1, cand.bbox.x1)
        iy1 = max(target_bbox.y1, cand.bbox.y1)
        ix2 = min(target_bbox.x2, cand.bbox.x2)
        iy2 = min(target_bbox.y2, cand.bbox.y2)

        if ix2 <= ix1 or iy2 <= iy1:
            continue

        inter = (ix2 - ix1) * (iy2 - iy1)
        target_area = target_bbox.area
        if target_area <= 0:
            continue

        # Fracción del target contenida en el candidato
        containment = inter / target_area
        if containment > best_score:
            best_score = containment
            best = cand

    return best


def _crop_wide_context(
    frame: np.ndarray,
    bbox: BoundingBox,
    h: int,
    w: int,
    expand: float = 3.0,
) -> Optional[np.ndarray]:
    """
    Captura una vista amplia del frame centrada en el bbox.

    expand=3.0 significa que el crop será 3x más grande que el bbox
    en cada dirección. Si el bbox es muy grande (>40% del frame),
    simplemente retorna el frame completo.
    """
    # Si el bbox ya cubre mucho del frame, devolver frame completo
    if bbox.area > 0.15:
        return frame.copy()

    cx, cy = bbox.center
    bw, bh = bbox.width, bbox.height

    # Expandir proporcionalmente
    half_w = max(bw * expand, 0.25)  # Mínimo 25% del ancho del frame
    half_h = max(bh * expand, 0.30)  # Mínimo 30% del alto del frame

    x1 = max(0, int((cx - half_w) * w))
    y1 = max(0, int((cy - half_h) * h))
    x2 = min(w, int((cx + half_w) * w))
    y2 = min(h, int((cy + half_h) * h))

    if x2 <= x1 or y2 <= y1:
        return frame.copy()

    return frame[y1:y2, x1:x2].copy()


def _add_capture(detection: Detection, context_image: Optional[np.ndarray], det_type: str) -> None:
    """Agrega una captura a la lista reciente (para la galería web)."""

    capture = {
        "type": det_type,
        "label": detection.label,
        "confidence": round(detection.confidence, 2),
        "timestamp": time.strftime("%H:%M:%S"),
        "person_id": detection.metadata.get("person_id"),
        "close_up": None,
        "context": None,
    }

    # Codificar close-up (cara o placa) a base64 para enviar al frontend
    if detection.crop_image is not None and detection.crop_image.size > 0:
        try:
            _, buf = cv2.imencode('.jpg', detection.crop_image, [cv2.IMWRITE_JPEG_QUALITY, 80])
            capture["close_up"] = base64.b64encode(buf).decode('ascii')
        except Exception:
            pass

    # Codificar contexto (cuerpo o vehículo) a base64
    if context_image is not None and context_image.size > 0:
        try:
            # Redimensionar contexto para no enviar imágenes enormes
            ctx_h, ctx_w = context_image.shape[:2]
            max_dim = 600
            if max(ctx_h, ctx_w) > max_dim:
                scale = max_dim / max(ctx_h, ctx_w)
                context_image = cv2.resize(context_image, None, fx=scale, fy=scale)

            _, buf = cv2.imencode('.jpg', context_image, [cv2.IMWRITE_JPEG_QUALITY, 80])
            capture["context"] = base64.b64encode(buf).decode('ascii')
        except Exception:
            pass

    _recent_captures.appendleft(capture)


# ═══════════════════════════════════════════════════════════════
#  Capture Thread (captura de cámara en background)
# ═══════════════════════════════════════════════════════════════

def _capture_loop() -> None:
    """
    Lee frames de la cámara en un thread dedicado.
    Almacena el último frame para MJPEG y envía al FrameBuffer para IA.
    """
    global _latest_frame, _camera_active, _fps_counter, _camera_info

    video_source = _container.video_source
    frame_count = 0
    loop_start = time.time()

    while _camera_active and video_source and video_source.is_active():
        frame = video_source.read_frame()

        if frame is not None:
            frame_count += 1

            # Guardar frame para el stream MJPEG
            with _latest_frame_lock:
                _latest_frame = frame

            # Enviar al detection worker cada 3 frames
            if _frame_buffer and frame_count % 3 == 0:
                _frame_buffer.put(frame)

            # FPS
            elapsed = time.time() - loop_start
            if elapsed > 0:
                _fps_counter = frame_count / elapsed

        elif not video_source.is_active():
            logger.warning("Cámara desconectada en capture thread.")
            break

        # Pequeña pausa para no saturar el CPU
        time.sleep(0.001)

    _camera_active = False
    logger.info(f"Capture thread finalizado. Frames: {frame_count}")


# ═══════════════════════════════════════════════════════════════
#  MJPEG Generator
# ═══════════════════════════════════════════════════════════════

def _generate_mjpeg():
    """
    Generador MJPEG: encode a JPEG y yield como multipart stream.
    Este es el patrón estándar de streaming que usan las cámaras IP.
    """
    while True:
        with _latest_frame_lock:
            frame = _latest_frame

        if frame is None:
            time.sleep(0.03)
            continue

        # Dibujar detecciones sobre el frame
        display = frame.copy()
        with _detections_lock:
            dets = list(_latest_detections)

        if dets:
            display = _draw_detections(display, dets)

        # Overlay de FPS
        cv2.putText(
            display,
            f"FPS: {_fps_counter:.0f}",
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
        DetectionType.FACE: (191, 90, 242),   # Púrpura
        DetectionType.PLATE: (255, 210, 100),  # Amarillo
        DetectionType.PERSON: (48, 209, 88),   # Verde
        DetectionType.VEHICLE: (100, 210, 255), # Cyan
    }

    for det in detections:
        x1, y1, x2, y2 = det.bbox.to_absolute(w, h)
        color = colors_map.get(det.detection_type, (255, 255, 255))

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

        label = det.label  # Ya incluye tipo + confianza/texto
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 8, y1), color, -1)
        cv2.putText(
            frame, label, (x1 + 4, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA,
        )

    return frame


# ═══════════════════════════════════════════════════════════════
#  Flask App Factory
# ═══════════════════════════════════════════════════════════════

def create_app(container: ServiceContainer) -> Flask:
    """Crea y configura la aplicación Flask."""
    global _container, _frame_buffer, _detection_worker

    _container = container
    _frame_buffer = FrameBuffer(max_size=5)
    _detection_worker = DetectionWorkerWeb(container, _frame_buffer)

    template_dir = Path(__file__).parent / "templates"
    static_dir = Path(__file__).parent / "static"

    app = Flask(
        __name__,
        template_folder=str(template_dir),
        static_folder=str(static_dir),
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
            _generate_mjpeg(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/api/camera/start", methods=["POST"])
    def camera_start():
        global _camera_active, _capture_thread, _start_time
        if _camera_active:
            return jsonify({"status": "already_active"})

        try:
            # Cargar modelos si no están cargados
            if not _detection_worker.is_running:
                logger.info("Pre-cargando modelos de detección...")
                _detection_worker.start()

            # Iniciar cámara
            video_source = container.video_source
            video_source.start()
            _camera_active = True
            _start_time = time.time()

            # Info de cámara
            global _camera_info
            _camera_info = {
                "resolution": f"{video_source.resolution[0]}x{video_source.resolution[1]}",
                "fps": video_source.fps,
                "device": str(container.config.camera.source),
            }

            # Lanzar capture thread
            _capture_thread = threading.Thread(
                target=_capture_loop, name="CaptureThread", daemon=True
            )
            _capture_thread.start()

            logger.info(f"Cámara iniciada: {_camera_info}")
            return jsonify({"status": "started", "camera": _camera_info})

        except Exception as e:
            _camera_active = False
            logger.error(f"Error iniciando cámara: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/camera/stop", methods=["POST"])
    def camera_stop():
        global _camera_active, _latest_frame, _known_person_ids, _unique_faces, _unique_plates
        if not _camera_active:
            return jsonify({"status": "already_stopped"})

        _camera_active = False

        # Esperar a que el capture thread termine
        if _capture_thread and _capture_thread.is_alive():
            _capture_thread.join(timeout=3.0)

        # Detener cámara
        video_source = container.video_source
        if video_source:
            video_source.stop()

        with _latest_frame_lock:
            _latest_frame = None

        _frame_buffer.clear()
        logger.info("Cámara detenida.")
        return jsonify({"status": "stopped"})

    @app.route("/api/camera/status")
    def camera_status():
        uptime = 0
        if _camera_active and _start_time > 0:
            uptime = int(time.time() - _start_time)

        return jsonify({
            "active": _camera_active,
            "camera": _camera_info if _camera_active else {},
            "fps": round(_fps_counter, 1),
            "uptime": uptime,
            "unique_faces": _unique_faces,
            "unique_plates": _unique_plates,
        })

    @app.route("/api/detections")
    def get_detections():
        with _detections_lock:
            history = list(_detection_history)
        return jsonify({
            "detections": history[:20],
            "unique_faces": _unique_faces,
            "unique_plates": _unique_plates,
        })

    @app.route("/api/captures")
    def get_captures():
        """Retorna las capturas recientes con pares de imágenes (base64)."""
        with _detections_lock:
            captures = list(_recent_captures)
        return jsonify({"captures": captures[:20]})

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
                    "theme": config.ui.theme,
                    "window_width": config.ui.window_width,
                    "window_height": config.ui.window_height,
                    "sidebar_width": config.ui.sidebar_width,
                    "font_family": config.ui.font_family,
                    "font_fallback": config.ui.font_fallback,
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
