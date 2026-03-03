"""
Tema Dark Mode inspirado en macOS / Apple Design System.

Centraliza todos los colores, fuentes y estilos visuales de la UI.
Cambiar el tema completo de la aplicación requiere modificar solo este archivo.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColorPalette:
    """Paleta de colores macOS Dark Mode."""

    # ── Fondos ──
    bg_primary: str = "#1E1E1E"       # Fondo principal (ventana)
    bg_secondary: str = "#2D2D2D"     # Paneles, cards
    bg_tertiary: str = "#3A3A3A"      # Hover, inputs
    bg_sidebar: str = "#252525"       # Sidebar navegación
    bg_elevated: str = "#383838"      # Elementos elevados (modales, tooltips)

    # ── Textos ──
    text_primary: str = "#FFFFFF"     # Texto principal
    text_secondary: str = "#A0A0A0"   # Texto secundario / labels
    text_tertiary: str = "#6B6B6B"    # Texto deshabilitado
    text_accent: str = "#0A84FF"      # Links, texto de acento

    # ── Acentos (sistema Apple) ──
    accent_blue: str = "#0A84FF"      # Azul principal
    accent_green: str = "#30D158"     # Éxito, activo
    accent_red: str = "#FF453A"       # Error, peligro
    accent_orange: str = "#FF9F0A"    # Advertencia
    accent_yellow: str = "#FFD60A"    # Info
    accent_purple: str = "#BF5AF2"    # Detección de rostros
    accent_teal: str = "#64D2FF"      # Detección de placas

    # ── Bordes y separadores ──
    border_subtle: str = "#3A3A3A"    # Bordes sutiles
    border_active: str = "#505050"    # Bordes activos
    separator: str = "#333333"        # Líneas separadoras

    # ── Detecciones (colores para bounding boxes) ──
    detection_face: str = "#BF5AF2"   # Púrpura para rostros
    detection_plate: str = "#64D2FF"  # Cian para placas

    # ── Overlay de video ──
    overlay_bg: str = "#000000B3"     # Fondo semi-transparente (70%)
    overlay_text: str = "#FFFFFF"     # Texto sobre overlay


@dataclass(frozen=True)
class Typography:
    """Sistema tipográfico estilo San Francisco."""

    # Familias (con fallbacks)
    family_display: str = "SF Pro Display"
    family_text: str = "SF Pro Text"
    family_mono: str = "SF Mono"
    fallback: str = "Helvetica Neue"
    fallback_system: str = "Arial"

    # Tamaños (en puntos)
    size_title: int = 22
    size_heading: int = 17
    size_subheading: int = 15
    size_body: int = 13
    size_caption: int = 11
    size_micro: int = 10

    # Pesos
    weight_bold: str = "bold"
    weight_medium: str = "normal"
    weight_regular: str = "normal"

    def font(self, size: int | None = None, weight: str | None = None) -> tuple:
        """Retorna tupla de fuente para CTk/Tk."""
        return (
            self.family_display,
            size or self.size_body,
            weight or self.weight_regular,
        )


@dataclass(frozen=True)
class Spacing:
    """Espaciado consistente (sistema de 4px)."""
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32
    section: int = 48

    # Radios de esquinas redondeadas (estilo macOS)
    radius_sm: int = 6
    radius_md: int = 10
    radius_lg: int = 14
    radius_xl: int = 20


@dataclass(frozen=True)
class MacOSTheme:
    """Tema completo macOS Dark Mode."""
    colors: ColorPalette = ColorPalette()
    typography: Typography = Typography()
    spacing: Spacing = Spacing()

    # Dimensiones de layout
    sidebar_width: int = 260
    statusbar_height: int = 36
    toolbar_height: int = 48
    min_window_width: int = 1024
    min_window_height: int = 680


# Instancia singleton del tema
THEME = MacOSTheme()
