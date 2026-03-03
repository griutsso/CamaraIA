# IA-CAM-SERVICE - Project Charter

Sistema Inteligente de Cámaras para Automóviles

**ACTA DE CONSTITUCIÓN**

Documento 2 de 7 | Versión 1.0

Marzo 2026

*Clasificación: Confidencial*

## Acta de Constitución del Proyecto

Este documento formaliza la existencia del proyecto IA-CAM-SERVICE, establece su justificación estratégica, define el alcance autorizado, identifica los recursos necesarios y documenta las restricciones y riesgos conocidos. Sirve como referencia oficial para la toma de decisiones a lo largo del ciclo de vida del proyecto.

## 1. Información General del Proyecto

| Campo | Detalle |
|-------|---------|
| Nombre del Proyecto | IA-CAM-SERVICE: Sistema Inteligente de Cámaras para Automóviles |
| Código Interno | IACAM-2026-001 |
| Patrocinador / Dueño | Por definir (Fundador / Inversor principal) |
| Project Manager | Por asignar |
| Fecha de Inicio | Marzo 2026 |
| Fecha Estimada de Cierre | Agosto 2026 (Semana 24) |
| Duración Estimada | 24 semanas (6 meses) |
| Metodología | Agile (Kanban con elementos de Scrum) + GitOps |
| Prioridad Organizacional | Alta |

## 2. Justificación del Proyecto

### 2.1 Contexto del Mercado

La inseguridad vehicular representa un problema sistémico en Latinoamérica y mercados emergentes. Según datos de la industria, el robo de vehículos y el vandalismo generan pérdidas estimadas en miles de millones de dólares anuales. Los sistemas de dashcam existentes capturan video pasivo que rara vez se revisa de forma proactiva, y las soluciones basadas en la nube introducen dependencias de conectividad, costos recurrentes y riesgos de privacidad que limitan su adopción.

### 2.2 Oportunidad Tecnológica

La convergencia de tres factores tecnológicos habilita este proyecto: primero, la madurez de modelos de detección de objetos en tiempo real (YOLO) que alcanzan precisión de grado producción con requerimientos computacionales modestos; segundo, la disponibilidad de hardware de borde asequible (Raspberry Pi 5, NVIDIA Jetson) capaz de ejecutar inferencia a tasas de frames útiles; y tercero, la consolidación de prácticas DevOps/GitOps que permiten gestionar actualizaciones remotas de software en dispositivos distribuidos de forma segura y escalable.

### 2.3 Propuesta de Valor

- Procesamiento 100% local (Edge AI): cero latencia de red, cero dependencia de internet.
- Privacidad por diseño: datos biométricos y placas nunca abandonan el dispositivo.
- Registro forense automático: cada detección queda documentada con timestamp, imagen cifrada y metadatos.
- Arquitectura modular: nuevos modelos de IA se integran como plugins sin modificar el código base.
- Actualizaciones OTA seguras: el software del vehículo se actualiza automáticamente vía GitOps.

## 3. Alcance del Proyecto

### 3.1 Dentro del Alcance (In Scope)

| ID | Área | Descripción |
|----|------|-------------|
| SC-01 | Captura de video | Pipeline de adquisición de video vía OpenCV soportando cámara USB, archivos de video y RTSP streams. Patrón productor-consumidor con colas thread-safe. |
| SC-02 | Detección de rostros | Módulo de detección facial usando YOLOv8-face con tracking básico para evitar capturas duplicadas. Almacenamiento de recortes con metadatos. |
| SC-03 | Detección de placas | Pipeline de localización de placas (YOLO) + preprocesamiento de imagen + reconocimiento de caracteres (EasyOCR). Validación con dataset de placas latinoamericanas. |
| SC-04 | Almacenamiento local | Base de datos SQLite en modo WAL con tablas de eventos, imágenes cifradas (AES-256) y logs. Rotación automática de archivos. |
| SC-05 | Contenedorización | Dockerfiles multi-stage para imágenes multi-arch (amd64 + arm64). Docker Compose con servicios separados. |
| SC-06 | CI/CD | Pipeline GitHub Actions para build, test, publicación en GHCR. Semantic versioning con Conventional Commits. |
| SC-07 | GitOps Edge | Agente de sincronización en dispositivo edge con estrategia de rollback A/B y health checks. |
| SC-08 | Pruebas | Suite automatizada con pytest: unitarias, integración y estrés (8 horas continuas). |

