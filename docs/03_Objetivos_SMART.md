# IA-CAM-SERVICE

## Sistema Inteligente de Cámaras para Automóviles

### OBJETIVOS SMART

Metas Estratégicas del Proyecto

**Documento 3 de 7 | Versión 1.0**

Marzo 2026

*Clasificación: Confidencial*

---

## Objetivos SMART del Proyecto

Los siguientes cuatro objetivos han sido formulados bajo la metodología SMART (Específico, Medible, Alcanzable, Relevante y con Tiempo definido). Cada uno está alineado con un entregable crítico del proyecto y cuenta con criterios de aceptación verificables que permitirán evaluar objetivamente el progreso y el éxito del proyecto.

---

## OBJ-1: Detección de Rostros en Tiempo Real

| **Criterio SMART** | **Descripción** |
|---|---|
| **S -- Específico** | Implementar un módulo de detección de rostros humanos utilizando el modelo YOLOv8-face (o equivalente evaluado) sobre el feed de video en vivo capturado por OpenCV. El módulo debe detectar rostros en el frame, aplicar tracking básico (IoU-based) para evitar capturas duplicadas del mismo individuo, y almacenar automáticamente un recorte facial con metadatos (timestamp, bounding box, score de confianza) en la base de datos local. |
| **M -- Medible** | Alcanzar un mAP\@0.5 ≥ 85% evaluado sobre un subconjunto de WIDER FACE (validation set, nivel easy+medium). El pipeline debe procesar ≥ 15 FPS en una laptop de desarrollo estándar (CPU i5/Ryzen 5 equivalente) y ≥ 10 FPS en el hardware edge objetivo. La tasa de falsos positivos debe ser ≤ 5% en escenarios diurnos controlados. |
| **A -- Alcanzable** | Se utilizarán modelos pre-entrenados del ecosistema Ultralytics, que han demostrado alcanzar estos niveles de precisión en benchmarks públicos. El fine-tuning será mínimo (transfer learning con dataset reducido). OpenCV provee una API madura y bien documentada para captura de video. El tracking IoU-based es un algoritmo liviano que no añade carga computacional significativa. |
| **R -- Relevante** | La detección de rostros es la funcionalidad central del MVP y el primer pilar del sistema de seguridad. Sin ella, el sistema no puede generar registros forenses de personas cercanas al vehículo, que es el caso de uso principal ante incidentes de robo, vandalismo o accidentes. |
| **T -- Temporal** | Completado y validado al final de la Semana 6 del proyecto (mediados de abril 2026). Hito intermedio: prototipo funcional (sin tracking) en Semana 5 para revisión temprana. |

### Criterios de Aceptación

- El módulo detecta correctamente rostros en el feed en vivo de una webcam con ≥ 85% mAP\@0.5.
- No se generan capturas duplicadas del mismo rostro en un intervalo de 3 segundos (tracking funcional).
- Cada detección genera un registro en SQLite con: ID único, timestamp ISO 8601, bounding box, confianza, ruta a imagen cifrada.
- El módulo puede activarse/desactivarse independientemente sin afectar otros componentes del pipeline.

---

## OBJ-2: Detección y Lectura de Placas Vehiculares

| **Criterio SMART** | **Descripción** |
|---|---|
| **S -- Específico** | Desarrollar un pipeline de dos etapas para placas vehiculares: primero, un modelo YOLO entrenado o fine-tuned para localizar la región de la placa en el frame; segundo, un pipeline de preprocesamiento (enderezado perspectivo, binarización adaptativa, aumento de contraste CLAHE) seguido de EasyOCR para extraer el texto alfanumérico de la placa. El resultado se registra en la base de datos con la imagen de la placa, el texto leído y un score de confianza. |
| **M -- Medible** | Precisión de lectura correcta del texto completo de la placa ≥ 80% en condiciones diurnas estándar (dataset de validación de placas latinoamericanas, ≥ 200 imágenes). Precisión de localización (IoU ≥ 0.5) ≥ 90%. El pipeline completo (detección + OCR) debe procesar ≥ 10 FPS en laptop y ≥ 5 FPS en hardware edge. Tiempo de OCR por placa detectada ≤ 100ms. |
| **A -- Alcanzable** | Existen datasets públicos de placas vehiculares (OpenALPR benchmark, datasets académicos latinoamericanos) para entrenar y validar. EasyOCR soporta múltiples idiomas y ha demostrado resultados competitivos en texto estructurado. El preprocesamiento con OpenCV es una técnica establecida que mejora significativamente la precisión de OCR en placas. |
| **R -- Relevante** | La lectura de placas es el segundo pilar del sistema de seguridad y complementa directamente la detección de rostros. Permite registrar los vehículos cercanos al auto del usuario, lo cual es crítico para la investigación de incidentes (accidentes con fuga, vehículos sospechosos, robos en estacionamientos). |
| **T -- Temporal** | Completado y validado al final de la Semana 10 del proyecto (finales de mayo 2026). Hito intermedio: localización de placas funcional (sin OCR) en Semana 8 para validación temprana del modelo YOLO. |

### Criterios de Aceptación

