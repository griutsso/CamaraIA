"""
Módulo de Detección de Rostros.

Jerarquía de backends:
  1. YOLO-face (si el modelo .pt existe)
  2. MediaPipe Face Detection (si mediapipe.solutions está disponible)
  3. OpenCV DNN SSD ResNet-10 (auto-descarga modelo ~10MB, muy preciso)

Sistema de tracking:
  - Batch matching: procesa TODAS las caras del frame a la vez
  - Garantiza que cada persona solo se asigna a UNA detección por frame
  - Re-identificación por histograma HSV cuando se pierde el tracking
  - Metadata "is_new_person" indica si debe capturarse screenshot
"""

from __future__ import annotations

import logging
import time
import urllib.request
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from src.core.interfaces import BoundingBox, Detection, DetectionType, IDetector

logger = logging.getLogger(__name__)

# URLs del modelo OpenCV DNN
_DNN_PROTOTXT_URL = (
    "https://raw.githubusercontent.com/opencv/opencv/master/"
    "samples/dnn/face_detector/deploy.prototxt"
)
_DNN_CAFFEMODEL_URL = (
    "https://raw.githubusercontent.com/opencv/opencv_3rdparty/"
    "dnn_samples_face_detector_20170830/"
    "res10_300x300_ssd_iter_140000.caffemodel"
)


# ═══════════════════════════════════════════════════════════════
#  Tracking y Re-identificación
# ═══════════════════════════════════════════════════════════════

class TrackedPerson:
    """Representa una persona rastreada a lo largo del tiempo."""

    def __init__(self, person_id: int, bbox: BoundingBox, histogram: np.ndarray) -> None:
        self.person_id = person_id
        self.bbox = bbox
        self.histogram = histogram
        self.first_seen = time.time()
        self.last_seen = time.time()
        self.last_capture_time = time.time()
        self.frame_count = 0
        self.is_active = True
        self.was_lost = False

    @property
    def center(self) -> tuple[float, float]:
        return self.bbox.center

    def update(self, bbox: BoundingBox, histogram: np.ndarray) -> None:
        """Actualiza posición y apariencia."""
        now = time.time()
        if now - self.last_seen > 3.0:
            self.was_lost = True
        self.bbox = bbox
        self.last_seen = now
        self.frame_count += 1
        self.is_active = True
        # Suavizar histograma (moving average)
        self.histogram = 0.7 * self.histogram + 0.3 * histogram


