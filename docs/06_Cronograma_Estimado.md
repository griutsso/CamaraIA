# IA-CAM-SERVICE

## Sistema Inteligente de Cámaras para Automóviles

**CRONOGRAMA ESTIMADO**

Planificación Temporal de 24 Semanas

Documento 6 de 7 | Versión 1.0

Marzo 2026

*Clasificación: Confidencial*

## Cronograma Estimado del Proyecto

Este documento presenta la planificación temporal del proyecto IA-CAM-SERVICE distribuida en 24 semanas (6 meses). El cronograma incluye la asignación de tiempos por fase, hitos de verificación, dependencias críticas y un buffer de contingencia integrado en las fases de mayor riesgo técnico.

## 1. Resumen Ejecutivo del Cronograma

| **Parámetro** | **Valor** |
|---------------|-----------|
| Fecha de inicio | Semana 1 - Marzo 2026 |
| Fecha de cierre estimada | Semana 24 - Agosto 2026 |
| Duración total | 24 semanas (168 días hábiles) |
| Número de fases | 8 fases + cierre |
| Número de hitos | 8 hitos verificables |
| Buffer de contingencia | ~15% integrado en fases críticas (Fase 3 y Fase 5) |
| Metodología de seguimiento | Kanban con reviews semanales |

## 2. Cronograma Detallado por Fase

| **Fase** | **Actividad Principal** | **Inicio** | **Fin** | **Duración** | **Hito** |
|----------|------------------------|-----------|---------|--------------|----------|
| Fase 0 | Configuración del entorno y gobernanza | S1 | S2 | 2 sem | H1 |
| Fase 1 | Módulo de captura de video (OpenCV) | S3 | S4 | 2 sem | --- |
| Fase 2 | Detección de rostros (YOLO-Face) | S5 | S6 | 2 sem | H2 |
| Fase 3 | Detección y lectura de placas (YOLO + EasyOCR) | S7 | S10 | 4 sem* | H3 |
| Fase 4 | Motor de registro y almacenamiento (SQLite + AES) | S11 | S12 | 2 sem | H4 |
| Fase 5 | Integración, pruebas y optimización (ONNX/TensorRT) | S13 | S16 | 4 sem* | H5 |
| Fase 6 | Contenedorización Docker multi-arch | S17 | S19 | 3 sem | H6 |
| Fase 7 | Pipeline GitOps y despliegue edge | S20 | S22 | 3 sem | H7 |
| Cierre | Pruebas de aceptación y documentación final | S23 | S24 | 2 sem | H8 |

*(*) Fases con buffer de contingencia integrado: incluyen ~1 semana adicional por complejidad y riesgo técnico.*

## 3. Distribución Visual (Diagrama de Gantt)

La siguiente representación muestra la distribución temporal de cada fase a lo largo de las 24 semanas del proyecto:

| **Fase** | **S1-2** | **S3-4** | **S5-6** | **S7-10** | **S11-12** | **S13-16** | **S17-19** | **S20-22** | **S23-24** |
|----------|----------|----------|----------|-----------|------------|-----------|-----------|-----------|-----------|
| F0: Entorno | ███ | | | | | | | | |
| F1: Captura | | ███ | | | | | | | |
| F2: Rostros | | | ███ | | | | | | |
| F3: Placas | | | | ████ | | | | | |
| F4: Storage | | | | | ███ | | | | |
| F5: Integración | | | | | | ████ | | | |
| F6: Docker | | | | | | | ███ | | |
| F7: GitOps | | | | | | | | ███ | |
| Cierre | | | | | | | | | ███ |

## 4. Dependencias Críticas

Las fases del proyecto siguen una secuencia mayoritariamente lineal, donde cada fase depende del entregable de la anterior. A continuación se documentan las dependencias críticas que, si se retrasan, impactarían directamente la fecha de cierre:

