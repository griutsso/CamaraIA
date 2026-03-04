#!/usr/bin/env python3
"""
IA-CAM-SERVICE — Punto de Entrada Principal

Sistema de Visión Artificial Offline para Automóviles.
Orquesta la inicialización de servicios, pipeline de detección y UI web.

Uso:
    python main.py                    # Modo web (Flask + MJPEG, default)
    python main.py --headless         # Sin UI (solo detección por consola)
    python main.py --config path.yaml # Config personalizada
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
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
from src.pipeline.detection_pipeline import DetectionPipeline

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  CLI
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
        choices=["web", "headless"],
        default="web",
        help="Modo de ejecución: web (Flask, default), headless (consola)",
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


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════

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
    else:
        _run_headless(container)


# ═══════════════════════════════════════════════════════════════
#  Modo Web (Flask + MJPEG)
# ═══════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════
#  Modo Headless (consola)
# ═══════════════════════════════════════════════════════════════

def _run_headless(container: ServiceContainer) -> None:
    """
    Modo headless: usa DetectionPipeline con FrameBuffer.
    La captura se hace en el main thread; la IA corre en el pipeline thread.
    """
    logger.info("Modo headless: pipeline ejecutándose en consola.")

    event_bus = container.event_bus
    video_source = container.video_source

    # Log de detecciones
    def on_detection(event_name, data):
        if data:
            logger.info(f"[DETECCIÓN] {data}")
    event_bus.subscribe(EventBus.DETECTION_SAVED, on_detection)

    # Crear pipeline
    frame_buffer = FrameBuffer(max_size=5)
    pipeline = DetectionPipeline(container, frame_buffer, encode_base64=False)

    # Iniciar cámara
    try:
        video_source.start()
    except Exception as e:
        logger.error(f"Error iniciando cámara: {e}")
        return

    # Iniciar pipeline (carga modelos en su thread)
    pipeline.start()

    logger.info("Pipeline headless activo. Ctrl+C para detener.")
    frame_count = 0
    start_time = time.time()

    try:
        while video_source.is_active():
            frame = video_source.read_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            # Enviar al pipeline cada 3 frames
            frame_count += 1
            if frame_count % 3 == 0:
                frame_buffer.put(frame)

            # Log periódico
            if frame_count % 300 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / max(elapsed, 1)
                stats = pipeline.get_stats()
                mins, secs = divmod(int(elapsed), 60)
                logger.info(
                    f"Uptime: {mins:02d}:{secs:02d} | "
                    f"Frames: {frame_count} | FPS captura: {fps:.1f} | "
                    f"FPS IA: {stats['fps']} | "
                    f"Rostros: {stats['unique_faces']} | "
                    f"Placas: {stats['unique_plates']}"
                )

    except KeyboardInterrupt:
        logger.info("Interrupción de teclado.")
    finally:
        pipeline.stop()
        video_source.stop()
        container.shutdown()


if __name__ == "__main__":
    main()
