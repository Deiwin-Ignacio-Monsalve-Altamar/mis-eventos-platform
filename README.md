# Mis Eventos

Aplicación full stack para descubrir y administrar eventos, sesiones y registros. El repositorio contiene una API Flask, una interfaz React/Vite y PostgreSQL. Para desarrollo local se recomienda Docker Compose: Python, Poetry, Node y npm solo se necesitan en el host para `make setup`, pruebas y lint; al ejecutar la aplicación, Compose instala sus dependencias dentro de las imágenes.

## Requisitos

- Git.
- Docker Desktop con Compose v2 en macOS o Windows, o Docker Engine y el plugin Compose en Linux.
- GNU Make y Python 3.12+ para los comandos del repositorio.
- Para `make setup`, pruebas y lint: Poetry 2.x, Node.js 22+ y npm compatible con Node 22.

Comprueba las herramientas desde cualquier terminal:

```sh
git --version
make --version
python3 --version
docker --version
docker compose version
docker info
poetry --version
node --version
npm --version
```

Instala Docker Desktop siguiendo las instrucciones oficiales para [macOS](https://docs.docker.com/desktop/setup/install/mac-install/), [Windows](https://docs.docker.com/desktop/setup/install/windows-install/) o [Linux](https://docs.docker.com/desktop/setup/install/linux/). En Linux también se puede instalar Docker Engine y el plugin de Compose desde la guía oficial de la distribución. Debe estar iniciado el motor de Docker antes de `make run`.

La versión de Python está declarada como `>=3.12,<4.0` en `backend/pyproject.toml`; el backend usa Python 3.12 en su imagen. La imagen frontend usa Node 22 y npm instala desde `frontend/package-lock.json`. Usa Poetry 2.x para respetar el formato del lockfile.

## Clonar y arrancar por primera vez

Ejecuta desde el directorio raíz del repositorio:

```sh
git clone <URL_DEL_REPOSITORIO> mis-eventos-platform
cd mis-eventos-platform
make setup
make run
```

`make setup` crea `.env` y `frontend/.env` únicamente cuando faltan, copiándolos de sus plantillas versionadas. Genera una clave JWT local criptográficamente segura (48 bytes aleatorios) si no existe o está vacía; la escribe solo en el `.env` ignorado por Git, no la imprime y no la vuelve a generar en ejecuciones posteriores. Un valor configurado de menos de 32 bytes causa un error claro y se conserva para que el usuario lo corrija. Los archivos `.env` que ya existen se conservan. Después instala el entorno Poetry con el lockfile y las dependencias npm con `npm ci`.

`make run` vuelve a comprobar/preparar los archivos locales y valida Docker/Compose antes de iniciar servicios. Construye o reutiliza las capas de las imágenes, inicia PostgreSQL, espera su healthcheck `pg_isready`, ejecuta `alembic upgrade head` en el servicio de migración de una sola ejecución, y solo entonces inicia backend y frontend. El proceso falla si la migración falla; no genera revisiones, no borra datos y conserva el volumen `postgres_data`. Se puede volver a ejecutar `make run` después de corregir un fallo.

URLs locales (puertos del `docker-compose.yml`):

- Interfaz: <http://localhost:5173>
- API (estado): <http://localhost:5000/api/v1/health>
- Preparación backend/base de datos: <http://localhost:5000/api/v1/ready>
- Swagger: <http://localhost:5000/apidocs/>
- Especificación OpenAPI: <http://localhost:5000/apispec_1.json>

## Configuración local y servicios externos

La plantilla raíz usa valores locales de desarrollo para PostgreSQL, tiempos de JWT y etiquetas de la aplicación. Compose proporciona las credenciales locales de PostgreSQL en `docker-compose.yml`; no son credenciales de producción. Nunca copies secretos de producción al entorno local. La clave JWT local se genera automáticamente y nunca debe compartirse ni agregarse al repositorio.

Cloudinary es opcional: la configuración de almacenamiento se valida al solicitar la función de imágenes, no durante la creación de la aplicación. El resto de la app puede iniciar sin `CLOUDINARY_URL`; para subir imágenes de eventos, configura una URL de Cloudinary válida localmente en `.env`. No hay credenciales externas ficticias en la plantilla. Si se agrega otro proveedor externo, sus credenciales deben configurarse solo para la funcionalidad que las requiere; las pruebas unitarias usan mocks y no necesitan cuentas reales.

`frontend/.env` solo contiene valores públicos del navegador y el proxy local. No coloques secretos en variables `VITE_*`.

## Comandos diarios

Desde la raíz del repositorio:

```sh
make status       # estado de Compose y endpoints
make logs         # últimas 100 líneas de logs
make migrate      # aplicar migraciones pendientes en la base local ya iniciada
make restart      # reiniciar servicios existentes
make stop         # detener y retirar contenedores; conserva los datos
make help         # lista de targets disponibles
```

`make run` vuelve a aplicar `upgrade head` de forma idempotente al iniciar; `make migrate` es útil cuando se necesita aplicar una migración manualmente en una pila activa. Para trabajar directamente en el backend, desde la raíz se puede usar `cd backend && poetry run alembic upgrade head`; el `.env` raíz se usa automáticamente por Compose, pero Alembic local toma las variables exportadas por el shell o el `DATABASE_URL` por defecto de PostgreSQL en localhost. No ejecutes `revision --autogenerate` como parte del arranque: resérvalo para cambios deliberados de esquema y revisa la migración antes de aplicarla.

Para detener el entorno sin perder datos:

```sh
make stop
```

El volumen nombrado permanece. Restablecer deliberadamente la base de datos es destructivo y separado del flujo normal. Solo después de confirmar que se desea borrar todos los datos locales, ejecuta desde la raíz:

```sh
docker compose down -v
```

No uses ese comando para solucionar errores rutinarios de arranque.

## Pruebas y calidad

Desde la raíz, `make setup` instala las dependencias locales necesarias. Las pruebas unitarias no necesitan Docker, PostgreSQL ni credenciales externas:

```sh
make test-backend
make test-frontend
make test
make lint
```

La compilación frontend también puede ejecutarse en `frontend/`:

```sh
cd frontend
npm run build
```

Pruebas Playwright E2E: instala Chromium una vez con `cd frontend && npx playwright install chromium`, luego ejecuta `npm run test:e2e` desde `frontend/` o `make test-e2e` desde la raíz. Las pruebas de integración del backend, separadas de la suite unitaria, se ejecutan desde la raíz con `cd backend && poetry run pytest tests/integration -m integration`; sus dependencias de infraestructura se simulan y no requieren una base externa.

## Problemas comunes

- **Falta `JWT_SECRET_KEY`:** ejecuta `make setup` o `make run`; ambos preparan el `.env` y generan una clave local. Si el valor existente tiene menos de 32 bytes, corrígelo localmente. No compartas el `.env` ni logs que contengan variables.
- **Alembic no encontrado:** `make setup` instala dependencias del grupo principal de Poetry, donde Alembic está declarado. Para ejecución manual, entra a `backend/` y usa `poetry run alembic ...`.
- **Docker no disponible:** inicia Docker Desktop o el servicio Docker; comprueba `docker info` y `docker compose version`.
- **Puerto ocupado:** libera 5432 (PostgreSQL), 5000 (API) o 5173 (Vite), o cambia deliberadamente el puerto publicado en `docker-compose.yml`; luego vuelve a correr `make run`.
- **Base de datos no disponible:** `make status` y `make logs` muestran estado y diagnóstico. Compose espera el healthcheck real de PostgreSQL antes de migrar.
- **Variables faltantes o inválidas:** `make run` valida `.env` antes de iniciar Compose. Solo las opciones locales se generan automáticamente; no se inventan credenciales para servicios externos.
- **Dependencias incompatibles:** usa Python 3.12+, Poetry 2.x y Node 22+, y vuelve a ejecutar `make setup` para sincronizar con `poetry.lock` y `package-lock.json`.
- **Migración fallida:** `make run` termina con error y no anuncia éxito. Consulta `make logs`, corrige la causa y vuelve a ejecutar `make run`; no borres el volumen como primer paso. Las migraciones se aplican exclusivamente a la base local configurada por Compose.

## Arquitectura y documentación

- `backend/`: API Flask, aplicación/dominio, persistencia SQLAlchemy, Alembic y pruebas pytest.
- `frontend/`: React, React Router, Vite, pruebas Node y Playwright.
- `docker-compose.yml`: PostgreSQL, migración puntual, API y frontend.
- `scripts/dev.py`: automatización de desarrollo y reportes de pruebas.

Consulta también [guía de despliegue](docs/deployment.md), [documentación backend](backend/README.md) y [documentación frontend](frontend/README.md).
