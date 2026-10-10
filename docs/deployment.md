# Production deployment guide

This guide describes a provider-neutral deployment for a static React frontend,
a Flask service, and managed PostgreSQL. No provider is selected in this
repository, so the hosting rules below define the required behavior without
assuming a vendor-specific configuration file.

## Prerequisites

- Python 3.12 or later and Poetry for the backend.
- Node.js 22 or later and npm for the frontend.
- A managed PostgreSQL database with network access from the backend service.
- A static host that supports SPA fallbacks and a same-origin reverse proxy for
  `/api/v1/*`, or an equivalent edge routing feature.
- HTTPS for the public frontend and backend route.

The backend dependency lock is `backend/poetry.lock`; the frontend lock is
`frontend/package-lock.json`. Use the locked installation commands below for
repeatable builds.

## Environment variables

Configure runtime secrets in the backend host's secret/environment settings,
not in source files, build arguments, or frontend variables. Configure the
frontend values as build-time variables in the static host.

| Variable | Component | Required | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | Backend and Alembic | Yes for hosted use | PostgreSQL URL. Use `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE`; percent-encode reserved characters. Add the SSL query parameters required by the database provider. |
| `JWT_SECRET_KEY` | Backend | Yes | Private signing key of at least 32 bytes. Generate a distinct production value and enter it only in the host's secret manager. |
| `APP_ENVIRONMENT` | Backend | Yes for deployment | Set to `production`; production validation requires secure cookies. |
| `JWT_COOKIE_SECURE` | Backend | Yes for deployment | Set to `true` when serving over HTTPS. |
| `JWT_ACCESS_TOKEN_TTL_SECONDS` | Backend | Optional | Positive token lifetime in seconds; default `3600`. |
| `PORT` | Backend server | Platform supplied; default `5000` | Listening port. Gunicorn binds to `0.0.0.0:$PORT`. |
| `WEB_CONCURRENCY` | Backend server | Optional | Gunicorn worker count; default `2`. Set according to the instance memory limit. |
| `APP_VERSION` | Backend and frontend | Optional | Release label for telemetry; default `dev`. |
| `SERVICE_NAME` | Backend | Optional | Service label for logs; default `mis-eventos-backend`. |
| `LOG_LEVEL` | Backend | Optional | Python logging level; default `INFO`. |
| `VITE_API_BASE_URL` | Frontend build | Optional | Public API prefix compiled into the bundle; use `/api/v1` for the same-origin proxy. |
| `VITE_APP_ENVIRONMENT` | Frontend build | Optional | Public telemetry label; default `local`. |
| `VITE_APP_VERSION` | Frontend build | Optional | Public telemetry label; default `dev`. |

The root `.env.example` contains local development values. Do not copy its
database credentials into a hosted service. The `VITE_*` values are public and
must never contain credentials or signing keys.

## Build and configure the static frontend

From `frontend/`:

```sh
npm ci
VITE_API_BASE_URL=/api/v1 VITE_APP_ENVIRONMENT=production npm run build
```

Publish the generated `frontend/dist/` directory. Set `VITE_APP_VERSION` in the
build environment if the deployment pipeline has a release identifier.

Configure the static host in this order:

1. Proxy `/api/v1/*` to the backend service, preserving the path, HTTP method,
   request body, `Cookie` request header, and response `Set-Cookie` header.
   Proxy all API status codes and response headers without rewriting them.
2. Serve existing assets from `dist/` normally.
3. For remaining frontend navigation paths, return `/index.html` with a
   successful status so React Router can render and reload routes such as
   `/profile` and `/my-events`.

Keep the API proxy rule ahead of the SPA fallback so API requests, including
404 responses, are never answered with the frontend HTML document. The Vite
`API_PROXY_TARGET` setting only configures the local development server; it
does not configure this production proxy. No provider-specific rules are
included until a hosting provider is selected.

## Configure and start the backend

Build the backend from the `backend/` directory using Python 3.12 and the
locked Poetry dependencies:

```sh
poetry install --only main --no-root
poetry run alembic upgrade head
poetry run gunicorn --config gunicorn.conf.py 'app.main:create_app()'
```

The production Docker image in `backend/Dockerfile` uses the same Gunicorn
configuration. Gunicorn listens on `0.0.0.0`, reads `PORT` (default `5000`),
logs to stdout/stderr, and uses a 30-second request timeout and graceful
shutdown timeout. `WEB_CONCURRENCY` controls workers. The local `python -m app`
flow remains available and also reads `PORT`; Docker Compose explicitly keeps
that development command.

Before starting, configure all required backend values using the hosting
provider's secret and environment settings. Never put `JWT_SECRET_KEY` or the
database password in a Docker build argument or frontend build variable.

## PostgreSQL and migrations

The application uses SQLAlchemy/Flask-SQLAlchemy, psycopg 3, and Alembic. Use
the `postgresql+psycopg://` scheme in `DATABASE_URL`; a bare
`postgresql://` may select a different driver. Set SSL parameters according to
the selected provider's connection instructions and use its private database
network endpoint when available.

Run `poetry run alembic upgrade head` once as a release/deployment migration
step, with the same `DATABASE_URL` used by the service. Alembic reads that
variable through `backend/app/config.py`; migration scripts are in
`backend/migrations/versions/`. The command is repeatable for an already
up-to-date schema. Do not run migrations concurrently from multiple service
instances.

Before the first migration, take a provider snapshot or export if the database
contains data. For ongoing recovery, enable the provider's automated backups
and document retention and point-in-time recovery limits. A portable logical
backup can be made with `pg_dump --format=custom "$DATABASE_URL"` in a secure
environment. Test restoration into a separate database with `pg_restore` before
relying on it; do not test restoration over the live database. If application
data must move from local PostgreSQL, export and restore it deliberately and
preserve the Alembic version table.

For rollback, redeploy the previous application artifact when a code release
fails. Restore the database only from a verified backup and into a controlled
recovery target. Apply an Alembic downgrade only when the specific migration is
known to be reversible and the recovery plan has been reviewed; otherwise use
a forward fix.

## Health checks and release verification

Configure the backend platform health check to use `/api/v1/ready`. It returns
success only when the signing configuration is valid and the database accepts
a lightweight query. `/api/v1/live` checks process availability without a
database query, and `/api/v1/health` is the existing lightweight health route.
The backend error handlers return JSON errors without internal traces or
connection credentials.

After deployment, verify from the public frontend origin:

- A direct visit and reload of `/events`, `/profile`, and another frontend
  route returns the React application.
- `/api/v1/ready` returns success, and an invalid or unavailable database
  causes readiness to fail without exposing the connection string.
- Registration/login, `GET /api/v1/auth/me`, a protected route, and logout work
  through the same-origin proxy. In browser developer tools, confirm that the
  login response's `Set-Cookie` is retained and the browser sends the cookie on
  the next API request.
- API errors remain API responses and are not replaced by `index.html`.
- The frontend bundle contains no private backend environment values.

Run repository checks before a release from the repository root:

```sh
make test-backend
make test-frontend
make test-e2e
make lint
cd backend && poetry run pytest tests/integration -m integration
```

The production frontend build is `npm run build` from `frontend/`. A hosted
PostgreSQL migration and end-to-end browser check require the configured
provider services and cannot be replaced by the local mocked E2E suite.

## Provider-specific work still required

Select a host and confirm its free-tier runtime, sleep behavior, memory and
request limits, static rewrite/proxy features, TLS termination, secret handling,
database SSL requirements, backup retention, and private networking. This
guide does not claim compatibility with a provider whose current plan and
routing behavior have not been verified.
