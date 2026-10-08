from app.domain.health.ports import HealthPort


class HealthRepository(HealthPort):
    """Infrastructure implementation of the health check port."""

    def check(self) -> dict[str, str]:
        return {"status": "ok"}
