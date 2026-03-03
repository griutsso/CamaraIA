"""
Vista de configuración del sistema.

Permite ajustar parámetros de cámara, detección y almacenamiento.
Se acopla dinámicamente a la cámara cuando se conecta.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from src.ui.theme import THEME

if TYPE_CHECKING:
    from src.core.container import ServiceContainer

logger = logging.getLogger(__name__)


class SettingsSection(ctk.CTkFrame):
    """Sección agrupada de configuración con título."""

    def __init__(self, master: ctk.CTkFrame, title: str, **kwargs) -> None:
        colors = THEME.colors
        typo = THEME.typography
        sp = THEME.spacing

        super().__init__(
            master,
            fg_color=colors.bg_secondary,
            corner_radius=sp.radius_lg,
            **kwargs,
        )

        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(
                family=typo.family_display,
                size=typo.size_subheading,
                weight="bold",
            ),
            text_color=colors.text_primary,
            anchor="w",
        ).pack(fill="x", padx=sp.lg, pady=(sp.lg, sp.sm))

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="x", padx=sp.lg, pady=(0, sp.lg))


class SettingsView(ctk.CTkFrame):
    """
    Vista de configuración con secciones agrupadas.
    Estilo macOS System Preferences. Se acopla a la cámara detectada.
    """

    def __init__(
        self,
        master: ctk.CTkFrame,
        container: "ServiceContainer",
    ) -> None:
        colors = THEME.colors
        super().__init__(master, fg_color=colors.bg_primary, corner_radius=0)

        self._container = container
        self._config = container.config

        # Referencias a widgets que se actualizan dinámicamente
        self._cam_resolution_menu: Optional[ctk.CTkOptionMenu] = None
        self._cam_fps_entry: Optional[ctk.CTkEntry] = None
        self._cam_source_entry: Optional[ctk.CTkEntry] = None
        self._cam_status_label: Optional[ctk.CTkLabel] = None
        self._confidence_slider: Optional[ctk.CTkSlider] = None
        self._confidence_label: Optional[ctk.CTkLabel] = None
        self._face_switch: Optional[ctk.CTkSwitch] = None
        self._plate_switch: Optional[ctk.CTkSwitch] = None
        self._fps_switch: Optional[ctk.CTkSwitch] = None
        self._bbox_switch: Optional[ctk.CTkSwitch] = None
        self._encryption_switch: Optional[ctk.CTkSwitch] = None
        self._storage_entry: Optional[ctk.CTkEntry] = None
        self._save_btn: Optional[ctk.CTkButton] = None
        self._status_message: Optional[ctk.CTkLabel] = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Construye las secciones de configuración."""
        colors = THEME.colors
        typo = THEME.typography
        sp = THEME.spacing

        # ── Scrollable content ──
        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
        )
        scroll.pack(fill="both", expand=True, padx=sp.lg, pady=sp.md)

        # ── Header ──
        ctk.CTkLabel(
            scroll,
            text="Configuración",
            font=ctk.CTkFont(
                family=typo.family_display,
                size=typo.size_title,
                weight="bold",
            ),
            text_color=colors.text_primary,
            anchor="w",
        ).pack(fill="x", pady=(0, sp.lg))

        # ── Sección: Cámara ──
        cam_section = SettingsSection(scroll, title="Cámara")
        cam_section.pack(fill="x", pady=(0, sp.md))

        # Status de cámara (se actualiza dinámicamente)
        status_row = ctk.CTkFrame(cam_section.content, fg_color="transparent")
        status_row.pack(fill="x", pady=sp.xs)

        ctk.CTkLabel(
            status_row,
            text="Estado",
            font=ctk.CTkFont(family=typo.family_display, size=typo.size_body),
            text_color=colors.text_primary,
            anchor="w",
        ).pack(side="left")

        self._cam_status_label = ctk.CTkLabel(
            status_row,
            text="● Desconectada",
            font=ctk.CTkFont(family=typo.family_mono, size=typo.size_caption),
            text_color=colors.text_tertiary,
            anchor="e",
        )
        self._cam_status_label.pack(side="right")

        # Fuente de video
        self._cam_source_entry = self._add_setting_row(
            cam_section.content,
            "Fuente de video",
            "Índice del dispositivo (0 = default)",
            default_value=str(self._config.camera.source),
        )

        # Resolución
        current_res = "Auto-detectar"
        if self._config.camera.width > 0 and self._config.camera.height > 0:
            current_res = f"{self._config.camera.width}x{self._config.camera.height}"

        self._cam_resolution_menu = self._add_option_row(
            cam_section.content,
            "Resolución",
            "Auto-detectar usa la resolución nativa de la cámara",
            options=["Auto-detectar", "640x480", "1280x720", "1920x1080"],
            default_value=current_res,
        )

        # FPS
        fps_text = "Auto" if self._config.camera.fps == 0 else str(self._config.camera.fps)
        self._cam_fps_entry = self._add_setting_row(
            cam_section.content,
            "FPS objetivo",
            "0 o 'Auto' = usar FPS nativo de la cámara",
            default_value=fps_text,
        )

        # ── Sección: Detección ──
        det_section = SettingsSection(scroll, title="Detección de IA")
        det_section.pack(fill="x", pady=(0, sp.md))

        self._face_switch = self._add_toggle_row(
            det_section.content,
            "Detección de rostros",
            "Módulo YOLO para detección facial",
            default=self._config.detection.face_enabled,
        )

        self._plate_switch = self._add_toggle_row(
            det_section.content,
            "Detección de placas",
            "OCR para placas vehiculares",
            default=self._config.detection.plate_enabled,
        )

        self._confidence_slider, self._confidence_label = self._add_slider_row(
            det_section.content,
            "Umbral de confianza",
            "Confianza mínima para aceptar una detección",
            from_=0.1,
            to=0.95,
            default=self._config.detection.confidence_threshold,
        )

        # ── Sección: Almacenamiento ──
        storage_section = SettingsSection(scroll, title="Almacenamiento")
        storage_section.pack(fill="x", pady=(0, sp.md))

        self._encryption_switch = self._add_toggle_row(
            storage_section.content,
            "Cifrado AES-256",
            "Cifra las imágenes almacenadas en disco",
            default=self._config.storage.encryption_enabled,
        )

        self._storage_entry = self._add_setting_row(
            storage_section.content,
            "Almacenamiento máximo (MB)",
            f"Límite actual: {self._config.storage.max_storage_mb} MB",
            default_value=str(self._config.storage.max_storage_mb),
        )

        # ── Sección: Interfaz ──
        ui_section = SettingsSection(scroll, title="Interfaz")
        ui_section.pack(fill="x", pady=(0, sp.md))

        self._fps_switch = self._add_toggle_row(
            ui_section.content,
            "Mostrar FPS",
            "Muestra el contador de frames por segundo",
            default=self._config.ui.show_fps,
        )

        self._bbox_switch = self._add_toggle_row(
            ui_section.content,
            "Mostrar bounding boxes",
            "Dibuja las cajas de detección sobre el video",
            default=self._config.ui.show_bounding_boxes,
        )

        # ── Status message ──
        self._status_message = ctk.CTkLabel(
            scroll,
            text="",
            font=ctk.CTkFont(family=typo.family_text, size=typo.size_caption),
            text_color=colors.accent_green,
            anchor="w",
        )
        self._status_message.pack(fill="x", pady=(sp.xs, 0))

        # ── Botón Guardar ──
        self._save_btn = ctk.CTkButton(
            scroll,
            text="Guardar Configuración",
            height=40,
            corner_radius=sp.radius_md,
            font=ctk.CTkFont(
                family=typo.family_display,
                size=typo.size_body,
                weight="bold",
            ),
            fg_color=colors.accent_blue,
            hover_color="#0070E0",
            command=self._on_save_click,
        )
        self._save_btn.pack(fill="x", pady=sp.lg)

    # ══════════════════════════════════════════════════════════
    #  Acoplamiento dinámico a la cámara
    # ══════════════════════════════════════════════════════════

    def update_camera_info(self, resolution: tuple[int, int], fps: float) -> None:
        """
        Se llama cuando la cámara se conecta. Actualiza la UI
        con los valores reales detectados de la cámara.
        """
        colors = THEME.colors
        w, h = resolution

        # Actualizar status
        if self._cam_status_label:
            self._cam_status_label.configure(
                text=f"● Activa ({w}x{h} @ {fps:.0f}FPS)",
                text_color=colors.accent_green,
            )

        # Actualizar resolución en el menú
        res_str = f"{w}x{h}"
        if self._cam_resolution_menu:
            current_values = list(self._cam_resolution_menu.cget("values"))
            if res_str not in current_values:
                current_values.insert(1, res_str)
                self._cam_resolution_menu.configure(values=current_values)
            self._cam_resolution_menu.set(res_str)

        # Actualizar FPS
        if self._cam_fps_entry:
            self._cam_fps_entry.delete(0, "end")
            self._cam_fps_entry.insert(0, f"{fps:.0f}")

        logger.info(f"Settings actualizados con cámara: {w}x{h} @ {fps:.0f}FPS")

    def update_camera_disconnected(self) -> None:
        """Se llama cuando la cámara se desconecta."""
        colors = THEME.colors
        if self._cam_status_label:
            self._cam_status_label.configure(
                text="● Desconectada",
                text_color=colors.text_tertiary,
            )

    # ══════════════════════════════════════════════════════════
    #  Guardar configuración
    # ══════════════════════════════════════════════════════════

    def _on_save_click(self) -> None:
        """Maneja el click en guardar — pide confirmación."""
        colors = THEME.colors

        # Crear diálogo de confirmación
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirmar")
        dialog.geometry("400x180")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        # Centrar en pantalla
        dialog.update_idletasks()
        x = dialog.winfo_screenwidth() // 2 - 200
        y = dialog.winfo_screenheight() // 2 - 90
        dialog.geometry(f"+{x}+{y}")

        frame = ctk.CTkFrame(dialog, fg_color=colors.bg_secondary, corner_radius=0)
        frame.pack(fill="both", expand=True)

        ctk.CTkLabel(
            frame,
            text="¿Guardar configuración?",
            font=ctk.CTkFont(
                family=THEME.typography.family_display,
                size=THEME.typography.size_subheading,
                weight="bold",
            ),
            text_color=colors.text_primary,
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            frame,
            text="Los cambios se aplicarán al reiniciar la cámara.",
            font=ctk.CTkFont(size=THEME.typography.size_caption),
            text_color=colors.text_secondary,
        ).pack(pady=(0, 20))

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkButton(
            btn_frame,
            text="Cancelar",
            width=120,
            height=36,
            fg_color=colors.bg_tertiary,
            hover_color=colors.border_active,
            text_color=colors.text_primary,
            command=dialog.destroy,
        ).pack(side="left", expand=True, padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Guardar",
            width=120,
            height=36,
            fg_color=colors.accent_blue,
            hover_color="#0070E0",
            command=lambda: self._do_save(dialog),
        ).pack(side="right", expand=True, padx=5)

    def _do_save(self, dialog: ctk.CTkToplevel) -> None:
        """Ejecuta el guardado real de la configuración."""
        import yaml
        from pathlib import Path

        dialog.destroy()

        try:
            # Leer valores de los widgets
            config = self._config

            # Cámara
            source_val = self._cam_source_entry.get().strip() if self._cam_source_entry else "0"
            try:
                config.camera.source = int(source_val)
            except ValueError:
                config.camera.source = source_val

            res_val = self._cam_resolution_menu.get() if self._cam_resolution_menu else "Auto-detectar"
            if res_val == "Auto-detectar":
                config.camera.width = 0
                config.camera.height = 0
            else:
                parts = res_val.split("x")
                if len(parts) == 2:
                    config.camera.width = int(parts[0])
                    config.camera.height = int(parts[1])

            fps_val = self._cam_fps_entry.get().strip() if self._cam_fps_entry else "0"
            if fps_val.lower() == "auto" or fps_val == "0":
                config.camera.fps = 0
            else:
                try:
                    config.camera.fps = int(float(fps_val))
                except ValueError:
                    config.camera.fps = 0

            # Detección
            config.detection.face_enabled = bool(self._face_switch and self._face_switch.get())
            config.detection.plate_enabled = bool(self._plate_switch and self._plate_switch.get())
            if self._confidence_slider:
                config.detection.confidence_threshold = round(self._confidence_slider.get(), 2)

            # Almacenamiento
            if self._encryption_switch:
                config.storage.encryption_enabled = bool(self._encryption_switch.get())
            storage_val = self._storage_entry.get().strip() if self._storage_entry else "5120"
            try:
                config.storage.max_storage_mb = int(storage_val)
            except ValueError:
                pass

            # UI
            config.ui.show_fps = bool(self._fps_switch and self._fps_switch.get())
            config.ui.show_bounding_boxes = bool(self._bbox_switch and self._bbox_switch.get())

            # Escribir YAML
            yaml_data = {
                "log_level": config.log_level,
                "camera": {
                    "source": config.camera.source,
                    "width": config.camera.width,
                    "height": config.camera.height,
                    "fps": config.camera.fps,
                    "buffer_size": config.camera.buffer_size,
                    "reconnect_attempts": config.camera.reconnect_attempts,
                    "reconnect_delay": config.camera.reconnect_delay,
                },
                "detection": {
                    "face_enabled": config.detection.face_enabled,
                    "plate_enabled": config.detection.plate_enabled,
                    "face_model": config.detection.face_model,
                    "plate_model": config.detection.plate_model,
                    "confidence_threshold": config.detection.confidence_threshold,
                    "face_min_size": config.detection.face_min_size,
                    "plate_min_size": config.detection.plate_min_size,
                    "tracking_iou_threshold": config.detection.tracking_iou_threshold,
                    "duplicate_cooldown": config.detection.duplicate_cooldown,
                },
                "storage": {
                    "database_path": config.storage.database_path,
                    "images_path": config.storage.images_path,
                    "encryption_enabled": config.storage.encryption_enabled,
                    "max_storage_mb": config.storage.max_storage_mb,
                    "rotation_threshold": config.storage.rotation_threshold,
                },
                "ui": {
                    "theme": config.ui.theme,
                    "window_width": config.ui.window_width,
                    "window_height": config.ui.window_height,
                    "sidebar_width": config.ui.sidebar_width,
                    "font_family": config.ui.font_family,
                    "font_fallback": config.ui.font_fallback,
                    "accent_color": config.ui.accent_color,
                    "show_fps": config.ui.show_fps,
                    "show_bounding_boxes": config.ui.show_bounding_boxes,
                },
            }

            config_path = Path(__file__).resolve().parent.parent.parent / "configs" / "settings.yaml"
            config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            if self._status_message:
                self._status_message.configure(
                    text="✓ Configuración guardada. Los cambios de cámara se aplican al reiniciar.",
                    text_color=THEME.colors.accent_green,
                )

            logger.info(f"Configuración guardada en {config_path}")

        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
            if self._status_message:
                self._status_message.configure(
                    text=f"✗ Error: {e}",
                    text_color=THEME.colors.accent_red,
                )

    # ══════════════════════════════════════════════════════════
    #  Helpers para construir filas de settings
    # ══════════════════════════════════════════════════════════

    def _add_setting_row(
        self, parent: ctk.CTkFrame, label: str, description: str, default_value: str = "",
    ) -> ctk.CTkEntry:
        """Fila con campo de texto. Retorna referencia al Entry."""
        colors = THEME.colors
        typo = THEME.typography
        sp = THEME.spacing

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=sp.xs)

        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            text_frame, text=label,
            font=ctk.CTkFont(family=typo.family_display, size=typo.size_body),
            text_color=colors.text_primary, anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            text_frame, text=description,
            font=ctk.CTkFont(family=typo.family_text, size=typo.size_micro),
            text_color=colors.text_tertiary, anchor="w",
        ).pack(fill="x")

        entry = ctk.CTkEntry(
            row, width=140, height=30,
            corner_radius=sp.radius_sm,
            fg_color=colors.bg_tertiary,
            border_color=colors.border_subtle,
            font=ctk.CTkFont(family=typo.family_mono, size=typo.size_caption),
        )
        if default_value:
            entry.insert(0, default_value)
        entry.pack(side="right", padx=(sp.md, 0))

        return entry

    def _add_option_row(
        self, parent: ctk.CTkFrame, label: str, description: str,
        options: list[str], default_value: str = "",
    ) -> ctk.CTkOptionMenu:
        """Fila con menú desplegable. Retorna referencia al OptionMenu."""
        colors = THEME.colors
        typo = THEME.typography
        sp = THEME.spacing

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=sp.xs)

        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            text_frame, text=label,
            font=ctk.CTkFont(family=typo.family_display, size=typo.size_body),
            text_color=colors.text_primary, anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            text_frame, text=description,
            font=ctk.CTkFont(family=typo.family_text, size=typo.size_micro),
            text_color=colors.text_tertiary, anchor="w",
        ).pack(fill="x")

        menu = ctk.CTkOptionMenu(
            row, values=options, width=160, height=30,
            corner_radius=sp.radius_sm,
            fg_color=colors.bg_tertiary,
            button_color=colors.border_active,
            font=ctk.CTkFont(size=typo.size_caption),
        )
        menu.set(default_value or options[0])
        menu.pack(side="right", padx=(sp.md, 0))

        return menu

    def _add_toggle_row(
        self, parent: ctk.CTkFrame, label: str, description: str, default: bool = True,
    ) -> ctk.CTkSwitch:
        """Fila con switch. Retorna referencia al Switch."""
        colors = THEME.colors
        typo = THEME.typography
        sp = THEME.spacing

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=sp.xs)

        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            text_frame, text=label,
            font=ctk.CTkFont(family=typo.family_display, size=typo.size_body),
            text_color=colors.text_primary, anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            text_frame, text=description,
            font=ctk.CTkFont(family=typo.family_text, size=typo.size_micro),
            text_color=colors.text_tertiary, anchor="w",
        ).pack(fill="x")

        switch = ctk.CTkSwitch(
            row, text="", width=46, height=24,
            fg_color=colors.bg_tertiary,
            progress_color=colors.accent_green,
            button_color=colors.text_primary,
        )
        if default:
            switch.select()
        switch.pack(side="right", padx=(sp.md, 0))

        return switch

    def _add_slider_row(
        self, parent: ctk.CTkFrame, label: str, description: str,
        from_: float = 0, to: float = 1, default: float = 0.5,
    ) -> tuple[ctk.CTkSlider, ctk.CTkLabel]:
        """Fila con slider. Retorna (slider, value_label)."""
        colors = THEME.colors
        typo = THEME.typography
        sp = THEME.spacing

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=sp.xs)

        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            text_frame, text=label,
            font=ctk.CTkFont(family=typo.family_display, size=typo.size_body),
            text_color=colors.text_primary, anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            text_frame, text=description,
            font=ctk.CTkFont(family=typo.family_text, size=typo.size_micro),
            text_color=colors.text_tertiary, anchor="w",
        ).pack(fill="x")

        slider_frame = ctk.CTkFrame(row, fg_color="transparent")
        slider_frame.pack(side="right", padx=(sp.md, 0))

        value_label = ctk.CTkLabel(
            slider_frame,
            text=f"{default:.0%}",
            font=ctk.CTkFont(family=typo.family_mono, size=typo.size_micro),
            text_color=colors.text_secondary,
            width=40,
        )
        value_label.pack(side="right")

        slider = ctk.CTkSlider(
            slider_frame, from_=from_, to=to, width=120, height=16,
            fg_color=colors.bg_tertiary,
            progress_color=colors.accent_blue,
            button_color=colors.text_primary,
            button_hover_color=colors.accent_blue,
            command=lambda v: value_label.configure(text=f"{v:.0%}"),
        )
        slider.set(default)
        slider.pack(side="right", padx=(0, sp.xs))

        return slider, value_label
