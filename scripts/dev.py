"""Run safe local development commands and create combined test reports."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
REPORTS = ROOT / "reports" / "coverage"
COMPOSE = ("docker", "compose")
SERVICE_PORTS = {"backend": 5000, "frontend": 5173}
WAIT_TIMEOUT_SECONDS = 90


def command_output(command: list[str], cwd: Path = ROOT) -> tuple[int, str]:
    """Run a command quietly and return its exit code and combined output."""
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        return 127, str(error)
    return result.returncode, "\n".join(
        part for part in (result.stdout, result.stderr) if part
    )


def run_command(command: list[str], cwd: Path = ROOT) -> int:
    """Run a command with live output and return its exit code."""
    print(f"\n$ {' '.join(command)}", flush=True)
    try:
        return subprocess.run(command, cwd=cwd, check=False).returncode
    except OSError as error:
        print(f"ERROR: unable to start command: {error}", file=sys.stderr)
        return 127


def stream_command(command: list[str], cwd: Path) -> tuple[int, str]:
    """Stream command output while retaining it for machine-readable summaries."""
    print(f"\n$ {' '.join(command)}", flush=True)
    output: list[str] = []
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as error:
        message = f"ERROR: unable to start command: {error}"
        print(message, file=sys.stderr)
        return 127, message

    assert process.stdout is not None
    for line in process.stdout:
        output.append(line)
        print(line, end="", flush=True)
    return process.wait(), "".join(output)


def compose_command(*arguments: str) -> list[str]:
    """Build a Docker Compose command using the repository configuration."""
    return [*COMPOSE, *arguments]


def check_tool(name: str, version_arguments: tuple[str, ...] = ("--version",)) -> bool:
    """Verify a required executable exists and can report its version."""
    executable = shutil.which(name)
    if executable is None:
        print(f"ERROR: {name} is not installed or is not on PATH.")
        install_guidance = {
            "docker": "Install Docker Desktop (with Compose) or Docker Engine with its Compose plugin.",
            "make": "Install GNU Make using your operating system's package manager.",
            "node": "Install Node.js 22 or newer from https://nodejs.org/.",
            "npm": "Install npm with Node.js 22 or newer from https://nodejs.org/.",
            "poetry": "Install Poetry using https://python-poetry.org/docs/#installation.",
        }
        if name in install_guidance:
            print(f"Install guidance: {install_guidance[name]}")
        return False
    code, output = command_output([executable, *version_arguments])
    if code != 0:
        print(f"ERROR: {name} could not be started successfully: {output.strip()}")
        return False
    first_line = output.splitlines()[0] if output.splitlines() else "available"
    print(f"OK: {name}: {first_line}")
    return True


def check_python_version() -> bool:
    """Require the host Python version declared by the backend project."""
    version = sys.version_info
    if version < (3, 12):
        print(
            f"ERROR: Python 3.12 or newer is required; found {version.major}.{version.minor}."
        )
        return False
    print(f"OK: Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_node_version() -> bool:
    """Require Node.js 22 or newer, matching the frontend container runtime."""
    code, output = command_output(["node", "--version"])
    match = re.search(r"v?(\d+)\.(\d+)\.(\d+)", output)
    if code != 0 or match is None:
        print("ERROR: unable to determine the installed Node.js version.")
        print("Install Node.js 22 or newer from https://nodejs.org/.")
        return False
    version = tuple(int(part) for part in match.groups())
    if version < (22, 0, 0):
        print(f"ERROR: Node.js 22 or newer is required; found {output.strip()}.")
        return False
    print(f"OK: Node.js {output.strip()}")
    return True


def check_docker_configuration() -> bool:
    """Validate the Compose file without printing resolved environment values."""
    code, output = command_output(compose_command("config", "--quiet"))
    if code != 0:
        print("ERROR: Docker Compose configuration is invalid.")
        if output.strip():
            print(output.strip())
        print(
            "Check .env against .env.example; do not paste secrets into the terminal output."
        )
        return False
    print("OK: docker-compose.yml and its required local environment values are valid.")
    return True


def check_tools(require_docker: bool = True) -> bool:
    """Check local language tools and optionally the Docker engine and Compose."""
    checks = [
        check_python_version(),
        check_tool("poetry"),
        check_node_version(),
        check_tool("npm"),
    ]
    if require_docker:
        checks.extend(
            [
                check_tool("make"),
                check_tool("docker"),
                check_tool("docker", ("compose", "version")),
            ]
        )
        code, output = command_output(
            ["docker", "info", "--format", "{{.ServerVersion}}"]
        )
        if code == 0:
            print(f"OK: Docker engine: {output.strip()}")
        else:
            print("ERROR: Docker is installed but its engine is unavailable.")
            if output.strip():
                print(output.strip())
            checks.append(False)
        checks.append(check_docker_configuration())
    return all(checks)


def read_environment_value(path: Path, key: str) -> str | None:
    """Read a single dotenv value without displaying its contents."""
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() == key:
            return value.strip().strip("\"'")
    return None


def install_dependencies() -> bool:
    """Install dependencies using Poetry and the checked-in npm lockfile."""
    poetry_command = [
        "poetry",
        "install",
        "--with",
        "dev",
        "--no-interaction",
        "--no-root",
    ]
    if run_command(poetry_command, BACKEND):
        print("ERROR: backend dependency installation failed (Poetry --no-root).")
        return False
    if run_command(["npm", "ci"], FRONTEND):
        print("ERROR: frontend dependency installation failed (npm ci).")
        return False
    return True


def setup() -> int:
    """Prepare missing local environment files and install locked dependencies."""
    if not check_tools(require_docker=False):
        print("Install the missing tool and rerun make setup.")
        return 1

    templates = (
        (ROOT / ".env.example", ROOT / ".env"),
        (FRONTEND / ".env.example", FRONTEND / ".env"),
    )
    for template, destination in templates:
        if destination.exists():
            print(f"Preserving existing {destination.relative_to(ROOT)}.")
        elif template.exists():
            shutil.copyfile(template, destination)
            print(f"Created {destination.relative_to(ROOT)} from its example template.")
        else:
            print(
                f"ERROR: expected template {template.relative_to(ROOT)} was not found."
            )
            return 1

    signing_key = read_environment_value(ROOT / ".env", "JWT_SECRET_KEY")
    if signing_key is None or len(signing_key.encode("utf-8")) < 32:
        print(
            "ACTION REQUIRED: set JWT_SECRET_KEY in the root .env file (at least 32 bytes)."
        )
        print(
            "Generate a local value with: python3 -c 'import secrets; print(secrets.token_urlsafe(48))'"
        )
        print(
            "The generated value is not written automatically; keep it private and do not commit .env."
        )

    if not install_dependencies():
        print("ERROR: make setup did not complete. Review the failed command above and retry.")
        return 1
    print("Setup completed. Run make check, then make run.")
    return 0


def compose_port(service: str) -> str | None:
    """Resolve a service's published HTTP URL from Docker Compose port mapping."""
    internal_port = SERVICE_PORTS[service]
    code, output = command_output(compose_command("port", service, str(internal_port)))
    if code != 0 or not output.strip():
        return None
    published = output.splitlines()[0].strip()
    host_port = published.rsplit(":", 1)[-1]
    if not host_port.isdigit():
        return None
    return f"http://localhost:{host_port}"


