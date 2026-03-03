"""
Configuración centralizada de logging.

Formato consistente, rotación de archivos y soporte para niveles configurables.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(
    level: str = "INFO",
    log_dir: Path | None = None,
    log_file: str = "iacam.log",
) -> None:
    """
    Configura el sistema de logging global.

    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR).
        log_dir: Directorio para archivos de log. None = solo consola.
        log_file: Nombre del archivo de log.
    """
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Limpiar handlers previos
    root_logger.handlers.clear()

    # Handler de consola con colores sutiles
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    root_logger.addHandler(console_handler)

    # Handler de archivo con rotación
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        root_logger.addHandler(file_handler)

    # Silenciar loggers ruidosos de terceros
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
