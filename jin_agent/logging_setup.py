"""P26 - structured JSON-lines logging (local file, rotated, redacted).

Har log line aik JSON object hai jo ``data/logs/agent.log`` mein jata hai; stdlib
``RotatingFileHandler`` rotation aur backup count khud sambhalta hai (koi
dependency nahi). Telegram bot token aur LLM key **kabhi** log nahi hotay:
``redact()`` message, fields aur exception text - sab par lagta hai. Sirf local
file, koi network log shipping nahi.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import config

LOGGER_ROOT = "jin_agent"
LOG_MAX_BYTES = 2_000_000
LOG_BACKUPS = 3
SECRET_TTL = 5.0

# Field names that must never reach disk, regardless of value shape.
SECRET_FIELDS = frozenset({
    "telegram_bot_token", "telegram_token", "bot_token", "token", "api_key",
    "apikey", "key", "secret", "password", "authorization",
    "github_token", "brave_key", "bing_key",
})

# Value patterns (bot token / OpenAI-style key / "token=..." dumps).
SECRET_PATTERNS = (
    re.compile(r"bot\d{6,}:[A-Za-z0-9_-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|bot[_-]?token|token|secret)\b"
               r"\s*[:=]\s*[\"']?[A-Za-z0-9_\-:.]{8,}"),
)

_LOCK = threading.Lock()
_SECRET_CACHE: dict = {"ts": 0.0, "values": ()}


def log_dir() -> Path:
    d = config.data_dir() / "logs"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Read-only data dir: logging degrade ho jati hai, run crash nahi hota.
        return config.data_dir()
    return d


def log_path() -> Path:
    return log_dir() / "agent.log"


def _collect_secrets(cfg: dict) -> tuple[str, ...]:
    values: list[str] = []
    token = str((cfg or {}).get("telegram_bot_token") or "").strip()
    if token:
        values.append(token)
    key = str(((cfg or {}).get("llm") or {}).get("key") or "").strip()
    if key:
        values.append(key)
    for field in ("github_token", "brave_key", "bing_key"):
        value = str((cfg or {}).get(field) or "").strip()
        if value:
            values.append(value)
    return tuple(values)


def secret_values(cfg: dict | None = None) -> tuple[str, ...]:
    """Configured token / key values (5 s cache) - exact-string redaction ke liye."""
    if cfg is not None:
        return _collect_secrets(cfg)
    now = time.monotonic()
    if now - _SECRET_CACHE["ts"] < SECRET_TTL:
        return _SECRET_CACHE["values"]
    try:
        values = _collect_secrets(config.load())
    except Exception:
        values = ()
    _SECRET_CACHE.update({"ts": now, "values": values})
    return values


def redact(value, secrets=None):
    """Recursive redaction: dict / list / str sab safe, baaki values untouched."""
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if str(key).strip().lower() in SECRET_FIELDS and str(item or "").strip():
                clean[key] = "***"
            else:
                clean[key] = redact(item, secrets)
        return clean
    if isinstance(value, (list, tuple)):
        return [redact(item, secrets) for item in value]
    if not isinstance(value, str):
        return value
    text = value
    for secret in (secrets if secrets is not None else secret_values()):
        if secret and len(secret) >= 6 and secret in text:
            text = text.replace(secret, "***")
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("***", text)
    return text


class JsonLineFormatter(logging.Formatter):
    """Aik line = aik JSON object. ``ts`` UTC ISO-8601 hota hai."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": redact(record.getMessage()),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict) and fields:
            payload["fields"] = redact(fields)
        if record.exc_info:
            payload["error"] = redact(self.formatException(record.exc_info))[:2000]
        return json.dumps(payload, ensure_ascii=False)


def _make_handler(path: Path) -> RotatingFileHandler:
    handler = RotatingFileHandler(str(path), maxBytes=LOG_MAX_BYTES,
                                  backupCount=LOG_BACKUPS, encoding="utf-8", delay=True)
    handler.setFormatter(JsonLineFormatter())
    handler._jin_path = str(path)  # type: ignore[attr-defined]
    return handler


def _rotate(path: Path, backups: int) -> None:
    """``supervisor.log`` -> ``.1`` -> ``.2`` ... (``.0`` nahi, backwards rotate)."""
    try:
        for i in range(backups - 1, 0, -1):
            src = path.with_name(path.name + f".{i}")
            dst = path.with_name(path.name + f".{i + 1}")
            if not src.exists():
                continue
            try:
                dst.unlink()
            except OSError:
                pass
            try:
                src.replace(dst)
            except OSError:
                pass
        path.replace(path.with_name(path.name + ".1"))
    except OSError:
        pass


def rotate_if_needed(path, max_bytes: int = LOG_MAX_BYTES,
                     backups: int = LOG_BACKUPS) -> bool:
    """File ``max_bytes`` se bara ho to rotate karo. Fail par False (crash nahi)."""
    p = Path(path)
    try:
        if not p.exists() or p.stat().st_size < max(0, int(max_bytes)):
            return False
    except OSError:
        return False
    _rotate(p, max(1, int(backups)))
    return True


def bounded_append(path, line: str, max_bytes: int = LOG_MAX_BYTES,
                   backups: int = LOG_BACKUPS) -> bool:
    """Size-capped append (default 2MB x 3) — plain-append logs ka lifetime hal.

    ``supervisor.log``, ``supervisor-child.log`` aur ``alerts.log`` pehle
    unbounded barte the. Ye writer rotation samet bounded rehta hai aur disk
    full hone par bhi run crash nahi karta.
    """
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    rotate_if_needed(p, max_bytes, backups)
    try:
        with open(p, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(line if str(line).endswith("\n") else str(line) + "\n")
        return True
    except OSError:
        return False


def _level(value=None) -> int:
    if isinstance(value, int):
        return value
    raw = str(value or os.environ.get("JIN_AGENT_LOG_LEVEL") or "").strip().upper()
    return getattr(logging, raw, logging.INFO) if raw else logging.INFO


def get_logger(name: str = "app", level=None) -> logging.Logger:
    """Named logger jo current ``data/logs/agent.log`` par likhta hai.

    Data dir badal jaye (tests) to purana handler hata kar naya lagta hai;
    handler duplicate nahi hota.
    """
    full = name if name.startswith(LOGGER_ROOT + ".") or name == LOGGER_ROOT \
        else f"{LOGGER_ROOT}.{name}"
    logger = logging.getLogger(full)
    logger.setLevel(_level(level))
    logger.propagate = False
    target = str(log_path())
    with _LOCK:
        for handler in list(logger.handlers):
            if getattr(handler, "_jin_path", "") == target:
                return logger
        for handler in list(logger.handlers):
            if getattr(handler, "_jin_path", None):
                logger.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass
        logger.addHandler(_make_handler(log_path()))
    return logger


def log(level, msg, logger: str = "app", **fields) -> None:
    """Chhota helper: ``log("info", "run done", items=4)``."""
    target = get_logger(logger)
    lvl = getattr(logging, str(level).upper(), logging.INFO) if isinstance(level, str) else int(level)
    target.log(lvl, msg, extra={"fields": fields} if fields else None)


def setup(level=None) -> logging.Logger:
    """Root package logger taiyar karo aur wapas do (idempotent)."""
    return get_logger("app", level=level)


def read_lines(limit: int = 200) -> list[dict]:
    """Aakhri ``limit`` log lines parse karke do (diagnostics ke liye)."""
    path = log_path()
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in raw:
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
    return out
