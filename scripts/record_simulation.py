import os
import subprocess
import time
import signal
import sys
from pathlib import Path

# Configuration
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
RECORDINGS_DIR = REPO_ROOT / "recordings"
VENV_PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
GODOT_EXE = REPO_ROOT / "Godot_v4.5.1-stable_win64.exe"
LAUNCH_SCRIPT = REPO_ROOT / "launch_godot_gui.py"
OUTPUT_FILE = RECORDINGS_DIR / "simulation_promo.mp4"
DONE_FILE = REPO_ROOT / "demo_done.tmp"

def main():
    if not RECORDINGS_DIR.exists():
        RECORDINGS_DIR.mkdir(parents=True)
    
    if DONE_FILE.exists():
        DONE_FILE.unlink()

    print("[RECORD] Preparing recording session...")
    
    # Environment for Godot Automation
    env = os.environ.copy()
    env["FBA_BENCH_DEMO_AUTOSTART"] = "true"
    env["FBA_BENCH_DEMO_AUTOQUIT"] = "true"
    env["FBA_BENCH_DEMO_DONE_FILE"] = str(DONE_FILE)
    env["FBA_BENCH_DEMO_CINEMATIC"] = "true"
    env["FBA_BENCH_DEMO_SPEED"] = "2.5"
    env["FBA_BENCH_DEMO_START_DELAY_SECONDS"] = "5.0"
    env["FBA_BENCH_DEMO_ENDCARD_HOLD_SECONDS"] = "8.0"
    env["FBA_BENCH_DEMO_SCENARIO"] = "Standard Operations (Tier 1)"
    env["FBA_BENCH_DEMO_AGENT"] = "minimax/minimax-m2.5"

    # Launch Backend and GUI
    print("[RECORD] Launching Simulation stack...")
    launch_cmd = [str(VENV_PYTHON), str(LAUNCH_SCRIPT), "--godot", str(GODOT_EXE)]
    gui_proc = subprocess.Popen(launch_cmd, env=env, cwd=str(REPO_ROOT))

    # Wait for the window to actually appear and settle
    print("[RECORD] Waiting for window 'FBA-Bench-GUI'...")
    time.sleep(8) 

    # Start ffmpeg
    # Using gdigrab to capture the window
    # Window title should match project.godot: "FBA-Bench-GUI"
    print(f"[RECORD] Starting ffmpeg capture to {OUTPUT_FILE}...")
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-f", "gdigrab",
        "-framerate", "60",
        "-i", "title=FBA-Bench-GUI (DEBUG)",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        str(OUTPUT_FILE)
    ]
    
    # Run ffmpeg in a separate process
    ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    print("[RECORD] Recording in progress. Monitoring for completion...")
    
    try:
        # Wait for the Godot process to finish (which happens when demo_autoquit triggers)
        while True:
            if DONE_FILE.exists():
                print("[RECORD] Simulation finished signal detected.")
                break
            if gui_proc.poll() is not None:
                print("[RECORD] GUI process terminated unexpectedly.")
                break
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("[RECORD] Interrupted by user.")

    print("[RECORD] Stopping ffmpeg...")
    # Cleanly stop ffmpeg by sending 'q' to its stdin
    ffmpeg_proc.communicate(input=b'q')
    
    if gui_proc.poll() is None:
        gui_proc.terminate()

    if DONE_FILE.exists():
        DONE_FILE.unlink()

    print(f"[RECORD] Success! Recording saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
