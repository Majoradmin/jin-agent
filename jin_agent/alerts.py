"""Telegram Bot API alerts + commands (opt-in) and local alert log.

Only the official Bot API is used. No MTProto / TDLib / Telethon / userbot,
no login, no private chats, no historical public-channel scrape. The bot token
is never logged, returned by the API, or written into a report.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from . import config, policy, store, util

API_HOST = "https://api.telegram.org"


def configured(cfg: dict | None = None) -> bool:
    cfg = cfg or config.load()
    return bool(str(cfg.get("telegram_bot_token") or "").strip()
                and str(cfg.get("telegram_chat_id") or "").strip())


def _base(cfg: dict) -> str:
    return API_HOST + "/bot" + str(cfg["telegram_bot_token"]).strip()


def send_telegram(text: str, cfg: dict | None = None) -> dict:
    cfg = cfg or config.load()
    if not configured(cfg):
        return {"ok": False, "error": "Telegram token / chat id set nahi; local alert likha gaya."}
    url = _base(cfg) + "/sendMessage"
    ok, reason = policy.check_url(url, policy.adapter_hosts())
    if not ok:
        return {"ok": False, "error": reason}
    payload = json.dumps({
        "chat_id": str(cfg["telegram_chat_id"]).strip(),
        "text": util.truncate(text, 3800),
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read(200_000).decode("utf-8", "replace"))
        return {"ok": bool(data.get("ok")), "error": "" if data.get("ok") else "Bot API ne ok=false diya"}
    except Exception as exc:
        # Never include the URL (it contains the token) in the error.
        return {"ok": False, "error": f"{type(exc).__name__}: {util.truncate(str(exc), 140)}"}


def get_updates(cfg: dict | None = None, offset: int = 0, limit: int = 20) -> list[dict]:
    """Read inbound commands only. No channel history is scraped."""
    from . import adapters
    cfg = cfg or config.load()
    if not configured(cfg):
        return []
    url = (_base(cfg) + "/getUpdates?offset=" + str(int(offset)) +
           "&limit=" + str(int(limit)) + "&timeout=0")
    try:
        text = adapters.fetch(url, cfg)
        data = json.loads(text)
    except Exception:
        return []
    out = []
    for upd in (data.get("result") or []):
        msg = upd.get("message") or {}
        body = str(msg.get("text") or "").strip()
        if body.startswith("/"):
            out.append({"update_id": upd.get("update_id", 0),
                        "chat_id": str((msg.get("chat") or {}).get("id", "")),
                        "text": body[:200]})
    return out


def notify(text: str, cfg: dict | None = None) -> dict:
    """Always writes a LOCAL alert; sends to Telegram only when configured."""
    cfg = cfg or config.load()
    store.init_db()
    store.add_event("alert", util.truncate(text, 400))
    line = util.now_iso() + " " + util.truncate(text.replace("\n", " "), 500) + "\n"
    try:
        with open(config.data_dir() / "alerts.log", "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass
    sent = send_telegram(text, cfg)
    return {"local": True, "telegram": sent}


def handle_command(text: str, cfg: dict | None = None) -> str:
    """Safe inbound command surface: /status /digest /eval /help."""
    from . import evaluator, orchestrator
    cfg = cfg or config.load()
    cmd = str(text or "").strip().split()[0].lower() if str(text or "").strip() else "/help"
    if cmd == "/status":
        s = orchestrator.status(cfg)
        return (f"JIN Agent {s['version']} | FTS5: {s['fts5']} | "
                f"Items: {s['counts']['items']} | Reports: {s['counts']['reports']} | "
                f"LLM: {s['llm']['mode']}")
    if cmd == "/digest":
        out = orchestrator.digest(cfg)
        return "Daily digest tayyar: " + str((out.get("saved") or {}).get("md", ""))
    if cmd == "/eval":
        out = evaluator.run(live=False, save=True)
        return (f"Eval: {'PASS' if out['passed'] else 'REVIEW'} | "
                f"coverage {out['metrics']['coverage_pct']}% | "
                f"fabricated {out['metrics']['fabricated_citations']}")
    return ("Commands: /status, /digest, /eval, /help. "
            "Ye agent sirf legal public sources par kaam karta hai; "
            "koi bypass ya device write instruction nahi deta.")
