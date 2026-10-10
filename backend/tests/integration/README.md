# Integration tests

Integration tests combine API routes and application services while mocking repositories and other infrastructure. The WSGI process test additionally starts Gunicorn on an ephemeral loopback port and uses an in-memory SQLite connection for readiness. The suite does not require PostgreSQL, Docker, or external network access. It does not verify PostgreSQL-specific queries, migrations against a live database, constraints, or provider connectivity.

Run them separately from the `backend` directory:

```sh
poetry run pytest tests/integration -m integration
```

The default unit-test command is `poetry run pytest`, configured to collect only `tests/unit`.
