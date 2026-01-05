#!/usr/bin/env python3
"""
FBA-Bench Godot GUI Launcher
Starts the FastAPI backend and launches the Godot GUI application.
"""

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class GodotGUILauncher:
    """Launcher for Godot-based FBA-Bench GUI."""

    def __init__(self):
        self.project_root = Path(__file__).parent.absolute()
        self.godot_dir = self.project_root / "godot_gui"
        self.backend_process = None
        self.godot_process = None

    def check_requirements(self) -> bool:
        """Check if required tools are available."""
        # Check Python/uvicorn
        try:
            import uvicorn  # noqa: F401
            logger.info("✓ Uvicorn found")
        except ImportError:
            logger.error("✗ Uvicorn not installed. Run: pip install uvicorn")
            return False

        # Check Godot
        godot_path = self._find_godot()
        if godot_path:
            logger.info(f"✓ Godot found: {godot_path}")
        else:
            logger.warning("⚠ Godot not found in PATH. You can still run the backend only.")
        
        return True

    def _find_godot(self) -> str | None:
        """Find Godot executable in PATH or common locations."""
        # Check PATH
        for name in ["godot", "godot4", "Godot_v4.3-stable_win64.exe"]:
            result = subprocess.run(
                ["where" if sys.platform == "win32" else "which", name],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        
        # Check common Windows locations
        if sys.platform == "win32":
            common_paths = [
                Path(os.environ.get("LOCALAPPDATA", "")) / "Godot",
                Path("C:/Program Files/Godot"),
                Path("C:/Godot"),
            ]
            for base in common_paths:
                if base.exists():
                    for exe in base.glob("*.exe"):
                        if "godot" in exe.name.lower():
                            return str(exe)
        
        return None

    def start_backend(self):
        """Start the FastAPI backend server or use existing one."""
        # Check if backend is already running
        if self._check_backend_ready():
            logger.info("✓ Backend already running on http://localhost:8000")
            return True

        logger.info("Starting FastAPI backend...")
        
        env = os.environ.copy()
        env["UVICORN_HOST"] = "0.0.0.0"
        env["UVICORN_PORT"] = "8000"
        
        self.backend_process = subprocess.Popen(
            [sys.executable, "api_server.py"],
            cwd=self.project_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        
        # Wait for backend to be ready
        for _ in range(10):
            if self._check_backend_ready():
                logger.info("✓ Backend started on http://localhost:8000")
                return True
            time.sleep(1)
        
        if self.backend_process.poll() is not None:
            logger.error("✗ Backend failed to start")
            return False
        
        return True

    def _check_backend_ready(self) -> bool:
        """Check if backend API key endpoints are responsive."""
        try:
            import urllib.request
            resp = urllib.request.urlopen("http://localhost:8000/api/v1/health", timeout=1)
            return resp.status == 200
        except Exception:
            try:
                 # Fallback for old health endpoint or just root check
                 import urllib.request
                 resp = urllib.request.urlopen("http://localhost:8000/docs", timeout=1)
                 return resp.status == 200
            except Exception:
                return False

    def start_godot(self):
        """Launch the Godot GUI application."""
        godot_path = self._find_godot()
        
        if not godot_path:
            logger.warning("Godot not found. Open the project manually:")
            logger.warning(f"  Project: {self.godot_dir}")
            return False
        
        logger.info("Launching Godot GUI...")
        
        self.godot_process = subprocess.Popen(
            [godot_path, "--path", str(self.godot_dir)],
            cwd=self.godot_dir,
        )
        
        logger.info("✓ Godot GUI launched")
        return True

    def cleanup(self):
        """Clean up running processes."""
        if self.backend_process:
            logger.info("Stopping backend...")
            self.backend_process.terminate()
            try:
                self.backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.backend_process.kill()
        
        if self.godot_process:
            logger.info("Godot process ended")

    def run(self):
        """Main launcher entry point."""
        logger.info("=" * 50)
        logger.info("FBA-Bench Enterprise - Godot GUI Launcher")
        logger.info("=" * 50)

        def signal_handler(signum, frame):
            logger.info("\nShutdown requested...")
            self.cleanup()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        if not self.check_requirements():
            logger.error("Requirements check failed. Exiting.")
            return 1

        if not self.start_backend():
            logger.error("Failed to start backend. Exiting.")
            return 1

        self.start_godot()

        logger.info("")
        logger.info("=" * 50)
        logger.info("System running. Press Ctrl+C to stop.")
        logger.info("Backend API: http://localhost:8000")
        logger.info("API Docs: http://localhost:8000/docs")
        logger.info("=" * 50)

        try:
            # Keep running until Godot closes or user interrupts
            if self.godot_process:
                self.godot_process.wait()
            else:
                # No Godot, just keep backend running
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

        return 0


def main():
    """Entry point for Godot GUI launcher."""
    launcher = GodotGUILauncher()
    sys.exit(launcher.run())


if __name__ == "__main__":
    main()
