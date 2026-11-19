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
import inspect
import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
# Real executor class ka private alias — tests ``tb.ThreadPoolExecutor`` ko fake
# se replace karte hain, magar control-dispatch ka guard asli class par bana rahe.
_ThreadPoolExecutor = ThreadPoolExecutor
try:
    import socks  # PySocks
    _SOCKS_AVAILABLE = True
except ImportError:
    _SOCKS_AVAILABLE = False

from . import (VERSION, channels as channels_mod, chat_context, config,
               dorks, highlight as highlight_mod, llm, orchestrator, policy,
               report_export, scheduler, searchmemory as memory_mod, store,
               util, verifier)


class BotAPIError(RuntimeError):
    """Telegram ne ok:false wala jawab bheja (409 conflict, 429 flood, 400)."""


SEND_CHUNK_LIMIT = 4096
POLL_TIMEOUT = 30
POLL_OFFSET = 0
MAX_COMMAND_LEN = 64

# Telegram ek hi chat par ~1 message/second ki limit rakhta hai. Chunks ke
# darmiyan intezar (second) 429 flood rokta hai. Default 1.0 s (pehle 0.5 s
# tha — FadeHost par 429 storm). 0 = intezar band. Env JIN_AGENT_SEND_DELAY.
def send_delay() -> float:
    try:
        return max(0.0, float(os.environ.get("JIN_AGENT_SEND_DELAY") or 1.0))
    except (TypeError, ValueError):
        return 1.0


SEND_DELAY = send_delay()


def max_rounds() -> int:
    """Research rounds ki cap (env ``JIN_AGENT_MAX_ROUNDS``, default 5)."""
    try:
        return max(1, int(str(os.environ.get("JIN_AGENT_MAX_ROUNDS", "5") or 5)))
    except (TypeError, ValueError):
        return 5


def require_chat_id() -> bool:
    """Opt-in: unset ``telegram_chat_id`` par bhi allow-all na ho.

    Default off (purana allow-all first-run behaviour barqarar). Production me
    ``JIN_AGENT_REQUIRE_CHAT_ID=1`` set karein.
    """
    return str(os.environ.get("JIN_AGENT_REQUIRE_CHAT_ID", "") or "").strip().lower() \
        in ("1", "true", "yes", "on")


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
# Light commands (help/status/channels/buttons) ke liye alag bounded pool.
# Research 30-60s tak main pool ka worker rooshta hai — is liye chhote commands
# usi queue me atkte the (live test me 10-45s lag). Default 4, env
# JIN_AGENT_CONTROL_WORKERS se badal sakte hain.
DEFAULT_CONTROL_WORKERS = 4
MAX_CONTROL_WORKERS = 16
# Ye commands research/report banate hain — unhe main (bounded) pool par bhejo.
HEAVY_COMMANDS = frozenset({"research", "deep", "explore", "digest"})
HELP_TEXT = (
    "Salam! Main aap ka JIN Agent hoon. 6 commands:\n\n"
    "/research <sawal> — research + Roman Urdu report\n"
    "  Misal: /research mediatek firmware unlock\n"
    "/search <keyword> — saved channels ke andar search\n"
    "  Misal: /search firmware\n"
    "/channels — saved channels ki list + clickable links, add/rm\n"
    "  Misal: /channels add https://t.me/durov  (hataana: /channels rm @durov)\n"
    "/explore <topic> — topic-wise channels + web + open source + deep links\n"
    "  Misal: /explore android security  (bina topic: /explore se topic chunein)\n"
    "/status — agent + explore ka live status\n"
    "  Misal: /status\n"
    "/help — yeh menu\n"
    "  Misal: /help\n"
    "/report [md|html] — aakhri report dobara bhejo (default md)\n\n"
    "Seedha matn bhi likh sakte hain — wo /research ban jata hai. "
    "Purane commands bhi chalte hain: /dork, /addchannel, /rmchannel, /tgsearch, "
    "/deep <topic>, /engines, /memory, /stop, /new, /digest, /reports, /alerts, "
    "/schedule, /channelhealth, /memoryaudit, /selftest.\n\n"
    "Har report ke baad bot poochta hai: mil gaya ya nahi. 'Nahi mila' par naye "
    "sources/channels try hote hain (purane skip). Policy SAHULAT-SAFE-SERVICE-v1; "
    "dark web links-only; Telegram public only."
)

# Telegram "/" menu ke liye 6 canonical commands (Bot API setMyCommands).
BOT_COMMANDS = [
    {"command": "research", "description": "Research + report — /research <sawal>"},
    {"command": "search", "description": "Saved channels me search — /search <keyword>"},
    {"command": "channels", "description": "Channels list/add/rm — /channels"},
    {"command": "explore", "description": "Channels + sites explore — /explore [topic]"},
    {"command": "status", "description": "Agent + explore status — /status"},
    {"command": "help", "description": "Command menu — /help"},
]

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
# ``/research <sawal> --deep`` flag (deep engines links report ke saath).
_DEEP_FLAG_RE = re.compile(r"(?:^|\s)--deep\s*$", re.I)
_DORK_FLAG_RE = re.compile(r"(?:^|\s)--dork\s*$", re.I)
# Explore confirm gate: exp:keep:ch:<handle> / exp:skip:st:<idx> / :all
_EXPLORE_CB_RE = re.compile(
    r"^exp:(keep|skip):(all|ch:[A-Za-z0-9_]{3,40}|st:\d{1,4})$")
# Explore topic picker / scope filter: exp:topic:<hash> / exp:scope:<scope>:<hash>
_EXPLORE_TOPIC_CB_RE = re.compile(r"^exp:topic:([a-f0-9]{6,24})$")
_EXPLORE_SCOPE_CB_RE = re.compile(
    r"^exp:scope:(all|tg|web|oss|deep):([a-f0-9]{6,24})$")
# "Aur explore karo" — wahi topic dobara discovery (naye items).
_EXPLORE_MORE_CB_RE = re.compile(r"^exp:more:([a-f0-9]{6,24})$")

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
# Poll failure observability: /status me dikhta hai (cap 0 = unlimited).
_poll_failures = 0
# Confirmation-gated actions: chat_id -> pending payload (ADR-006/008 pattern).
_pending_add: dict[int, str] = {}
# Progress edit-in-place (StatusTracker pattern): chat_id -> message_id.
_STATUS_MESSAGES: dict[int, int] = {}
# Progress edit throttle: chat_id -> aakhri edit ka monotonic waqt. Telegram
# ~20 edit/min limit hai; stage edits 3s se kam na hon (20/min ke andar).
_STATUS_LAST_EDIT: dict[int, float] = {}
STATUS_EDIT_MIN_GAP = 3.0
# Explore confirm gate: chat_id -> {"topic", "scope", "items": {key: item}}
_EXPLORE_PENDING: dict[int, dict] = {}
# Per-chat "pehle dikhaye gaye" item keys (max 200) — dobara /explore par wahi
# cheez na aaye. dict ordered-set ki tarah (key -> None).
_EXPLORE_SHOWN: dict[int, dict[str, None]] = {}
# topic hash -> topic (callback_data 64-byte limit ki wajah se hash use hota hai)
_EXPLORE_TOPICS: dict[str, str] = {}
# Group/chat rate limit: chat_id -> sliding window of dispatch timestamps.
_GROUP_HITS: dict[int, list[float]] = {}
GROUP_RATE_LIMIT = 20


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


def update_control_workers() -> int:
    """Control/callback pool size (env JIN_AGENT_CONTROL_WORKERS, default 4)."""
    raw = str(os.environ.get("JIN_AGENT_CONTROL_WORKERS", "") or "").strip()
    if not raw:
        return DEFAULT_CONTROL_WORKERS
    try:
        n = int(raw)
    except (TypeError, ValueError):
        print(f"[bot] JIN_AGENT_CONTROL_WORKERS ghalat ({raw!r}) — "
              f"default {DEFAULT_CONTROL_WORKERS}", flush=True)
        return DEFAULT_CONTROL_WORKERS
    return max(1, min(MAX_CONTROL_WORKERS, n))


_control_pool: ThreadPoolExecutor | None = None


def _get_control_pool() -> ThreadPoolExecutor:
    """Lazy control pool — light commands ke liye alag bounded executor.

    Process-lifetime hai (ek process me ek run). ``run()`` ke finally me
    shutdown + None kiya jata hai taake dobara run par naya bane.
    """
    global _control_pool
    if _control_pool is None:
        _control_pool = ThreadPoolExecutor(
            max_workers=update_control_workers(),
            thread_name_prefix="jin-control")
    return _control_pool


def _shutdown_control_pool() -> None:
    """Control pool band karo (run ke finally me). Dobara run par naya bane."""
    global _control_pool
    if _control_pool is None:
        return
    try:
        _control_pool.shutdown(wait=False, cancel_futures=True)
    except TypeError:  # Python < 3.9
        _control_pool.shutdown(wait=False)
    _control_pool = None


def _is_heavy_command(cmd: str) -> bool:
    """Research/report banane wale commands — main pool par, light nahi."""
    return str(cmd or "") in HEAVY_COMMANDS


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


def _submit_control(pool, fn, *args, **kwargs):
    """Light commands/callbacks ko dedicated bounded control pool par bhejo.

    ``/stop`` / ``/status`` aur ab baqi chhote commands bhi busy research
    workers ke peeche nahi atkte (live test me 10-45s lag tha). Real
    ``ThreadPoolExecutor`` par alag pool chalta hai; injected/fake pool
    (tests) par ``submit`` hi use hota hai.
    """
    if isinstance(pool, _ThreadPoolExecutor):
        return _get_control_pool().submit(fn, *args, **kwargs)
    return pool.submit(fn, *args, **kwargs)


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


