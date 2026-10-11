"""Register explicit operational commands that are not exposed over HTTP."""

import click
from flask import Flask

from app.core.exceptions import NotFoundError, RoleConflictError, ValidationError
from app.dependencies import get_administration_service


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
