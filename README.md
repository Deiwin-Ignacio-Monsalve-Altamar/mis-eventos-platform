# Mis Eventos

Full-stack application for discovering and managing events, sessions, and registrations. The repository contains a Flask API, a React/Vite interface, and PostgreSQL. Docker Compose is the recommended local development setup: Python, Poetry, Node, and npm are needed on the host for `make setup`, tests, and linting; Compose installs runtime dependencies in the application images.

## Requirements

- Git.
- Docker Desktop with Compose v2 on macOS or Windows, or Docker Engine and the Compose plugin on Linux.
- GNU Make and Python 3.12+ for repository commands.
- Poetry 2.x, Node.js 22+, and npm compatible with Node 22 for `make setup`, tests, and linting.

Check the tools from any terminal:

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

Install Docker Desktop using the official instructions for [macOS](https://docs.docker.com/desktop/setup/install/mac-install/), [Windows](https://docs.docker.com/desktop/setup/install/windows-install/), or [Linux](https://docs.docker.com/desktop/setup/install/linux/). On Linux, you can also install Docker Engine and the Compose plugin by following the official instructions for your distribution. Start the Docker engine before running `make run`.

The Python version is declared as `>=3.12,<4.0` in `backend/pyproject.toml`; the backend image uses Python 3.12. The frontend image uses Node 22 and npm installs from `frontend/package-lock.json`. Use Poetry 2.x to match the lockfile format.

## Clone and start for the first time

Run these commands from the repository root:

```sh
git clone <REPOSITORY_URL> mis-eventos-platform
cd mis-eventos-platform
make setup
make run
```

`make setup` creates `.env` and `frontend/.env` from their versioned templates only if the files are missing. It generates a cryptographically secure local JWT key (48 random bytes) if the key is missing or empty, writes it only to the Git-ignored root `.env`, does not print it, and does not regenerate it on later runs. A configured key shorter than 32 bytes produces a clear error and is preserved for the developer to fix. Existing environment files are preserved. Setup then installs the Poetry environment from its lockfile and npm dependencies with `npm ci`.

`make run` checks and prepares local files again and validates Docker/Compose before starting services. It builds or reuses image layers, starts PostgreSQL, waits for its `pg_isready` healthcheck, runs `alembic upgrade head` in a one-shot migration service, and only then starts the backend and frontend. Startup fails if migration fails; it does not generate migration revisions or delete data, and it preserves the `postgres_data` volume. You can rerun `make run` after correcting a failure.

Local URLs (ports from `docker-compose.yml`):

- Frontend: <http://localhost:5173>
- API health: <http://localhost:5000/api/v1/health>
- Backend/database readiness: <http://localhost:5000/api/v1/ready>
- Swagger: <http://localhost:5000/apidocs/>
- OpenAPI specification: <http://localhost:5000/apispec_1.json>

## Local configuration and external services

The root template uses local development defaults for PostgreSQL, JWT lifetime, and application labels. Compose provides local PostgreSQL credentials in `docker-compose.yml`; these are not production credentials. Never copy production secrets into a local environment. The local JWT key is generated automatically and must never be shared or committed.

Cloudinary is optional: its storage configuration is validated when the image feature is requested, not when the application is created. The rest of the app can start without `CLOUDINARY_URL`; to upload event images, configure a valid Cloudinary URL locally in `.env`. The template contains no fake external credentials. Any other provider credentials should be configured only for the feature that requires them; unit tests use mocks and do not need real accounts.

`frontend/.env` contains only browser-visible values and the local proxy configuration. Do not put secrets in `VITE_*` variables.

## Creating an Administrator User

The supported mechanism initializes the **first** administrator by promoting an existing account. Normal registration creates an `ATTENDEE`; migrations do not create administrators. The bootstrap command refuses to run if an administrator already exists, and there is no automated recovery command if all administrator accounts are lost.

### Prerequisites

From the repository root, complete `make setup` and `make run`. This starts PostgreSQL, applies migrations, and provides the backend's generated local `JWT_SECRET_KEY`. Keep the backend connected to the intended local database. In production, use the deployment's approved operational access and its production environment; never point a local setup at production or copy production secrets into `.env`.

### Register the account

Open <http://localhost:5173/register> and register the account that will become the first administrator. Registration requires an email, password, first name, and last name. The password must be 8–128 characters. Use a unique account email and a strong password; do not use a default or example password.

If the account already exists, skip registration and use its email. The CLI does not create accounts and does not accept or reset passwords.

### Initialize the first administrator

Run from the repository root after the account is registered and while the local Compose backend is running:

```sh
docker compose exec backend poetry run flask --app app.main:create_app bootstrap-admin admin@example.test
```

Replace `admin@example.test` with the registered account's email. The command checks that the account exists and no administrator has already been initialized, then promotes it in a database transaction. On success it prints `Administrator initialized for account ID <id>.`; the message contains no credentials. If the email is not registered, or an administrator already exists, it reports an error and makes no promotion. Do not rerun it after successful initialization.

### Sign in and verify access

Sign in at <http://localhost:5173/login> with that account's email and password. Verify the profile or authenticated session reports the `ADMIN` role, then open the administrator dashboard at <http://localhost:5173/admin/dashboard>. The corresponding protected API is `GET /api/v1/admin/dashboard`; administrator-only API routes reject accounts without the `ADMIN` role.

### Security and environment differences

Enter the password only in the registration and login forms. Do not put it in command arguments, shell history, `.env`, or logs. The bootstrap command takes only the account email and prints only the account ID. Never share environment files or logs containing credentials.

For local development, use the generated local JWT key and local Compose database. For production, run the same supported Flask CLI command only through an authorized operational session in the production deployment, after confirming that its configured database is the intended production database and that no administrator exists. Follow the production access and change-control process; do not run `docker compose exec` from this local development setup against production. Keep production credentials and signing keys in the deployment's secret-management system, not in the repository or a developer's `.env`.

## Daily commands

Run these commands from the repository root:

```sh
make status       # Compose and endpoint status
make logs         # Latest 100 lines of logs
make migrate      # Apply pending migrations to the already running local database
make restart      # Restart existing services
make stop         # Stop and remove containers; keep data
make help         # List available targets
```

`make run` applies `upgrade head` idempotently at startup; `make migrate` is useful when you need to apply pending migrations to an active stack. To work directly in the backend, run `cd backend && poetry run alembic upgrade head` from the repository root. Compose reads the root `.env` automatically, but local Alembic uses variables exported by the shell or the default PostgreSQL URL pointing to localhost. Do not run `revision --autogenerate` during startup; reserve it for deliberate schema changes and review the migration before applying it.

To stop the environment without losing data:

```sh
make stop
```

The named volume remains. Deliberately resetting the database is destructive and separate from the normal workflow. Only after confirming that you want to delete all local data, run this from the repository root:

```sh
docker compose down -v
```

Do not use that command to troubleshoot routine startup failures.

## Tests and quality

From the repository root, `make setup` installs the local dependencies needed for tests. Unit tests do not require Docker, PostgreSQL, or external credentials:

```sh
make test-backend
make test-frontend
make test
make lint
```

You can also build the frontend from `frontend/`:

```sh
cd frontend
npm run build
```

For Playwright E2E tests, install Chromium once with `cd frontend && npx playwright install chromium`, then run `npm run test:e2e` from `frontend/` or `make test-e2e` from the repository root. The backend integration tests are separate from the unit suite and run from the repository root with `cd backend && poetry run pytest tests/integration -m integration`; their infrastructure dependencies are mocked, so they do not require an external database.

## Common problems

- **Missing `JWT_SECRET_KEY`:** run `make setup` or `make run`; both prepare `.env` and generate a local key. If an existing value is shorter than 32 bytes, correct it locally. Do not share `.env` or logs containing variables.
- **Alembic not found:** `make setup` installs the main Poetry dependencies, which include Alembic. For manual execution, enter `backend/` and use `poetry run alembic ...`.
- **Docker unavailable:** start Docker Desktop or the Docker service; check `docker info` and `docker compose version`.
- **Port already in use:** free port 5432 (PostgreSQL), 5000 (API), or 5173 (Vite), or deliberately change the published port in `docker-compose.yml`; then rerun `make run`.
- **Database unavailable:** `make status` and `make logs` provide status and diagnostics. Compose waits for PostgreSQL's actual healthcheck before migrating.
- **Missing or invalid variables:** `make run` validates `.env` before starting Compose. Only local defaults are generated automatically; external-service credentials are not invented.
- **Incompatible dependencies:** use Python 3.12+, Poetry 2.x, and Node 22+, then rerun `make setup` to synchronize with `poetry.lock` and `package-lock.json`.
- **Migration failed:** `make run` exits with an error and does not report success. Check `make logs`, fix the cause, and rerun `make run`; do not delete the volume as a first step. Migrations apply only to the local database configured for Compose.

## Architecture and documentation

- `backend/`: Flask API, application/domain logic, SQLAlchemy persistence, Alembic, and pytest tests.
- `frontend/`: React, React Router, Vite, Node tests, and Playwright.
- `docker-compose.yml`: PostgreSQL, one-shot migration, API, and frontend.
- `scripts/dev.py`: development automation and test reports.

Also see the [deployment guide](docs/deployment.md), [backend documentation](backend/README.md), and [frontend documentation](frontend/README.md).
