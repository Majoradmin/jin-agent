"""Local configuration for JIN Agent. Python standard library only.

Secrets (Telegram bot token / LLM key) are stored in a local ``config.json``
and are NEVER returned by ``public()``, logged, or exported. Keeping that file
private is the operator's responsibility (open question O-TOKEN, see PHASES.md).
"""

from __future__ import annotations

import copy
import json
import os
import urllib.parse
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
    "channel_discovery_web": True,
    "channel_discovery_max_auto": 60,
    "channel_discovery_probe_per_run": 8,
    "channel_min_score": 4,
    "tor_mode": "links_only",
    # P27 retrieval++: per-source switches (explicit flags override adapter defaults)
    "source_enabled": {
        "reddit": True, "wikipedia": True, "wikidata": True,
        "gnews-topic": True, "wayback": True, "github-search": True,
        "nvd": True, "sitemap": True,
        "brave-search": False, "bing-search": False,
    },
    # Optional free-tier keys. Empty = adapter disabled, never an error.
    "brave_key": "",
    "bing_key": "",
    "github_token": "",
    "host_min_interval": 1.0,
    "host_backoff_base": 5.0,
    "host_backoff_max": 300.0,
    "sitemap_max_depth": 2,
    "sitemap_max_urls": 40,
    "sitemap_seed": "https://source.android.com/sitemap.xml",
    "reddit_subreddits": ["android", "AndroidQuestions", "firmware"],
    "snapshot_max_chars": 8000,
    "change_max_lines": 5,
    "near_dup_threshold": 0.72,
    "llm": {"provider": "off", "endpoint": "", "model": "", "key": "", "timeout": 30},
    "schedule": {
        "feeds_minutes": 15,
        "telegram_minutes": 30,
        "papers_minutes": 360,
        "digest_minutes": 1440,
        "watchlist_minutes": 5,
        "retention_minutes": 1440,
        "discovery_minutes": 720,
    },
    "retention_days": 90,
    "max_fetch_bytes": 2_000_000,
    "fetch_timeout": 10,
    "max_query_chars": 4000,
    "default_days": 7,
    "default_limit": 25,
    # Proxy settings (for regions where api.telegram.org is blocked)
    # proxy_type: "socks5" | "http" | "" (empty = no proxy)
    # For socks5: install PySocks first: pip install PySocks
    "proxy_type": "",
    "proxy_host": "",
    "proxy_port": 0,
    "proxy_user": "",
    "proxy_pass": "",
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
        raw = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in ("llm", "schedule", "assumptions", "source_enabled") and isinstance(value, dict):
                cfg[key].update(value)
            else:
                cfg[key] = value

    # Environment variable overrides (for cloud/Railway deploy)
    # Set these in Railway dashboard: Settings -> Variables
    env_map = {
        "TELEGRAM_BOT_TOKEN": "telegram_bot_token",
        "TELEGRAM_CHAT_ID": "telegram_chat_id",
        "GROQ_API_KEY": "llm.key",
        "LLM_PROVIDER": "llm.provider",
        "LLM_ENDPOINT": "llm.endpoint",
        "LLM_MODEL": "llm.model",
    }
    for env_key, cfg_key in env_map.items():
        val = os.environ.get(env_key, "").strip()
        if not val:
            continue
        if "." in cfg_key:
            section, field = cfg_key.split(".", 1)
            cfg.setdefault(section, {})[field] = val
        else:
            cfg[cfg_key] = val

    # Proxy fallback: hosted platforms (FadeHost/Railway/Render) aksar
    # HTTPS_PROXY / ALL_PROXY set karte hain. Agar config me proxy khali hai
    # to ye standard env vars apna lo — warna api.telegram.org blocked regions
    # me bot hamesha fail karta rahega (silent).
    if not str(cfg.get("proxy_type") or "").strip() and not str(cfg.get("proxy_host") or "").strip():
        raw = (os.environ.get("ALL_PROXY") or os.environ.get("HTTPS_PROXY")
               or os.environ.get("HTTP_PROXY") or os.environ.get("all_proxy")
               or os.environ.get("https_proxy") or "").strip()
        if raw:
            u = urllib.parse.urlparse(raw if "://" in raw else "http://" + raw)
            scheme = (u.scheme or "http").lower()
            ptype = "socks5" if "socks" in scheme else "http"
            cfg["proxy_type"] = ptype
            cfg["proxy_host"] = u.hostname or ""
            try:
                cfg["proxy_port"] = int(u.port or (1080 if ptype == "socks5" else 8080))
            except (TypeError, ValueError):
                cfg["proxy_port"] = 1080 if ptype == "socks5" else 8080
            if u.username:
                cfg["proxy_user"] = urllib.parse.unquote(u.username)
            if u.password:
                cfg["proxy_pass"] = urllib.parse.unquote(u.password)

    return cfg


def public(cfg: dict | None = None) -> dict:
    """Key-free view for the UI and API."""
    c = copy.deepcopy(cfg or load())
    c.setdefault("llm", {})["key"] = "***" if c["llm"].get("key") else ""
    c["telegram_bot_token"] = "***" if c.get("telegram_bot_token") else ""
    for key in ("brave_key", "bing_key", "github_token"):
        c[key] = "***" if c.get(key) else ""
    return c


def save(patch: dict) -> dict:
    """Merge a patch into the local config. Reject masked sentinel values."""
    cfg = load()
    patch = dict(patch or {})
    for key, value in patch.items():
        if value == "***":
            continue
        if key in ("llm", "schedule", "assumptions", "source_enabled") and isinstance(value, dict):
            # Masked sentinels must not be persisted inside nested sections either.
            cfg[key].update({k: v for k, v in value.items() if v != "***"})
        elif key in DEFAULT:
            cfg[key] = value
    ensure_dirs()
    tmp = config_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(config_path())
    return public(cfg)
