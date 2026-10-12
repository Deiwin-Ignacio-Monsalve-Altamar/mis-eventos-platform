"""Verify guarded, repeatable local demonstration account initialization."""

from types import SimpleNamespace

from flask import Flask

from app import commands
from app.core.security import hash_password, verify_password
from app.domain.entities.user_role import UserRole


class FakeRepository:
    def __init__(self, session):
        self.accounts = {}

    def find_by_email(self, email):
        return self.accounts.get(email)


class FakeAuth:
    def __init__(self, repository):
        self.repository = repository

    def register(self, email, password, first_name, last_name):
        account = SimpleNamespace(
            id=len(self.repository.accounts) + 1,
            email=email,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            role=UserRole.ATTENDEE,
        )
        self.repository.accounts[email] = account
        return account


def make_cli(monkeypatch, environment="local"):
    repository = FakeRepository(None)
    monkeypatch.setattr(
        commands, "SQLAlchemyUserRepository", lambda session: repository
    )
    monkeypatch.setattr(commands.db, "session", None)
    monkeypatch.setattr(commands, "get_auth_service", lambda: FakeAuth(repository))

    def administration_service():
        class Service:
            def bootstrap_first_admin(self, email):
                account = repository.accounts[email]
                account.role = UserRole.ADMIN
                return account

            def promote_to_organizer(self, user_id, actor_id, actor_role):
                account = next(
                    item for item in repository.accounts.values() if item.id == user_id
                )
                account.role = UserRole.ORGANIZER
                return account

        return Service()

    monkeypatch.setattr(commands, "get_administration_service", administration_service)
    app = Flask(__name__)
    app.config["APP_ENVIRONMENT"] = environment
    commands.register_commands(app)
    return app.test_cli_runner(), repository


def test_creates_demo_accounts_with_expected_roles_and_hashed_passwords(monkeypatch):
    runner, repository = make_cli(monkeypatch)

    result = runner.invoke(args=["init-demo-users"], env={"APP_ENVIRONMENT": "local"})

    assert result.exit_code == 0, result.output
    assert {account.role for account in repository.accounts.values()} == set(UserRole)
    for email, password, *_ in commands.DEMO_USERS:
        account = repository.accounts[email]
        assert account.password_hash != password
        assert verify_password(password, account.password_hash)


def test_rerun_is_idempotent(monkeypatch):
    runner, repository = make_cli(monkeypatch)
    assert (
        runner.invoke(
            args=["init-demo-users"], env={"APP_ENVIRONMENT": "local"}
        ).exit_code
        == 0
    )
    original = dict(repository.accounts)

    assert (
        runner.invoke(
            args=["init-demo-users"], env={"APP_ENVIRONMENT": "local"}
        ).exit_code
        == 0
    )
    assert repository.accounts == original
    assert len(repository.accounts) == 3


def test_existing_incompatible_account_is_preserved_and_reported(monkeypatch):
    runner, repository = make_cli(monkeypatch)
    email, *_ = commands.DEMO_USERS[0]
    original = SimpleNamespace(
        id=1,
        email=email,
        password_hash=hash_password("personal-password"),
        first_name="Existing",
        last_name="User",
        role=UserRole.ATTENDEE,
    )
    repository.accounts[email] = original

    result = runner.invoke(args=["init-demo-users"], env={"APP_ENVIRONMENT": "local"})

    assert result.exit_code != 0
    assert "incompatible data" in result.output
    assert repository.accounts[email] is original
    assert original.role is UserRole.ATTENDEE


def test_does_not_create_accounts_outside_local(monkeypatch):
    runner, repository = make_cli(monkeypatch, "production")

    result = runner.invoke(
        args=["init-demo-users"], env={"APP_ENVIRONMENT": "production"}
    )

    assert result.exit_code != 0
    assert "only available" in result.output
    assert repository.accounts == {}


def test_does_not_create_accounts_when_environment_is_unset(monkeypatch):
    runner, repository = make_cli(monkeypatch)

    result = runner.invoke(args=["init-demo-users"], env={})

    assert result.exit_code != 0
    assert repository.accounts == {}


def test_initialization_failure_is_reported(monkeypatch):
    runner, repository = make_cli(monkeypatch)

    def fail_registration(*args):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(
        commands,
        "get_auth_service",
        lambda: SimpleNamespace(register=fail_registration),
    )
    result = runner.invoke(args=["init-demo-users"], env={"APP_ENVIRONMENT": "local"})

    assert result.exit_code != 0
    assert "storage unavailable" in result.output
    assert repository.accounts == {}
