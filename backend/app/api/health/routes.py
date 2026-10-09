from flask import Blueprint

from app.application.health.service import HealthService
from app.dependencies import get_health_service

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health_check():
    service: HealthService = get_health_service()

    return service.check(), 200
