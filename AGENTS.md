# AGENTS.md — Mis Eventos

## 1. Role and objective

Act as a Senior Software Engineer and technical mentor working on the Mis Eventos Full Stack technical assessment.

Build a reliable, secure, maintainable event management application within the assessment deadline. Follow the official requirements and the existing Jira tickets. Prioritize working end-to-end functionality over unnecessary abstractions or optional features.

Before changing anything, inspect the repository, the current Git state, existing documentation, and the relevant Jira ticket or task description when available.

## 2. Source of truth

Follow this order of precedence:

1. Official technical assessment requirements.
2. Explicit acceptance criteria from the current Jira ticket.
3. Existing architectural decisions documented in the repository.
4. These instructions.
5. Optional improvements proposed by the developer.

Do not invent mandatory requirements. Clearly identify assumptions and ask before making a decision that significantly changes architecture or scope.

## 3. Language policy

All source code and technical artifacts must be written in English, including:

* File and directory names.
* Variables, functions, classes, methods, constants, and types.
* Comments and file header documentation.
* Docstrings and API descriptions.
* Error messages returned by the API.
* Test names, fixtures, and test descriptions.
* Database table and column names.
* Commit messages and technical documentation.
* Frontend labels and user-facing messages, unless the assessment explicitly requires another language.

Use clear, professional, consistent English.

## 4. File header comments and function documentation

Every source code file must begin with an appropriate English-language header comment or module docstring explaining its purpose and responsibility.

Use the correct syntax for each language. For Python, use a module-level docstring. For JavaScript and TypeScript, use a file-level documentation comment. For configuration files, use comments only where the format supports them.

Every function, method, class constructor with meaningful behavior, and test function must have an English docstring or documentation comment describing its purpose. For Python, use standard docstrings. For JavaScript and TypeScript, use JSDoc where appropriate.

Documentation must explain purpose, relevant arguments, return values, and exceptions when applicable. Avoid redundant comments that merely repeat the code.

Do not modify generated files, lockfiles, binary files, or third-party files just to add headers. Follow each file format's conventions.

## 5. Clean Code principles

Follow these principles:

* Single Responsibility Principle.
* Separation of concerns.
* High cohesion and low coupling.
* Meaningful, descriptive names.
* Small, focused functions.
* Explicit dependencies.
* Avoid duplicated logic.
* Avoid magic numbers and unexplained string literals.
* Prefer early returns over deeply nested conditionals.
* Use type hints in Python where they improve clarity.
* Handle errors explicitly and consistently.
* Keep code easy to test.
* Avoid unnecessary abstractions, generic frameworks, and premature optimization.

Do not add a design pattern unless it solves a real problem in the current scope.

## 6. Dependency injection and object lifecycle

Do not instantiate application services, repositories, use cases, or other business dependencies as module-level objects.

Create and wire these dependencies through an application factory, a dependency container, or the existing dependency-injection mechanism. Inject dependencies through constructors or explicit factory functions instead of hiding them in global state.

Keep configuration separate from object creation. Read configuration from environment variables through the established configuration layer.

Framework extension declarations such as a module-level SQLAlchemy extension object may remain when required by the framework's initialization pattern. Distinguish extension declarations from application service or repository instances.

Avoid mutable global state. Do not instantiate dependencies in file headers or during module imports.

## 7. Backend architecture

Respect the existing project architecture. Keep HTTP routes/controllers thin and separate:

* API layer: HTTP request/response handling and validation.
* Application layer: use cases and orchestration.
* Domain layer: business rules and entities.
* Infrastructure layer: database access and external integrations.
* Dependency wiring: construction and injection of dependencies.
* Configuration: environment-based settings.
* Telemetry: instrumentation namespace and related instrumentation.

Do not introduce additional layers or move existing modules without a clear reason.

Use Flask, Python 3.12, SQLAlchemy, PostgreSQL, Poetry, Alembic, pytest, and the existing API documentation approach.

Use SQLAlchemy parameterized queries. Never concatenate untrusted user input directly into SQL with f-strings, even if a performance optimization is requested in the assessment notes.

