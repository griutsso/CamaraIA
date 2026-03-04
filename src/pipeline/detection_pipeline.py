"""
Pipeline de detección unificado.

Consume frames del FrameBuffer, ejecuta detectores de IA,
empareja placas con vehículos, gestiona tracking de personas
y almacena resultados. Emite eventos para que la UI reaccione.

Reemplaza tanto DetectionWorker (headless) como
DetectionWorkerWeb (web) con un pipeline configurable.
"""

from __future__ import annotations

import base64
import logging
import threading
import time
import uuid
from collections import deque
from typing import Any, Callable, Optional

import cv2
import numpy as np

from src.capture.frame_buffer import FrameBuffer
from src.core.container import ServiceContainer
from src.core.events import EventBus
from src.core.interfaces import BoundingBox, Detection, DetectionType

logger = logging.getLogger(__name__)

# Tipo para callback de detecciones procesadas
OnDetectionsCallback = Callable[[dict[str, Any]], None]


class DetectionPipeline:
    """
    Pipeline unificado de detección de IA.

    Ejecuta en un thread secundario:
      1. Consume frames del FrameBuffer
      2. Ejecuta detectores (rostros, placas, objetos)
      3. Empareja placas ↔ vehículos
      4. Tracking + deduplicación de personas
      5. Almacena en storage con imágenes de contexto
      6. Emite eventos via EventBus

    Args:
        container: ServiceContainer con detectores, storage y event_bus.
        frame_buffer: FrameBuffer del que consumir frames.
        encode_base64: Si True, incluye imágenes base64 en los eventos
                       (necesario para la UI web, innecesario en headless).
    """

    def __init__(
        self,
        container: ServiceContainer,
        frame_buffer: FrameBuffer,
        encode_base64: bool = False,
    ) -> None:
        self._container = container
        self._event_bus = container.event_bus
        self._frame_buffer = frame_buffer
        self._encode_base64 = encode_base64

        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Estado interno de tracking (protegido por lock)
        self._state_lock = threading.Lock()
        self._known_person_ids: set[Any] = set()
        self._unique_faces: int = 0
        self._unique_plates: int = 0
        self._detection_history: deque[dict] = deque(maxlen=50)
        self._recent_captures: deque[dict] = deque(maxlen=30)

        # Métricas
        self._fps_counter: float = 0.0
        self._frame_count: int = 0

    # ── Propiedades (thread-safe) ──

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def fps(self) -> float:
        return self._fps_counter

    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas actuales del pipeline."""
        with self._state_lock:
            return {
                "unique_faces": self._unique_faces,
                "unique_plates": self._unique_plates,
                "fps": round(self._fps_counter, 1),
                "frames_processed": self._frame_count,
            }

    def get_detection_history(self, limit: int = 20) -> list[dict]:
        """Retorna historial reciente de detecciones."""
        with self._state_lock:
            return list(self._detection_history)[:limit]

    def get_recent_captures(self, limit: int = 20) -> list[dict]:
        """Retorna capturas recientes con imágenes."""
        with self._state_lock:
            return list(self._recent_captures)[:limit]

    def remove_capture(self, capture_id: str) -> bool:
        """Elimina una captura de la cache en memoria por su ID."""
        with self._state_lock:
            for i, cap in enumerate(self._recent_captures):
                if cap.get("id") == capture_id:
                    del self._recent_captures[i]
                    return True
        return False

    # ── Ciclo de vida ──

    def start(self) -> None:
        """Inicia el pipeline en un thread secundario."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._pipeline_loop,
            name="DetectionPipeline",
            daemon=True,
        )
        self._thread.start()
        logger.info("DetectionPipeline iniciado.")

    def stop(self) -> None:
        """Detiene el pipeline."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info("DetectionPipeline detenido.")

    def reset_tracking(self) -> None:
        """Limpia el estado de tracking (al reiniciar cámara)."""
        with self._state_lock:
            self._known_person_ids.clear()
            self._unique_faces = 0
            self._unique_plates = 0
            self._detection_history.clear()
            self._recent_captures.clear()
            self._frame_count = 0
            self._fps_counter = 0.0

    # ── Loop principal ──

    def _pipeline_loop(self) -> None:
        """Loop principal: carga modelos → consume frames → detecta → almacena."""
        detectors = self._container.detectors
        storage = self._container.storage

        # Pre-cargar modelos (puede tardar)
        logger.info("Cargando modelos de detección...")
        for detector in detectors:
            try:
                detector.load_model()
                logger.info(f"  ✓ {detector.name} cargado")
            except Exception as e:
                logger.error(f"  ✗ {detector.name}: {e}")
        logger.info("Modelos listos. Pipeline activo.")

        while self._running:
            frame = self._frame_buffer.get(timeout=0.1)
            if frame is None:
                continue

            loop_start = time.time()
            h, w = frame.shape[:2]

            # ── Paso 1: Ejecutar detectores ──
            faces, plates, persons, vehicles = self._run_detectors(frame, detectors)
            all_detections = faces + plates + persons + vehicles

            # ── Paso 2: Emparejar placas ↔ vehículos ──
            plate_vehicle_pairs = self._match_plates_to_vehicles(
                plates, vehicles, frame, h, w
            )

            # ── Paso 2b: Emparejar rostros ↔ personas ──
            face_person_pairs = self._match_faces_to_persons(
                faces, persons, frame, h, w
            )

            # ── Paso 3: Procesar rostros (tracking + captura) ──
            self._process_faces(face_person_pairs, storage)

            # ── Paso 4: Procesar placas (deduplicación + captura) ──
            self._process_plates(plate_vehicle_pairs, storage)

            # ── Paso 5: Emitir evento con resultados ──
            self._frame_count += 1
            elapsed = time.time() - loop_start
            self._fps_counter = 1.0 / max(elapsed, 0.001)

            self._event_bus.emit(EventBus.FRAME_PROCESSED, {
                "frame": frame,
                "detections": all_detections,
                "fps": self._fps_counter,
            })

    # ── Detección ──

    @staticmethod
    def _run_detectors(
        frame: np.ndarray,
        detectors: list,
    ) -> tuple[list[Detection], list[Detection], list[Detection], list[Detection]]:
        """Ejecuta todos los detectores y clasifica resultados por tipo."""
        faces: list[Detection] = []
        plates: list[Detection] = []
        persons: list[Detection] = []
        vehicles: list[Detection] = []

        for detector in detectors:
            if not detector.is_loaded:
                continue
            try:
                results = detector.detect(frame)
                for det in results:
                    if det.detection_type == DetectionType.FACE:
                        faces.append(det)
                    elif det.detection_type == DetectionType.PLATE:
                        plates.append(det)
                    elif det.detection_type == DetectionType.PERSON:
                        persons.append(det)
                    elif det.detection_type == DetectionType.VEHICLE:
                        vehicles.append(det)
            except Exception as e:
                logger.error(f"Error en {detector.name}: {e}")

        return faces, plates, persons, vehicles

    # ── Matching rostro ↔ persona ──

    def _match_faces_to_persons(
        self,
        faces: list[Detection],
        persons: list[Detection],
        frame: np.ndarray,
        h: int,
        w: int,
    ) -> list[tuple[Detection, Optional[np.ndarray]]]:
        """Empareja cada rostro con su persona (cuerpo completo) o genera contexto amplio."""
        pairs = []
        for face_det in faces:
            best_person = _find_best_overlap(face_det.bbox, persons)

            if best_person is not None:
                # Recortar del frame con padding para mostrar persona completa en contexto
                person_crop = _crop_bbox_with_padding(frame, best_person.bbox, h, w, padding=0.15)
            else:
                # Fallback: estimar cuerpo completo desde la posición del rostro
                person_crop = _crop_person_context(frame, face_det.bbox, h, w)

            pairs.append((face_det, person_crop))
        return pairs

    # ── Matching placa ↔ vehículo ──

    def _match_plates_to_vehicles(
        self,
        plates: list[Detection],
        vehicles: list[Detection],
        frame: np.ndarray,
        h: int,
        w: int,
    ) -> list[tuple[Detection, Optional[np.ndarray]]]:
        """Empareja cada placa con su vehículo o genera contexto amplio."""
        pairs = []
        for plate_det in plates:
            vehicle_crop = None
            best_vehicle = _find_best_overlap(plate_det.bbox, vehicles)

            if best_vehicle is not None:
                vehicle_crop = best_vehicle.crop_image
            else:
                vehicle_crop = _crop_wide_context(frame, plate_det.bbox, h, w, expand=5.0)

            pairs.append((plate_det, vehicle_crop))
        return pairs

    # ── Procesamiento de rostros ──

    def _process_faces(
        self,
        face_person_pairs: list[tuple[Detection, Optional[np.ndarray]]],
        storage: Optional[Any],
    ) -> None:
        """Procesa rostros: tracking, deduplicación, emparejamiento con persona y almacenamiento."""
        with self._state_lock:
            for face_det, person_crop in face_person_pairs:
                person_id = face_det.metadata.get("person_id")
                is_new_person = face_det.metadata.get("is_new_person", False)

                # Registrar persona única
                if person_id is not None and person_id not in self._known_person_ids:
                    self._known_person_ids.add(person_id)
                    self._unique_faces += 1

                if is_new_person:
                    self._detection_history.appendleft({
                        "type": "face",
                        "label": face_det.label,
                        "confidence": round(face_det.confidence, 2),
                        "timestamp": time.strftime("%H:%M:%S"),
                    })

                    detection_id = None
                    if storage:
                        try:
                            detection_id = storage.save_detection(face_det, context_image=person_crop)
                        except Exception as e:
                            logger.debug(f"Error guardando rostro: {e}")

                    self._add_capture(face_det, person_crop, "face", capture_id=detection_id)

    # ── Procesamiento de placas ──

    def _process_plates(
        self,
        plate_vehicle_pairs: list[tuple[Detection, Optional[np.ndarray]]],
        storage: Optional[Any],
    ) -> None:
        """Procesa placas: deduplicación por texto y almacenamiento."""
        with self._state_lock:
            for plate_det, vehicle_crop in plate_vehicle_pairs:
                plate_text = plate_det.metadata.get("plate_text", "???")

                if plate_text == "???" or not plate_text:
                    continue

                # Clave de deduplicación
                if plate_text == "DETECTADA":
                    plate_key = f"plate_detected_{time.time():.0f}"
                else:
                    plate_key = f"plate_{plate_text}"

                is_new = plate_key not in self._known_person_ids
                if is_new:
                    self._known_person_ids.add(plate_key)
                    self._unique_plates += 1

                    self._detection_history.appendleft({
                        "type": "plate",
                        "label": plate_det.label,
                        "confidence": round(plate_det.confidence, 2),
                        "timestamp": time.strftime("%H:%M:%S"),
                    })

                    detection_id = None
                    if storage:
                        try:
                            detection_id = storage.save_detection(plate_det, context_image=vehicle_crop)
                        except Exception as e:
                            logger.debug(f"Error guardando placa: {e}")

                    self._add_capture(plate_det, vehicle_crop, "plate", capture_id=detection_id)

    # ── Capturas para galería ──

    def _add_capture(
        self,
        detection: Detection,
        context_image: Optional[np.ndarray],
        det_type: str,
        capture_id: Optional[str] = None,
    ) -> None:
        """Añade una captura a la lista reciente (para la galería web)."""
        capture: dict[str, Any] = {
            "id": capture_id or str(uuid.uuid4())[:12],
            "type": det_type,
            "label": detection.label,
            "confidence": round(detection.confidence, 2),
            "timestamp": time.strftime("%H:%M:%S"),
            "person_id": detection.metadata.get("person_id"),
            "close_up": None,
            "context": None,
        }

        if self._encode_base64:
            capture["close_up"] = _encode_image_base64(detection.crop_image)
            capture["context"] = _encode_image_base64(context_image, max_dim=600)

        self._recent_captures.appendleft(capture)


# ═══════════════════════════════════════════════════════════════
#  Helpers (funciones puras, sin estado)
# ═══════════════════════════════════════════════════════════════

def _find_best_overlap(
    target_bbox: BoundingBox,
    candidates: list[Detection],
    min_overlap: float = 0.1,
) -> Optional[Detection]:
    """
    Encuentra la detección candidata que mejor contiene al target.
    Usa containment ratio (fracción del target dentro del candidato).
    """
    best = None
    best_score = min_overlap

    for cand in candidates:
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
    """Captura una vista amplia del frame centrada en el bbox."""
    if bbox.area > 0.15:
        return frame.copy()

    cx, cy = bbox.center
    bw, bh = bbox.width, bbox.height

    half_w = max(bw * expand, 0.25)
    half_h = max(bh * expand, 0.30)

    x1 = max(0, int((cx - half_w) * w))
    y1 = max(0, int((cy - half_h) * h))
    x2 = min(w, int((cx + half_w) * w))
    y2 = min(h, int((cy + half_h) * h))

    if x2 <= x1 or y2 <= y1:
        return frame.copy()

    return frame[y1:y2, x1:x2].copy()


def _crop_bbox_with_padding(
    frame: np.ndarray,
    bbox: BoundingBox,
    h: int,
    w: int,
    padding: float = 0.15,
) -> Optional[np.ndarray]:
    """
    Recorta del frame el área del bbox con padding proporcional alrededor.
    Útil para mostrar la persona completa con algo de contexto visual.
    """
    bw, bh = bbox.width, bbox.height
    pad_x = bw * padding
    pad_y = bh * padding

    x1 = max(0, int((bbox.x1 - pad_x) * w))
    y1 = max(0, int((bbox.y1 - pad_y) * h))
    x2 = min(w, int((bbox.x2 + pad_x) * w))
    y2 = min(h, int((bbox.y2 + pad_y) * h))

    if x2 <= x1 or y2 <= y1:
        return frame.copy()

    return frame[y1:y2, x1:x2].copy()


def _crop_person_context(
    frame: np.ndarray,
    face_bbox: BoundingBox,
    h: int,
    w: int,
) -> Optional[np.ndarray]:
    """
    Genera un recorte estimado del cuerpo completo a partir del rostro.

    Heurística: el rostro ocupa ~1/8 de la altura total de una persona.
    Expandimos generosamente hacia abajo y a los lados para capturar
    el cuerpo completo (cabeza a pies) con contexto.
    """
    cx, cy = face_bbox.center
    fw, fh = face_bbox.width, face_bbox.height

    # Expandir: 3x a cada lado en horizontal, 1.5x arriba y 8x abajo
    half_w = max(fw * 3.0, 0.15)
    top_expand = fh * 1.5
    bottom_expand = fh * 8.0

    x1 = max(0, int((cx - half_w) * w))
    y1 = max(0, int((cy - top_expand) * h))
    x2 = min(w, int((cx + half_w) * w))
    y2 = min(h, int((cy + bottom_expand) * h))

    if x2 <= x1 or y2 <= y1:
        return frame.copy()

    return frame[y1:y2, x1:x2].copy()


def _encode_image_base64(
    image: Optional[np.ndarray],
    quality: int = 80,
    max_dim: int = 0,
) -> Optional[str]:
    """Codifica una imagen a base64 JPEG para enviar al frontend."""
    if image is None or image.size == 0:
        return None

    try:
        img = image
        if max_dim > 0:
            ih, iw = img.shape[:2]
            if max(ih, iw) > max_dim:
                scale = max_dim / max(ih, iw)
                img = cv2.resize(img, None, fx=scale, fy=scale)

        _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return base64.b64encode(buf).decode('ascii')
    except Exception:
        return None
