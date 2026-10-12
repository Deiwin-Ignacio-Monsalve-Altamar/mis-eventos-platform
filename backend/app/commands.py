"""Register explicit operational commands that are not exposed over HTTP."""

import os

import click
from flask import Flask, current_app

from app.core.exceptions import (
    NotFoundError,
    RoleConflictError,
    ValidationError,
)
from app.dependencies import get_administration_service, get_auth_service
from app.domain.entities.user_role import UserRole
from app.extensions import db
from app.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)

DEMO_USERS = (
    (
        "admin@mis-eventos.test",
        "admin1234",
        "Demo",
        "Admin",
        UserRole.ADMIN,
    ),
    (
        "organizador@mis-eventos.test",
        "organizador_1234",
        "Demo",
        "Organizer",
        UserRole.ORGANIZER,
    ),
    (
        "asisitidor@mis-eventos.test",
        "asistidor_1234",
        "Demo",
        "Attendee",
        UserRole.ATTENDEE,
    ),
)


def register_commands(app: Flask) -> None:
    """Register the controlled first-administrator bootstrap command."""

    @app.cli.command("bootstrap-admin")
    @click.argument("email")
    def bootstrap_admin(email: str) -> None:
        """Promote an existing account only while no administrator exists."""
        try:
            account = get_administration_service().bootstrap_first_admin(email)
        except (NotFoundError, RoleConflictError, ValidationError) as error:
            raise click.ClickException(str(error)) from error
        click.echo(f"Administrator initialized for account ID {account.id}.")

    @app.cli.command("init-demo-users")
    def init_demo_users() -> None:
        """Create the fixed local evaluation accounts without changing existing accounts."""
        if (
            os.getenv("APP_ENVIRONMENT", "").strip().lower() != "local"
            or current_app.config.get("APP_ENVIRONMENT") != "local"
        ):
            raise click.ClickException(
                "Demo users are only available when APP_ENVIRONMENT=local."
            )

        repository = SQLAlchemyUserRepository(db.session)
        existing = {email: repository.find_by_email(email) for email, *_ in DEMO_USERS}
        for email, _, _, _, role in DEMO_USERS:
            account = existing[email]
            if account is not None and account.role is not role:
                raise click.ClickException(
                    f"Demo account {email} already exists with role "
                    f"{account.role.value}; expected {role.value}. "
                    "The account was left unchanged."
                )

        try:
            admin = repository.find_first_admin()
            auth = get_auth_service()
            admin_email, admin_password, admin_first, admin_last, _ = DEMO_USERS[0]
            if admin is None:
                auth.register(admin_email, admin_password, admin_first, admin_last)
                admin = get_administration_service().bootstrap_first_admin(admin_email)
            organizer_email, organizer_password, organizer_first, organizer_last, _ = (
                DEMO_USERS[1]
            )
            if existing[organizer_email] is None:
                auth.register(
                    organizer_email,
                    organizer_password,
                    organizer_first,
                    organizer_last,
                )
                organizer = repository.find_by_email(organizer_email)
                assert organizer is not None and organizer.id is not None
                assert admin is not None and admin.id is not None
                get_administration_service().promote_to_organizer(
                    organizer.id, admin.id, UserRole.ADMIN
                )
            attendee_email, attendee_password, attendee_first, attendee_last, _ = (
                DEMO_USERS[2]
            )
            if existing[attendee_email] is None:
                auth.register(
                    attendee_email, attendee_password, attendee_first, attendee_last
                )
        except Exception as error:
            raise click.ClickException(
                f"Demo-user initialization failed: {error}"
            ) from error
        click.echo("Local demo users are initialized.")
