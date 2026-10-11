"""Exercise controlled administrator bootstrap against isolated SQLite data."""

import pytest

from app.extensions import db
from app.infrastructure.database.models import User
from app.main import create_app


@pytest.fixture
def cli_app(monkeypatch):
    """Create an isolated application database and an existing attendee account."""
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-signing-key-long-enough-32")
    monkeypatch.setenv("APP_ENVIRONMENT", "test")
    app = create_app()
    with app.app_context():
        db.create_all()
        db.session.add(
            User(
                email="first-admin@example.test",
                password_hash="unused-test-value",
                first_name="First",
                last_name="Admin",
            )
        )
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


def test_bootstrap_command_initializes_existing_user_once(cli_app):
    """Promote the named existing account only on the first bootstrap invocation."""
    runner = cli_app.test_cli_runner()

    first = runner.invoke(args=["bootstrap-admin", "first-admin@example.test"])
    repeated = runner.invoke(args=["bootstrap-admin", "first-admin@example.test"])

    assert first.exit_code == 0
    assert "account ID 1" in first.output
    assert repeated.exit_code != 0
    with cli_app.app_context():
        user = db.session.scalar(db.select(User))
        assert user.role == "ADMIN"


def test_bootstrap_command_rejects_missing_target_without_partial_change(cli_app):
    """Fail closed for an unknown target and leave all users at their current role."""
    result = cli_app.test_cli_runner().invoke(
        args=["bootstrap-admin", "missing@example.test"]
    )

    assert result.exit_code != 0
    with cli_app.app_context():
        user = db.session.scalar(db.select(User))
        assert user.role == "ATTENDEE"


def test_bootstrap_is_cli_only_and_not_registered_as_http_route(cli_app):
    """Expose the controlled bootstrap command only through Flask's CLI registry."""
    assert "bootstrap-admin" in cli_app.cli.commands
    assert all(
        "bootstrap-admin" not in rule.rule for rule in cli_app.url_map.iter_rules()
    )
