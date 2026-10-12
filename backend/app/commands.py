"""Register explicit operational commands that are not exposed over HTTP."""

import os

import click
from flask import Flask, current_app

from app.core.exceptions import (
    NotFoundError,
    RoleConflictError,
    ValidationError,
)
from app.core.security import verify_password
from app.dependencies import get_administration_service, get_auth_service
from app.domain.entities.user_role import UserRole
from app.extensions import db
from app.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)

DEMO_USERS = (
    (
        "admin.demo@mis-eventos.local",
        "DemoAdmin-2026!",
        "Demo",
        "Admin",
        UserRole.ADMIN,
    ),
    (
        "organizer.demo@mis-eventos.local",
        "DemoOrganizer-2026!",
        "Demo",
        "Organizer",
        UserRole.ORGANIZER,
    ),
    (
        "attendee.demo@mis-eventos.local",
        "DemoAttendee-2026!",
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
        for email, password, first_name, last_name, role in DEMO_USERS:
            account = existing[email]
            if account is not None and (
                account.first_name != first_name
                or account.last_name != last_name
                or not verify_password(password, account.password_hash)
                or account.role is not role
            ):
                raise click.ClickException(
                    f"Demo account {email} already exists with incompatible data; "
                    "it was left unchanged."
                )

        auth = get_auth_service()
        try:
            for email, password, first_name, last_name, _ in DEMO_USERS:
                if existing[email] is None:
                    auth.register(email, password, first_name, last_name)
            admin_email = DEMO_USERS[0][0]
            if existing[admin_email] is None:
                admin = get_administration_service().bootstrap_first_admin(admin_email)
            else:
                admin = existing[admin_email]
            organizer_email = DEMO_USERS[1][0]
            if existing[organizer_email] is None:
                organizer = repository.find_by_email(organizer_email)
                assert organizer is not None and organizer.id is not None
                get_administration_service().promote_to_organizer(
                    organizer.id, admin.id, UserRole.ADMIN
                )
        except Exception as error:
            raise click.ClickException(
                f"Demo-user initialization failed: {error}"
            ) from error
        click.echo("Local demo users are initialized.")
