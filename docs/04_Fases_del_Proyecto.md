# IA-CAM-SERVICE - Fases del Proyecto

Sistema Inteligente de Cámaras para Automóviles

**Detalle Técnico de Cada Etapa de Desarrollo**

Documento 4 de 7 | Versión 1.0

Marzo 2026

*Clasificación: Confidencial*

---

## Introducción

Este documento detalla cada una de las ocho fases del proyecto IA-CAM-SERVICE, desde la configuración inicial del entorno de desarrollo hasta el despliegue automatizado en los dispositivos edge de los vehículos. Cada fase incluye su objetivo, actividades principales, entregables concretos, tecnologías involucradas y criterios de salida que deben cumplirse antes de avanzar a la siguiente fase.

---

## Fase 0: Configuración del Entorno y Gobernanza (S1--S2)

### Objetivo

Establecer la infraestructura de desarrollo, las convenciones del equipo y la gobernanza del proyecto para que todo el trabajo posterior se realice sobre una base sólida, estandarizada y reproducible.

### Actividades Principales

- Crear el repositorio Git (monorepo) en GitHub con la estructura de carpetas estándar del proyecto.
- Definir y documentar la estructura modular: src/capture/, src/detection/, src/ocr/, src/storage/, src/core/.
- Configurar el entorno virtual de Python con Poetry o pip-tools y generar el lock file de dependencias.
- Instalar y verificar las dependencias base: OpenCV 4.x, Ultralytics, EasyOCR, pytest.
- Configurar pre-commit hooks con Black (formateo), isort (imports), flake8 (linting) y mypy (type checking básico).
- Crear el tablero Kanban en GitHub Projects con las columnas: Backlog, Ready, In Progress (WIP:3), In Review, Testing, Done.
- Redactar el README.md del proyecto con instrucciones de setup, arquitectura de referencia y convenciones de código.
- Configurar el pipeline básico de CI en GitHub Actions (lint + tests en cada PR).

### Entregables

| **Entregable** | **Formato** | **Ubicación** |
|---|---|---|
| Repositorio configurado | Git (GitHub) | github.com/org/ia-cam-service |
| Estructura de carpetas | Directorios + `__init__.py` | src/, tests/, configs/, docker/, docs/ |
| Lock file de dependencias | poetry.lock / requirements.txt | Raíz del repositorio |
| Pre-commit hooks | .pre-commit-config.yaml | Raíz del repositorio |
| Tablero Kanban | GitHub Projects | Tab Projects del repositorio |
| CI básico | GitHub Actions workflow | .github/workflows/ci.yml |
| Documento de arquitectura | Markdown | docs/architecture.md |

### Criterios de Salida

- Todo miembro del equipo puede clonar el repo, instalar dependencias y ejecutar pytest sin errores.
- Un PR al repositorio dispara automáticamente lint + tests y bloquea el merge si fallan.
- El tablero Kanban tiene todas las tarjetas de la Fase 1 creadas y priorizadas.

---

## Fase 1: Módulo de Captura de Video (S3--S4)

### Objetivo

Desarrollar la capa de abstracción de cámara que sirva como fuente de datos para todos los módulos de detección, soportando múltiples fuentes de video y desacoplando la captura del procesamiento.

### Actividades Principales

- Implementar la clase abstracta VideoSource con métodos start(), read_frame(), stop() y propiedades (fps, resolution).
- Desarrollar implementaciones concretas: WebcamSource (USB/CSI), FileSource (archivos de video), RTSPSource (streams de red).
- Implementar el patrón productor-consumidor con queue.Queue thread-safe para desacoplar captura de procesamiento.
- Añadir configuración dinámica de resolución, FPS y formato de color mediante archivo YAML.
- Implementar manejo robusto de errores: reconexion automática ante desconexiones de cámara, timeout configurable, logging.
- Escribir tests unitarios para cada fuente de video y tests de integración para el flujo productor-consumidor.
- Crear un script de demo (capture_demo.py) que muestra el feed en vivo con FPS overlay para validación visual.