def wait_for_database() -> bool:
    """Wait for the configured PostgreSQL Compose health check to pass."""
    print("Waiting for PostgreSQL health check…")
    command = compose_command(
        "exec",
        "-T",
        "db",
        "sh",
        "-c",
        'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
    )
    deadline = time.monotonic() + WAIT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        code, _ = command_output(command)
        if code == 0:
            print("OK: PostgreSQL accepts connections.")
            return True
        time.sleep(2)
    print("ERROR: PostgreSQL did not become ready within 90 seconds.")
    return False


def probe_url(url: str, expected_status: int | None = None) -> tuple[bool, str]:
    """Probe an HTTP endpoint and return a sanitized status description."""
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            status = response.status
    except (urllib.error.URLError, TimeoutError) as error:
        return False, str(
            error.reason if isinstance(error, urllib.error.URLError) else error
        )
    valid = expected_status is None or status == expected_status
    return valid, f"HTTP {status}"


def wait_for_url(url: str, label: str) -> bool:
    """Wait for a local service URL to return a successful HTTP response."""
    deadline = time.monotonic() + WAIT_TIMEOUT_SECONDS
    last_error = "not reachable yet"
    while time.monotonic() < deadline:
        ready, last_error = probe_url(url)
        if ready:
            print(f"OK: {label}: {url} ({last_error})")
            return True
        time.sleep(2)
    print(f"ERROR: {label} failed to become ready at {url}: {last_error}")
    return False