def route_plain_text(text: str, forwarded: str = "") -> str:
    """Bina ``/`` wala matn: link/handle -> /addchannel, baqi -> /research.

    User ka hukm: seedha sawal likhna bhi research chalaye; magar link ya
    @handle, ya channel post forward, abhi bhi /addchannel hi rakha jaye.
    """
    s = str(text or "").strip()
    if not s:
        return ""
    if forwarded:
        return "/addchannel @" + forwarded
    if _LINK_ONLY_RE.fullmatch(s) or _HANDLE_ONLY_RE.fullmatch(s):
        return "/addchannel " + s
    return "/research " + s


def split_deep_flag(arg: str) -> tuple[str, bool]:
    """``/research <sawal> --deep`` -> (sawal, deep). Flag hamesha aakhir me."""
    s = str(arg or "").strip()
    m = _DEEP_FLAG_RE.search(s)
    if not m:
        return s, False
    return s[:m.start()].strip(), True


def split_dork_flag(arg: str) -> tuple[str, bool]:
    """``/explore <topic> --dork`` -> (topic, dork). Flag hamesha aakhir me."""
    s = str(arg or "").strip()
    m = _DORK_FLAG_RE.search(s)
    if not m:
        return s, False
    return s[:m.start()].strip(), True


def register_commands(api, commands: list[dict] | None = None) -> bool:
    """Bot API ``setMyCommands`` — startup par ek dafa. Best-effort.

    Purane/fake API jis me ye method nahi, wahan chupchaap skip.
    """
    fn = getattr(api, "set_my_commands", None)
    if not callable(fn):
        return False
    fn(list(commands if commands is not None else BOT_COMMANDS))
    return True


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