### Arquitectura del Módulo

El módulo sigue una arquitectura hexagonal donde la interfaz VideoSource define el contrato, las implementaciones concretas son intercambiables, y el FrameBuffer (cola thread-safe) actúa como intermediario entre la captura y los consumidores (módulos de detección). Esto permite añadir nuevas fuentes de video (por ejemplo, cámaras IP) sin modificar la lógica de detección.

### Criterios de Salida

- La webcam captura video a ≥ 30 FPS en resolución 640x480 sin frame drops.
- El patrón productor-consumidor funciona correctamente con ≥3 consumidores simultáneos.
- La reconexion automática funciona al desconectar y reconectar una cámara USB.
- Cobertura de tests ≥ 85% en el módulo de captura.

---

## Fase 2: Detección de Rostros (S5--S6)

### Objetivo

Implementar el primer módulo de inteligencia artificial del sistema: la detección de rostros humanos en tiempo real sobre el feed de video.

### Actividades Principales

- Evaluar y seleccionar el modelo de detección facial: YOLOv8-face vs. MediaPipe Face Detection vs. RetinaFace. Criterios: precisión, velocidad en CPU, tamaño del modelo.
- Implementar la clase FaceDetector como módulo plugin del pipeline, recibiendo frames del FrameBuffer y emitiendo detecciones.
- Implementar tracking básico IoU-based para asignar IDs temporales a rostros y evitar capturas duplicadas del mismo individuo.
- Desarrollar la lógica de captura: al detectar un rostro nuevo (no tracked), recortar la región facial, generar metadatos y encolar para almacenamiento.
- Implementar filtros de calidad: descartar detecciones con confianza < umbral configurable, rostros demasiado pequeños o borrosos (Laplacian variance check).
- Crear suite de tests con imágenes de prueba anotadas (ground truth) para medir mAP y FPS.
- Documentar el flujo de datos y las decisiones de diseño en docs/face_detection.md.

### Criterios de Salida

- mAP@0.5 ≥ 85% en WIDER FACE (easy+medium) evaluado con script de benchmark.
- ≥ 15 FPS en laptop, ≥ 10 FPS en hardware edge simulado (CPU throttled).
- El tracking evita ≥ 90% de capturas duplicadas en video de prueba de 5 minutos.
- Cada detección genera un evento estructurado con todos los metadatos requeridos.

---

## Fase 3: Detección y Lectura de Placas (S7--S10)

### Objetivo

Desarrollar el pipeline completo de detección de placas vehiculares: localización de la placa en el frame, preprocesamiento de imagen y reconocimiento óptico de caracteres.

### Actividades Principales

- Recopilar o curar un dataset de placas vehiculares latinoamericanas (≥ 1000 imágenes) con anotaciones de bounding box y texto ground truth.
- Entrenar o fine-tune un modelo YOLOv8n/s para localización de placas. Evaluar precisión y velocidad.
- Implementar pipeline de preprocesamiento de placa: corrección de perspectiva (homografía), conversión a escala de grises, binarización adaptativa (Otsu/Sauvola), CLAHE para mejora de contraste.
- Integrar EasyOCR con configuración específica para caracteres alfanuméricos de placas (charset restringido, sin puntuación).
- Implementar postprocesamiento OCR: validación de formato por país (regex), corrección de caracteres ambiguos (O/0, I/1, S/5).
- Implementar la clase PlateDetector como módulo plugin del pipeline, análogo a FaceDetector.
- Desarrollar script de benchmark para medir precisión de localización, precisión de lectura y FPS.
- Pruebas con video real de tráfico (grabaciones propias en estacionamientos y vías públicas).

### Pipeline Técnico

```
Frame → YOLO (localización) → Crop de placa → Perspectiva → Grayscale → CLAHE → Binarización → EasyOCR → Postprocesamiento (regex + corrección) → Registro en DB
```

