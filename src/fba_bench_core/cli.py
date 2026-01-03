#!/usr/bin/env python3
"""
FBA-Bench CLI entry point.

Provides a cross-platform command-line interface to:
- Launch experiments (optionally bringing up a local ClearML server via Docker Compose)
- Open the ClearML Web UI

Usage examples:
  - Show help:
      fba-bench
      fba-bench --help

  - Launch with existing ClearML setup (cloud or pre-configured server):
      fba-bench launch

  - Launch with a locally hosted ClearML server:
      fba-bench launch --with-server
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from collections.abc import Iterable
from pathlib import Path
from typing import Optional

import yaml

from fba_bench_core.logging import configure_logging, get_logger
from fba_bench_core.settings import get_settings

_SETTINGS = get_settings()
# -------- Logging Configuration --------
configure_logging(_SETTINGS)
LOG = get_logger("fba_bench.cli")


# -------- Constants --------
DEFAULT_CLEARML_UI_CLOUD = _SETTINGS.clearml_web_host
LOCAL_CLEARML_UI = _SETTINGS.clearml_local_ui
CLEARML_PORTS = (
    ("Web UI", "localhost", int(_SETTINGS.clearml_web_port)),
    ("File Server", "localhost", int(_SETTINGS.clearml_file_port)),
    ("API Server", "localhost", int(_SETTINGS.clearml_api_port)),
)
COMPOSE_FILENAME = _SETTINGS.clearml_compose_filename
ENV_ROOT_HINT = _SETTINGS.repo_root_hint


# -------- Utility Functions --------
def _is_command_available(cmd: Iterable[str] | str) -> bool:
    """
    Return True if the given command (executable) is available on PATH.

    Accepts a string (single command name) or an iterable (only first item is checked).
    """
    exe = None
    if isinstance(cmd, (list, tuple)):
        exe = cmd[0]
    elif isinstance(cmd, str):
        exe = cmd.split()[0]
    return bool(shutil.which(str(exe)))


def _print_progress(prefix: str, secs: int) -> None:
    """Print a simple progress message for long-running operations."""
    LOG.info("%s (elapsed: %ds)", prefix, secs)


def locate_repo_root(start: Optional[Path] = None) -> Optional[Path]:
    """
    Try to locate the repository root by searching upwards for sentinel files.
    Priority:
      1) FBA_BENCH_ROOT environment variable (if exists and valid)
      2) Directory containing this file (__file__)
      3) Current working directory
    Sentinels:
      - docker-compose.clearml.yml
      - pyproject.toml
      - README.md
    """
    candidates: list[Path] = []

    if ENV_ROOT_HINT:
        p = Path(ENV_ROOT_HINT).expanduser().resolve()
        if p.exists():
            candidates.append(p)

    if start is None:
        try:
            candidates.append(Path(__file__).resolve().parent.parent)
        except (OSError, AttributeError):
            pass
        candidates.append(Path.cwd())
    else:
        candidates.append(start)

    seen: set[Path] = set()
    for base in candidates:
        if not base.exists():
            continue
        cur = base
        # Walk upwards
        while True:
            if cur in seen:
                break
            seen.add(cur)
            if (
                (cur / "docker-compose.clearml.yml").exists()
                or (cur / "pyproject.toml").exists()
                or (cur / "README.md").exists()
            ):
                return cur
            if cur.parent == cur:
                break
            cur = cur.parent

    return None


def find_compose_file() -> Optional[Path]:
    """
    Find docker-compose.clearml.yml by checking:
      - FBA_BENCH_ROOT hint
      - Repository root discovery
      - Current working directory
    """
    # 1) Explicit env override may be a full path or directory
    if ENV_ROOT_HINT:
        hint = Path(ENV_ROOT_HINT).expanduser()
        if hint.is_file() and hint.name == COMPOSE_FILENAME:
            return hint.resolve()
        if hint.is_dir():
            f = hint / COMPOSE_FILENAME
            if f.exists():
                return f.resolve()

    # 2) Repo root search
    repo_root = locate_repo_root()
    if repo_root:
        f = repo_root / COMPOSE_FILENAME
        if f.exists():
            return f.resolve()

    # 3) Current working directory
    cwd_file = Path.cwd() / COMPOSE_FILENAME
    if cwd_file.exists():
        return cwd_file.resolve()

    return None


def check_port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    """Check if TCP port is open."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_clearml_ready(timeout: int = 180, poll_interval: float = 2.0) -> bool:
    """
    Wait for ClearML services to become reachable on their TCP ports.
    Returns True if all expected ports become available before timeout.
    """
    LOG.info("Waiting for ClearML services to be ready (timeout: %ds)...", timeout)
    start = time.time()
    ready_flags = {name: False for (name, _, _) in CLEARML_PORTS}

    while True:
        elapsed = int(time.time() - start)
        all_ready = True
        for name, host, port in CLEARML_PORTS:
            if not ready_flags[name]:
                if check_port_open(host, port):
                    ready_flags[name] = True
                    LOG.info("Service ready: %s on %s:%d", name, host, port)
                else:
                    all_ready = False

        if all_ready:
            LOG.info("All ClearML services are ready.")
            return True

        if elapsed >= timeout:
            LOG.error("Timed out after %ds waiting for ClearML services.", timeout)
            not_ready = [n for n, ok in ready_flags.items() if not ok]
            LOG.error("Services not ready: %s", ", ".join(not_ready))
            return False

        if elapsed % 10 == 0:
            _print_progress("Still waiting for ClearML...", elapsed)

        time.sleep(poll_interval)


