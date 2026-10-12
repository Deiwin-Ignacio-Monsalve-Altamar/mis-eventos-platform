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
    assert dev.read_environment_value(tmp_path / ".env", "APP_ENVIRONMENT") == "local"
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
    assert "APP_ENVIRONMENT=local" in before


def test_adds_environment_to_existing_env_without_changing_other_values(
    tmp_path, monkeypatch
):
    configure_paths(tmp_path, monkeypatch)
    original = "JWT_SECRET_KEY=" + "s" * 48 + "\nCUSTOM=value without newline"
    (tmp_path / ".env").write_text(original)

    assert dev.ensure_local_environment()

    updated = (tmp_path / ".env").read_text()
    assert updated == original + "\nAPP_ENVIRONMENT=local\n"
    assert (
        dev.read_environment_value(tmp_path / ".env", "CUSTOM")
        == "value without newline"
    )


def test_rejects_incompatible_environment_without_overwriting_env(
    tmp_path, monkeypatch, capsys
):
    configure_paths(tmp_path, monkeypatch)
    original = "APP_ENVIRONMENT=production\nCUSTOM=value\n"
    (tmp_path / ".env").write_text(original)

    assert not dev.ensure_local_environment()

    assert (tmp_path / ".env").read_text() == original
    assert "change it explicitly to APP_ENVIRONMENT=local" in capsys.readouterr().out


def test_compose_uses_env_file_not_inherited_app_environment(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs["env"])
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setattr(dev.subprocess, "run", fake_run)

    assert dev.run_command(dev.compose_command("config")) == 0
    assert "APP_ENVIRONMENT" not in captured


def test_rejects_short_configured_secret_without_overwriting_it(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    (tmp_path / ".env").write_text("JWT_SECRET_KEY=short\n")

    assert not dev.ensure_local_environment()
    assert dev.read_environment_value(tmp_path / ".env", "JWT_SECRET_KEY") == "short"
    assert dev.read_environment_value(tmp_path / ".env", "APP_ENVIRONMENT") == "local"


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


def test_backend_host_port_is_configurable_without_changing_internal_port():
    compose = (dev.ROOT / "docker-compose.yml").read_text()
    environment_example = (dev.ROOT / ".env.example").read_text()

    assert '"127.0.0.1:${BACKEND_HOST_PORT:-5000}:5000"' in compose
    assert "BACKEND_HOST_PORT=5000" in environment_example
    assert "API_PROXY_TARGET: http://backend:5000" in compose


def test_postgres_host_port_is_configurable_without_changing_internal_port():
    compose = (dev.ROOT / "docker-compose.yml").read_text()
    environment_example = (dev.ROOT / ".env.example").read_text()

    assert '"${POSTGRES_HOST_PORT:-5432}:5432"' in compose
    assert "POSTGRES_HOST_PORT=5432" in environment_example
    assert "@db:5432/" in compose


def test_compose_port_resolves_the_configured_backend_host_port(monkeypatch):
    commands = []

    def fake_command_output(command):
        commands.append(command)
        return 0, "127.0.0.1:5101"

    monkeypatch.setattr(dev, "command_output", fake_command_output)

    assert dev.compose_port("backend") == "http://localhost:5101"
    assert commands[0][-3:] == ["port", "backend", "5000"]


def test_service_readiness_checks_use_the_resolved_backend_url(monkeypatch):
    resolved_ports = {
        "backend": "http://localhost:5101",
        "frontend": "http://localhost:5173",
    }
    probed_urls = []
    monkeypatch.setattr(dev, "compose_port", lambda service: resolved_ports[service])
    monkeypatch.setattr(
        dev,
        "probe_url",
        lambda url: (probed_urls.append(url) is None, "200"),
    )

    assert dev.show_service_urls()
    assert probed_urls == [
        "http://localhost:5101/api/v1/ready",
        "http://localhost:5173",
        "http://localhost:5101/apidocs/",
    ]


def test_failed_compose_migration_prevents_success_message(
    tmp_path, monkeypatch, capsys
):
    configure_paths(tmp_path, monkeypatch)
    (tmp_path / ".env").write_text(
        "JWT_SECRET_KEY=" + "x" * 40 + "\n"
        "APP_ENVIRONMENT=local\nPOSTGRES_DB=events\nPOSTGRES_USER=events\nPOSTGRES_PASSWORD=local\n"
    )
    monkeypatch.setattr(dev, "check_docker_tools", lambda: True)
    monkeypatch.setattr(dev, "run_command", lambda *args, **kwargs: 1)

    assert dev.up() == 1
    output = capsys.readouterr().out
    assert "did not complete successfully" in output
    assert "All configured services are ready." not in output


def test_failed_demo_user_initialization_prevents_ready_message(
    tmp_path, monkeypatch, capsys
):
    configure_paths(tmp_path, monkeypatch)
    (tmp_path / ".env").write_text(
        "JWT_SECRET_KEY=" + "x" * 40 + "\nAPP_ENVIRONMENT=local\n"
        "POSTGRES_DB=events\nPOSTGRES_USER=events\nPOSTGRES_PASSWORD=local\n"
    )
    monkeypatch.setattr(dev, "check_docker_tools", lambda: True)
    calls = iter((0, 1))
    monkeypatch.setattr(dev, "run_command", lambda *args, **kwargs: next(calls))
    monkeypatch.setattr(dev, "wait_for_database", lambda: True)

    assert dev.up() == 1
    output = capsys.readouterr().out
    assert "demo-user initialization failed" in output
    assert "All configured services are ready." not in output
