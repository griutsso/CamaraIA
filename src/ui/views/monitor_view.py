"""
Vista principal de monitoreo en vivo.

Contiene el panel de video, el log de detecciones y los controles
del pipeline. Layout adaptativo con proporciones 70/30.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import customtkinter as ctk

from src.ui.components.detection_log import DetectionLog
from src.ui.components.video_panel import VideoPanel
from src.ui.theme import THEME

if TYPE_CHECKING:
    from src.core.container import ServiceContainer

logger = logging.getLogger(__name__)


class MonitorView(ctk.CTkFrame):
    """
    Vista de monitoreo en tiempo real.

    ┌───────────────────────┬──────────────┐
    │                       │              │
    │    Video Panel        │  Detection   │
    │    (70% width)        │    Log       │
    │                       │  (30% width) │
    │                       │              │
    └───────────────────────┴──────────────┘
    """

    def __init__(
        self,
        master: ctk.CTkFrame,
        container: "ServiceContainer",
    ) -> None:
        colors = THEME.colors
        super().__init__(master, fg_color=colors.bg_primary, corner_radius=0)

        self._container = container
        self._build_ui()

    def _build_ui(self) -> None:
        """Construye el layout de la vista de monitoreo."""
        sp = THEME.spacing

        # Grid: video (70%) + log (30%)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=7)
        self.grid_columnconfigure(1, weight=3)

        # ── Panel de Video ──
        self._video_panel = VideoPanel(self)
        self._video_panel.grid(
            row=0, column=0,
            sticky="nsew",
            padx=(sp.md, sp.xs),
            pady=sp.md,
        )

        # ── Panel derecho: Log + Stats ──
        right_panel = ctk.CTkFrame(
            self, fg_color="transparent", corner_radius=0
        )
        right_panel.grid(
            row=0, column=1,
            sticky="nsew",
            padx=(sp.xs, sp.md),
            pady=sp.md,
        )
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)

        # ── Quick Stats (mini dashboard) ──
        self._stats_panel = self._build_stats_panel(right_panel)
        self._stats_panel.grid(row=0, column=0, sticky="ew", pady=(0, sp.sm))

        # ── Detection Log ──
        self._detection_log = DetectionLog(right_panel)
        self._detection_log.grid(row=1, column=0, sticky="nsew")

    def _build_stats_panel(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        """Construye el mini dashboard de estadísticas rápidas."""
        colors = THEME.colors
        typo = THEME.typography
        sp = THEME.spacing

        panel = ctk.CTkFrame(
            parent,
            fg_color=colors.bg_secondary,
            corner_radius=sp.radius_lg,
            height=90,
        )
        panel.pack_propagate(False)

        # Grid 2x2 para las métricas
        panel.grid_columnconfigure((0, 1), weight=1)
        panel.grid_rowconfigure((0, 1), weight=1)

        metrics = [
            ("Rostros Hoy", "0", colors.detection_face),
            ("Placas Hoy", "0", colors.detection_plate),
            ("Tiempo Activo", "00:00", colors.accent_green),
            ("Almacenamiento", "0 MB", colors.text_secondary),
        ]

        self._stat_values: list[ctk.CTkLabel] = []

        for i, (label, value, color) in enumerate(metrics):
            row, col = divmod(i, 2)
            cell = ctk.CTkFrame(panel, fg_color="transparent")
            cell.grid(row=row, column=col, sticky="nsew", padx=sp.sm, pady=4)

            ctk.CTkLabel(
                cell,
                text=label,
                font=ctk.CTkFont(
                    family=typo.family_text,
                    size=typo.size_micro,
                ),
                text_color=colors.text_tertiary,
                anchor="w",
            ).pack(fill="x")

            val_label = ctk.CTkLabel(
                cell,
                text=value,
                font=ctk.CTkFont(
                    family=typo.family_display,
                    size=typo.size_subheading,
                    weight="bold",
                ),
                text_color=color,
                anchor="w",
            )
            val_label.pack(fill="x")
            self._stat_values.append(val_label)

        return panel

    @property
    def video_panel(self) -> VideoPanel:
        return self._video_panel

    @property
    def detection_log(self) -> DetectionLog:
        return self._detection_log

    def update_stats(
        self,
        faces_today: int = 0,
        plates_today: int = 0,
        uptime: str = "00:00",
        storage_mb: float = 0,
    ) -> None:
        """Actualiza las métricas del mini dashboard."""
        if len(self._stat_values) >= 4:
            self._stat_values[0].configure(text=str(faces_today))
            self._stat_values[1].configure(text=str(plates_today))
            self._stat_values[2].configure(text=uptime)
            self._stat_values[3].configure(text=f"{storage_mb:.1f} MB")
