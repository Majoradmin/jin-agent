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

import contextlib
import json
import os
import re
import socket
import threading
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

from . import (VERSION, channels as channels_mod, config, llm, orchestrator,
               policy, searchmemory as memory_mod, util)


class BotAPIError(RuntimeError):
    """Telegram ne ok:false wala jawab bheja (409 conflict, 429 flood, 400)."""


SEND_CHUNK_LIMIT = 4096
POLL_TIMEOUT = 30
POLL_OFFSET = 0
MAX_COMMAND_LEN = 64

# Telegram ek hi chat par ~1 message/second ki limit rakhta hai. Chunks ke
# darmiyan chhota intezar (second) 429 flood rokta hai. 0 = intezar band.
SEND_DELAY = max(0.0, float(os.environ.get("JIN_AGENT_SEND_DELAY") or 0.5))


def _telegram_retry_after(exc: urllib.error.HTTPError) -> int:
    """Telegram 429 ke jawab se retry_after (second) nikalo; na ho to 0."""
    try:
        data = json.loads(exc.read().decode())
        ra = (data.get("parameters") or {}).get("retry_after")
        if ra:
            return max(1, int(ra))
    except Exception:
        pass
    try:
        hdr = exc.headers.get("Retry-After") if exc.headers else None
        if hdr:
            return max(1, int(hdr))
    except Exception:
        pass
    return 0

# Per-update worker pool: har update ke liye naya thread kholna unbounded hota
# hai (telegram flood par thread storm). Is liye pool bounded hai. Default
# chhota rakha hai taake ek waqt me zyada research parallel na chale; env
# JIN_AGENT_UPDATE_WORKERS se barha sakte hain.
DEFAULT_UPDATE_WORKERS = 2
MAX_UPDATE_WORKERS = 16
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

# Global stop flag — /stop command set karta hai, research thread check karti hai.
# Sirf bool se kaam nahi chalta: do concurrent /research (ya research + /stop)
# race karte the. Is liye session id + lock:
#   * _send_research lock ke andar naya session banata hai.
#   * /stop bina lock kiye session invalidate karta hai (running research foran ruk ti hai).
#   * purana session ka koi hissa (thread/send) check karke apna kaam chhod deta hai.
_stop_research = False
_research_lock = threading.Lock()
_research_session = 0
_research_threads: set[threading.Thread] = set()
_research_threads_lock = threading.Lock()
_SOCKS_SCOPE_LOCK = threading.Lock()


def update_workers() -> int:
    """Per-update thread pool size (env JIN_AGENT_UPDATE_WORKERS, default 2)."""
    raw = str(os.environ.get("JIN_AGENT_UPDATE_WORKERS", "") or "").strip()
    if not raw:
        return DEFAULT_UPDATE_WORKERS
    try:
        n = int(raw)
    except (TypeError, ValueError):
        print(f"[bot] JIN_AGENT_UPDATE_WORKERS ghalat ({raw!r}) — "
              f"default {DEFAULT_UPDATE_WORKERS}", flush=True)
        return DEFAULT_UPDATE_WORKERS
    return max(1, min(MAX_UPDATE_WORKERS, n))


def max_poll_failures() -> int:
    """Lagataar poll failures ki cap (env JIN_AGENT_MAX_POLL_FAILURES).

    0 = unlimited (purana behaviour). Positive N = N failures ke baad process
    exit, taake supervisor/watchdog restart kar sake.
    """
    raw = str(os.environ.get("JIN_AGENT_MAX_POLL_FAILURES", "0") or "0").strip()
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        print(f"[bot] JIN_AGENT_MAX_POLL_FAILURES ghalat ({raw!r}) — "
              f"0 (unlimited) mana", flush=True)
        return 0


def _session_active(session: int) -> bool:
    """Kya ye research session abhi bhi chal raha hai?"""
    return session == _research_session and not _stop_research


def _register_research_thread(t: threading.Thread) -> None:
    with _research_threads_lock:
        _research_threads.add(t)


