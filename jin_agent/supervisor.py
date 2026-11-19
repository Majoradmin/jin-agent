"""Hosted entrypoint: web console + Telegram bot ek saath (auto-restart).

Bot long-polling karta hai aur TCP port nahi kholta — is liye hosted reverse
proxy (FadeHost/Render/Railway) ko 502 milta tha. Supervisor do child processes
chalata hai:

    1) python -m jin_agent serve   -> Agent Console, GET /api/health
    2) python -m jin_agent bot     -> Telegram long polling

Koi bhi child exit ho to exponential backoff ke saath dobara start hota hai.
SIGINT/SIGTERM par dono child terminate hote hain (orphan nahi). Koi nayi
dependency nahi — sirf stdlib subprocess.

Host binding: default loopback (127.0.0.1). Khulna sirf JIN_AGENT_HOST env /
``--host`` se — code ka default hamesha loopback rehta hai (security).
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import config, logging_setup

CONSOLE_ARGS = ("serve",)
BOT_ARGS = ("bot",)


def _log_file() -> Path:
    try:
        config.ensure_dirs()
        return config.data_dir() / "logs" / "supervisor.log"
    except OSError:
        return Path("supervisor.log")


def _emit(line: str) -> None:
    """Line ko process stdout par bhi mirror karo.

    Hosted consoles (FadeHost) sirf process ka stdout/stderr dekhte hain —
    `data/logs/*.log` unhein kabhi nahi dikhta. Is liye har line stdout par
    bhi jaye, warna console khali rehta hai aur lagta hai bot mar gaya.
    """
    try:
        sys.stdout.write(line)
        sys.stdout.flush()
    except Exception:
        pass


def _log(msg: str) -> None:
    line = "%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), msg)
    ok = logging_setup.bounded_append(_log_file(), line)
    _emit(line)
    if not ok:
        # Log dir na likhne par supervisor bhi anahq na ho.
        try:
            sys.stderr.write(line)
        except Exception:
            pass


def _pump(pipe, path: Path) -> None:
    """Child stdout/stderr ko bounded log me pump karo (har line par rotate)."""
    try:
        for raw in iter(pipe.readline, b""):
            text = raw.decode("utf-8", "replace")
            logging_setup.bounded_append(path, text)
            _emit(text)
    except Exception:
        pass
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def _python() -> str:
    exe = str(sys.executable or "python")
    if exe.lower().endswith("pythonw.exe"):
        cand = exe[: -len("pythonw.exe")] + "python.exe"
        if Path(cand).is_file():
            return cand
    return exe


def commands(port: int | None = None, host: str | None = None) -> dict:
    """Child commands: console (serve) + bot.

    Host sirf tab pass hota hai jab explicitly diya gaya ho — warna console
    apna loopback default use karti hai.
    """
    port = int(port if port is not None
                else (os.environ.get("PORT", "8766") or 8766))
    host = (host if host is not None
            else (os.environ.get("JIN_AGENT_HOST") or "")).strip()
    py = _python()
    console = [py, "-X", "utf8", "-u", "-m", "jin_agent", *CONSOLE_ARGS,
               "--port", str(port)]
    if host:
        console += ["--host", host]
    bot = [py, "-X", "utf8", "-u", "-m", "jin_agent", *BOT_ARGS]
    return {"console": console, "bot": bot}


def _spawn(cmd, log_name: str = "supervisor-child.log"):
    root = Path(__file__).resolve().parent.parent
    logp = _log_file().parent / log_name
    out = None
    try:
        logp.parent.mkdir(parents=True, exist_ok=True)
        logging_setup.rotate_if_needed(logp)
        out = subprocess.PIPE
    except OSError:
        out = None
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if out is None:
        proc = subprocess.Popen(
            cmd, cwd=str(root), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags)
        return proc
    proc = subprocess.Popen(
        cmd, cwd=str(root), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=flags)
    if proc.stdout is not None:
        threading.Thread(target=_pump, args=(proc.stdout, logp), daemon=True,
                         name="jin-child-log").start()
    return proc


def _terminate(proc) -> None:
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception:
        pass


def _install_signal_handlers(stop: threading.Event) -> None:
    def _handle(signum, frame):
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle)
        except (ValueError, OSError):
            pass  # main thread nahi, ya platform support nahi karta


def run(port=None, host=None, interval=10, max_backoff=300, stop=None,
        spawn=None, sleep_fn=None) -> int:
    """Console + bot child processes ko supervise karo.

    ``spawn``/``sleep_fn`` tests ke liye injection points hain.
    """
    interval = max(2, int(interval))
    stop = stop or threading.Event()
    spawn = spawn or _spawn
    sleep_fn = sleep_fn or time.sleep
    cmds = commands(port, host)
    procs = {"console": None, "bot": None}
    started = {"console": 0.0, "bot": 0.0}
    next_start = {"console": 0.0, "bot": 0.0}
    delays = {"console": interval, "bot": interval}
    _install_signal_handlers(stop)
    _log("supervisor: start (interval=%ds, max_backoff=%ds)"
         % (interval, max_backoff))
    try:
        while not stop.is_set():
            now = time.monotonic()
            for name in ("console", "bot"):
                proc = procs[name]
                if proc is not None and proc.poll() is not None:
                    code = proc.poll()
                    ran = now - started.get(name, now)
                    _log("supervisor: %s exited code=%s (ran %.0fs)"
                         % (name, code, ran))
                    procs[name] = None
                    # Lambi chali run = healthy; backoff reset karo.
                    if ran >= 60:
                        delays[name] = interval
                    next_start[name] = time.monotonic() + delays[name]
                    delays[name] = min(max_backoff, max(interval, delays[name] * 2))
                elif proc is None and now >= next_start[name] and not stop.is_set():
                    try:
                        procs[name] = spawn(cmds[name])
                        started[name] = time.monotonic()
                        _log("supervisor: %s started pid=%s"
                             % (name, getattr(procs[name], "pid", "?")))
                    except Exception as exc:
                        _log("supervisor: %s spawn failed: %s: %s"
                             % (name, type(exc).__name__, exc))
                        next_start[name] = time.monotonic() + delays[name]
                        delays[name] = min(max_backoff, max(interval, delays[name] * 2))
            # stop-aware sleep (1s slices)
            for _ in range(int(interval)):
                if stop.is_set():
                    break
                sleep_fn(1)
    finally:
        for name, proc in procs.items():
            _terminate(proc)
        _log("supervisor: stop")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="jin_agent supervisor",
        description="Console + Telegram bot ek saath (hosted deploy)")
    p.add_argument("--port", type=int,
                   default=int(os.environ.get("PORT", "8766") or 8766))
    p.add_argument("--host", default=os.environ.get("JIN_AGENT_HOST") or None,
                   help="console bind host — default loopback; hosted par "
                        "JIN_AGENT_HOST=0.0.0.0 set karein")
    p.add_argument("--interval", type=int, default=10)
    p.add_argument("--max-backoff", type=int, default=300)
    args = p.parse_args(argv)
    try:
        return run(port=args.port, host=args.host, interval=args.interval,
                   max_backoff=args.max_backoff)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
