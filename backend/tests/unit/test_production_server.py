"""Exercise production server configuration and an actual WSGI startup."""

import runpy
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
GUNICORN_CONFIG = BACKEND_ROOT / "gunicorn.conf.py"


def test_gunicorn_uses_the_platform_port_and_local_default(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    assert runpy.run_path(str(GUNICORN_CONFIG))["bind"] == "0.0.0.0:5000"

    monkeypatch.setenv("PORT", "8765")
    assert runpy.run_path(str(GUNICORN_CONFIG))["bind"] == "0.0.0.0:8765"


@pytest.mark.parametrize("port", ["0", "65536", "not-a-port"])
def test_gunicorn_rejects_invalid_ports(monkeypatch, port):
    monkeypatch.setenv("PORT", port)
    with pytest.raises(ValueError, match="PORT must be an integer"):
        runpy.run_path(str(GUNICORN_CONFIG))
