from app.application.health.service import HealthService
from app.domain.health.ports import HealthPort


class FakeHealthPort(HealthPort):
    def check(self) -> dict[str, str]:
        return {"status": "ok"}


def test_health_service_uses_injected_port():
    health_port = FakeHealthPort()
    service = HealthService(health_port=health_port)

    result = service.check()

    assert result == {"status": "ok"}