def migrate() -> int:
    """Wait for PostgreSQL, then apply the repository's Alembic migrations."""
    if not wait_for_database():
        return 1
    code, output = command_output(
        compose_command("ps", "--status", "running", "--services")
    )
    if code != 0 or "backend" not in output.split():
        print(
            "ERROR: backend container is not running; run make up before make migrate."
        )
        return 1
    code = run_command(
        compose_command(
            "exec", "-T", "backend", "poetry", "run", "alembic", "upgrade", "head"
        )
    )
    if code != 0:
        print("ERROR: Alembic upgrade head failed; inspect with make logs.")
        return code
    print("OK: Alembic migrations are current.")
    return 0


def show_service_urls() -> bool:
    """Print configured local service URLs and verify API and UI endpoints."""
    frontend_url = compose_port("frontend")
    backend_url = compose_port("backend")
    if frontend_url is None or backend_url is None:
        print("ERROR: unable to resolve the frontend/backend Compose port mappings.")
        return False
    health_url = f"{backend_url}/api/v1/health"
    docs_url = f"{backend_url}/apidocs/"
    all_ready = True
    for url, label in (
        (health_url, "Backend health"),
        (frontend_url, "Frontend"),
        (docs_url, "API documentation"),
    ):
        ready, detail = probe_url(url)
        print(f"{'OK' if ready else 'ERROR'}: {label}: {url} ({detail})")
        all_ready = all_ready and ready
    return all_ready


def diagnose_failure(step: str) -> None:
    """Give concise diagnostic commands without dumping environment secrets."""
    print(f"ERROR: {step} did not complete successfully.")
    print(
        "Diagnose with: make status and make logs. Check required values in .env privately."
    )


def up() -> int:
    """Build, start, migrate, and probe every configured Compose application service."""
    if not check_tools(require_docker=True):
        diagnose_failure("environment checks")
        return 1
    print("Preparing the db, backend, and frontend services from docker-compose.yml…")
    code = run_command(compose_command("up", "--build", "-d"))
    if code != 0:
        diagnose_failure("docker compose up --build -d")
        return code
    if not wait_for_database():
        diagnose_failure("database startup")
        return 1
    if migrate() != 0:
        diagnose_failure("database migration")
        return 1
    deadline = time.monotonic() + WAIT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if show_service_urls():
            print("All configured services are ready.")
            return 0
        time.sleep(2)
    diagnose_failure("frontend, backend, or API documentation health probe")
    return 1


def status() -> int:
    """Show Compose container health and probe the frontend, API, and docs."""
    code = run_command(compose_command("ps"))
    if code != 0:
        diagnose_failure("docker compose ps")
        return code
    database_command = compose_command(
        "exec",
        "-T",
        "db",
        "sh",
        "-c",
        'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
    )
    database_code, _ = command_output(database_command)
    database_ready = database_code == 0
    print(f"{'OK' if database_ready else 'ERROR'}: PostgreSQL health check.")
    applications_ready = show_service_urls()
    if not database_ready or not applications_ready:
        print("One or more services are not ready; inspect make logs for details.")
        return 1
    print("All configured services report ready.")
    return 0


