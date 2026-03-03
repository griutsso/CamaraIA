"""
Buffer de frames thread-safe (patrón productor-consumidor).

Desacopla la captura de video del procesamiento de IA.
Múltiples consumidores pueden leer frames sin interferir entre sí.
"""

from __future__ import annotations

import logging
from queue import Empty, Full, Queue
from threading import Event
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class FrameBuffer:
    """
    Cola thread-safe para frames de video.

    El productor (cámara) coloca frames; los consumidores (detectores)
    los leen. Si la cola está llena, se descartan los frames más antiguos
    para mantener baja latencia (comportamiento de dashcam).
    """

    def __init__(self, max_size: int = 30) -> None:
        """
        Args:
            max_size: Capacidad máxima del buffer.
        """
        self._queue: Queue[np.ndarray] = Queue(maxsize=max_size)
        self._latest_frame: Optional[np.ndarray] = None
        self._stop_event = Event()
        self._frame_count: int = 0

    def put(self, frame: np.ndarray) -> None:
        """
        Añade un frame al buffer.

        Si está lleno, descarta el frame más antiguo (non-blocking).
        """
        if self._stop_event.is_set():
            return

        # Si la cola está llena, descartar el más antiguo
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except Empty:
                pass

        try:
            self._queue.put_nowait(frame)
            self._latest_frame = frame
            self._frame_count += 1
        except Full:
            pass

    def get(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        """
        Obtiene el siguiente frame del buffer.

        Args:
            timeout: Tiempo máximo de espera en segundos.

        Returns:
            Frame BGR o None si no hay frames disponibles.
        """
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None

    @property
    def latest_frame(self) -> Optional[np.ndarray]:
        """Último frame recibido (para preview sin consumir la cola)."""
        return self._latest_frame

    @property
    def size(self) -> int:
        """Cantidad de frames actualmente en el buffer."""
        return self._queue.qsize()

    @property
    def frame_count(self) -> int:
        """Total de frames recibidos desde el inicio."""
        return self._frame_count

    def clear(self) -> None:
        """Vacía el buffer."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Empty:
                break

    def stop(self) -> None:
        """Señaliza que no se aceptarán más frames."""
        self._stop_event.set()
        self.clear()

    def reset(self) -> None:
        """Reinicia el buffer para reutilización."""
        self._stop_event.clear()
        self.clear()
        self._frame_count = 0
        self._latest_frame = None