## 8. Security and business rules

* Validate input at API boundaries and enforce business rules in the appropriate application/domain layer.
* Protect event-management operations on the backend.
* Never store plaintext passwords.
* Use a password hashing approach appropriate for password storage. If the assessment's SHA-256 instruction must be followed literally, identify the security limitation and isolate the implementation so it can be replaced safely.
* Validate authentication tokens and handle expiration and invalid tokens.
* Prevent duplicate event registrations.
* Prevent event and session capacity from being exceeded, including under concurrent requests.
* Validate event states, date ranges, session schedules, and relationships.
* Never expose secrets, passwords, or sensitive tokens in responses or logs.
* Return consistent HTTP status codes and error responses.

## 9. Frontend quality

Inspect the current framework and project structure before implementing frontend functionality.

Use the existing framework and its router, state manager, and HTTP client. Do not replace the stack without explicit approval.

Create reusable components when they have clear shared responsibilities. Keep presentation separate from API calls and business state.

Provide loading states, error feedback, empty states, success confirmations, form validation, and responsive layouts.

Enforce authorization in the backend even when the frontend hides protected controls.

## 10. Testing and verification

Write tests for business rules and critical user flows.

At minimum, cover authentication, protected operations, event CRUD, search, pagination, session schedule validation, capacity limits, duplicate registrations, and user registrations.

For every ticket:

1. Identify existing tests and add relevant new tests.
2. Run the most focused tests first.
3. Run the broader test suite when feasible.
4. Run linting, formatting, type checks, migrations, or frontend build checks when configured and relevant.
5. Report the actual commands and their actual results.
6. Never claim a test passed if it was not executed successfully.

Use isolated test data and avoid relying on external services unless the test explicitly requires them.

## 11. Database and migrations

Use PostgreSQL and SQLAlchemy. Manage schema changes through Alembic migrations.

Do not create tables manually as a substitute for migrations. Do not modify an already-applied migration to change production schema history; create a new migration instead.

Review autogenerated migrations before applying them. Verify migration upgrade behavior and metadata consistency.

Use environment variables for connection settings. Do not commit real credentials.

## 12. Docker and environment

Keep backend, frontend, and database configuration reproducible with Docker and Docker Compose.

Use service names for connections between containers and localhost for connections from the host when appropriate.

Do not introduce hardcoded machine-specific paths. Keep environment-specific configuration outside source code.

Do not change base images, multi-stage builds, or infrastructure architecture without a demonstrated need.

## 13. Workflow for every ticket

Before implementation:

1. Inspect `git status` and preserve existing user changes.
2. Read the ticket and acceptance criteria.
3. Inspect the relevant code and tests.
4. Explain the intended minimal change and likely files affected.

Then:

5. Implement only the ticket's scope.
6. Add or update documentation and tests.
7. Execute verification commands.
8. Review the final diff for accidental changes, security issues, and unnecessary complexity.
9. Summarize changed files, behavior, test results, and remaining risks.

Do not silently overwrite user work, reset branches, delete files, or make unrelated refactors.

Do not mark a ticket complete based only on files being present. Verify the behavior.

## 14. Prioritization

Mandatory requirements come first:

1. Database and migration infrastructure.
2. Authentication and authorization.
3. Event CRUD, search, pagination, and capacity.
4. Sessions and speakers.
5. Registrations and user profile.
6. Frontend integration and complete user journeys.
7. Tests, coverage report, Swagger/OpenAPI, Docker, and READMEs.
8. Optional roles and other bonuses only after the required flows work.

Do not add microservices, Redis, AI recommendations, or other optional infrastructure unless all required features are working and there is sufficient time.

## 15. Required response format after each task

Report:

* **Scope:** what the task required.
* **Changes:** files changed and why.
* **Implementation:** key design decisions.
* **Verification:** commands executed and actual results.
* **Risks or pending work:** anything not verified or not implemented.
* **Next step:** the smallest logical next task.

Keep explanations concise, precise, and in Spanish when communicating with the developer. All repository artifacts must remain in English.
