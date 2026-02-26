from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple, TypedDict

# Reuse CLI logic safely (functions have no CLI side-effects on import)
from fba_bench.cli import (
    check_docker_available as cli_check_docker_available,
    check_port_open as cli_check_port_open,
    docker_cmd_base as cli_docker_cmd_base,
    find_compose_file as cli_find_compose_file,  # type: ignore
    locate_repo_root as cli_locate_repo_root,
    start_docker_compose as cli_start_docker_compose,
)

from fba_bench_core.config import get_settings  # runtime env awareness

logger = logging.getLogger("fba_bench_api.stack")


def _truthy(env_val: Optional[str]) -> bool:
    if env_val is None:
        return False
    return env_val.strip().lower() in ("1", "true", "yes", "on")


def stack_control_allowed() -> bool:
    """
    Gate for stack control endpoints.
    Controlled by ALLOW_STACK_CONTROL=true (or 1/yes/on).
    Additionally, ALWAYS disabled in protected environments (staging/production).
    """
    try:
        # Lazy access to avoid import cycles during module import
        if get_settings().is_protected_env:
            return False
    except Exception:
        # Fail closed if settings cannot be determined
        return False
    return _truthy(os.getenv("ALLOW_STACK_CONTROL"))


def get_ports() -> Dict[str, int]:
    """
    Resolve ClearML ports honoring the same env vars as the CLI.
    """
    return {
        "web": int(os.getenv("FBA_BENCH_CLEARML_WEB_PORT", "8080") or "8080"),
        "file": int(os.getenv("FBA_BENCH_CLEARML_FILE_PORT", "8081") or "8081"),
        "api": int(os.getenv("FBA_BENCH_CLEARML_API_PORT", "8008") or "8008"),
    }


class PortStatus(TypedDict):
    port: int
    open: bool


class PortsReport(TypedDict):
    web: PortStatus
    api: PortStatus
    file: PortStatus


def _repo_root() -> Optional[Path]:
    """
    Discover the repository root using the same strategy as the CLI.
    """
    try:
        return cli_locate_repo_root()
    except Exception:
        return None


