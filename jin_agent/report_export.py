"""HTML report export — stdlib-only (P37).

Competitor tools HTML/PDF/MD dete hain; JIN pehle sirf `.md` deta tha. Ye
module briefer report dict (ya uska structured JSON) saaf HTML me badalta hai.

PDF ke liye third-party library (reportlab / weasyprint) zaroori hoti hai aur
yeh project **stdlib-only** hai — is liye PDF jaan-boojh kar nahi gaya. MD
aur HTML hi export formats hain.

Hur achhi report me saara user/report data ``html.escape`` se guzarta hai;
adhuri report (khaali items, missing keys) par bhi output valid HTML rehta hai.
"""

from __future__ import annotations

import html
import json

from . import briefer, highlight, policy, util

_STYLE = """
body{font-family:system-ui,Arial,sans-serif;margin:2rem;background:#f5f7fa;
     color:#1c2733;line-height:1.5}
.card{background:#fff;border:1px solid #d8e0e8;border-radius:8px;
      padding:1rem 1.25rem;margin-bottom:1rem}
h1{font-size:1.5rem;margin:0 0 .5rem}
h2{font-size:1.2rem;margin:1.25rem 0 .5rem;border-bottom:1px solid #d8e0e8;
   padding-bottom:.25rem}
h3{font-size:1.05rem;margin:1rem 0 .25rem}
.meta{color:#5b6b7b;font-size:.9rem}
.item{border-left:3px solid #3568b0;padding-left:.75rem;margin:.75rem 0}
.ok{color:#1a7739}.fail{color:#b42318}
table{border-collapse:collapse;width:100%;font-size:.9rem}
td,th{border:1px solid #d8e0e8;padding:4px 8px;text-align:left;vertical-align:top}
pre{background:#0f1720;color:#e6edf3;padding:.75rem;border-radius:6px;
    overflow:auto;font-size:.8rem}
"""


def _esc(value) -> str:
    """HTML-escape — koi raw user/report text markup me kabhi nahi jayega."""
    return html.escape("" if value is None else str(value), quote=True)


def _structured(report) -> dict:
    """``briefer.build()`` dict ya structured dict — dono se data nikalo."""
    if not isinstance(report, dict):
        return {}
    raw = report.get("json")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            return parsed
    return report


def _link(url) -> str:
    """Sirf http/https href — ``javascript:`` jaisi schemes kabhi link nahi."""
    u = str(url or "").strip()
    if u.lower().startswith(("http://", "https://")):
        return f'<a href="{_esc(u)}">{_esc(u)}</a>'
    return _esc(u)


def _items(report: dict, structured: dict) -> list[dict]:
    rows = structured.get("items")
    if not isinstance(rows, list):
        rows = report.get("items") if isinstance(report.get("items"), list) else []
    return [r for r in rows if isinstance(r, dict)]


def _bucket_sections(items: list[dict], terms: list[str],
                     summaries: dict[str, str] | None = None) -> list[str]:
    """Items ko beginner buckets me group karke HTML (bucket headings ke saath)."""
    by_bucket: dict[str, list[dict]] = {}
    for item in items:
        by_bucket.setdefault(briefer.bucket_for(item.get("category", "")), []).append(item)
    out = []
    for bucket in briefer.BUCKET_ORDER:
        rows = by_bucket.get(bucket)
        if not rows:
            continue
        out.append(f"<h3>{_esc(bucket)}</h3>")
        for item in rows[:5]:
            meta = item.get("meta") or {}
            if item.get("cross_verified"):
                cross = "yes"
            elif meta.get("offline") or item.get("link_only"):
                cross = "no (offline fixture / link-only: independent corroboration nahi)"
            else:
                cross = "no"
            source = briefer.display_source(item)
            title = highlight.highlight_html(_esc(item.get("title") or ""), terms)
            out.append(f'<div class="item"><strong>{title}</strong>'
                       f'<p class="meta">Source: {_esc(source)} | '
                       f'Category: {_esc(item.get("category") or "")} | '
                       f'Tier: {_esc(item.get("tier") or "")} | '
                       f'Date checked: {_esc(item.get("date_checked") or "")} | '
                       f'Published: {_esc(item.get("published") or "n/a")} | '
                       f'Confidence: {_esc(item.get("confidence") or 0)} | '
                       f'Trust: {_esc(item.get("trust_label") or "")} | '
                       f'Score: {_esc(item.get("score") or 0)}</p>'
                       f'<p class="meta">URL: {_link(item.get("url") or "")}</p>'
                       f'<p>{highlight.highlight_html(_esc(briefer.khulasa(item, None, summaries)), terms)}</p>'
                       f'<p class="meta">Cross-verified: {_esc(cross)}</p></div>')
        if len(rows) > 5:
            out.append(f'<p class="meta">{_esc(bucket)} mein mazid '
                       f'{len(rows) - 5} items archive mein hain.</p>')
    return out


