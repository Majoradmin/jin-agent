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
import urllib.error
from concurrent.futures import ThreadPoolExecutor
try:
    import socks  # PySocks
    _SOCKS_AVAILABLE = True
except ImportError:
    _SOCKS_AVAILABLE = False

from . import (VERSION, channels as channels_mod, config, orchestrator,
               policy, searchmemory as memory_mod, util)

SEND_CHUNK_LIMIT = 4096
POLL_TIMEOUT = 30
POLL_OFFSET = 0
MAX_COMMAND_LEN = 64
HELP_TEXT = (
    "Salam! Main aap ka JIN Agent hoon.\n\n"
    "/research <sawal> - agent research karo aur Roman Urdu report bhej do\n"
    "/stop - chal rahi research rok do\n"
    "/status - agent status\n"
    "/sources - legal source register\n"
    "/channels - aap ke saved channels (add + 1-click links)\n"
    "/addchannel <link> - channel save karo (post forward bhi kar sakte hain)\n"
    "/rmchannel <@handle> - channel archive karo\n"
    "/tgsearch <keyword> - saved channels ke ANDAR search\n"
    "/engines - Telegram search engines ke 1-click links\n"
    "/deep [keyword] - dark/deep web search engines ke links\n"
    "/memory - pehle use ho chuke sources (rounds)\n"
    "/help - yeh menu\n\n"
    "Har report ke baad bot poochta hai: mil gaya ya nahi. 'Nahi mila' par naye "
    "sources/channels try hote hain (purane skip). Policy SAHULAT-SAFE-SERVICE-v1; "
    "dark web links-only; Telegram public only."
)

# Sirf public preview (t.me/s + t.me/<handle>) - login/userbot nahi.
TG_SEARCH_ENGINES = [
    ("MotherSearch", "MotherSearchBot", "8M+ channels / 10B+ posts — sab se bara index"),
    ("Searchee", "SearcheeBot", "40 categories, inline mode — fast channel dhundne ke liye"),
    ("oSearch", "oSearchBot", "Channels, groups aur content search"),
    ("GlobalSearch", "GlobalSearchBot", "Multi-language search"),
    ("TgSearch", "tgsearchrobot", "Fast inline channel lookup"),
]
TG_ENGINES_WEB = [
    ("TGStat", "https://tgstat.com", "Sab se bada — analytics + keyword + posts"),
    ("Telemetr.io", "https://telemetr.io", "Channel ranking + competitor analysis"),
    ("Telegago", "https://telegago.com", "Google operators support — precise search"),
    ("TelegramChannels.me", "https://telegramchannels.me", "Category browse + keyword"),
    ("Tlgrm.eu", "https://tlgrm.eu", "EU-based fast channel search"),
    ("TLG.gr", "https://tlg.gr", "Quick no-frills search"),
    ("TStat.net", "https://tstat.net", "Advanced filter + spam detection"),
]
TG_ENGINES_NOTE = ("Telegram app ke search bar mein: MySearch, Argo Search, JISOU bhi mil jate hain.")

# Deep/dark web: {q} = URL-encoded keyword. Onion kabhi fetch nahi hota.
DEEP_ENGINES = [
    ("Ahmia (clearnet index)", "https://ahmia.fi/search/?q={q}",
     "Tor hidden services ka legal index - sirf links"),
    ("Ahmia (onion mirror)", "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={q}",
     "Tor browser zaroori - ahmia.fi ne khud verify kiya"),
    ("PubMed (NLM)", "https://pubmed.ncbi.nlm.nih.gov/?term={q}",
     "Medical/scientific database (deep web)"),
    ("OpenAlex", "https://openalex.org/works?search={q}",
     "Scholarly works database, no login"),
    ("Crossref", "https://search.crossref.org/?q={q}",
     "DOI metadata database"),
    ("Wayback Machine", "https://web.archive.org/web/*/{q}",
     "Deleted/archived pages"),
    ("Shodan (IoT search)", "https://www.shodan.io/search?query={q}",
     "Devices/services index - account chahiye"),
]