| **Dependencia** | **Fase Origen** | **Fase Destino** | **Tipo** | **Impacto si se Retrasa** |
|-----------------|-----------------|------------------|----------|--------------------------|
| DEP-01 | Fase 0 (Entorno) | Fase 1 (Captura) | Finish-to-Start | Retrasa toda la cadena de desarrollo |
| DEP-02 | Fase 1 (Captura) | Fase 2 (Rostros) | Finish-to-Start | No hay frames para procesar |
| DEP-03 | Fase 2 (Rostros) | Fase 3 (Placas) | Finish-to-Start | Pipeline compartido requerido |
| DEP-04 | Fase 3 (Placas) | Fase 4 (Storage) | Finish-to-Start | No hay eventos para almacenar |
| DEP-05 | Fases 2+3+4 | Fase 5 (Integración) | Finish-to-Start | No hay módulos que integrar |
| DEP-06 | Fase 5 (Integración) | Fase 6 (Docker) | Finish-to-Start | No hay aplicación que empaquetar |
| DEP-07 | Fase 6 (Docker) | Fase 7 (GitOps) | Finish-to-Start | No hay imagen Docker que desplegar |

## 5. Ruta Crítica

La ruta crítica del proyecto es la secuencia más larga de actividades dependientes que determina la duración mínima del proyecto. Cualquier retraso en estas fases impacta directamente la fecha de entrega:

**Fase 0 → Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5 → Fase 6 → Fase 7 → Cierre**

Dado que todas las fases están en la ruta crítica (secuencia lineal), la gestión de riesgos y el buffer de contingencia son especialmente importantes. Las fases con mayor riesgo técnico (Fase 3: Placas y Fase 5: Integración) tienen buffers integrados de ~1 semana cada una.

## 6. Calendario de Hitos

Asumiendo inicio en la primera semana de marzo 2026, las fechas estimadas de cada hito son:

| **Hito** | **Descripción** | **Semana** | **Fecha Estimada** |
|----------|-----------------|-----------|-------------------|
| H1 | Entorno operativo y CI básico | S2 | 14 marzo 2026 |
| H2 | Detección de rostros funcional | S6 | 11 abril 2026 |
| H3 | Detección dual (rostros + placas) | S10 | 9 mayo 2026 |
| H4 | Registro forense local completo | S12 | 23 mayo 2026 |
| H5 | Sistema optimizado y estable (8h) | S16 | 20 junio 2026 |
| H6 | Contenedor Docker multi-arch | S19 | 11 julio 2026 |
| H7 | Pipeline GitOps end-to-end | S22 | 1 agosto 2026 |
| H8 | Release Candidate v1.0 | S24 | 15 agosto 2026 |

## 7. Estimación de Esfuerzo por Rol

La siguiente tabla estima las horas/semana requeridas por rol en cada fase, asumiendo un equipo reducido (2-3 personas con roles compartidos):

| **Fase** | **Dev ML/CV** | **Dev Backend** | **DevOps** | **QA** |
|----------|---------------|-----------------|-----------|--------|
| F0: Entorno | 5h/sem | 10h/sem | 20h/sem | 5h/sem |
| F1: Captura | 5h/sem | 30h/sem | 5h/sem | 10h/sem |
| F2: Rostros | 30h/sem | 10h/sem | 5h/sem | 10h/sem |
| F3: Placas | 35h/sem | 10h/sem | 5h/sem | 10h/sem |
| F4: Storage | 5h/sem | 30h/sem | 5h/sem | 10h/sem |
| F5: Integración | 20h/sem | 15h/sem | 10h/sem | 20h/sem |
| F6: Docker | 5h/sem | 10h/sem | 30h/sem | 10h/sem |
| F7: GitOps | 5h/sem | 10h/sem | 30h/sem | 15h/sem |
| Cierre | 10h/sem | 10h/sem | 10h/sem | 20h/sem |

## 8. Plan de Contingencia Temporal

Ante retrasos significativos, se pueden activar las siguientes estrategias para proteger la fecha de entrega:

| **Estrategia** | **Aplicable Cuando** | **Impacto en Alcance** | **Ahorro Temporal** |
|----------------|---------------------|----------------------|-------------------|
| Reducir precisión objetivo de placas a 70% | Fase 3 se retrasa > 1 semana | Menor (se mejora post-release) | ≈1 semana |
| Omitir variante Docker NVIDIA (solo CPU) | Fase 6 se retrasa > 1 semana | Medio (sin aceleración GPU) | ≈1 semana |
| Simplificar rollback a manual (sin A/B) | Fase 7 se retrasa > 1 semana | Medio (rollback no automático) | ≈1 semana |
| Comprimir cierre a 1 semana | Retraso acumulado ≤ 1 semana | Menor (documentación reducida) | 1 semana |
| Paralelizar Fases 4 y 3 (overlap 1 sem) | Equipo disponible | Ninguno (si hay suficiente personal) | ≈1 semana |
