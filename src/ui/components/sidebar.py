"""
Sidebar de navegación estilo macOS.

Panel lateral con botones de navegación, logo del sistema
y controles principales de la aplicación.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

import customtkinter as ctk

from src.ui.theme import THEME

logger = logging.getLogger(__name__)


class SidebarButton(ctk.CTkButton):
    """Botón de navegación del sidebar con estado activo/inactivo."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        text: str,
        icon_text: str = "",
        command: Optional[Callable] = None,
        **kwargs,
    ) -> None:
        self._is_active = False
        colors = THEME.colors

        super().__init__(
            master,
            text=f"  {icon_text}  {text}" if icon_text else f"  {text}",
            command=command,
            anchor="w",
            height=38,
            corner_radius=THEME.spacing.radius_sm,
            font=ctk.CTkFont(
                family=THEME.typography.family_display,
                size=THEME.typography.size_body,
            ),
            fg_color="transparent",
            text_color=colors.text_secondary,
            hover_color=colors.bg_tertiary,
            **kwargs,
        )

    def set_active(self, active: bool) -> None:
        """Actualiza el estado visual del botón."""
        colors = THEME.colors
        self._is_active = active

        if active:
            self.configure(
                fg_color=colors.accent_blue,
                text_color=colors.text_primary,
                hover_color=colors.accent_blue,
            )
        else:
            self.configure(
                fg_color="transparent",
                text_color=colors.text_secondary,
                hover_color=colors.bg_tertiary,
            )


