"""
Tests para el módulo de almacenamiento.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from src.core.events import EventBus
from src.core.interfaces import BoundingBox, Detection, DetectionType
from src.storage.database import SQLiteStorage


@pytest.fixture
def temp_storage(event_bus: EventBus):
    """Storage temporal para tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SQLiteStorage(
            db_path=f"{tmpdir}/test.db",
            images_path=f"{tmpdir}/captures",
            event_bus=event_bus,
        )
        yield storage
        storage.close()


@pytest.fixture
def sample_detection() -> Detection:
    """Detección de ejemplo para tests."""
    return Detection(
        detection_type=DetectionType.FACE,
        bbox=BoundingBox(x1=0.1, y1=0.2, x2=0.5, y2=0.8),
        confidence=0.92,
        track_id=1,
        crop_image=np.zeros((100, 80, 3), dtype=np.uint8),
        metadata={"face_size": (80, 120)},
    )


class TestSQLiteStorage:
    """Tests para el backend SQLite."""

    def test_save_detection(self, temp_storage, sample_detection):
        det_id = temp_storage.save_detection(sample_detection)
        assert det_id is not None
        assert len(det_id) > 0

    def test_get_detections(self, temp_storage, sample_detection):
        temp_storage.save_detection(sample_detection)
        results = temp_storage.get_detections()
        assert len(results) == 1
        assert results[0]["type"] == "FACE"

    def test_get_detections_filtered(self, temp_storage):
        face = Detection(
            detection_type=DetectionType.FACE,
            bbox=BoundingBox(0, 0, 1, 1),
            confidence=0.9,
        )
        plate = Detection(
            detection_type=DetectionType.PLATE,
            bbox=BoundingBox(0, 0, 1, 1),
            confidence=0.8,
            metadata={"plate_text": "ABC-123"},
        )
        temp_storage.save_detection(face)
        temp_storage.save_detection(plate)

        faces = temp_storage.get_detections(detection_type=DetectionType.FACE)
        assert len(faces) == 1
        assert faces[0]["type"] == "FACE"

    def test_get_stats(self, temp_storage, sample_detection):
        temp_storage.save_detection(sample_detection)
        stats = temp_storage.get_stats()
        assert stats["total"] == 1
        assert "FACE" in stats["counts"]

    def test_event_emitted_on_save(self, temp_storage, sample_detection, event_bus):
        received = []
        event_bus.subscribe(
            EventBus.DETECTION_SAVED, lambda e, d: received.append(d)
        )
        temp_storage.save_detection(sample_detection)
        assert len(received) == 1
        assert received[0]["type"] == "FACE"

    def test_image_saved_to_disk(self, temp_storage, sample_detection):
        temp_storage.save_detection(sample_detection)
        results = temp_storage.get_detections()
        image_path = results[0]["image_path"]
        assert image_path is not None
        assert Path(image_path).exists()
