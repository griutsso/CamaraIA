# IA-CAM-SERVICE

## Sistema Inteligente de Cámaras para Automóviles

**ROADMAP MACRO**

Hitos Técnicos Principales

Documento 5 de 7 | Versión 1.0

Marzo 2026

*Clasificación: Confidencial*

## Roadmap Macro del Proyecto

Este documento presenta la visión de alto nivel del proyecto IA-CAM-SERVICE organizada en tres grandes etapas estratégicas: Fundación, Inteligencia y Despliegue. Cada etapa agrupa hitos técnicos que representan logros verificables y entregables concretos del proyecto. El roadmap sirve como instrumento de comunicación ejecutiva y herramienta de seguimiento para stakeholders.

## 1. Visión General del Roadmap

El proyecto se estructura en 8 hitos distribuidos a lo largo de 24 semanas. Los hitos están diseñados para ser incrementales: cada uno construye sobre el anterior y genera un entregable funcional que puede demostrarse. Esta aproximación permite obtener feedback temprano, detectar desviaciones y ajustar el rumbo sin esperar al final del proyecto.

| **Etapa** | **Semanas** | **Enfoque** | **Resultado Esperado** |
|-----------|-------------|-------------|----------------------|
| FUNDACIÓN | S1 - S6 | Infraestructura + Primera detección | Pipeline de captura + rostros detectados en vivo |
| INTELIGENCIA | S7 - S16 | Detecciones completas + Optimización | Rostros + placas + almacenamiento + 8h estable |
| DESPLIEGUE | S17 - S24 | Contenedores + GitOps + Release | Sistema empaquetado, desplegable y actualizable |

## 2. Etapa 1: FUNDACIÓN (Semanas 1-6)

La etapa de Fundación establece toda la infraestructura necesaria y demuestra la primera capacidad de inteligencia artificial del sistema. Al completarse, el equipo tiene un entorno de desarrollo robusto y un prototipo funcional de detección facial.

### Hito H1: Entorno Operativo (Semana 2)

**Descripción:** El repositorio Git está configurado con la estructura modular del proyecto, las dependencias instaladas, el CI básico operativo y el tablero Kanban poblado con las tareas de las primeras fases.

**Entregable Clave:** Repositorio configurado con CI básico funcional y captura de video operativa.

**Verificación del Hito**

- Cualquier desarrollador puede clonar, instalar y ejecutar tests en ≤ 5 minutos.
- Un PR dispara lint + tests automáticamente.
- La webcam captura video a ≥ 30 FPS sin drops.

**Riesgos Específicos**

- Incompatibilidad de dependencias entre plataformas (mitigación: lock files + Docker temprano).

### Hito H2: Primer Frame Procesado (Semana 6)

**Descripción:** El pipeline de detección de rostros está operativo, procesando video en vivo desde la webcam y detectando rostros con la precisión objetivo. Es la primera demostración tangible de IA funcionando en tiempo real.

**Entregable Clave:** Módulo de detección facial corriendo en laptop con ≥ 15 FPS y mAP ≥ 85%.

**Verificación del Hito**

- Demo en vivo: la webcam detecta y enmarca rostros en tiempo real.
- Benchmark automatizado reporta mAP@0.5 ≥ 85%.
- El tracking evita capturas duplicadas en demo de 5 minutos.

**Riesgos Específicos**

- Precisión insuficiente con el primer modelo evaluado (mitigación: 3 modelos candidatos evaluados).

## 3. Etapa 2: INTELIGENCIA (Semanas 7-16)

La etapa de Inteligencia completa las capacidades de detección del sistema, implementa el almacenamiento seguro y valida la estabilidad operativa. Al completarse, el sistema es funcionalmente completo para su caso de uso principal.

### Hito H3: Detección Dual (Semana 10)

**Descripción:** Ambos módulos de detección (rostros y placas) operan simultáneamente sobre el mismo feed de video, compartiendo el pipeline de captura y generando eventos independientes.

**Entregable Clave:** Rostros y placas detectados simultáneamente en video en vivo con FPS ≥ 10.

**Verificación del Hito**

- Demo dual: la webcam detecta y anota rostros y placas simultáneamente.
- Lectura correcta de placas ≥ 80% en dataset de validación.
- Ambos módulos son independientes: desactivar uno no afecta al otro.