CMD_RE = re.compile(r"^/([A-Za-z0-9_]{1,20})(?:@[\w_]{1,20})?\s*(.*)$", re.S)
# Sirf akela link/handle -> /addchannel (normal sawal ko hijack na kare)
_LINK_ONLY_RE = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me)/(?:s/)?@?[A-Za-z0-9_]{3,40}/?", re.I)
_HANDLE_ONLY_RE = re.compile(r"@[A-Za-z0-9_]{3,40}")

# Global stop flag — /stop command set karta hai, research thread check karta hai
_stop_research = False


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


def forwarded_handle(msg: dict) -> str:
    """Channel post forward se channel handle (sirf asli channel origin).

    Bot API user ki subscriptions nahi padh sakta, is liye registration ka
    tareeqa: koi post forward karo -> handle yahan se nikalta hai.
    """
    if not isinstance(msg, dict):
        return ""
    origin = msg.get("forward_origin") or {}
    if str(origin.get("type") or "") == "channel":
        return channels_mod.clean_handle(
            (origin.get("chat") or {}).get("username") or "")
    old = msg.get("forward_from_chat") or {}
    if str(old.get("type") or "") == "channel":
        return channels_mod.clean_handle(old.get("username") or "")
    return ""


def format_channels(rows: list[dict]) -> str:
    """Saved channels + 1-click links (plain text, Telegram khud link banata hai)."""
    if not rows:
        return ("Koi channel save nahi hai.\n\n"
                "Add karne ke 2 tareeqe:\n"
                "1) Kisi bhi channel ka post yahan forward karein (khud add ho jayega)\n"
                "2) /addchannel https://t.me/channelname\n\n"
                "Sirf PUBLIC channels ke andar search ho sakti hai "
                "(private/invite-only preview nahi deta).")
    lines = [f"📡 Aap ke channels ({len(rows)}):", ""]
    for row in rows[:20]:
        handle = str(row.get("channel") or "")
        title = str(row.get("title") or "").strip()
        subs = str(row.get("subscribers") or "").strip()
        bits = [b for b in (title, (subs + " subs") if subs else "",
                            f"{row.get('post_count') or 0} posts") if b]
        lines.append(f"• @{handle}" + (f" — {' · '.join(bits)}" if bits else ""))
        lines.append(f"  https://t.me/{handle}")
    if len(rows) > 20:
        lines.append(f"... aur {len(rows) - 20} channels")
    lines.append("")
    lines.append("Andar search: /tgsearch <keyword>")
    return "\n".join(lines)


def format_tg_results(res: dict) -> str:
    """Channel-search result -> chhota readable Roman Urdu block."""
    query = str((res or {}).get("query") or "")
    items = (res or {}).get("items") or []
    total = len((res or {}).get("channels") or [])
    if not items:
        return (f'🔍 "{query}" aap ke channels ke andar nahi mila '
                f"({total} channels check kiye).\n\n"
                "Agla step:\n"
                "• Chhota keyword try karein (1-2 lafz)\n"
                "• /research <sawal> se web + Telegram search chala lein\n"
                "• Naye channels add karein: /addchannel <link>")
    lines = [f'🔍 Channel search: "{query}" — {len(items)} results', ""]
    for i, item in enumerate(items, 1):
        text = util.truncate(str(item.get("excerpt") or item.get("title") or ""),
                             220).replace("\n", " ").strip()
        lines.append(f"{i}. @{item.get('channel')} — {text}")
        lines.append(f"   {item.get('url')}")
        lines.append("")
    failed = (res or {}).get("failed") or []
    if failed:
        names = ", ".join("@" + str(f.get("channel")) for f in failed[:5])
        lines.append(f"⚠️ {len(failed)} channel reach nahi hua: {names}")
    return "\n".join(lines).strip()


def format_engines() -> str:
    lines = ["🔎 Telegram Search Engines", ""]
    lines.append("── Telegram Bots (app ke andar) ──")
    for name, handle, desc in TG_SEARCH_ENGINES:
        lines.append(f"• {name} — {desc}")
        lines.append(f"  https://t.me/{handle}")
    lines.append("")
    lines.append("── Web Search Engines ──")
    for name, url, desc in TG_ENGINES_WEB:
        lines.append(f"• {name} — {desc}")
        lines.append(f"  {url}")
    lines.append("")
    lines.append(TG_ENGINES_NOTE)
    return "\n".join(lines)


