#!/usr/bin/env python3
"""
IA-CAM-SERVICE — Punto de Entrada Principal

Sistema de Visión Artificial Offline para Automóviles.
Orquesta la inicialización de servicios, pipeline de detección y UI.

Uso:
    python main.py                    # Modo normal (UI + detección)
    python main.py --headless         # Sin UI (solo detección por consola)
    python main.py --config path.yaml # Config personalizada

NOTA DE ARQUITECTURA macOS:
    AVFoundation (backend de cámara en macOS) exige que VideoCapture.read()
    se invoque desde el MAIN THREAD. Por eso la captura de video se ejecuta
    mediante un timer de Tkinter (app.after), mientras que la detección de IA
    y el almacenamiento corren en un thread secundario. El FrameBuffer actúa
    como puente thread-safe entre ambos.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import time
from pathlib import Path

# Asegurar que el directorio raíz del proyecto está en el path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import AppConfig, load_config
from src.core.container import ServiceContainer
from src.core.events import EventBus
from src.core.logger import setup_logging
from src.capture.frame_buffer import FrameBuffer

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Detection Worker (thread secundario)
# ═══════════════════════════════════════════════════════════════

class DetectionWorker:
    """
    Ejecuta la detección de IA en un thread secundario.

    Consume frames del FrameBuffer, ejecuta los detectores,
    almacena resultados y emite eventos para la UI.
    """

    def __init__(self, container: ServiceContainer, frame_buffer: FrameBuffer) -> None:
        self._container = container
        self._event_bus = container.event_bus
        self._frame_buffer = frame_buffer
        self._running = False
        self._thread: threading.Thread | None = None
        self._fps_counter: float = 0.0
        self._frame_count: int = 0

    def start(self) -> None:
        """Inicia el worker de detección."""
        if self._running:
            return

        # Pre-cargar modelos ANTES de empezar (EasyOCR tarda ~18s)
        detectors = self._container.detectors
        logger.info("Pre-cargando modelos de detección (esto puede tardar)...")
        for detector in detectors:
            try:
                detector.load_model()
                logger.info(f"  ✓ {detector.name} cargado")
            except Exception as e:
                logger.error(f"  ✗ Error cargando {detector.name}: {e}")

        self._running = True
        self._thread = threading.Thread(
            target=self._detection_loop,
            name="DetectionWorker",
            daemon=True,
        )
        self._thread.start()
        logger.info("DetectionWorker iniciado.")

    def stop(self) -> None:
        """Detiene el worker."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info("DetectionWorker detenido.")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def fps(self) -> float:
        return self._fps_counter

    def _detection_loop(self) -> None:
        """Loop de detección: consume frames, ejecuta IA, almacena."""
        detectors = self._container.detectors
        storage = self._container.storage

        while self._running:
            frame = self._frame_buffer.get(timeout=0.1)
            if frame is None:
                continue

            loop_start = time.time()

            # Ejecutar detectores
            all_detections = []
            for detector in detectors:
                if detector.is_loaded:
                    try:
                        dets = detector.detect(frame)
                        all_detections.extend(dets)
                    except Exception as e:
                        logger.error(f"Error en {detector.name}: {e}")

            # Almacenar
            if storage and all_detections:
                for det in all_detections:
                    try:
                        storage.save_detection(det)
                    except Exception as e:
                        logger.error(f"Error guardando detección: {e}")

            # Emitir evento con resultados
            self._event_bus.emit(EventBus.FRAME_PROCESSED, {
                "frame": frame,
                "detections": all_detections,
                "fps": self._fps_counter,
            })

            # FPS de detección
            self._frame_count += 1
            elapsed = time.time() - loop_start
            self._fps_counter = 1.0 / max(elapsed, 0.001)


# ═══════════════════════════════════════════════════════════════
#  Funciones de arranque
# ═══════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    """Parsea argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="IA-CAM-SERVICE: Sistema de Visión Artificial Offline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Ruta al archivo de configuración YAML",
    )
    parser.add_argument(
        "--mode",
        choices=["web", "gui", "headless"],
        default="web",
        help="Modo de ejecución: web (Flask, default), gui (CustomTkinter), headless (consola)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Ejecutar sin interfaz gráfica (solo consola)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Puerto del servidor web (default: 8080)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Activar logging en modo DEBUG",
    )
    return parser.parse_args()


def main() -> None:
    """Punto de entrada principal."""
    args = parse_args()

    # 1. Cargar configuración
    config_path = Path(args.config) if args.config else None
    config: AppConfig = load_config(config_path)
    if args.debug:
        config.log_level = "DEBUG"

    # 2. Logging
    log_dir = PROJECT_ROOT / "logs"
    setup_logging(level=config.log_level, log_dir=log_dir)

    # Determinar modo
    mode = "headless" if args.headless else args.mode

    logger.info("=" * 60)
    logger.info(f"  {config.app_name} v{config.version}")
    logger.info(f"  Sistema de Visión Artificial Offline")
    logger.info(f"  Modo: {mode.upper()}")
    logger.info("=" * 60)

    # 3. Construir contenedor de dependencias
    container = ServiceContainer(config)
    try:
        container.build_default_services()
    except Exception as e:
        logger.error(f"Error construyendo servicios: {e}")

    # 4. Señales
    def signal_handler(sig, frame):
        logger.info(f"Señal {sig} recibida. Cerrando...")
        container.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 5. Lanzar según modo
    if mode == "web":
        _run_web(container, port=args.port, debug=args.debug)
    elif mode == "gui":
        _run_gui(container)
    else:
        _run_headless(container)


