/* MobileLab frontend - no external libraries, fully offline-capable UI. */
'use strict';

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const human = (n) => { n = +n || 0; const u=['B','KB','MB','GB','TB']; let i=0; while(n>=1024&&i<4){n/=1024;i++;} return (i?n.toFixed(1):n.toFixed(0))+' '+u[i]; };
/* QA #4: EVERY external href is funnelled through safe_url()/linkHtml().
   http/https only; javascript:, data:, and malformed URLs are rejected. */
const safe_url = (u) => {
  const s = String(u ?? '').trim();
  if (!/^https?:\/\//i.test(s)) return '';
  try { const p = new URL(s); return (p.protocol === 'http:' || p.protocol === 'https:') ? p.href : ''; }
  catch { return ''; }
};
const linkHtml = (u, text, cls = '') => {
  const href = safe_url(u);
  const c = cls ? ` class="${esc(cls)}"` : '';
  if (!href) return `<span${c}>${esc(text)}</span>`;
  return `<a href="${esc(href)}"${c} target="_blank" rel="noopener noreferrer">${esc(text)}</a>`;
};

const TITLES = {
  dashboard: ['Dashboard', 'Your local mobile-software workspace'],
  packages:  ['Firmware Packages', 'Scan, validate and catalog — MTK scatter/preloader/DA and Qualcomm Firehose'],
  research:  ['Research Agent', 'Live browsing, filters and Roman Urdu summaries'],
  memory:    ['Agent Memory', 'Persistent sources, Telegram public channels, queries, problems and feedback'],
  models:    ['Model Brief', 'Local model card and live information for this model'],
  jobs:      ['Job Register', 'IMEI, ownership proof and official route records'],
  sahulat:   ['Sahulat / Official Route', 'Checklist, consent, service-request letter and case register — with reason + official link'],
  knowledge: ['Knowledge / Help', 'Research findings, official routes, glossary and setup'],
  settings:  ['Settings', 'Optional LLM and app preferences'],
};

const state = {
  status: null, sources: [], presets: [], categories: [], knowledge: null,
  packages: [], selected: null, researchLoaded: false, savedMode: false,
  preset: 'all', lastItems: [], sampleDir: '',
  sahulat: null, sahLoaded: false,
  serviceBrief: null, svcLastClass: null,
  memory: null, memoryLoaded: false,
};

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  let j;
  try { j = await r.json(); } catch { throw new Error('Invalid server response'); }
  if (!r.ok || j.error) throw new Error(j.error || ('HTTP ' + r.status));
  return j;
}
const post = (p, b) => api(p, { method: 'POST', body: JSON.stringify(b || {}) });

function toast(msg, bad = false) {
  const t = $('#toast');
  t.textContent = msg; t.className = 'toast show' + (bad ? ' bad' : '');
  clearTimeout(t._t); t._t = setTimeout(() => t.className = 'toast', 3600);
}
function busy(btn, on, label) {
  if (!btn) return;
  btn.disabled = on;
  if (on) { btn._l = btn.textContent; btn.textContent = label || 'Working…'; }
  else btn.textContent = btn._l || btn.textContent;
}

function nav(view, updateHash = true) {
  if (!TITLES[view]) view = 'dashboard';
  if (updateHash && location.hash !== '#' + view) location.hash = view;
  $$('.nav-item').forEach(b => {
    const on = b.dataset.view === view;
    b.classList.toggle('active', on);
    b.setAttribute('aria-selected', on ? 'true' : 'false');
    b.tabIndex = on ? 0 : -1;
    if (on) b.setAttribute('aria-current', 'page');
    else b.removeAttribute('aria-current');
  });
  $$('.view').forEach(v => v.classList.remove('active'));
  const el = $('#view-' + view); if (el) el.classList.add('active');
  const [t, s] = TITLES[view] || TITLES.dashboard;
  $('#viewTitle').textContent = t; $('#viewSub').textContent = s;
  window.scrollTo({ top: 0, behavior: 'smooth' });
  if (view === 'research' && !state.researchLoaded) fetchResearch(false);
  if (view === 'packages' && !state.packages.length) loadPackages();
  if (view === 'jobs') loadJobs();
  if (view === 'sahulat') loadSahulat();
  if (view === 'memory') loadMemory();
}

/* ------------------------------------------------------------------ dashboard */
function renderStats() {
  const c = (state.status && state.status.counts) || {};
  const items = [
    ['Packages', c.packages || 0], ['Scanned files', c.files || 0],
    ['Research items', c.articles || 0], ['Saved', c.saved || 0],
    ['Model cards', c.models || 0], ['Jobs', c.jobs || 0], ['Sahulat cases', c.cases || 0],
  ];
  $('#statGrid').innerHTML = items.map(([l, n]) =>
    `<div class="stat"><div class="n">${n}</div><div class="l">${l}</div></div>`).join('');
  $('#sideMeta').textContent = 'v' + (state.status?.version || '1.0') + ' · Python ' + (state.status?.python || '');
}

function renderFocus() {
  const f = [
    ['Preloader / DA match', 'Scatter platform, preloader chipset aur DA/auth version aik doosre se match karayein.'],
    ['Firehose storage', 'eMMC vs UFS loader, LUN coverage aur sector size — galat loader port par khamosh rehta hai.'],
    ['Missing images', 'Scatter aur rawprogram XML ke har referenced image ki maujoodgi check.'],
    ['Sector overlap', 'Do partitions ka aik hi sector range likhna silent corruption ka sabab hai.'],
    ['Identity guard', 'frp / persistent / modemst / nvram jaise partitions sirf flag, kabhi erase script nahi.'],
    ['Live intel', 'Naye security patch, loader aur firmware releases ka Roman Urdu khulasa real time mein.'],
    ['Local catalog', 'Har package ka fingerprint, health score, notes aur duplicates aap ke PC par.'],
    ['Official routes', 'Account / activation locks ke liye verified official links aur job register.'],
  ];
  $('#focusGrid').innerHTML = f.map(([t, d]) =>
    `<div class="focus-item"><div class="ft">${esc(t)}</div><div class="fd" lang="ur-PK-Latn">${esc(d)}</div></div>`).join('');
}

async function loadDashNews() {
  const box = $('#dashNews'); box.innerHTML = '<div class="skeleton"></div><div class="skeleton" style="margin-top:8px"></div>';
  try {
    const r = await api('/api/research?preset=all&days=30&min_score=2&limit=8&sources=gnews,gsmarena,androidauthority,xda');
    const items = r.items.slice(0, 6);
    box.innerHTML = items.length ? items.map(i =>
      `<div class="mn"><div class="mt">${linkHtml(i.url, i.title)}</div>
       <div class="mk" lang="ur-PK-Latn">${esc(i.khulasa)}</div></div>`).join('')
      : '<p class="muted small" lang="ur-PK-Latn">Abhi koi matching khabar nahi mili. Research Agent mein filters khol kar dobara try karain.</p>';
  } catch (e) { box.innerHTML = `<p class="muted small" lang="ur-PK-Latn">Fetch nahi hua: ${esc(e.message)}</p>`; }
  refreshCounts();
}

/* ------------------------------------------------------------------ packages */
function samplePath() {
  // QA #7: /api/status deliberately hides the absolute install path. The server
  // supplies a RELATIVE sample_dir instead, resolved against the app folder.
  return state.sampleDir || 'samples\\MTK_Demo_MT6899_UFS';
}

async function loadPackages() {
  const box = $('#pkgList');
  try {
    const r = await api('/api/packages');
    state.packages = r.items;
    if (!r.items.length) { box.innerHTML = '<div class="empty-state" lang="ur-PK-Latn">Abhi koi package nahi. Upar folder scan karain.</div>'; return; }
    box.innerHTML = r.items.map(p => {
      const h = p.health, cls = h >= 80 ? 'green' : h >= 55 ? 'amber' : 'red';
      const bg = h >= 80 ? 'var(--green-soft)' : h >= 55 ? 'var(--amber-soft)' : 'var(--red-soft)';
      const col = h >= 80 ? 'var(--green)' : h >= 55 ? 'var(--amber)' : 'var(--red)';
      return `<div class="pkg-item ${state.selected === p.id ? 'active' : ''}" data-id="${p.id}">
        <div class="pn">${esc(p.name)}<span class="health-mini" style="background:${bg};color:${col}">${h}%</span></div>
        <div class="pm">${esc(p.platform || '?')} · ${esc(p.chipset || '?')} · ${esc(p.storage || '?')} · ${p.file_count} files · ${human(p.total_size)}</div>
        <div class="pm">${esc(p.model || '')} ${p.tags ? '· ' + esc(p.tags) : ''}</div></div>`;
    }).join('');
    $$('.pkg-item', box).forEach(el => el.onclick = () => loadPackage(+el.dataset.id));
    if (!state.selected && r.items.length) loadPackage(r.items[0].id);
  } catch (e) { box.innerHTML = `<div class="empty-state" lang="ur-PK-Latn">${esc(e.message)}</div>`; }
}

