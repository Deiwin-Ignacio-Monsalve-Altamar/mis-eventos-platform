SHELL := /bin/sh
.DEFAULT_GOAL := help

PYTHON ?= python3

.PHONY: help check setup run up status logs migrate test-backend test-frontend test coverage lint stop down restart

help: ## Show available development commands.
	@awk 'BEGIN {FS = ":.*##"; print "Mis Eventos local development commands:"} /^[a-zA-Z_-]+:.*##/ {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check: ## Check required local tools and Docker Compose configuration.
	@command -v $(PYTHON) >/dev/null 2>&1 || { echo "ERROR: Python 3.12+ is required; install it and rerun make check."; exit 1; }
	@$(PYTHON) scripts/dev.py check

setup: ## Copy missing environment templates and install locked dependencies.
	@$(PYTHON) scripts/dev.py setup

run: ## Build, start, migrate, and verify all Compose services.
	@$(PYTHON) scripts/dev.py up

up: run ## Alias for make run.

status: ## Show container state and probe configured application endpoints.
	@$(PYTHON) scripts/dev.py status

logs: ## Show the latest logs from all Compose services.
	@$(PYTHON) scripts/dev.py logs

migrate: ## Wait for PostgreSQL and apply the existing Alembic migrations.
	@$(PYTHON) scripts/dev.py migrate

test-backend: ## Run backend pytest with line and branch coverage reports.
	@$(PYTHON) scripts/dev.py test-backend

test-frontend: ## Run frontend Node tests with native coverage reporting.
	@$(PYTHON) scripts/dev.py test-frontend

test: ## Run both test suites and create a combined HTML report.
	@$(PYTHON) scripts/dev.py test

coverage: ## Run both suites and generate detailed coverage artifacts and charts.
	@$(PYTHON) scripts/dev.py coverage

lint: ## Run backend Ruff checks and the frontend lint script.
	@$(PYTHON) scripts/dev.py lint

stop: ## Stop and remove Compose containers while preserving named volumes.
	@$(PYTHON) scripts/dev.py down

down: stop ## Alias for make stop.

restart: ## Restart running Compose services and verify their health.
	@$(PYTHON) scripts/dev.py restart