def _run_web(container: ServiceContainer, port: int = 8080, debug: bool = False) -> None:
    """
    Modo Web: Flask + MJPEG streaming.
    Más rápido que Tkinter para video — usa encoding JPEG nativo.
    """
    try:
        from src.web.server import create_app
    except ImportError as e:
        logger.error(f"No se pudo importar Flask: {e}")
        logger.info("Instala Flask con: pip install flask")
        logger.info("Ejecutando en modo headless como fallback...")
        _run_headless(container)
        return

    app = create_app(container)
    logger.info(f"Servidor web iniciando en http://localhost:{port}")
    logger.info(f"Abre tu navegador en http://localhost:{port}")

    import webbrowser
    webbrowser.open(f"http://localhost:{port}")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug,
        threaded=True,
        use_reloader=False,  # No reloader (interfiere con threads de cámara)
    )


def _run_gui(container: ServiceContainer) -> None:
    """
    Modo GUI: captura de video en el MAIN THREAD (requerido por macOS),
    detección de IA en un thread secundario.
    """
    try:
        from src.ui.app import MainApplication
        from src.ui.theme import THEME
    except ImportError as e:
        logger.error(f"No se pudo importar la UI: {e}")
        logger.info("Ejecutando en modo headless como fallback...")
        _run_headless(container)
        return

    app = MainApplication(container)
    event_bus = container.event_bus
    video_source = container.video_source

    # Buffer compartido entre main thread (captura) y worker (detección)
    frame_buffer = FrameBuffer(max_size=5)
    detection_worker = DetectionWorker(container, frame_buffer)

    # Estado mutable para el loop de captura
    camera_active = False
    capture_timer_id = None

    # ── Loop de captura (se ejecuta en el main thread via after()) ──
    frames_since_start = 0
    last_good_frame_time = 0.0
    DETECTION_EVERY_N = 3  # Enviar al detection worker cada N frames (IA no necesita 30fps)

    def capture_loop():
        """Lee un frame de la cámara y lo envía al buffer + UI."""
        nonlocal camera_active, capture_timer_id, frames_since_start, last_good_frame_time

        if not camera_active or not video_source:
            return

        frame = video_source.read_frame()

        if frame is not None:
            frames_since_start += 1
            last_good_frame_time = time.time()

            # Enviar al detection worker cada N frames (después del warmup)
            if frames_since_start > 5 and frames_since_start % DETECTION_EVERY_N == 0:
                frame_buffer.put(frame)

            # Mostrar frame en la UI directamente (estamos en el main thread)
            try:
                monitor = app._views.get("monitor")
                if monitor:
                    monitor.video_panel.update_frame(frame)
            except Exception:
                pass

        elif not video_source.is_active():
            logger.warning("Cámara desconectada.")
            stop_camera()
            return

        # Programar siguiente lectura (~30 FPS = cada 33ms)
        capture_timer_id = app.after(33, capture_loop)

    # ── Conectar detecciones del worker → UI ──
    def on_frame_processed(event_name, data):
        """Callback del DetectionWorker (thread secundario) → UI."""
        if not data:
            return
        detections = list(data.get("detections", []))
        if not detections:
            return

        def _update_detections():
            try:
                if not app.winfo_exists():
                    return
                monitor = app._views.get("monitor")
                if monitor:
                    monitor.video_panel.set_detections(detections)
                    for det in detections:
                        monitor.detection_log.add_detection(det)
            except Exception:
                pass

        try:
            app.after(0, _update_detections)
        except Exception:
            pass

    event_bus.subscribe(EventBus.FRAME_PROCESSED, on_frame_processed)

    # ── Control de cámara ──
    def start_camera():
        nonlocal camera_active, frames_since_start
        if camera_active:
            return

        try:
            # Iniciar detección worker primero (carga modelos pesados)
            if not detection_worker.is_running:
                detection_worker.start()

            # Abrir cámara en el main thread
            video_source.start()
            camera_active = True
            frames_since_start = 0
            event_bus.emit(EventBus.CAMERA_STARTED)
            app._sidebar.update_camera_status(True)
            logger.info("Cámara iniciada (main thread).")

            # Acoplar info de cámara a settings
            try:
                settings_view = app._views.get("settings")
                if settings_view and hasattr(settings_view, "update_camera_info"):
                    settings_view.update_camera_info(
                        video_source.resolution, video_source.fps
                    )
            except Exception:
                pass

            # Comenzar loop de captura
            capture_loop()

        except Exception as e:
            logger.error(f"Error iniciando cámara: {e}")
            camera_active = False
            event_bus.emit(EventBus.CAMERA_ERROR, str(e))

    def stop_camera():
        nonlocal camera_active, capture_timer_id
        camera_active = False

        if capture_timer_id is not None:
            app.after_cancel(capture_timer_id)
            capture_timer_id = None

        if video_source:
            video_source.stop()

        frame_buffer.clear()
        app._sidebar.update_camera_status(False)
        event_bus.emit(EventBus.CAMERA_STOPPED)

        # Notificar a settings
        try:
            settings_view = app._views.get("settings")
            if settings_view and hasattr(settings_view, "update_camera_disconnected"):
                settings_view.update_camera_disconnected()
        except Exception:
            pass

        logger.info("Cámara detenida.")

    # ── Confirmaciones de seguridad ──
    def _confirm_action(title: str, message: str, on_confirm) -> None:
        """Muestra un diálogo de confirmación estilo macOS."""
        import customtkinter as ctk_mod
        colors = THEME.colors

        dialog = ctk_mod.CTkToplevel(app)
        dialog.title(title)
        dialog.geometry("420x170")
        dialog.resizable(False, False)
        dialog.transient(app)
        dialog.grab_set()

        dialog.update_idletasks()
        x = app.winfo_x() + (app.winfo_width() - 420) // 2
        y = app.winfo_y() + (app.winfo_height() - 170) // 2
        dialog.geometry(f"+{x}+{y}")

        frame = ctk_mod.CTkFrame(dialog, fg_color=colors.bg_secondary, corner_radius=0)
        frame.pack(fill="both", expand=True)

        ctk_mod.CTkLabel(
            frame, text=title,
            font=ctk_mod.CTkFont(
                family=THEME.typography.family_display,
                size=THEME.typography.size_subheading,
                weight="bold",
            ),
            text_color=colors.text_primary,
        ).pack(pady=(20, 5))

        ctk_mod.CTkLabel(
            frame, text=message,
            font=ctk_mod.CTkFont(size=THEME.typography.size_caption),
            text_color=colors.text_secondary,
        ).pack(pady=(0, 20))

        btn_frame = ctk_mod.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))

        ctk_mod.CTkButton(
            btn_frame, text="Cancelar", width=120, height=36,
            fg_color=colors.bg_tertiary, hover_color=colors.border_active,
            text_color=colors.text_primary,
            command=dialog.destroy,
        ).pack(side="left", expand=True, padx=5)

        def do_confirm():
            dialog.destroy()
            on_confirm()

        ctk_mod.CTkButton(
            btn_frame, text="Confirmar", width=120, height=36,
            fg_color=colors.accent_blue, hover_color="#0070E0",
            command=do_confirm,
        ).pack(side="right", expand=True, padx=5)

    def toggle_camera():
        if camera_active:
            _confirm_action(
                "Detener Cámara",
                "¿Deseas detener la captura de video?",
                stop_camera,
            )
        else:
            start_camera()

    app._sidebar._camera_btn.configure(command=toggle_camera)

    # ── Cierre limpio con confirmación ──
    original_on_close = app._on_close

    def on_close():
        if camera_active:
            _confirm_action(
                "Cerrar Aplicación",
                "La cámara está activa. ¿Cerrar la aplicación?",
                lambda: _do_close(),
            )
        else:
            _do_close()

    def _do_close():
        stop_camera()
        detection_worker.stop()
        original_on_close()

    app.protocol("WM_DELETE_WINDOW", on_close)

    # ── Arrancar ──
    logger.info("Lanzando interfaz gráfica...")
    app.start()


