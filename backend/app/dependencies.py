from app.application.health.service import HealthService
from app.infrastructure.health.repository import HealthRepository


def get_health_service() -> HealthService:
    health_repository = HealthRepository()

    return HealthService(health_port=health_repository)
