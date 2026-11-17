"""P26 - in-memory metrics: counters, gauges aur latency p50/p95.

Thread-safe (aik ``threading.Lock``), stdlib only, koi external dep nahi. Summary
``data/metrics.json`` mein **best-effort** likhi jati hai: disk write fail ho to
run crash nahi hota, sirf in-memory numbers zinda rehte hain. Yahan koi secret
(token / API key) kabhi nahi aata.
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from pathlib import Path

from . import config, util

COUNTERS = ("queries_total", "runs_ok", "runs_blocked", "fetch_errors",
            "reports_total", "evals_total", "llm_calls", "rate_limited")
LATENCY_NAMES = ("run", "fetch", "eval")
MAX_SAMPLES = 500
PERSIST_INTERVAL = 5.0

_LOCK = threading.Lock()
_COUNTERS: dict[str, int] = {k: 0 for k in COUNTERS}
_GAUGES: dict[str, float] = {}
_SAMPLES: dict[str, deque] = {k: deque(maxlen=MAX_SAMPLES) for k in LATENCY_NAMES}
_LAST_PERSIST = 0.0


def summary_path() -> Path:
    return config.data_dir() / "metrics.json"


def inc(name: str, amount: int = 1) -> int:
    """Counter barhao (default +1) aur naya value wapas do."""
    step = int(amount)
    with _LOCK:
        _COUNTERS[name] = int(_COUNTERS.get(name, 0)) + step
        value = _COUNTERS[name]
    _maybe_persist()
    return value


def get(name: str) -> int:
    with _LOCK:
        return int(_COUNTERS.get(name, 0))


def counters() -> dict:
    with _LOCK:
        return dict(_COUNTERS)


def set_gauge(name: str, value) -> None:
    """Aakhri value wala naap (e.g. items_last_run)."""
    try:
        clean = float(value)
    except (TypeError, ValueError):
        return
    with _LOCK:
        _GAUGES[str(name)] = clean
    _maybe_persist()


def gauges() -> dict:
    with _LOCK:
        return dict(_GAUGES)


def observe(name: str, ms) -> None:
    """Latency sample (milliseconds) record karo; purane samples bounded hain."""
    try:
        value = max(0.0, float(ms))
    except (TypeError, ValueError):
        return
    with _LOCK:
        bucket = _SAMPLES.setdefault(str(name), deque(maxlen=MAX_SAMPLES))
        bucket.append(value)
    _maybe_persist()


def percentile(values, pct: float) -> float:
    """Nearest-rank percentile (0-100). Khaali list par 0.0 - jhoota number nahi."""
    data = sorted(float(v) for v in (values or []) if v is not None)
    if not data:
        return 0.0
    if len(data) == 1:
        return round(data[0], 1)
    idx = int(round((float(pct) / 100.0) * (len(data) - 1)))
    return round(data[max(0, min(len(data) - 1, idx))], 1)


def p50(values) -> float:
    return percentile(values, 50)


def p95(values) -> float:
    return percentile(values, 95)


def latency(name: str) -> dict:
    with _LOCK:
        values = list(_SAMPLES.get(str(name)) or ())
    if not values:
        return {"count": 0, "p50_ms": 0.0, "p95_ms": 0.0, "avg_ms": 0.0, "max_ms": 0.0}
    return {"count": len(values), "p50_ms": p50(values), "p95_ms": p95(values),
            "avg_ms": round(sum(values) / len(values), 1),
            "max_ms": round(max(values), 1)}


def snapshot() -> dict:
    with _LOCK:
        sample_names = sorted(_SAMPLES)
    return {"ts": util.now_iso(), "counters": counters(), "gauges": gauges(),
            "latency": {name: latency(name) for name in sample_names}}


def compact() -> dict:
    """Status payload ke liye chhota block (koi raw sample list nahi)."""
    run = latency("run")
    return {"counters": counters(), "run_p50_ms": run["p50_ms"],
            "run_p95_ms": run["p95_ms"], "latency_samples": run["count"],
            "gauges": gauges()}


def persist(snapshot_data: dict | None = None) -> str:
    """Summary ko ``data/metrics.json`` mein likho. Best-effort: fail par ``""``."""
    payload = snapshot_data if snapshot_data is not None else snapshot()
    try:
        config.ensure_dirs()
        path = summary_path()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return str(path)
    except (OSError, TypeError, ValueError):
        return ""


def _maybe_persist() -> None:
    """Throttled auto-persist - har counter par disk hit na ho."""
    global _LAST_PERSIST
    now = time.monotonic()
    with _LOCK:
        if now - _LAST_PERSIST < PERSIST_INTERVAL:
            return
        _LAST_PERSIST = now
    persist()


def reset(clear_samples: bool = True) -> None:
    """Tests / naye session ke liye counters zero karo (files ko chheda nahi jata)."""
    global _LAST_PERSIST
    with _LOCK:
        for key in list(_COUNTERS):
            _COUNTERS[key] = 0
        _GAUGES.clear()
        if clear_samples:
            for key in list(_SAMPLES):
                _SAMPLES[key].clear()
        _LAST_PERSIST = 0.0
