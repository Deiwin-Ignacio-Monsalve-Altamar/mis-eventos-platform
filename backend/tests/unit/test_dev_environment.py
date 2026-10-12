"""Tests for safe first run environment preparation."""

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "dev_script", Path(__file__).resolve().parents[3] / "scripts" / "dev.py"
)
dev = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(dev)


def configure_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(dev, "ROOT", tmp_path)
    monkeypatch.setattr(dev, "FRONTEND", tmp_path / "frontend")
    dev.FRONTEND.mkdir()
    (tmp_path / ".env.example").write_text(
        "JWT_SECRET_KEY=\nAPP_ENVIRONMENT=local\n"
        "POSTGRES_DB=events\nPOSTGRES_USER=events\nPOSTGRES_PASSWORD=local\n"
    )
    (dev.FRONTEND / ".env.example").write_text("VITE_API_BASE_URL=/api/v1\n")


def test_creates_env_files_and_random_secret_without_printing_it(
    tmp_path, monkeypatch, capsys
):
    configure_paths(tmp_path, monkeypatch)

    assert dev.ensure_local_environment()

    secret = dev.read_environment_value(tmp_path / ".env", "JWT_SECRET_KEY")
    assert secret is not None and len(secret.encode()) >= 32
    assert (dev.FRONTEND / ".env").exists()
    assert secret not in capsys.readouterr().out


def test_preserves_existing_env_and_secret_on_repeated_setup(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    (tmp_path / ".env").write_text(
        "JWT_SECRET_KEY=" + "x" * 40 + "\nCUSTOM=value\n"
        "POSTGRES_DB=events\nPOSTGRES_USER=events\nPOSTGRES_PASSWORD=local\n"
    )

    assert dev.ensure_local_environment()
    before = (tmp_path / ".env").read_text()
    assert dev.ensure_local_environment()

    assert (tmp_path / ".env").read_text() == before
    assert "CUSTOM=value" in before


def test_rejects_short_configured_secret_without_overwriting_it(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    (tmp_path / ".env").write_text("JWT_SECRET_KEY=short\n")

    assert not dev.ensure_local_environment()
    assert (tmp_path / ".env").read_text() == "JWT_SECRET_KEY=short\n"


def test_allows_compose_database_defaults_when_overrides_are_absent(
    tmp_path, monkeypatch
):
    configure_paths(tmp_path, monkeypatch)
    (tmp_path / ".env").write_text("JWT_SECRET_KEY=" + "x" * 40 + "\n")

    assert dev.ensure_local_environment()


def test_rejects_explicitly_empty_database_override(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    (tmp_path / ".env").write_text(
        "JWT_SECRET_KEY=" + "x" * 40 + "\nPOSTGRES_PASSWORD=\n"
    )

    assert not dev.ensure_local_environment()


def test_rejects_invalid_token_ttl(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    (tmp_path / ".env").write_text(
        "JWT_SECRET_KEY=" + "x" * 40 + "\n"
        "POSTGRES_DB=events\nPOSTGRES_USER=events\nPOSTGRES_PASSWORD=local\n"
        "JWT_ACCESS_TOKEN_TTL_SECONDS=zero\n"
    )

    assert not dev.ensure_local_environment()


def test_compose_orders_database_migrations_and_backend_without_revision_generation():
    compose = (dev.ROOT / "docker-compose.yml").read_text()

    assert "condition: service_healthy" in compose
    assert "condition: service_completed_successfully" in compose
    assert '"upgrade", "head"' in compose
    assert "revision --autogenerate" not in compose


def test_failed_compose_migration_prevents_success_message(
    tmp_path, monkeypatch, capsys
):
    configure_paths(tmp_path, monkeypatch)
    (tmp_path / ".env").write_text(
        "JWT_SECRET_KEY=" + "x" * 40 + "\n"
        "POSTGRES_DB=events\nPOSTGRES_USER=events\nPOSTGRES_PASSWORD=local\n"
    )
    monkeypatch.setattr(dev, "check_docker_tools", lambda: True)
    monkeypatch.setattr(dev, "run_command", lambda *args, **kwargs: 1)

    assert dev.up() == 1
    output = capsys.readouterr().out
    assert "did not complete successfully" in output
    assert "All configured services are ready." not in output