### Criterios de Salida

- IoU ≥ 0.5 en ≥ 90% de las placas del dataset de validación.
- Lectura correcta del texto completo ≥ 80% en condiciones diurnas.
- Pipeline completo ≥ 10 FPS en laptop.
- Soporte validado para formatos de placas de México, Colombia y Argentina.

---

## Fase 4: Motor de Registro y Almacenamiento (S11--S12)

### Objetivo

Implementar el sistema de persistencia local que almacena de forma segura, eficiente y estructurada todos los eventos de detección generados por los módulos de rostros y placas.

### Actividades Principales

- Diseñar el esquema de base de datos SQLite con tablas: detections (tipo, timestamp, bbox, confianza, ruta_imagen, texto_placa), system_logs (nivel, mensaje, timestamp), config (clave-valor).
- Configurar SQLite en modo WAL (Write-Ahead Logging) para soportar lecturas y escrituras concurrentes sin bloqueo.
- Implementar cifrado AES-256-GCM para las imágenes almacenadas en disco usando la librería cryptography de Python. Las claves se derivan de una master key almacenada en un keyfile protegido.
- Desarrollar el servicio StorageManager como consumidor async de la cola de eventos de detección.
- Implementar rotación automática: cuando el almacenamiento alcanza el 80% de capacidad, se eliminan los registros más antiguos (FIFO) y se registra la purga en system_logs.
- Desarrollar una interfaz CLI simple para consultar la base de datos: listar detecciones, exportar imágenes descifradas, generar reportes.
- Tests de integridad de datos: verificar que las imágenes se descifran correctamente, que no hay pérdida de registros bajo carga concurrente.

### Criterios de Salida

- SQLite soporta ≥ 50 escrituras/segundo sin errores de bloqueo o corrupción.
- Las imágenes cifradas se descifran correctamente al 100% en suite de tests.
- La rotación automática se activa correctamente cuando el almacenamiento supera el umbral.
- La CLI permite listar, filtrar por fecha/tipo, y exportar registros.

---

## Fase 5: Integración, Pruebas y Optimización (S13--S16)

### Objetivo

Integrar todos los módulos desarrollados en el pipeline unificado, ejecutar pruebas exhaustivas y optimizar el rendimiento para cumplir las restricciones del hardware edge.

### Actividades Principales

- Integrar los módulos de captura, detección de rostros, detección de placas y almacenamiento en el pipeline principal (main.py).
- Implementar el Pipeline Orchestrator que gestiona el flujo de frames desde la captura hasta el almacenamiento, con configuración dinámica de módulos activos.
- Ejecutar pruebas de regresión completas (pytest) para verificar que la integración no introduce errores.
- Profiling de rendimiento con cProfile y line_profiler para identificar cuellos de botella.
- Exportar modelos YOLO a ONNX Runtime para inferencia optimizada en CPU.
- Para hardware NVIDIA: exportar modelos a TensorRT para aceleración GPU.
- Ejecutar tests de estrés de 8 horas continuas: monitorear FPS, uso de memoria (psutil), temperatura, y verificar ausencia de memory leaks.
- Implementar métricas de rendimiento en tiempo real: FPS counter, latencia por frame, queue sizes.

### Criterios de Salida

- Pipeline unificado funcional con detección simultánea de rostros y placas.
- 8 horas continuas sin crashes, memory leaks ni degradación de FPS > 10%.
- Modelos exportados a ONNX/TensorRT con mejora de velocidad ≥ 30% respecto a PyTorch nativo.
- Cobertura de tests global ≥ 80%.

---

## Fase 6: Contenedorización Docker (S17--S19)

### Objetivo

Empaquetar la aplicación completa en contenedores Docker reproducibles y multi-arquitectura, habilitando el despliegue automático en cualquier dispositivo soportado.

### Actividades Principales

