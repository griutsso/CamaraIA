"""
Implementaciones concretas de fuentes de video.

Soporta: Webcam USB/CSI, archivos de video y streams RTSP.
Patrón Strategy + Template Method para comportamiento compartido.

NOTA macOS (AVFoundation):
  - La cámara DEBE leerse desde el main thread.
  - read_frame() NUNCA bloquea (sin sleep).
  - Se auto-detectan resolución y FPS nativos si no se especifican.
  - Warmup: los primeros frames pueden ser negros — es normal.
"""

from __future__ import annotations

import logging
import platform
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from src.core.interfaces import IVideoSource

logger = logging.getLogger(__name__)

# Detectar macOS para ajustes específicos de AVFoundation
_IS_MACOS = platform.system() == "Darwin"


class WebcamSource(IVideoSource):
    """
    Fuente de video desde webcam USB o CSI.

    Características:
      - Auto-detección de resolución y FPS nativos de la cámara.
      - Warmup transparente (frames iniciales negros no cuentan como fallos).
      - read_frame() NUNCA bloquea — devuelve None si no hay frame.
      - Reconexión automática ante desconexiones reales.
    """

    # Frames fallidos (ret=False) consecutivos antes de reconexión.
    # Es alto porque en macOS los primeros frames pueden fallar.
    MAX_CONSECUTIVE_FAILURES = 30

    # Período de warmup: durante estos segundos no contamos fallos.
    WARMUP_SECONDS = 3.0

    def __init__(
        self,
        device_index: int | str = 0,
        width: int = 0,       # 0 = auto-detectar
        height: int = 0,      # 0 = auto-detectar
        target_fps: int = 0,  # 0 = auto-detectar
        reconnect_attempts: int = 5,
        reconnect_delay: float = 2.0,
    ) -> None:
        self._device_index = device_index
        self._requested_width = width
        self._requested_height = height
        self._requested_fps = target_fps
        self._reconnect_attempts = reconnect_attempts
        self._reconnect_delay = reconnect_delay

        self._cap: Optional[cv2.VideoCapture] = None
        self._active = False
        self._width: int = 0
        self._height: int = 0
        self._actual_fps: float = 0.0
        self._consecutive_failures: int = 0
        self._start_time: float = 0.0
        self._total_frames_read: int = 0
        self._total_frames_ok: int = 0

    def start(self) -> None:
        """Inicia la captura desde la webcam con auto-detección."""
        logger.info(f"Iniciando webcam (device={self._device_index}, macOS={_IS_MACOS})...")

        # Abrir cámara
        self._cap = self._open_camera()
        if self._cap is None or not self._cap.isOpened():
            raise RuntimeError(
                f"No se pudo abrir la cámara en índice {self._device_index}. "
                f"Verifica permisos en Ajustes del Sistema > Privacidad > Cámara."
            )

        # Aplicar resolución/FPS solo si el usuario los especificó (>0)
        if self._requested_width > 0 and self._requested_height > 0:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._requested_width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._requested_height)
            logger.info(f"  Resolución solicitada: {self._requested_width}x{self._requested_height}")
        if self._requested_fps > 0:
            self._cap.set(cv2.CAP_PROP_FPS, self._requested_fps)
            logger.info(f"  FPS solicitado: {self._requested_fps}")

        # Leer valores REALES que la cámara asignó
        self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._actual_fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0

        self._active = True
        self._consecutive_failures = 0
        self._total_frames_read = 0
        self._total_frames_ok = 0
        self._start_time = time.time()

        logger.info(
            f"Webcam activa: {self._width}x{self._height} @ {self._actual_fps:.1f} FPS "
            f"(warmup {self.WARMUP_SECONDS}s)"
        )

    def read_frame(self) -> Optional[np.ndarray]:
        """
        Lee un frame de la webcam. NUNCA bloquea.

        Retorna:
          - np.ndarray si hay frame válido (incluyendo frames negros de warmup).
          - None si no hay frame disponible (fallo transitorio).
          - None + is_active()=False si la cámara se desconectó.
        """
        if not self._cap or not self._active:
            return None

        ret, frame = self._cap.read()
        self._total_frames_read += 1

        if not ret or frame is None:
            self._consecutive_failures += 1

            # ¿Estamos en periodo de warmup? Ser más tolerante.
            in_warmup = (time.time() - self._start_time) < self.WARMUP_SECONDS
            max_failures = self.MAX_CONSECUTIVE_FAILURES * 3 if in_warmup else self.MAX_CONSECUTIVE_FAILURES

            if self._consecutive_failures <= max_failures:
                # Fallo transitorio — no bloquear, solo log cada 10
                if self._consecutive_failures % 10 == 0:
                    phase = "warmup" if in_warmup else "normal"
                    logger.debug(
                        f"Frames perdidos: {self._consecutive_failures}/{max_failures} ({phase})"
                    )
                return None  # SIN sleep — no bloquear main thread

            # Demasiados fallos: intentar reconexión
            logger.warning(
                f"{self._consecutive_failures} frames perdidos consecutivos. "
                f"Intentando reconexión..."
            )
            if self._try_reconnect():
                self._consecutive_failures = 0
                self._start_time = time.time()  # Reset warmup
                return None  # Siguiente frame en la próxima iteración
            else:
                self._active = False
                return None

        # ── Frame exitoso ──
        self._consecutive_failures = 0
        self._total_frames_ok += 1

        # Log de primer frame exitoso
        if self._total_frames_ok == 1:
            elapsed = time.time() - self._start_time
            mean_brightness = float(np.mean(frame))
            logger.info(
                f"Primer frame válido: {frame.shape} | "
                f"brillo={mean_brightness:.1f} | "
                f"después de {elapsed:.2f}s y {self._total_frames_read} intentos"
            )

        return frame

    def stop(self) -> None:
        """Detiene la webcam y libera recursos."""
        self._active = False
        if self._cap:
            self._cap.release()
            self._cap = None
        logger.info(
            f"Webcam detenida. Frames: {self._total_frames_ok}/{self._total_frames_read} exitosos."
        )

    def is_active(self) -> bool:
        return self._active

    @property
    def fps(self) -> float:
        return self._actual_fps

    @property
    def resolution(self) -> tuple[int, int]:
        return (self._width, self._height)

    def _open_camera(self) -> Optional[cv2.VideoCapture]:
        """Abre la cámara con el backend apropiado para el SO."""
        try:
            if _IS_MACOS and isinstance(self._device_index, int):
                cap = cv2.VideoCapture(self._device_index, cv2.CAP_AVFOUNDATION)
                logger.debug("Backend: CAP_AVFOUNDATION")
            else:
                cap = cv2.VideoCapture(self._device_index)
                logger.debug("Backend: auto")
            return cap
        except Exception as e:
            logger.error(f"Error abriendo cámara: {e}")
            return None

    def _try_reconnect(self) -> bool:
        """Intenta reconectar la cámara."""
        for attempt in range(1, self._reconnect_attempts + 1):
            logger.info(
                f"Reconexión intento {attempt}/{self._reconnect_attempts}..."
            )
            if self._cap:
                self._cap.release()
                self._cap = None

            time.sleep(self._reconnect_delay)

            self._cap = self._open_camera()
            if self._cap and self._cap.isOpened():
                # Leer resolución real
                self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self._actual_fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
                self._active = True
                logger.info(
                    f"Reconexión exitosa: {self._width}x{self._height} @ {self._actual_fps:.1f} FPS"
                )
                return True

        logger.error("Reconexión fallida tras todos los intentos.")
        return False


