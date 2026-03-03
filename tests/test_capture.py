"""
Tests para el módulo de captura de video.
"""

import numpy as np
import pytest

from src.capture.frame_buffer import FrameBuffer


class TestFrameBuffer:
    """Tests para el buffer de frames thread-safe."""

    def test_put_and_get(self):
        buffer = FrameBuffer(max_size=5)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        buffer.put(frame)
        result = buffer.get(timeout=1.0)
        assert result is not None
        assert result.shape == (480, 640, 3)

    def test_get_empty_returns_none(self):
        buffer = FrameBuffer(max_size=5)
        result = buffer.get(timeout=0.1)
        assert result is None

    def test_overflow_discards_oldest(self):
        buffer = FrameBuffer(max_size=2)
        for i in range(5):
            frame = np.full((10, 10, 3), i, dtype=np.uint8)
            buffer.put(frame)
        # Debe tener solo 2 frames (los más recientes)
        assert buffer.size <= 2

    def test_latest_frame(self):
        buffer = FrameBuffer(max_size=5)
        frame1 = np.zeros((10, 10, 3), dtype=np.uint8)
        frame2 = np.ones((10, 10, 3), dtype=np.uint8)
        buffer.put(frame1)
        buffer.put(frame2)
        assert np.array_equal(buffer.latest_frame, frame2)

    def test_frame_count(self):
        buffer = FrameBuffer(max_size=5)
        for _ in range(10):
            buffer.put(np.zeros((10, 10, 3), dtype=np.uint8))
        assert buffer.frame_count == 10

    def test_clear(self):
        buffer = FrameBuffer(max_size=5)
        for _ in range(3):
            buffer.put(np.zeros((10, 10, 3), dtype=np.uint8))
        buffer.clear()
        assert buffer.size == 0

    def test_stop_rejects_new_frames(self):
        buffer = FrameBuffer(max_size=5)
        buffer.stop()
        buffer.put(np.zeros((10, 10, 3), dtype=np.uint8))
        assert buffer.size == 0

    def test_reset(self):
        buffer = FrameBuffer(max_size=5)
        buffer.put(np.zeros((10, 10, 3), dtype=np.uint8))
        buffer.stop()
        buffer.reset()
        buffer.put(np.zeros((10, 10, 3), dtype=np.uint8))
        assert buffer.size == 1
        assert buffer.frame_count == 1
