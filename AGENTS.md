# Mis Eventos — Development Guide

## Project structure and technology

Mis Eventos is an event management application. The repository is organized into:

- `backend/`: Flask API, application and domain logic, SQLAlchemy persistence, Alembic migrations, observability, and backend tests.
- `frontend/`: React application built with Vite, API clients, UI components, and frontend and Playwright tests.
- `scripts/`: local development and validation helpers.
- `docker-compose.yml`: local backend, frontend, and PostgreSQL services.

The backend uses Python 3.12, Flask, SQLAlchemy, PostgreSQL, Poetry, Alembic, and pytest. The frontend uses Node.js, npm, React, React Router, and Vite. See [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for component-specific setup and behavior.

## Working in the repository

- Read the task requirements and inspect the relevant implementation, tests, and current Git status before editing.
- Follow the existing architecture and conventions. Keep changes within the task's scope; avoid adding layers, dependencies, or abstractions without a concrete need.
- Preserve existing local and in-progress changes. Do not overwrite or revert work unrelated to the task.
- Keep source code, identifiers, comments, and technical documentation in English. User-facing text may follow the language required by the product. Communicate with the project maintainer in Spanish.
- Use descriptive names, focused functions, and type annotations where they improve clarity. Add comments or docstrings when they explain a non-obvious decision, constraint, or public interface; avoid repeating what the code already says.
- Match the formatter and linter configuration in each component rather than introducing new style rules.

## Architecture and implementation

Keep Flask routes focused on HTTP handling, input validation, and response serialization. Put application orchestration and business rules in the existing application and domain modules, and database access in the infrastructure layer. Wire application dependencies through the existing factory or dependency mechanism; do not create business services or repositories as module-level instances. Framework extension objects may follow the framework's initialization pattern.

In the frontend, use the existing React components, router, state management, and API clients. Keep presentation, API communication, and application state responsibilities clear. Provide appropriate loading, error, empty, and success states for user flows.

Use SQLAlchemy's parameterized query mechanisms; never interpolate untrusted input into SQL. Validate input at API boundaries and enforce authorization in the backend, even when the frontend hides restricted actions. Preserve existing API contracts and business rules unless the task requires a verified change.

## Security and configuration

- Never commit real credentials, tokens, personal data, or local `.env` files. Use the checked-in environment templates as examples and keep secrets outside source code.
- Treat `VITE_*` values as public because they are included in the browser bundle.
- Never store plaintext passwords. Follow the password hashing approach required by the assessment and keep its implementation isolated so it can be replaced if requirements change.
- Validate authentication tokens and enforce event, session, and registration permissions and capacity rules on the backend.
- Do not expose secrets, tokens, passwords, or internal traces in API responses or logs.
- Manage schema changes with Alembic. Review generated migrations, do not rewrite migrations already applied to shared environments, and avoid destructive database operations or volume removal unless explicitly required and approved.
- In Docker, use service names for container-to-container connections and `localhost` for connections from the host where appropriate. Keep environment-specific settings outside source code.

## Tests and validation

Add or update tests for changed behavior, including relevant business rules and API or UI contracts. Use isolated test data and mock external services unless a test specifically requires them. Do not remove or weaken tests to make a suite pass.

Run focused checks first, then the relevant broader suites and build or lint checks when feasible. Report the commands actually run and their results; identify checks that could not run and why.

The root `Makefile` provides these common commands:

| Command | Purpose |
| --- | --- |
| `make help` | List available development commands. |
| `make check` | Check required local tools and Compose configuration. |
| `make setup` | Prepare missing environment files from templates and install locked dependencies. |
| `make run` | Build and start Compose services, apply migrations, and check availability. |
| `make status` / `make logs` | Inspect service state or view recent logs. |
| `make migrate` | Apply Alembic migrations after PostgreSQL is ready. |
| `make test-backend` / `make test-frontend` | Run the backend or frontend test suite. |
| `make test-e2e` | Run frontend Playwright tests. |
| `make test` / `make coverage` | Run both test suites and generate reports. |
| `make lint` | Run backend Ruff checks and frontend lint. |
| `make stop` | Stop and remove Compose containers while preserving named volumes. |

See the component READMEs for local, component-specific commands and configuration. Check `make help` if the Makefile changes.

## Git and task completion

Work on the current task branch. Do not discard local changes or use destructive Git operations. Do not commit, push, merge, or rebase unless requested.

Before finishing, review the diff for scope, secrets, and unintended changes, and run `git diff --check`. Summarize the files changed, implementation decisions, verification results, and remaining limitations in Spanish.