def _sources_section(diagnostics) -> list[str]:
    rows = diagnostics if isinstance(diagnostics, list) else []
    out = ["<h2>Sources &amp; Diagnostics</h2>", "<table>",
           "<tr><th>Source</th><th>Tier</th><th>Status</th>"
           "<th>Items</th><th>Note</th></tr>"]
    if not rows:
        out.append("<tr><td>(none)</td><td>-</td><td>-</td><td>0</td>"
                   "<td>Blocked request par koi fetch nahi hua</td></tr>")
    for diag in rows:
        if not isinstance(diag, dict):
            continue
        status = "OK" if diag.get("ok") else "FAIL"
        cls = "ok" if diag.get("ok") else "fail"
        out.append(
            f'<tr><td>{_esc(diag.get("name") or "")}</td>'
            f'<td>{_esc(diag.get("tier") or "")}</td>'
            f'<td class="{cls}">{_esc(status)}</td>'
            f'<td>{_esc(diag.get("count") or 0)}</td>'
            f'<td>{_esc(util.truncate(diag.get("error") or "", 90))}</td></tr>')
    out.append("</table>")
    return out


def to_html(report: dict) -> str:
    """Report dict (``briefer.build`` ya structured) → valid HTML document."""
    structured = _structured(report)
    items = _items(report, structured)
    verified = sum(1 for i in items if i.get("verified"))
    unverified = len(items) - verified
    conf = structured.get("confidence") if isinstance(structured.get("confidence"), dict) else {}
    query = str(structured.get("query") or report.get("query") or "")
    terms = highlight.terms(query)
    title = str(report.get("title") or f"JIN Agent Brief - {util.truncate(query, 60)}")
    blocked = structured.get("blocked") or None
    audit = structured.get("audit") or {}
    metrics = structured.get("metrics") or {}
    summaries = structured.get("summaries")
    if not isinstance(summaries, dict):
        summaries = {}

    top_sources = sorted({briefer.display_source(i) for i in items})[:6]
    bluf = (f"Is run mein <strong>{len(items)}</strong> unique stories mile, jin mein "
            f"<strong>{verified}</strong> verified citation ke sath aur "
            f"<strong>{unverified}</strong> abhi verify nahi hue. "
            f"Kaam karne wale sources: {_esc(', '.join(top_sources)) if top_sources else 'koi nahi'}.")
    bluf = highlight.highlight_html(bluf, terms)

    parts = [
        "<!DOCTYPE html>",
        '<html lang="ur">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_esc(title)}</title>",
        f"<style>{_STYLE}</style>",
        "</head>",
        "<body>",
        f"<h1>{highlight.highlight_html(_esc(title), terms)}</h1>",
        '<div class="card meta">',
        f"<div>Query: {highlight.highlight_html(_esc(query), terms)}</div>",
        f"<div>Date checked: {_esc(structured.get('date_checked') or '')}</div>",
        f"<div>Mode: {_esc(structured.get('mode') or 'n/a')} | "
        f"Policy: {_esc(structured.get('policy_id') or policy.POLICY_ID)}</div>",
        f"<div>Tor: {_esc(structured.get('tor_mode') or 'links_only')}</div>",
        f"<div>Confidence: {_esc(conf.get('label') or 'n/a')} "
        f"({_esc(conf.get('value') or 0)}) — "
        f"{_esc(conf.get('cross_verified') or 0)} cross-verified / "
        f"{_esc(conf.get('verified') or verified)} verified / "
        f"{_esc(conf.get('items') or len(items))} items</div>",
        "</div>",
        "<h2>BLUF</h2>",
    ]
    if blocked:
        parts += [
            f'<div class="card"><p>Ye request <strong>Sahulat &amp; Safe Service '
            f'Policy</strong> ke tahat block hai. Koi live search nahi ki gayi.</p>',
            f"<p>Wajah: {_esc((blocked or {}).get('reason') or '')}</p>",
            "<p>Official route: "
            + ", ".join(_link(u) for u in (blocked or {}).get("official_links") or [])
            + "</p>",
            "</div>",
        ]
    else:
        parts.append(f'<div class="card"><p>{bluf}</p>')
        parts.append("<ul>")
        for item in items[:5]:
            t = util.truncate(str(item.get("title") or "").strip(), 100)
            if t:
                parts.append(f"<li>{_esc(t)}</li>")
        if not items:
            parts.append("<li>Koi key finding nahi mili.</li>")
        parts.append("</ul></div>")

    parts.append("<h2>Findings</h2>")
    if items:
        parts.extend(_bucket_sections(items, terms, summaries))
    else:
        parts.append('<div class="card"><p>Is query par koi item nahi mili. '
                     "Offline ya network failure ki soorat mein agent khali natija "
                     "deti hai, koi banawati khabar nahi banata.</p></div>")

    parts.extend(_sources_section(structured.get("diagnostics")))

    parts.append("<h2>Not Verified / Limitations</h2>")
    parts.append("<ul>")
    if unverified:
        parts.append(f"<li><strong>{unverified}</strong> items abhi verified nahi: "
                     "article URL agent ne khud fetch nahi kiya; ye adapter ke "
                     "citation hain.</li>")
    else:
        parts.append("<li>Is run mein koi unresolved item nahi.</li>")
    if audit.get("link_only"):
        parts.append(f"<li><strong>{audit['link_only']}</strong> onion links sirf "
                     f"display ke liye hain; {_esc(policy.DARK_WEB_RULE)}</li>")
    if audit.get("offline_fixtures"):
        parts.append(f"<li><strong>{audit['offline_fixtures']}</strong> offline "
                     "evaluation fixtures hain — ye asli citations nahi.</li>")
    parts.append("</ul>")

    parts.append("<h2>Provenance</h2>")
    parts.append('<div class="card meta"><ul style="margin:0">'
                 f"<li>Items: {_esc(audit.get('total', len(items)))}</li>"
                 f"<li>With URL: {_esc(audit.get('with_url', 0))}</li>"
                 f"<li>With date checked: {_esc(audit.get('with_date', 0))}</li>"
                 f"<li>With source: {_esc(audit.get('with_source', 0))}</li>"
                 f"<li>Provenance: {_esc(audit.get('provenance_pct', 100))}%</li>"
                 f"<li>Fabricated citations: {_esc(audit.get('fabricated', 0))}</li>"
                 "</ul></div>")

    parts.append("<h2>Metrics</h2>")
    try:
        metrics_json = json.dumps(metrics, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        metrics_json = "{}"
    parts.append(f"<pre>{_esc(metrics_json)}</pre>")
    parts += ["</body>", "</html>"]
    return "\n".join(parts)


def from_report_file(md_path: str) -> tuple[str, str]:
    """Saved MD report path se HTML banaye.

    Returns ``(html, error)`` — error khali to kamyabi. JSON archive (wahi stem)
    mujood hona chahiye; na ho to MD fallback ki wajah saaf likhi jati hai.
    """
    import os

    base, _ = os.path.splitext(str(md_path or ""))
    json_path = base + ".json"
    if not os.path.isfile(json_path):
        return "", "json archive nahi mila"
    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            structured = json.load(fh)
    except (OSError, ValueError) as exc:
        return "", f"json parhna fail: {type(exc).__name__}"
    return to_html(structured), ""