### Hito H4: Registro Forense (Semana 12)

**Descripción:** El motor de almacenamiento local está operativo, registrando automáticamente cada detección con imágenes cifradas, metadatos estructurados y logs del sistema.

**Entregable Clave:** Base de datos SQLite con eventos de detección, imágenes cifradas AES-256 y CLI de consulta.

**Verificación del Hito**

- Después de 30 minutos de operación, la CLI muestra registros completos con imágenes descifrables.
- SQLite soporta ≥ 50 escrituras/segundo bajo prueba de carga.
- La rotación de archivos funciona al alcanzar el umbral configurado.

### Hito H5: Optimización y Estabilidad (Semana 16)

**Descripción:** Los modelos están optimizados (ONNX/TensorRT), el pipeline unificado es estable y el sistema supera las pruebas de estrés de larga duración.

**Entregable Clave:** Sistema integrado corriendo 8 horas estables sin degradación, modelos optimizados.

**Verificación del Hito**

- 8 horas continuas sin crashes, memory leaks ni caída de FPS > 10%.
- Modelos ONNX/TensorRT con mejora de velocidad ≥ 30% vs. PyTorch nativo.
- Cobertura de tests global ≥ 80%.

## 4. Etapa 3: DESPLIEGUE (Semanas 17-24)

La etapa de Despliegue empaqueta el sistema para distribución, implementa la automatización GitOps y prepara el Release Candidate. Al completarse, el sistema está listo para piloto en vehículos reales.

### Hito H6: Contenedor Multi-Arch (Semana 19)

**Descripción:** La aplicación está empaquetada en contenedores Docker multi-arquitectura que funcionan tanto en el entorno de desarrollo como en el hardware edge objetivo.

**Entregable Clave:** Imagen Docker ≤ 2 GB corriendo en laptop (amd64) y Raspberry Pi/Jetson (arm64).

**Verificación del Hito**

- docker compose up levanta el sistema sin errores en ambas arquitecturas.
- Los tests pasan dentro del contenedor.
- Health-checks reportan estado saludable en todos los servicios.

### Hito H7: GitOps End-to-End (Semana 22)

**Descripción:** El pipeline CI/CD completo está operativo: un push a main dispara build, tests, publicación de imagen firmada y despliegue automático en el dispositivo edge con capacidad de rollback.

**Entregable Clave:** Pipeline completo: commit → build → push → deploy automático en dispositivo edge.

**Verificación del Hito**

- CI completo en ≤ 10 minutos.
- Dispositivo edge aplica actualización en ≤ 5 minutos adicionales.
- Rollback automático verificado con imagen defectuosa intencional.

### Hito H8: Release Candidate v1.0 (Semana 24)

**Descripción:** El sistema está completamente validado contra los criterios de aceptación, documentado profesionalmente y etiquetado como Release Candidate. Está listo para iniciar un programa piloto en vehículos reales.

**Entregable Clave:** Release v1.0 en GitHub con documentación completa, changelog y retrospectiva.

**Verificación del Hito**

- Los 4 objetivos SMART están verificados con evidencia documentada.
- Documentación técnica completa: arquitectura, API, instalación, runbook, troubleshooting.
- Retrospectiva completada con lecciones aprendidas y roadmap futuro.

## 5. Visión Post-v1.0 (Roadmap Futuro)

Aunque fuera del alcance actual del proyecto, la arquitectura modular de IA-CAM-SERVICE está diseñada para soportar las siguientes extensiones futuras:

| **Fase Futura** | **Capacidad** | **Complejidad** | **Prioridad Estimada** |
|-----------------|---------------|-----------------|----------------------|
| v1.1 | Detección de somnolencia del conductor (eye tracking) | Media | Alta |
| v1.2 | Alertas por proximidad sospechosa de personas | Media | Alta |
| v1.3 | Reconocimiento de señales de tránsito | Baja | Media |
| v1.4 | Detección de daños en carrocería (pre/post estacionamiento) | Alta | Media |
| v2.0 | Dashboard web local para visualización de eventos | Media | Alta |
| v2.1 | Aplicación móvil para consulta remota (vía WiFi local) | Alta | Media |
| v2.2 | Integración OBD-II para correlación con datos del vehículo | Alta | Baja |
| v3.0 | Gestión centralizada de flota con telemetría agregada | Muy Alta | Media |