def _unregister_research_thread(t: threading.Thread) -> None:
    with _research_threads_lock:
        _research_threads.discard(t)


def _active_research_threads() -> list[threading.Thread]:
    with _research_threads_lock:
        return list(_research_threads)


def _cancel_research(join_timeout: float = 1.0) -> None:
    """Running research session ko roko: session invalidate + threads join.

    Join sirf chhota timeout rakhta hai — orchestrator ke andar network call
    ko beech me nahi kaata, magar session invalidate hone se research apna
    baaki kaam (report banana/bhejna) chhod deta hai. Threads daemon hain,
    is liye process exit bhi safe hai.
    """
    global _stop_research, _research_session
    _stop_research = True
    _research_session += 1
    me = threading.current_thread()
    for t in _active_research_threads():
        if t is me or not t.is_alive():
            continue
        t.join(timeout=join_timeout)



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
        # Aik hi lambri line (bina newline) bhi todi jaye, warna Telegram
        # "message too long" (400) deta hai.
        while len(add) > limit:
            if buf.strip():
                out.append(buf)
                buf = ""
            out.append(add[:limit])
            add = add[limit:]
        if len(buf) + len(add) > limit and buf.strip():
            out.append(buf)
            buf = add
        else:
            buf += add
    if buf.strip():
        out.append(buf)
    raw = [c for c in (x if x.endswith("\n") else x + "\n" for x in out) if c.strip()]
    # trailing newline add hone ke baad bhi har chunk limit ke andar ho.
    final: list[str] = []
    for c in raw:
        while len(c) > limit:
            final.append(c[:limit])
            c = c[limit:]
        if c.strip():
            final.append(c)
    return final


def send_chunks(api, chat_id: int, text: str, delay: float | None = None) -> int:
    """Text ko Telegram chunks me bhejo, har chunk ke baad chhota intezar.

    429 flood (FadeHost console par thread storm) ka asli hal: chunks ek ke
    baad ek bina waqt ke. Return: bheje gaye chunks ki tadad.
    """
    d = SEND_DELAY if delay is None else max(0.0, float(delay))
    sent = 0
    for i, chunk in enumerate(split_text(text)):
        if i and d > 0:
            time.sleep(d)
        api.send(chat_id, chunk)
        sent += 1
    return sent


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




def _socks5_target(cfg: dict | None = None):
    """(host, port, user, pass) agar SOCKS5 configured hai, warna None."""
    cfg = cfg or config.load()
    ptype = str(cfg.get("proxy_type") or "").strip().lower()
    phost = str(cfg.get("proxy_host") or "").strip()
    try:
        pport = int(cfg.get("proxy_port") or 0)
    except (TypeError, ValueError):
        return None
    if phost and pport and ptype == "socks5":
        return (phost, pport, cfg.get("proxy_user") or None,
                cfg.get("proxy_pass") or None)
    return None


@contextlib.contextmanager
def _socks_scope(cfg: dict | None = None):
    """SOCKS5 ko SIRF is HTTP call tak scope karo (process-global nahi).

    Purana code `socket.socket = socks.socksocket` globally patch karta tha —
    us se poora process (console ke HTTP handler bhi) SOCKS use karta tha.
    Ab patch sirf `opener.open()` ke dauran hota hai, aur lock ki wajah se
    do concurrent calls race nahi karti; finally me asli socket restore hota hai.
    """
    target = _socks5_target(cfg) if _SOCKS_AVAILABLE else None
    if not target:
        yield
        return
    with _SOCKS_SCOPE_LOCK:
        orig_socket = socket.socket
        socks.set_default_proxy(socks.SOCKS5, target[0], target[1], True,
                                target[2], target[3])
        socket.socket = socks.socksocket
        try:
            yield
        finally:
            socket.socket = orig_socket
            try:
                socks.set_default_proxy()  # global default wapas saaf
            except Exception:
                pass


