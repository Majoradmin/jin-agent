"""Local configuration for JIN Agent. Python standard library only.

Secrets (Telegram bot token / LLM key) are stored in a local ``config.json``
and are NEVER returned by ``public()``, logged, or exported. Keeping that file
private is the operator's responsibility (open question O-TOKEN, see PHASES.md).
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent

TOPICS = [
    "Mobile & Firmware", "Android", "iOS", "Security", "AI & Local LLM",
    "Hardware & Chipsets", "Tools & Reverse Engineering", "Telecom",
    "Business & Policy", "Science", "World", "Custom Watchlist",
]

# Assumptions for the 4 questions the opencode plan left open. These are
# documented, not silently guessed, and any of them can be changed in Settings.
ASSUMPTIONS = {
    "hardware": "CPU-only assumed; local LLM stays OFF until a model is installed.",
    "topics": "The plan's 12 default categories are enabled.",
    "telegram_channels": "No channels are pre-configured; add public channels in Settings.",
    "tor": "links_only - legal onion links are displayed, never fetched or crawled.",
}

DEFAULT = {
    "version": 1,
    "date_checked": "2026-11-14",
    "topics": list(TOPICS),
    "assumptions": dict(ASSUMPTIONS),
    "telegram_channels": [],
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "tor_mode": "links_only",
    "llm": {"provider": "off", "endpoint": "", "model": "", "key": "", "timeout": 30},
    "schedule": {
        "feeds_minutes": 15,
        "telegram_minutes": 30,
        "papers_minutes": 360,
        "digest_minutes": 1440,
        "watchlist_minutes": 5,
        "retention_minutes": 1440,
    },
    "retention_days": 90,
    "max_fetch_bytes": 2_000_000,
    "fetch_timeout": 10,
    "max_query_chars": 4000,
    "default_days": 7,
    "default_limit": 25,
}


def data_dir() -> Path:
    """Dynamic on purpose: tests point JIN_AGENT_DATA at a throwaway folder."""
    raw = os.environ.get("JIN_AGENT_DATA")
    return Path(raw) if raw else BASE / "data"


def ensure_dirs() -> Path:
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "reports").mkdir(exist_ok=True)
    (d / "backups").mkdir(exist_ok=True)
    return d


def config_path() -> Path:
    return data_dir() / "config.json"


def db_path() -> Path:
    return data_dir() / "jin_agent.db"


def reports_dir() -> Path:
    p = data_dir() / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def backups_dir() -> Path:
    p = data_dir() / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def load() -> dict:
    cfg = copy.deepcopy(DEFAULT)
    try:
        raw = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cfg
    if not isinstance(raw, dict):
        return cfg
    for key, value in raw.items():
        if key in ("llm", "schedule", "assumptions") and isinstance(value, dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    return cfg


def public(cfg: dict | None = None) -> dict:
    """Key-free view for the UI and API."""
    c = copy.deepcopy(cfg or load())
    c.setdefault("llm", {})["key"] = "***" if c["llm"].get("key") else ""
    c["telegram_bot_token"] = "***" if c.get("telegram_bot_token") else ""
    return c


def save(patch: dict) -> dict:
    """Merge a patch into the local config. Reject masked sentinel values."""
    cfg = load()
    patch = dict(patch or {})
    for key, value in patch.items():
        if value == "***":
            continue
        if key in ("llm", "schedule", "assumptions") and isinstance(value, dict):
            # Masked sentinels must not be persisted inside nested sections either.
            cfg[key].update({k: v for k, v in value.items() if v != "***"})
        elif key in DEFAULT:
            cfg[key] = value
    ensure_dirs()
    tmp = config_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(config_path())
    return public(cfg)
