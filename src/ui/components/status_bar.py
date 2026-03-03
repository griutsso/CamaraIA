"""
Barra de estado inferior estilo macOS.

Muestra métricas del sistema: conteo de detecciones, uso de memoria,
estado de la cámara y hora actual.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

import customtkinter as ctk

from src.ui.theme import THEME

if TYPE_CHECKING:
    from src.core.container import ServiceContainer

logger = logging.getLogger(__name__)


class StatusBar(ctk.CTkFrame):
    """Barra de estado inferior con métricas en tiempo real."""

    def __init__(
        self,
        master: ctk.CTk,
        container: "ServiceContainer",
    ) -> None:
        colors = THEME.colors
        super().__init__(
            master,
            height=THEME.statusbar_height,
            fg_color=colors.bg_sidebar,
            corner_radius=0,
        )
        self.pack_propagate(False)

        self._container = container
        self._build_ui()
        self._update_clock()

    def _build_ui(self) -> None:
        """Construye los elementos de la barra de estado."""
        colors = THEME.colors
        typo = THEME.typography
        sp = THEME.spacing
        font = ctk.CTkFont(family=typo.family_mono, size=typo.size_micro)

        # ── Izquierda: Estado de conexión ──
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.pack(side="left", padx=sp.lg)

        self._conn_indicator = ctk.CTkLabel(
            left_frame,
            text="●",
            font=ctk.CTkFont(size=10),
            text_color=colors.text_tertiary,
        )
        self._conn_indicator.pack(side="left", padx=(0, 4))

        self._conn_label = ctk.CTkLabel(
            left_frame,
            text="Offline",
            font=font,
            text_color=colors.text_tertiary,
        )
        self._conn_label.pack(side="left")

        # ── Separador ──
        ctk.CTkLabel(
            self, text="│", font=font,
            text_color=colors.separator,
        ).pack(side="left", padx=sp.sm)

        # ── Centro: Contadores ──
        self._faces_count = ctk.CTkLabel(
            self,
            text="Rostros: 0",
            font=font,
            text_color=colors.detection_face,
        )
        self._faces_count.pack(side="left", padx=sp.sm)

        self._plates_count = ctk.CTkLabel(
            self,
            text="Placas: 0",
            font=font,
            text_color=colors.detection_plate,
        )
        self._plates_count.pack(side="left", padx=sp.sm)

        # ── Separador ──
        ctk.CTkLabel(
            self, text="│", font=font,
            text_color=colors.separator,
        ).pack(side="left", padx=sp.sm)

        # ── Memoria ──
        self._memory_label = ctk.CTkLabel(
            self,
            text="RAM: --",
            font=font,
            text_color=colors.text_tertiary,
        )
        self._memory_label.pack(side="left", padx=sp.sm)

        # ── Derecha: Reloj ──
        self._clock_label = ctk.CTkLabel(
            self,
            text="",
            font=font,
            text_color=colors.text_secondary,
        )
        self._clock_label.pack(side="right", padx=sp.lg)

    def update_stats(
        self,
        faces: int = 0,
        plates: int = 0,
        camera_active: bool = False,
        memory_mb: float = 0,
    ) -> None:
        """Actualiza las métricas mostradas."""
        colors = THEME.colors

        self._faces_count.configure(text=f"Rostros: {faces}")
        self._plates_count.configure(text=f"Placas: {plates}")

        if camera_active:
            self._conn_indicator.configure(text_color=colors.accent_green)
            self._conn_label.configure(
                text="Cámara activa", text_color=colors.accent_green
            )
        else:
            self._conn_indicator.configure(text_color=colors.text_tertiary)
            self._conn_label.configure(
                text="Offline", text_color=colors.text_tertiary
            )

        if memory_mb > 0:
            self._memory_label.configure(text=f"RAM: {memory_mb:.0f} MB")

    def _update_clock(self) -> None:
        """Actualiza el reloj cada segundo."""
        now = datetime.now().strftime("%H:%M:%S")
        self._clock_label.configure(text=now)
        self.after(1000, self._update_clock)