def logs() -> int:
    """Display recent logs for all Compose services without following indefinitely."""
    return run_command(compose_command("logs", "--tail=100"))


def stop() -> int:
    """Stop and remove Compose containers while retaining named database volumes."""
    code = run_command(compose_command("down"))
    if code == 0:
        print("Compose services stopped. Persistent named volumes were retained.")
    else:
        diagnose_failure("docker compose down")
    return code


def restart() -> int:
    """Restart existing Compose services and verify their HTTP endpoints."""
    code = run_command(compose_command("restart"))
    if code != 0:
        diagnose_failure("docker compose restart")
        return code
    if wait_for_database() and show_service_urls():
        print("All configured services restarted successfully.")
        return 0
    diagnose_failure("service restart health checks")
    return 1


def parse_junit(path: Path, coverage_path: Path, exit_code: int) -> dict[str, Any]:
    """Read pytest's JUnit report and normalize test and coverage counters."""
    summary: dict[str, Any] = {
        "status": "passed" if exit_code == 0 else "failed",
        "tests": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "line_coverage": None,
        "branch_coverage": None,
        "files": [],
    }
    if path.exists():
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError) as error:
            print(f"ERROR: could not parse the current pytest report: {error}")
            summary["errors"] = 1
        else:
            cases = list(root.iter("testcase"))
            summary["tests"] = len(cases)
            summary["failed"] = sum(case.find("failure") is not None for case in cases)
            summary["errors"] = sum(case.find("error") is not None for case in cases)
            summary["skipped"] = sum(case.find("skipped") is not None for case in cases)
            summary["passed"] = max(
                summary["tests"]
                - summary["failed"]
                - summary["errors"]
                - summary["skipped"],
                0,
            )
    if summary["tests"] == 0 and exit_code != 0:
        summary["errors"] = 1
    if coverage_path.exists():
        try:
            coverage = ET.parse(coverage_path).getroot()
        except (ET.ParseError, OSError) as error:
            print(f"ERROR: could not parse the current coverage report: {error}")
            summary["errors"] += 1
        else:
            summary["line_coverage"] = float(coverage.attrib["line-rate"]) * 100
            if "branch-rate" in coverage.attrib:
                summary["branch_coverage"] = float(coverage.attrib["branch-rate"]) * 100
            classes = coverage.findall(".//class")
            files = []
            for row in classes:
                uncovered_lines = [
                    line.attrib["number"]
                    for line in row.findall(".//line")
                    if line.attrib.get("hits") == "0"
                ]
                files.append(
                    {
                        "name": row.attrib.get("filename", "unknown"),
                        "coverage": float(row.attrib.get("line-rate", "0")) * 100,
                        "uncovered": ", ".join(uncovered_lines),
                    }
                )
            summary["files"] = sorted(files, key=lambda item: item["coverage"])[:10]
    if exit_code != 0 or summary["errors"]:
        summary["status"] = "failed"
    return summary