def _run_headless(container: ServiceContainer) -> None:
    """Modo headless: todo corre en el main thread."""
    logger.info("Modo headless: pipeline ejecutándose en consola.")

    event_bus = container.event_bus
    video_source = container.video_source
    detectors = container.detectors
    storage = container.storage

    # Log de detecciones
    def on_detection(event_name, data):
        if data:
            logger.info(f"[DETECCIÓN] {data}")
    event_bus.subscribe(EventBus.DETECTION_SAVED, on_detection)

    # Cargar modelos
    logger.info("Cargando modelos...")
    for detector in detectors:
        try:
            detector.load_model()
        except Exception as e:
            logger.error(f"Error cargando {detector.name}: {e}")

    # Iniciar cámara
    try:
        video_source.start()
    except Exception as e:
        logger.error(f"Error iniciando cámara: {e}")
        return

    logger.info("Pipeline headless activo. Ctrl+C para detener.")
    frame_count = 0
    start_time = time.time()

    try:
        while video_source.is_active():
            frame = video_source.read_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            # Detectar
            for detector in detectors:
                if detector.is_loaded:
                    dets = detector.detect(frame)
                    if storage:
                        for det in dets:
                            storage.save_detection(det)

            frame_count += 1
            if frame_count % 300 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / max(elapsed, 1)
                mins, secs = divmod(int(elapsed), 60)
                logger.info(f"Uptime: {mins:02d}:{secs:02d} | Frames: {frame_count} | FPS: {fps:.1f}")

    except KeyboardInterrupt:
        logger.info("Interrupción de teclado.")
    finally:
        video_source.stop()
        container.shutdown()


if __name__ == "__main__":
    main()
