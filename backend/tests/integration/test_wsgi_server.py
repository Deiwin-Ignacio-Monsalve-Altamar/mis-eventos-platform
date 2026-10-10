"""Start Gunicorn as a process and verify its health routes over HTTP."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
GUNICORN_CONFIG = BACKEND_ROOT / "gunicorn.conf.py"


@pytest.mark.integration
def test_gunicorn_starts_the_factory_and_serves_health_routes():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENVIRONMENT": "local",
            "DATABASE_URL": "sqlite://",
            "JWT_SECRET_KEY": "deployment-test-key-with-at-least-32-bytes",
            "PORT": str(port),
            "WEB_CONCURRENCY": "1",
        }
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "gunicorn",
            "--config",
            str(GUNICORN_CONFIG),
            "app.main:create_app()",
        ],
        cwd=BACKEND_ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        base_url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(
                    f"Gunicorn exited during startup with status {process.returncode}."
                )
            try:
                with urlopen(f"{base_url}/api/v1/live", timeout=1) as response:
                    if response.status == 200:
                        break
            except (OSError, URLError):
                time.sleep(0.1)
        else:
            pytest.fail(
                "Gunicorn did not become available before the startup deadline."
            )

        for path in ("/api/v1/health", "/api/v1/live", "/api/v1/ready"):
            with urlopen(f"{base_url}{path}", timeout=3) as response:
                assert response.status == 200
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
