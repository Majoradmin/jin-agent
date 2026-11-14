/* JIN Agent console - vanilla JS, no inline scripts (CSP: script-src 'self'). */
'use strict';

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

async function api(path, opts) {
  const res = await fetch(path, opts);
  let data;
  try { data = await res.json(); } catch (e) { throw new Error('Server response samajh nahi aaya'); }
  if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}
const post = (path, body) => api(path, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body || {})
});

let toastTimer = null;
function toast(msg, bad = false) {
  const box = $('#toast');
  box.textContent = msg;
  box.className = 'toast' + (bad ? ' bad' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => box.classList.add('hidden'), 3600);
}
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = String(text);
  return n;
}
function safeUrl(u) {
  try { const p = new URL(u); return (p.protocol === 'http:' || p.protocol === 'https:') ? p.href : ''; }
  catch (e) { return ''; }
}
function badge(text, kind) { return el('span', 'badge ' + (kind || 'mid'), text); }
function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

function showView(view) {
  $$('.view').forEach(v => v.classList.add('hidden'));
  const target = $('#view-' + view);
  if (target) target.classList.remove('hidden');
  $$('.tab').forEach(t => {
    const active = t.dataset.view === view;
    t.classList.toggle('active', active);
    t.setAttribute('aria-selected', String(active));
  });
  if (LOADERS[view]) LOADERS[view]();
}

/* ---------------- Status ---------------- */
async function loadStatus() {
  try {
    const s = await api('/api/status');
    $('#appVersion').textContent = 'v' + s.version;
    $('#statusLine').textContent =
      'FTS5 ' + (s.fts5 ? 'ON' : 'OFF') + ' · LLM ' + s.llm.mode +
      ' · items ' + (s.counts ? s.counts.items : 0);
    $('#footerStatus').textContent =
      'Policy ' + s.policy_id + ' · Tor ' + s.tor_mode + ' · sources ' + s.source_register;
  } catch (e) {
    $('#statusLine').textContent = 'Offline';
    toast(e.message, true);
  }
}

/* ---------------- Console ---------------- */
function renderMetrics(m) {
  const box = $('#metricStrip'); clear(box);
  if (!m) return;
  const rows = [
    ['Items', m.items], ['Sources OK', m.sources_ok], ['Sources failed', m.sources_failed],
    ['Provenance', (m.provenance_pct || 0) + '%'], ['Fabricated', m.fabricated_citations],
    ['Cross-verified', m.cross_verified], ['Tools', m.tools_used], ['Duration', m.duration_ms + ' ms']
  ];
  rows.forEach(([k, v]) => {
    const n = el('div', 'metric');
    n.appendChild(el('b', '', v));
    n.appendChild(el('span', '', k));
    box.appendChild(n);
  });
}
function renderPlan(plan) {
  const box = $('#planTools'); clear(box);
  if (!plan) return;
  box.appendChild(el('span', 'chip', 'planner: ' + (plan.source || 'n/a')));
  (plan.calls || []).forEach(c => box.appendChild(el('span', 'chip', c.tool)));
  (plan.rejected || []).forEach(() => box.appendChild(el('span', 'chip warn', 'rejected')));
}
function renderResults(items) {
  const box = $('#resultList'); clear(box);
  if (!items || !items.length) {
    box.appendChild(el('p', 'muted', 'Koi item nahi mila. Agent khali natija deta hai, banawati khabar nahi banata.'));
    return;
  }
  items.forEach(it => {
    const n = el('div', 'item');
    n.appendChild(el('h4', '', it.title || '(no title)'));
    const meta = el('div', 'meta');
    meta.appendChild(el('span', '', it.source || ''));
    meta.appendChild(el('span', '', it.category || ''));
    meta.appendChild(badge(it.trust_label || '', it.verified ? 'ok' : 'mid'));
    meta.appendChild(el('span', '', 'conf ' + (it.confidence || 0)));
    meta.appendChild(el('span', '', 'score ' + (it.score || 0)));
    if (it.cross_verified) meta.appendChild(badge('cross-verified', 'ok'));
    if (it.link_only) meta.appendChild(badge('link only', 'no'));
    n.appendChild(meta);
    const href = safeUrl(it.url);
    if (href) {
      const a = el('a', '', href);
      a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer';
      a.style.fontSize = '11px'; a.style.wordBreak = 'break-all';
      n.appendChild(a);
    }
    n.appendChild(el('div', 'desc', (it.excerpt || '').slice(0, 220)));
    box.appendChild(n);
  });
}
let lastMarkdown = '';
async function runResearch() {
  const q = $('#query').value.trim();
  if (!q) { toast('Pehle query likhein', true); return; }
  const btn = $('#runBtn'); btn.disabled = true;
  $('#runState').textContent = 'Running…';
  try {
    const out = await post('/api/run', {
      query: q, live: $('#liveMode').checked, days: 7, limit: 25, save: true
    });
    renderPlan(out.plan);
    renderMetrics(out.metrics);
    renderResults(out.items);
    lastMarkdown = out.report ? out.report.markdown : '';
    $('#reportText').textContent = lastMarkdown || 'Report khali hai.';
    $('#runState').textContent = out.blocked
      ? 'Request policy se block hui. Koi live search nahi hui.'
      : (out.metrics.live ? 'Live' : 'Offline') + ' run mukammal · ' +
        out.metrics.items + ' items · ' + out.metrics.duration_ms + ' ms';
    toast(out.blocked ? 'Blocked by safe-service policy' : 'Research mukammal', out.blocked);
  } catch (e) {
    $('#runState').textContent = '✗ ' + e.message;
    toast(e.message, true);
  } finally { btn.disabled = false; }
}

