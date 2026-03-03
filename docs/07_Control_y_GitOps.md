# IA-CAM-SERVICE

## Sistema Inteligente de Cámaras para Automóviles

**SISTEMA DE CONTROL Y ESTRATEGIA GITOPS**

Gobernanza, Ramificación y Despliegue Continuo

Documento 7 de 7 | Versión 1.0

Marzo 2026

*Clasificación: Confidencial*

## Sistema de Control y Estrategia GitOps

Este documento define el framework completo de gobernanza del desarrollo del proyecto IA-CAM-SERVICE: la gestión ágil del trabajo, la estrategia de ramificación en Git, el pipeline de CI/CD y la implementación de GitOps para el despliegue automático y seguro de actualizaciones en los dispositivos edge de los vehículos.

## 1. Gestión Ágil: Kanban con WIP Limits

### 1.1 Filosofía de Gestión

El proyecto adopta Kanban como framework ágil principal por su flexibilidad para equipos pequeños y su enfoque en el flujo continuo de trabajo, complementado con elementos puntuales de Scrum (retrospectivas quincenales, demos de hito). La herramienta de gestión es GitHub Projects, integrada nativamente con Issues y Pull Requests del repositorio.

### 1.2 Tablero Kanban

| **Columna** | **Descripción** | **WIP Limit** | **Reglas de Transición** |
|-------------|-----------------|---------------|-------------------------|
| Backlog | Todas las tareas identificadas, priorizadas por valor/urgencia | Sin límite | Product Owner prioriza; equipo refina |
| Ready | Tareas refinadas con criterios de aceptación claros | 5 | Debe tener descripción, AC y estimación |
| In Progress | Tareas en desarrollo activo, asignadas a un developer | 3 | Developer asigna y crea branch feature/* |
| In Review | Pull Request creado, esperando revisión de código | 3 | PR pasa CI automático; reviewer asignado |
| Testing | Cambio aprobado en review, en validación funcional | 2 | QA ejecuta tests manuales si aplica |
| Done | Tarea completada, merge a develop realizado | Sin límite | PR mergeado con squash commit |

### 1.3 Ceremonias

| **Ceremonia** | **Frecuencia** | **Duración** | **Propósito** |
|---------------|----------------|-------------|---------------|
| Daily Standup (async) | Lunes, Miércoles, Viernes | 15 min | Sincronización de avances y bloqueos |
| Backlog Refinement | Semanal (Lunes) | 30 min | Priorizar y detallar tareas del backlog |
| Demo de Hito | Al completar cada hito | 30-45 min | Demostrar entregable a stakeholders |
| Retrospectiva | Quincenal (Viernes) | 45 min | Identificar mejoras en el proceso |

### 1.4 Métricas de Flujo

- **Lead Time:** tiempo desde que una tarea entra a Ready hasta que llega a Done. Objetivo: ≤ 5 días hábiles.
- **Cycle Time:** tiempo desde In Progress hasta Done. Objetivo: ≤ 3 días hábiles.
- **Throughput:** número de tareas completadas por semana. Objetivo: ≥ 4 tareas/semana.
- **WIP Violations:** número de veces que se excede el WIP limit. Objetivo: 0/semana.

## 2. Estrategia de Ramificación Git (GitFlow Simplificado)

### 2.1 Ramas Principales

| **Rama** | **Propósito** | **Protección** | **Política de Merge** |
|----------|---------------|---------------|--------------------|
| main | Código en producción desplegado en dispositivos edge | Protegida: requiere PR + 1 approval + CI verde | Solo desde release/* o hotfix/* (merge commit) |
| develop | Rama de integración continua del equipo | Protegida: requiere PR + CI verde | Desde feature/* (squash merge) |

### 2.2 Ramas de Trabajo

| **Tipo de Rama** | **Nomenclatura** | **Origen** | **Destino** | **Ejemplo** |
|-----------------|-----------------|-----------|-----------|-----------|
| Feature | feature/IACAM-{n}-{desc} | develop | develop | feature/IACAM-12-face-tracking |
| Hotfix | hotfix/IACAM-{n}-{desc} | main | main + develop | hotfix/IACAM-45-sqlite-crash |
| Release | release/v{X.Y.Z} | develop | main + develop | release/v1.0.0 |
| Experiment | experiment/{desc} | develop | Se descarta o PR a develop | experiment/retinaface-eval |

### 2.3 Flujo de Trabajo Típico

1. El developer toma una tarea de Ready y la mueve a In Progress.
2. Crea una rama feature/IACAM-XX-descripcion desde develop.
3. Desarrolla la funcionalidad con commits pequeños siguiendo Conventional Commits.
4. Crea un Pull Request hacia develop con descripción, enlace al Issue y checklist de AC.
5. GitHub Actions ejecuta automáticamente: lint, tests, cobertura, security scan.
6. Un reviewer aprueba el PR (o solicita cambios).
7. Se hace squash merge a develop. El Issue se mueve a Testing.
8. QA valida en develop. Si pasa, la tarea se mueve a Done.

### 2.4 Conventional Commits

Todos los mensajes de commit deben seguir la especificación Conventional Commits para habilitar la generación automática de changelog y semantic versioning:

| **Prefijo** | **Uso** | **Ejemplo** | **Efecto en Versión** |
|-------------|---------|-----------|----------------------|
| feat: | Nueva funcionalidad | feat(detection): add face tracking module | Minor (0.X.0) |
| fix: | Corrección de bug | fix(storage): prevent SQLite WAL corruption | Patch (0.0.X) |
| perf: | Mejora de rendimiento | perf(ocr): optimize CLAHE preprocessing | Patch |
| refactor: | Refactorización sin cambio funcional | refactor(capture): extract VideoSource ABC | Ninguno |
| test: | Añadir o modificar tests | test(detection): add WIDER FACE benchmark | Ninguno |
| docs: | Documentación | docs: update architecture diagram | Ninguno |
| ci: | Cambios en CI/CD | ci: add arm64 Docker build stage | Ninguno |
| chore: | Tareas de mantenimiento | chore: update dependencies | Ninguno |
| BREAKING CHANGE: | Cambio incompatible | feat!: redesign detection plugin API | Major (X.0.0) |

## 3. Pipeline CI/CD (GitHub Actions)

### 3.1 Continuous Integration (en cada Pull Request)

Cada Pull Request dispara automáticamente el siguiente pipeline de validación. El PR no puede mergearse si alguno de estos pasos falla:

| **Step** | **Herramienta** | **Criterio de Aprobación** | **Tiempo Estimado** |
|----------|-----------------|--------------------------|-------------------|
| 1. Lint & Format | Black + isort + flake8 | 0 errores de formateo o linting | ≈30 seg |
| 2. Type Check | mypy (modo básico) | 0 errores en interfaces públicas | ≈45 seg |
| 3. Unit Tests | pytest | 100% tests pasan | ≈1-2 min |
| 4. Integration Tests | pytest (markers) | 100% tests pasan | ≈2-3 min |
| 5. Coverage | pytest-cov | Cobertura ≥ 80% (fail under) | ≈Incluido en tests |
| 6. Security Scan | Safety / pip-audit | 0 vulnerabilidades críticas/altas | ≈30 seg |

### 3.2 Continuous Delivery (en merge a main)

Cuando un release branch se mergea a main, se ejecuta el pipeline completo de entrega:

| **Step** | **Acción** | **Artefacto Generado** |
|---------|-----------|----------------------|
| 1. CI completo | Re-ejecutar lint + tests + coverage + security | Reporte de CI |
| 2. Build Docker (amd64) | docker buildx build --platform linux/amd64 | Imagen amd64 en GHCR |
| 3. Build Docker (arm64) | docker buildx build --platform linux/arm64 | Imagen arm64 en GHCR |
| 4. Sign Image | cosign sign --key ... ghcr.io/org/iacam:tag | Firma Cosign verificable |
| 5. Run Container Tests | docker compose run tests | Reporte de tests en contenedor |
| 6. Generate Changelog | semantic-release / release-please | CHANGELOG.md actualizado |
| 7. Create Release | gh release create vX.Y.Z | Release en GitHub con binarios |
| 8. Notify | GitHub webhook / Slack (opcional) | Notificación al equipo |

### 3.3 Estructura del Workflow

El pipeline se implementa en dos archivos de workflow de GitHub Actions:

- **ci.yml:** se ejecuta en cada PR a develop. Contiene los steps 1-6 de CI.
- **release.yml:** se ejecuta en merge a main. Contiene CI completo + build Docker + sign + release.

Ambos workflows utilizan caching agresivo (pip cache, Docker layer cache) para minimizar tiempos de ejecución.

## 4. Despliegue GitOps en Dispositivos Edge

### 4.1 Principios de Diseño

El despliegue GitOps en dispositivos edge sigue los principios de GitOps adaptados a un entorno con conectividad intermitente:

- **Declarativo:** el estado deseado del sistema está definido por la imagen Docker publicada en GHCR con el tag latest o un tag semántico específico.
- **Versionado:** cada imagen corresponde a un release semántico (vX.Y.Z) con changelog y firma Cosign.
- **Automatizado:** el agente de sincronización en el dispositivo edge aplica actualizaciones sin intervención humana.
- **Observable:** cada acción del agente queda registrada en un log inmutable local.
- **Resiliente:** si una actualización falla, el sistema revierte automáticamente a la versión anterior.

### 4.2 Arquitectura del Agente de Sincronización

En cada dispositivo edge (vehículo) corre un agente liviano implementado en Python que ejecuta el siguiente ciclo cada 5 minutos (configurable via cron):

1. Verificar conectividad: el agente solo actúa si detecta conexión a internet (ping a GHCR).
2. Consultar GHCR: comparar el digest de la imagen local con la última publicada.
3. Si hay nueva versión: descargar la imagen, verificar firma Cosign.
4. Pre-deploy health-check: levantar la nueva imagen en un contenedor temporal, ejecutar health endpoint.
5. Deploy: si el health-check pasa, detener el contenedor activo y levantar el nuevo.
6. Post-deploy health-check: verificar que el nuevo contenedor responde correctamente en ≤30 segundos.
7. Rollback (si falla): si el post-deploy health-check falla 2 veces consecutivas, revertir a la imagen anterior (estrategia A/B).
8. Logging: registrar todo el proceso con timestamp, versión anterior, versión nueva, resultado.

### 4.3 Estrategia de Rollback A/B

El dispositivo edge mantiene siempre dos imágenes Docker: la activa (A) y la anterior (B). El flujo de actualización es:

| **Estado** | **Imagen A (Activa)** | **Imagen B (Backup)** | **Acción del Agente** |
|-----------|----------------------|----------------------|----------------------|
| Pre-actualización | v1.2.0 (corriendo) | v1.1.0 (almacenada) | Detecta v1.3.0 disponible |
| Descarga | v1.2.0 (corriendo) | v1.1.0 → se descarta | Descarga v1.3.0, firma verificada |
| Deploy exitoso | v1.3.0 (corriendo) | v1.2.0 (almacenada) | Health-check OK, deploy completado |
| Deploy fallido | v1.2.0 (restaurada) | v1.3.0 (marcada como defectuosa) | Rollback automático, alerta registrada |

## 5. Seguridad del Pipeline

### 5.1 Cadena de Confianza

La seguridad del pipeline se basa en una cadena de confianza verificable desde el código fuente hasta el dispositivo edge:

| **Capa** | **Mecanismo de Seguridad** | **Herramienta** |
|---------|---------------------------|-----------------|
| Código fuente | Branch protection + PR reviews obligatorios | GitHub |
| Dependencias | Escaneo de vulnerabilidades en cada PR | Safety / pip-audit / Snyk |
| Build | Builds reproducibles en runners efimeros | GitHub Actions |
| Imágenes Docker | Firma criptográfica con Cosign (Sigstore) | Cosign |
| Transporte | Comunicación cifrada TLS con GHCR | HTTPS/TLS |
| Dispositivo edge | Verificación de firma antes de deploy | Cosign verify |
| Secretos | Variables cifradas, nunca en código | GitHub Secrets + SOPS |

### 5.2 Políticas de Seguridad

- Rotación de tokens de GHCR cada 90 días.
- Máximo 2 intentos de actualización fallida antes de bloquear y notificar.
- Los secretos del dispositivo edge se almacenan cifrados con SOPS + age.
- Auditoría: log inmutable de cada operación del agente, exportable para revisión.
- El agente de sincronización corre con permisos mínimos (non-root user en Docker).

## 6. Monitoreo y Observabilidad

### 6.1 Telemetría Diferida

Dado que el sistema opera offline, se implementa un mecanismo de telemetría diferida: las métricas de salud del dispositivo se almacenan localmente en formato JSON y se sincronizan con un servidor central (opcional) cuando el vehículo tiene conectividad WiFi disponible.

### 6.2 Métricas Recolectadas

| **Métrica** | **Frecuencia** | **Umbral de Alerta** | **Acción Automática** |
|------------|----------------|---------------------|----------------------|
| FPS promedio | Cada 60 seg | < 5 FPS durante > 5 min | Log warning + notificar en próxima sync |
| Uso de CPU | Cada 30 seg | > 90% durante > 10 min | Reducir resolución dinámicamente |
| Uso de RAM | Cada 30 seg | > 85% de 2 GB | Forzar garbage collection + log critical |
| Temperatura SoC | Cada 30 seg | > 70°C | Reducir FPS; > 80°C: shutdown graceful |
| Espacio en disco | Cada 5 min | < 15% libre | Activar rotación de archivos anticipada |
| Errores de detección | Cada detección | > 20% tasa de error en 100 frames | Log warning + recargar modelo |
| Health-check del servicio | Cada 60 seg | 2 fallos consecutivos | Reiniciar contenedor automáticamente |
| Versión de software | Cada sync | Versión no coincide con GHCR | Disparar actualización |

### 6.3 Dashboard Local (Futuro v2.0)

En versiones futuras, se implementará un dashboard web local (accesible vía WiFi del vehículo) que mostrará en tiempo real: estado del sistema, últimas detecciones, métricas de salud y log de actualizaciones. Para el MVP (v1.0), la observabilidad se limita a los logs locales y la CLI de consulta implementada en la Fase 4.

## 7. Resumen de Herramientas del Ecosistema

| **Área** | **Herramienta** | **Propósito** |
|---------|-----------------|---------------|
| Gestión de tareas | GitHub Projects (Kanban) | Seguimiento visual del flujo de trabajo |
| Control de versiones | Git + GitHub | Repositorio central, PRs, reviews |
| CI | GitHub Actions (ci.yml) | Lint, tests, coverage, security en cada PR |
| CD | GitHub Actions (release.yml) | Build Docker, sign, publish, release |
| Registro de contenedores | GitHub Container Registry (GHCR) | Almacén de imágenes Docker firmadas |
| Firma de imágenes | Cosign (Sigstore) | Verificación de integridad criptográfica |
| GitOps Edge | Agente custom Python + cron | Sincronización y deploy automático |
| Secretos | GitHub Secrets + SOPS | Gestión segura de credenciales |
| Monitoreo local | psutil + JSON logs + SQLite | Telemetría diferida del dispositivo |
| Changelog | semantic-release / release-please | Generación automática desde Conventional Commits |
