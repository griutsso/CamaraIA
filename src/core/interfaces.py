"""
Contratos abstractos (interfaces) del sistema IA-CAM-SERVICE.

Define los contratos que cada módulo debe implementar, garantizando
desacoplamiento total entre captura, detección, almacenamiento y UI.
Principio de Inversión de Dependencias (DIP - SOLID).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Optional, Protocol

import numpy as np


# ─────────────────────────────────────────────
#  Modelos de Datos (Value Objects)
# ─────────────────────────────────────────────

class DetectionType(Enum):
    """Tipos de detección soportados por el sistema."""
    FACE = auto()
    PLATE = auto()
    PERSON = auto()
    VEHICLE = auto()


@dataclass(frozen=True)
class BoundingBox:
    """Bounding box normalizado [0..1] para independencia de resolución."""
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def area(self) -> float:
        return self.width * self.height

    def to_absolute(self, frame_w: int, frame_h: int) -> tuple[int, int, int, int]:
        """Convierte a coordenadas absolutas en píxeles."""
        return (
            int(self.x1 * frame_w),
            int(self.y1 * frame_h),
            int(self.x2 * frame_w),
            int(self.y2 * frame_h),
        )


@dataclass(frozen=True)
class Detection:
    """Resultado inmutable de una detección de IA."""
    detection_type: DetectionType
    bbox: BoundingBox
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    track_id: Optional[int] = None
    crop_image: Optional[np.ndarray] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        """Etiqueta legible para la UI."""
        base = self.detection_type.name.capitalize()

        # Placas: mostrar texto leído
        text = self.metadata.get("plate_text", "")
        if text:
            return f"{base}: {text}"

        # Rostros: mostrar ID de persona
        person_id = self.metadata.get("person_id")
        if person_id is not None:
            return f"Persona #{person_id} ({self.confidence:.0%})"

        return f"{base} ({self.confidence:.0%})"


# ─────────────────────────────────────────────
#  Contratos Abstractos
# ─────────────────────────────────────────────

class IVideoSource(ABC):
    """
    Contrato para fuentes de video.

    Cualquier fuente (webcam, archivo, RTSP) debe implementar esta interfaz.
    Principio Abierto/Cerrado: nuevas fuentes se añaden sin modificar consumidores.
    """

    @abstractmethod
    def start(self) -> None:
        """Inicia la captura de video."""

    @abstractmethod
    def read_frame(self) -> Optional[np.ndarray]:
        """Lee el siguiente frame. Retorna None si no hay frame disponible."""

    @abstractmethod
    def stop(self) -> None:
        """Detiene la captura y libera recursos."""

    @abstractmethod
    def is_active(self) -> bool:
        """Indica si la fuente está activa y entregando frames."""

    @property
    @abstractmethod
    def fps(self) -> float:
        """Frames por segundo de la fuente."""

    @property
    @abstractmethod
    def resolution(self) -> tuple[int, int]:
        """Resolución (ancho, alto) de la fuente."""


class IDetector(ABC):
    """
    Contrato para módulos de detección de IA.

    Patrón Strategy: cada detector es intercambiable.
    El pipeline no conoce la implementación concreta.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre identificador del detector."""

    @property
    @abstractmethod
    def detection_type(self) -> DetectionType:
        """Tipo de detección que realiza este módulo."""

    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[Detection]:
        """
        Ejecuta la detección sobre un frame.

        Args:
            frame: Imagen BGR de OpenCV (np.ndarray).

        Returns:
            Lista de detecciones encontradas en el frame.
        """

    @abstractmethod
    def load_model(self) -> None:
        """Carga el modelo de IA en memoria."""

    @abstractmethod
    def unload_model(self) -> None:
        """Libera el modelo de memoria."""

    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """Indica si el modelo está cargado y listo."""


class IStorageBackend(ABC):
    """
    Contrato para el backend de almacenamiento.

    Principio de Segregación de Interfaces: solo operaciones CRUD básicas.
    """

    @abstractmethod
    def save_detection(self, detection: Detection) -> str:
        """
        Persiste una detección. Retorna el ID del registro.

        Args:
            detection: Objeto Detection a almacenar.

        Returns:
            ID único del registro almacenado.
        """

    @abstractmethod
    def get_detections(
        self,
        detection_type: Optional[DetectionType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Recupera detecciones con filtros opcionales."""

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del almacenamiento (conteos, espacio, etc.)."""

    @abstractmethod
    def close(self) -> None:
        """Cierra conexiones y libera recursos."""


# ─────────────────────────────────────────────
#  Protocolo para Observadores (Event Bus)
# ─────────────────────────────────────────────

class IEventListener(Protocol):
    """Protocolo para listeners de eventos del sistema."""

    def on_event(self, event_name: str, data: Any) -> None:
        """Callback invocado cuando ocurre un evento."""
        ...
