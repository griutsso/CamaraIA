"""
Contenedor de Inyección de Dependencias (DI Container).

Centraliza la creación y ciclo de vida de todos los servicios del sistema.
Permite intercambiar implementaciones concretas sin modificar el código cliente.

Patrón: Composition Root + Service Locator simplificado.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from src.core.config import AppConfig
from src.core.events import EventBus
from src.core.interfaces import IDetector, IStorageBackend, IVideoSource

logger = logging.getLogger(__name__)


class ServiceContainer:
    """
    Contenedor central de servicios.

    Gestiona la creación, inyección y ciclo de vida de todos
    los componentes del sistema. Punto único de configuración.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._event_bus = EventBus()
        self._video_source: Optional[IVideoSource] = None
        self._detectors: list[IDetector] = []
        self._storage: Optional[IStorageBackend] = None
        logger.info("ServiceContainer inicializado")

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def video_source(self) -> Optional[IVideoSource]:
        return self._video_source

    @property
    def detectors(self) -> list[IDetector]:
        return list(self._detectors)

    @property
    def storage(self) -> Optional[IStorageBackend]:
        return self._storage

    # ── Registro de servicios ──

    def register_video_source(self, source: IVideoSource) -> None:
        """Registra la fuente de video activa."""
        self._video_source = source
        logger.info(f"VideoSource registrado: {type(source).__name__}")

    def register_detector(self, detector: IDetector) -> None:
        """Añade un detector al pipeline."""
        self._detectors.append(detector)
        logger.info(f"Detector registrado: {detector.name}")

    def register_storage(self, storage: IStorageBackend) -> None:
        """Registra el backend de almacenamiento."""
        self._storage = storage
        logger.info(f"Storage registrado: {type(storage).__name__}")

    # ── Factory Methods ──

    def build_default_services(self) -> None:
        """
        Construye e inyecta los servicios por defecto según la configuración.

        Este método es el Composition Root: aquí se decide qué implementaciones
        concretas se usan para cada interfaz abstracta.
        """
        from src.capture.video_source import WebcamSource
        from src.detection.face_detector import FaceDetector
        from src.detection.plate_detector import PlateDetector
        from src.detection.object_detector import ObjectDetector
        from src.storage.database import SQLiteStorage

        # Video source
        source = WebcamSource(
            device_index=self._config.camera.source,
            width=self._config.camera.width,
            height=self._config.camera.height,
            target_fps=self._config.camera.fps,
        )
        self.register_video_source(source)

        # Detectores (solo los habilitados)
        if self._config.detection.face_enabled:
            face_detector = FaceDetector(
                model_path=str(
                    Path("models") / self._config.detection.face_model
                ),
                confidence_threshold=self._config.detection.confidence_threshold,
                min_face_size=self._config.detection.face_min_size,
            )
            self.register_detector(face_detector)

        if self._config.detection.plate_enabled:
            plate_detector = PlateDetector(
                model_path=str(
                    Path("models") / self._config.detection.plate_model
                ),
                confidence_threshold=self._config.detection.confidence_threshold,
                min_plate_size=self._config.detection.plate_min_size,
            )
            self.register_detector(plate_detector)

        # Detector de objetos (personas + vehículos)
        # Umbral más bajo (0.35) porque MobileNet-SSD necesita más sensibilidad
        # para detectar personas parcialmente visibles en webcam
        if self._config.detection.person_enabled or self._config.detection.vehicle_enabled:
            object_detector = ObjectDetector(
                confidence_threshold=min(self._config.detection.confidence_threshold, 0.35),
                detect_persons=self._config.detection.person_enabled,
                detect_vehicles=self._config.detection.vehicle_enabled,
            )
            self.register_detector(object_detector)

        # Storage
        db_path = Path(self._config.storage.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        storage = SQLiteStorage(
            db_path=str(db_path),
            images_path=self._config.storage.images_path,
            event_bus=self._event_bus,
        )
        self.register_storage(storage)

        logger.info(
            f"Servicios construidos: "
            f"camera={type(source).__name__}, "
            f"detectores={len(self._detectors)}, "
            f"storage={type(storage).__name__}"
        )

    # ── Ciclo de vida ──

    def shutdown(self) -> None:
        """Libera todos los recursos de forma ordenada."""
        logger.info("Iniciando shutdown del contenedor...")

        if self._video_source:
            try:
                self._video_source.stop()
            except Exception as e:
                logger.error(f"Error deteniendo video source: {e}")

        for detector in self._detectors:
            try:
                detector.unload_model()
            except Exception as e:
                logger.error(f"Error descargando detector {detector.name}: {e}")

        if self._storage:
            try:
                self._storage.close()
            except Exception as e:
                logger.error(f"Error cerrando storage: {e}")

        self._event_bus.clear()
        logger.info("Shutdown completo.")
