"""
Detector de Objetos Generales (Personas y Vehículos).

Jerarquía de backends:
  1. YOLOv8n COCO (preferido, detecta 80 clases incluyendo person, car, truck, etc.)
  2. MobileNet-SSD (fallback, auto-descarga ~23MB)

Clases de interés (COCO IDs):
  - person (0)
  - bicycle (1), car (2), motorcycle (3), bus (5), truck (7)
"""

from __future__ import annotations

import logging
import urllib.request
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from src.core.interfaces import BoundingBox, Detection, DetectionType, IDetector

logger = logging.getLogger(__name__)

# Clases COCO de interés para YOLOv8
COCO_PERSON_ID = 0
COCO_VEHICLE_IDS = {1, 2, 3, 5, 7}  # bicycle, car, motorcycle, bus, truck
COCO_VEHICLE_NAMES = {1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

# MobileNet-SSD fallback
_SSD_PROTOTXT_URL = (
    "https://raw.githubusercontent.com/djmv/MobilNet_SSD_opencv/"
    "master/MobileNetSSD_deploy.prototxt"
)
_SSD_CAFFEMODEL_URL = (
    "https://github.com/chuanqi305/MobileNet-SSD/raw/master/"
    "mobilenet_iter_73000.caffemodel"
)

VOC_CLASSES = [
    "background", "aeroplane", "bicycle", "bird", "boat", "bottle",
    "bus", "car", "cat", "chair", "cow", "diningtable", "dog",
    "horse", "motorbike", "person", "pottedplant", "sheep", "sofa",
    "train", "tvmonitor",
]
VOC_PERSON_ID = 15
VOC_VEHICLE_IDS = {2, 6, 7, 14}  # bicycle, bus, car, motorbike


class ObjectDetector(IDetector):
    """
    Detector de personas y vehículos.

    Backend primario: YOLOv8n (COCO, 80 clases, ~6MB)
    Backend fallback: MobileNet-SSD (PASCAL VOC, 20 clases, ~23MB)
    """

    def __init__(
        self,
        confidence_threshold: float = 0.35,
        detect_persons: bool = True,
        detect_vehicles: bool = True,
    ) -> None:
        self._confidence_threshold = confidence_threshold
        self._detect_persons = detect_persons
        self._detect_vehicles = detect_vehicles
        self._model = None       # YOLO model
        self._ssd_net = None     # MobileNet-SSD fallback
        self._is_loaded = False
        self._backend = "none"   # "yolo", "ssd", "none"

    @property
    def name(self) -> str:
        return "ObjectDetector"

    @property
    def detection_type(self) -> DetectionType:
        return DetectionType.PERSON

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def load_model(self) -> None:
        """Carga el mejor backend disponible."""
        # ── Intento 1: YOLOv8n COCO ──
        if self._try_load_yolo():
            self._is_loaded = True
            return

        # ── Intento 2: MobileNet-SSD fallback ──
        if self._try_load_ssd():
            self._is_loaded = True
            return

        logger.warning(
            "⚠ ObjectDetector: ningún backend disponible. "
            "Instala ultralytics: pip install ultralytics"
        )
        self._backend = "none"
        self._is_loaded = True  # Marcado como "cargado" pero sin backend

    def _try_load_yolo(self) -> bool:
        """Intenta cargar YOLOv8n COCO."""
        try:
            from ultralytics import YOLO

            models_dir = Path("models")
            models_dir.mkdir(parents=True, exist_ok=True)
            model_path = models_dir / "yolov8n.pt"

            # YOLOv8n se auto-descarga si no existe (~6MB)
            self._model = YOLO(str(model_path))
            self._backend = "yolo"
            logger.info(
                f"✓ ObjectDetector: YOLOv8n COCO cargado "
                f"(persona={self._detect_persons}, vehículo={self._detect_vehicles}, "
                f"threshold={self._confidence_threshold})"
            )
            return True

        except ImportError:
            logger.info("ultralytics no instalado. Intentando MobileNet-SSD...")
            return False
        except Exception as e:
            logger.warning(f"Error cargando YOLOv8n: {e}")
            return False

    def _try_load_ssd(self) -> bool:
        """Intenta cargar MobileNet-SSD como fallback."""
        models_dir = Path("models")
        models_dir.mkdir(parents=True, exist_ok=True)

        prototxt = models_dir / "MobileNetSSD_deploy.prototxt"
        caffemodel = models_dir / "mobilenet_iter_73000.caffemodel"

        # Descargar si no existe
        if not prototxt.exists():
            logger.info("Descargando MobileNet-SSD prototxt...")
            try:
                urllib.request.urlretrieve(_SSD_PROTOTXT_URL, str(prototxt))
            except Exception as e:
                logger.warning(f"No se pudo descargar prototxt: {e}")
                return False

        if not caffemodel.exists():
            logger.info("Descargando MobileNet-SSD (~23MB)...")
            try:
                urllib.request.urlretrieve(_SSD_CAFFEMODEL_URL, str(caffemodel))
                if caffemodel.stat().st_size < 20_000_000:
                    logger.warning("Archivo truncado, eliminando...")
                    caffemodel.unlink(missing_ok=True)
                    return False
            except Exception as e:
                logger.warning(f"No se pudo descargar modelo: {e}")
                return False

        try:
            self._ssd_net = cv2.dnn.readNetFromCaffe(str(prototxt), str(caffemodel))
            self._backend = "ssd"
            logger.info("✓ ObjectDetector: MobileNet-SSD cargado (fallback)")
            return True
        except Exception as e:
            logger.error(f"Error cargando MobileNet-SSD: {e}")
            return False

    def unload_model(self) -> None:
        self._model = None
        self._ssd_net = None
        self._is_loaded = False
        self._backend = "none"
        logger.info("ObjectDetector descargado.")

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Detecta personas y vehículos en el frame."""
        if not self._is_loaded:
            return []

        if self._backend == "yolo":
            return self._detect_yolo(frame)
        elif self._backend == "ssd":
            return self._detect_ssd(frame)
        return []

    # ── YOLOv8 Backend ──

    def _detect_yolo(self, frame: np.ndarray) -> list[Detection]:
        """Detección con YOLOv8n COCO."""
        try:
            results = self._model(
                frame, verbose=False, conf=self._confidence_threshold
            )
            h, w = frame.shape[:2]
            detections: list[Detection] = []

            for result in results:
                if result.boxes is None:
                    continue

                for box in result.boxes:
                    class_id = int(box.cls[0])
                    conf = float(box.conf[0])

                    # Persona
                    if class_id == COCO_PERSON_ID and self._detect_persons:
                        det_type = DetectionType.PERSON
                        class_name = "person"
                    # Vehículo
                    elif class_id in COCO_VEHICLE_IDS and self._detect_vehicles:
                        det_type = DetectionType.VEHICLE
                        class_name = COCO_VEHICLE_NAMES.get(class_id, "vehicle")
                    else:
                        continue

                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    bbox = BoundingBox(
                        x1=float(x1) / w, y1=float(y1) / h,
                        x2=float(x2) / w, y2=float(y2) / h,
                    )

                    px1, py1 = int(x1), int(y1)
                    px2, py2 = int(x2), int(y2)
                    crop = frame[py1:py2, px1:px2].copy() if (px2 > px1 and py2 > py1) else None

                    detections.append(Detection(
                        detection_type=det_type,
                        bbox=bbox,
                        confidence=conf,
                        crop_image=crop,
                        metadata={
                            "class_name": class_name,
                            "class_id": class_id,
                            "backend": "yolov8n_coco",
                        },
                    ))

            return detections

        except Exception as e:
            logger.error(f"Error en ObjectDetector YOLO: {e}")
            return []

    # ── MobileNet-SSD Fallback ──

    def _detect_ssd(self, frame: np.ndarray) -> list[Detection]:
        """Detección con MobileNet-SSD (fallback)."""
        try:
            h, w = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(
                cv2.resize(frame, (300, 300)),
                scalefactor=0.007843, size=(300, 300), mean=127.5,
            )
            self._ssd_net.setInput(blob)
            raw = self._ssd_net.forward()

            detections: list[Detection] = []

            for i in range(raw.shape[2]):
                conf = float(raw[0, 0, i, 2])
                if conf < self._confidence_threshold:
                    continue

                class_id = int(raw[0, 0, i, 1])

                if class_id == VOC_PERSON_ID and self._detect_persons:
                    det_type = DetectionType.PERSON
                elif class_id in VOC_VEHICLE_IDS and self._detect_vehicles:
                    det_type = DetectionType.VEHICLE
                else:
                    continue

                x1 = max(0.0, float(raw[0, 0, i, 3]))
                y1 = max(0.0, float(raw[0, 0, i, 4]))
                x2 = min(1.0, float(raw[0, 0, i, 5]))
                y2 = min(1.0, float(raw[0, 0, i, 6]))

                bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
                px1, py1 = int(x1 * w), int(y1 * h)
                px2, py2 = int(x2 * w), int(y2 * h)
                crop = frame[py1:py2, px1:px2].copy() if (px2 > px1 and py2 > py1) else None

                class_name = VOC_CLASSES[class_id] if class_id < len(VOC_CLASSES) else "unknown"

                detections.append(Detection(
                    detection_type=det_type,
                    bbox=bbox,
                    confidence=conf,
                    crop_image=crop,
                    metadata={
                        "class_name": class_name,
                        "class_id": class_id,
                        "backend": "mobilenet_ssd",
                    },
                ))

            return detections

        except Exception as e:
            logger.error(f"Error en ObjectDetector SSD: {e}")
            return []

    # ── Métodos estáticos de estimación heurística ──

    @staticmethod
    def estimate_body_from_face(
        face_bbox: BoundingBox,
        frame_h: int,
        frame_w: int,
    ) -> BoundingBox:
        """Estima la región del cuerpo a partir de un rostro detectado."""
        face_h = face_bbox.height
        face_w = face_bbox.width
        cx, cy = face_bbox.center

        body_h = face_h * 4.5
        body_w = face_w * 2.5

        y1 = max(0.0, face_bbox.y1 - face_h * 0.2)
        y2 = min(1.0, face_bbox.y1 + body_h)
        x1 = max(0.0, cx - body_w / 2)
        x2 = min(1.0, cx + body_w / 2)

        return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)

    @staticmethod
    def estimate_vehicle_from_plate(
        plate_bbox: BoundingBox,
        frame_h: int,
        frame_w: int,
    ) -> BoundingBox:
        """Estima la región del vehículo a partir de una placa detectada."""
        plate_h = plate_bbox.height
        plate_w = plate_bbox.width
        cx, cy = plate_bbox.center

        vehicle_w = max(plate_w * 6.0, 0.3)
        vehicle_h = max(plate_h * 8.0, 0.25)

        y1 = max(0.0, cy - vehicle_h * 0.85)
        y2 = min(1.0, cy + vehicle_h * 0.15)
        x1 = max(0.0, cx - vehicle_w / 2)
        x2 = min(1.0, cx + vehicle_w / 2)

        return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
