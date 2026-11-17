"""P27 - stdlib in-memory per-host rate limiting with exponential backoff.

Free-tier endpoints (GitHub unauthenticated, NVD, Reddit) punish bursts. The
limiter is intentionally tiny and local:

  * one minimum interval per host (``host_min_interval`` seconds),
  * exponential backoff after a failure (``host_backoff_base`` doubling up to
    ``host_backoff_max``), reset on the next success,
  * no disk state, no threads, no external dependency.

``adapters.fetch()`` calls :func:`wait` before every request and
:func:`note_success` / :func:`note_failure` after it. Tests can inject ``now``
and use interval 0 to stay deterministic and sleep-free.
"""

from __future__ import annotations

import threading
import time
from urllib.parse import urlsplit

from . import util

_LOCK = threading.Lock()
_LAST: dict[str, float] = {}
_BACKOFF_UNTIL: dict[str, float] = {}
_FAILURES: dict[str, int] = {}

MAX_SLEEP_SECONDS = 5.0


class RateLimited(RuntimeError):
    """Host is in backoff - the call was skipped, not queued forever."""

    def __init__(self, host: str, retry_after: float):
        self.host = host
        self.retry_after = round(max(0.0, float(retry_after)), 2)
        super().__init__(f"{host} backoff active; retry after {self.retry_after}s")


def host_of(url: str) -> str:
    try:
        return (urlsplit(str(url or "")).hostname or "").lower().rstrip(".")
    except Exception:
        return ""


def interval(cfg: dict | None = None) -> float:
    return util.clamp((cfg or {}).get("host_min_interval"), 0.0, 60.0, 1.0)


def backoff_base(cfg: dict | None = None) -> float:
    return util.clamp((cfg or {}).get("host_backoff_base"), 0.0, 600.0, 5.0)


def backoff_max(cfg: dict | None = None) -> float:
    return util.clamp((cfg or {}).get("host_backoff_max"), 0.0, 3600.0, 300.0)


def delay_for(host: str, cfg: dict | None = None,
              now: float | None = None) -> float:
    """Seconds a caller would have to wait before touching ``host``."""
    if not host:
        return 0.0
    now = time.monotonic() if now is None else float(now)
    with _LOCK:
        last = _LAST.get(host)
        until = _BACKOFF_UNTIL.get(host, 0.0)
    delay = max(0.0, until - now)
    if last is not None:
        delay = max(delay, interval(cfg) - (now - last))
    return round(max(0.0, delay), 3)


def blocked_for(host: str, now: float | None = None) -> float:
    """Remaining hard backoff (0 when the host is not blocked)."""
    now = time.monotonic() if now is None else float(now)
    with _LOCK:
        until = _BACKOFF_UNTIL.get(host, 0.0)
    return round(max(0.0, until - now), 3)


def wait(host: str, cfg: dict | None = None) -> float:
    """Sleep for the minimum interval, or raise :class:`RateLimited` in backoff.

    Returns the seconds actually slept. Sleep is capped so a single source can
    never stall a whole parallel run; a real backoff skips the request instead.
    """
    if not host:
        return 0.0
    remaining = blocked_for(host)
    if remaining > 0:
        raise RateLimited(host, remaining)
    delay = min(delay_for(host, cfg), MAX_SLEEP_SECONDS)
    if delay > 0:
        time.sleep(delay)
    with _LOCK:
        _LAST[host] = time.monotonic()
    return round(delay, 3)


def note_success(host: str) -> None:
    if not host:
        return
    with _LOCK:
        _BACKOFF_UNTIL.pop(host, None)
        _FAILURES.pop(host, None)


def note_failure(host: str, cfg: dict | None = None) -> float:
    """Record a failure and return the applied backoff in seconds."""
    if not host:
        return 0.0
    base = backoff_base(cfg)
    cap = backoff_max(cfg)
    with _LOCK:
        count = int(_FAILURES.get(host, 0)) + 1
        _FAILURES[host] = count
        seconds = min(cap, base * (2 ** (count - 1))) if base > 0 else 0.0
        if seconds > 0:
            _BACKOFF_UNTIL[host] = time.monotonic() + seconds
    return round(seconds, 2)


def state() -> dict:
    """Small diagnostics snapshot (no secrets, hosts only)."""
    with _LOCK:
        return {"last": {k: round(v, 3) for k, v in sorted(_LAST.items())},
                "failures": {k: int(v) for k, v in sorted(_FAILURES.items())},
                "backoff_until": {k: round(v, 3)
                                  for k, v in sorted(_BACKOFF_UNTIL.items())}}


def reset() -> None:
    """Tests / new session: forget all hosts."""
    with _LOCK:
        _LAST.clear()
        _BACKOFF_UNTIL.clear()
        _FAILURES.clear()
