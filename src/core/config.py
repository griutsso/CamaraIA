"""
Gestor de configuración centralizado.

Carga configuración desde YAML con valores por defecto seguros.
Principio de Responsabilidad Única: solo gestiona configuración.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Ruta base del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "settings.yaml"


@dataclass
class CameraConfig:
    """Configuración del módulo de captura."""
    source: int | str = 0  # 0 = webcam por defecto
    width: int = 0         # 0 = auto-detectar resolución nativa
    height: int = 0        # 0 = auto-detectar resolución nativa
    fps: int = 0           # 0 = auto-detectar FPS nativo
    buffer_size: int = 30
    reconnect_attempts: int = 5
    reconnect_delay: float = 2.0


@dataclass
class DetectionConfig:
    """Configuración de los módulos de detección."""
    face_enabled: bool = True
    plate_enabled: bool = True
    person_enabled: bool = True
    vehicle_enabled: bool = True
    face_model: str = "yolov8n-face.pt"
    plate_model: str = "yolov8n-plate.pt"
    confidence_threshold: float = 0.5
    face_min_size: int = 40
    plate_min_size: int = 60
    tracking_iou_threshold: float = 0.4
    duplicate_cooldown: float = 3.0


@dataclass
class StorageConfig:
    """Configuración del almacenamiento local."""
    database_path: str = "data/detections.db"
    images_path: str = "data/captures"
    encryption_enabled: bool = False  # TODO: Implementar cifrado AES-256 en Fase 4
    max_storage_mb: int = 5120  # 5 GB
    rotation_threshold: float = 0.8  # 80% activa purga


@dataclass
class WebUIConfig:
    """Configuración de la interfaz web."""
    accent_color: str = "#0A84FF"
    show_fps: bool = True
    show_bounding_boxes: bool = True


@dataclass
class AppConfig:
    """Configuración raíz de la aplicación."""
    app_name: str = "IA-CAM-SERVICE"
    version: str = "0.1.0"
    log_level: str = "INFO"
    camera: CameraConfig = field(default_factory=CameraConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    ui: WebUIConfig = field(default_factory=WebUIConfig)


def load_config(config_path: Path | None = None) -> AppConfig:
    """
    Carga la configuración desde un archivo YAML.

    Si el archivo no existe, retorna configuración por defecto.

    Args:
        config_path: Ruta al archivo YAML. None usa la ruta por defecto.

    Returns:
        AppConfig con la configuración cargada.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    config = AppConfig()

    if not path.exists():
        logger.warning(f"Config no encontrada en {path}, usando valores por defecto.")
        return config

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}

        # Mapear secciones YAML a dataclasses
        if "camera" in raw:
            config.camera = CameraConfig(**raw["camera"])
        if "detection" in raw:
            config.detection = DetectionConfig(**raw["detection"])
        if "storage" in raw:
            config.storage = StorageConfig(**raw["storage"])
        if "ui" in raw:
            # Filtrar campos legacy del GUI desktop
            ui_fields = {k: v for k, v in raw["ui"].items()
                         if k in WebUIConfig.__dataclass_fields__}
            config.ui = WebUIConfig(**ui_fields)
        if "log_level" in raw:
            config.log_level = raw["log_level"]

        logger.info(f"Configuración cargada desde {path}")

    except Exception as e:
        logger.error(f"Error cargando configuración: {e}. Usando valores por defecto.")

    return config