- Crear Dockerfile multi-stage: stage 1 (builder) compila dependencias nativas y descarga modelos; stage 2 (runtime) contiene solo lo necesario para ejecución.
- Configurar Docker Buildx para compilación cruzada: linux/amd64 (desarrollo) + linux/arm64 (Raspberry Pi / Jetson).
- Crear variantes de Dockerfile: base (CPU), nvidia (con CUDA/TensorRT para Jetson).
- Definir docker-compose.yml con servicios: capture (captura de video), detection (inferencia de modelos), storage (persistencia), y un servicio opcional monitor (métricas locales).
- Configurar volúmenes Docker para persistencia: /data/db (SQLite), /data/images (imágenes cifradas), /config (archivos de configuración YAML).
- Implementar health-checks en cada servicio Docker para que el orquestador pueda verificar el estado de salud.
- Optimizar tamaño de imagen: eliminar caches, usar .dockerignore, comprimir modelos, slim base images.
- Tests de integración Docker: verificar que el sistema funciona correctamente dentro del contenedor en ambas arquitecturas.

### Criterios de Salida

- `docker compose up` funciona sin errores en amd64 y arm64.
- Imagen final ≤ 2 GB.
- Health-checks reportan estado correcto en todos los servicios.
- Tests pasan dentro del contenedor: `docker compose run tests`.

---

## Fase 7: Pipeline GitOps y Despliegue Edge (S20--S22)

### Objetivo

Cerrar el ciclo DevOps implementando el pipeline de integración continua, entrega continua y despliegue automático GitOps hacia los dispositivos de borde en los vehículos.

### Actividades Principales

- Implementar workflow completo de GitHub Actions con stages: lint, test, build-docker, push-ghcr, create-release.
- Configurar Conventional Commits y generación automática de changelog con semantic-release o release-please.
- Implementar firma de imágenes Docker con Cosign (Sigstore) para verificar integridad antes del despliegue.
- Desarrollar el agente de sincronización edge: script Python liviano que ejecuta periódicamente (cron cada 5 min): verifica nueva imagen en GHCR, valida firma Cosign, descarga imagen, ejecuta health-check, reemplaza contenedor activo.
- Implementar estrategia de rollback A/B: mantener la imagen anterior como fallback; si el health-check de la nueva imagen falla 2 veces consecutivas, revertir automáticamente.
- Configurar logging inmutable de actualizaciones: cada operación del agente queda registrada con timestamp, versión anterior, versión nueva, resultado.
- Pruebas end-to-end: simular el flujo completo desde commit hasta despliegue en un Raspberry Pi de prueba.
- Redactar runbook operativo: procedimientos de troubleshooting, rollback manual, recuperación de desastres.

### Criterios de Salida

- Push a main → imagen en GHCR en ≤ 10 minutos.
- Dispositivo edge aplica actualización en ≤ 5 minutos adicionales.
- Rollback automático funciona correctamente (verificado con imagen intencionalmente defectuosa).
- Runbook operativo completo y revisado.

---

## Cierre: Pruebas de Aceptación y Documentación (S23--S24)

### Objetivo

Validar que el sistema cumple todos los criterios de aceptación definidos en los objetivos SMART, generar la documentación final y preparar el Release Candidate v1.0.

### Actividades Principales

- Ejecutar la suite completa de pruebas de aceptación contra los KPIs definidos en los objetivos SMART.
- Realizar pruebas de campo con la cámara de laptop en condiciones reales (estacionamientos, vías públicas).
- Generar documentación técnica completa: API interna, diagramas de arquitectura, guía de instalación, runbook.
- Etiquetar el Release Candidate v1.0 en GitHub con changelog completo.
- Retrospectiva final del proyecto: lecciones aprendidas, deuda técnica identificada, roadmap futuro.

### Criterios de Salida

- Todos los KPIs de los 4 objetivos SMART están verificados y documentados.
- Release v1.0 publicado en GitHub con documentación completa.
- Retrospectiva documentada con plan de acción para mejoras futuras.
