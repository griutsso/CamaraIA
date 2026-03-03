# Guia de Contribucion — IA-CAM-SERVICE

## Configuracion del entorno

```bash
# 1. Clonar y crear entorno virtual
git clone https://github.com/<tu-usuario>/ia-cam-service.git
cd ia-cam-service
python3 -m venv venv
source venv/bin/activate

# 2. Instalar dependencias (incluye dev tools)
pip install -r requirements.txt

# 3. Instalar pre-commit hooks
pre-commit install

# 4. Verificar que todo funciona
pytest tests/ -v
```

## Flujo de trabajo con Git

### Ramas

- `main` — Rama estable. Solo se hace merge via PR con CI verde.
- `develop` — Rama de integracion. Los features se mergean aqui primero.
- `feature/<nombre>` — Ramas de trabajo para nuevas funcionalidades.
- `fix/<nombre>` — Ramas de correccion de bugs.

### Proceso

1. Crear rama desde `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/mi-nueva-funcionalidad
   ```

2. Desarrollar con commits frecuentes usando Conventional Commits:
   ```bash
   git commit -m "feat: agregar deteccion de somnolencia"
   git commit -m "test: agregar tests para SleepDetector"
   ```

3. Ejecutar checks antes de push:
   ```bash
   pre-commit run --all-files
   pytest tests/ -v
   ```

4. Crear Pull Request hacia `develop`.

5. El CI debe pasar (lint + tests + build check) antes del merge.

## Conventional Commits

Todos los commits deben seguir el formato:

```
<tipo>: <descripcion corta>

[cuerpo opcional]
```

### Tipos permitidos

| Tipo | Uso |
|---|---|
| `feat` | Nueva funcionalidad |
| `fix` | Correccion de bug |
| `docs` | Cambios en documentacion |
| `style` | Formateo (no cambia logica) |
| `refactor` | Reestructuracion de codigo |
| `test` | Agregar o modificar tests |
| `chore` | Tareas de mantenimiento |
| `ci` | Cambios en CI/CD |
| `perf` | Mejoras de rendimiento |

## Estilo de codigo

- **Formateo:** Black con linea maxima de 100 caracteres
- **Imports:** Ordenados con isort (perfil black)
- **Linting:** flake8 sin errores
- **Type hints:** Obligatorios en funciones publicas
- **Docstrings:** Obligatorios en clases y funciones publicas (formato Google)
- **Idioma del codigo:** Variables y funciones en ingles; docstrings y comentarios en espanol

## Tests

- Todo nuevo modulo debe incluir tests en `tests/`.
- Cobertura minima objetivo: 80%.
- Ejecutar tests: `pytest tests/ -v --cov=src`

## Estructura de un nuevo detector

Para agregar un nuevo modulo de deteccion:

1. Crear clase en `src/detection/` que implemente `IDetector`
2. Registrar en `ServiceContainer.build_default_services()`
3. Agregar configuracion en `settings.yaml`
4. Escribir tests en `tests/`
5. Documentar en el README
