# IA-CAM-SERVICE

## Reporte de Avance #03

| Campo | Valor |
|-------|-------|
| Proyecto | IA-CAM-SERVICE — Sistema de Visión Artificial Offline |
| Fecha | 03 de March de 2026 |
| Versión | 0.1.0-alpha.3 |
| Autor | Claude (Asistente de Desarrollo) |

## 1. Resumen Ejecutivo

Este reporte documenta el diagnóstico y solución del problema de captura de video en negro (black frames) que impedía el funcionamiento de la cámara web en macOS. Se identificaron tres causas raíz y se aplicaron correcciones en los módulos video_source.py, main.py y config.py.

## 2. Problema Reportado

Al iniciar la aplicación en macOS (MacBook Air) y activar la cámara, el sistema mostraba los siguientes síntomas:

- La cámara se conecta exitosamente (reporta 640x480 @ 30 FPS)
- La ventana de video muestra pantalla completamente negra
- Después de ~23 segundos, se alcanzan 16 frames perdidos consecutivos
- El sistema intenta reconexión, reconecta exitosamente, pero inmediatamente se desconecta
- El log muestra "Cámara desconectada" y el video se detiene

## 3. Diagnóstico — Causas Raíz Identificadas

### 3.1 Bloqueo del Main Thread (CRÍTICO)

Dentro de read_frame() en video_source.py, cada frame fallido ejecutaba time.sleep(0.03), bloqueando el main thread de Tkinter durante 30ms. Con 16 frames fallidos consecutivos, eso son 480ms de bloqueo acumulado que impide tanto la actualización de la UI como la entrega de frames por AVFoundation, creando un ciclo vicioso de fallos.

### 3.2 Resolución y FPS Forzados

El sistema forzaba 640x480 a 30 FPS independientemente de las capacidades reales de la cámara. En la FaceTime Camera del MacBook Air, esto puede forzar un modo de captura no nativo, causando frames negros o latencia excesiva en el pipeline.

### 3.3 Warmup Insuficiente

El código anterior usaba solo 5 llamadas a grab() como período de calentamiento. Estas llamadas se ejecutan instantáneamente sin dar tiempo real al hardware de la cámara para estabilizarse. AVFoundation en macOS necesita típicamente 1-3 segundos para entregar frames estables después de abrir el dispositivo.

## 4. Correcciones Aplicadas

| Archivo | Cambio | Impacto |
|---------|--------|--------|
| video_source.py | Eliminado time.sleep() de read_frame() | read_frame() NUNCA bloquea el main thread |
| video_source.py | Auto-detección de resolución/FPS (width=0, height=0, fps=0) | La cámara usa su modo nativo óptimo |
| video_source.py | Período de warmup de 3 segundos con tolerancia triple a fallos | Frames negros iniciales no causan desconexión |
| main.py | Skip primeros 5 frames para detection worker | Evita procesar frames de warmup con IA |

### 4.1 Cambios en video_source.py

Se reescribió completamente WebcamSource con la siguiente filosofía: "La cámara decide sus parámetros; el software se adapta".

- read_frame() retorna None sin bloquear cuando no hay frame (sin sleep)
- Auto-detección: si width/height/fps son 0, no se configura nada y se lee lo que la cámara asigna
- WARMUP_SECONDS = 3.0: durante el warmup, la tolerancia a fallos se triplica (90 frames)
- Logging del primer frame exitoso con brillo promedio y tiempo transcurrido
- Estadísticas finales al detener: frames exitosos / intentados
- Eliminados los 5 grab() de estabilización (innecesarios con warmup)
- Eliminado CAP_PROP_BUFFERSIZE = 1 (no soportado por AVFoundation)

### 4.2 Cambios en config.py y settings.yaml

Los valores por defecto de CameraConfig ahora son width=0, height=0, fps=0, indicando auto-detección. El usuario puede sobrescribirlos en settings.yaml si necesita forzar una resolución específica.

### 4.3 Cambios en main.py

Se agregó un contador frames_since_start que evita enviar al DetectionWorker los primeros 5 frames (que pueden ser negros de warmup). Esto previene que los detectores procesen frames inútiles.

## 5. Herramienta de Diagnóstico: test_camera.py

Se creó un script standalone (app/test_camera.py) para diagnosticar problemas de cámara independientemente de la aplicación principal. El script:

- Abre la cámara SIN forzar parámetros (auto-detección pura)
- Reporta backend, resolución nativa, FPS nativo y buffer size
- Lee 30 frames de warmup reportando estado de cada uno (OK/NEGRO/FALLO)
- Abre una ventana de OpenCV con overlay de FPS y estadísticas en tiempo real
- Al salir, muestra resumen: duración, frames exitosos, frames negros, FPS promedio

Uso: `python test_camera.py` (presionar "q" para salir)

## 6. Arquitectura de Threading (Actualizada)

| Thread | Responsabilidad | Comunicación |
|--------|-----------------|--------------|
| Main Thread (Tkinter) | Camera.read_frame(), UI updates, event loop | Escribe en FrameBuffer |
| DetectionWorker | YOLO inference, EasyOCR, almacenamiento | Lee de FrameBuffer, emite EventBus |
| UI Updates | Renderizar detecciones y bounding boxes | EventBus → app.after(0, callback) |

Principio clave: "La cámara es del main thread; la IA es del worker thread". Esto respeta la restricción de AVFoundation en macOS y mantiene la UI responsiva.

## 7. Verificación Pendiente

Las correcciones han sido aplicadas pero requieren verificación por parte del usuario en el hardware real (MacBook Air). Los pasos de verificación son:

1. Ejecutar `python test_camera.py` para confirmar que OpenCV puede capturar frames
2. Verificar que el warmup de 30 frames muestra transición de NEGRO → OK
3. Ejecutar `python main.py` y activar la cámara desde la UI
4. Confirmar que el video se muestra en la ventana sin pantalla negra
5. Verificar estabilidad: mantener la cámara activa por al menos 2 minutos

## 8. Lecciones Aprendidas

**Nunca bloquear el main thread:** En aplicaciones GUI con captura de video, cualquier sleep() o I/O bloqueante en el main thread destruye tanto la UI como el pipeline de video.

**Auto-detectar antes de configurar:** Forzar resolución/FPS sin verificar las capacidades del hardware causa fallos silenciosos. El enfoque correcto es abrir la cámara con defaults y leer los valores reales que el driver asigna.

**macOS AVFoundation es particular:** AVFoundation tiene requisitos estrictos: main thread obligatorio, warmup necesario, y comportamiento diferente a V4L2 (Linux) o DirectShow (Windows).
