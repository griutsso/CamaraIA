"""
Estado centralizado y thread-safe del servidor web.

Reemplaza las ~15 variables globales de server.py con una clase
que protege todo el acceso concurrente mediante locks.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional

import cv2
import numpy as np

from src.core.interfaces import Detection


class WebState:
    """
    Estado compartido entre el capture thread, el detection pipeline
    y los handlers HTTP de Flask. Todo acceso es thread-safe.
    """

    def __init__(self) -> None:
        # ── Frame de video ──
        self._frame_lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None

        # ── Detecciones actuales (para dibujar bounding boxes) ──
        self._detections_lock = threading.Lock()
        self._latest_detections: list[Detection] = []

        # ── Estado de cámara ──
        self._camera_lock = threading.Lock()
        self._camera_active = False
        self._camera_info: dict[str, Any] = {}
        self._fps_counter: float = 0.0
        self._start_time: float = 0.0

        # ── Sesión activa ──
        self._session_lock = threading.Lock()
        self._session_id: Optional[str] = None
        self._session_folder: Optional[str] = None

        # ── Grabación de video ──
        self._recording_lock = threading.Lock()
        self._recording_active = False
        self._recording_path: Optional[str] = None
        self._recording_start_time: Optional[float] = None
        self._video_writer: Optional[cv2.VideoWriter] = None

    # ═══ Frame ═══

    def set_frame(self, frame: np.ndarray) -> None:
        """Almacena el último frame capturado."""
        with self._frame_lock:
            self._latest_frame = frame

    def get_frame(self) -> Optional[np.ndarray]:
        """Obtiene el último frame (o None)."""
        with self._frame_lock:
            return self._latest_frame

    # ═══ Detecciones actuales ═══

    def set_detections(self, detections: list[Detection]) -> None:
        """Actualiza las detecciones visibles en el stream."""
        with self._detections_lock:
            self._latest_detections = list(detections)

    def get_detections(self) -> list[Detection]:
        """Obtiene las detecciones actuales."""
        with self._detections_lock:
            return list(self._latest_detections)

    # ═══ Estado de cámara ═══

    @property
    def camera_active(self) -> bool:
        with self._camera_lock:
            return self._camera_active

    @camera_active.setter
    def camera_active(self, value: bool) -> None:
        with self._camera_lock:
            self._camera_active = value

    def set_camera_info(
        self,
        info: dict[str, Any],
        start_time: Optional[float] = None,
    ) -> None:
        """Establece la información de la cámara al iniciar."""
        with self._camera_lock:
            self._camera_info = info
            if start_time is not None:
                self._start_time = start_time

    def set_fps(self, fps: float) -> None:
        """Actualiza el contador de FPS del capture thread."""
        with self._camera_lock:
            self._fps_counter = fps

    def get_camera_status(self) -> dict[str, Any]:
        """Retorna el estado completo de la cámara."""
        with self._camera_lock:
            uptime = 0
            if self._camera_active and self._start_time > 0:
                uptime = int(time.time() - self._start_time)
            return {
                "active": self._camera_active,
                "camera": dict(self._camera_info) if self._camera_active else {},
                "fps": round(self._fps_counter, 1),
                "uptime": uptime,
            }

    # ═══ Sesión ═══

    @property
    def session_id(self) -> Optional[str]:
        with self._session_lock:
            return self._session_id

    @session_id.setter
    def session_id(self, value: Optional[str]) -> None:
        with self._session_lock:
            self._session_id = value

    @property
    def session_folder(self) -> Optional[str]:
        with self._session_lock:
            return self._session_folder

    @session_folder.setter
    def session_folder(self, value: Optional[str]) -> None:
        with self._session_lock:
            self._session_folder = value

    # ═══ Grabación de video ═══

    @property
    def recording_active(self) -> bool:
        with self._recording_lock:
            return self._recording_active

    def set_recording(
        self,
        active: bool,
        path: Optional[str] = None,
        writer: Optional[cv2.VideoWriter] = None,
    ) -> None:
        """Establece el estado de grabación y el video writer."""
        with self._recording_lock:
            self._recording_active = active
            if path is not None:
                self._recording_path = path
            if writer is not None:
                self._video_writer = writer
            if active:
                self._recording_start_time = time.time()
            else:
                self._recording_start_time = None

    def get_recording_info(self) -> dict[str, Any]:
        """Retorna información del estado de grabación."""
        with self._recording_lock:
            info: dict[str, Any] = {
                "active": self._recording_active,
                "path": self._recording_path or "",
            }
            if self._recording_active and self._recording_start_time:
                info["duration"] = int(time.time() - self._recording_start_time)
            return info

    def get_video_writer(self) -> Optional[cv2.VideoWriter]:
        """Obtiene el video writer actual (para el capture thread)."""
        with self._recording_lock:
            return self._video_writer

    def write_frame(self, frame: np.ndarray) -> bool:
        """
        Escribe un frame al video writer de forma atómica y thread-safe.

        Mantiene el lock durante toda la operación write() para evitar
        que close_video_writer() libere el writer mientras se escribe.
        Retorna True si se escribió, False si no hay grabación activa.
        """
        with self._recording_lock:
            if self._recording_active and self._video_writer is not None:
                try:
                    self._video_writer.write(frame)
                    return True
                except Exception:
                    return False
            return False

    def close_video_writer(self) -> None:
        """Cierra el video writer de forma segura."""
        with self._recording_lock:
            if self._video_writer:
                self._video_writer.release()
                self._video_writer = None
            self._recording_active = False

    # ═══ Reset ═══

    def reset(self) -> None:
        """Limpia todo el estado (al detener la cámara)."""
        with self._frame_lock:
            self._latest_frame = None
        with self._detections_lock:
            self._latest_detections.clear()
        with self._camera_lock:
            self._camera_active = False
            self._camera_info.clear()
            self._fps_counter = 0.0
        with self._session_lock:
            self._session_id = None
            self._session_folder = None
        with self._recording_lock:
            # Liberar el video writer si quedó abierto
            if self._video_writer is not None:
                try:
                    self._video_writer.release()
                except Exception:
                    pass
                self._video_writer = None
            self._recording_active = False
            self._recording_path = None
            self._recording_start_time = None
