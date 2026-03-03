"""
Sistema de eventos (Event Bus) desacoplado.

Implementa el patrón Observer/Pub-Sub para comunicación entre módulos
sin acoplamiento directo. La UI, el storage y los detectores se comunican
exclusivamente a través de este bus de eventos.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from threading import Lock
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Tipo para callbacks de eventos
EventCallback = Callable[[str, Any], None]


class EventBus:
    """
    Bus de eventos thread-safe con soporte pub/sub.

    Uso:
        bus = EventBus()
        bus.subscribe("detection:new", mi_callback)
        bus.emit("detection:new", detection_data)
    """

    # Eventos del sistema documentados
    DETECTION_NEW = "detection:new"
    DETECTION_SAVED = "detection:saved"
    CAMERA_STARTED = "camera:started"
    CAMERA_STOPPED = "camera:stopped"
    CAMERA_ERROR = "camera:error"
    FRAME_PROCESSED = "frame:processed"
    PIPELINE_STARTED = "pipeline:started"
    PIPELINE_STOPPED = "pipeline:stopped"
    SYSTEM_ERROR = "system:error"
    STATS_UPDATED = "stats:updated"

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventCallback]] = defaultdict(list)
        self._lock = Lock()

    def subscribe(self, event_name: str, callback: EventCallback) -> None:
        """
        Suscribe un callback a un evento específico.

        Args:
            event_name: Nombre del evento (usar constantes de clase).
            callback: Función que recibe (event_name, data).
        """
        with self._lock:
            if callback not in self._subscribers[event_name]:
                self._subscribers[event_name].append(callback)
                logger.debug(f"Suscriptor añadido a '{event_name}'")

    def unsubscribe(self, event_name: str, callback: EventCallback) -> None:
        """Remueve un callback de un evento."""
        with self._lock:
            try:
                self._subscribers[event_name].remove(callback)
            except ValueError:
                pass

    def emit(self, event_name: str, data: Any = None) -> None:
        """
        Emite un evento a todos los suscriptores.

        Args:
            event_name: Nombre del evento.
            data: Datos asociados al evento.
        """
        with self._lock:
            callbacks = list(self._subscribers.get(event_name, []))

        for callback in callbacks:
            try:
                callback(event_name, data)
            except Exception as e:
                logger.error(
                    f"Error en suscriptor de '{event_name}': {e}",
                    exc_info=True,
                )

    def clear(self) -> None:
        """Elimina todas las suscripciones."""
        with self._lock:
            self._subscribers.clear()