class Sidebar(ctk.CTkFrame):
    """
    Panel lateral de navegación.

    Contiene el logo, botones de navegación y controles de cámara.
    """

    def __init__(
        self,
        master: ctk.CTk,
        width: int = 260,
        on_navigate: Optional[Callable[[str], None]] = None,
    ) -> None:
        colors = THEME.colors
        super().__init__(
            master,
            width=width,
            corner_radius=0,
            fg_color=colors.bg_sidebar,
        )
        self.grid_propagate(False)

        self._on_navigate = on_navigate
        self._buttons: dict[str, SidebarButton] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        """Construye los elementos del sidebar."""
        colors = THEME.colors
        typo = THEME.typography
        sp = THEME.spacing

        # ── Logo / Título ──
        logo_frame = ctk.CTkFrame(self, fg_color="transparent")
        logo_frame.pack(fill="x", padx=sp.lg, pady=(sp.xl, sp.xs))

        # Indicador visual (punto de color)
        indicator = ctk.CTkLabel(
            logo_frame,
            text="●",
            font=ctk.CTkFont(size=24),
            text_color=colors.accent_blue,
        )
        indicator.pack(side="left", padx=(0, sp.sm))

        title_label = ctk.CTkLabel(
            logo_frame,
            text="IA-CAM",
            font=ctk.CTkFont(
                family=typo.family_display,
                size=typo.size_heading,
                weight="bold",
            ),
            text_color=colors.text_primary,
        )
        title_label.pack(side="left")

        subtitle_label = ctk.CTkLabel(
            logo_frame,
            text="SERVICE",
            font=ctk.CTkFont(
                family=typo.family_display,
                size=typo.size_heading,
                weight="normal",
            ),
            text_color=colors.text_secondary,
        )
        subtitle_label.pack(side="left", padx=(4, 0))

        # ── Separador ──
        separator = ctk.CTkFrame(
            self, height=1, fg_color=colors.separator
        )
        separator.pack(fill="x", padx=sp.lg, pady=sp.md)

        # ── Sección: Navegación ──
        nav_label = ctk.CTkLabel(
            self,
            text="NAVEGACIÓN",
            font=ctk.CTkFont(
                family=typo.family_text,
                size=typo.size_micro,
                weight="bold",
            ),
            text_color=colors.text_tertiary,
            anchor="w",
        )
        nav_label.pack(fill="x", padx=sp.lg, pady=(sp.md, sp.xs))

        # Botones de navegación
        nav_items = [
            ("monitor", "Monitor en Vivo", "◉"),
            ("settings", "Configuración", "⚙"),
        ]

        for view_id, label, icon in nav_items:
            btn = SidebarButton(
                self,
                text=label,
                icon_text=icon,
                command=lambda vid=view_id: self._on_button_click(vid),
            )
            btn.pack(fill="x", padx=sp.sm, pady=2)
            self._buttons[view_id] = btn

        # ── Separador ──
        sep2 = ctk.CTkFrame(self, height=1, fg_color=colors.separator)
        sep2.pack(fill="x", padx=sp.lg, pady=sp.md)

        # ── Sección: Estado ──
        status_label = ctk.CTkLabel(
            self,
            text="ESTADO",
            font=ctk.CTkFont(
                family=typo.family_text,
                size=typo.size_micro,
                weight="bold",
            ),
            text_color=colors.text_tertiary,
            anchor="w",
        )
        status_label.pack(fill="x", padx=sp.lg, pady=(sp.md, sp.xs))

        # Indicadores de estado
        self._camera_status = self._create_status_indicator(
            "Cámara", "Desconectada", colors.text_tertiary
        )
        self._face_status = self._create_status_indicator(
            "Rostros", "Inactivo", colors.text_tertiary
        )
        self._plate_status = self._create_status_indicator(
            "Placas", "Inactivo", colors.text_tertiary
        )

        # ── Espaciador flexible ──
        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # ── Botón de control de cámara (al fondo) ──
        self._camera_btn = ctk.CTkButton(
            self,
            text="▶  Iniciar Cámara",
            height=40,
            corner_radius=THEME.spacing.radius_md,
            font=ctk.CTkFont(
                family=typo.family_display,
                size=typo.size_body,
                weight="bold",
            ),
            fg_color=colors.accent_green,
            hover_color="#28B84C",
            text_color="#FFFFFF",
        )
        self._camera_btn.pack(fill="x", padx=sp.lg, pady=(sp.sm, sp.xl))

        # ── Versión ──
        version_label = ctk.CTkLabel(
            self,
            text="v0.1.0 · Edge AI",
            font=ctk.CTkFont(
                family=typo.family_mono,
                size=typo.size_micro,
            ),
            text_color=colors.text_tertiary,
        )
        version_label.pack(pady=(0, sp.md))

    def _create_status_indicator(
        self, label: str, status: str, color: str
    ) -> ctk.CTkLabel:
        """Crea un indicador de estado en el sidebar."""
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=THEME.spacing.lg, pady=2)

        ctk.CTkLabel(
            frame,
            text=label,
            font=ctk.CTkFont(size=THEME.typography.size_caption),
            text_color=THEME.colors.text_secondary,
            anchor="w",
        ).pack(side="left")

        status_lbl = ctk.CTkLabel(
            frame,
            text=status,
            font=ctk.CTkFont(size=THEME.typography.size_caption),
            text_color=color,
            anchor="e",
        )
        status_lbl.pack(side="right")

        return status_lbl

    def _on_button_click(self, view_id: str) -> None:
        """Maneja click en botón de navegación."""
        if self._on_navigate:
            self._on_navigate(view_id)

    def set_active(self, view_id: str) -> None:
        """Marca un botón como activo."""
        for vid, btn in self._buttons.items():
            btn.set_active(vid == view_id)

    def update_camera_status(self, active: bool) -> None:
        """Actualiza el indicador de estado de la cámara."""
        colors = THEME.colors
        if active:
            self._camera_status.configure(
                text="Activa", text_color=colors.accent_green
            )
            self._camera_btn.configure(
                text="■  Detener Cámara",
                fg_color=colors.accent_red,
                hover_color="#E03E34",
            )
        else:
            self._camera_status.configure(
                text="Desconectada", text_color=colors.text_tertiary
            )
            self._camera_btn.configure(
                text="▶  Iniciar Cámara",
                fg_color=colors.accent_green,
                hover_color="#28B84C",
            )