### 3.2 Fuera del Alcance (Out of Scope)

| ID | Exclusión | Justificación |
|----|-----------|---------------|
| EX-01 | Reconocimiento facial (identificación de personas) | Implicaciones legales de datos biométricos; se limita a detección (hay/no hay rostro). |
| EX-02 | Transmisión de datos a la nube | Contradice el principio fundacional de privacidad local del proyecto. |
| EX-03 | Diseño o fabricación de hardware | Se utilizará hardware comercial existente (RPi5, Jetson). |
| EX-04 | Integración con OBD-II del vehículo | Fuera del MVP; candidato para fases futuras. |
| EX-05 | Aplicación móvil para el usuario final | Fuera del MVP; interfaz será web local o CLI. |
| EX-06 | Entrenamiento de modelos custom desde cero | Se utilizan modelos pre-entrenados con fine-tuning mínimo. |

## 4. Interesados del Proyecto (Stakeholders)

| Rol | Responsabilidad | Nivel de Influencia |
|-----|-----------------|---------------------|
| Patrocinador / Dueño del Producto | Define la visión, prioriza features, aprueba releases | Alto |
| Project Manager | Planificación, seguimiento, gestión de riesgos, facilitación ágil | Alto |
| Desarrollador(es) ML/CV | Implementación de modelos de detección, optimización de inferencia | Alto |
| Desarrollador(es) Backend | Pipeline de captura, almacenamiento, API interna | Alto |
| Ingeniero DevOps | Docker, CI/CD, GitOps, infraestructura edge | Medio-Alto |
| QA / Tester | Diseño y ejecución de pruebas, validación de rendimiento | Medio |
| Usuario Piloto | Pruebas en campo, feedback de usabilidad | Medio |

## 5. Recursos y Stack Tecnológico

### 5.1 Stack de Software

| Área | Tecnología | Versión / Nota |
|------|-----------|-----------------|
| Lenguaje principal | Python | 3.10+ con type hints |
| Gestión de dependencias | Poetry / pip-tools | Lock file para reproducibilidad |
| Visión por computadora | OpenCV | 4.x (con soporte CUDA opcional) |
| Detección de objetos | Ultralytics YOLO | v8 o v11 (modelos nano/small para edge) |
| OCR | EasyOCR / PaddleOCR | Última estable |
| Detección facial | YOLO-Face / MediaPipe | Evaluación comparativa en Fase 2 |
| Base de datos local | SQLite 3 | Modo WAL para concurrencia |
| Cifrado | cryptography (Python) | AES-256-GCM |
| Contenedores | Docker + Docker Compose | Con Buildx para multi-arch |
| CI/CD | GitHub Actions | Runners Ubuntu latest |
| Registro de contenedores | GitHub Container Registry (GHCR) | Imágenes firmadas con Cosign |
| GitOps Edge | Watchtower / script custom | Pull periódico + health check |
| Linting / Formateo | Black + isort + flake8 | Pre-commit hooks |
| Testing | pytest + pytest-cov | Cobertura mínima 80% |
| Optimización de modelos | ONNX Runtime / TensorRT | Exportación desde Ultralytics |

### 5.2 Hardware

