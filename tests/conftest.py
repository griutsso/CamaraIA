"""
Fixtures compartidos para la suite de tests.
"""

import sys
from pathlib import Path

import pytest
import numpy as np

# Asegurar imports desde la raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import AppConfig
from src.core.events import EventBus


@pytest.fixture
def app_config() -> AppConfig:
    """Configuración por defecto para tests."""
    return AppConfig()


@pytest.fixture
def event_bus() -> EventBus:
    """EventBus limpio para cada test."""
    bus = EventBus()
    yield bus
    bus.clear()


@pytest.fixture
def sample_frame() -> np.ndarray:
    """Frame de prueba (640x480 BGR, negro)."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def sample_frame_with_content() -> np.ndarray:
    """Frame de prueba con contenido visual aleatorio."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)