class PersonTracker:
    """
    Sistema de tracking + re-identificación con BATCH MATCHING.

    Procesa TODAS las detecciones de un frame a la vez para garantizar
    que cada persona conocida se asigna a máximo UNA detección.
    Esto evita que dos caras distintas reciban el mismo ID.
    """

    def __init__(
        self,
        max_center_distance: float = 0.12,
        histogram_threshold: float = 0.65,
        position_hist_threshold: float = 0.20,
        lost_timeout: float = 8.0,
        person_expiry: float = 600.0,
    ) -> None:
        self._max_center_dist = max_center_distance
        self._hist_threshold = histogram_threshold
        self._pos_hist_threshold = position_hist_threshold
        self._lost_timeout = lost_timeout
        self._person_expiry = person_expiry
        self._persons: dict[int, TrackedPerson] = {}
        self._next_id = 0

    @property
    def unique_count(self) -> int:
        return self._next_id

    @property
    def active_count(self) -> int:
        now = time.time()
        return sum(1 for p in self._persons.values() if now - p.last_seen < 2.0)

    def match_batch(self, detections: list[tuple[BoundingBox, np.ndarray]]) -> list[tuple[int, bool]]:
        """
        Asigna IDs a TODAS las detecciones del frame simultáneamente.
        Garantiza que cada persona existente solo se asigna una vez.

        Args:
            detections: lista de (bbox, face_crop) para cada cara detectada

        Returns:
            lista de (person_id, should_capture) en el mismo orden
        """
        now = time.time()
        self._cleanup(now)

        if not detections:
            return []

        recapture_interval = 60.0
        n_dets = len(detections)

        # Pre-calcular histogramas de todas las detecciones
        histograms = [self._compute_histogram(crop) for _, crop in detections]

        # IDs ya asignados en este frame (evita duplicados)
        used_pids: set[int] = set()
        # Resultado: det_idx → (pid, should_capture)
        assignments: dict[int, tuple[int, bool]] = {}

        # ════════════════════════════════════════════════
        # Paso 1: Match por posición + histograma
        # ════════════════════════════════════════════════
        # Construir TODAS las posibles parejas (det_idx, pid, dist, hist_sim)
        pos_candidates = []
        for det_idx, (bbox, _) in enumerate(detections):
            cx, cy = bbox.center
            for pid, person in self._persons.items():
                if now - person.last_seen > self._lost_timeout:
                    continue
                px, py = person.center
                dist = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
                if dist < self._max_center_dist:
                    hist_sim = self._compare_histograms(histograms[det_idx], person.histogram)
                    if hist_sim > self._pos_hist_threshold:
                        pos_candidates.append((det_idx, pid, dist, hist_sim))

        # Asignar greedily: mejor match primero (menor distancia)
        pos_candidates.sort(key=lambda x: x[2])
        for det_idx, pid, dist, hist_sim in pos_candidates:
            if det_idx in assignments or pid in used_pids:
                continue
            person = self._persons[pid]
            person.update(detections[det_idx][0], histograms[det_idx])

            should_capture = False
            if person.was_lost:
                should_capture = True
                person.was_lost = False
                person.last_capture_time = now
                logger.info(f"Persona #{pid} reapareció → captura")
            elif now - person.last_capture_time > recapture_interval:
                should_capture = True
                person.last_capture_time = now

            assignments[det_idx] = (pid, should_capture)
            used_pids.add(pid)

        # ════════════════════════════════════════════════
        # Paso 2: Re-ID por histograma (para caras sin match por posición)
        # ════════════════════════════════════════════════
        hist_candidates = []
        for det_idx in range(n_dets):
            if det_idx in assignments:
                continue
            for pid, person in self._persons.items():
                if pid in used_pids:
                    continue
                if now - person.last_seen > self._person_expiry:
                    continue
                sim = self._compare_histograms(histograms[det_idx], person.histogram)
                if sim > self._hist_threshold:
                    hist_candidates.append((det_idx, pid, sim))

        # Asignar greedily: mejor similitud primero
        hist_candidates.sort(key=lambda x: -x[2])
        for det_idx, pid, sim in hist_candidates:
            if det_idx in assignments or pid in used_pids:
                continue
            person = self._persons[pid]
            should_capture = (now - person.last_capture_time > recapture_interval)
            person.update(detections[det_idx][0], histograms[det_idx])
            if should_capture:
                person.last_capture_time = now
                logger.info(f"Persona #{pid} re-identificada (sim={sim:.2f}) → captura")
            assignments[det_idx] = (pid, should_capture)
            used_pids.add(pid)

        # ════════════════════════════════════════════════
        # Paso 3: Crear personas nuevas para detecciones sin match
        # ════════════════════════════════════════════════
        for det_idx in range(n_dets):
            if det_idx in assignments:
                continue
            pid = self._next_id
            self._next_id += 1
            bbox, crop = detections[det_idx]
            self._persons[pid] = TrackedPerson(pid, bbox, histograms[det_idx])
            logger.info(f"Nueva persona detectada: ID #{pid}")
            assignments[det_idx] = (pid, True)

        # Construir lista de resultados en orden
        return [assignments[i] for i in range(n_dets)]

    def _compute_histogram(self, face_crop: np.ndarray) -> np.ndarray:
        """Calcula histograma HSV normalizado del rostro."""
        try:
            if face_crop is None or face_crop.size == 0:
                return np.zeros(256, dtype=np.float32)

            hsv = cv2.cvtColor(face_crop, cv2.COLOR_BGR2HSV)
            hist_h = cv2.calcHist([hsv], [0], None, [180], [0, 180])
            hist_s = cv2.calcHist([hsv], [1], None, [76], [0, 256])

            hist = np.concatenate([hist_h, hist_s]).flatten().astype(np.float32)
            cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
            return hist
        except Exception:
            return np.zeros(256, dtype=np.float32)

    @staticmethod
    def _compare_histograms(h1: np.ndarray, h2: np.ndarray) -> float:
        """Compara dos histogramas usando correlación."""
        try:
            if h1.shape != h2.shape:
                return 0.0
            return float(cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL))
        except Exception:
            return 0.0

    def _cleanup(self, now: float) -> None:
        """Elimina personas expiradas."""
        expired = [
            pid for pid, p in self._persons.items()
            if now - p.last_seen > self._person_expiry
        ]
        for pid in expired:
            del self._persons[pid]


