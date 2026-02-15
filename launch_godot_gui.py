"""
Local helper to start the backend (optional) and launch the Godot GUI project.

This is intended for developer convenience only.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _tcp_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.25)
        return s.connect_ex((host, port)) == 0


def _http_ok(url: str) -> bool:
    try:
        req = Request(url, headers={"User-Agent": "fba-bench-launcher"})
        with urlopen(req, timeout=1.5) as resp:
            return 200 <= int(resp.status) < 300
    except Exception:
        return False


def _wait_for_backend(health_url: str, timeout_s: int) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _http_ok(health_url):
            return True
        time.sleep(0.5)
    return False


def _find_godot_exe(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    return shutil.which("godot") or shutil.which("godot4")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-backend", action="store_true", help="Do not start the backend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Start backend with uvicorn reload.")
    parser.add_argument("--wait-seconds", type=int, default=60)
    parser.add_argument("--godot", default=os.environ.get("GODOT_EXE"), help="Godot executable path.")
    args = parser.parse_args()

    root = _repo_root()
    godot_project = root / "godot_gui"
    if not godot_project.exists():
        print(f"godot project directory not found: {godot_project}", file=sys.stderr)
        return 2

    backend_proc: subprocess.Popen[str] | None = None
    health_url = f"http://{args.host}:{args.port}/api/v1/health"

    if not args.no_backend:
        if not _tcp_port_open(args.host, args.port):
            cmd = [
                sys.executable,
                "-m",
                "uvicorn",
                "fba_bench_api.main:get_app",
                "--factory",
                "--host",
                args.host,
                "--port",
                str(args.port),
            ]
            if args.reload:
                cmd.append("--reload")

            env = os.environ.copy()
            env.setdefault("PYTHONPATH", str(root / "src"))

            backend_proc = subprocess.Popen(cmd, cwd=str(root), env=env)
        if not _wait_for_backend(health_url, timeout_s=args.wait_seconds):
            if backend_proc is not None:
                backend_proc.terminate()
            print(f"backend did not become ready: {health_url}", file=sys.stderr)
            return 3

    godot_exe = _find_godot_exe(args.godot)
    if not godot_exe:
        if backend_proc is not None:
            print("backend started; Godot not found in PATH (set GODOT_EXE).", file=sys.stderr)
            return 4
        print("Godot not found in PATH (set GODOT_EXE).", file=sys.stderr)
        return 4

    try:
        # Godot 4 CLI: `--path` points at the project directory.
        # Provide the GUI with connection info via environment variables so the project
        # can run against either:
        # - backend-only (default :8000), or
        # - one-click stack (use --no-backend --port 8080).
        ui_host = args.host
        if ui_host in ("0.0.0.0", "::"):
            ui_host = "127.0.0.1"

        godot_env = os.environ.copy()
        godot_env.setdefault("FBA_BENCH_HTTP_BASE_URL", f"http://{ui_host}:{args.port}")
        godot_env.setdefault(
            "FBA_BENCH_WS_URL", f"ws://{ui_host}:{args.port}/ws/realtime"
        )

        subprocess.run(
            [godot_exe, "--path", str(godot_project)], check=False, env=godot_env
        )
    finally:
        # Leave backend running; launcher is a convenience tool and shouldn't kill user processes.
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