def parse_node_summary(output: str, exit_code: int) -> dict[str, Any]:
    """Parse TAP totals and native Node coverage output for the frontend suite."""
    values = {
        key: _tap_count(output, key)
        for key in ("tests", "pass", "fail", "cancelled", "skipped", "todo")
    }
    has_summary = values["tests"] is not None
    tests = values["tests"] or 0
    failed = values["fail"] or 0
    skipped = values["skipped"] or 0
    errors = (values["cancelled"] or 0) + (
        1 if not has_summary and exit_code != 0 else 0
    )
    summary: dict[str, Any] = {
        "status": "passed" if exit_code == 0 and has_summary else "failed",
        "tests": tests,
        "passed": values["pass"] or 0,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "line_coverage": None,
        "branch_coverage": None,
        "function_coverage": None,
        "files": [],
    }
    directories: dict[int, str] = {}
    for line in output.splitlines():
        if "|" not in line or "coverage report" in line or "---" in line:
            continue
        raw_fields = line.removeprefix("# ").split("|")
        raw_name = raw_fields[0]
        depth = len(raw_name) - len(raw_name.lstrip())
        fields = [field.strip() for field in raw_fields]
        if len(fields) < 5:
            continue
        file_name, line_percent, branch_percent, function_percent, uncovered = fields[
            :5
        ]
        if file_name == "all files":
            summary["line_coverage"] = _percentage(line_percent)
            summary["branch_coverage"] = _percentage(branch_percent)
            summary["function_coverage"] = _percentage(function_percent)
        elif file_name and _percentage(line_percent) is not None:
            parents = [
                directories[index] for index in sorted(directories) if index < depth
            ]
            relative_name = "/".join([*parents, file_name])
            summary["files"].append(
                {
                    "name": relative_name,
                    "coverage": _percentage(line_percent),
                    "branches": _percentage(branch_percent),
                    "functions": _percentage(function_percent),
                    "uncovered": uncovered,
                }
            )
        elif file_name:
            directories = {
                index: directory
                for index, directory in directories.items()
                if index < depth
            }
            directories[depth] = file_name
    summary["files"] = sorted(summary["files"], key=lambda item: item["coverage"])[:10]
    if exit_code != 0:
        summary["status"] = "failed"
    return summary


def _tap_count(output: str, key: str) -> int | None:
    """Return the final TAP summary count for one test outcome category."""
    matches = re.findall(rf"^# {re.escape(key)} (\d+)\s*$", output, flags=re.MULTILINE)
    return int(matches[-1]) if matches else None


def _percentage(value: str) -> float | None:
    """Parse a coverage percentage while preserving unavailable measurements."""
    try:
        return float(value.strip().rstrip("%"))
    except (ValueError, AttributeError):
        return None


def run_backend_tests() -> tuple[int, dict[str, Any]]:
    """Run pytest with line/branch coverage, JUnit, XML, and HTML artifacts."""
    artifact_dir = REPORTS / "backend"
    run_id = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    html_dir = artifact_dir / f"htmlcov-{run_id}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    junit_path = artifact_dir / f"junit-{run_id}.xml"
    coverage_xml = artifact_dir / f"coverage-{run_id}.xml"
    command = [
        "poetry",
        "run",
        "python",
        "-m",
        "pytest",
        "--cov=app",
        "--cov-branch",
        "--cov-report=term-missing",
        f"--cov-report=xml:{coverage_xml}",
        f"--cov-report=html:{html_dir}",
        f"--junitxml={junit_path}",
    ]
    environment = os.environ.copy()
    environment["COVERAGE_FILE"] = str(artifact_dir / f".coverage-{run_id}")
    code, _ = stream_command_with_environment(command, BACKEND, environment)
    summary = parse_junit(junit_path, coverage_xml, code)
    summary["html_report"] = str(html_dir / "index.html") if html_dir.exists() else None
    return code, summary


def stream_command_with_environment(
    command: list[str], cwd: Path, environment: dict[str, str]
) -> tuple[int, str]:
    """Stream a command with a controlled environment and retain all output."""
    print(f"\n$ {' '.join(command)}", flush=True)
    output: list[str] = []
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as error:
        message = f"ERROR: unable to start command: {error}"
        print(message, file=sys.stderr)
        return 127, message
    assert process.stdout is not None
    for line in process.stdout:
        output.append(line)
        print(line, end="", flush=True)
    return process.wait(), "".join(output)


