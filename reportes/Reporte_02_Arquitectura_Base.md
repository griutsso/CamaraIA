# IA-CAM-SERVICE

## Reporte de Avance #02

### Arquitectura Base y Código Inicial

3 de Marzo de 2026

**Versión 1.0**

---

## 1. Resumen Ejecutivo

Se ha diseñado e implementado exitosamente la arquitectura base del proyecto IA-CAM-SERVICE, siguiendo los principios SOLID (Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion). La arquitectura incorpora inyección de dependencias, comunicación basada en eventos, y una estructura modular preparada para containerización con Docker. El código inicial proporciona una base sólida y extensible para la integración de detección de rostros, reconocimiento de placas vehiculares, y almacenamiento persistente de datos e imágenes.

---

## 2. Arquitectura del Sistema

### 2.1 Componentes Principales

#### core/

- **interfaces.py**: Define contratos base (IVideoSource, IDetector, IStorageBackend, Detection, BoundingBox, DetectionType)
- **events.py**: Sistema de eventos pub-sub con EventBus para comunicación desacoplada entre componentes
- **config.py**: Gestión centralizada de configuración del sistema (AppConfig, CameraConfig, DetectionConfig)
- **container.py**: Contenedor de inyección de dependencias (ServiceContainer) con resolución automática
- **logger.py**: Sistema de logging estructurado con múltiples niveles

#### capture/

- **video_source.py**: Abstracción base para múltiples fuentes de video (WebcamSource, FileSource, RTSPSource) en un único archivo
- **frame_buffer.py**: Buffer circular de fotogramas con sincronización thread-safe (Queue-based)

#### detection/

- **face_detector.py**: Detector de rostros con soporte para múltiples algoritmos y PersonTracker integrado
- **plate_detector.py**: Detector de placas vehiculares usando YOLO con EasyOCR para OCR
- **object_detector.py**: Detector de objetos genérico (personas, vehículos) via MobileNet SSD
- **Interfaces en core/interfaces.py**: Clases base Detection y BoundingBox para resultados de detección

#### storage/

- **database.py**: Almacenamiento relacional SQLite con Write-Ahead Logging (WAL) en un único archivo
- Transacciones ACID y recuperación ante fallos garantizada
- Persistencia de imágenes con estructura de directorios organizada

#### ui/

