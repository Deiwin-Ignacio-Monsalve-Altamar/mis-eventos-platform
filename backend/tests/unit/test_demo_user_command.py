"""Verify guarded, repeatable local demonstration account initialization."""

from types import SimpleNamespace

import pytest
from flask import Flask

from app import commands
from app.core.security import hash_password, verify_password
from app.domain.entities.user_role import UserRole


class FakeRepository:
    def __init__(self, session):
        self.accounts = {}

    def find_by_email(self, email):
        return self.accounts.get(email)

    def find_first_admin(self):
        return next(
            (
                account
                for account in self.accounts.values()
                if account.role is UserRole.ADMIN
            ),
            None,
        )


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
    calls = {"bootstrap": 0, "promote": 0}
    monkeypatch.setattr(
        commands, "SQLAlchemyUserRepository", lambda session: repository
    )
    monkeypatch.setattr(commands.db, "session", None)
    monkeypatch.setattr(commands, "get_auth_service", lambda: FakeAuth(repository))

    def administration_service():
        class Service:
            def bootstrap_first_admin(self, email):
                calls["bootstrap"] += 1
                account = repository.accounts[email]
                account.role = UserRole.ADMIN
                return account

            def promote_to_organizer(self, user_id, actor_id, actor_role):
                calls["promote"] += 1
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
    return app.test_cli_runner(), repository, calls


def add_account(repository, email, role, password="existing-password"):
    account = SimpleNamespace(
        id=len(repository.accounts) + 1,
        email=email,
        password_hash=hash_password(password),
        first_name="Existing",
        last_name="Person",
        role=role,
    )
    repository.accounts[email] = account
    return account


def test_creates_demo_accounts_with_expected_roles_and_hashed_passwords(monkeypatch):
    runner, repository, _ = make_cli(monkeypatch)

    result = runner.invoke(args=["init-demo-users"], env={"APP_ENVIRONMENT": "local"})

    assert result.exit_code == 0, result.output
    assert {account.role for account in repository.accounts.values()} == set(UserRole)
    for email, password, *_ in commands.DEMO_USERS:
        account = repository.accounts[email]
        assert account.password_hash != password
        assert verify_password(password, account.password_hash)


def test_rerun_is_idempotent(monkeypatch):
    runner, repository, _ = make_cli(monkeypatch)
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
    runner, repository, _ = make_cli(monkeypatch)
    email, _, _, _, _ = commands.DEMO_USERS[0]
    original = add_account(repository, email, UserRole.ATTENDEE, "personal-password")

    result = runner.invoke(args=["init-demo-users"], env={"APP_ENVIRONMENT": "local"})

    assert result.exit_code != 0
    assert "expected ADMIN" in result.output
    assert repository.accounts[email] is original
    assert original.role is UserRole.ATTENDEE


@pytest.mark.parametrize(
    ("configured_environment", "process_environment"),
    [
        ("production", "production"),
        ("staging", "staging"),
        ("local", None),
        ("production", "local"),
    ],
)
def test_rejects_unsafe_environment_before_repository_access(
    monkeypatch, configured_environment, process_environment
):
    runner, repository, calls = make_cli(monkeypatch, configured_environment)
    if process_environment is None:
        monkeypatch.delenv("APP_ENVIRONMENT", raising=False)

    def unexpected_repository_access(_session):
        pytest.fail("init-demo-users accessed the user repository before its guard")

    monkeypatch.setattr(
        commands, "SQLAlchemyUserRepository", unexpected_repository_access
    )
    environment = (
        {"APP_ENVIRONMENT": process_environment}
        if process_environment is not None
        else {}
    )

    result = runner.invoke(args=["init-demo-users"], env=environment)

    assert result.exit_code != 0
    assert "only available" in result.output
    assert repository.accounts == {}
    assert calls == {"bootstrap": 0, "promote": 0}


def test_initialization_failure_is_reported(monkeypatch):
    runner, repository, _ = make_cli(monkeypatch)

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


def test_existing_admin_skips_demo_admin_and_creates_missing_roles(monkeypatch):
    runner, repository, calls = make_cli(monkeypatch)
    existing_admin = add_account(
        repository, "existing-admin@example.test", UserRole.ADMIN
    )

    result = runner.invoke(args=["init-demo-users"], env={"APP_ENVIRONMENT": "local"})

    assert result.exit_code == 0, result.output
    assert repository.find_by_email(commands.DEMO_USERS[0][0]) is None
    organizer = repository.find_by_email(commands.DEMO_USERS[1][0])
    attendee = repository.find_by_email(commands.DEMO_USERS[2][0])
    assert organizer.role is UserRole.ORGANIZER
    assert attendee.role is UserRole.ATTENDEE
    assert calls == {"bootstrap": 0, "promote": 1}
    assert repository.find_first_admin() is existing_admin


def test_missing_admin_uses_existing_first_admin_bootstrap(monkeypatch):
    runner, repository, calls = make_cli(monkeypatch)

    result = runner.invoke(args=["init-demo-users"], env={"APP_ENVIRONMENT": "local"})

    assert result.exit_code == 0, result.output
    assert repository.find_by_email(commands.DEMO_USERS[0][0]).role is UserRole.ADMIN
    assert calls == {"bootstrap": 1, "promote": 1}


def test_correct_existing_accounts_are_not_modified(monkeypatch):
    runner, repository, calls = make_cli(monkeypatch)
    originals = []
    for email, _, _, _, role in commands.DEMO_USERS:
        originals.append(add_account(repository, email, role, "keep-my-password"))

    result = runner.invoke(args=["init-demo-users"], env={"APP_ENVIRONMENT": "local"})

    assert result.exit_code == 0, result.output
    assert [repository.accounts[account.email] for account in originals] == originals
    assert all(
        account.password_hash == hash_password("keep-my-password")
        for account in originals
    )
    assert calls == {"bootstrap": 0, "promote": 0}


def test_required_demo_credentials_are_configured_exactly():
    assert [(email, password) for email, password, *_ in commands.DEMO_USERS] == [
        ("admin@mis-eventos.test", "admin1234"),
        ("organizador@mis-eventos.test", "organizador_1234"),
        ("asisitidor@mis-eventos.test", "asistidor_1234"),
    ]
