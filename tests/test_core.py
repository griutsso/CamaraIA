"""
Tests para el módulo core: config, events, interfaces.
"""

import pytest
from src.core.config import AppConfig, load_config, CameraConfig
from src.core.events import EventBus
from src.core.interfaces import BoundingBox, Detection, DetectionType


class TestBoundingBox:
    """Tests para el value object BoundingBox."""

    def test_properties(self):
        bbox = BoundingBox(x1=0.1, y1=0.2, x2=0.5, y2=0.8)
        assert bbox.width == pytest.approx(0.4)
        assert bbox.height == pytest.approx(0.6)
        assert bbox.area == pytest.approx(0.24)

    def test_center(self):
        bbox = BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0)
        assert bbox.center == pytest.approx((0.5, 0.5))

    def test_to_absolute(self):
        bbox = BoundingBox(x1=0.25, y1=0.25, x2=0.75, y2=0.75)
        abs_coords = bbox.to_absolute(640, 480)
        assert abs_coords == (160, 120, 480, 360)


class TestDetection:
    """Tests para el value object Detection."""

    def test_label_face(self):
        det = Detection(
            detection_type=DetectionType.FACE,
            bbox=BoundingBox(0, 0, 1, 1),
            confidence=0.92,
        )
        assert "Face" in det.label
        assert "92%" in det.label

    def test_label_plate_with_text(self):
        det = Detection(
            detection_type=DetectionType.PLATE,
            bbox=BoundingBox(0, 0, 1, 1),
            confidence=0.88,
            metadata={"plate_text": "ABC-1234"},
        )
        assert "ABC-1234" in det.label


class TestEventBus:
    """Tests para el sistema de eventos."""

    def test_subscribe_and_emit(self, event_bus: EventBus):
        received = []
        event_bus.subscribe("test:event", lambda e, d: received.append(d))
        event_bus.emit("test:event", {"key": "value"})
        assert len(received) == 1
        assert received[0]["key"] == "value"

    def test_unsubscribe(self, event_bus: EventBus):
        received = []
        callback = lambda e, d: received.append(d)
        event_bus.subscribe("test:event", callback)
        event_bus.unsubscribe("test:event", callback)
        event_bus.emit("test:event", "data")
        assert len(received) == 0

    def test_error_in_callback_doesnt_crash(self, event_bus: EventBus):
        def bad_callback(e, d):
            raise ValueError("boom")

        received = []
        event_bus.subscribe("test:event", bad_callback)
        event_bus.subscribe("test:event", lambda e, d: received.append(d))
        event_bus.emit("test:event", "data")
        assert len(received) == 1  # Second callback still fires


class TestConfig:
    """Tests para la carga de configuración."""

    def test_default_config(self):
        config = AppConfig()
        assert config.app_name == "IA-CAM-SERVICE"
        assert config.camera.width == 640
        assert config.detection.face_enabled is True

    def test_load_nonexistent_returns_defaults(self):
        from pathlib import Path
        config = load_config(Path("/nonexistent/config.yaml"))
        assert config.app_name == "IA-CAM-SERVICE"