- **app.py**: Aplicación principal (CustomTkinter) con tema Dark Mode
- **theme.py**: Definición de tema oscuro
- **components/**: Componentes reutilizables
  - detection_log.py: Registro de detecciones con historial
  - sidebar.py: Navegación lateral
  - status_bar.py: Barra de estado
  - video_panel.py: Panel de reproducción de video en tiempo real
- **views/**: Vistas principales
  - monitor_view.py: Vista de monitoreo
  - settings_view.py: Panel de configuración del sistema

#### web/

- **server.py**: Servidor Flask con streaming MJPEG para acceso remoto a video en vivo
- **templates/index.html**: Interfaz web básica para visualización remota

---

## 3. Estructura de Carpetas

| Ruta | Descripción |
|------|-------------|
| app/ | Raíz del proyecto |
| ├── main.py | Punto de entrada de la aplicación |
| ├── configs/settings.yaml | Configuración centralizada del sistema |
| ├── src/ | Código fuente principal |
| ├── src/__init__.py | Inicializador del paquete |
| ├── src/core/ | Componentes base del sistema |
| │   ├── __init__.py | Inicializador del módulo |
| │   ├── interfaces.py | Contratos e interfaces (IVideoSource, IDetector, IStorageBackend, Detection, BoundingBox, DetectionType) |
| │   ├── config.py | Configuración centralizada (AppConfig, CameraConfig, DetectionConfig) |
| │   ├── container.py | Contenedor de inyección de dependencias (ServiceContainer) |
| │   ├── events.py | Sistema de eventos pub-sub (EventBus) |
| │   └── logger.py | Sistema de logging |
| ├── src/capture/ | Captura de video |
| │   ├── __init__.py | Inicializador del módulo |
| │   ├── video_source.py | Implementación de fuentes de video (WebcamSource, FileSource, RTSPSource) |
| │   └── frame_buffer.py | Buffer circular de fotogramas con sincronización thread-safe |
| ├── src/detection/ | Detección de objetos |
| │   ├── __init__.py | Inicializador del módulo |
| │   ├── face_detector.py | Detector de rostros con PersonTracker |
| │   ├── plate_detector.py | Detector de placas vehiculares con OCR |
| │   └── object_detector.py | Detector de objetos genérico (personas, vehículos) |
| ├── src/storage/ | Almacenamiento de datos |
| │   ├── __init__.py | Inicializador del módulo |
| │   └── database.py | Almacenamiento relacional SQLite con WAL |
| ├── src/ui/ | Interfaz de usuario gráfica |
| │   ├── __init__.py | Inicializador del módulo |
| │   ├── app.py | Aplicación principal (CustomTkinter) |
| │   ├── theme.py | Tema Dark Mode |
| │   ├── components/ | Componentes reutilizables |
| │   │   ├── __init__.py | Inicializador del módulo |
| │   │   ├── detection_log.py | Panel de registro de detecciones |
| │   │   ├── sidebar.py | Barra de navegación lateral |
| │   │   ├── status_bar.py | Barra de estado |
| │   │   └── video_panel.py | Panel de reproducción de video |
| │   └── views/ | Vistas principales |
| │       ├── __init__.py | Inicializador del módulo |
| │       ├── monitor_view.py | Vista de monitoreo en tiempo real |
| │       └── settings_view.py | Vista de configuración |
| ├── src/web/ | Servidor web para streaming |
| │   ├── __init__.py | Inicializador del módulo |
| │   ├── server.py | Servidor Flask con streaming MJPEG |
| │   └── templates/index.html | Plantilla HTML para interfaz web |
| ├── tests/ | Suite de pruebas unitarias |
| │   ├── __init__.py | Inicializador del módulo |
| │   ├── conftest.py | Configuración de pytest |
| │   ├── test_capture.py | Tests de captura de video |
| │   ├── test_core.py | Tests de componentes core |
| │   └── test_storage.py | Tests de almacenamiento |
| ├── docker/ | Configuración de containerización |
| │   ├── Dockerfile | Imagen Docker para la aplicación |
| │   └── docker-compose.yml | Orquestación de contenedores |
| ├── models/.gitkeep | Directorio para modelos entrenados |
| ├── requirements.txt | Dependencias del proyecto |
| ├── test_camera.py | Script de prueba de cámara |
| └── README.md | Documentación del proyecto |

---

## 4. Patrones de Diseño Utilizados

**Strategy**: Diferentes implementaciones de VideoSource (WebcamSource, FileSource, RTSPSource) permiten cambiar el comportamiento en tiempo de ejecución

**Observer / Pub-Sub**: Sistema de eventos desacoplado para comunicación entre componentes mediante EventBus

**Dependency Injection**: ServiceContainer gestiona la creación e inyección de dependencias automáticamente

**Producer-Consumer**: FrameBuffer implementa patrón productor-consumidor para sincronización thread-safe de fotogramas

**Template Method**: Clases base abstractas definen esquema de procesamiento para especializaciones concretas

---

## 5. Diseño de Interfaz de Usuario

La interfaz de usuario ha sido diseñada siguiendo la estética Dark Mode nativa, proporcionando una experiencia visual moderna y accesible. Los componentes se organizan de la siguiente manera:

### 5.1 Componentes de Interfaz

- **Navegación Lateral**: Sidebar colapsable con acceso a módulos principales (Video, Detecciones, Configuración)
- **Panel de Video**: Visualización en tiempo real con overlay de detecciones (cuadros delimitadores, identificadores)
- **Registro de Detecciones**: Tabla interactiva con historial de eventos, filtrado por tipo, fecha y confianza
- **Panel de Configuración**: Controles para ajustar parámetros de detección, fuente de video, y opciones de almacenamiento
- **Tema Dark Mode**: Paleta de colores oscura para reducción de fatiga visual

---

## 6. Suite de Pruebas

Se han implementado pruebas unitarias que cubren los componentes críticos del sistema. El estado actual es: todos los tests pasando exitosamente.

### 6.1 Tests Implementados

- **test_capture.py**: Tests de captura de video desde múltiples fuentes (webcam, archivo, RTSP) y sincronización de fotogramas
- **test_core.py**: Tests de componentes core incluyendo configuración, inyección de dependencias, y sistema de eventos
- **test_storage.py**: Tests de persistencia SQLite, integridad de datos y operaciones transaccionales

**Estado**: 3/3 tests pasando

---

## 7. Próximos Pasos

1. Configurar entorno virtual Python (venv) con dependencias específicas
2. Descargar e integrar modelos entrenados de YOLO (v8 face detection, v8 license plate detection)
3. Implementar demostración de captura de video con prueba en vivo
4. Iniciar integración del detector de rostros con pipeline de detección
5. Configurar almacenamiento de detecciones en base de datos SQLite
6. Refinar UI con feedback de usuarios y optimizar rendimiento
7. Preparar documentación de API REST para acceso a detecciones
8. Configurar pipelines CI/CD para testing automático
9. Crear imagen Docker optimizada y documentación de deployment

---

*Fin del Reporte*
