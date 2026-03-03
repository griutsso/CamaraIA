# IA-CAM-SERVICE

## Reporte de Avance #01

Sistema de Visión Artificial Offline para Automóviles

### Metadata del Proyecto

| Campo | Valor |
|-------|-------|
| **Proyecto** | IA-CAM-SERVICE |
| **Fase** | Inicio -- Configuración del entorno |
| **Fecha** | 03 de marzo de 2026 |
| **Versión** | 1.0 |

## 1. Resumen Ejecutivo

Este primer reporte documenta el inicio formal del proyecto IA-CAM-SERVICE, un sistema de visión artificial offline diseñado para operar a bordo de vehículos mediante Edge Computing. El sistema procesará video en tiempo real desde las cámaras del vehículo sin depender de conexión a internet, enfocándose inicialmente en la detección, captura y registro de rostros y placas vehiculares.

En esta fase se estableció la estructura organizativa del proyecto, incluyendo la creación de la carpeta app/ (donde residirá el código fuente) y la carpeta reportes/ (donde se almacenarán los reportes de avance como el presente documento).

## 2. Objetivos de Esta Fase

- Establecer la estructura de carpetas del proyecto.
- Crear el directorio app/ para el código fuente del sistema.
- Crear el directorio reportes/ para la documentación de avances.
- Documentar el estado inicial del proyecto en este primer reporte.

## 3. Estructura del Proyecto

A continuación se detalla la estructura de carpetas establecida para el proyecto:

| Carpeta / Archivo | Descripción |
|-------------------|-------------|
| CamaraIA/ | Carpeta raíz del workspace del proyecto |
| CamaraIA/app/ | Código fuente del sistema de visión artificial |
| CamaraIA/reportes/ | Reportes de avance del proyecto |
| CamaraIA/docs/ | Documentación de planificación (7 documentos existentes) |

## 4. Documentación Existente

El proyecto ya cuenta con los siguientes documentos de planificación en la carpeta docs/:

| Documento | Descripción |
|-----------|-------------|
| 01_Elevator_Pitch.docx | Presentación rápida del concepto del proyecto |
| 02_Project_Charter.docx | Carta constitutiva del proyecto |
| 03_Objetivos_SMART.docx | Definición de objetivos específicos y medibles |
| 04_Fases_del_Proyecto.docx | Desglose de las fases de desarrollo |
| 05_Roadmap_Macro.docx | Hoja de ruta general del proyecto |
| 06_Cronograma_Estimado.docx | Estimación de tiempos por fase |
| 07_Control_y_GitOps.docx | Estrategia de control de versiones y operaciones |

## 5. Actividades Realizadas

### Revisión del proyecto

Se revisó la descripción general del proyecto y la documentación existente en la carpeta docs/.

### Creación de carpeta app/

Se creó el directorio app/ que contendrá todo el código fuente del sistema de visión artificial, incluyendo módulos de detección de rostros, reconocimiento de placas, y el motor principal de procesamiento de video.

### Creación de carpeta reportes/

Se creó el directorio reportes/ destinado a almacenar todos los reportes de avance del proyecto de forma organizada y secuencial.

### Elaboración de Reporte #01

Se redactó el presente documento como registro formal del inicio de la fase de desarrollo del proyecto.

## 6. Próximos Pasos

- Configurar el entorno de desarrollo Python dentro de app/ (virtual environment, dependencias base).
- Implementar el módulo de captura de video desde la cámara de la laptop (fase de pruebas).
- Integrar modelos de IA para detección de rostros (OpenCV / YOLO).
- Integrar modelos de IA para reconocimiento de placas vehiculares (OCR).
- Diseñar la arquitectura modular del sistema para permitir expansión futura.
- Establecer el sistema de logging y almacenamiento de detecciones.

## 7. Notas

Este reporte se irá actualizando conforme avancemos en cada fase del proyecto. Cada reporte posterior se numerará secuencialmente (Reporte #02, #03, etc.) y se almacenará en la carpeta reportes/ para mantener un historial completo del desarrollo.
