"""
Panel de visualización de video en tiempo real.

OPTIMIZACIÓN DE RENDIMIENTO:
  - Resize con cv2.resize (INTER_LINEAR) a tamaño de display ANTES de PIL.
  - ImageTk.PhotoImage directo (sin CTkImage — evita overhead de HiDPI).
  - Un solo resize por frame (OpenCV), sin doble escalado.
  - HUD actualizado cada N frames, no cada frame.
  - Cache de tamaño del widget.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

import cv2
import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk

from src.core.interfaces import Detection, DetectionType
from src.ui.theme import THEME

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)


class VideoPanel(ctk.CTkFrame):
    """
    Panel de video con overlay de detecciones.
    Usa ImageTk.PhotoImage directo para máximo rendimiento.
    """

    # Resolución de display (se reduce desde 1080p a esto)
    DISPLAY_WIDTH = 854
    DISPLAY_HEIGHT = 480

    def __init__(
        self,
        master: ctk.CTkFrame,
        **kwargs,
    ) -> None:
        colors = THEME.colors
        super().__init__(
            master,
            fg_color=colors.bg_secondary,
            corner_radius=THEME.spacing.radius_lg,
            **kwargs,
        )

        self._photo_image: Optional[ImageTk.PhotoImage] = None
        self._fps_history: list[float] = []
        self._last_frame_time: float = time.time()
        self._detections: list[Detection] = []
        self._frame_count: int = 0

        # Cache de tamaño de display
        self._display_size: tuple[int, int] = (self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT)

        self._build_ui()

    def _build_ui(self) -> None:
        """Construye los elementos del panel de video."""
        colors = THEME.colors
        typo = THEME.typography
        sp = THEME.spacing

        # ── Header del panel ──
        header = ctk.CTkFrame(self, fg_color="transparent", height=40)
        header.pack(fill="x", padx=sp.md, pady=(sp.md, 0))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Vista en Vivo",
            font=ctk.CTkFont(
                family=typo.family_display,
                size=typo.size_subheading,
                weight="bold",
            ),
            text_color=colors.text_primary,
        ).pack(side="left")

        # FPS Badge
        self._fps_badge = ctk.CTkLabel(
            header,
            text="-- FPS",
            font=ctk.CTkFont(family=typo.family_mono, size=typo.size_caption),
            text_color=colors.accent_green,
            fg_color=colors.bg_tertiary,
            corner_radius=THEME.spacing.radius_sm,
            padx=8,
            pady=2,
        )
        self._fps_badge.pack(side="right")

        # Resolución label
        self._res_label = ctk.CTkLabel(
            header,
            text="--",
            font=ctk.CTkFont(family=typo.family_mono, size=typo.size_micro),
            text_color=colors.text_tertiary,
        )
        self._res_label.pack(side="right", padx=(0, sp.sm))

        # ── Contenedor de video ──
        self._canvas_frame = ctk.CTkFrame(
            self,
            fg_color=colors.bg_primary,
            corner_radius=THEME.spacing.radius_md,
        )
        self._canvas_frame.pack(fill="both", expand=True, padx=sp.md, pady=sp.md)

        # Label de tkinter PURO para el video (mucho más rápido que CTkLabel)
        self._video_label = tk.Label(
            self._canvas_frame,
            bg=colors.bg_primary,
            borderwidth=0,
            highlightthickness=0,
        )
        self._video_label.pack(fill="both", expand=True)

        # Bind de resize para actualizar display_size
        self._video_label.bind("<Configure>", self._on_resize)

        # ── Placeholder ──
        self._placeholder = ctk.CTkLabel(
            self._canvas_frame,
            text="📷\n\nCámara no conectada\nPresione 'Iniciar Cámara' para comenzar",
            font=ctk.CTkFont(family=typo.family_display, size=typo.size_body),
            text_color=colors.text_tertiary,
            justify="center",
        )
        self._placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def _on_resize(self, event) -> None:
        """Actualiza el tamaño de display cuando el widget cambia."""
        if event.width > 10 and event.height > 10:
            self._display_size = (event.width, event.height)

    def update_frame(self, frame: "np.ndarray") -> None:
        """
        Actualiza el frame mostrado. Pipeline optimizado:
        1. cv2.resize al tamaño de display (rápido)
        2. cv2.cvtColor BGR→RGB (en frame pequeño)
        3. PIL Image.fromarray → ImageTk.PhotoImage (directo, sin CTkImage)
        """
        try:
            # Ocultar placeholder (solo primera vez)
            if self._placeholder.winfo_ismapped():
                self._placeholder.place_forget()

            self._frame_count += 1

            # ── FPS (solo calcular, actualizar UI cada 10 frames) ──
            now = time.time()
            dt = now - self._last_frame_time
            if dt > 0:
                self._fps_history.append(1.0 / dt)
                if len(self._fps_history) > 30:
                    self._fps_history.pop(0)
            self._last_frame_time = now

            # ── Obtener tamaño de display ──
            disp_w, disp_h = self._display_size
            if disp_w < 10 or disp_h < 10:
                return

            h, w = frame.shape[:2]

            # ── UN SOLO resize con OpenCV al tamaño exacto del widget ──
            ratio = min(disp_w / w, disp_h / h)
            new_w = int(w * ratio)
            new_h = int(h * ratio)

            if new_w != w or new_h != h:
                display_frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            else:
                display_frame = frame

            # ── Dibujar detecciones en frame reducido ──
            if self._detections:
                display_frame = self._draw_detections(display_frame, w, h)

            # ── BGR → RGB ──
            rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

            # ── PIL → ImageTk.PhotoImage (sin CTkImage, directo) ──
            pil_image = Image.fromarray(rgb)
            photo = ImageTk.PhotoImage(image=pil_image)

            self._video_label.configure(image=photo)
            self._photo_image = photo  # Mantener referencia

            # ── HUD cada 10 frames ──
            if self._frame_count % 10 == 0:
                self._update_hud(w, h)

        except Exception as e:
            if self._frame_count < 3:
                logger.error(f"Error actualizando frame: {e}")

    def set_detections(self, detections: list[Detection]) -> None:
        """Actualiza las detecciones a dibujar sobre el video."""
        self._detections = detections

    def _draw_detections(self, display_frame: "np.ndarray", orig_w: int, orig_h: int) -> "np.ndarray":
        """Dibuja bounding boxes en el frame reducido."""
        disp_h, disp_w = display_frame.shape[:2]
        scale_x = disp_w / orig_w
        scale_y = disp_h / orig_h

        colors_map = {
            DetectionType.FACE: (191, 90, 242),
            DetectionType.PLATE: (255, 210, 100),
        }

        frame = display_frame.copy()
        for det in self._detections:
            x1, y1, x2, y2 = det.bbox.to_absolute(orig_w, orig_h)
            x1, y1 = int(x1 * scale_x), int(y1 * scale_y)
            x2, y2 = int(x2 * scale_x), int(y2 * scale_y)
            color = colors_map.get(det.detection_type, (255, 255, 255))

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

            label = det.label
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)
            cv2.putText(frame, label, (x1 + 3, y1 - 3),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        return frame

    def _update_hud(self, frame_w: int, frame_h: int) -> None:
        """Actualiza métricas del HUD."""
        if not self._fps_history:
            return
        avg_fps = sum(self._fps_history) / len(self._fps_history)
        self._fps_badge.configure(text=f"{avg_fps:.0f} FPS")

        colors = THEME.colors
        if avg_fps >= 20:
            self._fps_badge.configure(text_color=colors.accent_green)
        elif avg_fps >= 12:
            self._fps_badge.configure(text_color=colors.accent_orange)
        else:
            self._fps_badge.configure(text_color=colors.accent_red)

        self._res_label.configure(text=f"{frame_w}x{frame_h}")

    @staticmethod
    def _fit_image(image: Image.Image, max_w: int, max_h: int) -> Image.Image:
        """Fallback por compatibilidad."""
        img_w, img_h = image.size
        ratio = min(max_w / img_w, max_h / img_h)
        if ratio >= 1.0:
            return image
        new_w = int(img_w * ratio)
        new_h = int(img_h * ratio)
        return image.resize((new_w, new_h), Image.Resampling.BILINEAR)
