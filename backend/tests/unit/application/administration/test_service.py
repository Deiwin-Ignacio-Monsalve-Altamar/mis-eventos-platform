"""Verify privileged role transitions and their actor checks."""

from unittest.mock import Mock

import pytest

from app.application.administration.service import AdministrationService
from app.core.exceptions import AuthorizationError, ValidationError
from app.domain.entities.user_account import UserAccount
from app.domain.entities.user_role import UserRole
from app.domain.repositories.user_repository import UserRepository


def test_admin_can_promote_another_account():
    """Delegate a permitted promotion with the target and actor identities."""
    repository = Mock(spec=UserRepository)
    expected = UserAccount("organizer@example.test", "hash", "Alex", "Rivera")
    repository.promote_attendee_to_organizer.return_value = expected
    service = AdministrationService(repository)

    result = service.promote_to_organizer(23, actor_id=7, actor_role=UserRole.ADMIN)

    assert result is expected
    repository.promote_attendee_to_organizer.assert_called_once_with(23)


@pytest.mark.parametrize("role", [UserRole.ATTENDEE, UserRole.ORGANIZER])
def test_non_admin_cannot_promote_users(role):
    """Reject an actor lacking administrator privileges before repository access."""
    repository = Mock(spec=UserRepository)
    service = AdministrationService(repository)

    with pytest.raises(AuthorizationError):
        service.promote_to_organizer(23, actor_id=7, actor_role=role)

    repository.promote_attendee_to_organizer.assert_not_called()


def test_admin_cannot_promote_self():
    """Prevent an administrator from using a target ID equal to their own."""
    repository = Mock(spec=UserRepository)
    service = AdministrationService(repository)

    with pytest.raises(ValidationError):
        service.promote_to_organizer(7, actor_id=7, actor_role=UserRole.ADMIN)

    repository.promote_attendee_to_organizer.assert_not_called()
