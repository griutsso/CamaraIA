# IA-CAM-SERVICE

**Sistema Inteligente de Camaras para Automoviles**

Sistema de vision artificial offline que se instala a bordo de un vehiculo y procesa el video de las camaras en tiempo real (Edge Computing). Detecta rostros y placas vehiculares de forma automatica sin depender de internet. Toda la inteligencia corre localmente: cero dependencia de red, maxima privacidad y registro forense inmediato.

> **Estado actual:** Fase 1 — Modulo de Captura de Video + deteccion de rostros/placas en pruebas.

---

## Arquitectura

```
app/
├── main.py                  # Punto de entrada (web / headless)
├── configs/
│   └── settings.yaml        # Configuracion del sistema
├── src/
│   ├── core/                # Interfaces, config, eventos, DI container
│   │   ├── interfaces.py    # Contratos abstractos (IVideoSource, IDetector, IStorageBackend)
│   │   ├── config.py        # Dataclasses de configuracion (YAML → Python)
│   │   ├── container.py     # Contenedor de inyeccion de dependencias
│   │   ├── events.py        # Event Bus (pub/sub desacoplado)
│   │   └── logger.py        # Configuracion de logging
│   ├── capture/             # Captura de video
│   │   ├── video_source.py  # WebcamSource, FileSource, RTSPSource
│   │   └── frame_buffer.py  # Cola thread-safe productor-consumidor
│   ├── detection/           # Modulos de IA
│   │   ├── face_detector.py # Deteccion facial (YOLO / MediaPipe / OpenCV DNN)
│   │   ├── plate_detector.py# Deteccion de placas (YOLO + EasyOCR)
│   │   └── object_detector.py # Deteccion de personas y vehiculos
│   ├── pipeline/            # Pipeline unificado de deteccion
│   │   └── detection_pipeline.py  # Consume frames, ejecuta IA, almacena
│   ├── storage/             # Persistencia local
│   │   └── database.py      # SQLite WAL + guardado de imagenes
│   └── web/                 # Interfaz web (Flask + MJPEG)
│       ├── server.py        # API REST + streaming de video
│       ├── state.py         # Estado centralizado thread-safe
│       └── templates/
│           └── index.html   # SPA del dashboard
├── models/                  # Modelos de IA (no versionados, ver seccion Modelos)
├── docker/                  # Dockerfile multi-stage + docker-compose
├── tests/                   # Suite de pruebas (pytest)
├── data/                    # Capturas e imagenes (no versionado)
└── logs/                    # Logs del sistema (no versionado)
```

### Principios de diseno

- **Arquitectura hexagonal** — Interfaces abstractas (`IVideoSource`, `IDetector`, `IStorageBackend`) desacoplan cada modulo.
- **Inyeccion de dependencias** — `ServiceContainer` construye y conecta todos los servicios.
- **Event Bus** — Comunicacion pub/sub entre modulos sin acoplamiento directo.
- **Patron productor-consumidor** — `FrameBuffer` (cola thread-safe) separa captura de procesamiento.
- **Privacy by Design** — Todo el procesamiento es local; los datos nunca abandonan el dispositivo.

---

## Requisitos

### Software

| Componente | Version |
|---|---|
| Python | 3.10+ |
| OpenCV | 4.8+ |
| Sistema Operativo | Linux / macOS / Windows |

### Hardware minimo (desarrollo)

- CPU x86_64 o ARM64
- 8 GB RAM
- Webcam USB o integrada
- GPU opcional (mejora rendimiento con CUDA)

### Hardware objetivo (edge)

- Raspberry Pi 5 (8 GB RAM) o NVIDIA Jetson Orin Nano
- Camara CSI o USB
- microSD 64 GB+ o SSD NVMe

---

## Instalacion

### 1. Clonar el repositorio

```bash
git clone https://github.com/<tu-usuario>/ia-cam-service.git
cd ia-cam-service
```

### 2. Crear entorno virtual

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tu clave de cifrado:
# python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Descargar modelos de IA

Los modelos `.pt` no se incluyen en el repositorio por su tamano. Opciones:

