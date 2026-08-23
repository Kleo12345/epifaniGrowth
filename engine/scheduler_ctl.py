"""
Start/stop/check the Epifani scheduler daemon (core/scheduler.py).

Cross-platform replacement for start_scheduler.sh / stop_scheduler.sh — pure
Python via subprocess + a PID file, so it works the same on Linux, macOS, and
Windows. Also used by web_ui/dashboard.py for the Start/Stop buttons.

Usage:
  conda activate epifani-growth
  python scheduler_ctl.py start
  python scheduler_ctl.py stop
  python scheduler_ctl.py status
"""
import os
import signal
import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
PID_FILE   = ENGINE_DIR / "scheduler.pid"
LOG_FILE   = ENGINE_DIR / "scheduler.log"


def pid_alive(pid: int) -> bool:
    """Probe whether a PID is running, without side effects.
    NOTE: os.kill(pid, 0) is NOT a safe liveness probe on Windows — sig 0 is
    passed straight to TerminateProcess as the exit code, killing the process
    instead of just checking it. Use OpenProcess there instead."""
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    return True


def get_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
    except ValueError:
        return None
    return pid if pid_alive(pid) else None


def start() -> int:
    existing = get_pid()
    if existing is not None:
        print(f"Scheduler is already running (PID {existing}).")
        return existing

    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True

    with open(LOG_FILE, "ab") as log:
        proc = subprocess.Popen(
            [sys.executable, str(ENGINE_DIR / "core" / "scheduler.py")],
            cwd=str(ENGINE_DIR), stdout=log, stderr=log, stdin=subprocess.DEVNULL,
            **kwargs,
        )
    PID_FILE.write_text(str(proc.pid))
    print(f"Started (PID {proc.pid}). Log: {LOG_FILE}")
    return proc.pid


def stop() -> None:
    pid = get_pid()
    if pid is None:
        print("Scheduler is not running.")
        PID_FILE.unlink(missing_ok=True)
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        os.kill(pid, signal.SIGTERM)
    PID_FILE.unlink(missing_ok=True)
    print(f"Scheduler stopped (PID {pid}).")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "status":
        pid = get_pid()
        print(f"Running (PID {pid})" if pid else "Stopped")
    else:
        print(__doc__)
        sys.exit(1)
