# Changelog

All notable changes to Mis Eventos are documented in this file.

## [Unreleased]

### Added

* Added root Makefile commands for environment checks, dependency setup, Docker Compose lifecycle, migrations, tests, lint, and combined coverage reporting.
* Added `make stop` to stop and remove Compose containers and networks while preserving persistent volumes; `make down` remains an alias.
* Added a local HTML dashboard combining real backend and frontend test and coverage results.
* Documented backend API endpoints with OpenAPI 3.0.3 and enabled interactive Swagger UI for local development.
* Added a shared festive frontend visual system with purple, pink, yellow, lavender, and turquoise accents across events, authentication, profile, and forms.
* Added accessible session availability labels for available, full, pending, and unknown capacity states.

### Changed

* Expanded the README with first-time local setup and service startup instructions; `make run` is the primary startup command and `make up` remains an alias.
* Updated shared buttons, navigation, form controls, cards, feedback, and responsive styling while preserving existing frontend routes and API behavior.
* Documented frontend design tokens, accessibility, responsive conventions, and mocked test practices.


### Session Management

#### Added

* Added event-scoped session CRUD, schedule and capacity validation, speaker assignment, and overlap detection.
* Added service, API, and repository coverage using mocked persistence.
* Added session attendee enrollment linked to event registrations, cancellation, occupancy reporting, and capacity-safe concurrent writes.
* Restricted attendee roster access to the event creator and enrollment changes to the authenticated attendee.
* Added optimistic version checks to event and session updates, with conflict responses that report the current version.
* Serialized session enrollment, cancellation, and capacity changes with PostgreSQL row locks and transactional occupancy checks.
* Added self-service event registration, cancellation, and reactivation; event cancellation now cancels linked active session enrollments atomically.

### Event Registration and Attendee Management

#### Added

* Added registration availability checks for published events starting in the future.
* Added a paginated authenticated endpoint for listing the current user's active and cancelled event registrations with event details.

### Protected Event Management

#### Added

* Added paginated `GET /api/v1/events` with text search, `GET /api/v1/events/<event_id>`, authenticated `POST /api/v1/events`, `PATCH /api/v1/events/<event_id>`, and `DELETE /api/v1/events/<event_id>` endpoints.
* Added nullable event creator attribution and its Alembic migration.
* Added tests for event creation, editing, retrieval, listing, pagination, search, token rejection, validation, and deletion constraints.

#### Security

* Set event creator identity from the validated access token and ignored client-supplied identity fields.
* Prevented deletion of events that still have registrations, sessions, or speakers.

### Authentication and Authorization

#### Added

* Added user registration and login endpoints.
* Added email validation and duplicate account handling.
* Added authentication tests for registration, login, duplicate emails, invalid input, and token validation.
* Added JWT authentication with expiration and HttpOnly cookies.

#### Security

* Added SHA-256 password hashing as required by the technical challenge.
* Added constant-time password hash comparison.
* Documented the security limitations of SHA-256 password hashing.

#### Fixed

* Fixed import ordering and code formatting issues.
* Fixed authentication validation and error handling.

#### Changed

* Updated authentication documentation.

## [Completed]

### Data Models and Migrations

#### Added

* Added SQLAlchemy models for users, events, sessions, speakers, and registrations.
* Added many-to-many relationships for speakers and events, and speakers and sessions.
* Added the initial Alembic migration.
* Added unit tests for database models.

#### Changed

* Updated the database model registry and migration configuration.
* Updated the README with database setup information.

### Database Configuration

#### Added

* Added PostgreSQL configuration through environment variables.
* Added Alembic migration support.
* Added Docker Compose database health checks.
* Added Ruff and pre-commit configuration.

#### Changed

* Updated backend startup to wait for database readiness.
* Updated development instructions in `AGENTS.md`.