def _is_within(base: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


def _env_compose_override_path() -> Optional[Path]:
    """
    If FBA_BENCH_CLEARML_COMPOSE is an absolute path, treat it as an explicit override whitelist.
    """
    raw = os.getenv("FBA_BENCH_CLEARML_COMPOSE")
    if not raw:
        return None
    p = Path(raw).expanduser()
    try:
        # If relative filename, caller will resolve against repo root; whitelist only absolute files here.
        if p.is_absolute():
            return p.resolve()
    except Exception:
        return None
    return None


def resolve_compose_file(
    user_path: Optional[str],
) -> Tuple[Optional[Path], Optional[str]]:
    """
    Resolve and validate the docker-compose.clearml.yml path with path whitelisting.

    Rules:
    - If user provided a path, it must:
        * exist, and
        * be within the discovered repo root; OR
        * exactly match an absolute explicit override from FBA_BENCH_CLEARML_COMPOSE.
    - Otherwise, fallback to CLI's find_compose_file().
    Returns (compose_file_path, error_message_if_any).
    """
    repo_root = _repo_root()
    override_abs = _env_compose_override_path()

    if user_path:
        candidate = Path(user_path).expanduser().resolve()
        if not candidate.exists():
            return None, f"Compose file not found: {candidate}"

        if override_abs and candidate == override_abs:
            logger.info("Compose path allowed via explicit env override: %s", candidate)
            return candidate, None

        if repo_root:
            if _is_within(repo_root, candidate):
                return candidate, None
            else:
                return (
                    None,
                    "Compose path is outside the repository root and no explicit override is configured.",
                )
        else:
            # No repo root identified: only allow explicit override for absolute paths
            if override_abs and candidate == override_abs:
                return candidate, None
            return (
                None,
                "Repository root not found; refusing untrusted compose path without explicit override.",
            )

    # No user path: use CLI discovery
    discovered = cli_find_compose_file()
    if not discovered or not discovered.exists():
        return None, "Could not locate docker-compose.clearml.yml using CLI discovery."
    return discovered, None


def docker_variant() -> str:
    """
    Determine which docker compose command variant will be used.
    """
    base = cli_docker_cmd_base()
    if base is None:
        return "unavailable"
    if base == ["docker", "compose"]:
        return "docker compose"
    if base == ["docker-compose"]:
        return "docker-compose"
    return "unknown"


def stop_docker_compose(compose_file: Path) -> Tuple[bool, Optional[str]]:
    """
    Stop ClearML stack using 'docker compose -f file down' with robust fallback to docker-compose.
    """
    base = cli_docker_cmd_base()
    if base is None:
        return False, "Docker is not installed or not on PATH."

    # Validate 'version' and fallback if needed
    try:
        version_proc = subprocess.run(
            base + ["version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if version_proc.returncode != 0 and base == ["docker", "compose"]:
            # Fall back to docker-compose if docker compose v2 is not available
            base = ["docker-compose"]
    except Exception:
        # On any error, try docker-compose if present
        if shutil_which("docker-compose"):
            base = ["docker-compose"]

    cmd = base + ["-f", str(compose_file), "down"]
    logger.info("Stopping ClearML stack with: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, check=False)
        if proc.returncode != 0:
            return False, f"Failed to stop ClearML stack (exit code {proc.returncode})."
    except FileNotFoundError:
        return (
            False,
            "Docker Compose command not found. Ensure Docker is installed and on PATH.",
        )
    except Exception as e:
        return False, f"Error stopping Docker Compose: {e}"

    return True, None


def shutil_which(cmd: str) -> bool:
    try:
        import shutil

        return bool(shutil.which(cmd))
    except Exception:
        return False


def start_stack(
    compose_path: Optional[str], detach: bool = True
) -> Tuple[bool, Optional[Path], str, str]:
    """
    Start the ClearML docker compose stack. Always uses detached mode (up -d) for API safety.

    Returns (started, compose_file, message, docker_variant).
    """
    compose_file, err = resolve_compose_file(compose_path)
    if err:
        logger.warning("Compose resolution failed: %s", err)
        return False, None, err, docker_variant()

    # Check docker availability
    ok, err2 = cli_check_docker_available()
    if not ok:
        logger.warning("Docker not available: %s", err2)
        return False, compose_file, (err2 or "Docker not available"), docker_variant()

    # Enforce detached mode (API cannot safely run foreground)
    if not detach:
        logger.info(
            "detach=false was requested, but API enforces detached mode for safety."
        )
    logger.info("Using compose file: %s", compose_file)
    logger.info("Docker command variant: %s", docker_variant())

    started = cli_start_docker_compose(compose_file)
    if not started:
        return (
            False,
            compose_file,
            "Failed to start ClearML stack. Check Docker logs.",
            docker_variant(),
        )

    return (
        True,
        compose_file,
        "ClearML stack is starting in detached mode.",
        docker_variant(),
    )


def stop_stack(compose_path: Optional[str]) -> Tuple[bool, Optional[Path], str, str]:
    """
    Stop the ClearML docker compose stack.

    Returns (stopped, compose_file, message, docker_variant).
    """
    compose_file, err = resolve_compose_file(compose_path)
    if err:
        logger.warning("Compose resolution failed for stop: %s", err)
        return False, None, err, docker_variant()

    ok, err2 = cli_check_docker_available()
    if not ok:
        logger.warning("Docker not available: %s", err2)
        return False, compose_file, (err2 or "Docker not available"), docker_variant()

    stopped, serr = stop_docker_compose(compose_file)  # type: ignore[arg-type]
    if not stopped:
        return (
            False,
            compose_file,
            serr or "Failed to stop ClearML stack.",
            docker_variant(),
        )

    return True, compose_file, "ClearML stack stopped.", docker_variant()


def ports_status() -> Tuple[PortsReport, bool]:
    """
    Compute non-blocking status of ClearML ports on localhost.
    Returns (ports_report, running_all) where running_all indicates all three ports are open.
    """
    ports = get_ports()
    web_open = cli_check_port_open("localhost", ports["web"], timeout=0.5)
    api_open = cli_check_port_open("localhost", ports["api"], timeout=0.5)
    file_open = cli_check_port_open("localhost", ports["file"], timeout=0.5)

    report: PortsReport = {
        "web": {"port": ports["web"], "open": bool(web_open)},
        "api": {"port": ports["api"], "open": bool(api_open)},
        "file": {"port": ports["file"], "open": bool(file_open)},
    }
    running_all = (
        report["web"]["open"] and report["api"]["open"] and report["file"]["open"]
    )
    return report, bool(running_all)


def urls(ports: Dict[str, int], running_local: bool) -> Tuple[str, str, str]:
    """
    Compute URLs honoring env vars similar to CLI.
    """
    # Web URL
    web_ui_override = os.getenv("FBA_BENCH_CLEARML_LOCAL_UI")
    if web_ui_override:
        web_url = web_ui_override.strip()
    else:
        web_url = (
            f"http://localhost:{ports['web']}"
            if running_local
            else os.getenv("CLEARML_WEB_HOST", "https://app.clear.ml")
        )

    # API/Files URLs are always localhost-based for local stack
    api_url = f"http://localhost:{ports['api']}"
    file_url = f"http://localhost:{ports['file']}"

    return web_url, api_url, file_url


def status(compose_path: Optional[str]) -> Dict[str, object]:
    """
    Build status payload:
    {
      running: bool,
      web_url, api_url, file_url: str,
      ports: { web:{port,open}, api:{port,open}, file:{port,open} },
      compose_file: str
    }
    """
    compose_file, _ = resolve_compose_file(
        compose_path
    )  # best-effort; status should not fail if missing
    ports = get_ports()
    ports_report, running_all = ports_status()
    web_url, api_url, file_url = urls(ports, running_local=running_all)

    payload: Dict[str, object] = {
        "running": bool(running_all),
        "web_url": web_url,
        "api_url": api_url,
        "file_url": file_url,
        "ports": ports_report,
        "compose_file": str(compose_file) if compose_file else "",
    }
    return payload
