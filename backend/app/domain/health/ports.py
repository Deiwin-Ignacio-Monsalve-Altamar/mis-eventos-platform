from abc import ABC, abstractmethod


class HealthPort(ABC):
    """Contract for health check implementations."""

    @abstractmethod
    def check(self) -> dict[str, str]:
        """Return the health status."""
        raise NotImplementedError
