from app.main import create_app
from app.observability.logging import get_logger

app = create_app()
logger = get_logger("lifecycle")


if __name__ == "__main__":
    logger.info(
        "Backend HTTP server starting.",
        extra={
            "service": app.config["SERVICE_NAME"],
            "environment": app.config["APP_ENVIRONMENT"],
            "version": app.config["APP_VERSION"],
            "stage": "server_start",
        },
    )
    try:
        app.run(host="0.0.0.0", port=5000)
    except KeyboardInterrupt:
        logger.info("Backend shutdown requested.", extra={"stage": "shutdown"})
    except Exception:
        logger.exception("Backend server failed.", extra={"stage": "server_runtime"})
        raise
    finally:
        logger.info("Backend HTTP server stopped.", extra={"stage": "shutdown"})