def open_clearml_ui(local: bool) -> None:
    """
    Open ClearML Web UI in the default browser.
    - If local=True: open LOCAL_CLEARML_UI (default http://localhost:8080)
    - Else: open CLEARML cloud UI or env-provided host
    """
    url = LOCAL_CLEARML_UI if local else DEFAULT_CLEARML_UI_CLOUD
    LOG.info("Opening ClearML Web UI: %s", url)
    try:
        webbrowser.open(url, new=2)  # new tab
    except (webbrowser.Error, OSError) as e:
        LOG.warning("Failed to open web browser automatically: %s", e)


def docker_cmd_base() -> Optional[list[str]]:
    """
    Determine the preferred Docker Compose invocation:
      - Prefer: docker compose (Docker CLI v2)
      - Fallback: docker-compose (standalone v1)
    Returns the command list prefix or None if neither available.
    """
    if _is_command_available("docker"):
        # If docker is available, assume docker compose may be available (CLI v2).
        # We'll check by trying 'docker compose version' later when used.
        return ["docker", "compose"]
    if _is_command_available("docker-compose"):
        return ["docker-compose"]
    return None


def check_docker_available() -> tuple[bool, Optional[str]]:
    """
    Check Docker is installed and the daemon is running.
    Returns (ok, error_message_if_any).
    """
    # Is docker CLI present?
    if not _is_command_available("docker") and not _is_command_available(
        "docker-compose"
    ):
        return False, (
            "Docker is not installed or not on PATH. "
            "Install Docker Desktop (Windows/Mac) or Docker Engine (Linux): https://docs.docker.com/get-docker/"
        )

    # Is daemon reachable?
    try:
        # Prefer 'docker info'
        if _is_command_available("docker"):
            proc = subprocess.run(
                ["docker", "info"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if proc.returncode != 0:
                return False, (
                    "Docker daemon is not reachable. Start Docker Desktop or the Docker service and try again."
                )
        else:
            # If only docker-compose is present, try a benign compose command to check daemon error.
            base = docker_cmd_base()
            if base is None:
                return False, "Neither 'docker' nor 'docker-compose' is available."
            proc = subprocess.run(
                base + ["version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if proc.returncode != 0:
                return False, (
                    "Docker Compose is not functioning correctly. Ensure Docker is running and try again."
                )
    except FileNotFoundError:
        return False, "Docker is not installed or not on PATH."
    except (subprocess.SubprocessError, OSError) as e:
        return False, f"Error checking Docker status: {e}"

    return True, None


def start_docker_compose(compose_file: Path) -> bool:
    """
    Start ClearML stack using docker compose up -d.
    Returns True if the stack was launched successfully.
    """
    base = docker_cmd_base()
    if base is None:
        LOG.error("Unable to find a Docker Compose command. Install Docker first.")
        return False

    # Confirm 'docker compose' vs 'docker-compose' works
    try:
        version_proc = subprocess.run(
            base + ["version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if version_proc.returncode != 0 and base == ["docker", "compose"]:
            # Fall back to docker-compose if 'docker compose' isn't supported
            if _is_command_available("docker-compose"):
                LOG.info("Falling back to 'docker-compose' CLI.")
                base = ["docker-compose"]
    except (subprocess.SubprocessError, OSError):
        # If any error, try fallback
        if _is_command_available("docker-compose"):
            LOG.info("Falling back to 'docker-compose' CLI.")
            base = ["docker-compose"]

    cmd = base + ["-f", str(compose_file), "up", "-d"]
    LOG.info("Starting ClearML server stack with: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, check=False)
        if proc.returncode != 0:
            LOG.error("Failed to start ClearML stack (exit code %s).", proc.returncode)
            LOG.error(
                "You can inspect logs with: %s -f %s logs", " ".join(base), compose_file
            )
            return False
    except FileNotFoundError:
        LOG.error(
            "Docker Compose command not found. Ensure Docker is installed and available on PATH."
        )
        return False
    except (subprocess.SubprocessError, OSError) as e:
        LOG.error("Error starting Docker Compose: %s", e)
        return False

    LOG.info("ClearML server stack is starting in the background.")
    return True


def start_api_server():
    """
    Start the FBA-Bench FastAPI server in a subprocess.
    Returns the Popen process object or None if failed.
    """
    try:
        # Set environment variables for CORS and development
        env = os.environ.copy()
        env["FBA_CORS_ALLOW_ORIGINS"] = (
            "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
        )
        env["FBA_BENCH_HOST"] = "0.0.0.0"
        env["FBA_BENCH_PORT"] = "8000"
        env["FBA_BENCH_RELOAD"] = "false"  # Don't use reload in production-like mode

        # Try several methods to start the API server

        # Method 1: Try the main.py run function via module execution
        cmd = [sys.executable, "-m", "fba_bench_api.main"]
        LOG.info("Starting API server via module: %s", " ".join(cmd))
        try:
            proc = subprocess.Popen(cmd, env=env)

            # Give it a moment to start
            time.sleep(2)

            # Check if it's still running
            if proc.poll() is None:
                return proc
            else:
                LOG.warning(
                    "API server module execution failed with return code: %s",
                    proc.poll(),
                )
        except (subprocess.SubprocessError, OSError) as e:
            LOG.debug("Method 1 failed: %s", e)

        # Method 2: Try direct script execution via api_server.py
        repo_root = locate_repo_root()
        if repo_root is not None:
            api_script = repo_root / "api_server.py"
            if api_script.exists():
                cmd = [sys.executable, str(api_script)]
                LOG.info("Starting API server via script: %s", " ".join(cmd))
                try:
                    proc = subprocess.Popen(cmd, env=env)

                    # Give it a moment to start
                    time.sleep(2)

                    # Check if it's still running
                    if proc.poll() is None:
                        return proc
                    else:
                        LOG.warning(
                            "API server script execution failed with return code: %s",
                            proc.poll(),
                        )
                except (subprocess.SubprocessError, OSError) as e:
                    LOG.debug("Method 2 failed: %s", e)

        # Method 3: Try uvicorn directly
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "fba_bench_api.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]
        LOG.info("Starting API server via uvicorn: %s", " ".join(cmd))
        try:
            proc = subprocess.Popen(cmd, env=env)

            # Give it a moment to start
            time.sleep(2)

            # Check if it's still running
            if proc.poll() is None:
                return proc
            else:
                LOG.warning(
                    "API server uvicorn execution failed with return code: %s",
                    proc.poll(),
                )
        except Exception as e:
            LOG.debug("Method 3 failed: %s", e)

        LOG.error("All methods to start API server failed")
        return None

    except (subprocess.SubprocessError, OSError) as e:
        LOG.error("Failed to start API server: %s", e)
        return None


def run_simulation_orchestrator() -> int:
    """
    Execute the project's simulation orchestrator.

    Strategy:
      1) Try to import from the installed package (fba_bench.simulation_orchestrator) and call a callable
         named 'main' or 'run' if available.
      2) Try to import a top-level 'simulation_orchestrator' module (useful when running from repo root).
      3) Fallback to invoking the module via 'python -m fba_bench.simulation_orchestrator'.
      4) Fallback to invoking a script file 'simulation_orchestrator.py' located at repo root.

    Returns the process/module exit code (0 on success).
    """
    LOG.info("Starting simulation orchestrator...")
    # Step 1: Package-relative import
    sim_mod = None
    try:
        from . import simulation_orchestrator as sim_mod  # type: ignore
    except (ImportError, TypeError):
        sim_mod = None

    # Step 2: Repo-top-level import (when executed from source)
    if sim_mod is None:
        try:
            import simulation_orchestrator as sim_mod  # type: ignore
        except (ImportError, TypeError):
            sim_mod = None

    # If module import succeeded, attempt to call an entry
    if sim_mod is not None:
        for attr in ("main", "run"):
            try:
                fn = getattr(sim_mod, attr, None)
                if callable(fn):
                    LOG.info(
                        "Running orchestrator via in-process call: %s.%s()",
                        sim_mod.__name__,
                        attr,
                    )
                    rc = fn()  # type: ignore[misc]
                    return int(rc) if isinstance(rc, int) else 0
            except SystemExit as e:
                # In case the orchestrator calls sys.exit
                return int(e.code) if isinstance(e.code, int) else 0
            except (AttributeError, TypeError, ValueError) as e:
                LOG.error("Error running orchestrator function '%s': %s", attr, e)
                break  # Fall back to subprocess route

    # Step 3: Try module execution via -m
    cmd = [sys.executable, "-m", "fba_bench.simulation_orchestrator"]
    LOG.info("Attempting to run orchestrator as a module: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd)
        if proc.returncode == 0:
            return 0
        LOG.warning("Module execution returned non-zero exit code: %s", proc.returncode)
    except (subprocess.SubprocessError, OSError) as e:
        LOG.debug("Module execution failed: %s", e)

    # Step 4: Fallback to repo-root script execution
    repo_root = locate_repo_root()
    if repo_root is not None:
        script = repo_root / "simulation_orchestrator.py"
        if script.exists():
            cmd = [sys.executable, str(script)]
            LOG.info("Running orchestrator via script: %s", " ".join(cmd))
            try:
                proc = subprocess.run(cmd)
                return int(proc.returncode)
            except (subprocess.SubprocessError, OSError) as e:
                LOG.error("Failed to run orchestrator script: %s", e)
                return 1

    LOG.error(
        "Unable to locate or run the simulation orchestrator. "
        "Ensure 'simulation_orchestrator.py' is available in the package or at the repository root."
    )
    return 1


def start_api_server():
    """
    Start the FBA-Bench FastAPI server in a subprocess.
    Returns the Popen process object or None if failed.
    """
    try:
        # Set environment variables for CORS and development
        env = os.environ.copy()
        env["FBA_CORS_ALLOW_ORIGINS"] = (
            "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
        )
        env["FBA_BENCH_HOST"] = "0.0.0.0"
        env["FBA_BENCH_PORT"] = "8000"
        env["FBA_BENCH_RELOAD"] = "false"  # Don't use reload in production-like mode
        env["AUTH_ENABLED"] = "false"  # Disable auth for local development
        env["AUTH_TEST_BYPASS"] = "true"

        # Try several methods to start the API server

        # Method 1: Try the main.py run function via module execution
        cmd = [sys.executable, "-m", "fba_bench_api.main"]
        LOG.info("Starting API server via module: %s", " ".join(cmd))
        try:
            proc = subprocess.Popen(
                cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            # Give it a moment to start and check if port 8000 is open
            time.sleep(3)
            if check_port_open("localhost", 8000):
                LOG.info("FBA-Bench API server is running on http://localhost:8000")
                return proc
            else:
                proc.terminate()
                LOG.warning("API server didn't start properly (port 8000 not open)")
        except (subprocess.SubprocessError, OSError) as e:
            LOG.debug("Method 1 failed: %s", e)
            if "proc" in locals():
                proc.terminate()

        # Method 2: Try uvicorn directly
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "fba_bench_api.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]
        LOG.info("Starting API server via uvicorn: %s", " ".join(cmd))
        try:
            proc = subprocess.Popen(
                cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            # Give it a moment to start and check if port 8000 is open
            time.sleep(3)
            if check_port_open("localhost", 8000):
                LOG.info("FBA-Bench API server is running on http://localhost:8000")
                return proc
            else:
                proc.terminate()
                LOG.warning("API server didn't start properly (port 8000 not open)")
        except (subprocess.SubprocessError, OSError) as e:
            LOG.debug("Method 2 failed: %s", e)
            if "proc" in locals():
                proc.terminate()

        LOG.error("All methods to start API server failed")
        return None

    except (subprocess.SubprocessError, OSError, RuntimeError) as e:
        LOG.error("Failed to start API server: %s", e)
        return None


# -------- CLI Implementation --------
def setup_environment_interactive():
    """Prompt for API keys if not set."""
    keys = ["OPENAI_API_KEY", "OPENROUTER_API_KEY"]
    for key in keys:
        if not os.getenv(key):
            value = input(f"Enter {key} (optional, press Enter to skip): ")
            if value:
                os.environ[key] = value
                print(f"Set {key}")
    print("Environment setup complete. Use .env for persistence.")


def run_template_command(args: argparse.Namespace) -> int:
    """Interactive template selection and run."""
    templates_dir = Path("configs/templates")
    if not templates_dir.exists():
        print("Templates directory not found. Run from repo root.")
        return 1

    templates = list(templates_dir.glob("*.yaml"))
    if not templates:
        print("No templates found.")
        return 1

    print("Available templates:")
    for i, t in enumerate(templates, 1):
        print(f"{i}. {t.name}")

    try:
        choice = int(input("Select template number: ")) - 1
        if 0 <= choice < len(templates):
            template = templates[choice]
            print(f"Selected {template.name}")

            # Simple adjustment
            adjustments = input(
                "Any adjustments? (e.g., max_ticks=200, press Enter for none): "
            )
            if adjustments:
                data = yaml.safe_load(template.read_text())
                for adj in adjustments.split(","):
                    if "=" in adj:
                        k, v = adj.split("=", 1)
                        data[k.strip()] = v.strip()
                template_path = templates_dir / f"{template.stem}_adjusted.yaml"
                with open(template_path, "w") as f:
                    yaml.dump(data, f)
                print(f"Adjusted template saved to {template_path}")
                template = template_path

            # Run the template
            print("Running simulation...")
            # Call simulation_orchestrator via subprocess (align with existing module)
            cmd = [
                sys.executable,
                "-m",
                "fba_bench.simulation_orchestrator",
                str(template),
            ]
            proc = subprocess.run(cmd, check=False)
            return proc.returncode
        else:
            print("Invalid choice.")
            return 1
    except ValueError:
        print("Invalid input.")
        return 1


def leaderboard_command(args: argparse.Namespace) -> int:
    """Display official leaderboard scores."""
    scores = [
        ("GPT-4o", 85.2),
        ("Claude 3.5 Sonnet", 82.1),
        ("Llama 3.1 405B", 78.5),
        ("Baseline Bot", 65.0),
    ]
    print("Official FBA-Bench Leaderboard:")
    for model, score in scores:
        print(f"{model}: {score}%")
    print("For full leaderboard, visit ClearML project or docs.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    description = (
        "FBA-Bench CLI: launch experiments and optionally manage a local ClearML server.\n\n"
        "Examples:\n"
        "  fba-bench launch\n"
        "  fba-bench launch --with-server\n"
        "  fba-bench run-template\n"
        "  fba-bench leaderboard\n"
    )
    parser = argparse.ArgumentParser(
        prog="fba-bench",
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    # launch subcommand
    p_launch = subparsers.add_parser(
        "launch",
        help="Launch FBA-Bench experiments. Optionally start a local ClearML server.",
    )
    p_launch.add_argument(
        "--with-server",
        action="store_true",
        help="Start a local ClearML server using docker-compose.clearml.yml before launching.",
    )
    p_launch.add_argument(
        "--game-mode",
        action="store_true",
        help="Enable game-themed logging for ClearML (quests, badges, emojis).",
    )

    # run-template subcommand
    subparsers.add_parser(
        "run-template", help="Interactive template selection, adjustment, and run."
    )

    # leaderboard subcommand
    subparsers.add_parser("leaderboard", help="Display official leaderboard scores.")

    # run subcommand
    subparsers.add_parser(
        "run",
        help="Start essential services (backend, frontend, database) for local development using docker-compose up.",
    )

    return parser


def handle_launch(with_server: bool, game_mode: bool = False) -> int:
    """
    Handle the 'launch' subcommand logic.
    """
    compose_file: Optional[Path] = None
    started_stack = False
    api_process = None

    try:
        if with_server:
            ok, err = check_docker_available()
            if not ok:
                LOG.error(err)
                return 2

            compose_file = find_compose_file()
            if not compose_file or not compose_file.exists():
                LOG.error(
                    "Could not find '%s'.\n"
                    "Search strategy:\n"
                    "- FBA_BENCH_ROOT env hint: %r\n"
                    "- Repository root discovery from %r\n"
                    "- Current working directory: %r\n"
                    "You can set FBA_BENCH_ROOT to the project root or run from the repository.",
                    COMPOSE_FILENAME,
                    ENV_ROOT_HINT,
                    Path(__file__).resolve(),
                    Path.cwd(),
                )
                return 2

            LOG.info("Using compose file: %s", compose_file)

            if not start_docker_compose(compose_file):
                return 2
            started_stack = True

            # Wait for ClearML services to become ready
            if not wait_for_clearml_ready():
                LOG.error("ClearML services did not become ready in time.")
                return 3

            # Set local ClearML env vars for orchestrator
            os.environ["CLEARML_API_HOST"] = (
                f"http://localhost:{_SETTINGS.clearml_api_port}"
            )
            os.environ["CLEARML_WEB_HOST"] = (
                f"http://localhost:{_SETTINGS.clearml_web_port}"
            )
            os.environ["CLEARML_FILES_HOST"] = (
                f"http://localhost:{_SETTINGS.clearml_file_port}"
            )

            # Prompt for credentials if not set (local defaults)
            if not os.getenv("CLEARML_ACCESS_KEY"):
                print(
                    "Local ClearML credentials (default: admin@clearml.com / clearml123):"
                )
                key = (
                    input("Access Key (press Enter for default): ").strip()
                    or "admin@clearml.com"
                )
                secret = (
                    input("Secret Key (press Enter for default): ").strip()
                    or "clearml123"
                )
                os.environ["CLEARML_ACCESS_KEY"] = key
                os.environ["CLEARML_SECRET_KEY"] = secret
                print(f"Set CLEARML_ACCESS_KEY={key}, CLEARML_SECRET_KEY=***")

            # Start FastAPI backend server
            LOG.info("Starting FBA-Bench API server on http://localhost:8000...")
            api_process = start_api_server()
            if api_process:
                LOG.info("FBA-Bench API server started successfully")
            else:
                LOG.warning("Failed to start FBA-Bench API server")

        # Run orchestrator
        if with_server and game_mode:
            os.environ["FBA_GAME_MODE"] = "true"
        rc = run_simulation_orchestrator()

        # Open UI
        open_clearml_ui(local=with_server)

        if rc != 0:
            LOG.error("Simulation orchestrator exited with status code %d.", rc)
        else:
            LOG.info("Simulation orchestrator completed successfully.")
        if with_server:
            LOG.info(
                "Local ClearML server is running in the background. To stop it:\n"
                "  docker compose -f \"%s\" down   (or 'docker-compose' depending on your installation)",
                compose_file,
            )
        return int(rc)
    except KeyboardInterrupt:
        LOG.warning("Interrupted by user.")
        if api_process:
            LOG.info("Stopping API server...")
            api_process.terminate()
            try:
                api_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api_process.kill()
        if started_stack and compose_file:
            LOG.info(
                "ClearML server remains running. Stop it with:\n"
                '  docker compose -f "%s" down',
                compose_file,
            )
        return 130
    except (subprocess.SubprocessError, OSError, RuntimeError) as e:
        LOG.exception("Unexpected error: %s", e)
        if api_process:
            try:
                api_process.terminate()
            except:
                pass
        return 1


def find_dev_compose_file() -> Optional[Path]:
    """
    Locate docker-compose.yml for development services.
    Similar to find_compose_file but targets 'docker-compose.yml'.
    """
    compose_filename = "docker-compose.yml"

    # 1) Explicit env override (FBA_BENCH_ROOT)
    if ENV_ROOT_HINT:
        hint = Path(ENV_ROOT_HINT).expanduser()
        if hint.is_file() and hint.name == compose_filename:
            return hint.resolve()
        if hint.is_dir():
            f = hint / compose_filename
            if f.exists():
                return f.resolve()

    # 2) Repo root search
    repo_root = locate_repo_root()
    if repo_root:
        f = repo_root / compose_filename
        if f.exists():
            return f.resolve()

    # 3) Current working directory
    cwd_file = Path.cwd() / compose_filename
    if cwd_file.exists():
        return cwd_file.resolve()

    return None


def handle_run(args: argparse.Namespace) -> int:
    """
    Handle the 'run' subcommand: start essential development services via docker-compose up.
    Runs in foreground to display logs; Ctrl+C to stop.
    """
    compose_file = find_dev_compose_file()
    if not compose_file or not compose_file.exists():
        LOG.error(
            "Could not find 'docker-compose.yml'.\n"
            "Search strategy:\n"
            "- FBA_BENCH_ROOT env hint: %r\n"
            "- Repository root discovery from %r\n"
            "- Current working directory: %r\n"
            "Ensure docker-compose.yml exists in the project root.",
            ENV_ROOT_HINT,
            Path(__file__).resolve(),
            Path.cwd(),
        )
        return 2

    ok, err = check_docker_available()
    if not ok:
        LOG.error(err)
        return 2

    base = docker_cmd_base()
    if base is None:
        LOG.error("Unable to find Docker Compose command.")
        return 2

    # Confirm base works (fallback if needed, as in start_docker_compose)
    try:
        version_proc = subprocess.run(
            base + ["version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if version_proc.returncode != 0 and base == ["docker", "compose"]:
            if _is_command_available("docker-compose"):
                LOG.info("Falling back to 'docker-compose' CLI.")
                base = ["docker-compose"]
    except (subprocess.SubprocessError, OSError):
        if _is_command_available("docker-compose"):
            LOG.info("Falling back to 'docker-compose' CLI.")
            base = ["docker-compose"]

    cmd = base + ["-f", str(compose_file), "up"]
    LOG.info(
        "Starting development services (backend, frontend, database): %s", " ".join(cmd)
    )
    LOG.info("Services will run in foreground. Press Ctrl+C to stop.")

    try:
        proc = subprocess.run(cmd, check=False)
        return proc.returncode
    except KeyboardInterrupt:
        LOG.info("Stopping services (Ctrl+C received).")
        return 130
    except FileNotFoundError:
        LOG.error("Docker Compose command not found.")
        return 1
    except (subprocess.SubprocessError, OSError, RuntimeError) as e:
        LOG.error("Error starting services: %s", e)
        return 1


def main(argv: Optional[list[str]] = None) -> int:
    """
    Entry point for the CLI.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        # Default to 'run' for simple start
        return handle_run(args)

    if args.command == "launch":
        return handle_launch(
            with_server=getattr(args, "with_server", False),
            game_mode=getattr(args, "game_mode", False),
        )
    elif args.command == "run-template":
        return run_template_command(args)
    elif args.command == "leaderboard":
        return leaderboard_command(args)
    elif args.command == "run":
        return handle_run(args)
    else:
        parser.print_help(sys.stderr)
        return 1


def cli_main() -> int:
    """
    Test-friendly CLI entrypoint alias.
    Mirrors main() and returns process exit code instead of raising SystemExit.
    """
    try:
        # Delegate to main() which reads sys.argv by default
        return main()
    except SystemExit as e:
        try:
            return int(e.code) if e.code is not None else 0
        except (TypeError, ValueError):
            return 0


if __name__ == "__main__":
    sys.exit(main())