- **Sin modelos externos:** El sistema usa MediaPipe (rostros) y OpenCV DNN como fallback automatico. No requiere descarga.
- **Con modelos YOLO (mejor precision):**
  ```bash
  # Modelo general YOLOv8 nano
  pip install ultralytics
  yolo export model=yolov8n.pt format=pt

  # Copiar a models/
  cp yolov8n.pt models/
  ```

---

## Uso

### Modo Web (recomendado)

```bash
python main.py
# Abre http://localhost:8080 en tu navegador
```

### Modo Headless (sin interfaz)

```bash
python main.py --headless
```

### Opciones

```
python main.py --help

opciones:
  --config, -c PATH    Ruta al archivo de configuracion YAML
  --mode {web,headless}      Modo de ejecucion (default: web)
  --headless           Ejecutar sin interfaz grafica
  --port PORT          Puerto del servidor web (default: 8080)
  --debug              Activar logging en modo DEBUG
```

---

## Configuracion

El archivo `configs/settings.yaml` controla todos los parametros del sistema:

```yaml
camera:
  source: 0              # 0 = webcam, ruta a archivo, o URL RTSP
  width: 0               # 0 = auto-detectar
  height: 0
  fps: 0

detection:
  face_enabled: true
  plate_enabled: true
  confidence_threshold: 0.5

storage:
  database_path: "data/detections.db"
  images_path: "data/captures"
  encryption_enabled: true
  max_storage_mb: 5120
```

---

## Docker

### Build y ejecucion

```bash
cd docker
docker compose up --build
```

### Acceso a la camara del host

El `docker-compose.yml` monta `/dev/video0`. Para otras camaras, editar la seccion `devices`.

---

## Tests

```bash
# Ejecutar toda la suite
pytest tests/ -v

# Con cobertura
pytest tests/ --cov=src --cov-report=html

# Solo un modulo
pytest tests/test_capture.py -v
```

---

## Desarrollo

### Pre-commit hooks

```bash
pre-commit install
pre-commit run --all-files
```

### Estilo de codigo

- **Formateo:** Black (linea maxima 100 caracteres)
- **Imports:** isort (perfil black)
- **Linting:** flake8
- **Tipos:** mypy (modo basico)

### Conventional Commits

Este proyecto usa [Conventional Commits](https://www.conventionalcommits.org/) para mensajes de commit:

```
feat: agregar deteccion de somnolencia
fix: corregir reconexion de camara en macOS
docs: actualizar instrucciones de instalacion
test: agregar tests para PlateDetector
refactor: extraer logica de tracking a clase separada
```

---

## Roadmap

| Fase | Descripcion | Estado |
|---|---|---|
| Fase 0 | Configuracion del entorno y gobernanza | Completa |
| Fase 1 | Modulo de captura de video | **En progreso** |
| Fase 2 | Deteccion de rostros (YOLO-Face) | En pruebas |
| Fase 3 | Deteccion de placas (YOLO + EasyOCR) | En pruebas |
| Fase 4 | Almacenamiento cifrado (SQLite + AES-256) | Parcial |
| Fase 5 | Integracion y optimizacion | Pendiente |
| Fase 6 | Contenedorizacion Docker multi-arch | Parcial |
| Fase 7 | Pipeline GitOps y despliegue edge | Pendiente |

---

## Stack tecnologico

| Area | Tecnologia |
|---|---|
| Lenguaje | Python 3.10+ |
| Vision por computadora | OpenCV 4.x |
| Deteccion de objetos | Ultralytics YOLO v8 |
| Deteccion facial | YOLO-Face / MediaPipe / OpenCV DNN |
| OCR | EasyOCR |
| Base de datos | SQLite 3 (WAL mode) |
| Cifrado | cryptography (AES-256-GCM) |
| UI Web | Flask + MJPEG streaming |
| Contenedores | Docker + Docker Compose |
| CI/CD | GitHub Actions |
| Testing | pytest + pytest-cov |

---

## Licencia

Este proyecto es de uso privado. Consultar con los autores antes de cualquier distribucion.

---

## Contacto

IA-CAM-SERVICE Team — Proyecto en desarrollo activo (Marzo 2026).
