# Integration tests

Integration tests combine API routes and application services while mocking repositories and other infrastructure. They do not initialize SQLAlchemy, create a database, or require PostgreSQL, Docker, or network access. They do not verify actual SQL queries, migrations, constraints, or persistence behavior.

Run them separately from the `backend` directory:

```sh
poetry run pytest tests/integration -m integration
```

The default unit-test command is `poetry run pytest`, configured to collect only `tests/unit`.
