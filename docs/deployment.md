# Production deployment guide

This guide describes the production frontend and the provider-neutral
configuration for a static React frontend, a Flask service, and managed
PostgreSQL. The production frontend URL is
<https://mis-eventos-frontend-h2j3.onrender.com/>. The repository does not
specify the public backend URL or its hosting configuration.

## Prerequisites

- Python 3.12 or later and Poetry for the backend.
- Node.js 22 or later and npm for the frontend.
- A managed PostgreSQL database with network access from the backend service.
- A static host that supports SPA fallbacks. For separate frontend and API
  origins, the API must allow the frontend origin and credentialed requests.
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
| `FRONTEND_ORIGIN` | Backend | Required for direct cross-origin browser access | Exact public origin of the frontend, such as `https://events.example.com`, with no path or trailing slash. CORS is disabled when this value is empty. |
| `VITE_API_BASE_URL` | Frontend build | Optional | Public API base compiled into the bundle; use the backend's public URL plus `/api/v1` for separate services, or `/api/v1` when a same-origin proxy exists. |
| `VITE_APP_ENVIRONMENT` | Frontend build | Optional | Public telemetry label; default `local`. |
| `VITE_APP_VERSION` | Frontend build | Optional | Public telemetry label; default `dev`. |
| `CLOUDINARY_URL` | Backend secret | Optional at startup; required for new event image uploads and cleanup of managed Cloudinary images | Cloudinary connection URL in the form `cloudinary://<api_key>:<api_secret>@<cloud_name>`. Store it only in the backend's private environment settings. |

The root `.env.example` contains local development values. Do not copy its
database credentials into a hosted service. The `VITE_*` values are public and
must never contain credentials or signing keys.

### Event image storage and delivery

The current backend integration uploads new event images to Cloudinary, not
Cloudflare R2. Set `CLOUDINARY_URL` from the Cloudinary API credentials in the
backend host's private environment settings. The variable is optional at
application startup. The storage adapter parses and validates it when an image
upload is requested, or when deleting an event that has images managed by this
Cloudinary integration. A missing or malformed value makes those operations
fail with an image-storage error; it does not prevent the API from starting or
serving other operations.

Uploads are converted to WebP and stored under `mis-eventos/events`. Cloudinary
returns both a `public_id` and an HTTPS `secure_url`; the backend persists the
identifier and URL in the event gallery. The URL returned by Cloudinary is used
by the frontend as the image source, so image delivery goes through the URL's
Cloudinary delivery/CDN host. The application has no separate CDN URL or
Cloudflare R2 endpoint setting in this integration.

Some existing gallery records may contain URLs for images previously stored in
Cloudflare R2. The backend preserves and returns those stored URLs, allowing
the browser to request the image from the URL already recorded (including an
R2 custom-domain/CDN URL if that is what the record contains). The current code
does not upload to R2, configure R2 credentials or endpoints, select an R2 CDN,
or migrate/delete legacy R2 objects. No R2 or project-specific CDN variables
are defined by the checked-in implementation. Configure any externally
managed legacy R2 delivery separately; it is not controlled by this backend.

## Build and configure the static frontend

From `frontend/`:

```sh
npm ci
VITE_API_BASE_URL=https://api.example.com/api/v1 VITE_APP_ENVIRONMENT=production npm run build
```

Replace `api.example.com` with the backend's public host before building.

Publish the generated `frontend/dist/` directory. Set `VITE_APP_VERSION` in the
build environment if the deployment pipeline has a release identifier.

For the production frontend at
`https://mis-eventos-frontend-h2j3.onrender.com/`, set `VITE_API_BASE_URL` to
the backend's public HTTPS URL including `/api/v1`, and set
`FRONTEND_ORIGIN=https://mis-eventos-frontend-h2j3.onrender.com` on the backend.
The repository does not provide the backend's public URL; obtain it from the
backend host configuration. The backend allows credentialed
CORS only from that origin and only on `/api/v1/*`. `API_PROXY_TARGET` remains a
Vite development-server setting and does not route production traffic.

Configure the static host to serve existing assets normally and rewrite
remaining frontend navigation paths to `/index.html`, so React Router can
reload routes such as `/profile` and `/my-events`. Browser API requests go
directly to the configured backend URL and do not pass through this SPA
fallback.

The access cookie remains `HttpOnly`, `Secure` in production, and scoped to
`/api/v1`. When `FRONTEND_ORIGIN` is configured and Secure cookies are enabled,
login and logout use `SameSite=None` so the browser can include the cookie on
cross-site requests. Otherwise they retain `SameSite=Lax`. `SameSite=None`
requires HTTPS, and browser settings that block third-party cookies can still
prevent the cookie from being sent. Verify the login response and subsequent
private request in the target browser before treating cross-origin
authentication as confirmed.

For a local or custom test origin, set `FRONTEND_ORIGIN` to exactly one origin,
for example `http://localhost:5173` locally. Never set it to `*` for
credentialed requests.

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
- Verify CORS preflight and allowed-origin behavior. A browser check of login,
  `GET /api/v1/auth/me`, a protected route, and logout is still required; the
  current cookie policy may prevent cross-site authentication on separate
  default Render domains.
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
