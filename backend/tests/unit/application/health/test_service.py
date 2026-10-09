"""Verify health service delegation using a mocked health port."""

from unittest.mock import Mock

from app.application.health.service import HealthService
from app.domain.health.ports import HealthPort


def test_health_service_uses_injected_port():
    """Return the result from the health dependency without external access."""
    health_port = Mock(spec=HealthPort)
    health_port.check.return_value = {"status": "ok"}
    service = HealthService(health_port=health_port)

    result = service.check()

    assert result == {"status": "ok"}
    health_port.check.assert_called_once_with()