function renderReport(rep, meta, pid) {
  if (!rep) return '';
  const h = rep.health;
  const color = h >= 80 ? 'var(--green)' : h >= 55 ? 'var(--amber)' : 'var(--red)';
  const issues = (rep.issues || []).map(i =>
    `<div class="issue ${esc(i.level)}"><div class="it">${esc(i.msg)}</div>
     ${i.detail ? `<div class="id">${esc(i.detail)}</div>` : ''}</div>`).join('') ||
    '<p class="muted small" lang="ur-PK-Latn">Koi issue nahi mila — package saaf lag raha hai.</p>';
  const checks = (rep.checks || []).map(c =>
    `<tr><td>${esc(c.name)}</td><td class="${c.ok ? 'good' : 'bad'}">${esc(c.value)}${c.ok ? '' : ' ⚠'}</td></tr>`).join('');
  return `<div class="report-block">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
      <strong>Package health: ${h}%</strong>
      <div><span class="tag red">${rep.counts?.error || 0} error</span>
      <span class="tag amber">${rep.counts?.warn || 0} warning</span>
      <span class="tag">${rep.counts?.info || 0} info</span></div>
    </div>
    <div class="health-bar"><span style="width:${h}%;background:${color}"></span></div>
    <div class="report-grid">
      <div><h3 style="margin-bottom:8px">Issues / findings</h3>${issues}</div>
      <div><h3 style="margin-bottom:8px">Checks</h3><table class="check-table">${checks}</table>
        <div style="margin-top:12px" class="small muted">Platform: ${esc(meta?.platform || '?')} ·
        Chipset: ${esc(meta?.chipset || '?')} · Storage: ${esc(meta?.storage || '?')}</div>
      </div>
    </div></div>`;
}

