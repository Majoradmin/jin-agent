"""Bot supervisor (watchdog): bot crash / exit par auto-restart.

User ka hukm: "bot ko chalty rahna chiye tha na" — is liye ek supervisor
process bot ko child ke tor par chalata hai; exit hone par backoff ke saath
dobara start karta hai. Scheduled task / Run key se logon par khud start hota hai.

Boundaries: koi network call nahi, koi secret log nahi, sirf subprocess manage.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

from . import config

BOT_CMD = ("-X", "utf8", "-u", "-m", "jin_agent", "bot")


def _log_file() -> Path:
    try:
        config.ensure_dirs()
        return config.data_dir() / "logs" / "watchdog.log"
    except OSError:
        return Path("watchdog.log")


def _log(msg: str) -> None:
    line = "%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), msg)
    try:
        p = _log_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(line)
    except OSError:
        # Log dir na likhne par supervisor bhi anahq na ho.
        try:
            sys.stderr.write(line)
        except Exception:
            pass


def _python() -> str:
    exe = str(sys.executable or "python")
    if exe.lower().endswith("pythonw.exe"):
        cand = exe[: -len("pythonw.exe")] + "python.exe"
        if Path(cand).is_file():
            return cand
    return exe


def _spawn() -> subprocess.Popen:
    root = Path(__file__).resolve().parent.parent
    logp = _log_file().parent / "bot.log"
    try:
        logp.parent.mkdir(parents=True, exist_ok=True)
        out = open(logp, "a", encoding="utf-8", buffering=1)
    except OSError:
        out = subprocess.DEVNULL
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [_python(), *BOT_CMD],
        cwd=str(root),
        stdin=subprocess.DEVNULL,
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=flags,
    )


def run(interval: int = 10, max_backoff: int = 300, stop: threading.Event | None = None,
        spawn=_spawn) -> int:
    """Bot ko supervise karo; exit par restart (exponential backoff)."""
    interval = max(2, int(interval))
    stop = stop or threading.Event()
    delay = interval
    proc = None
    _log("watchdog: start (interval=%ds, max_backoff=%ds)" % (interval, max_backoff))
    try:
        while not stop.is_set():
            try:
                proc = spawn()
            except Exception as exc:  # spawn failure bhi handle
                _log("watchdog: spawn failed: %s: %s" % (type(exc).__name__, exc))
                proc = None
            else:
                _log("watchdog: bot started pid=%s" % getattr(proc, "pid", "?"))
                started = time.monotonic()
                try:
                    code = proc.wait()
                except KeyboardInterrupt:
                    _log("watchdog: interrupted, bot terminated")
                    stop.set()
                    break
                ran = time.monotonic() - started
                _log("watchdog: bot exited code=%s (ran %.0fs)" % (code, ran))
                # Lambi chali run = healthy; backoff reset karo (warna ek purani
                # crash ke baad agli crash 300s tak restart nahi hoti).
                if ran >= 60:
                    delay = interval
            # restart wait (stop-aware)
            waited = 0
            while waited < delay and not stop.is_set():
                time.sleep(1)
                waited += 1
            delay = min(max_backoff, max(interval, delay * 2))
    finally:
        # Ctrl+C / crash par child orphan na rahe.
        p = proc
        poll = getattr(p, "poll", None)
        if p is not None and callable(poll) and poll() is None:
            try:
                p.terminate()
                _log("watchdog: child terminate")
            except Exception:
                pass
    _log("watchdog: stop")
    return 0


def main(interval: int = 10, max_backoff: int = 300) -> int:
    try:
        return run(interval=interval, max_backoff=max_backoff)
    except KeyboardInterrupt:
        _log("watchdog: keyboard interrupt")
        return 0
