# Changelog

All notable changes to Mis Eventos are documented in this file.

## [Unreleased]

### Authentication and Authorization

#### Added

* Added user registration and login endpoints.
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
* Deferred event creation and editing authorization until event endpoints are implemented.


### Authentication and Authorization

#### Added

* Added user registration and login endpoints.
* Added email validation and duplicate account handling.
* Added token-based authentication with expiration.
* Added authentication tests for registration, login, and unauthorized access.

#### Security

* Added password hashing and credential verification.
* Added HttpOnly authentication cookies.

#### Fixed

* Fixed code formatting and import ordering issues.
* Fixed authentication validation issues identified during testing.

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