/* ---------------- Archive ---------------- */
async function loadArchive() {
  const q = $('#archiveQ').value.trim();
  try {
    const out = await api('/api/archive?q=' + encodeURIComponent(q) + '&limit=60');
    const box = $('#archiveList'); clear(box);
    if (!out.items.length) { box.appendChild(el('p', 'muted', 'Archive khali hai ya koi match nahi.')); return; }
    out.items.forEach(it => {
      const n = el('div', 'item');
      n.appendChild(el('h4', '', it.title || ''));
      const meta = el('div', 'meta');
      meta.appendChild(el('span', '', it.source || ''));
      meta.appendChild(el('span', '', it.category || ''));
      meta.appendChild(el('span', '', 'score ' + (it.score || 0)));
      meta.appendChild(badge(it.verified ? 'verified' : 'not verified', it.verified ? 'ok' : 'mid'));
      n.appendChild(meta);
      const href = safeUrl(it.url);
      if (href) { const a = el('a', '', href); a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer'; a.style.fontSize = '11px'; n.appendChild(a); }
      box.appendChild(n);
    });
  } catch (e) { toast(e.message, true); }
}

/* ---------------- Sources ---------------- */
async function loadSources() {
  try {
    const out = await api('/api/sources');
    const body = $('#sourceTable tbody'); clear(body);
    out.sources.forEach(s => {
      const tr = el('tr');
      const name = el('td'); const a = el('a', '', s.name);
      const href = safeUrl(s.url); if (href) { a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer'; }
      name.appendChild(a); tr.appendChild(name);
      [s.tier, s.category, String(s.trust), s.auto ? 'yes' : 'no',
       'OK ' + s.ok_count + ' / FAIL ' + s.fail_count, (s.notes || '').slice(0, 120)]
        .forEach(v => tr.appendChild(el('td', '', v)));
      body.appendChild(tr);
    });
  } catch (e) { toast(e.message, true); }
}

/* ---------------- Watchlist ---------------- */
async function loadWatchlist() {
  try {
    const out = await api('/api/watchlist');
    const box = $('#watchList'); clear(box);
    if (!out.items.length) { box.appendChild(el('p', 'muted', 'Watchlist khali hai.')); return; }
    out.items.forEach(w => {
      const n = el('div', 'item');
      n.appendChild(el('h4', '', w.term));
      const meta = el('div', 'meta');
      meta.appendChild(el('span', '', w.category));
      meta.appendChild(badge(w.active ? 'active' : 'archived', w.active ? 'ok' : 'mid'));
      meta.appendChild(el('span', '', 'last hit: ' + (w.last_hit || 'never')));
      n.appendChild(meta);
      box.appendChild(n);
    });
  } catch (e) { toast(e.message, true); }
}

/* ---------------- Reports ---------------- */
async function loadReports() {
  try {
    const out = await api('/api/reports');
    const box = $('#reportList'); clear(box);
    if (!out.items.length) { box.appendChild(el('p', 'muted', 'Abhi koi report nahi.')); return; }
    out.items.forEach(r => {
      const n = el('div', 'item clickable');
      n.appendChild(el('h4', '', r.title || ('Report #' + r.id)));
      n.appendChild(el('div', 'meta', r.created_at + ' · ' + r.fmt));
      n.onclick = async () => {
        try {
          const res = await fetch('/api/report?id=' + encodeURIComponent(r.id));
          const text = await res.text();
          $('#reportView').textContent = text;
        } catch (e) { toast(e.message, true); }
      };
      box.appendChild(n);
    });
  } catch (e) { toast(e.message, true); }
}

/* ---------------- Evaluation ---------------- */
function renderEval(result) {
  const m = result.metrics;
  const wrap = $('#evalMetrics'); clear(wrap);
  const table = el('table');
  const head = el('thead'); const hr = el('tr');
  ['Metric', 'Value'].forEach(h => hr.appendChild(el('th', '', h)));
  head.appendChild(hr); table.appendChild(head);
  const body = el('tbody');
  Object.keys(m).forEach(k => {
    const tr = el('tr'); tr.appendChild(el('td', '', k)); tr.appendChild(el('td', '', JSON.stringify(m[k]))); body.appendChild(tr);
  });
  table.appendChild(body); wrap.appendChild(table);
  const box = $('#evalSafety'); clear(box);
  Object.keys(result.safety).forEach(k => {
    const n = el('div', 'item');
    n.appendChild(el('h4', '', k.replace(/_/g, ' ')));
    n.appendChild(badge(result.safety[k] ? 'PASS' : 'FAIL', result.safety[k] ? 'ok' : 'no'));
    box.appendChild(n);
  });
  $('#evalState').textContent = (result.passed ? 'PASS' : 'REVIEW') +
    ' · mode ' + result.mode + ' · coverage ' + m.coverage_pct + '% · ' +
    m.fabricated_citations + ' fabricated citations';
}
async function runEval() {
  const btn = $('#evalBtn'); btn.disabled = true;
  $('#evalState').textContent = 'Running 25 queries…';
  try {
    const out = await post('/api/eval/run', { live: $('#evalLive').checked });
    renderEval(out.result);
    toast(out.result.passed ? 'Evaluation PASS' : 'Evaluation REVIEW', !out.result.passed);
  } catch (e) { $('#evalState').textContent = '✗ ' + e.message; toast(e.message, true); }
  finally { btn.disabled = false; }
}

/* ---------------- Settings ---------------- */
function syncLlmProvider() {
  const custom = $('#setProvider').value === 'custom';
  ['#setEndpoint', '#setKey'].forEach(id => {
    $(id).disabled = !custom;
    $(id).title = custom ? '' : 'Sirf custom provider ke liye';
  });
}
async function loadSettings() {
  try {
    const out = await api('/api/settings');
    const s = out.settings;
    $('#setProvider').value = (s.llm && s.llm.provider) || 'off';
    $('#setModel').value = (s.llm && s.llm.model) || '';
    $('#setEndpoint').value = (s.llm && s.llm.endpoint) || '';
    $('#setKey').value = '';
    $('#setKey').placeholder = (s.llm && s.llm.key) ? 'saved (masked)' : 'sirf custom ke liye';
    $('#setChannels').value = (s.telegram_channels || []).join(', ');
    $('#setToken').value = '';
    $('#setToken').placeholder = s.telegram_bot_token ? 'saved (masked)' : 'optional';
    $('#setChat').value = s.telegram_chat_id || '';
    $('#setTor').value = s.tor_mode || 'links_only';
    $('#setRetention').value = s.retention_days || 90;
    syncLlmProvider();
  } catch (e) { toast(e.message, true); }
}
async function saveSettings() {
  const payload = {
    llm: { provider: $('#setProvider').value, model: $('#setModel').value.trim() },
    telegram_channels: $('#setChannels').value.split(',').map(x => x.trim()).filter(Boolean),
    telegram_chat_id: $('#setChat').value.trim(),
    tor_mode: $('#setTor').value,
    retention_days: Number($('#setRetention').value) || 90
  };
  if ($('#setProvider').value === 'custom') {
    payload.llm.endpoint = $('#setEndpoint').value.trim();
    if ($('#setKey').value.trim()) payload.llm.key = $('#setKey').value.trim();
  }
  if ($('#setToken').value.trim()) payload.telegram_bot_token = $('#setToken').value.trim();
  try {
    await post('/api/settings', payload);
    $('#setState').textContent = 'Settings save ho gayiin.';
    toast('Settings saved'); loadStatus();
  } catch (e) { $('#setState').textContent = '✗ ' + e.message; toast(e.message, true); }
}

/* ---------------- Wire up ---------------- */
const LOADERS = {
  archive: loadArchive, sources: loadSources, watchlist: loadWatchlist,
  reports: loadReports, settings: loadSettings
};
$$('.tab').forEach(t => t.onclick = () => showView(t.dataset.view));
$('#runBtn').onclick = runResearch;
$('#query').onkeydown = e => { if (e.key === 'Enter') runResearch(); };
$('#archiveBtn').onclick = loadArchive;
$('#archiveQ').onkeydown = e => { if (e.key === 'Enter') loadArchive(); };
$('#watchAdd').onclick = async () => {
  const term = $('#watchTerm').value.trim();
  if (!term) { toast('Keyword likhein', true); return; }
  try { await post('/api/watchlist', { term: term, category: $('#watchCat').value.trim() || 'Custom Watchlist' }); $('#watchTerm').value = ''; loadWatchlist(); toast('Added'); }
  catch (e) { toast(e.message, true); }
};
$('#reportRefresh').onclick = loadReports;
$('#evalBtn').onclick = runEval;
$('#setProvider').onchange = syncLlmProvider;
$('#setSave').onclick = saveSettings;
$('#llmTestBtn').onclick = async () => {
  $('#llmTestMsg').textContent = 'Testing…';
  try { const r = await post('/api/llm/test', {}); const x = r.result; $('#llmTestMsg').textContent = x.ok ? '✓ ' + x.provider + ' / ' + x.model + ' — ' + x.latency_ms + ' ms' : '✗ ' + x.error; toast(x.ok ? 'Model chal raha hai' : 'Model test fail', !x.ok); }
  catch (e) { $('#llmTestMsg').textContent = '✗ ' + e.message; }
};
$('#setBackup').onclick = async () => { try { const r = await post('/api/backup', {}); $('#setState').textContent = 'Backup: ' + r.result.path; toast('Backup ready'); } catch (e) { toast(e.message, true); } };
$('#setDigest').onclick = async () => { try { const r = await post('/api/digest', {}); $('#setState').textContent = 'Digest: ' + ((r.result.saved || {}).md || 'saved'); toast('Digest ready'); } catch (e) { toast(e.message, true); } };
$('#setAlert').onclick = async () => { try { await post('/api/alert/test', { text: 'JIN Agent test alert' }); $('#setState').textContent = 'Local alert likha gaya.'; toast('Alert sent'); } catch (e) { toast(e.message, true); } };
$('#tickBtn').onclick = async () => { try { const r = await post('/api/scheduler', { action: 'tick', offline: true }); $('#setState').textContent = 'Tick: ' + r.result.enqueued.length + ' enqueued, ' + r.result.processed.length + ' processed.'; toast('Tick done'); } catch (e) { toast(e.message, true); } };
$('#downloadMd').onclick = () => {
  if (!lastMarkdown) { toast('Pehle research chalayein', true); return; }
  const blob = new Blob([lastMarkdown], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'jin-agent-brief.md';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
};

loadStatus();