| Entorno | Dispositivo | Especificaciones Clave |
|---------|------------|--------------------------|
| Desarrollo / Pruebas | Laptop de desarrollo | CPU x86_64, 8+ GB RAM, webcam integrada, GPU opcional |
| Edge Target (opción A) | Raspberry Pi 5 | ARM Cortex-A76, 8 GB RAM, cámara CSI / USB |
| Edge Target (opción B) | NVIDIA Jetson Orin Nano | ARM + GPU CUDA, 8 GB RAM, aceleración TensorRT |
| Almacenamiento edge | microSD 64GB+ o SSD NVMe | Para imágenes cifradas y base de datos |

## 6. Restricciones Técnicas

| ID | Restricción | Justificación | Métrica |
|----|------------|-----------------|---------|
| RT-01 | Procesamiento 100% offline | Principio fundacional de privacidad | 0 llamadas a APIs externas durante inferencia |
| RT-02 | Latencia < 200ms por frame | Requisito de tiempo real para seguridad | Medido con profiler en hardware objetivo |
| RT-03 | Consumo de RAM ≤ 2 GB | Límite de hardware embebido asequible | Monitoreado con psutil en pruebas de estrés |
| RT-04 | Almacenamiento cifrado AES-256 | Protección de datos biométricos | Validado con suite de tests de cifrado |
| RT-05 | Estabilidad ≥ 8 horas continuas | Jornada típica de uso del vehículo | Test de estrés sin memory leaks ni crashes |
| RT-06 | Imágenes Docker < 2 GB | Ancho de banda limitado para OTA | Medido post-build con docker images |
| RT-07 | Temperatura operativa ≤ 70°C | Seguridad del hardware en vehículo | Sensores de temperatura con alertas |

## 7. Registro de Riesgos

| ID | Riesgo | Prob. | Impacto | Estrategia de Mitigación |
|----|--------|-------|---------|--------------------------|
| R-01 | Rendimiento insuficiente en hardware edge | Media | Alto | Optimizar con TensorRT/ONNX; usar modelos nano; reducir resolución dinámicamente |
| R-02 | Baja precisión en condiciones nocturnas | Alta | Medio | Dataset aumentado con imágenes nocturnas; preprocesamiento adaptativo (CLAHE) |
| R-03 | Sobrecalentamiento del hardware | Media | Medio | Throttling dinámico de FPS; disipador pasivo; monitoreo de temperatura |
| R-04 | Corrupción de datos por vibración | Baja | Alto | SQLite WAL mode; writes atómicos; journaling robusto |
| R-05 | Actualización OTA deja dispositivo inoperante | Baja | Crítico | Partición A/B; rollback automático; health-check pre-switch |
| R-06 | Dependencia de modelo YOLO cambia licencia | Baja | Medio | Abstracción de modelos; compatibilidad con alternativas (RT-DETR, etc.) |
| R-07 | Scope creep por nuevos requerimientos | Alta | Medio | Backlog priorizado; cambios pasan por proceso formal de Change Request |

## 8. Criterios de Éxito del Proyecto

- El sistema detecta rostros con mAP@0.5 ≥ 85% y placas con precisión de lectura ≥ 80% en condiciones diurnas.
- El pipeline completo procesa ≥ 10 FPS en el hardware objetivo (Raspberry Pi 5 o Jetson Nano).
- El contenedor Docker arranca y opera correctamente en arquitecturas amd64 y arm64 sin intervención manual.
- Un push a la rama main dispara el pipeline CI/CD completo y el dispositivo edge aplica la actualización en ≤ 15 minutos.
- El sistema opera de forma estable durante 8 horas continuas sin memory leaks, crashes ni degradación de FPS > 10%.
- El proyecto se completa dentro del plazo de 24 semanas con una desviación máxima de ±2 semanas.

## 9. Aprobaciones

Este documento requiere la aprobación formal de los siguientes interesados antes de que el proyecto inicie oficialmente la ejecución:

| Rol | Nombre | Firma | Fecha |
|-----|--------|-------|-------|
| Patrocinador del Proyecto | _____________________ | _____________________ | ____/____/2026 |
| Project Manager | _____________________ | _____________________ | ____/____/2026 |
| Líder Técnico | _____________________ | _____________________ | ____/____/2026 |