def format_deep(query: str = "") -> str:
    """Dark/deep web engines ke links (onion fetch NAHI hota)."""
    q = urllib.parse.quote(str(query or "").strip()[:150])
    lines = ["🕵️ Dark / Deep web search engines:", ""]
    for name, url, note in DEEP_ENGINES:
        if q:
            link = url.replace("{q}", q)
        else:
            base = url.split("?")[0].replace("{q}", "")
            link = base if base.endswith("/") else base
        lines.append(f"• {name}")
        lines.append(f"  {link}")
        lines.append(f"  {note}")
    lines.append("")
    lines.append("⚠️ " + policy.DARK_WEB_RULE)
    lines.append("Onion site khud kholne ke liye Tor Browser zaroori hai.")
    return "\n".join(lines)


def format_memory(rows: list[dict]) -> str:
    if not rows:
        return ("🧠 Memory khali hai. /research chalao ge to bot yaad rakhega "
                "kaunse engines aur channels use hue, taake agle round me "
                "wahi cheez dobara na dhoondhi jaye.")
    lines = ["🧠 Recent research memory:", ""]
    for row in rows:
        status = "✅ done" if row.get("status") == "done" else "🔁 active"
        lines.append(f"• {util.truncate(str(row.get('query') or ''), 90)}")
        lines.append(f"  Round {row.get('round_no')} · {status} · "
                     f"{len(row.get('used_sources') or [])} engines · "
                     f"{len(row.get('used_channels') or [])} channels")
    lines.append("")
    lines.append("Sirf 6 latest dikhte hain (DB me sab save hai).")
    return "\n".join(lines)




def _make_opener(cfg: dict | None = None):
    """
    Build a urllib opener with SOCKS5 proxy if configured.
    cfg keys: proxy_type (socks5/http), proxy_host, proxy_port, proxy_user, proxy_pass
    Falls back to direct if PySocks not installed or proxy not configured.
    """
    cfg = cfg or config.load()
    ptype = str(cfg.get("proxy_type") or "").strip().lower()
    phost = str(cfg.get("proxy_host") or "").strip()
    pport = int(cfg.get("proxy_port") or 0)

    if phost and pport and ptype == "socks5" and _SOCKS_AVAILABLE:
        puser = cfg.get("proxy_user") or None
        ppass = cfg.get("proxy_pass") or None
        socks.set_default_proxy(socks.SOCKS5, phost, pport, True, puser, ppass)
        import socket
        socket.socket = socks.socksocket
        return urllib.request.build_opener()

    if phost and pport and ptype == "http":
        proxy_url = f"http://{phost}:{pport}"
        proxy_handler = urllib.request.ProxyHandler({
            "http": proxy_url, "https": proxy_url
        })
        return urllib.request.build_opener(proxy_handler)

    return urllib.request.build_opener()