def run_frontend_tests() -> tuple[int, dict[str, Any]]:
    """Run Node's built-in tests and experimental line/branch/function coverage."""
    command = ["node", "--test", "--experimental-test-coverage", "--test-reporter=tap"]
    code, output = stream_command(command, FRONTEND)
    return code, parse_node_summary(output, code)


def render_bar(value: float | None, maximum: float, color: str) -> str:
    """Render a labeled SVG bar without substituting missing measurements."""
    if value is None:
        return '<span class="unavailable">No disponible</span>'
    width = 0 if maximum <= 0 else max(0, min(100, value / maximum * 100))
    return (
        f'<div class="bar-track"><div class="bar-fill" style="width:{width:.2f}%;'
        f'background:{color}"></div></div><span>{value:.2f}%</span>'
    )


def render_file_table(suites: dict[str, dict[str, Any]]) -> str:
    """Render the lowest-coverage backend and frontend files from current reports."""
    rows: list[str] = []
    for suite_name, suite in suites.items():
        for item in suite.get("files", []):
            coverage = item.get("coverage")
            if coverage is None:
                continue
            details = html.escape(str(item.get("uncovered", "")))
            rows.append(
                "<tr>"
                f"<td>{html.escape(suite_name)}</td>"
                f"<td>{html.escape(str(item.get('name', 'unknown')))}</td>"
                f"<td>{coverage:.2f}%</td>"
                f"<td>{details or '—'}</td></tr>"
            )
    if not rows:
        return '<p class="muted">No hay datos de archivos para esta ejecución.</p>'
    return (
        "<table><thead><tr><th>Suite</th><th>Archivo</th><th>Líneas</th>"
        "<th>Líneas sin cubrir</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def write_report(suites: dict[str, dict[str, Any]], generated_at: str) -> None:
    """Write current-run JSON and a self-contained HTML dashboard with SVG charts."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    total_tests = sum(item.get("tests", 0) for item in suites.values())
    total_passed = sum(item.get("passed", 0) for item in suites.values())
    failed_tests = sum(
        item.get("failed", 0) + item.get("errors", 0) for item in suites.values()
    )
    overall_status = (
        "fallido"
        if any(item.get("status") == "failed" for item in suites.values())
        else "correcto"
        if all(item.get("status") == "passed" for item in suites.values())
        else "incompleto"
    )
    report_data = {
        "generated_at": generated_at,
        "status": overall_status,
        "total_tests": total_tests,
        "failed_tests": failed_tests,
        "suites": suites,
    }
    (REPORTS / "summary.json").write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    coverage_values = [
        item.get("line_coverage")
        for item in suites.values()
        if item.get("line_coverage") is not None
    ]
    coverage_max = max([100.0, *coverage_values])
    test_max = max([1, *(item.get("tests", 0) for item in suites.values())])
    coverage_rows: list[str] = []
    test_rows: list[str] = []
    for suite_name in ("backend", "frontend"):
        item = suites[suite_name]
        status_class = (
            "good"
            if item.get("status") == "passed"
            else "bad"
            if item.get("status") == "failed"
            else "neutral"
        )
        coverage_rows.append(
            f'<div class="chart-row"><strong>{suite_name.title()}</strong>'
            f"{render_bar(item.get('line_coverage'), coverage_max, '#6d3bff')}</div>"
        )
        width = item.get("tests", 0) / test_max * 100
        test_rows.append(
            f'<div class="chart-row"><strong>{suite_name.title()}</strong>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{width:.2f}%;background:#f52d91"></div></div>'
            f"<span>{item.get('tests', 0)} pruebas</span></div>"
        )
        item["status_class"] = status_class

    cards: list[str] = []
    for suite_name in ("backend", "frontend"):
        item = suites[suite_name]
        line_cover = item.get("line_coverage")
        cover_text = "No disponible" if line_cover is None else f"{line_cover:.2f}%"
        secondary_metrics = []
        if item.get("branch_coverage") is not None:
            secondary_metrics.append(f"ramas {item['branch_coverage']:.2f}%")
        if item.get("function_coverage") is not None:
            secondary_metrics.append(f"funciones {item['function_coverage']:.2f}%")
        metric_detail = " · ".join(secondary_metrics)
        metric_detail_html = (
            f'<p class="muted">{html.escape(metric_detail)}</p>'
            if metric_detail
            else ""
        )
        html_report = item.get("html_report")
        report_link = ""
        if html_report:
            relative_report = Path(html_report).relative_to(REPORTS)
            report_link = (
                f'<p><a href="{html.escape(relative_report.as_posix())}">'
                "Abrir reporte detallado</a></p>"
            )
        cards.append(
            f'<article class="card {item["status_class"]}"><h2>{suite_name.title()}</h2>'
            f'<p class="coverage">{cover_text}</p><p>{item.get("passed", 0)} aprobadas · '
            f"{item.get('failed', 0)} fallidas · {item.get('skipped', 0)} omitidas · "
            f'{item.get("errors", 0)} errores</p><p class="state">{html.escape(item.get("status", "not run"))}</p>'
            f"{metric_detail_html}{report_link}</article>"
        )

    html_page = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mis Eventos · cobertura de pruebas</title>
<style>
:root{{color-scheme:light;--ink:#20204a;--muted:#667085;--purple:#6d3bff;--pink:#f52d91;--line:#e7e5ee;--surface:#fff;--bg:#f7f8ff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:36px 22px 64px}}header{{display:flex;justify-content:space-between;align-items:end;gap:18px;margin-bottom:24px}}
h1{{font-size:clamp(1.8rem,4vw,2.8rem);line-height:1.1;margin:0}}h2{{font-size:1.05rem;margin:0 0 10px}}.muted{{color:var(--muted)}}.status{{font-weight:700;color:{"#087a58" if overall_status == "correcto" else "#b42318" if overall_status == "fallido" else "#805b00"}}}
.cards{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}.card,.panel{{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:0 4px 18px #20204a0a}}
.card.bad{{border-color:#f4a9a9}}.coverage{{font-size:2rem;font-weight:750;margin:8px 0}}.state{{text-transform:capitalize;color:var(--muted)}}section{{margin-top:22px}}.chart-row{{display:grid;grid-template-columns:110px minmax(100px,1fr) 105px;align-items:center;gap:12px;margin:14px 0}}
.bar-track{{height:16px;background:#efedf5;border-radius:999px;overflow:hidden}}.bar-fill{{height:100%;border-radius:inherit}}.unavailable{{color:var(--muted);font-size:.9rem}}
table{{width:100%;border-collapse:collapse;font-size:.92rem}}th,td{{padding:10px;text-align:left;border-bottom:1px solid var(--line)}}th{{color:var(--muted)}}footer{{margin-top:28px;color:var(--muted);font-size:.85rem}}
@media(max-width:720px){{header{{display:block}}.cards{{grid-template-columns:1fr}}.chart-row{{grid-template-columns:78px minmax(80px,1fr) 82px;gap:8px;font-size:.85rem}}main{{padding:24px 14px}}.panel{{overflow-x:auto}}}}
</style></head><body><main>
<header><div><h1>Reporte de pruebas</h1><p class="muted">Mis Eventos · ejecución local</p></div><div class="status">Estado general: {overall_status}</div></header>
<div class="cards">{"".join(cards)}<article class="card"><h2>Total combinado</h2><p class="coverage">{total_tests}</p><p>{total_passed} aprobadas · {failed_tests} fallidas o con error</p></article></div>
<section class="panel"><h2>Cobertura de líneas</h2>{"".join(coverage_rows)}</section>
<section class="panel"><h2>Pruebas ejecutadas</h2>{"".join(test_rows)}</section>
<section class="panel"><h2>Archivos con menor cobertura</h2>{render_file_table(suites)}</section>
<footer>Generado: {html.escape(generated_at)} · Los valores reflejan únicamente esta ejecución; suites no ejecutadas aparecen como no disponibles.</footer>
</main></body></html>"""
    (REPORTS / "index.html").write_text(html_page, encoding="utf-8")
    print(f"HTML conjunto: {REPORTS / 'index.html'}")


def empty_suite(status: str = "not run") -> dict[str, Any]:
    """Create an explicit unavailable result instead of reusing an old report."""
    return {
        "status": status,
        "tests": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "line_coverage": None,
        "branch_coverage": None,
        "files": [],
    }


def print_suite_summary(name: str, result: dict[str, Any]) -> None:
    """Print normalized test totals and the current line coverage measurement."""
    line_coverage = result.get("line_coverage")
    coverage_text = (
        "no disponible" if line_coverage is None else f"{line_coverage:.2f}%"
    )
    print(
        f"{name}: {result.get('passed', 0)} aprobadas, {result.get('failed', 0)} fallidas, "
        f"{result.get('skipped', 0)} omitidas, {result.get('errors', 0)} errores; "
        f"cobertura de líneas {coverage_text} ({result.get('status')})."
    )


def run_tests(target: str) -> int:
    """Run requested suites, continue after failures, and render current metrics."""
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    suites = {"backend": empty_suite(), "frontend": empty_suite()}
    exit_codes: list[int] = []
    if target in ("backend", "both"):
        code, suites["backend"] = run_backend_tests()
        exit_codes.append(code)
        print_suite_summary("Backend", suites["backend"])
    if target in ("frontend", "both"):
        code, suites["frontend"] = run_frontend_tests()
        exit_codes.append(code)
        print_suite_summary("Frontend", suites["frontend"])
    write_report(suites, generated_at)
    total_tests = sum(item.get("tests", 0) for item in suites.values())
    total_passed = sum(item.get("passed", 0) for item in suites.values())
    total_failed = sum(item.get("failed", 0) for item in suites.values())
    total_skipped = sum(item.get("skipped", 0) for item in suites.values())
    total_errors = sum(item.get("errors", 0) for item in suites.values())
    print(
        f"Total: {total_tests} tests, {total_passed} aprobadas, {total_failed} fallidas, "
        f"{total_skipped} omitidas, {total_errors} errores."
    )
    return 1 if any(code != 0 for code in exit_codes) else 0


def lint() -> int:
    """Run configured backend Ruff and frontend ESLint checks without short-circuiting."""
    commands = [
        (["poetry", "run", "ruff", "check", "."], BACKEND),
        (["poetry", "run", "ruff", "format", "--check", "."], BACKEND),
        (["npm", "run", "lint"], FRONTEND),
    ]
    results = [run_command(command, cwd) for command, cwd in commands]
    return 1 if any(result != 0 for result in results) else 0


def dispatch(command: str) -> int:
    """Route a Make target to its local development implementation."""
    if command == "check":
        return 0 if check_tools(require_docker=True) else 1
    if command == "setup":
        return setup()
    if command == "up":
        return up()
    if command == "status":
        return status()
    if command == "logs":
        return logs()
    if command == "migrate":
        return migrate()
    if command == "test-backend":
        return run_tests("backend")
    if command == "test-frontend":
        return run_tests("frontend")
    if command in ("test", "coverage"):
        return run_tests("both")
    if command == "lint":
        return lint()
    if command == "down":
        return stop()
    if command == "restart":
        return restart()
    raise ValueError(f"Unknown development command: {command}")


def main() -> int:
    """Parse the helper command and return its process exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "check",
            "setup",
            "up",
            "status",
            "logs",
            "migrate",
            "test-backend",
            "test-frontend",
            "test",
            "coverage",
            "lint",
            "down",
            "restart",
        ),
    )
    arguments = parser.parse_args()
    return dispatch(arguments.command)


if __name__ == "__main__":
    raise SystemExit(main())
