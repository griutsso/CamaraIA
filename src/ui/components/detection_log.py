"""
Panel de log de detecciones en tiempo real.

Muestra las detecciones más recientes con timestamp, tipo,
confianza y miniatura del crop detectado.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import customtkinter as ctk

from src.core.interfaces import Detection, DetectionType
from src.ui.theme import THEME

logger = logging.getLogger(__name__)


class DetectionLogEntry(ctk.CTkFrame):
    """Entrada individual en el log de detecciones."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        detection_type: str,
        confidence: float,
        timestamp: str,
        detail: str = "",
    ) -> None:
        colors = THEME.colors
        typo = THEME.typography

        super().__init__(
            master,
            fg_color=colors.bg_tertiary,
            corner_radius=THEME.spacing.radius_sm,
            height=52,
        )
        self.pack_propagate(False)

        # Color del indicador según tipo
        type_colors = {
            "FACE": colors.detection_face,
            "PLATE": colors.detection_plate,
        }
        indicator_color = type_colors.get(detection_type, colors.text_tertiary)

        # ── Indicador de tipo (barra lateral de color) ──
        indicator = ctk.CTkFrame(
            self, width=3, fg_color=indicator_color, corner_radius=2
        )
        indicator.pack(side="left", fill="y", padx=(6, 8), pady=6)

        # ── Contenido ──
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, pady=4)

        # Línea 1: Tipo + Confianza
        top_row = ctk.CTkFrame(content, fg_color="transparent")
        top_row.pack(fill="x")

        type_label = detection_type.capitalize()
        ctk.CTkLabel(
            top_row,
            text=type_label,
            font=ctk.CTkFont(
                family=typo.family_display,
                size=typo.size_caption,
                weight="bold",
            ),
            text_color=indicator_color,
        ).pack(side="left")

        ctk.CTkLabel(
            top_row,
            text=f"{confidence:.0%}",
            font=ctk.CTkFont(
                family=typo.family_mono,
                size=typo.size_micro,
            ),
            text_color=colors.text_secondary,
        ).pack(side="right", padx=(0, 8))

        # Línea 2: Detalle + Timestamp
        bottom_row = ctk.CTkFrame(content, fg_color="transparent")
        bottom_row.pack(fill="x")

        detail_text = detail if detail else "Detectado"
        ctk.CTkLabel(
            bottom_row,
            text=detail_text,
            font=ctk.CTkFont(
                family=typo.family_text,
                size=typo.size_micro,
            ),
            text_color=colors.text_secondary,
        ).pack(side="left")

        ctk.CTkLabel(
            bottom_row,
            text=timestamp,
            font=ctk.CTkFont(
                family=typo.family_mono,
                size=typo.size_micro,
            ),
            text_color=colors.text_tertiary,
        ).pack(side="right", padx=(0, 8))


class DetectionLog(ctk.CTkFrame):
    """
    Panel scrollable con el log de detecciones recientes.
    """

    MAX_ENTRIES = 50

    def __init__(self, master: ctk.CTkFrame, **kwargs) -> None:
        colors = THEME.colors
        super().__init__(
            master,
            fg_color=colors.bg_secondary,
            corner_radius=THEME.spacing.radius_lg,
            **kwargs,
        )

        self._entries: list[DetectionLogEntry] = []
        self._build_ui()

    def _build_ui(self) -> None:
        """Construye el panel de log."""
        colors = THEME.colors
        typo = THEME.typography
        sp = THEME.spacing

        # ── Header ──
        header = ctk.CTkFrame(self, fg_color="transparent", height=36)
        header.pack(fill="x", padx=sp.md, pady=(sp.md, sp.xs))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Detecciones Recientes",
            font=ctk.CTkFont(
                family=typo.family_display,
                size=typo.size_body,
                weight="bold",
            ),
            text_color=colors.text_primary,
        ).pack(side="left")

        self._count_badge = ctk.CTkLabel(
            header,
            text="0",
            font=ctk.CTkFont(
                family=typo.family_mono,
                size=typo.size_micro,
            ),
            text_color=colors.text_secondary,
            fg_color=colors.bg_tertiary,
            corner_radius=8,
            padx=8,
            pady=2,
        )
        self._count_badge.pack(side="right")

        # ── Lista scrollable ──
        self._scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
        )
        self._scroll_frame.pack(fill="both", expand=True, padx=sp.sm, pady=(0, sp.sm))

    def add_detection(self, detection: Detection) -> None:
        """Añade una nueva detección al log."""
        entry = DetectionLogEntry(
            master=self._scroll_frame,
            detection_type=detection.detection_type.name,
            confidence=detection.confidence,
            timestamp=detection.timestamp.strftime("%H:%M:%S"),
            detail=detection.metadata.get("plate_text", ""),
        )
        entry.pack(fill="x", pady=2)

        self._entries.insert(0, entry)

        # Limitar entradas
        while len(self._entries) > self.MAX_ENTRIES:
            old = self._entries.pop()
            old.destroy()

        self._count_badge.configure(text=str(len(self._entries)))

    def clear(self) -> None:
        """Limpia todo el log."""
        for entry in self._entries:
            entry.destroy()
        self._entries.clear()
        self._count_badge.configure(text="0")