def _make_opener(cfg: dict | None = None):
    """
    Build a urllib opener with SOCKS5 proxy if configured.
    cfg keys: proxy_type (socks5/http), proxy_host, proxy_port, proxy_user, proxy_pass
    Falls back to direct if PySocks not installed or proxy not configured.

    SOCKS5 ke liye yahan koi global socket patch NAHI hota — patch `_socks_scope`
    ke andar `_post` ke waqt hota hai (sirf us HTTP call par).
    """
    cfg = cfg or config.load()
    ptype = str(cfg.get("proxy_type") or "").strip().lower()
    phost = str(cfg.get("proxy_host") or "").strip()
    try:
        pport = int(cfg.get("proxy_port") or 0)
    except (TypeError, ValueError):
        print(f"[bot] proxy_port ghalat ({cfg.get('proxy_port')!r}) — direct connection",
              flush=True)
        pport = 0

    if phost and pport and ptype not in ("socks5", "http"):
        # Unsupported proxy type (socks4/socks5h/typo) — pehle silent direct tha,
        # region-block me matlab connection bina satarkhuseed direct jati thi.
        print(f"[bot] proxy_type '{ptype}' supported nahi (socks5/http) — direct connection",
              flush=True)
        return urllib.request.build_opener()

    if phost and pport and ptype == "socks5":
        if not _SOCKS_AVAILABLE:
            print("[bot] SOCKS5 configure hai magar PySocks nahi hai — direct connection",
                  flush=True)
        return urllib.request.build_opener()

    if phost and pport and ptype == "http":
        puser = cfg.get("proxy_user") or ""
        ppass = cfg.get("proxy_pass") or ""
        creds = ""
        if puser:
            creds = urllib.parse.quote(str(puser), safe="")
            if ppass:
                creds += ":" + urllib.parse.quote(str(ppass), safe="")
            creds += "@"
        proxy_url = f"http://{creds}{phost}:{pport}"
        proxy_handler = urllib.request.ProxyHandler({
            "http": proxy_url, "https": proxy_url
        })
        return urllib.request.build_opener(proxy_handler)

    return urllib.request.build_opener()