class FileSource(IVideoSource):
    """
    Fuente de video desde archivo local.
    Útil para testing y reproducción de grabaciones.
    """

    def __init__(self, file_path: str, loop: bool = False) -> None:
        self._file_path = Path(file_path)
        self._loop = loop
        self._cap: Optional[cv2.VideoCapture] = None
        self._active = False
        self._fps_value: float = 30.0
        self._width: int = 0
        self._height: int = 0

    def start(self) -> None:
        if not self._file_path.exists():
            raise FileNotFoundError(f"Video no encontrado: {self._file_path}")

        self._cap = cv2.VideoCapture(str(self._file_path))
        if not self._cap.isOpened():
            raise RuntimeError(f"No se pudo abrir: {self._file_path}")

        self._fps_value = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._active = True
        logger.info(f"FileSource activa: {self._file_path.name}")

    def read_frame(self) -> Optional[np.ndarray]:
        if not self._cap or not self._active:
            return None
        ret, frame = self._cap.read()
        if not ret:
            if self._loop:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()
                if ret:
                    return frame
            self._active = False
            return None
        return frame

    def stop(self) -> None:
        self._active = False
        if self._cap:
            self._cap.release()
            self._cap = None

    def is_active(self) -> bool:
        return self._active

    @property
    def fps(self) -> float:
        return self._fps_value

    @property
    def resolution(self) -> tuple[int, int]:
        return (self._width, self._height)


class RTSPSource(IVideoSource):
    """Fuente de video desde stream RTSP."""

    def __init__(self, url: str, width: int = 640, height: int = 480) -> None:
        self._url = url
        self._width = width
        self._height = height
        self._cap: Optional[cv2.VideoCapture] = None
        self._active = False

    def start(self) -> None:
        self._cap = cv2.VideoCapture(self._url)
        if not self._cap.isOpened():
            raise RuntimeError(f"No se pudo conectar a RTSP: {self._url}")
        self._active = True
        logger.info(f"RTSPSource conectada: {self._url}")

    def read_frame(self) -> Optional[np.ndarray]:
        if not self._cap or not self._active:
            return None
        ret, frame = self._cap.read()
        if not ret:
            self._active = False
            return None
        return frame

    def stop(self) -> None:
        self._active = False
        if self._cap:
            self._cap.release()
            self._cap = None

    def is_active(self) -> bool:
        return self._active

    @property
    def fps(self) -> float:
        if self._cap:
            return self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        return 30.0

    @property
    def resolution(self) -> tuple[int, int]:
        return (self._width, self._height)
