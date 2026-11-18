"""Optional local LLM client (Ollama / LM Studio / custom OpenAI-compatible).

The model NEVER gets raw internet access. It only produces structured tool
requests, which planner.validate() checks before planner.dispatch() fetches
anything. When the provider is OFF (default), every caller falls back to the
deterministic rule-based path - no model is required to run the agent.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from . import policy, util

LOCAL_BASES = {
    "ollama": "http://127.0.0.1:11434/v1",
    "lmstudio": "http://127.0.0.1:1234/v1",
}
PROVIDERS = ("off", "ollama", "lmstudio", "custom")

SYSTEM_RESEARCH = (
    "You are a professional research assistant. Summarize ONLY the provided "
    "sources. Never invent facts, URLs, dates or citations. Separate facts "
    "from recommendations. Write explanations in natural Roman Urdu while "
    "keeping technical terms and headings in English. For sensitive topics "
    "give high-level educational information and cite official sources. "
    "Never provide operational instructions for bypassing ownership controls, "
    "device unlocking, or writing/erasing device partitions."
)

SYSTEM_PLANNER = (
    "You choose research tools. Reply with ONLY a JSON array of objects of the "
    "form {\"tool\":\"name\",\"args\":{...}}. Allowed tools are listed below. "
    "Never include URLs you have not been given. Never ask for shell, file, "
    "POST or raw browsing access. Maximum 6 calls."
)


def resolve(cfg: dict | None = None) -> dict:
    cfg = cfg or {}
    llm = cfg.get("llm") or {}
    provider = str(llm.get("provider") or "off").strip().lower()
    if provider not in PROVIDERS:
        provider = "off"
    model = str(llm.get("model") or "").strip()
    key = str(llm.get("key") or "").strip()
    endpoint = str(llm.get("endpoint") or "").strip()
    reason, key_required, base = "", False, ""
    if provider in LOCAL_BASES:
        base = LOCAL_BASES[provider]
    elif provider == "custom":
        key_required = True
        if not policy.trusted_public_endpoint(endpoint):
            reason = "Custom endpoint public https host hona chahiye (IP / internal mana hai)."
        else:
            base = endpoint.rstrip("/")
    else:
        reason = "Model band hai: provider OFF. Rule-based Roman Urdu chal raha hai (ye bug nahi)."
    if provider != "off" and not model and not reason:
        reason = "Model name set karein."
    if provider == "custom" and not key and not reason:
        reason = "Custom provider ke liye API key zaroori hai."
    enabled = bool(base and model and (key or not key_required) and not reason)
    return {
        "enabled": enabled, "provider": provider, "base": base, "model": model,
        "key": key, "key_required": key_required, "key_present": bool(key),
        "mode": "llm" if enabled else "rule_based", "reason": reason,
    }


def status(cfg: dict | None = None) -> dict:
    """Key-free diagnostics for /api/status and Settings."""
    c = resolve(cfg)
    return {k: c[k] for k in ("enabled", "provider", "model", "mode", "reason",
                              "key_required", "key_present")} | {"endpoint": c["base"]}


def _post(cfg: dict, messages: list[dict], timeout: float = 30) -> dict:
    c = resolve(cfg)
    if not c["enabled"]:
        return {"ok": False, "error": c["reason"] or "Model enabled nahi hai"}
    url = c["base"] + "/chat/completions"
    payload = json.dumps({"model": c["model"], "messages": messages,
                          "temperature": 0.2, "max_tokens": 900}).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if c["key"]:
        headers["Authorization"] = "Bearer " + c["key"]
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read(1_000_000).decode("utf-8", "replace"))
        text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        return {"ok": bool(text), "text": text.strip(),
                "latency_ms": round((time.monotonic() - started) * 1000),
                "error": "" if text else "Model ne khali jawab diya"}
    except Exception as exc:
        return {"ok": False, "text": "",
                "latency_ms": round((time.monotonic() - started) * 1000),
                "error": f"{type(exc).__name__}: {util.truncate(str(exc), 160)}"}


def chat(cfg: dict, system: str, user: str, timeout: float = 30) -> dict:
    return _post(cfg, [{"role": "system", "content": system},
                       {"role": "user", "content": str(user)[:8000]}], timeout)


def probe(cfg: dict | None = None, timeout: float = 8) -> dict:
    c = resolve(cfg or {})
    if not c["enabled"]:
        return {"ok": False, "provider": c["provider"], "model": c["model"],
                "error": c["reason"], "latency_ms": 0}
    out = chat(cfg or {}, "Reply with exactly: OK", "ping", timeout)
    return {"ok": out["ok"], "provider": c["provider"], "model": c["model"],
            "error": out["error"], "latency_ms": out["latency_ms"]}


def tool_plan(cfg: dict, query: str, tool_names: list[str], timeout: float = 30):
    """Ask the model for tool requests. Returns a list, or None on any failure."""
    if not resolve(cfg)["enabled"]:
        return None
    prompt = ("User request: " + str(query)[:1200] +
              "\nAllowed tools: " + ", ".join(tool_names) +
              "\nReturn ONLY the JSON array.")
    out = chat(cfg, SYSTEM_PLANNER, prompt, timeout)
    if not out["ok"]:
        return None
    text = out["text"].strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return None
    try:
        calls = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return calls if isinstance(calls, list) else None


def polish(cfg: dict, text: str, timeout: float = 30) -> str | None:
    """Rewrite report prose only. Never adds facts; caller keeps the citations."""
    if not resolve(cfg)["enabled"]:
        return None
    out = chat(cfg, SYSTEM_RESEARCH,
               "Rewrite this research note in professional Roman Urdu, 2 sentences, "
               "adding no facts: " + str(text)[:1500], timeout)
    return out["text"][:600] if out["ok"] else None


def related_queries(cfg: dict, query: str, n: int = 3, timeout: float = 30) -> list[str]:
    """LLM se related research sub-queries generate karo (fallback: []).

    User ka /research flow "related round" isi se banta hai: "nahi mila" →
    LLM related queries → naye queries engines + channels par search.
    """
    if not resolve(cfg)["enabled"]:
        return []
    n = max(1, int(n or 3))
    prompt = ("User research question: " + str(query)[:1200] +
              "\nGenerate " + str(n) + " closely related research sub-queries "
              "(different angles/magnitudes of the same topic). "
              "Return ONLY a JSON array of short strings.")
    out = chat(cfg, SYSTEM_RESEARCH, prompt, timeout)
    if not out["ok"]:
        return []
    text = out["text"].strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        arr = json.loads(text[start:end + 1])
    except ValueError:
        return []
    if not isinstance(arr, list):
        return []
    out_q = [str(x).strip() for x in arr if str(x).strip()]
    return out_q[:n]


def translate_text(cfg: dict, text: str, timeout: float = 30) -> str:
    """Source content ko Roman Urdu me translate karo (facts/URLs mat badlo)."""
    if not resolve(cfg)["enabled"]:
        return ""
    out = chat(cfg, SYSTEM_RESEARCH,
               "Translate this source content into natural Roman Urdu (Roman Urdu + English "
               "technical terms), changing NOTHING except language: " + str(text)[:1500],
               timeout)
    return out["text"][:1200] if out["ok"] else ""
