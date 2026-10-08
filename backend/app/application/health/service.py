from app.domain.health.ports import HealthPort


class HealthService:
    """Application service for the health check use case."""

    def __init__(self, health_port: HealthPort):
        self._health_port = health_port

    def check(self) -> dict[str, str]:
        return self._health_port.check()