def _api(token: str, cfg: dict | None = None):
    """Tiny Bot API client (stdlib urllib) with optional proxy support."""
    cfg = cfg or config.load()
    opener = _make_opener(cfg)

    class _API:
        base = "https://api.telegram.org/bot" + str(token)

        def _post(self, path: str, payload: dict, timeout: int) -> dict:
            body = json.dumps(payload).encode()
            req = urllib.request.Request(
                self.base + path, data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            # Telegram rate limit (429) par retry_after se dobara koshish. Pehle
            # ye HTTPError ban kar thread ko mar deta tha (FadeHost console log:
            # "HTTP Error 429: Too Many Requests" -> Thread-278/280/287 storm).
            for attempt in range(1, 4):
                try:
                    with _socks_scope(cfg):
                        with opener.open(req, timeout=timeout) as r:
                            return json.loads(r.read().decode())
                except urllib.error.HTTPError as exc:
                    if exc.code != 429 or attempt >= 3:
                        raise
                    wait = _telegram_retry_after(exc) or min(5 * attempt, 60)
                    print(f"[bot] Telegram 429 (rate limit) — {wait}s baad retry "
                          f"({attempt}/2)", flush=True)
                    time.sleep(wait)
            return {}

        def _checked(self, res: dict, what: str) -> dict:
            # Telegram ok:false (409 conflict, 429 flood, 400) pehle ignore hota
            # tha -> generic exception -> backoff. Ab saaf, named error.
            if not res.get("ok"):
                code = res.get("error_code")
                desc = str(res.get("description") or "")
                raise BotAPIError(f"{what}: {code} {desc}".strip())
            return res

        def send(self, chat_id: int, text: str, buttons=None) -> dict:
            payload = {
                "chat_id": int(chat_id), "text": str(text),
                "disable_web_page_preview": True}
            if buttons:
                payload["reply_markup"] = {"inline_keyboard": buttons}
            return self._checked(self._post("/sendMessage", payload, 60), "sendMessage")

        def answer_callback(self, callback_id: str, text: str = "") -> dict:
            payload = {"callback_query_id": str(callback_id),
                       "text": str(text)[:200]}
            return self._checked(self._post("/answerCallbackQuery", payload, 30),
                                 "answerCallbackQuery")

        def get_updates(self, offset: int, timeout: int = POLL_TIMEOUT) -> list[dict]:
            res = self._checked(
                self._post("/getUpdates",
                           {"offset": int(offset), "timeout": int(timeout)},
                           timeout + 10),
                "getUpdates")
            return res.get("result") or []

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


def format_channel_section(items: list[dict], failed: list | None = None) -> str:
    """Channel hits ko report ke aakhir me ek chhota section banao."""
    if not items and not failed:
        return ""
    lines = ["## Telegram Channels (aap ke saved)", ""]
    for i, item in enumerate(items[:8], 1):
        text = util.truncate(str(item.get("excerpt") or item.get("title") or ""),
                             200).replace("\n", " ").strip()
        lines.append(f"{i}. @{item.get('channel')} — {text}")
        lines.append(f"   {item.get('url')}")
    if failed:
        # Pehle errors chhupaye jate the — user ko report ke baghair koi warning
        # nahi milta tha.
        lines.append("")
        lines.append("⚠️ Channel search fail: " + ", ".join(str(c) for c in failed[:5]))
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
        except Exception as exc:
            print(f"[bot] channel search fail ({type(exc).__name__}: {exc})", flush=True)
            tg = {"items": [], "channels": saved, "failed": list(saved),
                  "error": f"{type(exc).__name__}: {util.truncate(str(exc), 200)}"}
    except Exception as exc:
        return {"ok": False, "sources": [], "channels": [],
                "markdown": f"❌ Research error: {type(exc).__name__}: "
                            f"{util.truncate(str(exc), 300)}"}
    finally:
        try:
            pool.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # Python < 3.9
            pool.shutdown(wait=False)

    if out.get("blocked"):
        return {"ok": False, "sources": [], "channels": [],
                "markdown": "⛔ Request block hua policy ke hisaab se. Detail: "
                            + json.dumps(out.get("gate") or {}, ensure_ascii=False)}
    md = str((out.get("report") or {}).get("markdown")
             or (out.get("report") or {}).get("text")
             or "# Report nahi bana pa raha")
    section = format_channel_section(tg.get("items") or [], tg.get("failed"))
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
        # Pehle session invalidate karo (running research turant apna kaam chhod
        # deti hai), phir khabar bhejo. Lock ki zaroorat nahi — isi liye /stop
        # research ke chalne ke dauran bhi foran kaam karta hai.
        _cancel_research()
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
            send_chunks(api, chat_id, format_tg_results(res))
            return {"ok": True, "action": "tgsearch", "query": arg,
                    "count": len(res.get("items") or [])}
        rows = channels_mod.list_channels("active")
        send_chunks(api, chat_id, format_channels(rows))
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
        send_chunks(api, chat_id, format_engines())
        return {"ok": True, "action": "engines", "count": len(TG_SEARCH_ENGINES)}
    if cmd in ("deep", "darkweb"):
        send_chunks(api, chat_id, format_deep(arg))
        return {"ok": True, "action": "deep", "count": len(DEEP_ENGINES)}
    if cmd == "memory":
        rows = memory_mod.recent(chat_id, 6)
        send_chunks(api, chat_id, format_memory(rows))
        return {"ok": True, "action": "memory", "count": len(rows)}
    if cmd == "research":
        if not arg:
            api.send(chat_id, "Research ke liye query likhein: /research <sawal>")
            return {"ok": False, "action": "research", "error": "query required"}
        return _send_research(chat_id, arg, cfg=cfg, api=api, research=research)
    api.send(chat_id, "Maaf kijiye, yeh command samajh nahi aaya. /help use kijiye.")
    return {"ok": False, "action": "unknown", "error": "unknown command"}


def _send_research(chat_id: int, query: str, cfg: dict, api, research=None,
                   row_id: int | None = None, advance: bool = False,
                   related: bool = False) -> dict:
    """Research chalao -> report chunks -> 'mil gaya?' buttons + memory.

    Serialization: `_research_lock` ke andar chalta hai, is liye do /research
    (ya /research + /stop) race nahi karte. Har session ki apni id hoti hai;
    /stop ya naya research purana session invalidate kar deta hai.
    """
    global _stop_research, _research_session
    with _research_lock:
        _research_session += 1
        session = _research_session
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
            if not _session_active(session):
                return
            try:
                if related and research is None:
                    # User ne "Nahi mila" maula -> LLM related queries -> un se
                    # naye sources/channels dhoondho.
                    queries = llm.related_queries(cfg, query, n=3) or [query]
                    final = None
                    for q in queries:
                        if not _session_active(session):
                            return
                        final = research_full(q, cfg, skip_sources=used_sources,
                                              skip_channels=used_channels)
                        if str((final or {}).get("markdown") or "").strip():
                            break
                    result_box[0] = final
                elif research is None:
                    result_box[0] = research_full(
                        query, cfg, skip_sources=used_sources,
                        skip_channels=used_channels)
                else:
                    result_box[0] = research(query, cfg)
            except Exception as exc:
                result_box[0] = {"ok": False, "markdown": f"❌ Research error: "
                                 f"{type(exc).__name__}: {util.truncate(str(exc), 250)}",
                                 "sources": [], "channels": []}
            finally:
                _unregister_research_thread(threading.current_thread())

        t = threading.Thread(target=_do_research, daemon=True,
                             name="jin-research")
        _register_research_thread(t)
        t.start()
        # Stop-aware join: /stop aane par turant wake ho (150s blind join nahi).
        deadline = time.monotonic() + 150
        while t.is_alive() and time.monotonic() < deadline:
            t.join(timeout=0.5)
            if not _session_active(session):
                break
        if not _session_active(session):
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

        final_md = md
        try:
            translated = llm.translate_text(cfg, md)
            if translated:
                final_md = translated  # foreign sources -> Roman Urdu report
        except Exception:
            final_md = md
        chunks = split_text(final_md)
        for i, chunk in enumerate(chunks):
            if not _session_active(session):
                api.send(chat_id, "🛑 Report rok di gayi.")
                break
            if i and SEND_DELAY > 0:
                time.sleep(SEND_DELAY)
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
                    research=None, callback_id: str = "") -> dict:
    """Inline button: ✅ Mil gaya / 🔁 Nahi mila - aur dhondo."""
    cfg = cfg or config.load()
    api = api or _api(str(cfg.get("telegram_bot_token") or ""), cfg)
    # Telegram spinner rokne ke liye callback ka jawab lazmi bhejo (warna button
    # hamesha "loading" par atka dikhta hai).
    if callback_id:
        try:
            api.answer_callback(callback_id)
        except Exception:
            pass
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
                              research=research, row_id=row_id, advance=True,
                              related=True)
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
    """Long polling (getUpdates offset+timeout). Stop via threading.Event.

    Har update ek bounded ThreadPoolExecutor (JIN_AGENT_UPDATE_WORKERS, default
    2) par dispatch hota hai — telegram flood par thread storm nahi. Pool ka
    shutdown clean hai (pending tasks cancel).
    """
    cfg = cfg or config.load()
    api = api or _api(token, cfg)
    stop = stop or type("S", (), {"is_set": lambda self: False})()
    workers = update_workers()
    pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="jin-update")

    # --- STARTUP: purani queue clear karo (restart ke baad loop band) ---
    # Telegram ki pending queue ko skip karo: offset se shuru kar ke tak update
    # na aaye, process mat karo. Drain fail hone par bhi offset aage rakhte hain
    # (warna restart ke baad saari pending updates dobara process hoti thin).
    try:
        offset = int(POLL_OFFSET)
        drained = 0
        while True:
            _drain = api.get_updates(offset, 0) or []
            if not _drain:
                break
            drained += len(_drain)
            offset = int((_drain[-1].get("update_id") or 0)) + 1
            if drained > 10000:
                print("[bot] startup drain: 10000+ pending update rok diye", flush=True)
                break
        if drained:
            print(f"[bot] startup drain: {drained} pending update(s) skip", flush=True)
    except Exception as exc:
        offset = int(POLL_OFFSET)
        print(f"[bot] startup drain fail ({type(exc).__name__}: {exc}); "
              f"offset={offset} se shuru", flush=True)
    # --- END STARTUP DRAIN ---

    # Chat allowlist: unset = allow-all (first-run). Production me ye amnitarian
    # khatra hai — is liye shuru me lazmi khabar (is_owner ka raw behaviour
    # allow-all hi rehta hai, tests bhi wahi assert karte hain).
    if not str(cfg.get("telegram_chat_id") or "").strip():
        print("[bot] KHABARDAAR: telegram_chat_id unset — allow-all mode. "
              "Production me TELEGRAM_CHAT_ID set karein.", flush=True)

    print(f"[bot] update workers: {workers} (JIN_AGENT_UPDATE_WORKERS)", flush=True)

    # Network failure par exponential backoff + visible log. Purana code har
    # failure par 5s sleep karta tha bina log ke — region-block (api.telegram.org
    # unreachable) par bot hamesha "down" lagta tha magar crash nahi hota tha.
    # Ab: backoff, counter, aur JIN_AGENT_MAX_POLL_FAILURES (0 = unlimited, purana
    # behaviour) ke baad process exit -> watchdog/supervisor restart karega.
    fail_count = 0
    max_fail = max_poll_failures()
    if max_fail:
        print(f"[bot] poll failure cap: {max_fail} (0 = unlimited)", flush=True)

    try:
        while not stop.is_set():
            try:
                updates = api.get_updates(offset, POLL_TIMEOUT) or []
            except Exception as exc:
                fail_count += 1
                delay = min(5 * (2 ** min(fail_count - 1, 4)), 60)  # 5, 10, 20, 40, 60s
                print(f"[bot] get_updates fail #{fail_count} "
                      f"({type(exc).__name__}: {exc}); {delay}s baad retry", flush=True)
                if max_fail and fail_count >= max_fail:
                    print(f"[bot] {max_fail} lagataar failures — process exit "
                          f"(watchdog restart karega)", flush=True)
                    raise
                time.sleep(delay)
                continue
            if fail_count:
                print(f"[bot] get_updates wapas chal gaya (failures: {fail_count})", flush=True)
                fail_count = 0
            last_id = offset
            for u in updates:
                mid = int((u.get("update_id") or 0))
                last_id = max(last_id, mid)
                cb = u.get("callback_query") or {}
                if cb:
                    # Inline button: ✅ Mil gaya / 🔁 Nahi mila - aur dhondo
                    try:
                        bot_chat = (cb.get("message") or {}).get("chat") or {}
                        cb_chat_id = int((bot_chat or {}).get("id") or 0)
                        if is_owner(cb_chat_id, cfg):
                            pool.submit(
                                handle_callback,
                                cb_chat_id, str(cb.get("data") or ""),
                                cfg=cfg, api=api,
                                callback_id=str(cb.get("id") or ""),
                            )
                    except Exception:
                        time.sleep(2)
                    continue
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
                # Bounded pool: dispatch loop ko block nahi karta aur flood par
                # threads ki tadad env cap ke andar rehti hai.
                try:
                    pool.submit(dispatch, chat_id, text, cfg=cfg, api=api)
                except Exception:
                    time.sleep(2)
            if updates:
                offset = last_id + 1
            if stop.is_set():
                break
    finally:
        try:
            pool.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # Python < 3.9
            pool.shutdown(wait=False)
        _cancel_research(join_timeout=1.0)


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