# ═══════════════════════════════════════════════════════════════
#  Detector Principal
# ═══════════════════════════════════════════════════════════════

class FaceDetector(IDetector):
    """
    Detector de rostros con backends intercambiables y
    tracking persistente de personas únicas.
    """

    def __init__(
        self,
        model_path: str = "models/yolov8n-face.pt",
        confidence_threshold: float = 0.5,
        min_face_size: int = 40,
        iou_threshold: float = 0.4,
        duplicate_cooldown: float = 3.0,
    ) -> None:
        self._model_path = model_path
        self._confidence_threshold = confidence_threshold
        self._min_face_size = min_face_size
        self._iou_threshold = iou_threshold
        self._duplicate_cooldown = duplicate_cooldown
        self._model = None
        self._mp_detector = None
        self._dnn_net = None
        self._backend = "none"
        self._is_loaded = False

        # Sistema de tracking con batch matching
        self._tracker = PersonTracker(
            max_center_distance=0.12,      # 12% del frame para posición
            histogram_threshold=0.65,       # Re-ID por apariencia: alto para no confundir
            position_hist_threshold=0.20,   # Confirmación mínima para match por posición
            lost_timeout=8.0,
            person_expiry=600.0,
        )

    @property
    def name(self) -> str:
        return "FaceDetector"

    @property
    def detection_type(self) -> DetectionType:
        return DetectionType.FACE

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def unique_persons(self) -> int:
        return self._tracker.unique_count

    @property
    def active_persons(self) -> int:
        return self._tracker.active_count

    def load_model(self) -> None:
        """Carga el mejor backend disponible."""
        model_file = Path(self._model_path)

        # Intento 1: YOLO-face
        if model_file.exists():
            try:
                from ultralytics import YOLO
                self._model = YOLO(str(model_file))
                self._backend = "yolo"
                self._is_loaded = True
                logger.info(f"✓ FaceDetector: YOLO cargado ({model_file.name})")
                return
            except ImportError:
                logger.warning("ultralytics no instalado.")
            except Exception as e:
                logger.warning(f"Error cargando YOLO: {e}")
        else:
            logger.info(f"Modelo YOLO no encontrado ({model_file}).")

        # Intento 2: MediaPipe
        try:
            import mediapipe as mp
            self._mp_detector = mp.solutions.face_detection.FaceDetection(
                model_selection=1,
                min_detection_confidence=self._confidence_threshold,
            )
            self._backend = "mediapipe"
            self._is_loaded = True
            logger.info("✓ FaceDetector: MediaPipe cargado")
            return
        except (ImportError, AttributeError) as e:
            logger.info(f"MediaPipe no disponible: {e}")
        except Exception as e:
            logger.warning(f"Error MediaPipe: {e}")

        # Intento 3: OpenCV DNN
        try:
            self._load_opencv_dnn()
            if self._dnn_net is not None:
                self._backend = "dnn"
                self._is_loaded = True
                logger.info("✓ FaceDetector: OpenCV DNN cargado (ResNet-10 SSD)")
                return
        except Exception as e:
            logger.warning(f"Error OpenCV DNN: {e}")

        logger.error(
            "⚠ FaceDetector: SIN BACKEND DISPONIBLE.\n"
            "  1. pip install mediapipe==0.10.14\n"
            "  2. Descargar modelo YOLO-face\n"
            "  3. Verificar internet (auto-descarga OpenCV DNN)"
        )
        self._backend = "none"
        self._is_loaded = True

    def _load_opencv_dnn(self) -> None:
        """Carga/descarga el detector OpenCV DNN."""
        models_dir = Path("models")
        models_dir.mkdir(parents=True, exist_ok=True)

        prototxt = models_dir / "deploy.prototxt"
        caffemodel = models_dir / "res10_300x300_ssd_iter_140000.caffemodel"

        if not prototxt.exists():
            logger.info("Descargando deploy.prototxt (~28KB)...")
            try:
                urllib.request.urlretrieve(_DNN_PROTOTXT_URL, str(prototxt))
            except Exception as e:
                logger.error(f"Error descargando prototxt: {e}")
                return

        if not caffemodel.exists():
            logger.info("Descargando modelo DNN rostros (~10MB, una sola vez)...")
            try:
                urllib.request.urlretrieve(_DNN_CAFFEMODEL_URL, str(caffemodel))
            except Exception as e:
                logger.error(f"Error descargando caffemodel: {e}")
                if prototxt.exists():
                    prototxt.unlink()
                return

        self._dnn_net = cv2.dnn.readNetFromCaffe(str(prototxt), str(caffemodel))

    def unload_model(self) -> None:
        if self._mp_detector:
            try:
                self._mp_detector.close()
            except Exception:
                pass
            self._mp_detector = None
        self._model = None
        self._dnn_net = None
        self._is_loaded = False
        self._backend = "none"
        logger.info("FaceDetector descargado.")

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Detecta rostros y los asocia con personas conocidas (batch)."""
        if not self._is_loaded or self._backend == "none":
            return []

        # Obtener detecciones brutas del backend
        if self._backend == "yolo":
            raw = self._detect_yolo(frame)
        elif self._backend == "mediapipe":
            raw = self._detect_mediapipe(frame)
        elif self._backend == "dnn":
            raw = self._detect_dnn(frame)
        else:
            return []

        if not raw:
            return []

        h, w = frame.shape[:2]

        # Preparar datos para batch matching
        batch_input = [(bbox, crop) for bbox, conf, crop, meta in raw]

        # Batch matching: asigna IDs a todas las caras a la vez
        match_results = self._tracker.match_batch(batch_input)

        # Construir detecciones finales
        results: list[Detection] = []
        for i, (bbox, conf, crop, backend_meta) in enumerate(raw):
            person_id, should_capture = match_results[i]

            metadata = {
                **backend_meta,
                "person_id": person_id,
                "is_new_person": should_capture,
                "unique_persons": self._tracker.unique_count,
                "active_persons": self._tracker.active_count,
            }

            # Si se va a capturar, mejorar la calidad del crop
            if should_capture:
                enhanced = self._enhance_crop(frame, bbox, h, w)
                if enhanced is not None:
                    crop = enhanced

            results.append(Detection(
                detection_type=DetectionType.FACE,
                bbox=bbox,
                confidence=conf,
                track_id=person_id,
                crop_image=crop,
                metadata=metadata,
            ))

        return results

    @staticmethod
    def _enhance_crop(frame: np.ndarray, bbox: BoundingBox, h: int, w: int) -> Optional[np.ndarray]:
        """
        Crea un crop de mejor calidad con padding alrededor de la cara.
        Añade 40% de margen para incluir más contexto facial.
        """
        try:
            bw = bbox.width * w
            bh = bbox.height * h
            cx, cy = bbox.center

            pad_x = bw * 0.4
            pad_y = bh * 0.4

            x1 = max(0, int(cx * w - bw / 2 - pad_x))
            y1 = max(0, int(cy * h - bh / 2 - pad_y))
            x2 = min(w, int(cx * w + bw / 2 + pad_x))
            y2 = min(h, int(cy * h + bh / 2 + pad_y))

            if x2 <= x1 or y2 <= y1:
                return None

            crop = frame[y1:y2, x1:x2].copy()

            # Escalar a un tamaño mínimo
            crop_h, crop_w = crop.shape[:2]
            min_size = 200
            if max(crop_h, crop_w) < min_size:
                scale = min_size / max(crop_h, crop_w)
                crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

            return crop
        except Exception:
            return None

    # ═══ Backends (retornan datos crudos) ═══

    def _detect_yolo(self, frame: np.ndarray) -> list[tuple]:
        """Retorna lista de (bbox, conf, crop, metadata)."""
        try:
            results = self._model(frame, verbose=False, conf=self._confidence_threshold)
            raw = []
            h, w = frame.shape[:2]

            for result in results:
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0])
                    fw, fh = x2 - x1, y2 - y1
                    if fw < self._min_face_size or fh < self._min_face_size:
                        continue

                    bbox = BoundingBox(x1=x1/w, y1=y1/h, x2=x2/w, y2=y2/h)
                    crop = frame[int(y1):int(y2), int(x1):int(x2)].copy()
                    raw.append((bbox, conf, crop, {"backend": "yolo", "face_size": (int(fw), int(fh))}))
            return raw
        except Exception as e:
            logger.error(f"Error YOLO: {e}")
            return []

    def _detect_mediapipe(self, frame: np.ndarray) -> list[tuple]:
        try:
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._mp_detector.process(rgb)
            if not results.detections:
                return []

            raw = []
            for mp_det in results.detections:
                conf = mp_det.score[0]
                bb = mp_det.location_data.relative_bounding_box
                x1 = max(0.0, bb.xmin)
                y1 = max(0.0, bb.ymin)
                x2 = min(1.0, bb.xmin + bb.width)
                y2 = min(1.0, bb.ymin + bb.height)
                fw, fh = bb.width * w, bb.height * h
                if fw < self._min_face_size or fh < self._min_face_size:
                    continue

                bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
                px1, py1, px2, py2 = int(x1*w), int(y1*h), int(x2*w), int(y2*h)
                crop = frame[py1:py2, px1:px2].copy() if (px2 > px1 and py2 > py1) else None
                raw.append((bbox, conf, crop, {"backend": "mediapipe", "face_size": (int(fw), int(fh))}))
            return raw
        except Exception as e:
            logger.error(f"Error MediaPipe: {e}")
            return []

    def _detect_dnn(self, frame: np.ndarray) -> list[tuple]:
        """Detección con OpenCV DNN (ResNet-10 SSD) + filtro de piel."""
        try:
            h, w = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(
                cv2.resize(frame, (300, 300)),
                scalefactor=1.0, size=(300, 300),
                mean=(104.0, 177.0, 123.0),
            )
            self._dnn_net.setInput(blob)
            raw_dets = self._dnn_net.forward()

            # Umbral alto para DNN — evita falsos positivos
            min_conf = max(self._confidence_threshold, 0.60)

            results = []
            for i in range(raw_dets.shape[2]):
                conf = float(raw_dets[0, 0, i, 2])
                if conf < min_conf:
                    continue

                x1 = max(0.0, float(raw_dets[0, 0, i, 3]))
                y1 = max(0.0, float(raw_dets[0, 0, i, 4]))
                x2 = min(1.0, float(raw_dets[0, 0, i, 5]))
                y2 = min(1.0, float(raw_dets[0, 0, i, 6]))

                fw_px = (x2 - x1) * w
                fh_px = (y2 - y1) * h
                if fw_px < self._min_face_size or fh_px < self._min_face_size:
                    continue

                # Aspect ratio: caras reales son aprox cuadradas
                aspect = fw_px / max(fh_px, 1)
                if aspect < 0.6 or aspect > 1.6:
                    continue

                bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
                px1, py1 = int(x1 * w), int(y1 * h)
                px2, py2 = int(x2 * w), int(y2 * h)
                crop = frame[py1:py2, px1:px2].copy() if (px2 > px1 and py2 > py1) else None

                # Filtro de color de piel
                if crop is not None and not self._has_skin_tone(crop):
                    continue

                results.append((bbox, conf, crop, {
                    "backend": "opencv_dnn",
                    "face_size": (int(fw_px), int(fh_px)),
                }))
            return results
        except Exception as e:
            logger.error(f"Error OpenCV DNN: {e}")
            return []

    @staticmethod
    def _has_skin_tone(crop: np.ndarray, min_ratio: float = 0.15) -> bool:
        """
        Verifica si la imagen contiene suficientes píxeles con tono de piel.
        Usa espacio de color YCrCb que es robusto a iluminación.
        """
        try:
            if crop is None or crop.size == 0:
                return False

            ycrcb = cv2.cvtColor(crop, cv2.COLOR_BGR2YCrCb)
            lower = np.array([0, 133, 77], dtype=np.uint8)
            upper = np.array([255, 173, 127], dtype=np.uint8)
            mask = cv2.inRange(ycrcb, lower, upper)

            skin_ratio = np.sum(mask > 0) / max(mask.size, 1)
            return skin_ratio >= min_ratio
        except Exception:
            return True