- El modelo YOLO localiza placas con IoU ≥ 0.5 en ≥ 90% de las imágenes del dataset de validación.
- EasyOCR lee correctamente el texto completo de la placa en ≥ 80% de los casos (condiciones diurnas).
- El pipeline soporta formatos de placas de al menos 3 países latinoamericanos (México, Colombia, Argentina).
- Cada detección genera un registro con: texto de placa, confianza OCR, imagen de la placa cifrada, timestamp.

---

## OBJ-3: Empaquetado y Despliegue Containerizado

| **Criterio SMART** | **Descripción** |
|---|---|
| **S -- Específico** | Empaquetar la totalidad de la aplicación (código fuente, modelos de IA, dependencias Python, configuraciones) en contenedores Docker multi-arquitectura (amd64 para desarrollo, arm64 para hardware edge). Utilizar Dockerfiles multi-stage para separar el entorno de build del entorno de ejecución y minimizar el tamaño final. Definir un docker-compose.yml con servicios separados para captura, detección y registro. |
| **M -- Medible** | El contenedor arranca correctamente en laptop (amd64) y en Raspberry Pi 5 / Jetson (arm64) sin intervención manual (docker compose up). La imagen final pesa ≤ 2 GB. El tiempo de arranque en frío es ≤ 30 segundos. Los tests automatizados pasan dentro del contenedor (docker compose run tests). |
| **A -- Alcanzable** | Docker Buildx soporta nativamente compilación cruzada multi-arch. Existen imágenes base optimizadas con OpenCV y CUDA pre-compilados (nvidia/cuda, arm64v8/python). La separación en servicios Docker Compose es una práctica estándar y bien documentada. |
| **R -- Relevante** | La contenedorización es el requisito habilitante para el despliegue automático en vehículos. Sin contenedores reproducibles, cada instalación en hardware edge requeriría configuración manual, lo cual es inviable a escala. |
| **T -- Temporal** | Completado al final de la Semana 16 del proyecto (julio 2026). Hito intermedio: Dockerfile funcional en amd64 en Semana 14. |

### Criterios de Aceptación

- docker compose up levanta todos los servicios sin errores en ambas arquitecturas.
- Los modelos de IA se cargan correctamente y el sistema comienza a procesar video en ≤ 30 segundos.
- La imagen Docker pesa ≤ 2 GB y está publicada en GHCR con tags semánticos.
- docker compose run tests ejecuta la suite completa de pytest con ≥ 80% de cobertura.

---

## OBJ-4: Pipeline GitOps para Actualización Remota

| **Criterio SMART** | **Descripción** |
|---|---|
| **S -- Específico** | Implementar un pipeline CI/CD completo con GitHub Actions que, ante cada merge a la rama main, ejecute: linting, tests unitarios/integración, build de imagen Docker multi-arch, publicación en GHCR con firma Cosign, y creación de Release con changelog automático. En el dispositivo edge, un agente liviano (Watchtower o script custom con cron) monitorea GHCR, descarga nuevas imágenes, ejecuta health-checks y reemplaza el contenedor activo con estrategia de rollback A/B. |
| **M -- Medible** | El pipeline CI completo (lint + tests + build + push) se ejecuta en ≤ 10 minutos. El dispositivo edge detecta y aplica la actualización en ≤ 5 minutos adicionales. El rollback automático se activa en ≤ 60 segundos si el health-check falla. La disponibilidad del servicio durante actualización es ≥ 99% (downtime ≤ 30 segundos). |
| **A -- Alcanzable** | GitHub Actions ofrece runners gratuitos con capacidad suficiente para builds Docker. Watchtower es una herramienta madura y liviana para monitoreo de imágenes. La estrategia A/B con Docker es implementable mediante scripts shell + Docker API. Cosign es la herramienta estándar de la industria para firma de imágenes. |
| **R -- Relevante** | El pipeline GitOps cierra el ciclo completo de DevOps y es lo que permite mantener actualizados de forma segura y escalable todos los vehículos desplegados. Sin él, cada actualización requeriría acceso físico al vehículo. |
| **T -- Temporal** | Completado y probado end-to-end al final de la Semana 22 del proyecto (agosto 2026). Hito intermedio: CI funcional (sin despliegue edge) en Semana 20. |

### Criterios de Aceptación

- Un commit en main dispara automáticamente el pipeline CI/CD y genera una imagen Docker firmada en GHCR.
- El dispositivo edge aplica la nueva imagen automáticamente sin intervención humana.
- Si el health-check falla, el sistema revierte a la imagen anterior en ≤ 60 segundos.
- El changelog se genera automáticamente a partir de Conventional Commits.
- Todo el flujo está documentado en un runbook operativo.

---

## Matriz Resumen de Objetivos

| **Objetivo** | **KPI Principal** | **Deadline** | **Dependencia** |
|---|---|---|---|
| OBJ-1: Detección de Rostros | mAP\@0.5 ≥ 85%, ≥ 15 FPS | Semana 6 | Fase 0 + Fase 1 |
| OBJ-2: Placas Vehiculares | Lectura correcta ≥ 80%, ≥ 10 FPS | Semana 10 | OBJ-1 (pipeline compartido) |
| OBJ-3: Docker Multi-Arch | Arranque en amd64 + arm64, ≤ 2 GB | Semana 16 | OBJ-1 + OBJ-2 |
| OBJ-4: GitOps End-to-End | CI ≤ 10min, deploy edge ≤ 5min | Semana 22 | OBJ-3 |
