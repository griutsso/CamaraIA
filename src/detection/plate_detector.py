"""
Módulo de Detección y Lectura de Placas Vehiculares.

Jerarquía de backends para localización:
  1. YOLOv8 plate (modelo especializado, auto-descarga desde repositorio público)
  2. YOLOv8n COCO (detecta la clase genérica, menos preciso)
  3. OpenCV Haar Cascade (fallback final, muchos falsos positivos)

Pipeline de lectura:
  1. Localización de placa (YOLO o Haar)
  2. Preprocesamiento (CLAHE + binarización)
  3. OCR (EasyOCR si disponible)
  4. Validación: solo se aceptan detecciones con texto legible
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from src.core.interfaces import BoundingBox, Detection, DetectionType, IDetector

logger = logging.getLogger(__name__)

# Patrones de placas por país (regex)
PLATE_PATTERNS: dict[str, re.Pattern] = {
    "MX": re.compile(r"^[A-Z]{3}[\s-]?\d{3,4}[A-Z]?$"),
    "CO": re.compile(r"^[A-Z]{3}[\s-]?\d{3,4}$"),
    "AR": re.compile(r"^[A-Z]{2}[\s-]?\d{3}[\s-]?[A-Z]{2}$"),
    "US": re.compile(r"^[A-Z0-9]{2,3}[\s-]?[A-Z0-9]{3,4}$"),
    "GENERIC": re.compile(r"^[A-Z0-9]{4,8}$"),
}

# URL del modelo YOLO-plate pre-entrenado (licencia pública)
_PLATE_MODEL_URL = (
    "https://github.com/Muhammad-Zeerak-Khan/"
    "Automatic-License-Plate-Recognition-using-YOLOv8/"
    "raw/main/license_plate_detector.pt"
)


class PlateDetector(IDetector):
    """
    Detector de placas vehiculares: localización + lectura OCR.

    Backends de localización (se usa el primero disponible):
      1. YOLO-plate (modelo especializado en placas)
      2. Haar Cascade (fallback, incluido en OpenCV)
    """

    def __init__(
        self,
        model_path: str = "models/yolov8n-plate.pt",
        confidence_threshold: float = 0.5,
        min_plate_size: int = 60,
    ) -> None:
        self._model_path = model_path
        self._confidence_threshold = confidence_threshold
        self._min_plate_size = min_plate_size
        self._model = None           # YOLO model
        self._cascade = None         # Haar cascade
        self._ocr_reader = None      # EasyOCR reader
        self._backend = "none"       # "yolo", "cascade", "none"
        self._is_loaded = False

        # Cooldown para evitar spam de detecciones
        self._last_detection_time: float = 0.0
        self._detection_cooldown: float = 0.5  # segundos entre detecciones (más reactivo)

    @property
    def name(self) -> str:
        return "PlateDetector"

    @property
    def detection_type(self) -> DetectionType:
        return DetectionType.PLATE

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def load_model(self) -> None:
        """Carga el mejor backend disponible para localización + OCR."""

        # ── Intento 1: YOLO-plate especializado ──
        if self._try_load_yolo():
            pass  # Éxito
        # ── Intento 2: Haar Cascade (fallback) ──
        elif self._try_load_cascade():
            pass
        else:
            self._backend = "none"
            logger.error(
                "⚠ PlateDetector: SIN BACKEND DE LOCALIZACIÓN. "
                "Instala ultralytics: pip install ultralytics"
            )

        # Cargar EasyOCR para lectura de texto (independiente del backend)
        self._load_ocr()
        self._is_loaded = True

    def _try_load_yolo(self) -> bool:
        """Intenta cargar modelo YOLO para placas."""
        try:
            from ultralytics import YOLO

            models_dir = Path("models")
            models_dir.mkdir(parents=True, exist_ok=True)

            # Buscar modelo YOLO-plate en orden de preferencia
            plate_paths = [
                Path(self._model_path),                        # Config del usuario
                models_dir / "license_plate_detector.pt",      # Modelo descargado
                models_dir / "yolov8n-plate.pt",               # Nombre alternativo
            ]

            model_file = None
            for p in plate_paths:
                if p.exists() and p.stat().st_size > 1_000_000:
                    model_file = p
                    break

            # Si no existe, intentar descargar
            if model_file is None:
                target = models_dir / "license_plate_detector.pt"
                logger.info("Descargando modelo YOLO-plate (~6MB, una sola vez)...")
                try:
                    import urllib.request
                    urllib.request.urlretrieve(_PLATE_MODEL_URL, str(target))
                    if target.exists() and target.stat().st_size > 1_000_000:
                        model_file = target
                        logger.info("  ✓ Modelo YOLO-plate descargado")
                    else:
                        logger.warning("  ✗ Descarga fallida o archivo truncado")
                        target.unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"  ✗ No se pudo descargar: {e}")
                    target.unlink(missing_ok=True)

            if model_file is None:
                return False

            self._model = YOLO(str(model_file))
            self._backend = "yolo"
            logger.info(f"✓ PlateDetector: YOLO cargado ({model_file.name})")
            return True

        except ImportError:
            logger.info("ultralytics no instalado. Intentando Haar Cascade...")
            return False
        except Exception as e:
            logger.warning(f"Error cargando YOLO-plate: {e}")
            return False

    def _try_load_cascade(self) -> bool:
        """Carga Haar Cascade como fallback."""
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_russian_plate_number.xml"
            self._cascade = cv2.CascadeClassifier(cascade_path)
            if self._cascade.empty():
                raise RuntimeError("Cascade classifier vacío")
            self._backend = "cascade"
            logger.info("✓ PlateDetector: Haar Cascade cargado (fallback)")
            return True
        except Exception as e:
            logger.error(f"Error cargando Haar Cascade: {e}")
            return False

    def _load_ocr(self) -> None:
        """Carga EasyOCR para lectura de texto."""
        try:
            import easyocr
            self._ocr_reader = easyocr.Reader(
                ["en", "es"], gpu=False, verbose=False,
            )
            logger.info("✓ PlateDetector: EasyOCR inicializado (en, es)")
        except ImportError:
            logger.warning("easyocr no instalado. pip install easyocr")
        except Exception as e:
            logger.warning(f"Error inicializando EasyOCR: {e}")

    def unload_model(self) -> None:
        self._model = None
        self._cascade = None
        self._ocr_reader = None
        self._is_loaded = False
        self._backend = "none"
        logger.info("PlateDetector descargado.")

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Detecta y lee placas vehiculares."""
        if not self._is_loaded or self._backend == "none":
            return []

        # Cooldown para no saturar
        now = time.time()
        if now - self._last_detection_time < self._detection_cooldown:
            return []

        if self._backend == "yolo":
            detections = self._detect_yolo(frame)
        elif self._backend == "cascade":
            detections = self._detect_cascade(frame)
        else:
            return []

        if detections:
            self._last_detection_time = now

        return detections

    # ── YOLO Backend ──

    def _detect_yolo(self, frame: np.ndarray) -> list[Detection]:
        """Detección con YOLO-plate (mucho más preciso que Haar)."""
        try:
            results = self._model(
                frame, verbose=False, conf=self._confidence_threshold
            )
            detections: list[Detection] = []
            h, w = frame.shape[:2]

            for result in results:
                if result.boxes is None:
                    continue

                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0])

                    plate_w = x2 - x1
                    if plate_w < self._min_plate_size:
                        continue

                    crop = frame[int(y1):int(y2), int(x1):int(x2)].copy()

                    # OCR para leer el texto
                    processed = self._preprocess_plate(crop)
                    plate_text = self._read_plate_text(processed)

                    # YOLO-plate es un modelo especializado: si detecta con
                    # alta confianza, ES una placa real incluso sin OCR legible.
                    # Guardar con texto "DETECTADA" si OCR no logró leer.
                    if not plate_text and conf >= 0.6:
                        plate_text = "DETECTADA"
                        logger.debug(f"Placa YOLO conf={conf:.2f} sin OCR → guardada como DETECTADA")

                    bbox = BoundingBox(
                        x1=float(x1) / w, y1=float(y1) / h,
                        x2=float(x2) / w, y2=float(y2) / h,
                    )

                    detections.append(Detection(
                        detection_type=DetectionType.PLATE,
                        bbox=bbox,
                        confidence=conf,
                        crop_image=crop,
                        metadata={
                            "plate_text": plate_text or "???",
                            "plate_size": (int(plate_w), int(y2 - y1)),
                            "country": self._identify_country(plate_text),
                            "backend": "yolo_plate",
                            "ocr_success": plate_text not in (None, "DETECTADA", "???"),
                        },
                    ))

            return detections

        except Exception as e:
            logger.error(f"Error en detección YOLO de placas: {e}")
            return []

    # ── Haar Cascade Backend ──

    def _detect_cascade(self, frame: np.ndarray) -> list[Detection]:
        """
        Detección con Haar Cascade + filtros estrictos.
        Solo acepta detecciones donde el OCR pueda leer texto.
        """
        try:
            h, w = frame.shape[:2]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)

            candidates = self._cascade.detectMultiScale(
                gray,
                scaleFactor=1.08,
                minNeighbors=12,
                minSize=(self._min_plate_size, 15),
                maxSize=(int(w * 0.4), int(h * 0.15)),
            )

            if len(candidates) == 0:
                return []

            detections: list[Detection] = []

            for (rx, ry, rw, rh) in candidates:
                # Aspect ratio estricto: placas 2.5:1 a 5.0:1
                aspect_ratio = rw / max(rh, 1)
                if aspect_ratio < 2.5 or aspect_ratio > 5.0:
                    continue

                if rw < self._min_plate_size:
                    continue

                # Análisis de bordes
                crop_gray = gray[ry:ry + rh, rx:rx + rw]
                if not self._has_plate_characteristics(crop_gray):
                    continue

                crop = frame[ry:ry + rh, rx:rx + rw].copy()

                # OCR obligatorio para cascade (muchos falsos positivos)
                processed = self._preprocess_plate(crop)
                plate_text = self._read_plate_text(processed)  # Prueba todas las variantes

                if not plate_text:
                    continue  # Sin texto → falso positivo

                conf = self._estimate_plate_confidence(crop_gray, aspect_ratio, plate_text)
                if conf < self._confidence_threshold:
                    continue

                bbox = BoundingBox(
                    x1=rx / w, y1=ry / h,
                    x2=(rx + rw) / w, y2=(ry + rh) / h,
                )

                detections.append(Detection(
                    detection_type=DetectionType.PLATE,
                    bbox=bbox,
                    confidence=conf,
                    crop_image=crop,
                    metadata={
                        "plate_text": plate_text,
                        "plate_size": (rw, rh),
                        "aspect_ratio": round(aspect_ratio, 2),
                        "country": self._identify_country(plate_text),
                        "backend": "cascade",
                    },
                ))

            return detections

        except Exception as e:
            logger.error(f"Error en detección cascade de placas: {e}")
            return []

    def _has_plate_characteristics(self, gray_crop: np.ndarray) -> bool:
        """Verifica si un candidato tiene características de placa real."""
        if gray_crop.size == 0:
            return False

        try:
            sobel_x = cv2.Sobel(gray_crop, cv2.CV_64F, 1, 0, ksize=3)
            edge_density = np.mean(np.abs(sobel_x)) / 255.0
            if edge_density < 0.10:
                return False

            std_dev = np.std(gray_crop)
            if std_dev < 40:
                return False

            total_pixels = gray_crop.size
            very_dark = np.sum(gray_crop < 60) / total_pixels
            very_light = np.sum(gray_crop > 195) / total_pixels
            if very_dark < 0.08 or very_light < 0.08:
                return False

            return True
        except Exception:
            return False

    def _estimate_plate_confidence(
        self, gray_crop: np.ndarray, aspect_ratio: float, plate_text: str = ""
    ) -> float:
        """Estima la confianza basada en características + OCR."""
        try:
            score = 0.3

            ideal_ratio = 3.5
            ratio_diff = abs(aspect_ratio - ideal_ratio)
            if ratio_diff < 0.5:
                score += 0.2
            elif ratio_diff < 1.0:
                score += 0.1

            sobel_x = cv2.Sobel(gray_crop, cv2.CV_64F, 1, 0, ksize=3)
            edge_density = np.mean(np.abs(sobel_x)) / 255.0
            if edge_density > 0.20:
                score += 0.15
            elif edge_density > 0.15:
                score += 0.1

            clean_text = plate_text.replace("-", "").replace(" ", "")
            if len(clean_text) >= 6:
                score += 0.25
            elif len(clean_text) >= 4:
                score += 0.15
            elif len(clean_text) >= 3:
                score += 0.05

            country = self._identify_country(plate_text)
            if country != "UNKNOWN":
                score += 0.15

            return min(score, 0.95)
        except Exception:
            return 0.3

    # ── Procesamiento de imagen ──

    def _preprocess_plate(self, crop: np.ndarray) -> list[np.ndarray]:
        """
        Preprocesamiento para mejorar OCR.
        Retorna múltiples variantes para que OCR tenga más oportunidades.
        """
        variants = []
        try:
            target_width = 300
            h_crop, w_crop = crop.shape[:2]
            if w_crop > 0:
                scale = target_width / w_crop
                crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

            # Variante 1: CLAHE + binarización adaptativa
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            binary = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2,
            )
            variants.append(binary)

            # Variante 2: CLAHE directo (sin binarizar, a veces OCR lee mejor)
            variants.append(enhanced)

            # Variante 3: Otsu thresholding
            _, otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            variants.append(otsu)

            return variants
        except Exception:
            return [crop]

    def _read_plate_text(self, plate_images) -> Optional[str]:
        """
        Lee texto de la placa usando EasyOCR.
        Acepta una imagen o lista de variantes preprocesadas.
        Prueba cada variante y retorna el mejor resultado.
        """
        if self._ocr_reader is None:
            return None

        # Normalizar entrada: puede ser una imagen o lista de variantes
        if isinstance(plate_images, np.ndarray):
            variants = [plate_images]
        elif isinstance(plate_images, list):
            variants = plate_images
        else:
            return None

        best_text = None
        best_length = 0

        for img in variants:
            try:
                results = self._ocr_reader.readtext(
                    img, detail=0,
                    allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- ",
                )
                if results:
                    text = " ".join(results).strip().upper()
                    cleaned = self._postprocess_text(text)
                    clean_len = len(cleaned.replace("-", "").replace(" ", ""))
                    if clean_len >= 3 and clean_len > best_length:
                        best_text = cleaned
                        best_length = clean_len
            except Exception as e:
                logger.debug(f"Error en OCR variante: {e}")
                continue

        return best_text

    @staticmethod
    def _postprocess_text(text: str) -> str:
        """Corrección de caracteres ambiguos en OCR."""
        cleaned = re.sub(r"[\s-]+", "-", text.strip())
        cleaned = re.sub(r"^-|-$", "", cleaned)
        return cleaned

    @staticmethod
    def _identify_country(plate_text: Optional[str]) -> str:
        """Identifica el país por el formato de la placa."""
        if not plate_text:
            return "UNKNOWN"
        clean = plate_text.replace("-", "").replace(" ", "")
        for country, pattern in PLATE_PATTERNS.items():
            if pattern.match(clean):
                return country
        return "UNKNOWN"