async function loadPackage(id) {
  state.selected = id;
  $$('.pkg-item').forEach(el => el.classList.toggle('active', +el.dataset.id === id));
  const box = $('#pkgDetail'); box.innerHTML = '<div class="skeleton"></div>';
  try {
    const p = await api('/api/packages/' + id);
    const rep = p.report || {};
    const meta = { platform: p.platform, chipset: p.chipset, storage: p.storage };
    const dup = (p.duplicates || []).length
      ? `<div class="issue info"><div class="it">${p.duplicates.length} duplicate fingerprint match doosre packages mein</div>
         <div class="id">${esc(p.duplicates.slice(0,5).map(d => d.file + ' ↔ ' + d.package_name).join('; '))}</div></div>` : '';
    const files = (p.files || []).map(f => `<tr><td>${esc(f.relpath)}</td>
      <td><span class="kind ${esc(f.kind.startsWith('qcom') ? 'qcom' : '')}">${esc(f.kind)}</span></td>
      <td>${human(f.size)}</td><td class="small muted">${esc((f.fingerprint || '').slice(0,12))}</td></tr>`).join('');
    box.innerHTML = `
      <div class="card-head"><h2>${esc(p.name)}</h2>
        <div><button class="btn ghost sm" id="pdReveal">Open folder</button>
        <button class="btn ghost sm" id="pdDelete" style="color:var(--red)">Delete</button></div></div>
      <div class="kv" style="margin-bottom:14px">
        <div class="k">Path</div><div>${esc(p.path)}</div>
        <div class="k">OEM / Model</div><div>${esc(p.oem || '—')} / ${esc(p.model || '—')}</div>
        <div class="k">Platform / Chipset</div><div>${esc(p.platform || '—')} / ${esc(p.chipset || '—')}</div>
        <div class="k">Storage / Size</div><div>${esc(p.storage || '—')} / ${human(p.total_size)} (${p.file_count} files)</div>
        <div class="k">Tags / Notes</div><div>${esc(p.tags || '—')} ${esc(p.notes || '')}</div>
      </div>
      ${renderReport(rep, meta, id)} ${dup}
      <h3 style="margin:18px 0 4px">Files (${(p.files||[]).length})</h3>
      <div style="max-height:360px;overflow:auto"><table class="file-table">
        <thead><tr><th>File</th><th>Kind</th><th>Size</th><th>Fingerprint</th></tr></thead>
        <tbody>${files || '<tr><td colspan="4">No files</td></tr>'}</tbody></table></div>`;
    $('#pdReveal').onclick = async () => {
      try { await post('/api/reveal', { path: p.path }); }
      catch (e) { toast(e.message, true); }
    };
    $('#pdDelete').onclick = async () => {
      if (!confirm('Remove this package from the catalog? (Files stay on disk)')) return;
      await api('/api/packages/' + id, { method: 'DELETE' });
      state.selected = null; box.innerHTML = '<div class="empty-state" lang="ur-PK-Latn">Package hata diya gaya.</div>';
      loadPackages(); refreshCounts(); toast('Package removed from catalog');
    };
  } catch (e) { box.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`; }
}

async function runScan(pathEl, outEl, extra = {}) {
  const path = pathEl.value.trim().replace(/^"|"$/g, '');
  if (!path) { toast('Enter a folder path first', true); return; }
  outEl.innerHTML = '<div class="skeleton"></div>';
  try {
    const r = await post('/api/scan', { path, ...extra });
    outEl.innerHTML = `<div class="notice soft"><div class="notice-icon" aria-hidden="true">✓</div><div>
      <strong>Scan complete — ${r.file_count} files, health ${r.report.health}%</strong>
      <p lang="ur-PK-Latn">${esc(r.meta.platform || 'Unknown')} / ${esc(r.meta.chipset || '?')} / ${esc(r.meta.storage || '?')}.
      Neeche poori report aur right side mein file list hai.</p></div></div>` + renderReport(r.report, r.meta, r.id);
    await loadPackages(); await loadPackage(r.id); refreshCounts();
    toast('Scan complete — package #' + r.id + ' saved');
    if ($('#view-packages').classList.contains('active') === false) nav('packages');
  } catch (e) { outEl.innerHTML = `<div class="issue error"><div class="it">Scan fail</div><div class="id">${esc(e.message)}</div></div>`; toast(e.message, true); }
}

/* ------------------------------------------------------------------ research */
function renderPresets() {
  $('#presetRow').innerHTML = state.presets.map(p =>
    `<button class="chip ${p.id === state.preset ? 'active' : ''}" data-p="${esc(p.id)}">${esc(p.label)}</button>`).join('');
  $$('#presetRow .chip').forEach(b => b.onclick = () => {
    state.preset = b.dataset.p;
    $$('#presetRow .chip').forEach(x => x.classList.toggle('active', x === b));
    const p = state.presets.find(x => x.id === state.preset);
    if (p && !$('#resQ').value.trim()) { /* query placeholder shows effective preset */ }
  });
}
function renderCategories() {
  $('#resCat').innerHTML = '<option value="all">All categories</option>' +
    state.categories.map(c => `<option value="${esc(c.id)}">${esc(c.label)}</option>`).join('');
  $('#srcCount').textContent = '(' + state.sources.length + ')';
  $('#srcChecks').innerHTML = state.sources.map(s =>
    `<label class="checkline"><input type="checkbox" value="${esc(s.id)}" checked> ${esc(s.name)}</label>`).join('');
}
function selectedSources() {
  return $$('#srcChecks input:checked').map(i => i.value);
}

async function fetchResearch(force) {
  const btn = $('#resFetch'); busy(btn, true, 'Fetching…');
  const params = new URLSearchParams({
    preset: state.preset, q: $('#resQ').value.trim(), category: $('#resCat').value,
    days: $('#resDays').value, min_score: $('#resScore').value,
    exclude: $('#resExclude').value.trim(), limit: $('#resLimit').value,
    refresh: force ? '1' : '0', sources: selectedSources().join(','),
  });
  try {
    const r = await api('/api/research?' + params.toString());
    state.researchLoaded = true; state.savedMode = false;
    state.lastItems = r.items; state.lastResult = r;
    $('#fetchStamp').textContent = r.cached ? 'cached · ' + r.fetched_at : 'live · ' + r.fetched_at;
    $('#resDiag').innerHTML = (r.diagnostics || []).map(d =>
      `<span class="${d.ok ? '' : 'bad'}">${esc(d.source)}: ${d.ok ? d.count + ' items' : esc(d.error)}</span>`).join('');
    renderResearch(r);
  } catch (e) {
    $('#resResults').innerHTML = `<div class="card"><div class="issue error"><div class="it">Fetch fail</div><div class="id">${esc(e.message)}</div></div></div>`;
    toast(e.message, true);
  } finally { busy(btn, false); }
}

function resCard(i) {
  const catColors = { huawei:'', mtk:'green', qcom:'green', apple:'amber', security:'red', tools:'', firmware:'' };
  const href = safe_url(i.url);
  return `<div class="res-card ${i.saved ? 'saved' : ''}" data-g="${esc(i.guid)}" data-src="${esc(i.source || '')}">
    <div class="rc-top">
      <span class="tag ${catColors[i.category] || ''}">${esc(i.category_label)}</span>
      <span class="score">score ${i.score}</span>
      <span class="small muted">${esc(i.published || 'no date')}</span>
    </div>
    <div class="rc-title">${linkHtml(i.url, i.title)}</div>
    <div class="rc-khulasa" lang="ur-PK-Latn">${esc(i.khulasa)}${i.llm ? ' <span class="tag">LLM</span>' : ''}</div>
    ${i.excerpt ? `<div class="rc-excerpt">${esc(i.excerpt)}</div>` : ''}
    ${i.matched ? `<div class="small muted" style="margin-bottom:9px">Match: ${esc(i.matched)}</div>` : ''}
    <div class="rc-foot">
      <span class="src">${esc(i.source)}${i.age_days !== null && i.age_days !== undefined ? ' · ' + i.age_days + ' days ago' : ''}</span>
      <button class="btn ghost sm" data-act="save">${i.saved ? '✓ Saved' : 'Save'}</button>
      <button class="btn ghost sm" data-act="read">${i.is_read ? 'Read ✓' : 'Mark read'}</button>
      <button class="btn ghost sm" data-act="useful" title="Memory: is source ki usefulness barhao">Useful</button>
      <button class="btn ghost sm" data-act="bad" title="Memory: is source ki usefulness kam karo">Not useful</button>
      ${href ? linkHtml(i.url, 'Open ↗', 'btn ghost sm') : ''}
    </div>
  </div>`;
}

function renderResearch(r) {
  const items = r.items || [];
  const head = `<div class="card"><div class="res-toolbar">
      <div><strong>${items.length} results</strong> <span class="muted small">/ ${r.total ?? '—'} raw items · query: "${esc(r.query || '')}"</span></div>
      <span class="muted small">${r.cached ? 'cached' : 'live fetch'} · ${esc(r.fetched_at || '')}</span></div>
      <div class="muted small" lang="ur-PK-Latn">Filters: category=${esc(r.category || 'all')} · relevance score ke hisaab se sorted. Roman Urdu khulasa rule-based hai; asal headline English mein hai (technical accuracy ke liye).</div></div>`;
  const cards = items.length
    ? `<div class="res-results">${items.map(resCard).join('')}</div>`
    : '<div class="card"><div class="empty-state" lang="ur-PK-Latn">Is filter par koi result nahi. Min score kam karain, days barhayein ya query badlein.</div></div>';
  $('#resResults').innerHTML = head + cards;
}

async function showSaved() {
  state.savedMode = true;
  try {
    const r = await api('/api/articles?mode=saved');
    $('#resResults').innerHTML = `<div class="card"><div class="res-toolbar"><div><strong>${r.items.length} saved items</strong></div>
      <button class="btn ghost sm" id="backLive">Back to live results</button></div></div>` +
      (r.items.length ? `<div class="res-results">${r.items.map(i => resCard({
        guid:i.guid,title:i.title,url:i.url,source:i.source,published:i.published,
        category:i.category,category_label:(state.categories.find(c=>c.id===i.category)||{}).label || i.category,
        score:i.score,matched:i.matched,excerpt:i.excerpt,khulasa:i.khulasa,saved:1,is_read:i.is_read,
        age_days:null,
      })).join('')}</div>` : '<div class="card"><div class="empty-state" lang="ur-PK-Latn">Abhi kuch save nahi kiya. Research cards par "Save" dabayein.</div></div>');
    $('#backLive').onclick = () => { state.savedMode = false; renderResearch({ ...state.lastResult, items: state.lastItems }); };
  } catch (e) { toast(e.message, true); }
}

/* ------------------------------------------------------------------ memory */
function memDate(ts) {
  if (!ts) return '—';
  const d = new Date(ts * 1000);
  return isNaN(d.getTime()) ? '—' : d.toLocaleString();
}
function memItem(html) { return `<div class="mem-item">${html}</div>`; }

async function loadMemory(force) {
  if (state.memoryLoaded && !force) return;
  try {
    const o = await api('/api/memory/overview');
    state.memory = o; state.memoryLoaded = true;
    renderMemory(o);
  } catch (e) {
    ['#memSourceList', '#memTgList', '#memQueries', '#memProbList', '#memFeedback'].forEach(sel => {
      const el = $(sel); if (el) el.innerHTML = `<div class="issue error"><div class="it">${esc(e.message)}</div></div>`;
    });
  }
}

function renderMemory(o) {
  const c = o.counts || {};
  $('#memStats').innerHTML = [
    ['Active sources', c.sources || 0], ['Archived', c.archived_sources || 0],
    ['Telegram groups', c.telegram || 0], ['Queries', c.queries || 0],
    ['Problems', c.problems || 0], ['Reports', c.reports || 0],
    ['Feedback', c.feedback || 0], ['Entities', c.entities || 0],
  ].map(([l, n]) => `<div class="stat"><div class="n">${n}</div><div class="l">${esc(l)}</div></div>`).join('');
  $('#memSrcCount').textContent = (o.sources || []).length + ' active';
  $('#memTgCount').textContent = (o.telegram || []).length + ' saved';
  $('#memFbCount').textContent = (o.feedback || []).length;

  $('#memSourceList').innerHTML = (o.sources || []).map(s => memItem(
    `<div class="mem-top"><strong>${esc(s.name)}</strong>
       <span class="tag ${s.status === 'active' ? 'green' : 'amber'}">${esc(s.status)}</span>
       <span class="tag">u${s.usefulness} · p${s.priority}</span></div>
     <div class="small muted">${esc(s.type)} · ${esc(s.category)} · trust ${s.trust} · ok ${s.ok_count} / fail ${s.fail_count}${s.last_ok ? ' · last ' + memDate(s.last_ok) : ''}</div>
     ${s.url ? `<div class="small">${linkHtml(s.url, s.url)}</div>` : ''}
     ${s.notes ? `<div class="small muted">${esc(s.notes)}</div>` : ''}
     <div class="row-actions">
       <button class="btn ghost sm" data-promote="${s.id}">+ Priority</button>
       <button class="btn ghost sm" data-demote="${s.id}">− Priority</button>
       <button class="btn ghost sm" data-archive="${s.id}" style="color:var(--red)">Archive</button>
     </div>`)).join('') || '<p class="muted small" lang="ur-PK-Latn">Koi source nahi.</p>';

  $('#memTgList').innerHTML = (o.telegram || []).map(t => memItem(
    `<div class="mem-top"><strong>@${esc(t.channel)}</strong>
       <span class="tag ${t.enabled ? 'green' : 'amber'}">${t.enabled ? 'active' : 'archived'}</span>
       <span class="tag">${esc(t.category)}</span></div>
     <div class="small muted">${esc(t.title)} · ok ${t.ok_count} / fail ${t.fail_count}${t.last_ok ? ' · last ' + memDate(t.last_ok) : ''}</div>
     ${t.last_error ? `<div class="small" style="color:var(--red)">${esc(t.last_error)}</div>` : ''}
     <div class="row-actions">
       <button class="btn ghost sm" data-tgsearch="${esc(t.channel)}">Search</button>
       <button class="btn ghost sm" data-tgarchive="${t.id}" style="color:var(--red)">Archive</button>
     </div>`)).join('') || '<p class="muted small" lang="ur-PK-Latn">Abhi koi channel save nahi. Apne GSM / OSINT / AI groups add karain.</p>';

  $('#memQueries').innerHTML = (o.queries || []).map(q => memItem(
    `<div class="mem-top"><strong>${esc(q.query)}</strong><span class="tag">${esc(q.category)}</span></div>
     <div class="small muted">${q.returned}/${q.result_count} items · sources ok ${q.sources_ok} / fail ${q.sources_failed} · ${q.hits} run(s) · ${memDate(q.updated_at)}</div>
     <div class="row-actions"><button class="btn ghost sm" data-recall="${esc(q.query)}">Recall &amp; research</button></div>`)).join('')
    || '<p class="muted small" lang="ur-PK-Latn">Research karne par query yahan khud save hogi.</p>';

  $('#memProbList').innerHTML = (o.problems || []).map(p => memItem(
    `<div class="mem-top"><strong>P-${p.id} ${esc(p.title)}</strong><span class="tag ${p.status === 'resolved' ? 'green' : 'amber'}">${esc(p.status)}</span></div>
     <div class="small muted">${esc(p.model || 'model —')} · ${memDate(p.updated_at)}</div>
     ${p.symptoms ? `<div class="small">${esc(p.symptoms)}</div>` : ''}`)).join('')
    || '<p class="muted small" lang="ur-PK-Latn">Masla save karne par next time instant recall hoga.</p>';

  $('#memFeedback').innerHTML = (o.feedback || []).map(f => memItem(
    `<div class="mem-top"><strong>${esc(f.rating)}</strong><span class="tag">${esc(f.target_type)}</span></div>
     <div class="small muted">${esc(f.source || '—')} · ${memDate(f.created_at)}</div>
     ${f.target_key ? `<div class="small">${esc(f.target_key)}</div>` : ''}`)).join('')
    || '<p class="muted small" lang="ur-PK-Latn">Research cards par “Useful / Not useful” dabayein — agent isi se seekhta hai.</p>';
}

function renderRecall(r) {
  const out = $('#memRecallOut');
  const qs = (r.queries || []).map(q =>
    `<div class="mem-item"><div class="mem-top"><strong>${esc(q.query)}</strong><span class="tag">${esc(q.category)}</span></div>
      <div class="small muted">${q.hits} run(s) · last ${memDate(q.updated_at)}</div></div>`).join('');
  const ps = (r.problems || []).map(p =>
    `<div class="mem-item"><div class="mem-top"><strong>P-${p.id} ${esc(p.title)}</strong><span class="tag">${esc(p.status)}</span></div>
      <div class="small muted">${esc(p.model || '')} · last ${memDate(p.updated_at)}</div></div>`).join('');
  const ss = (r.sources || []).slice(0, 6).map(s =>
    `<div class="small">${linkHtml(s.url, s.name)} <span class="muted">· p${s.priority} · u${s.usefulness}</span></div>`).join('');
  out.innerHTML = `<div class="issue ${r.known ? 'info' : 'warn'}">
      <div class="it">${r.known ? 'Memory recall — pehle ka record mila' : 'Memory mein pehla record nahi mila'}</div>
      <div class="id">${esc(r.message || 'Naya topic — research ke baad ye khud save ho jayega.')}</div></div>
    ${qs ? `<h3 class="sah-h3">Past queries</h3>${qs}` : ''}
    ${ps ? `<h3 class="sah-h3">Known problems</h3>${ps}` : ''}
    ${ss ? `<h3 class="sah-h3">Priority sources</h3>${ss}` : ''}`;
}

async function memAddSource() {
  const name = $('#memSourceName').value.trim();
  const url = $('#memSourceUrl').value.trim();
  if (!name) { toast('Source ka naam likhein', true); return; }
  try {
    await post('/api/memory/sources', {
      name, url, type: $('#memSourceType').value,
      category: $('#memSourceCat').value.trim() || 'general',
      usefulness: +$('#memSourceUse').value,
    });
    ['#memSourceName', '#memSourceUrl', '#memSourceCat'].forEach(s => $(s).value = '');
    toast('Source memory mein save ho gaya');
    await loadMemory(true); refreshCounts();
  } catch (e) { toast(e.message, true); }
}

async function memAddTelegram() {
  const channel = $('#memTgChannel').value.trim();
  if (!channel) { toast('Channel username likhein', true); return; }
  try {
    await post('/api/memory/telegram', {
      channel, category: $('#memTgCat').value.trim() || 'gsm',
      title: channel,
    });
    $('#memTgChannel').value = ''; $('#memTgCat').value = '';
    toast('Telegram channel memory mein save ho gaya');
    await loadMemory(true); refreshCounts();
  } catch (e) { toast(e.message, true); }
}

async function memSearchTelegram(channel, q) {
  const ch = (channel || $('#memTgSearchChannel').value || '').trim();
  if (!ch) { toast('Channel username likhein', true); return; }
  const query = q !== undefined ? q : $('#memTgSearchQ').value.trim();
  const out = $('#memTgResults');
  out.innerHTML = '<div class="skeleton"></div>';
  try {
    const r = await api('/api/memory/telegram/search?channel=' + encodeURIComponent(ch) +
      '&q=' + encodeURIComponent(query) + '&limit=' + ($('#memTgSearchLimit').value || '20'));
    if (!r.ok) {
      out.innerHTML = `<div class="issue error"><div class="it">Telegram preview fetch nahi hua</div><div class="id">${esc(r.error || '')}</div></div>`;
    } else {
      out.innerHTML = `<div class="small muted">@${esc(r.channel)} · ${r.count} public messages · ${esc(r.fetched_at)} · ${linkHtml(r.url, 'open preview ↗')}</div>` +
        (r.items.length ? r.items.map(m => `<div class="mem-item">
          <div class="small muted">${esc(m.published || 'no date')}${m.views ? ' · ' + esc(m.views) + ' views' : ''}</div>
          <div class="mem-text">${esc(m.text)}</div>
          ${m.url ? `<div class="small">${linkHtml(m.url, 'message link ↗')}</div>` : ''}</div>`).join('')
          : '<p class="muted small" lang="ur-PK-Latn">Is query par koi public message nahi mila.</p>');
    }
    state.memoryLoaded = false; refreshCounts();
  } catch (e) {
    out.innerHTML = `<div class="issue error"><div class="it">${esc(e.message)}</div></div>`;
  }
}

async function memRecall() {
  const q = $('#memRecallQ').value.trim();
  try {
    const r = await api('/api/memory/recall?q=' + encodeURIComponent(q));
    renderRecall(r);
  } catch (e) { $('#memRecallOut').innerHTML = `<div class="issue error"><div class="it">${esc(e.message)}</div></div>`; }
}

async function memAddProblem() {
  const title = $('#memProbTitle').value.trim();
  if (!title) { toast('Problem likhein', true); return; }
  try {
    await post('/api/memory/problems', { title, model: $('#memProbModel').value.trim() });
    $('#memProbTitle').value = ''; $('#memProbModel').value = '';
    toast('Problem memory mein save ho gayi');
    await loadMemory(true); refreshCounts();
  } catch (e) { toast(e.message, true); }
}

async function memExport() {
  try {
    const r = await post('/api/memory/export', {});
    $('#memExportMsg').textContent = '✓ ' + r.file + ' regenerate ho gayi (' + r.bytes + ' bytes) · ' + r.generated_at;
    toast('agent_memory.md update ho gayi');
  } catch (e) { $('#memExportMsg').textContent = '✕ ' + e.message; toast(e.message, true); }
}

/* ------------------------------------------------------------------ models */
async function searchModel() {
  const q = $('#modelQ').value.trim();
  if (!q) { toast('Enter a model number', true); return; }
  const out = $('#modelOut'); out.innerHTML = '<div class="card"><div class="skeleton"></div></div>';
  const live = $('#modelLive').checked ? '1' : '0';
  try {
    const r = await api('/api/model-brief?q=' + encodeURIComponent(q) + '&live=' + live);
    const c = r.card || {};
    const pkgs = r.packages.length ? r.packages.map(p =>
      `<div class="issue info"><div class="it">${esc(p.name)} — health ${p.health}%</div>
       <div class="id">${esc(p.platform||'?')} / ${esc(p.chipset||'?')} / ${esc(p.storage||'?')}</div></div>`).join('')
      : '<p class="muted small" lang="ur-PK-Latn">Is model ka koi scanned package nahi.</p>';
    const news = (r.live && r.live.items || []).map(i =>
      `<div class="mn"><div class="mt">${linkHtml(i.url, i.title)}</div>
       <div class="mk" lang="ur-PK-Latn">${esc(i.khulasa)}</div></div>`).join('') || '<p class="muted small" lang="ur-PK-Latn">Koi live khabar nahi mili.</p>';
    out.innerHTML = `
      <div class="two-col">
        <div class="card"><div class="card-head"><h2>Model card — ${esc(q)}</h2><span class="tag">editable</span></div>
          <div class="form-grid">
            <label>OEM <input id="mcOem" value="${esc(c.oem||'')}"></label>
            <label>Chipset <input id="mcChip" value="${esc(c.chipset||'')}"></label>
            <label>Platform <select id="mcPlat">
              ${['','MediaTek','Qualcomm','HiSilicon Kirin','Samsung Exynos','UNISOC','Apple Silicon','Other']
                .map(x=>`<option ${x===c.platform?'selected':''}>${esc(x||'(select)')}</option>`).join('')}</select></label>
            <label>Storage <select id="mcStore">
              ${['','UFS','eMMC','NAND','SPI-NOR','unknown'].map(x=>`<option ${x===c.storage?'selected':''}>${esc(x||'(select)')}</option>`).join('')}</select></label>
            <label class="wide">Official firmware / support link <input id="mcUrl" value="${esc(c.official_url||'')}"></label>
            <label class="wide">Notes <textarea id="mcNotes" rows="4" placeholder="scatter version, DA/auth, loader, region, build…">${esc(c.notes||'')}</textarea></label>
          </div>
          <button class="btn primary" id="mcSave">Save model card</button>
          <span class="muted small" style="margin-left:10px" lang="ur-PK-Latn">Ye aap ka apna local knowledge base hai — jitna bharein utna behtar brief banega.</span>
        </div>
        <div class="card"><div class="card-head"><h2>Live information</h2><span class="tag green">${esc(r.live?.fetched_at || 'offline')}</span></div>
          <div class="mini-news">${news}</div>
          <h3 style="margin:16px 0 8px">Related scanned packages</h3>${pkgs}
        </div>
      </div>
      <div class="card"><div class="card-head"><h2>Official routes for account / activation issues</h2></div>
        ${officialRoutesHtml(r.official)}</div>`;
    $('#mcSave').onclick = async () => {
      try {
        await post('/api/models', { model:q, oem:$('#mcOem').value, chipset:$('#mcChip').value,
          platform:$('#mcPlat').value === '(select)' ? '' : $('#mcPlat').value,
          storage:$('#mcStore').value === '(select)' ? '' : $('#mcStore').value,
          official_url:$('#mcUrl').value, notes:$('#mcNotes').value });
        toast('Model card saved'); refreshCounts();
      } catch (e) { toast(e.message, true); }
    };
  } catch (e) { out.innerHTML = `<div class="card"><div class="issue error"><div class="it">${esc(e.message)}</div></div></div>`; }
}

function officialRoutesHtml(routes) {
  return (routes || []).map(r => `<div class="route"><div class="rt">${esc(r.issue)}</div>
    <ol>${(r.steps||[]).map(s => `<li>${esc(s)}</li>`).join('')}</ol>
    <div class="rl">${(r.links||[]).map(([t,u]) => linkHtml(u, t + ' ↗')).join('')}</div>
    <div class="rn">${esc(r.note||'')}</div></div>`).join('');
}

/* ------------------------------------------------------------------ jobs */
function renderJobRoutes() {
  const routes = (state.knowledge && state.knowledge.official_routes) || [];
  $('#jobRoute').innerHTML = '<option value="">(select)</option>' +
    routes.map(r => `<option value="${esc(r.issue)}">${esc(r.issue)}</option>`).join('') +
    '<option value="Firmware repair / system restore">Firmware repair / system restore</option>';
  $('#jobRoutes').innerHTML = officialRoutesHtml(routes);
}
async function loadJobs() {
  const box = $('#jobList');
  try {
    const r = await api('/api/jobs');
    box.innerHTML = r.items.length ? `<table class="job-table"><thead><tr>
      <th>Date</th><th>IMEI</th><th>Model</th><th>Customer</th><th>Proof</th><th>Route</th><th>Notes</th></tr></thead><tbody>
      ${r.items.map(j => `<tr><td>${esc(new Date(j.created_at*1000).toLocaleString())}</td>
        <td>${esc(j.imei||'—')}</td><td>${esc(j.model||'—')}</td><td>${esc(j.customer||'—')}</td>
        <td>${j.proof_ok?'<span class="tag green">verified</span>':'<span class="tag amber">pending</span>'}</td>
        <td>${esc(j.route||'—')}</td><td>${esc(j.notes||'')}</td></tr>`).join('')}</tbody></table>`
      : '<div class="empty-state" lang="ur-PK-Latn">Register khaali hai. Upar pehla job add karain.</div>';
  } catch (e) { box.innerHTML = `<div class="issue error"><div class="it">${esc(e.message)}</div></div>`; }
}

/* ------------------------------------------------------------------ sahulat */
async function loadSahulat() {
  if (!state.sahLoaded) {
    try {
      state.sahulat = await api('/api/sahulat/overview');
      state.sahLoaded = true;
      renderSahulat();
    } catch (e) {
      $('#sahRoutes').innerHTML = `<div class="issue error"><div class="it">Sahulat data failed to load</div><div class="id">${esc(e.message)}</div></div>`;
      return;
    }
  }
  loadSahCases();
}

function renderSahulat() {
  const o = state.sahulat; if (!o) return;
  $('#sahPolicyTitle').textContent = o.policy.name;
  $('#sahPolicyLead').textContent = o.policy.lead;
  $('#sahRouteCount').textContent = o.routes.length + ' routes';
  $('#sahConsent').textContent = o.consent_text;
  $('#sahBrand').innerHTML = o.routes.map(r =>
    `<option value="${esc(r.id)}">${esc(r.brand)}</option>`).join('');
  $('#sahChecklist').innerHTML = o.checklist.map(c =>
    `<label class="sah-check"><input type="checkbox" value="${esc(c.id)}">
      <span><b>${esc(c.label)}</b>${c.required ? ' <span class="tag amber">required</span>' : ''}
      <em>${esc(c.hint)}</em></span></label>`).join('');
  $('#sahRoutes').innerHTML = o.routes.map((r, idx) =>
    `<details class="sah-route" ${idx === 0 ? 'open' : ''}>
      <summary><strong>${esc(r.brand)}</strong> — ${esc(r.issue)}</summary>
      <div class="sr-body">
        <div class="sr-docs"><b>Required documents:</b><ul>${r.documents.map(d => `<li>${esc(d)}</li>`).join('')}</ul></div>
        <ol class="sr-steps">${r.steps.map(s => `<li>${esc(s)}</li>`).join('')}</ol>
        <div class="rl">${r.links.length
          ? r.links.map(([t, u]) => linkHtml(u, t + ' ↗')).join('')
          : '<span class="muted small">Apne department / operator ka official channel istemal karain.</span>'}</div>
        <div class="rn">${esc(r.note)}</div>
        <button class="btn ghost sm" data-pick="${esc(r.id)}">Use this route in the form</button>
      </div>
    </details>`).join('');
  $$('#sahRoutes [data-pick]').forEach(b => b.onclick = () => {
    $('#sahBrand').value = b.dataset.pick;
    const r = o.routes.find(x => x.id === b.dataset.pick);
    if (r && !$('#sahIssue').value.trim()) $('#sahIssue').value = r.issue;
    toast('Route selected in the form');
  });
  $('#sahBoundary').innerHTML = `
    <div class="notice" style="margin-bottom:12px"><div class="notice-icon" aria-hidden="true">i</div>
      <div><strong>${esc(o.policy.canonical)}</strong></div></div>
    <h3 class="sah-h3"><span aria-hidden="true">✓</span> What we help with</h3>
    <ul class="do-list">${o.policy.helps.map(x => `<li>${esc(x)}</li>`).join('')}</ul>
    <h3 class="sah-h3"><span aria-hidden="true">✕</span> Service boundary (in force)</h3>
    <ul class="do-list no">${o.policy.boundary.map(x => `<li>${esc(x)}</li>`).join('')}</ul>
    <p class="small muted" style="margin-top:10px">${esc(o.policy.why)}</p>`;
}

function sahFormData() {
  const o = state.sahulat || { routes: [] };
  const rid = $('#sahBrand').value;
  const route = o.routes.find(r => r.id === rid) || {};
  return {
    customer: $('#sahCustomer').value, contact: $('#sahContact').value,
    brand: route.brand || '', model: $('#sahModel').value,
    device_id: $('#sahDevice').value, issue_type: $('#sahIssue').value,
    notes: $('#sahNotes').value, route_id: rid, lang: $('#sahLang').value,
    technician: ($('#setTech') && $('#setTech').value) || '',
    shop: ($('#setShop') && $('#setShop').value) || '',
    consent: $('#sahConsentChk').checked,
    proof: $$('#sahChecklist input:checked').map(i => i.value),
  };
}
function sahMsg(msg, bad = false) {
  const el = $('#sahFormMsg');
  el.textContent = msg; el.style.color = bad ? 'var(--red)' : 'var(--muted)';
}
function copyText(txt, okMsg) {
  if (!txt) { toast('Prepare the text first', true); return; }
  const fallback = () => {
    const ta = document.createElement('textarea');
    ta.value = txt; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); toast(okMsg); }
    catch { toast('Copy failed — select the text manually', true); }
    ta.remove();
  };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(txt).then(() => toast(okMsg)).catch(fallback);
  } else fallback();
}

async function sahCheck() {
  const q = $('#sahCheckQ').value.trim();
  const out = $('#sahCheckOut');
  if (!q) { out.innerHTML = '<p class="muted small">Pehle customer ki request likhein.</p>'; return; }
  out.innerHTML = '<div class="skeleton"></div>';
  try {
    const r = await api('/api/sahulat/check?q=' + encodeURIComponent(q));
    const links = r.official_links.length
      ? `<div class="rl">${r.official_links.map(([t, u]) => linkHtml(u, t + ' ↗')).join('')}</div>` : '';
    const docs = r.documents.length
      ? `<div class="sr-docs"><b>Required documents:</b><ul>${r.documents.map(d => `<li>${esc(d)}</li>`).join('')}</ul></div>` : '';
    out.innerHTML = `
      <div class="issue ${r.blocked ? 'warn' : 'info'}">
        <div class="it">${r.blocked ? 'Boundary request — official route provided' : 'This task is handled in-app'}</div>
        <div class="id">${esc(r.reason)}</div></div>
      ${r.blocked ? `<div class="small muted"><b>Official route:</b> ${esc(r.official_route)}</div>${links}${docs}` : ''}
      <ol class="sr-steps">${r.safe_next_steps.map(s => `<li>${esc(s)}</li>`).join('')}</ol>
      ${r.refusal_line ? `<div class="notice" style="margin-top:10px"><div class="notice-icon" aria-hidden="true">i</div><div><p>${esc(r.refusal_line)}</p></div></div>` : ''}
      <div class="small muted">Policy: ${esc(r.policy)}</div>`;
  } catch (e) { out.innerHTML = `<div class="issue error"><div class="it">Check fail</div><div class="id">${esc(e.message)}</div></div>`; }
}

async function sahLetter() {
  const btn = $('#sahLetterBtn'); busy(btn, true, 'Generating letter…');
  try {
    const r = await post('/api/sahulat/letter', sahFormData());
    $('#sahLetter').textContent = r.letter;
    $('#sahLetter').setAttribute('lang', $('#sahLang').value === 'english' ? 'en' : 'ur-PK-Latn');
    sahMsg('✓ Letter preview ready. Case not saved yet — use the button below.');
  } catch (e) { sahMsg(e.message, true); toast(e.message, true); }
  finally { busy(btn, false); }
}

async function sahSaveCase() {
  const btn = $('#sahCaseBtn'); busy(btn, true, 'Saving case…');
  try {
    const r = await post('/api/sahulat/case', sahFormData());
    if (r.letter) {
      $('#sahLetter').textContent = r.letter;
      $('#sahLetter').setAttribute('lang', $('#sahLang').value === 'english' ? 'en' : 'ur-PK-Latn');
    }
    sahMsg(r.letter_error
      ? '✓ Case saved (' + r.case.status + '). For letter: ' + r.letter_error
      : '✓ Case ' + r.case.case_no + ' saved and letter ready.', false);
    toast('Case ' + r.case.case_no + ' saved');
    loadSahCases(); refreshCounts();
  } catch (e) { sahMsg(e.message, true); toast(e.message, true); }
  finally { busy(btn, false); }
}

async function loadSahCases() {
  const box = $('#sahCases'); if (!box) return;
  try {
    const r = await api('/api/sahulat/cases');
    box.innerHTML = r.items.length ? `<table class="job-table"><thead><tr>
      <th>Date</th><th>Case no</th><th>Customer</th><th>Device</th><th>Route</th><th>Proof</th><th>Status</th></tr></thead><tbody>
      ${r.items.map(c => `<tr><td>${esc(new Date(c.created_at * 1000).toLocaleString())}</td>
        <td>${esc(c.case_no)}</td><td>${esc(c.customer)}</td>
        <td>${esc(c.model || c.brand || '—')}</td><td>${esc(c.route_id || '—')}</td>
        <td>${c.proof_ok ? '<span class="tag green">complete</span>' : '<span class="tag amber">pending</span>'}</td>
        <td>${esc(c.status)}</td></tr>`).join('')}</tbody></table>`
      : '<div class="empty-state" lang="ur-PK-Latn">Case register khaali hai. Upar form bhar kar pehla case save karain.</div>';
  } catch (e) { box.innerHTML = `<div class="issue error"><div class="it">${esc(e.message)}</div></div>`; }
}

/* -------------------------------------------------- service brief (P12) */
function renderSvcChecks() {
  const o = state.serviceBrief; if (!o) return;
  const list = (o.checks && (o.checks[$('#svcBrand').value] || o.checks.other)) || [];
  $('#svcChecks').innerHTML = list.map(c =>
    `<label class="sah-check"><input type="checkbox" value="${esc(c.id)}" checked>
      <span><b>${esc(c.label)}</b><em>${esc(c.where)}</em></span></label>`).join('') ||
    '<p class="muted small" lang="ur-PK-Latn">Is brand ke liye koi check maujood nahi.</p>';
}

function renderServiceBrief() {
  const o = state.serviceBrief; if (!o) return;
  $('#svcVersion').textContent = 'v' + o.version + ' · worksheet only';
  $('#svcDisclaimer').textContent = (o.disclaimer || '') + ' ' + (o.privacy_note || '');
  $('#svcSources').innerHTML =
    '<h3 class="sah-h3">Verified sources (URL + date checked)</h3>' +
    (o.sources || []).map(s =>
      `<div class="svc-src">${linkHtml(s.url, s.label + ' ↗')}
        <span class="small muted">[${esc(s.id)}] · checked ${esc(s.date_checked)} · ${esc(s.purpose)}</span></div>`).join('') +
    ((o.excluded_sources || []).length
      ? `<p class="small muted" lang="ur-PK-Latn">Excluded (checked but unavailable): ${o.excluded_sources.map(x => esc(x.url) + ' — ' + esc(x.reason)).join('; ')}</p>` : '');
  renderSvcChecks();
  $('#svcProof').innerHTML = (o.checklist || []).map(c =>
    `<label class="sah-check"><input type="checkbox" value="${esc(c.id)}">
      <span><b>${esc(c.label)}</b>${c.required ? ' <span class="tag amber">required</span>' : ''}
      <em>${esc(c.hint)}</em></span></label>`).join('');
}

function svcFormData() {
  const q = $('#svcAsk').value.trim();
  return {
    q, issue: q,
    customer: $('#svcCustomer').value.trim(), contact: $('#svcContact').value.trim(),
    model: $('#svcModel').value.trim(), brand: $('#svcBrand').value,
    device_id: $('#svcId').value.trim(),
    consent: $('#svcConsentChk').checked, live: $('#svcLive').checked,
    proof: $$('#svcProof input:checked').map(i => i.value),
    checks: $$('#svcChecks input:checked').map(i => i.value),
  };
}

function svcMsg(msg, bad = false) {
  const el = $('#svcMsg');
  el.textContent = msg; el.style.color = bad ? 'var(--red)' : 'var(--muted)';
}

function svcRefusalHtml(r) {
  return `<div class="issue warn"><div class="it">Boundary request — official route only</div>
      <div class="id">${esc(r.reason || '')}</div></div>
    <div class="rl">${(r.official_links || []).map(([t, u]) => linkHtml(u, t + ' ↗')).join('')}</div>
    <ol class="sr-steps">${(r.safe_next_steps || []).map(s => `<li>${esc(s)}</li>`).join('')}</ol>
    ${r.refusal_line ? `<p class="small muted" lang="ur-PK-Latn">${esc(r.refusal_line)}</p>` : ''}`;
}

function svcShowResult(r) {
  const text = r.report || r.worksheet || r.brief || '';
  $('#svcOutput').textContent = text || '(koi text nahi)';
  const facts = r.facts || [], recs = r.recommendations || [];
  let h = '';
  if (r.blocked) {
    h += svcRefusalHtml(r);
  } else if (facts.length || recs.length || r.offline) {
    h += `<div class="two-col" style="margin-top:14px">
      <div class="card"><div class="card-head"><h2>Facts — verified feeds</h2><span class="tag green">${facts.length}</span></div>
        ${facts.length ? facts.map(f => `<div class="mn"><div class="mt">${linkHtml(f.url, f.title)}</div>
          <div class="mk" lang="ur-PK-Latn">${esc(f.khulasa)}</div>
          <div class="small muted">${esc(f.source)} · checked ${esc(f.date_checked)}</div></div>`).join('')
          : '<p class="muted small" lang="ur-PK-Latn">Koi feed item nahi mila — koi banawati khabar nahi likhi gayi.</p>'}</div>
      <div class="card"><div class="card-head"><h2>Recommendations — official routes</h2><span class="tag">${recs.length}</span></div>
        ${recs.length ? recs.map(x => `<div class="mn"><div class="mt">${linkHtml(x.url, x.label)}</div>
          <div class="mk" lang="ur-PK-Latn">${esc(x.reason || '')}</div></div>`).join('')
          : '<p class="muted small" lang="ur-PK-Latn">Is masle ke liye koi specific official route map nahi hua.</p>'}</div></div>`;
    if (r.offline) h += '<p class="small muted" lang="ur-PK-Latn">OFFLINE MODE: feeds se koi natija nahi mila, is liye koi khabar ka dawa nahi kiya gaya — sirf verified official links hain.</p>';
  }
  if (r.kind === 'gsx') {
    h += `<div class="notice" style="margin-top:14px"><div class="notice-icon" aria-hidden="true">!</div>
      <div><strong>Ye Apple GSX report nahi hai</strong><p lang="ur-PK-Latn">${esc(r.disclaimer || '')}</p></div></div>`;
  }
  if (!r.blocked && (r.official_links || []).length && r.kind !== 'brief') {
    h += `<div class="svc-links"><h3 class="sah-h3">Official links</h3>
      ${r.official_links.map(([t, u]) => linkHtml(u, t + ' ↗')).join('')}</div>`;
  }
  $('#svcFacts').innerHTML = h;
}

async function svcAnalyze() {
  const q = $('#svcAsk').value.trim();
  const out = $('#svcAskOut');
  if (!q) { out.innerHTML = '<p class="muted small">Pehle apna sawaal / masla likhein.</p>'; return; }
  out.innerHTML = '<div class="skeleton"></div>';
  try {
    const r = await api('/api/service-brief/classify?q=' + encodeURIComponent(q));
    state.svcLastClass = r;
    if (r.blocked) { out.innerHTML = svcRefusalHtml(r); return; }
    $('#svcMode').value = r.suggested_mode || 'status';
    $('#svcBrand').value = r.suggested_brand || 'other';
    renderSvcChecks();
    const labels = { status: 'Status check worksheet', gsx: 'GSX request worksheet', brief: 'Problem / research brief' };
    out.innerHTML = `<div class="issue info"><div class="it">Safe request — ${esc(labels[r.suggested_mode] || 'worksheet')}</div>
      <div class="id">${esc(r.reason)}</div></div>
      <p class="small muted" lang="ur-PK-Latn">Mode aur brand auto-select ho gaye. Ab neeche form bhar kar "Generate report / worksheet" dabayein. Ye app khud koi status query ya GSX access nahi karta.</p>`;
  } catch (e) {
    out.innerHTML = `<div class="issue error"><div class="it">Analyze fail</div><div class="id">${esc(e.message)}</div></div>`;
  }
}

async function svcRun() {
  const btn = $('#svcRunBtn'); busy(btn, true, 'Generating…');
  let d = svcFormData();
  try {
    let mode = $('#svcMode').value;
    if (mode === 'auto') {
      const c = await api('/api/service-brief/classify?q=' + encodeURIComponent(d.q));
      if (c.blocked) {
        $('#svcOutput').textContent = c.reason;
        $('#svcFacts').innerHTML = svcRefusalHtml(c);
        svcMsg('Boundary request — sirf official raasta diya gaya.', true);
        return;
      }
      mode = c.suggested_mode || 'status';
      $('#svcMode').value = mode;
      $('#svcBrand').value = c.suggested_brand || 'other';
      renderSvcChecks();
      d = svcFormData();
      state.svcLastClass = c;
    }
    if (mode !== 'brief' && !d.customer) { svcMsg('Customer ka naam zaroori hai', true); return; }
    let r;
    if (mode === 'status') r = await post('/api/service-brief/status', d);
    else if (mode === 'gsx') r = await post('/api/service-brief/gsx', d);
    else r = await post('/api/service-brief/problem', d);
    svcShowResult(r);
    svcMsg(r.blocked ? 'Boundary request — official routes dikhaye gaye.'
                     : '✓ ' + (r.kind || mode) + ' tayyar. Koi live status query, GSX access ya fabricated finding nahi.', false);
  } catch (e) { svcMsg(e.message, true); toast(e.message, true); }
  finally { busy(btn, false); }
}

/* ------------------------------------------------------------------ knowledge */
function renderKnowledge() {
  const k = state.knowledge; if (!k) return;
  const b = k.boundary;
  $('#knowledgeOut').innerHTML = `
    <div class="card"><div class="card-head"><h2>${esc(b.title)}</h2><span class="tag green">${esc(b.policy_name || 'Service Policy')}</span></div>
      <div class="notice soft" style="margin-bottom:14px"><div class="notice-icon" aria-hidden="true">✓</div>
        <div><strong>${esc(b.lead || '')}</strong>
        <p>${esc(b.canonical || '')}</p></div></div>
      ${(b.helps || []).length ? `<div class="focus-grid" style="margin-bottom:14px">${b.helps.map(x => `<div class="focus-item"><div class="fd">${esc(x)}</div></div>`).join('')}</div>` : ''}
      <div class="two-col" style="gap:14px">
        <div><h3 style="color:var(--green);margin-bottom:6px"><span aria-hidden="true">✓</span> What it does</h3>
          <ul class="do-list">${b.does.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>
        <div><h3 style="color:var(--red);margin-bottom:6px"><span aria-hidden="true">✕</span> What it does not</h3>
          <ul class="do-list no">${b.does_not.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>
      </div>
      <div class="notice" style="margin:16px 0 0"><div class="notice-icon" aria-hidden="true">i</div><div>
        <strong>Why?</strong><p>${esc(b.why)}</p></div></div>
      <div class="small muted" style="margin-top:10px">${esc(k.security_note)}</div>
    </div>

    <div class="card"><div class="card-head"><h2>How paid tools work — research summary</h2><span class="tag">deep research</span></div>
      ${k.tool_arch.map(a=>`<details class="acc"><summary>${esc(a.h)}</summary><div class="ab">${esc(a.b)}</div></details>`).join('')}
    </div>

    <div class="two-col">
      <div class="card"><div class="card-head"><h2>Glossary</h2></div>
        <table class="gloss">${k.glossary.map(g=>`<tr><td>${esc(g.term)}</td><td>${esc(g.def)}</td></tr>`).join('')}</table></div>
      <div class="card"><div class="card-head"><h2>Setup / Help</h2></div>
        ${k.help.map(h=>`<details class="acc"><summary>${esc(h.title)}</summary><div class="ab">${esc(h.body)}</div></details>`).join('')}
      </div>
    </div>

    <div class="card"><div class="card-head"><h2>Official routes (verified links)</h2></div>
      ${officialRoutesHtml(k.official_routes)}</div>`;
}

/* ------------------------------------------------------------------ settings */
/* Endpoint / key are CUSTOM-only. For local providers the app owns the
   loopback URL, so sending a stale user endpoint would hit the SSRF guard. */
function syncLlmProvider() {
  const custom = $('#setProvider').value === 'custom';
  for (const id of ['#setEndpoint', '#setKey']) {
    const el = $(id);
    el.disabled = !custom;
    el.title = custom ? '' : 'Sirf custom provider ke liye';
  }
}

async function loadSettings() {
  try {
    const s = await api('/api/settings');
    $('#setTech').value = s.technician || ''; $('#setShop').value = s.shop || '';
    $('#setEndpoint').value = s.llm_endpoint || ''; $('#setKey').value = '';
    $('#setModel').value = s.llm_model || ''; $('#setCache').value = s.cache_minutes || '15';
    $('#setProvider').value = s.llm_provider || 'off';
    syncLlmProvider();
    const lm = await api('/api/llm/status').catch(() => null);
    const modelLine = !lm ? 'Model: status dastiyab nahi'
      : (lm.enabled ? `Model ON — ${lm.provider} / ${lm.model}; research khulasa LLM se rewrite hoga.`
                    : `Model OFF — ${lm.reason}`);
    $('#llmState').textContent = modelLine;
    const st = state.status || await api('/api/status');
    $('#statusOut').innerHTML = Object.entries({
      'App version': st.version, 'Python': st.python, 'Local URL': st.web,
      'Database': st.db, 'Live sources': st.sources, 'Model': modelLine,
      'Security': st.security_note,
    }).map(([a,b]) => `<div class="k">${esc(a)}</div><div>${esc(b)}</div>`).join('');
  } catch (e) { toast(e.message, true); }
}

async function refreshCounts() {
  try { state.status = await api('/api/status'); renderStats(); } catch {}
}

/* ------------------------------------------------------------------ bindings */
function bind() {
  $('#nav').addEventListener('click', e => {
    const b = e.target.closest('.nav-item'); if (b) nav(b.dataset.view);
  });
  $('#nav').addEventListener('keydown', e => {
    const tabs = $$('.nav-item');
    const i = tabs.indexOf(document.activeElement);
    if (i < 0) return;
    let n = -1;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') n = (i + 1) % tabs.length;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') n = (i - 1 + tabs.length) % tabs.length;
    else if (e.key === 'Home') n = 0;
    else if (e.key === 'End') n = tabs.length - 1;
    else return;
    e.preventDefault();
    tabs[n].focus();
    nav(tabs[n].dataset.view);
  });
  window.addEventListener('hashchange', () => {
    const v = (location.hash || '').replace('#', '');
    if (v && !$('#view-' + v)?.classList.contains('active')) nav(v, false);
  });
  document.addEventListener('click', e => {
    const g = e.target.closest('[data-goto]');
    if (g) { e.preventDefault(); nav(g.dataset.goto); }
  });

  $('#dashSampleBtn').onclick = () => { $('#dashPath').value = samplePath(); };
  $('#dashScanBtn').onclick = () => runScan($('#dashPath'), $('#dashScanOut'));
  $('#dashNewsBtn').onclick = loadDashNews;
  $('#pkgSampleBtn').onclick = () => { $('#pkgPath').value = samplePath(); };
  $('#pkgScanBtn').onclick = () => runScan($('#pkgPath'), $('#pkgScanOut'), {
    name: $('#pkgName').value.trim(), tags: $('#pkgTags').value.trim(),
  });
  $('#pkgReload').onclick = loadPackages;

  $('#resFetch').onclick = () => fetchResearch(false);
  $('#resRefresh').onclick = () => fetchResearch(true);
  $('#resSavedToggle').onclick = showSaved;
  $('#srcAll').onclick = () => $$('#srcChecks input').forEach(i => i.checked = true);
  $('#srcNone').onclick = () => $$('#srcChecks input').forEach(i => i.checked = false);
  $('#resOnlyImportant').onchange = e => { if (e.target.checked) $('#resScore').value = '7'; };
  $('#resResults').addEventListener('click', async e => {
    const btn = e.target.closest('button[data-act]'); if (!btn) return;
    const card = btn.closest('.res-card'); const guid = card?.dataset.g; if (!guid) return;
    const act = btn.dataset.act;
    if (act === 'useful' || act === 'bad') {
      try {
        await post('/api/memory/feedback', {
          target_type: 'item', target_key: guid, source: card.dataset.src || '',
          rating: act === 'useful' ? 'useful' : 'not_useful',
        });
        state.memoryLoaded = false;
        toast(act === 'useful' ? 'Memory: source ki usefulness barha di'
                               : 'Memory: source demote ho gaya (archive nahi)');
        refreshCounts();
      } catch (err) { toast(err.message, true); }
      return;
    }
    let action = act === 'save' ? (btn.textContent.includes('Saved') ? 'unsave' : 'save')
                               : (btn.textContent.includes('Read ✓') ? 'unread' : 'read');
    try {
      await post('/api/article', { guid, action });
      if (action === 'save') { btn.textContent = '✓ Saved'; card.classList.add('saved'); }
      if (action === 'unsave') { btn.textContent = 'Save'; card.classList.remove('saved'); }
      if (action === 'read') btn.textContent = 'Read ✓';
      if (action === 'unread') btn.textContent = 'Mark read';
      refreshCounts();
    } catch (err) { toast(err.message, true); }
  });

  $('#modelSearch').onclick = searchModel;
  $('#modelQ').addEventListener('keydown', e => { if (e.key === 'Enter') searchModel(); });
  $('#jobAdd').onclick = async () => {
    try {
      await post('/api/jobs', { imei:$('#jobImei').value, model:$('#jobModel').value,
        customer:$('#jobCustomer').value, proof_ok:$('#jobProof').checked,
        route:$('#jobRoute').value, notes:$('#jobNotes').value });
      ['#jobImei','#jobModel','#jobCustomer','#jobNotes'].forEach(s => $(s).value = '');
      $('#jobProof').checked = false;
      loadJobs(); refreshCounts(); toast('Job registered');
    } catch (e) { toast(e.message, true); }
  };
  $('#jobReload').onclick = loadJobs;

  $('#sahCheckBtn').onclick = sahCheck;
  $('#sahCheckQ').addEventListener('keydown', e => { if (e.key === 'Enter') sahCheck(); });
  $('#sahLetterBtn').onclick = sahLetter;
  $('#sahCaseBtn').onclick = sahSaveCase;
  $('#sahReload').onclick = loadSahCases;
  $('#sahLetterCopy').onclick = () => copyText($('#sahLetter').textContent, 'Letter copied');
  $('#sahConsentCopy').onclick = () => copyText($('#sahConsent').textContent, 'Consent form copied');

  // ---- Agent memory ----
  $('#memSourceAdd').onclick = memAddSource;
  $('#memSourceName').addEventListener('keydown', e => { if (e.key === 'Enter') memAddSource(); });
  $('#memTgAdd').onclick = memAddTelegram;
  $('#memTgChannel').addEventListener('keydown', e => { if (e.key === 'Enter') memAddTelegram(); });
  $('#memTgSearchBtn').onclick = () => memSearchTelegram();
  $('#memTgSearchQ').addEventListener('keydown', e => { if (e.key === 'Enter') memSearchTelegram(); });
  $('#memRecallBtn').onclick = memRecall;
  $('#memRecallQ').addEventListener('keydown', e => { if (e.key === 'Enter') memRecall(); });
  $('#memProbAdd').onclick = memAddProblem;
  $('#memExportBtn').onclick = memExport;
  $('#memReloadBtn').onclick = () => loadMemory(true);
  $('#memSourceList').addEventListener('click', async e => {
    const p = e.target.closest('[data-promote]');
    const d = e.target.closest('[data-demote]');
    const a = e.target.closest('[data-archive]');
    try {
      if (p) { await post('/api/memory/sources/promote', { id: +p.dataset.promote, useful: true }); toast('Priority barha di'); }
      if (d) { await post('/api/memory/sources/promote', { id: +d.dataset.demote, useful: false }); toast('Priority kam kar di'); }
      if (a) { await api('/api/memory/sources/' + a.dataset.archive, { method: 'DELETE' }); toast('Source archive ho gaya'); }
      if (p || d || a) { await loadMemory(true); refreshCounts(); }
    } catch (err) { toast(err.message, true); }
  });
  $('#memTgList').addEventListener('click', async e => {
    const s = e.target.closest('[data-tgsearch]');
    const a = e.target.closest('[data-tgarchive]');
    try {
      if (s) {
        $('#memTgSearchChannel').value = s.dataset.tgsearch;
        memSearchTelegram(s.dataset.tgsearch, '');
      }
      if (a) {
        await api('/api/memory/telegram/' + a.dataset.tgarchive, { method: 'DELETE' });
        toast('Channel archive ho gaya'); await loadMemory(true); refreshCounts();
      }
    } catch (err) { toast(err.message, true); }
  });
  $('#memQueries').addEventListener('click', e => {
    const b = e.target.closest('[data-recall]'); if (!b) return;
    $('#resQ').value = b.dataset.recall;
    state.memoryLoaded = false;
    nav('research');
    fetchResearch(false);
  });

  $('#svcAskBtn').onclick = svcAnalyze;
  $('#svcAsk').addEventListener('keydown', e => { if (e.key === 'Enter') svcAnalyze(); });
  $('#svcBrand').onchange = renderSvcChecks;
  $('#svcRunBtn').onclick = svcRun;
  $('#svcCopyBtn').onclick = () => copyText($('#svcOutput').textContent, 'Report copied');

  $('#setProvider').onchange = syncLlmProvider;
  $('#setSave').onclick = async () => {
    try {
      const payload = { technician:$('#setTech').value, shop:$('#setShop').value,
        llm_provider:$('#setProvider').value,
        llm_model:$('#setModel').value, cache_minutes:$('#setCache').value };
      if (payload.llm_provider === 'custom') {
        payload.llm_endpoint = $('#setEndpoint').value;
        payload.llm_key = $('#setKey').value;
      }
      await post('/api/settings', payload);
      $('#setMsg').textContent = '✓ Saved'; $('#setKey').value = '';
      setTimeout(() => $('#setMsg').textContent = '', 3000);
      toast('Settings saved');
      await loadSettings();
    } catch (e) { toast(e.message, true); }
  };
  $('#llmTest').onclick = async () => {
    const out = $('#llmTestMsg');
    out.textContent = 'Testing…';
    try {
      const r = await post('/api/llm/test', {});
      out.textContent = r.ok
        ? `✓ ${r.provider} / ${r.model} — ${r.latency_ms} ms`
        : `✗ ${r.error || 'Model se rabta nahi ho saka'}`;
      toast(r.ok ? 'Model chal raha hai' : 'Model test fail', !r.ok);
    } catch (e) { out.textContent = '✗ ' + e.message; toast(e.message, true); }
  };
}

/* ------------------------------------------------------------------ boot */
async function init() {
  bind();
  renderFocus();
  try {
    const [status, sources, knowledge, sahulat, serviceBrief] = await Promise.all([
      api('/api/status'), api('/api/sources'), api('/api/knowledge'), api('/api/sahulat/overview'),
      api('/api/service-brief/overview'),
    ]);
    state.status = status; state.sources = sources.sources;
    state.presets = sources.presets; state.categories = sources.categories;
    state.knowledge = knowledge;
    state.sahulat = sahulat; state.sahLoaded = true;
    state.serviceBrief = serviceBrief;
    state.sampleDir = status.sample_dir || 'samples\\MTK_Demo_MT6899_UFS';
    renderStats(); renderPresets(); renderCategories(); renderJobRoutes(); renderKnowledge();
    renderSahulat(); renderServiceBrief();
  } catch (e) { toast('Init fail: ' + e.message, true); }
  nav((location.hash || '').replace('#', '') || 'dashboard', false);
  loadPackages(); loadDashNews(); loadJobs(); loadSettings();
  const tick = () => { $('#clock').textContent = new Date().toLocaleString(undefined,
    { weekday:'short', day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit' }); };
  tick(); setInterval(tick, 30000);
}
init();
