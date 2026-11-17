"""P25: Telegram Bot API front-end (long polling, chat allowlist, Roman Urdu replies).

Aap ka hukm: telegram bot sirf user tak access kare, dark web / deep web /
telegram / public-private channels se information lae, Roman Urdu report banao.

Boundary (Sahulat & Safe Service Policy / C12 / C13 / C27):
- Bot token sirf local config me (telegram_bot_token) - kabhi log/API response me.
- Chat allowlist: telegram_chat_id set hona chahiye (user ka chat id); sirf wohi
  chat commands process karti hai. Unset = sab se pehle allow-all (first-run state).
- Telegram channels: sirf PUBLIC t.me/s channels (P23 discovery + P16 adapter).
  Private group / userbot / MTProto / login scrape - koi nahi (C12 / C27).
- Research: orchestrator.run(...) → professional Roman Urdu markdown brief →
  Telegram reply (4096 char chunks).
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request

from . import VERSION, config, orchestrator, util

SEND_CHUNK_LIMIT = 4096
POLL_TIMEOUT = 30
POLL_OFFSET = 0
MAX_COMMAND_LEN = 64
HELP_TEXT = (
    "Salam! Main aap ka JIN Agent hoon.\n\n"
    "/start - shuru\n"
    "/research <sawal> - agent research karo aur Roman Urdu report bhej do\n"
    "/status - agent status\n"
    "/sources - legal source register\n"
    "/channels - telegram channel registry\n"
    "/help - yeh menu\n\n"
    "Research me LLM (free tier / local) use hoga; policy SAHULAT-SAFE-SERVICE-v1; "
    "dark web links-only; Telegram public only."
)

CMD_RE = re.compile(r"^/([A-Za-z0-9_]{1,20})(?:@[\w_]{1,20})?\s*(.*)$", re.S)


# --------------------------------------------------------------------------
# Pure helpers (testable)
# --------------------------------------------------------------------------

def parse_command(text: str) -> tuple[str, str]:
    """Return (cmd, arg). Unknown -> ('unknown', text)."""
    s = str(text or "").strip()
    m = CMD_RE.match(s)
    if not m:
        return "unknown", s
    return m.group(1).lower(), (m.group(2) or "").strip()


def split_text(text: str, limit: int = SEND_CHUNK_LIMIT) -> list[str]:
    """Telegram sendMessage limit (4096) par chunks."""
    out, buf = [], ""
    for para in str(text or "").split("\n"):
        add = para + "\n" if para else ""
        if len(buf) + len(add) > limit and buf.strip():
            out.append(buf)
            buf = add
        else:
            buf += add
    if buf.strip():
        out.append(buf)
    return [c for c in (x if x.endswith("\n") else x + "\n" for x in out) if c.strip()]


def is_owner(chat_id: int | None, cfg: dict | None = None) -> bool:
    """Sirf wohi chat allowed (telegram_chat_id). Unset = allow-all (first run)."""
    cfg = cfg or config.load()
    raw = str(cfg.get("telegram_chat_id") or "").strip()
    if not raw:
        return True
    try:
        return int(chat_id or -1) == int(raw)
    except ValueError:
        return False


def _api(token: str):
    """Tiny Bot API client (stdlib urllib)."""

    class _API:
        base = "https://api.telegram.org/bot" + str(token)

        def send(self, chat_id: int, text: str) -> dict:
            body = json.dumps({
                "chat_id": int(chat_id), "text": str(text),
                "disable_web_page_preview": True}).encode()
            req = urllib.request.Request(
                self.base + "/sendMessage", data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())

        def get_updates(self, offset: int, timeout: int = POLL_TIMEOUT) -> list[dict]:
            body = json.dumps({"offset": int(offset), "timeout": int(timeout)}).encode()
            req = urllib.request.Request(
                self.base + "/getUpdates", data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode()).get("result") or []

    return _API()


# --------------------------------------------------------------------------
# Research → reply
# --------------------------------------------------------------------------

def research_markdown(query: str, cfg: dict | None = None, save: bool = True,
                      live: bool = False) -> str:
    """Agent run karo, Roman Urdu markdown brief return karo (error -> text)."""
    cfg = cfg or config.load()
    try:
        out = orchestrator.run(str(query)[: 4000], live=live, limit=25, cfg=cfg, save=save)
        if out.get("blocked"):
            return "⛔ Request block hua policy ke hisaab se. Detail: " \
                   f"{json.dumps(out.get('gate') or {}, ensure_ascii=False)}"
        md = out.get("report") or {}
        return str(md.get("markdown") or md.get("text") or "# Report nahi bana pa raha")
    except Exception as exc:  # kabhi crash na ho
        return f"❌ Research error: {type(exc).__name__}: {util.truncate(str(exc), 300)}"


# --------------------------------------------------------------------------
# Command dispatch (chat -> action)
# --------------------------------------------------------------------------

def dispatch(chat_id: int, text: str, cfg: dict | None = None, api=None,
            research=None) -> dict:
    """Handle one private chat command. Returns {'ok':.., 'action':..}."""
    cfg = cfg or config.load()
    api = api or _api(str(cfg.get("telegram_bot_token") or ""))
    cmd, arg = parse_command(text)
    if cmd == "start":
        api.send(chat_id, HELP_TEXT)
        return {"ok": True, "action": "start"}
    if cmd == "help":
        api.send(chat_id, HELP_TEXT)
        return {"ok": True, "action": "help"}
    if cmd == "status":
        api.send(chat_id, "Status: JIN Agent chal raha hai (policy " + str(cfg.get("policy_id") or "SAHULAT-SAFE-SERVICE-v1") + ").")
        return {"ok": True, "action": "status"}
    if cmd == "sources":
        api.send(chat_id, "Sources register open hai (22 official/legal sources). /research <sawal> se detail.")
        return {"ok": True, "action": "sources"}
    if cmd == "channels":
        api.send(chat_id, "Channels registry open hai. Agent khud informative channels add karta hai (P23).")
        return {"ok": True, "action": "channels"}
    if cmd == "research":
        if not arg:
            api.send(chat_id, "Research ke liye query likhein: /research <sawal>")
            return {"ok": False, "action": "research", "error": "query required"}
        md = (research or research_markdown)(arg, cfg)
        chunks = split_text(md)
        for c in chunks:
            api.send(chat_id, c)
        return {"ok": True, "action": "research", "query": arg, "chunks": len(chunks)}
    api.send(chat_id, "Maaf kijiye, yeh command samajh nahi aaya. /help use kijiye.")
    return {"ok": False, "action": "unknown", "error": "unknown command"}


# --------------------------------------------------------------------------
# Long polling loop
# --------------------------------------------------------------------------

def run(token: str, cfg: dict | None = None, stop=None, api=None) -> None:
    """Long polling (getUpdates offset+timeout). Stop via threading.Event."""
    cfg = cfg or config.load()
    api = api or _api(token)
    stop = stop or type("S", (), {"is_set": lambda self: False})()
    offset = int(POLL_OFFSET)
    while not stop.is_set():
        try:
            updates = api.get_updates(offset, POLL_TIMEOUT) or []
        except Exception:
            # Network hiccup -> bot crash na ho, retry next cycle
            time.sleep(5)
            continue
        last_id = offset
        for u in updates:
            mid = int((u.get("update_id") or 0))
            last_id = max(last_id, mid)
            msg = u.get("message") or {}
            chat = msg.get("chat") or {}
            chat_id = int(chat.get("id") or 0)
            text = str(msg.get("text") or "")
            if not text:
                continue
            if not is_owner(chat_id, cfg):
                continue
            try:
                dispatch(chat_id, text, cfg, api=api)
            except Exception:
                time.sleep(2)
        offset = last_id + 1
        if stop.is_set():
            break


def status(cfg: dict | None = None) -> dict:
    cfg = cfg or config.load()
    return {
        "version": VERSION,
        "policy_id": "SAHULAT-SAFE-SERVICE-v1",
        "bot_token_set": bool(str(cfg.get("telegram_bot_token") or "").strip()),
        "chat_id_set": bool(str(cfg.get("telegram_chat_id") or "").strip()),
        "llm": cfg.get("llm") or {},
        "tor_mode": cfg.get("tor_mode") or "links_only",
    }