def _api(token: str, cfg: dict | None = None):
    """Tiny Bot API client (stdlib urllib) with optional proxy support."""
    opener = _make_opener(cfg)

    class _API:
        base = "https://api.telegram.org/bot" + str(token)

        def send(self, chat_id: int, text: str, buttons=None) -> dict:
            payload = {
                "chat_id": int(chat_id), "text": str(text),
                "disable_web_page_preview": True}
            if buttons:
                payload["reply_markup"] = {"inline_keyboard": buttons}
            body = json.dumps(payload).encode()
            req = urllib.request.Request(
                self.base + "/sendMessage", data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            with opener.open(req, timeout=60) as r:
                return json.loads(r.read().decode())

        def answer_callback(self, callback_id: str, text: str = "") -> dict:
            body = json.dumps({"callback_query_id": str(callback_id),
                               "text": str(text)[:200]}).encode()
            req = urllib.request.Request(
                self.base + "/answerCallbackQuery", data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            with opener.open(req, timeout=30) as r:
                return json.loads(r.read().decode())

        def get_updates(self, offset: int, timeout: int = POLL_TIMEOUT) -> list[dict]:
            body = json.dumps({"offset": int(offset), "timeout": int(timeout)}).encode()
            req = urllib.request.Request(
                self.base + "/getUpdates", data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            with opener.open(req, timeout=timeout + 10) as r:
                return json.loads(r.read().decode()).get("result") or []

    return _API()


# --------------------------------------------------------------------------
# Research → reply
# --------------------------------------------------------------------------

def research_markdown(query: str, cfg: dict | None = None, save: bool = True,
                      live: bool = True) -> str:
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


def format_channel_section(items: list[dict]) -> str:
    """Channel hits ko report ke aakhir me ek chhota section banao."""
    if not items:
        return ""
    lines = ["## Telegram Channels (aap ke saved)", ""]
    for i, item in enumerate(items[:8], 1):
        text = util.truncate(str(item.get("excerpt") or item.get("title") or ""),
                             200).replace("\n", " ").strip()
        lines.append(f"{i}. @{item.get('channel')} — {text}")
        lines.append(f"   {item.get('url')}")
    return "\n".join(lines)


def research_full(query: str, cfg: dict | None = None, save: bool = True,
                  live: bool = True, skip_sources=None, skip_channels=None) -> dict:
    """Web adapters + saved-channel search PARALLEL, ek hi markdown report.

    Returns ``{"ok", "markdown", "sources", "channels", "error"}``.
    ``skip_*`` = pichle rounds ki memory (wahi cheez dobara nahi dhoondhi jati).
    """
    cfg = cfg or config.load()
    skip_sources = [str(s) for s in (skip_sources or [])]
    skip_channels = [str(c) for c in (skip_channels or [])]
    q = str(query)[:4000]

    saved = [c for c in channels_mod.adapter_channels(cfg)
             if c not in skip_channels]
    pool = ThreadPoolExecutor(max_workers=2)
    try:
        f_web = pool.submit(orchestrator.run, q, live, 7, 25, None, cfg, save,
                            skip_sources)
        f_tg = pool.submit(channels_mod.search_posts, q, saved, cfg, 8)
        out = f_web.result(timeout=180)
        try:
            tg = f_tg.result(timeout=60)
        except Exception:
            tg = {"items": [], "channels": saved, "failed": []}
    except Exception as exc:
        return {"ok": False, "sources": [], "channels": [],
                "markdown": f"❌ Research error: {type(exc).__name__}: "
                            f"{util.truncate(str(exc), 300)}"}
    finally:
        pool.shutdown(wait=False)

    if out.get("blocked"):
        return {"ok": False, "sources": [], "channels": [],
                "markdown": "⛔ Request block hua policy ke hisaab se. Detail: "
                            + json.dumps(out.get("gate") or {}, ensure_ascii=False)}
    md = str((out.get("report") or {}).get("markdown")
             or (out.get("report") or {}).get("text")
             or "# Report nahi bana pa raha")
    section = format_channel_section(tg.get("items") or [])
    if section:
        md = md.rstrip() + "\n\n" + section + "\n"
    sources = [str(d.get("key")) for d in (out.get("diagnostics") or [])
               if int(d.get("count") or 0) > 0]
    return {"ok": True, "markdown": md, "sources": sources,
            "channels": list(tg.get("channels") or []), "error": ""}


def after_report_buttons(row_id: int) -> list[list[dict]]:
    return [[
        {"text": "✅ Mil gaya", "callback_data": f"mem:{int(row_id)}:done"},
        {"text": "🔁 Nahi mila — aur dhondo", "callback_data": f"mem:{int(row_id)}:more"},
    ]]


def parse_callback(data: str) -> tuple[int, str]:
    """``mem:<row_id>:<action>`` -> (row_id, action). Ghalat = (0, '')."""
    m = re.fullmatch(r"mem:(\d{1,12}):([a-z]{2,8})", str(data or "").strip())
    if not m:
        return 0, ""
    return int(m.group(1)), m.group(2)


def ask_after_report(row: dict, sources: int, channels: int) -> str:
    return ("❓ Aapko ye information mil gayi?\n\n"
            f"Round {row.get('round_no') or 1}: {sources} engines + "
            f"{channels} channels use hue (memory me save).\n"
            "Agar 'Nahi mila' dabayen to main naye sources/channels try karunga - "
            "jo use ho chuke hain wo skip ho jayenge.")



# --------------------------------------------------------------------------
# Command dispatch (chat -> action)
# --------------------------------------------------------------------------

def dispatch(chat_id: int, text: str, cfg: dict | None = None, api=None,
            research=None, probe=None, tg_search=None) -> dict:
    """Handle one private chat command. Returns {'ok':.., 'action':..}."""
    global _stop_research
    cfg = cfg or config.load()
    api = api or _api(str(cfg.get("telegram_bot_token") or ""), cfg)
    cmd, arg = parse_command(text)
    if cmd == "start":
        api.send(chat_id, HELP_TEXT)
        return {"ok": True, "action": "start"}
    if cmd == "help":
        api.send(chat_id, HELP_TEXT)
        return {"ok": True, "action": "help"}
    if cmd == "stop":
        _stop_research = True
        api.send(chat_id, "🛑 Research rok di gayi. Naya /research karne se phir shuru hoga.")
        return {"ok": True, "action": "stop"}
    if cmd == "status":
        api.send(chat_id, "Status: JIN Agent chal raha hai (policy " + str(cfg.get("policy_id") or "SAHULAT-SAFE-SERVICE-v1") + ").")
        return {"ok": True, "action": "status"}
    if cmd == "sources":
        api.send(chat_id, "Sources register open hai (22 official/legal sources). /research <sawal> se detail.")
        return {"ok": True, "action": "sources"}
    if cmd in ("channels", "tgsearch"):
        if cmd == "tgsearch" or arg:
            if not arg:
                api.send(chat_id, "Keyword likhein: /tgsearch firmware\n"
                                  "(ya /channels <keyword> - dono ek hi kaam karte hain)")
                return {"ok": False, "action": "tgsearch", "error": "query required"}
            try:
                api.send(chat_id, f'🔍 Channels ke andar search: "{arg}" ...')
            except Exception:
                pass
            try:
                res = (tg_search or channels_mod.search_posts)(arg, cfg=cfg)
            except Exception as exc:
                api.send(chat_id, f"❌ Channel search fail: {type(exc).__name__}: "
                                  f"{util.truncate(str(exc), 200)}")
                return {"ok": False, "action": "tgsearch", "error": "search failed"}
            for chunk in split_text(format_tg_results(res)):
                api.send(chat_id, chunk)
            return {"ok": True, "action": "tgsearch", "query": arg,
                    "count": len(res.get("items") or [])}
        rows = channels_mod.list_channels("active")
        for chunk in split_text(format_channels(rows)):
            api.send(chat_id, chunk)
        return {"ok": True, "action": "channels", "count": len(rows)}
    if cmd == "addchannel":
        handle = channels_mod.clean_handle(arg)
        if not handle:
            api.send(chat_id, "Link ya @username dein. Misal:\n"
                              "/addchannel https://t.me/durov\n"
                              "ya channel ka koi post yahan forward kar dein.")
            return {"ok": False, "action": "addchannel", "error": "handle required"}
        try:
            channels_mod.add_channel(handle, origin="manual",
                                     note="user ne bot se add kiya")
        except Exception as exc:
            api.send(chat_id, f"❌ Channel add nahi hua: {util.truncate(str(exc), 150)}")
            return {"ok": False, "action": "addchannel", "error": "add failed"}
        try:
            info = (probe or channels_mod.check_channel)(handle, cfg) or {}
        except Exception:
            info = {}
        alive = bool(info.get("alive"))
        title = str(info.get("title") or "").strip()
        subs = str(info.get("subscribers") or "").strip()
        bits = [b for b in (title, (subs + " subs") if subs else "",
                            f"{info.get('post_count') or 0} recent posts"
                            if alive else "public preview nahi mila") if b]
        head = "✅ Channel save ho gaya" if alive else \
               "⚠️ Channel save hua, magar public preview nahi mila"
        api.send(chat_id, f"{head}: @{handle}\n"
                          f"{' · '.join(bits)}\n"
                          f"🔗 https://t.me/{handle}\n\n"
                          f"Ab /tgsearch <keyword> se iske andar search karein.")
        return {"ok": True, "action": "addchannel", "channel": handle,
                "alive": alive}
    if cmd == "rmchannel":
        handle = channels_mod.clean_handle(arg)
        if not handle:
            api.send(chat_id, "Handle dein: /rmchannel @channelname")
            return {"ok": False, "action": "rmchannel", "error": "handle required"}
        try:
            channels_mod.remove_channel(handle)
        except Exception as exc:
            api.send(chat_id, f"❌ {util.truncate(str(exc), 150)}")
            return {"ok": False, "action": "rmchannel", "error": "not found"}
        api.send(chat_id, f"🗄️ @{handle} archive kar diya (delete nahi hua).")
        return {"ok": True, "action": "rmchannel", "channel": handle}
    if cmd == "engines":
        for chunk in split_text(format_engines()):
            api.send(chat_id, chunk)
        return {"ok": True, "action": "engines", "count": len(TG_SEARCH_ENGINES)}
    if cmd in ("deep", "darkweb"):
        for chunk in split_text(format_deep(arg)):
            api.send(chat_id, chunk)
        return {"ok": True, "action": "deep", "count": len(DEEP_ENGINES)}
    if cmd == "memory":
        rows = memory_mod.recent(chat_id, 6)
        for chunk in split_text(format_memory(rows)):
            api.send(chat_id, chunk)
        return {"ok": True, "action": "memory", "count": len(rows)}
    if cmd == "research":
        if not arg:
            api.send(chat_id, "Research ke liye query likhein: /research <sawal>")
            return {"ok": False, "action": "research", "error": "query required"}
        return _send_research(chat_id, arg, cfg=cfg, api=api, research=research)
    api.send(chat_id, "Maaf kijiye, yeh command samajh nahi aaya. /help use kijiye.")
    return {"ok": False, "action": "unknown", "error": "unknown command"}


def _send_research(chat_id: int, query: str, cfg: dict, api, research=None,
                   row_id: int | None = None, advance: bool = False) -> dict:
    """Research chalao -> report chunks -> 'mil gaya?' buttons + memory."""
    global _stop_research
    _stop_research = False
    used_sources: list[str] = []
    used_channels: list[str] = []
    round_no = 1
    if row_id:
        row = memory_mod.get(row_id) or {}
        used_sources = row.get("used_sources") or []
        used_channels = row.get("used_channels") or []
        round_no = int(row.get("round_no") or 1) + (1 if advance else 0)
    header = ("🔍 Research chal rahi hai... (30-60 seconds lag sakte hain)\n"
              "🛑 Rokne ke liye /stop likhein") if round_no <= 1 else \
             (f"🔁 Round {round_no}: naye sources/channels try ho rahe hain "
              f"({len(used_sources)} engines + {len(used_channels)} channels skip)...\n"
              "🛑 Rokne ke liye /stop likhein")
    try:
        api.send(chat_id, header)
    except Exception:
        pass

    result_box = [None]

    def _do_research():
        if _stop_research:
            return
        try:
            if research is None:
                result_box[0] = research_full(
                    query, cfg, skip_sources=used_sources,
                    skip_channels=used_channels)
            else:
                result_box[0] = research(query, cfg)
        except Exception as exc:
            result_box[0] = {"ok": False, "markdown": f"❌ Research error: "
                             f"{type(exc).__name__}: {util.truncate(str(exc), 250)}",
                             "sources": [], "channels": []}

    import threading
    t = threading.Thread(target=_do_research, daemon=True)
    t.start()
    t.join(timeout=150)
    if _stop_research:
        return {"ok": False, "action": "research", "error": "stopped by user"}
    if result_box[0] is None:
        api.send(chat_id, "⏱️ Research timeout ho gaya. Dobara try karein ya chota sawal likhein.")
        return {"ok": False, "action": "research", "error": "timeout"}

    out = result_box[0]
    if isinstance(out, dict):
        md = str(out.get("markdown") or "")
        sources = [str(s) for s in (out.get("sources") or [])]
        channels_used = [str(c) for c in (out.get("channels") or [])]
    else:
        md, sources, channels_used = str(out or ""), [], []
    if not md.strip():
        md = "❌ Report khali rahi. /research dobara try karein."

    chunks = split_text(md)
    for chunk in chunks:
        if _stop_research:
            api.send(chat_id, "🛑 Report rok di gayi.")
            break
        api.send(chat_id, chunk)

    # Memory: kaunse sources/channels is round me use hue
    try:
        if row_id:
            row = memory_mod.remember(row_id, sources, channels_used,
                                      advance=advance)
        else:
            row = memory_mod.begin(chat_id, query)
            row = memory_mod.remember(row["id"], sources, channels_used)
        row = row or {"id": 0, "round_no": round_no}
    except Exception:
        row = {"id": 0, "round_no": round_no}
    if row.get("id"):
        try:
            api.send(chat_id, ask_after_report(row, len(row.get("used_sources") or []),
                                               len(row.get("used_channels") or [])),
                     buttons=after_report_buttons(row["id"]))
        except Exception:
            pass
    _stop_research = True
    return {"ok": True, "action": "research", "query": query,
            "chunks": len(chunks), "round": row.get("round_no") or 1,
            "sources": len(sources), "channels": len(channels_used)}


def handle_callback(chat_id: int, data: str, cfg: dict | None = None, api=None,
                    research=None) -> dict:
    """Inline button: ✅ Mil gaya / 🔁 Nahi mila - aur dhondo."""
    cfg = cfg or config.load()
    api = api or _api(str(cfg.get("telegram_bot_token") or ""), cfg)
    row_id, action = parse_callback(data)
    if not row_id:
        api.send(chat_id, "Purana button hai. Naya /research karein.")
        return {"ok": False, "action": "callback", "error": "bad data"}
    row = memory_mod.get(row_id)
    if not row:
        api.send(chat_id, "Ye research memory me nahi mili. Naya /research karein.")
        return {"ok": False, "action": "callback", "error": "not found"}
    if action == "done":
        memory_mod.mark_done(row_id)
        api.send(chat_id, "✅ Theek hai, yaad rakh liya.\n"
                          f"Query: {util.truncate(row.get('query') or '', 200)}\n"
                          f"Rounds: {row.get('round_no')} · "
                          f"Used: {len(row.get('used_sources') or [])} engines, "
                          f"{len(row.get('used_channels') or [])} channels\n\n"
                          "Naya sawal: /research <sawal>")
        return {"ok": True, "action": "callback_done", "round": row.get("round_no")}
    if action == "more":
        if not (row.get("used_sources") or row.get("used_channels")):
            memory_mod.reset(row_id)
            row = memory_mod.get(row_id) or row
        return _send_research(chat_id, row.get("query") or "", cfg=cfg, api=api,
                              research=research, row_id=row_id, advance=True)
    if action == "reset":
        memory_mod.reset(row_id)
        api.send(chat_id, "♻️ Memory reset - sab sources dobara try honge.")
        return {"ok": True, "action": "callback_reset"}
    api.send(chat_id, "Samajh nahi aaya. Naya /research karein.")
    return {"ok": False, "action": "callback", "error": "unknown action"}



# --------------------------------------------------------------------------
# Long polling loop
# --------------------------------------------------------------------------

def run(token: str, cfg: dict | None = None, stop=None, api=None) -> None:
    """Long polling (getUpdates offset+timeout). Stop via threading.Event."""
    import threading as _threading
    cfg = cfg or config.load()
    api = api or _api(token, cfg)
    stop = stop or type("S", (), {"is_set": lambda self: False})()

    # --- STARTUP: purani queue clear karo (restart ke baad loop band) ---
    # Telegram ki pending queue ko skip karo: timeout=0 se sab pending updates
    # ek baar fetch karo aur unka offset aage le jao, process mat karo.
    try:
        _drain = api.get_updates(0, 0) or []
        if _drain:
            offset = int((_drain[-1].get("update_id") or 0)) + 1
        else:
            offset = int(POLL_OFFSET)
    except Exception:
        offset = int(POLL_OFFSET)
    # --- END STARTUP DRAIN ---

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
            if not text.startswith("/"):
                handle = forwarded_handle(msg)
                if handle:
                    text = "/addchannel @" + handle
                elif _LINK_ONLY_RE.fullmatch(text.strip()) or \
                        _HANDLE_ONLY_RE.fullmatch(text.strip()):
                    text = "/addchannel " + text.strip()
            if not text or text == "/addchannel ":
                continue
            if not is_owner(chat_id, cfg):
                continue
            # Fire-and-forget: dispatch thread ko block mat karo.
            # done.wait(timeout=150) hata diya -- yahi loop ka sabab tha.
            try:
                _threading.Thread(
                    target=dispatch,
                    args=(chat_id, text),
                    kwargs={"cfg": cfg, "api": api},
                    daemon=True,
                ).start()
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