def _html_escape(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _highlight_html(text: str, query: str) -> str:
    """Markdown/plain text -> HTML jismein query ke lafz ``<b>`` se highlight hon.

    User ka maksad: "report jo milti hai wo keyword highlight kar ky mily".
    Highlight sirf **text nodes** me hota hai (tags, attributes, URLs, entities
    nahi chhoo-te) — waja: ``highlight.highlight_html``. Chunking ke liye
    ``highlight.split_html`` use karo (entity-safe, tag-balanced).
    Koi masla ho to escape-only HTML — kabhi adhura message nahi.
    """
    try:
        html = markdown_to_html(text)
        return highlight_mod.highlight_html(html, highlight_mod.terms(query))
    except Exception:
        return _html_escape(text)


def markdown_to_html(text: str) -> str:
    """briefer markdown -> Telegram HTML (``parse_mode='HTML'``).

    Pehle escape, phir bold/italic/link/code/bullet convert. Headings
    (``#``) plain text ki tarah rehte hain (backward-compatible chunking).
    """
    html = _html_escape(text)
    html = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                  lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', html)
    html = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", html)
    html = re.sub(r"\*\*([^*]+)\*\*", lambda m: f"<b>{m.group(1)}</b>", html)
    html = re.sub(r"\*([^*]+)\*", lambda m: f"<i>{m.group(1)}</i>", html)
    html = re.sub(r"(?m)^- ", "• ", html)
    return html


def send_chunks(api, chat_id: int, text: str, delay: float | None = None,
                parse_mode: str | None = None) -> int:
    """Text ko Telegram chunks me bhejo, har chunk ke baad chhota intezar.

    429 flood (FadeHost console par thread storm) ka asli hal: chunks ek ke
    baad ek bina waqt ke. Return: bheje gaye chunks ki tadad.
    """
    d = SEND_DELAY if delay is None else max(0.0, float(delay))
    sent = 0
    for i, chunk in enumerate(split_text(text)):
        if i and d > 0:
            time.sleep(d)
        if parse_mode:
            try:
                api.send(chat_id, chunk, parse_mode=parse_mode)
            except TypeError:  # purana/fake API jis me parse_mode nahi
                api.send(chat_id, chunk)
        else:
            api.send(chat_id, chunk)
        sent += 1
    return sent


def is_owner(chat_id: int | None, cfg: dict | None = None) -> bool:
    """Sirf wohi chat allowed (telegram_chat_id).

    Unset = allow-all (first run) — magar ``JIN_AGENT_REQUIRE_CHAT_ID=1`` on
    ho to unset par reject (production opt-in). Default raw behaviour tests
    ke mutabiq barqarar hai.
    """
    cfg = cfg or config.load()
    raw = str(cfg.get("telegram_chat_id") or "").strip()
    if not raw:
        return not require_chat_id()
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


def format_channels(rows: list[dict], counts: dict | None = None) -> str:
    """Saved channels + 1-click links (plain text, Telegram khud link banata hai)."""
    if not rows:
        dead = int((counts or {}).get("dead") or 0)
        archived = int((counts or {}).get("archived") or 0)
        if dead or archived:
            return (f"❌ Saare channels dead/archived hain "
                    f"({dead} dead, {archived} archived) — koi active channel nahi.\n\n"
                    "Sab channels dikhane ke liye: /channels --all\n"
                    "Naye channel add karein: /addchannel https://t.me/channelname\n"
                    "Ya kisi channel ka post yahan forward karein (khud add ho jayega).\n\n"
                    "Sirf PUBLIC channels ke andar search ho sakti hai "
                    "(private/invite-only preview nahi deta).")
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


def format_explore(res: dict) -> str:
    """``/explore`` ka result — discovery + scored archive items (chhota digest)."""
    res = res or {}
    topic = str(res.get("topic") or res.get("query") or "")
    disc = res.get("discovery") or {}
    scored = res.get("scored") or []
    added = disc.get("added") or []
    dead = disc.get("dead") or []
    lines = [f"🧭 Explore: {util.truncate(topic, 90)}", ""]
    lines.append(f"Discovery: {len(added)} naye active, {len(dead)} dead "
                 f"(candidates {disc.get('candidates', 0)}, "
                 f"probed {disc.get('probed', 0)}).")
    if scored:
        lines += ["", "Top scored archive results:"]
        for i, item in enumerate(scored[:5], 1):
            lines.append(f"{i}. {util.truncate(str(item.get('title') or ''), 90)} "
                         f"| score {item.get('score', 0)} | "
                         f"{util.truncate(str(item.get('source') or ''), 30)}")
    else:
        lines += ["", "Archive me is topic ka koi scored item nahi mila."]
    lines += ["", f"📄 Digest: {res.get('items', 0)} items (local archive report).",
              "", "Rozana explore: scheduler explore_minutes (default 1440)."]
    return "\n".join(lines)


def format_explore_cards(topic: str, chan_items: list[dict],
                         site_items: list[dict]) -> str:
    """Explore digest + clickable cards (naam, @handle, link, score, subs, status)."""
    lines = [f"🧭 Explore: {util.truncate(topic, 90)}", ""]
    if chan_items:
        lines.append(f"📡 Naye channels ({len(chan_items)}):")
        for i, it in enumerate(chan_items, 1):
            bits = [b for b in (f"score {it.get('score', 0)}",
                                (str(it.get("subs") or "") + " subs") if it.get("subs") else "",
                                str(it.get("status") or "active")) if b]
            lines.append(f"{i}. {util.truncate(str(it.get('title') or it.get('handle')), 70)}"
                         f" — @{it.get('handle')}")
            lines.append(f"   {' · '.join(bits)}")
            lines.append(f"   {it.get('url')}")
        lines.append("")
    if site_items:
        lines.append(f"🌐 Sites / sources ({len(site_items)}):")
        start = len(chan_items) + 1
        for j, it in enumerate(site_items, start):
            src = f" · {it['source']}" if it.get("source") else ""
            lines.append(f"{j}. {util.truncate(str(it.get('title') or it.get('url')), 80)}{src}")
            lines.append(f"   {it.get('url')}")
        lines.append("")
    if not chan_items and not site_items:
        lines.append("Koi naya channel/site nahi mila.")
    lines.append("✅ = memory me rakho · ❌ = skip. Bulk: ✅ Sab rakho / ❌ Kuch nahi.")
    return "\n".join(lines)


def parse_explore_callback(data: str) -> tuple[str, str]:
    """``exp:keep:ch:<handle>`` / ``exp:skip:st:<idx>`` / ``exp:keep:all``."""
    m = _EXPLORE_CB_RE.match(str(data or "").strip())
    if not m:
        return "", ""
    return m.group(1), m.group(2)


def parse_explore_topic_callback(data: str) -> str:
    """``exp:topic:<hash>`` -> hash (topic picker button)."""
    m = _EXPLORE_TOPIC_CB_RE.match(str(data or "").strip())
    return m.group(1) if m else ""


def parse_explore_more_callback(data: str) -> str:
    """``exp:more:<hash>`` -> hash ("Aur explore karo" button)."""
    m = _EXPLORE_MORE_CB_RE.match(str(data or "").strip())
    return m.group(1) if m else ""


def parse_explore_scope_callback(data: str) -> tuple[str, str]:
    """``exp:scope:<scope>:<hash>`` -> (scope, hash)."""
    m = _EXPLORE_SCOPE_CB_RE.match(str(data or "").strip())
    if not m:
        return "", ""
    return m.group(1), m.group(2)


def _keep_explore_item(item: dict, cfg: dict | None = None) -> None:
    """Confirm gate ✅: channel registry / site memory me rakho."""
    if not isinstance(item, dict):
        return
    if item.get("kind") == "channel":
        try:
            channels_mod.add_channel(str(item.get("handle") or ""),
                                     origin="manual", note="explore confirm")
        except Exception:
            pass
    else:
        try:
            channels_mod.add_site(str(item.get("url") or ""),
                                  title=str(item.get("title") or ""),
                                  source=str(item.get("source") or ""),
                                  topic=str(item.get("topic") or ""))
        except Exception:
            pass


def _skip_explore_item(item: dict, cfg: dict | None = None) -> None:
    """Confirm gate ❌: channel archive (delete nahi), site memory se nahi rakha."""
    if isinstance(item, dict) and item.get("kind") == "channel":
        try:
            channels_mod.remove_channel(str(item.get("handle") or ""))
        except Exception:
            pass


def _handle_explore_callback(chat_id: int, action: str, key: str,
                             cfg: dict, api) -> dict:
    """Explore ke ✅/❌ buttons (per-item aur bulk) — purana gate format."""
    pending = _EXPLORE_PENDING.get(int(chat_id)) or {}
    items = pending.get("items") or {}
    if key == "all":
        kept = skipped = 0
        for item in list(items.values()):
            if action == "keep":
                _keep_explore_item(item, cfg)
                kept += 1
            else:
                _skip_explore_item(item, cfg)
                skipped += 1
        _EXPLORE_PENDING.pop(int(chat_id), None)
        mark = "✅" if action == "keep" else "❌"
        api.send(chat_id, f"{mark} Bulk explore: {kept} memory me, {skipped} skip.")
        return {"ok": True, "action": "explore_bulk",
                "kept": kept, "skipped": skipped}
    item = items.get(key)
    if not item:
        api.send(chat_id, "Purana explore gate hai. Naya /explore karein.")
        return {"ok": False, "action": "explore", "error": "expired"}
    items.pop(key, None)
    label = str(item.get("label") or item.get("title") or key)
    if action == "keep":
        _keep_explore_item(item, cfg)
        api.send(chat_id, f"✅ {util.truncate(label, 60)} memory me rakh liya.")
        return {"ok": True, "action": "explore_keep", "kind": item.get("kind")}
    _skip_explore_item(item, cfg)
    api.send(chat_id, f"❌ {util.truncate(label, 60)} skip kar diya.")
    return {"ok": True, "action": "explore_skip", "kind": item.get("kind")}


EXPLORE_SCOPES = [
    ("all", "🌐 Sab"), ("tg", "🐦 Telegram"), ("web", "🌐 Open web"),
    ("oss", "📚 Open source"), ("deep", "🕶️ Deep web"),
]
SCOPE_LABELS = {k: v for k, v in EXPLORE_SCOPES}
# Ek /explore run me 10-15 channels dikhao (user ne 10-15 maanga). Discovery
# bhi utne hi candidates probe karti hai (EXPLORE_DISCOVERY_MAX_ADD).
EXPLORE_DISCOVERY_MAX_ADD = 15
_EXPLORE_GROUP_CAP = {"tg": EXPLORE_DISCOVERY_MAX_ADD, "web": 5, "oss": 5,
                      "deep": 4}


def _explore_topic_hash(topic: str) -> str:
    """Topic ka chhota hash (callback_data 64-byte limit ke liye)."""
    return util.fingerprint(str(topic or ""))[:12]


def explore_scope_buttons(topic: str) -> list[list[dict]]:
    """Scope filter buttons (callback me hash; topic pending/map me rehta hai)."""
    h = _explore_topic_hash(topic)
    _EXPLORE_TOPICS[h] = str(topic)
    return [[{"text": label, "callback_data": f"exp:scope:{key}:{h}"}]
            for key, label in EXPLORE_SCOPES]


def explore_topic_buttons(cfg: dict | None = None) -> list[list[dict]]:
    """``/explore`` bina topic: config.TOPICS se 6-8 topic buttons (koi niche default nahi)."""
    cfg = cfg or config.load()
    topics = [str(t).strip() for t in (cfg.get("topics") or config.TOPICS)
              if str(t).strip()][:8]
    for t in topics:
        _EXPLORE_TOPICS[_explore_topic_hash(t)] = t
    return [[{"text": t[:28],
              "callback_data": "exp:topic:" + _explore_topic_hash(t)}]
            for t in topics]


def explore_deep_links(topic: str) -> list[dict]:
    """Deep-web engines ke prefilled links — sirf display, fetch/crawl NAHI."""
    q = urllib.parse.quote(str(topic or "").strip()[:150])
    out = []
    for name, url, note in DEEP_ENGINES:
        link = url.replace("{q}", q) if q else url.split("?")[0].replace("{q}", "")
        out.append({"kind": "deep", "title": str(name), "url": link,
                    "source": "deep-web", "note": str(note)})
    return out


def _explore_shown(chat_id: int) -> dict[str, None]:
    return _EXPLORE_SHOWN.setdefault(int(chat_id), {})


def _explore_mark_shown(chat_id: int, keys) -> None:
    """Dikhaye gaye keys yaad rakho (max 200) — dobara explore par skip."""
    seen = _explore_shown(chat_id)
    for k in keys:
        if k:
            seen[k] = None
    while len(seen) > 200:
        seen.pop(next(iter(seen)))


def _explore_item_key(item: dict) -> str:
    if not isinstance(item, dict):
        return ""
    if item.get("kind") == "channel":
        return "ch:" + str(item.get("handle") or "")
    return "url:" + str(item.get("url") or "")


def _explore_channel_item(handle: str, rows: dict) -> dict:
    row = rows.get(handle) or {}
    return {"kind": "channel", "key": "ch:" + str(handle),
            "handle": str(handle),
            "title": str(row.get("title") or handle),
            "score": int(row.get("score") or 0),
            "subs": str(row.get("subscribers") or ""),
            "status": str(row.get("status") or "active"),
            # run_discovery active + score>=min ko origin='auto' se tg_channels
            # me save karta hai — card par saaf dikhao.
            "auto_saved": True,
            "url": "https://t.me/" + str(handle),
            "label": "@" + str(handle)}


def _explore_site_item(it: dict, url: str, topic: str, idx: int) -> dict:
    return {"kind": "site", "key": "st:" + str(idx),
            "title": str(it.get("title") or url),
            "source": str(it.get("source") or ""),
            "url": url, "topic": topic,
            "score": it.get("score") or 0,
            "label": str(it.get("source") or "site")}


def _explore_groups(res: dict, topic: str, scope: str) -> dict:
    """Discovery + scored + deep links ko 4 scope-group me todo.

    Site-like items (web/oss/deep) ke keys global ``st:<idx>`` hote hain —
    purana ``exp:keep:st:<idx>`` callback format barqarar aur keys unique.
    """
    disc = (res or {}).get("discovery") or {}
    scored = (res or {}).get("scored") or []
    groups: dict[str, list[dict]] = {"tg": [], "web": [], "oss": [], "deep": []}
    if scope in ("all", "tg"):
        try:
            rows = {r["channel"]: r for r in channels_mod.list_channels()}
        except Exception:
            rows = {}
        for handle in (disc.get("added") or [])[:_EXPLORE_GROUP_CAP["tg"]]:
            groups["tg"].append(_explore_channel_item(str(handle), rows))
    idx = 0
    if scope in ("all", "web", "oss"):
        for it in scored:
            url = str(it.get("url") or "").strip()
            if not url:
                continue
            if scheduler.is_oss_item(it):
                if scope in ("all", "oss"):
                    groups["oss"].append(_explore_site_item(it, url, topic, idx))
                    idx += 1
            elif scheduler.is_web_item(it):
                if scope in ("all", "web"):
                    groups["web"].append(_explore_site_item(it, url, topic, idx))
                    idx += 1
    if scope in ("all", "deep"):
        for d in explore_deep_links(topic):
            d = dict(d)
            d["key"] = "st:" + str(idx)
            d["label"] = "deep link"
            idx += 1
            groups["deep"].append(d)
    for g in groups:
        groups[g] = groups[g][:_EXPLORE_GROUP_CAP[g]]
    return groups


def _explore_filter_items(groups: dict, chat_id: int) -> dict:
    """Same handle/URL ek baar + pehle dikhaye gaye keys skip."""
    seen = _explore_shown(chat_id)
    out: dict[str, list[dict]] = {"tg": [], "web": [], "oss": [], "deep": []}
    used: set[str] = set()
    for g in ("tg", "web", "oss", "deep"):
        for it in groups.get(g) or []:
            key = _explore_item_key(it)
            if not key or key in used or key in seen:
                continue
            used.add(key)
            out[g].append(it)
    return out


def format_explore_cards_v2(topic: str, scope: str, groups: dict) -> str:
    """Ek hi message: har scope ka heading + clickable link + score."""
    label = SCOPE_LABELS.get(scope, scope)
    lines = [f"🧭 Explore: {util.truncate(topic, 80)} · {label}", ""]
    for g, head in (("tg", "📡 Telegram"), ("web", "🌐 Open web"),
                    ("oss", "📚 Papers & code"), ("deep", "🕶️ Deep web links")):
        items = groups.get(g) or []
        if not items:
            continue
        suffix = " — links only, bot fetch nahi karta" if g == "deep" else ""
        lines.append(f"{head} ({len(items)}){suffix}")
        for i, it in enumerate(items, 1):
            title = util.truncate(str(it.get("title") or it.get("url") or ""), 70)
            if g == "tg":
                bits = [b for b in (f"score {it.get('score', 0)}",
                                    (str(it.get("subs") or "") + " subs")
                                    if it.get("subs") else "",
                                    str(it.get("status") or "active")) if b]
                if it.get("auto_saved"):
                    bits.append("auto-save ✅")  # run_discovery ne memory me rakha
                lines.append(f"{i}. {title} — @{it.get('handle')}")
                lines.append(f"   {' · '.join(bits)}")
            else:
                src = f" · {it['source']}" if it.get("source") else ""
                score = f" · score {it['score']}" if it.get("score") else ""
                lines.append(f"{i}. {title}{src}{score}")
            lines.append(f"   {it.get('url')}")
        lines.append("")
    if len(lines) <= 2:
        lines.append("Koi naya item nahi mila.")
    lines.append("✅ = memory me rakho · ❌ = skip. Bulk: ✅ Sab rakho / ❌ Kuch nahi.")
    return util.truncate("\n".join(lines), 3500)


def _explore_buttons(groups: dict) -> list[list[dict]]:
    """Har item par ✅/❌ (purana callback format barqarar)."""
    buttons: list[list[dict]] = []
    for g in ("tg", "web", "oss", "deep"):
        for it in groups.get(g) or []:
            buttons.append([
                {"text": "✅ " + str(it.get("label") or "")[:20],
                 "callback_data": "exp:keep:" + it["key"]},
                {"text": "❌", "callback_data": "exp:skip:" + it["key"]},
            ])
    return buttons


def _explore_bulk_buttons() -> list[dict]:
    return [{"text": "✅ Sab rakho", "callback_data": "exp:keep:all"},
            {"text": "❌ Kuch nahi", "callback_data": "exp:skip:all"}]


def _filter_groups(groups: dict, scope: str) -> dict:
    """Scope button par sirf us group ko dikhao (baqi khaali)."""
    if scope == "all":
        return groups
    return {g: (list(groups.get(g) or []) if g == scope else [])
            for g in ("tg", "web", "oss", "deep")}


def _explore_empty_reason(res: dict, scope: str) -> str:
    """0-item explore par wajah (honest) — anti-bot search failure saaf lage."""
    disc = (res or {}).get("discovery") or {}
    if scope in ("all", "tg") and int(disc.get("candidates") or 0) == 0:
        ws = disc.get("web_search") or {}
        if ws.get("anomaly"):
            return ("📡 Telegram: is dafa koi naya channel nahi mila — search "
                    "engine ne results nahi diye (anti-bot). `/status` par "
                    "engine health dekhein.")
        if ws.get("error"):
            return (f"📡 Telegram: koi naya channel nahi mila — "
                    f"{util.truncate(str(ws['error']), 120)}.")
    return "Koi naya item nahi mila (ya sab pehle dikhaye chuke hain)."


def _render_explore(chat_id: int, topic: str, scope: str, res: dict,
                    cfg: dict, api, groups: dict | None = None) -> dict:
    """Ek hi explore message bhejo (dedupe + shown memory ke saath).

    ``groups`` diya ho (scope button par pending se) to dobara discovery nahi
    chalti aur shown-filter bhi lagta nahi — warna scope badalne par sab
    "pehle dikhaye" skip ho jatay.
    """
    if groups is None:
        full = _explore_filter_items(_explore_groups(res, topic, "all"),
                                     chat_id)
        groups = _filter_groups(full, scope)
        mark = True
    else:
        full = groups
        groups = _filter_groups(groups, scope)
        mark = False
    items: dict[str, dict] = {}
    keys = []
    for g in ("tg", "web", "oss", "deep"):
        for it in groups.get(g) or []:
            items[it["key"]] = it
            keys.append(_explore_item_key(it))
    if not items:
        _EXPLORE_PENDING.pop(int(chat_id), None)
        api.send(chat_id,
                 f"🧭 Explore: {util.truncate(topic, 80)} · "
                 f"{SCOPE_LABELS.get(scope, scope)}\n\n"
                 f"{_explore_empty_reason(res, scope)}\n"
                 "Dobara /explore karein ya neeche scope badlein.",
                 buttons=explore_scope_buttons(topic))
        return {"ok": True, "action": "explore", "topic": topic, "scope": scope,
                "items": 0, "empty": True}
    _EXPLORE_PENDING[int(chat_id)] = {"topic": topic, "scope": scope,
                                      "items": items, "groups": full}
    if mark:
        _explore_mark_shown(chat_id, keys)
    _EXPLORE_TOPICS[_explore_topic_hash(topic)] = topic
    more_btn = [{"text": "🔄 Aur explore karo",
                 "callback_data": "exp:more:" + _explore_topic_hash(topic)}]
    buttons = (_explore_buttons(groups) + [more_btn]
               + explore_scope_buttons(topic) + [_explore_bulk_buttons()])
    api.send(chat_id, format_explore_cards_v2(topic, scope, groups),
             buttons=buttons)
    return {"ok": True, "action": "explore", "topic": topic, "scope": scope,
            "items": len(items), "empty": False}


def _send_dork(chat_id: int, query: str, cfg: dict, api) -> dict:
    """``/dork <query>`` — dork presets + working backend ke links/results."""
    q = str(query or "").strip()
    if not q:
        api.send(chat_id, "Dork ke liye query likhein: /dork <query>")
        return {"ok": False, "action": "dork", "error": "query required"}
    results = []
    try:
        results = dorks.search(dorks.tg(q), cfg)
    except Exception:
        results = []
    send_chunks(api, chat_id, dorks.render(q, results))
    try:
        store.add_event("dork", f"query={util.truncate(q, 60)} "
                                 f"results={len(results)}")
    except Exception:
        pass
    return {"ok": True, "action": "dork", "query": q, "results": len(results)}


def _run_explore(chat_id: int, topic: str, scope: str, cfg: dict, api) -> dict:
    """``/explore <topic>`` — topic required; scope default all.

    ``--dork`` flag par dork presets + backend links bhi bheje jate hain.
    """
    topic, dork = split_dork_flag(topic)
    topic = str(topic or "").strip()
    scope = str(scope or "all").strip().lower()
    if scope not in SCOPE_LABELS:
        scope = "all"
    if not topic:
        api.send(chat_id,
                 "🧭 Explore ke liye topic chunein ya `/explore <kuch bhi>` likhein.\n"
                 "Phir scope choose karein: 🐦 Telegram · 🌐 Open web · "
                 "📚 Open source · 🕶️ Deep web.",
                 buttons=explore_topic_buttons(cfg))
        return {"ok": True, "action": "explore_topics"}
    try:
        # Manual explore: asli discovery (network probes) chalao, topic ke saath.
        # max_add=15: ek run me 10-15 channels probe/dikhao.
        res = scheduler.run_job("explore",
                                {"query": topic, "scope": scope,
                                 "max_add": EXPLORE_DISCOVERY_MAX_ADD},
                                cfg, offline=False)
    except Exception as exc:
        api.send(chat_id, f"❌ Explore fail: {type(exc).__name__}: "
                          f"{util.truncate(str(exc), 200)}")
        return {"ok": False, "action": "explore", "error": "explore failed"}
    out = _render_explore(chat_id, topic, scope, res, cfg, api)
    out["items"] = int(out.get("items") or 0)
    out["archive_items"] = int(res.get("items") or 0)
    if dork:
        out["dork"] = _send_dork(chat_id, topic, cfg, api)
    return out


def last_explore_event() -> dict:
    """Aakhri explore event (``/status`` ke liye); na ho to {}."""
    try:
        for e in store.list_events(200):
            if str(e.get("kind") or "") == "explore":
                return e
    except Exception:
        pass
    return {}


def last_explore_at() -> str:
    """Aakhri explore event ka ts (``/status`` ke liye); na ho to ""."""
    return str(last_explore_event().get("ts") or "")


def last_explore_scope() -> str:
    """Aakhri explore ka scope (event detail se)."""
    m = re.search(r"scope=(\S+)", str(last_explore_event().get("detail") or ""))
    return m.group(1) if m else ""


def last_explore_topic() -> str:
    """Aakhri explore ka topic (event detail se)."""
    m = re.search(r"topic=(.*?)\s+scope=",
                  str(last_explore_event().get("detail") or ""))
    return m.group(1).strip() if m else ""


def source_health(sources: list[dict] | None = None) -> dict:
    """Sources ka **non-overlapping** health breakdown (P36).

    Purana hisaab overlap karta tha: ``status == "ok"`` magar ``fail_count > 0``
    wala source ok aur fail dono buckets me gina jata tha (live bot ne
    `45 ok / 1 fail (total 45)` dikhaya tha). Ab har source sirf ek bucket me:
    ``disabled`` (auto magar enabled falsy) pehle, phir status ke mutabiq
    ``failed`` / ``stale`` / ``ok``. ``registry-only`` (adapter ke baghair)
    sources buckets me nahi — wo alag honest gincha jati hain, is liye
    buckets ka total hamesha ``auto`` ke barabar hota hai. Wo ``disabled``
    nahi hain; user ne band nahi kiye, adapter mojood nahi.
    """
    if sources is None:
        try:
            sources = store.list_sources()
        except Exception:
            sources = []
    buckets = {"ok": 0, "failed": 0, "stale": 0, "disabled": 0}
    auto = registry_only = 0
    failed: list[dict] = []
    stale: list[dict] = []
    for s in sources:
        if not s.get("auto"):
            registry_only += 1
            continue
        auto += 1
        if not s.get("enabled"):
            buckets["disabled"] += 1
            continue
        status = str(s.get("status") or "ok") or "ok"
        if status == "verification_failed":
            buckets["failed"] += 1
            failed.append(s)
        elif status == "stale":
            buckets["stale"] += 1
            stale.append(s)
        else:
            buckets["ok"] += 1
    return {"total": len(sources), "buckets": buckets, "auto": auto,
            "registry_only": registry_only, "failed": failed, "stale": stale}


def format_status_text(cfg: dict | None = None) -> str:
    """``/status`` — agent + Telegram + sites + sources + explore ka live hisaab."""
    cfg = cfg or config.load()
    try:
        ch = channels_mod.counts()
    except Exception:
        ch = {}
    try:
        sites = channels_mod.site_counts()
    except Exception:
        sites = {}
    health = source_health()
    b = health["buckets"]
    try:
        pending = channels_mod.pending_candidates()
    except Exception:
        pending = 0
    last = last_explore_at()
    last_scope = last_explore_scope()
    last_topic = last_explore_topic()
    try:
        disc = channels_mod.last_discovery_state()
    except Exception:
        disc = {}
    lines = [
        "📊 JIN Agent status",
        f"• Policy: {cfg.get('policy_id') or 'SAHULAT-SAFE-SERVICE-v1'}",
        f"• Poll failures: {_poll_failures}",
        f"• Telegram: {ch.get('active', 0)} active / {ch.get('dead', 0)} dead / "
        f"{ch.get('archived', 0)} archived / {ch.get('stale', 0)} stale",
        f"• Sites memory: {sites.get('total', 0)} "
        f"(is hafte {sites.get('week', 0)})",
        f"• Sources: {health['total']} total — {health['auto']} auto / "
        f"{health['registry_only']} registry-only (adapter ke baghair) | "
        f"auto: {b['ok']} ok / {b['failed']} failed / {b['stale']} stale / "
        f"{b['disabled']} disabled",
        f"• Explore: last {last or 'kabhi nahi'} · "
        f"scope {last_scope or 'n/a'} · pending candidates {pending}",
        f"• Aakhri explore: {last_topic or 'kabhi nahi'}",
    ]
    if disc:
        try:
            disc_ts = time.strftime("%Y-%m-%d %H:%M",
                                    time.localtime(float(disc.get("ts") or 0)))
        except (TypeError, ValueError, OverflowError, OSError):
            disc_ts = "n/a"
        eng = str(disc.get("engine") or "")
        reason = util.truncate(str(disc.get("error") or ""), 100)
        line = (
            f"• Telegram discovery: last {disc_ts} · "
            f"engine {eng or 'n/a'} · "
            f"candidates {int(disc.get('candidates') or 0)} · "
            f"probed {int(disc.get('probed') or 0)} · "
            f"added {int(disc.get('added') or 0)}")
        # Engine milne par wajah ek hi line me (honest hisaab); engine nahi
        # to alag ✗ line — dono sobat me "kyun" saaf rahe.
        if reason and eng:
            line += f" · wajah: {reason}"
        lines.append(line)
        if reason and not eng:
            lines.append("  ✗ wajah: " + reason)
    try:
        dstat = dorks.backend_status()
    except Exception:
        dstat = []
    if dstat:
        ok_n = sum(1 for s in dstat if s["ok"])
        lines.append(
            f"• Dork: {ok_n} kaam / {len(dstat) - ok_n} blocked — "
            + " · ".join(f"{s['name']} {'✓' if s['ok'] else '✗'}"
                         for s in dstat))
    # Fail/stale source ka naam + wajah — hisaab chhota rehne par bhi khabar
    # saaf honi chahiye (kaunsa source, kyun band).
    for row in health["failed"]:
        name = str(row.get("name") or row.get("key") or "source")
        err = util.truncate(row.get("last_error") or "wajah darj nahi", 80)
        lines.append(f"  ✗ {util.truncate(name, 60)}: {err}")
    for row in health["stale"]:
        name = str(row.get("name") or row.get("key") or "source")
        err = util.truncate(row.get("last_error") or "verification purana", 80)
        lines.append(f"  ⏳ {util.truncate(name, 60)}: {err}")
    lines += ["", "Explore: /explore <topic> (ya /explore se topic chunein)"]
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

        def _post_bytes(self, path: str, body: bytes, content_type: str,
                        timeout: int) -> dict:
            """Multipart/raw POST — 429 par wahi retry_policy (sendDocument)."""
            req = urllib.request.Request(
                self.base + path, data=body,
                headers={"Content-Type": content_type}, method="POST")
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

        def send_document(self, chat_id: int, file_path: str, caption: str = "",
                          timeout: int = 120) -> dict:
            """Report ko ``sendDocument`` se bhejo (chat flood ki jagah file).

            Telegram Bot API: document 50MB tak, caption 1024 chars. Koi public
            URL nahi — file multipart upload hoti hai (hosted-friendly).
            """
            boundary = "----JINAgent" + uuid.uuid4().hex
            filename = os.path.basename(str(file_path))
            with open(file_path, "rb") as fh:
                data = fh.read()
            parts: list[bytes] = []

            def field(name: str, value: str) -> None:
                parts.append(
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n".encode("utf-8"))

            field("chat_id", str(int(chat_id)))
            if caption:
                field("caption", str(caption)[:1024])
            parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="document"; '
                f'filename="{filename}"\r\n'
                f"Content-Type: application/octet-stream\r\n\r\n".encode("utf-8"))
            parts.append(data)
            parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
            body = b"".join(parts)
            return self._checked(
                self._post_bytes("/sendDocument", body,
                                 "multipart/form-data; boundary=" + boundary,
                                 timeout),
                "sendDocument")

        def _checked(self, res: dict, what: str) -> dict:
            # Telegram ok:false (409 conflict, 429 flood, 400) pehle ignore hota
            # tha -> generic exception -> backoff. Ab saaf, named error.
            if not res.get("ok"):
                code = res.get("error_code")
                desc = str(res.get("description") or "")
                raise BotAPIError(f"{what}: {code} {desc}".strip())
            return res

        def send(self, chat_id: int, text: str, buttons=None,
                 parse_mode: str | None = None) -> dict:
            payload = {
                "chat_id": int(chat_id), "text": str(text),
                "disable_web_page_preview": True}
            if buttons:
                payload["reply_markup"] = {"inline_keyboard": buttons}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            return self._checked(self._post("/sendMessage", payload, 60), "sendMessage")

        def edit(self, chat_id: int, message_id: int, text: str,
                 parse_mode: str | None = None) -> dict:
            payload = {"chat_id": int(chat_id), "message_id": int(message_id),
                       "text": str(text)}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            return self._checked(self._post("/editMessageText", payload, 60),
                                 "editMessageText")

        def set_my_commands(self, commands: list[dict], timeout: int = 30) -> dict:
            """Telegram ke "/" menu me 6 canonical commands dikhao (startup par)."""
            return self._checked(self._post("/setMyCommands",
                                            {"commands": commands}, timeout),
                                 "setMyCommands")

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
                  live: bool = True, skip_sources=None, skip_channels=None,
                  on_stage=None) -> dict:
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
                            skip_sources, on_stage=on_stage)
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
                "failed_channels": [], "report_path": "", "confidence": 0.0,
                "confidence_label": "n/a", "absence_kind": "fetch_failed",
                "items": [],
                "markdown": f"❌ Research error: {type(exc).__name__}: "
                            f"{util.truncate(str(exc), 300)}"}
    finally:
        try:
            pool.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # Python < 3.9
            pool.shutdown(wait=False)

    if out.get("blocked"):
        return {"ok": False, "sources": [], "channels": [],
                "failed_channels": [], "report_path": "", "confidence": 0.0,
                "confidence_label": "n/a", "absence_kind": "blocked", "items": [],
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
    metrics = out.get("metrics") or {}
    items = list(out.get("items") or [])
    sources_failed = sum(1 for d in (out.get("diagnostics") or []) if not d.get("ok"))
    if not items:
        absence = "fetch_failed" if sources_failed else "no_results"
    elif sources_failed:
        absence = "partial"
    else:
        absence = "ok"
    return {"ok": True, "markdown": md, "sources": sources,
            "channels": list(tg.get("channels") or []), "error": "",
            "failed_channels": [str(f.get("channel")) for f in (tg.get("failed") or [])
                                if f.get("channel")],
            "report_path": str((out.get("saved") or {}).get("md") or ""),
            "trace_path": str(out.get("trace_path") or ""),
            "confidence": float(metrics.get("confidence") or 0.0),
            "confidence_label": str(metrics.get("confidence_label") or "n/a"),
            "absence_kind": absence, "items": items}


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


def parse_action_callback(data: str) -> tuple[str, str]:
    """``add:ok:<handle>`` / ``add:no`` -> (action, handle). Ghalat = ('', '')."""
    m = re.fullmatch(r"add:(ok|no)(?::([A-Za-z0-9_]{3,40}))?",
                     str(data or "").strip())
    if not m:
        return "", ""
    return m.group(1), (m.group(2) or "")


def ask_after_report(row: dict, sources: int, channels: int) -> str:
    return ("❓ Aapko ye information mil gayi?\n\n"
            f"Round {row.get('round_no') or 1}: {sources} engines + "
            f"{channels} channels use hue (memory me save).\n"
            "Agar 'Nahi mila' dabayen to main naye sources/channels try karunga - "
            "jo use ho chuke hain wo skip ho jayenge.")



# --------------------------------------------------------------------------
# Command dispatch (chat -> action)
# --------------------------------------------------------------------------

def _addchannel_now(chat_id: int, handle: str, cfg: dict, api,
                    probe=None) -> dict:
    """Confirm ke baad channel save + probe + khabar (shared helper)."""
    try:
        channels_mod.add_channel(handle, origin="manual",
                                 note="user ne bot se add kiya (confirmed)")
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


def _ask_add_channel(chat_id: int, handle: str, api) -> dict:
    """Channel add ka confirm gate (✅/❌) — ``/channels add`` aur ``/addchannel``."""
    _pending_add[int(chat_id)] = handle
    buttons = [[{"text": "✅ Confirm", "callback_data": f"add:ok:{handle}"},
                {"text": "❌ Cancel", "callback_data": "add:no"}]]
    api.send(chat_id, f"➕ Channel add karein?\n\n@{handle}\nhttps://t.me/{handle}\n\n"
                      f"Save karne ke liye ✅ dabayein (cancel ❌).", buttons=buttons)
    return {"ok": True, "action": "addchannel_pending", "channel": handle,
            "pending": True}


def _do_channel_search(chat_id: int, arg: str, cfg: dict, api,
                       tg_search=None, action: str = "search") -> dict:
    """Saved channels ke andar keyword search (``/search`` / ``/tgsearch``)."""
    if not arg:
        api.send(chat_id, "Keyword likhein: /search firmware\n"
                          "(ya /channels <keyword> — dono ek hi kaam karte hain)")
        return {"ok": False, "action": action, "error": "query required"}
    try:
        api.send(chat_id, f'🔍 Channels ke andar search: "{arg}" ...')
    except Exception:
        pass
    try:
        res = (tg_search or channels_mod.search_posts)(arg, cfg=cfg)
    except Exception as exc:
        api.send(chat_id, f"❌ Channel search fail: {type(exc).__name__}: "
                          f"{util.truncate(str(exc), 200)}")
        return {"ok": False, "action": action, "error": "search failed"}
    send_chunks(api, chat_id, format_tg_results(res))
    return {"ok": True, "action": action, "query": arg,
            "count": len(res.get("items") or [])}


def _do_report(chat_id: int, arg: str, api) -> dict:
    """``/report [md|html]`` — aakhri saved report dobara bhejo (default md)."""
    fmt = str(arg or "").strip().lower() or "md"
    if fmt not in ("md", "html"):
        api.send(chat_id, "Format `md` ya `html` likhein. PDF is stdlib-only "
                          "project me support nahi karta.")
        return {"ok": False, "action": "report", "error": "bad format"}
    rows = store.list_reports(1)
    if not rows:
        api.send(chat_id, "Koi report nahi mila — pehle /research chalayein.")
        return {"ok": False, "action": "report", "error": "no report"}
    row = rows[0]
    md_path = str(row.get("path") or "")
    title = util.truncate(row.get("title") or "JIN Agent Brief", 80)
    if fmt == "html":
        html, err = report_export.from_report_file(md_path)
        if err or not html:
            api.send(chat_id, f"HTML export nahi bana ({err}) — MD bhej raha hoon.")
            if os.path.isfile(md_path):
                api.send_document(chat_id, md_path, caption=title)
                return {"ok": True, "action": "report", "fmt": "md", "path": md_path,
                        "fallback": "html unavailable"}
            api.send(chat_id, "Report file bhi nahi mili (purani entry).")
            return {"ok": False, "action": "report", "error": "report file missing"}
        html_path = os.path.splitext(md_path)[0] + ".html"
        try:
            with open(html_path, "w", encoding="utf-8") as fh:
                fh.write(html)
        except OSError as exc:
            api.send(chat_id, f"HTML file likhna fail ({type(exc).__name__}) — "
                              f"MD bhej raha hoon.")
            api.send_document(chat_id, md_path, caption=title)
            return {"ok": True, "action": "report", "fmt": "md", "path": md_path,
                    "fallback": "html write failed"}
        api.send_document(chat_id, html_path, caption=title)
        return {"ok": True, "action": "report", "fmt": "html", "path": html_path}
    if not os.path.isfile(md_path):
        api.send(chat_id, "Report file nahi mili (purani entry).")
        return {"ok": False, "action": "report", "error": "report file missing"}
    api.send_document(chat_id, md_path, caption=title)
    return {"ok": True, "action": "report", "fmt": "md", "path": md_path}


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
        try:
            ch = channels_mod.counts()
        except Exception:
            ch = {}
        text_status = format_status_text(cfg)
        health = source_health()
        b = health["buckets"]
        api.send(chat_id, text_status)
        return {"ok": True, "action": "status", "poll_failures": int(_poll_failures),
                "channels_active": int(ch.get("active") or 0),
                "channels_dead": int(ch.get("dead") or 0),
                "channels_archived": int(ch.get("archived") or 0),
                "channels_stale": int(ch.get("stale") or 0),
                "pending_candidates": channels_mod.pending_candidates(),
                "last_explore_at": last_explore_at(),
                "last_explore_scope": last_explore_scope(),
                "last_explore_topic": last_explore_topic(),
                "sites": channels_mod.site_counts().get("total", 0),
                "sites_week": channels_mod.site_counts().get("week", 0),
                "sources_total": health["total"],
                "sources_ok": b["ok"], "sources_failed": b["failed"],
                "sources_stale": b["stale"], "sources_disabled": b["disabled"],
                "sources_auto": health["auto"],
                "sources_registry_only": health["registry_only"]}
    if cmd == "sources":
        api.send(chat_id, f"Sources register open hai ({len(policy.register())} official/legal sources). "
                          f"/research <sawal> se detail.")
        return {"ok": True, "action": "sources"}
    if cmd == "channels":
        parts = str(arg or "").strip().split(None, 1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""
        if sub in ("add", "rm", "remove", "del", "delete"):
            if sub == "add":
                handle = channels_mod.clean_handle(rest)
                if not handle:
                    api.send(chat_id, "Link ya @username dein. Misal:\n"
                                      "/channels add https://t.me/durov\n"
                                      "ya channel ka koi post yahan forward kar dein.")
                    return {"ok": False, "action": "channels_add",
                            "error": "handle required"}
                return _ask_add_channel(chat_id, handle, api)
            handle = channels_mod.clean_handle(rest)
            if not handle:
                api.send(chat_id, "Handle dein: /channels rm @channelname")
                return {"ok": False, "action": "channels_rm",
                        "error": "handle required"}
            try:
                channels_mod.remove_channel(handle)
            except Exception as exc:
                api.send(chat_id, f"❌ {util.truncate(str(exc), 150)}")
                return {"ok": False, "action": "channels_rm", "error": "not found"}
            api.send(chat_id, f"🗄️ @{handle} archive kar diya (delete nahi hua).")
            return {"ok": True, "action": "channels_rm", "channel": handle}
        if sub in ("--all", "all"):
            rows = channels_mod.list_channels()
            send_chunks(api, chat_id, format_channels(rows, counts=channels_mod.counts()))
            return {"ok": True, "action": "channels_all", "count": len(rows)}
        if arg.strip():
            return _do_channel_search(chat_id, arg.strip(), cfg, api,
                                      tg_search=tg_search, action="channels_search")
        rows = channels_mod.list_channels("active")
        send_chunks(api, chat_id, format_channels(rows, counts=channels_mod.counts()))
        return {"ok": True, "action": "channels", "count": len(rows)}
    if cmd in ("search", "tgsearch"):
        return _do_channel_search(chat_id, arg, cfg, api,
                                  tg_search=tg_search,
                                  action="tgsearch" if cmd == "tgsearch" else "search")
    if cmd == "addchannel":
        handle = channels_mod.clean_handle(arg)
        if not handle:
            api.send(chat_id, "Link ya @username dein. Misal:\n"
                              "/addchannel https://t.me/durov\n"
                              "ya channel ka koi post yahan forward kar dein.")
            return {"ok": False, "action": "addchannel", "error": "handle required"}
        return _ask_add_channel(chat_id, handle, api)
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
        topic = str(arg or "").strip()
        if topic:
            # ``/deep <topic>`` — deep research chalao + deep engines ke links
            # report ke saath (onion sirf link, fetch kabhi nahi hota).
            try:
                composed = chat_context.attach(chat_id, topic)
                chat_context.note(chat_id, topic)
            except Exception:
                composed = topic
            res = _send_research(chat_id, composed, cfg=cfg, api=api, research=research)
            if res.get("ok"):
                send_chunks(api, chat_id, format_deep(topic))
                res["deep"] = True
            return res
        # Bina topic: sirf deep-engine list (purana raasta barqarar)
        send_chunks(api, chat_id, format_deep(arg))
        return {"ok": True, "action": "deep", "count": len(DEEP_ENGINES)}
    if cmd == "memory":
        rows = memory_mod.recent(chat_id, 6)
        send_chunks(api, chat_id, format_memory(rows))
        return {"ok": True, "action": "memory", "count": len(rows)}
    if cmd == "new":
        try:
            closed = memory_mod.reset_chat(chat_id)
        except Exception:
            closed = 0
        try:
            chat_context.clear(chat_id)
        except Exception:
            pass
        _pending_add.pop(int(chat_id), None)
        _STATUS_MESSAGES.pop(int(chat_id), None)
        _STATUS_LAST_EDIT.pop(int(chat_id), None)
        _EXPLORE_PENDING.pop(int(chat_id), None)
        _EXPLORE_SHOWN.pop(int(chat_id), None)
        api.send(chat_id, f"🌱 Naya context shuru — {closed} purana research band kar "
                          f"diya. Naya /research foran shuru ho jayega.")
        return {"ok": True, "action": "new", "closed": int(closed)}
    if cmd == "digest":
        try:
            out = orchestrator.digest(cfg)
        except Exception as exc:
            api.send(chat_id, f"❌ Digest fail: {type(exc).__name__}: "
                              f"{util.truncate(str(exc), 150)}")
            return {"ok": False, "action": "digest", "error": "digest failed"}
        path = str((out.get("saved") or {}).get("md") or "")
        send_chunks(api, chat_id, f"📔 Daily digest tayyar "
                                  f"({out['report']['facts_count']} items).\n"
                                  f"Local report: {path or 'n/a'}")
        return {"ok": True, "action": "digest",
                "items": int(out["report"]["facts_count"]), "path": path}
    if cmd == "alerts":
        rows = [e for e in store.list_events(30) if e.get("kind") == "alert"]
        if not rows:
            api.send(chat_id, "🔔 Koi alert nahi.")
        else:
            send_chunks(api, chat_id, "🔔 Recent alerts:\n" + "\n".join(
                f"• {util.truncate(e.get('detail') or '', 120)}" for e in rows[:10]))
        return {"ok": True, "action": "alerts", "count": len(rows)}
    if cmd == "reports":
        rows = store.list_reports(10)
        if not rows:
            api.send(chat_id, "📄 Koi report nahi.")
        else:
            send_chunks(api, chat_id, "📄 Recent reports:\n" + "\n".join(
                f"• {util.truncate(r.get('title') or '', 80)} — {r.get('path') or ''}"
                for r in rows))
        return {"ok": True, "action": "reports", "count": len(rows)}
    if cmd == "report":
        return _do_report(chat_id, arg, api)
    if cmd == "schedule":
        sch = cfg.get("schedule") or {}
        lines = ["⏰ Schedule (minutes):"] + [f"• {k}: {v}" for k, v in sorted(sch.items())]
        api.send(chat_id, "\n".join(lines))
        return {"ok": True, "action": "schedule"}
    if cmd == "channelhealth":
        send_chunks(api, chat_id, format_channel_health())
        return {"ok": True, "action": "channelhealth"}
    if cmd == "memoryaudit":
        out = memory_mod.audit()
        send_chunks(api, chat_id, format_memory_audit(out))
        return {"ok": True, "action": "memoryaudit", **out}
    if cmd == "selftest":
        res = channels_mod.parser_selftest()
        send_chunks(api, chat_id, format_selftest(res))
        return {"ok": True, "action": "selftest", "ok": bool(res.get("ok"))}
    if cmd == "dork":
        return _send_dork(chat_id, arg, cfg, api)
    if cmd == "explore":
        # Topic required — bina topic par topic picker (koi niche default nahi).
        return _run_explore(chat_id, arg.strip(), "all", cfg, api)
    if cmd == "research":
        query, deep = split_deep_flag(arg)
        if not query:
            api.send(chat_id, "Research ke liye query likhein: /research <sawal>")
            return {"ok": False, "action": "research", "error": "query required"}
        # Multi-turn: chhota follow-up ho to pichhla sawal context me jodo
        # (max 1). Context table na hone par research as-is chalta rahe.
        try:
            composed = chat_context.attach(chat_id, query)
            chat_context.note(chat_id, query)
        except Exception:
            composed = query
        res = _send_research(chat_id, composed, cfg=cfg, api=api, research=research)
        if deep and res.get("ok"):
            # ``/deep`` ka kaam ek jagah: deep engines links report ke saath.
            send_chunks(api, chat_id, format_deep(query))
            res["deep"] = True
        return res
    api.send(chat_id, "Maaf kijiye, yeh command samajh nahi aaya. /help use kijiye.")
    return {"ok": False, "action": "unknown", "error": "unknown command"}


def format_channel_health() -> str:
    """Channel health digest — "alive magar khamosh" (last_post_at purana)."""
    counts = channels_mod.counts()
    rows = channels_mod.list_channels("active")
    quiet = []
    for row in rows:
        age = channels_mod._age_days(row.get("last_post_at") or "")
        if age > 30:
            quiet.append((str(row.get("channel") or ""), int(age),
                          str(row.get("last_post_at") or "")))
    lines = [f"🩺 Channel health: {counts.get('active', 0)} active / "
             f"{counts.get('dead', 0)} dead / {counts.get('archived', 0)} archived / "
             f"{counts.get('stale', 0)} stale"]
    if quiet:
        lines += ["", "⚠️ Alive magar khamosh (last post > 30 din):"]
        for handle, age, last in quiet[:10]:
            lines.append(f"• @{handle} — {age} din ({last[:10]})")
    else:
        lines += ["", "✅ Saare active channels fresh hain (last post <= 30 din)."]
    return "\n".join(lines)


def format_memory_audit(out: dict) -> str:
    out = out or {}
    lines = ["🧾 Memory audit:", "",
             f"• duplicates: {len(out.get('duplicates') or [])}",
             f"• conflicts: {len(out.get('conflicts') or [])}",
             f"• stale active: {len(out.get('stale') or [])}"]
    for row in (out.get("duplicates") or [])[:5]:
        lines.append(f"  - dup: {util.truncate(str(row.get('query') or ''), 70)} "
                     f"({row.get('count')} rows)")
    for row in (out.get("conflicts") or [])[:5]:
        lines.append(f"  - conflict: {util.truncate(str(row.get('query') or ''), 70)}")
    for row in (out.get("stale") or [])[:5]:
        lines.append(f"  - stale: {util.truncate(str(row.get('query') or ''), 70)} "
                     f"({row.get('age_days')} din)")
    return "\n".join(lines)


def format_selftest(res: dict) -> str:
    res = res or {}
    ok = bool(res.get("ok"))
    lines = [f"🧪 Parser selftest: {'PASS' if ok else 'FAIL'}", ""]
    for check in res.get("checks") or []:
        mark = "✅" if check.get("ok") else "❌"
        lines.append(f"{mark} {check.get('name', '')}: {check.get('detail', '')}")
    return "\n".join(lines)


def _status_supported(api) -> bool:
    return hasattr(api, "edit")


def _edit_status(chat_id: int, api, text: str) -> bool:
    """Progress ko naye message ki jagah wahi message edit karke dikhao."""
    mid = _STATUS_MESSAGES.get(int(chat_id))
    if not mid:
        return False
    try:
        return bool(api.edit(chat_id, mid, text))
    except Exception:
        return False


def _stage_status(chat_id: int, api, text: str,
                  min_gap: float | None = None) -> bool:
    """Research stage edit — Telegram ki 20/min limit ke andar (3s throttle)."""
    gap = STATUS_EDIT_MIN_GAP if min_gap is None else max(0.0, float(min_gap))
    now = time.monotonic()
    last = float(_STATUS_LAST_EDIT.get(int(chat_id), 0.0) or 0.0)
    if now - last < gap:
        return False
    if not _edit_status(chat_id, api, text):
        return False
    _STATUS_LAST_EDIT[int(chat_id)] = now
    return True


def _trace_display(path: str) -> str:
    """Trace ka local path ``data/runs/<id>.json`` ki shakl me (jhooti URL nahi)."""
    p = str(path or "").strip()
    if not p:
        return ""
    try:
        rel = os.path.relpath(p, str(config.data_dir()))
        if rel and not rel.startswith(".."):
            return "data/" + rel.replace(os.sep, "/")
    except Exception:
        pass
    return os.path.basename(p)


def _bluf_text(query: str, out: dict, confidence: float, label: str,
               sources: list, channels: list, kind: str = "ok",
               trace_path: str = "") -> str:
    """BLUF — TL;DR + 3-5 key findings, <=1000 chars (poori report file me)."""
    items = []
    for it in (out.get("items") or [])[:5]:
        title = util.truncate(str(it.get("title") or "").strip(), 100)
        if title:
            items.append("• " + title)
    body = "\n".join(items[:5]) if items else "• Koi key finding nahi mili."
    note = {"partial": " (partial — kuch sources fail)"}.get(kind, "")
    text = (f"📌 Report tayyar hai{note} — {util.truncate(query, 70)}\n\n"
            f"{body}\n\nConfidence: {label} ({confidence}) · "
            f"{len(sources)} engines · {len(channels)} channels")
    trace = _trace_display(trace_path)
    if trace:
        text += f"\n🗂️ Trace: {trace}"
    return text[:1000]


def _group_allowed(chat_id: int, limit: int | None = None) -> bool:
    """Per-chat sliding-window rate limit (default 20/min)."""
    lim = GROUP_RATE_LIMIT if limit is None else max(1, int(limit))
    now = time.monotonic()
    hits = [t for t in _GROUP_HITS.get(int(chat_id), []) if now - t < 60.0]
    if len(hits) >= lim:
        _GROUP_HITS[int(chat_id)] = hits
        return False
    hits.append(now)
    _GROUP_HITS[int(chat_id)] = hits
    return True


def _call_research_full(query: str, cfg: dict, skip_sources, skip_channels,
                        on_stage) -> dict:
    """``research_full`` ko on_stage ke saath bulayo — purane mocks jin me ye
    param nahi, un par bina on_stage fallback (tests/backward compat)."""
    fn = research_full
    accepts = True
    try:
        params = inspect.signature(fn).parameters
        accepts = (any(p.kind == p.VAR_KEYWORD for p in params.values())
                   or "on_stage" in params)
    except (TypeError, ValueError):
        accepts = True
    if accepts:
        return fn(query, cfg, skip_sources=skip_sources,
                  skip_channels=skip_channels, on_stage=on_stage)
    return fn(query, cfg, skip_sources=skip_sources,
              skip_channels=skip_channels)


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
        failed: list[str] = []
        round_no = 1
        if row_id:
            row = memory_mod.get(row_id) or {}
            used_sources = row.get("used_sources") or []
            used_channels = row.get("used_channels") or []
            failed = memory_mod.failed_channels(row_id)
            round_no = int(row.get("round_no") or 1) + (1 if advance else 0)
            if advance and round_no > max_rounds():
                limit = max_rounds()
                api.send(chat_id, f"🛑 Aur sources nahi mile. Round limit ({limit}) "
                                  f"chuki — naya /research shuru karein.")
                return {"ok": False, "action": "research", "error": "max rounds"}
        header = ("🔍 Research chal rahi hai... (30-60 seconds lag sakte hain)\n"
                  "🛑 Rokne ke liye /stop likhein") if round_no <= 1 else \
                 (f"🔁 Round {round_no}: naye sources/channels try ho rahe hain "
                  f"({len(used_sources)} engines + {len(used_channels)} channels skip)...\n"
                  "🛑 Rokne ke liye /stop likhein")
        try:
            header_res = api.send(chat_id, header)
            if _status_supported(api) and isinstance(header_res, dict):
                mid = int((header_res.get("result") or {}).get("message_id") or 0)
                if mid:
                    _STATUS_MESSAGES[int(chat_id)] = mid
        except Exception:
            pass

        _STATUS_LAST_EDIT.pop(int(chat_id), None)

        def on_stage(name: str, detail: str = "") -> None:
            """Plan → Sources → Fetch → Verify → Brief — wahi message edit (3s throttle)."""
            _stage_status(chat_id, api,
                          f"⏳ {name} — {util.truncate(query, 60)}"
                          + (f" ({util.truncate(detail, 40)})" if detail else ""))

        result_box = [None]
        # Agla round: use ho chuke AUR failed (negative memory) channels skip.
        skip_channels = list(dict.fromkeys(used_channels + failed))

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
                        final = _call_research_full(q, cfg, used_sources,
                                                    skip_channels, on_stage)
                        if str((final or {}).get("markdown") or "").strip():
                            break
                    result_box[0] = final
                elif research is None:
                    result_box[0] = _call_research_full(
                        query, cfg, used_sources, skip_channels, on_stage)
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
            failed_new = [str(c) for c in (out.get("failed_channels") or [])]
            report_path = str(out.get("report_path") or "")
            trace_path = str(out.get("trace_path") or "")
            confidence = float(out.get("confidence") or 0.0)
            confidence_label = str(out.get("confidence_label") or "n/a")
            absence_kind = str(out.get("absence_kind") or "ok")
        else:
            md, sources, channels_used = str(out or ""), [], []
            failed_new, report_path, trace_path = [], "", ""
            confidence, confidence_label = 0.0, "n/a"
            absence_kind = "ok"
        if not md.strip():
            md = "❌ Report khali rahi. /research dobara try karein."

        final_md = md
        try:
            translated = llm.translate_text(cfg, md)
            if translated:
                final_md = translated  # foreign sources -> Roman Urdu report
        except Exception:
            final_md = md

        # Delivery stage: report tayyar — wahi status message edit (throttle ki
        # parsed asaan hai; aakhri edit hamesha lagti hai).
        _edit_status(chat_id, api, f"✅ Report tayyar hai — {util.truncate(query, 60)}")
        # Delivery: report file (sendDocument) — chat flood ki jagah. Confidence
        # gate ke niche file nahi bhejti, sirf khabar local console ki taraf.
        threshold = verifier.confidence_threshold()
        delivered = False
        chunks: list[str] = []
        if report_path and os.path.isfile(report_path):
            caption = (f"📄 JIN Agent Brief — {util.truncate(query, 80)}\n"
                       f"Confidence: {confidence_label} ({confidence})\n"
                       f"{len(sources)} engines · {len(channels_used)} channels"
                       + (f"\n🗂️ Trace: {_trace_display(trace_path)}" if trace_path else ""))
            if absence_kind == "no_results":
                api.send(chat_id, "🔍 Koi result nahi mila — sources live the magar is "
                                  "query par kuch nahi aaya. Chhota keyword ya /explore "
                                  "try karein.")
                delivered = True
            elif absence_kind == "fetch_failed":
                api.send(chat_id, "⚠️ Fetch fail hua — sources reach nahi hue; report "
                                  "incomplete. Detail local console par hai.")
                delivered = True
            elif confidence >= threshold:
                try:
                    _edit_status(chat_id, api,
                                 f"✅ Report tayyar hai — {util.truncate(query, 60)}")
                    bluf = _bluf_text(query, out if isinstance(out, dict) else {},
                                      confidence, confidence_label, sources,
                                      channels_used, absence_kind,
                                      trace_path=trace_path)
                    try:                       # query ke lafz <b> se highlight
                        api.send(chat_id, _highlight_html(bluf, query),
                                 parse_mode="HTML")
                    except TypeError:          # fake/purana API — plain fallback
                        api.send(chat_id, bluf)
                    if SEND_DELAY > 0:
                        time.sleep(SEND_DELAY)
                    api.send_document(chat_id, report_path, caption=caption)
                    delivered = True
                except Exception as exc:
                    print(f"[bot] sendDocument fail ({type(exc).__name__}: {exc}); "
                          f"chunks par wapas", flush=True)
            else:
                try:
                    api.send(chat_id, f"⚠️ Report bharosemand nahi "
                                      f"(confidence {confidence_label} {confidence} < "
                                      f"{threshold}) — detail local console par hai.")
                    delivered = True
                except Exception:
                    pass
        if not delivered:
            html = _highlight_html(final_md, query)      # query terms <b> me
            chunks = highlight_mod.split_html(html)      # entity-safe + balanced
            for i, chunk in enumerate(chunks):
                if not _session_active(session):
                    api.send(chat_id, "🛑 Report rok di gayi.")
                    break
                if i and SEND_DELAY > 0:
                    time.sleep(SEND_DELAY)
                try:
                    api.send(chat_id, chunk, parse_mode="HTML")
                except TypeError:  # fake/purana API — plain text fallback
                    api.send(chat_id, chunk)

        # Memory: kaunse sources/channels is round me use hue
        try:
            if row_id:
                row = memory_mod.remember(row_id, sources, channels_used,
                                          advance=advance)
            else:
                row = memory_mod.begin(chat_id, query)
                row = memory_mod.remember(row["id"], sources, channels_used)
            if row and row.get("id"):
                if failed_new:
                    try:
                        memory_mod.remember_failed(row["id"], failed_new)
                    except Exception:
                        pass
                for src in sources:
                    try:
                        memory_mod.note_source_stat(row["id"], src, "cited")
                    except Exception:
                        pass
                if advance:
                    try:
                        memory_mod.remember_rejected(row["id"], [query])
                    except Exception:
                        pass
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
    act, handle = parse_action_callback(data)
    if act in ("ok", "no"):
        if act == "no":
            _pending_add.pop(int(chat_id), None)
            api.send(chat_id, "❌ Channel add cancel ho gaya.")
            return {"ok": True, "action": "addchannel_cancel"}
        target = handle or _pending_add.pop(int(chat_id), None)
        if not target:
            api.send(chat_id, "Purana confirmation hai. Dobara /addchannel karein.")
            return {"ok": False, "action": "addchannel", "error": "expired"}
        return _addchannel_now(chat_id, target, cfg, api)
    topic_hash = parse_explore_topic_callback(data)
    if topic_hash:
        topic = _EXPLORE_TOPICS.get(topic_hash, "")
        if not topic:
            api.send(chat_id, "Purana topic button hai. Naya /explore karein.")
            return {"ok": False, "action": "explore", "error": "expired"}
        return _run_explore(chat_id, topic, "all", cfg, api)
    more_hash = parse_explore_more_callback(data)
    if more_hash:
        # "Aur explore karo": wahi topic dobara discovery. run_discovery purane
        # (known) channels ko chhod deta hai, is liye naye cards milte hain.
        topic = _EXPLORE_TOPICS.get(more_hash, "")
        if not topic:
            api.send(chat_id, "Purana explore button hai. Naya /explore karein.")
            return {"ok": False, "action": "explore_more", "error": "expired"}
        return _run_explore(chat_id, topic, "all", cfg, api)
    scope, scope_hash = parse_explore_scope_callback(data)
    if scope:
        pending = _EXPLORE_PENDING.get(int(chat_id)) or {}
        topic = str(pending.get("topic") or "") or _EXPLORE_TOPICS.get(scope_hash, "")
        if not topic:
            api.send(chat_id, "Purana scope button hai. Naya /explore karein.")
            return {"ok": False, "action": "explore", "error": "expired"}
        groups = pending.get("groups")
        if groups:
            # Wahi items, sirf scope filter (shown memory dobara na lagay)
            return _render_explore(chat_id, topic, scope, None, cfg, api,
                                   groups=groups)
        return _run_explore(chat_id, topic, scope, cfg, api)
    exp_action, exp_key = parse_explore_callback(data)
    if exp_action:
        return _handle_explore_callback(chat_id, exp_action, exp_key, cfg, api)
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
    global _poll_failures
    cfg = cfg or config.load()
    api = api or _api(token, cfg)
    stop = stop or type("S", (), {"is_set": lambda self: False})()
    workers = update_workers()
    pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="jin-update")

    # Telegram "/" menu: 6 canonical commands (best-effort, startup par ek dafa).
    try:
        if register_commands(api):
            print("[bot] Telegram command menu set (6 commands)", flush=True)
    except Exception as exc:
        print(f"[bot] setMyCommands fail ({type(exc).__name__}: {exc}) — ignore",
              flush=True)

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
        # KHABARDAAR: offset ko 0 par reset NAHI karte — warna restart ke baad saari
        # pending updates dobara process hoti thin (duplicate reports + 429 flood).
        # Aakhri kaamyaab offset hi rehta hai.
        print(f"[bot] startup drain fail ({type(exc).__name__}: {exc}); "
              f"offset={offset} se shuru (reset nahi kiya)", flush=True)
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
    _poll_failures = 0
    max_fail = max_poll_failures()
    if max_fail:
        print(f"[bot] poll failure cap: {max_fail} (0 = unlimited)", flush=True)

    try:
        while not stop.is_set():
            try:
                updates = api.get_updates(offset, POLL_TIMEOUT) or []
            except Exception as exc:
                fail_count += 1
                _poll_failures = fail_count
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
                _poll_failures = 0
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
                            _submit_control(
                                pool,
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
                    text = route_plain_text(text, forwarded_handle(msg))
                if not text or text == "/addchannel ":
                    continue
                if not is_owner(chat_id, cfg):
                    continue
                # Bounded pool: dispatch loop ko block nahi karta aur flood par
                # threads ki tadad env cap ke andar rehti hai. /stop aur /status
                # ke liye dedicated thread — busy research workers ke peeche
                # nahi atkte (2 busy workers par bhi /stop foran chalta hai).
                cmd_name, _ = parse_command(text)
                # Per-chat group rate limit (default 20/min); control commands
                # (stop/status) is se exempt taa ke roknay ka raasta khula rahe.
                if cmd_name not in ("stop", "status") and not _group_allowed(chat_id):
                    continue
                try:
                    if _is_heavy_command(cmd_name):
                        # Research/report banata hai — main bounded pool (worker
                        # rooshta hai; isi liye light commands is pool ko chhorti hain)
                        pool.submit(dispatch, chat_id, text, cfg=cfg, api=api)
                    else:
                        # Light command — control pool, busy research ke peeche
                        # nahi atka (live test me 10-45s lag tha)
                        _submit_control(pool, dispatch, chat_id, text,
                                        cfg=cfg, api=api)
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
        try:
            _shutdown_control_pool()
        except Exception:
            pass
        _cancel_research(join_timeout=1.0)


def status(cfg: dict | None = None) -> dict:
    cfg = cfg or config.load()
    out = {
        "version": VERSION,
        "policy_id": "SAHULAT-SAFE-SERVICE-v1",
        "bot_token_set": bool(str(cfg.get("telegram_bot_token") or "").strip()),
        "chat_id_set": bool(str(cfg.get("telegram_chat_id") or "").strip()),
        "llm": cfg.get("llm") or {},
        "tor_mode": cfg.get("tor_mode") or "links_only",
        "poll_failures": int(_poll_failures),
        "max_rounds": max_rounds(),
        "send_delay": send_delay(),
    }
    try:
        ch = channels_mod.counts()
        out["channels_active"] = int(ch.get("active") or 0)
        out["channels_dead"] = int(ch.get("dead") or 0)
        out["channels_archived"] = int(ch.get("archived") or 0)
        out["channels_stale"] = int(ch.get("stale") or 0)
        out["pending_candidates"] = channels_mod.pending_candidates()
        out["sites"] = channels_mod.site_counts().get("total", 0)
    except Exception:
        out["channels_active"] = 0
        out["channels_dead"] = 0
        out["channels_archived"] = 0
        out["channels_stale"] = 0
        out["pending_candidates"] = 0
        out["sites"] = 0
    return out
