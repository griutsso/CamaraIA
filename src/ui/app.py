"""
Ventana principal de IA-CAM-SERVICE.

Implementa la interfaz gráfica con estética macOS Dark Mode
usando CustomTkinter. Layout: Sidebar + Area Principal + Status Bar.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import customtkinter as ctk

from src.ui.theme import THEME
from src.ui.components.sidebar import Sidebar
from src.ui.components.status_bar import StatusBar
from src.ui.views.monitor_view import MonitorView
from src.ui.views.settings_view import SettingsView

if TYPE_CHECKING:
    from src.core.container import ServiceContainer

logger = logging.getLogger(__name__)


class MainApplication(ctk.CTk):
    """
    Ventana principal con layout macOS-inspired.

    ┌──────────┬───────────────────────────┐
    │          │                           │
    │ Sidebar  │      Vista Activa         │
    │          │    (Monitor/Settings)      │
    │          │                           │
    ├──────────┴───────────────────────────┤
    │            Status Bar                │
    └──────────────────────────────────────┘
    """

    def __init__(self, container: "ServiceContainer") -> None:
        super().__init__()

        self._container = container
        self._config = container.config
        self._current_view: str = "monitor"

        # ── Configuración de CustomTkinter ──
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # ── Ventana principal ──
        self.title(f"{self._config.app_name} v{self._config.version}")
        self.geometry(
            f"{self._config.ui.window_width}x{self._config.ui.window_height}"
        )
        self.minsize(THEME.min_window_width, THEME.min_window_height)
        self.configure(fg_color=THEME.colors.bg_primary)

        # Centrar en pantalla
        self._center_window()

        # ── Construir Layout ──
        self._build_layout()

        # ── Protocolo de cierre ──
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        logger.info("UI inicializada correctamente.")

    def _center_window(self) -> None:
        """Centra la ventana en la pantalla."""
        self.update_idletasks()
        w = self._config.ui.window_width
        h = self._config.ui.window_height
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_layout(self) -> None:
        """Construye el layout principal."""

        # Grid layout: sidebar (columna 0) + contenido (columna 1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ── Sidebar ──
        self._sidebar = Sidebar(
            master=self,
            width=THEME.sidebar_width,
            on_navigate=self._navigate_to,
        )
        self._sidebar.grid(row=0, column=0, sticky="nsw", padx=0, pady=0)

        # ── Contenedor de vistas ──
        self._view_container = ctk.CTkFrame(
            self,
            fg_color=THEME.colors.bg_primary,
            corner_radius=0,
        )
        self._view_container.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self._view_container.grid_rowconfigure(0, weight=1)
        self._view_container.grid_columnconfigure(0, weight=1)

        # ── Vistas ──
        self._views: dict[str, ctk.CTkFrame] = {}

        self._views["monitor"] = MonitorView(
            master=self._view_container,
            container=self._container,
        )

        self._views["settings"] = SettingsView(
            master=self._view_container,
            container=self._container,
        )

        # Mostrar vista inicial
        self._show_view("monitor")

        # ── Status Bar (fondo inferior) ──
        self._status_bar = StatusBar(
            master=self,
            container=self._container,
        )
        self._status_bar.grid(
            row=1, column=0, columnspan=2,
            sticky="sew", padx=0, pady=0,
        )

    def _navigate_to(self, view_name: str) -> None:
        """Navega a una vista específica."""
        if view_name == self._current_view:
            return
        self._show_view(view_name)

    def _show_view(self, view_name: str) -> None:
        """Muestra una vista y oculta las demás."""
        for name, view in self._views.items():
            if name == view_name:
                view.grid(row=0, column=0, sticky="nsew")
            else:
                view.grid_forget()
        self._current_view = view_name
        self._sidebar.set_active(view_name)
        logger.debug(f"Vista activa: {view_name}")

    def _on_close(self) -> None:
        """Manejo de cierre limpio de la aplicación."""
        logger.info("Cerrando aplicación...")

        # Detener pipeline si está corriendo
        try:
            self._container.shutdown()
        except Exception as e:
            logger.error(f"Error en shutdown: {e}")

        self.quit()
        self.destroy()

    def start(self) -> None:
        """Inicia el loop principal de la UI."""
        logger.info("Iniciando loop de UI...")
        self.mainloop()
