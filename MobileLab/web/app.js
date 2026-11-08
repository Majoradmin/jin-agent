/* MobileLab frontend - no external libraries, fully offline-capable UI. */
'use strict';

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const human = (n) => { n = +n || 0; const u=['B','KB','MB','GB','TB']; let i=0; while(n>=1024&&i<4){n/=1024;i++;} return (i?n.toFixed(1):n.toFixed(0))+' '+u[i]; };
/* QA #4: only http/https links may become href. javascript:/data: rejected. */
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
  dashboard: ['Dashboard', 'Aap ka local mobile-software workspace'],
  packages:  ['Firmware Packages', 'Scan, validate aur catalog — MTK scatter/preloader/DA aur Qualcomm Firehose'],
  research:  ['Research Agent', 'Live browsing, filters aur Roman Urdu khulasa'],
  models:    ['Model Brief', 'Local model card + usi model par live information'],
  jobs:      ['Job Register', 'IMEI, ownership proof aur official route ka record'],
  sahulat:   ['Sahulat / Official Route', 'Checklist, consent, service-request letter aur case register — wajah + official link ke saath'],
  knowledge: ['Knowledge / Help', 'Research findings, official routes, glossary aur setup'],
  settings:  ['Settings', 'Ikhtiyari LLM aur app preferences'],
};

const state = {
  status: null, sources: [], presets: [], categories: [], knowledge: null,
  packages: [], selected: null, researchLoaded: false, savedMode: false,
  preset: 'all', lastItems: [], basePath: '',
  sahulat: null, sahLoaded: false,
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
  if (on) { btn._l = btn.textContent; btn.textContent = label || 'Chal raha hai…'; }
  else btn.textContent = btn._l || btn.textContent;
}

function nav(view, updateHash = true) {
  if (!TITLES[view]) view = 'dashboard';
  if (updateHash && location.hash !== '#' + view) location.hash = view;
  $$('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  $$('.view').forEach(v => v.classList.remove('active'));
  const el = $('#view-' + view); if (el) el.classList.add('active');
  const [t, s] = TITLES[view] || TITLES.dashboard;
  $('#viewTitle').textContent = t; $('#viewSub').textContent = s;
  window.scrollTo({ top: 0, behavior: 'smooth' });
  if (view === 'research' && !state.researchLoaded) fetchResearch(false);
  if (view === 'packages' && !state.packages.length) loadPackages();
  if (view === 'jobs') loadJobs();
  if (view === 'sahulat') loadSahulat();
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
    `<div class="focus-item"><div class="ft">${esc(t)}</div><div class="fd">${esc(d)}</div></div>`).join('');
}

async function loadDashNews() {
  const box = $('#dashNews'); box.innerHTML = '<div class="skeleton"></div><div class="skeleton" style="margin-top:8px"></div>';
  try {
    const r = await api('/api/research?preset=all&days=30&min_score=2&limit=8&sources=gnews,gsmarena,androidauthority,xda');
    const items = r.items.slice(0, 6);
    box.innerHTML = items.length ? items.map(i =>
      `<div class="mn"><div class="mt">${linkHtml(i.url, i.title)}</div>
       <div class="mk">${esc(i.khulasa)}</div></div>`).join('')
      : '<p class="muted small">Abhi koi matching khabar nahi mili. Research Agent mein filters khol kar dobara try karain.</p>';
  } catch (e) { box.innerHTML = `<p class="muted small">Fetch nahi hua: ${esc(e.message)}</p>`; }
  refreshCounts();
}

/* ------------------------------------------------------------------ packages */
function samplePath() {
  if (!state.basePath) return '';
  return state.basePath + 'samples\\MTK_Demo_MT6899_UFS';
}

async function loadPackages() {
  const box = $('#pkgList');
  try {
    const r = await api('/api/packages');
    state.packages = r.items;
    if (!r.items.length) { box.innerHTML = '<div class="empty-state">Abhi koi package nahi. Upar folder scan karain.</div>'; return; }
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
  } catch (e) { box.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`; }
}

function renderReport(rep, meta, pid) {
  if (!rep) return '';
  const h = rep.health;
  const color = h >= 80 ? 'var(--green)' : h >= 55 ? 'var(--amber)' : 'var(--red)';
  const issues = (rep.issues || []).map(i =>
    `<div class="issue ${esc(i.level)}"><div class="it">${esc(i.msg)}</div>
     ${i.detail ? `<div class="id">${esc(i.detail)}</div>` : ''}</div>`).join('') ||
    '<p class="muted small">Koi issue nahi mila — package saaf lag raha hai.</p>';
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
        <div><button class="btn ghost sm" id="pdReveal">Folder kholen</button>
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
        <tbody>${files || '<tr><td colspan="4">Koi file nahi</td></tr>'}</tbody></table></div>`;
    $('#pdReveal').onclick = async () => {
      try { await post('/api/reveal', { path: p.path }); }
      catch (e) { toast(e.message, true); }
    };
    $('#pdDelete').onclick = async () => {
      if (!confirm('Ye package catalog se hata dein? (Disk par files rahein gi)')) return;
      await api('/api/packages/' + id, { method: 'DELETE' });
      state.selected = null; box.innerHTML = '<div class="empty-state">Package hata diya gaya.</div>';
      loadPackages(); refreshCounts(); toast('Package catalog se hata diya');
    };
  } catch (e) { box.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`; }
}

async function runScan(pathEl, outEl, extra = {}) {
  const path = pathEl.value.trim().replace(/^"|"$/g, '');
  if (!path) { toast('Pehle folder path likhein', true); return; }
  outEl.innerHTML = '<div class="skeleton"></div>';
  try {
    const r = await post('/api/scan', { path, ...extra });
    outEl.innerHTML = `<div class="notice soft"><div class="notice-icon">✓</div><div>
      <strong>Scan mukammal — ${r.file_count} files, health ${r.report.health}%</strong>
      <p>${esc(r.meta.platform || 'Unknown')} / ${esc(r.meta.chipset || '?')} / ${esc(r.meta.storage || '?')}.
      Neeche poori report aur right side mein file list hai.</p></div></div>` + renderReport(r.report, r.meta, r.id);
    await loadPackages(); await loadPackage(r.id); refreshCounts();
    toast('Scan ho gaya — package #' + r.id + ' save ho gaya');
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
  $('#resCat').innerHTML = '<option value="all">Sab categories</option>' +
    state.categories.map(c => `<option value="${esc(c.id)}">${esc(c.label)}</option>`).join('');
  $('#srcCount').textContent = '(' + state.sources.length + ')';
  $('#srcChecks').innerHTML = state.sources.map(s =>
    `<label class="checkline"><input type="checkbox" value="${esc(s.id)}" checked> ${esc(s.name)}</label>`).join('');
}
function selectedSources() {
  return $$('#srcChecks input:checked').map(i => i.value);
}

async function fetchResearch(force) {
  const btn = $('#resFetch'); busy(btn, true, 'Fetch ho raha hai…');
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
    $('#fetchStamp').textContent = r.cached ? 'cache se · ' + r.fetched_at : 'live · ' + r.fetched_at;
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
  return `<div class="res-card ${i.saved ? 'saved' : ''}" data-g="${esc(i.guid)}">
    <div class="rc-top">
      <span class="tag ${catColors[i.category] || ''}">${esc(i.category_label)}</span>
      <span class="score">score ${i.score}</span>
      <span class="small muted">${esc(i.published || 'date nahi')}</span>
    </div>
    <div class="rc-title">${linkHtml(i.url, i.title)}</div>
    <div class="rc-khulasa">${esc(i.khulasa)}${i.llm ? ' <span class="tag">LLM</span>' : ''}</div>
    ${i.excerpt ? `<div class="rc-excerpt">${esc(i.excerpt)}</div>` : ''}
    ${i.matched ? `<div class="small muted" style="margin-bottom:9px">Match: ${esc(i.matched)}</div>` : ''}
    <div class="rc-foot">
      <span class="src">${esc(i.source)}${i.age_days !== null && i.age_days !== undefined ? ' · ' + i.age_days + ' din pehle' : ''}</span>
      <button class="btn ghost sm" data-act="save">${i.saved ? '✓ Saved' : 'Save'}</button>
      <button class="btn ghost sm" data-act="read">${i.is_read ? 'Read ✓' : 'Mark read'}</button>
      ${href ? `<a class="btn ghost sm" href="${esc(href)}" target="_blank" rel="noopener noreferrer">Open ↗</a>` : ''}
    </div>
  </div>`;
}

function renderResearch(r) {
  const items = r.items || [];
  const head = `<div class="card"><div class="res-toolbar">
      <div><strong>${items.length} results</strong> <span class="muted small">/ ${r.total ?? '—'} raw items · query: "${esc(r.query || '')}"</span></div>
      <span class="muted small">${r.cached ? 'cached' : 'live fetch'} · ${esc(r.fetched_at || '')}</span></div>
      <div class="muted small">Filters: category=${esc(r.category || 'all')} · relevance score ke hisaab se sorted. Roman Urdu khulasa rule-based hai; asal headline English mein hai (technical accuracy ke liye).</div></div>`;
  const cards = items.length
    ? `<div class="res-results">${items.map(resCard).join('')}</div>`
    : '<div class="card"><div class="empty-state">Is filter par koi result nahi. Min score kam karain, days barhayein ya query badlein.</div></div>';
  $('#resResults').innerHTML = head + cards;
}

async function showSaved() {
  state.savedMode = true;
  try {
    const r = await api('/api/articles?mode=saved');
    $('#resResults').innerHTML = `<div class="card"><div class="res-toolbar"><div><strong>${r.items.length} saved items</strong></div>
      <button class="btn ghost sm" id="backLive">Wapas live results</button></div></div>` +
      (r.items.length ? `<div class="res-results">${r.items.map(i => resCard({
        guid:i.guid,title:i.title,url:i.url,source:i.source,published:i.published,
        category:i.category,category_label:(state.categories.find(c=>c.id===i.category)||{}).label || i.category,
        score:i.score,matched:i.matched,excerpt:i.excerpt,khulasa:i.khulasa,saved:1,is_read:i.is_read,
        age_days:null,
      })).join('')}</div>` : '<div class="card"><div class="empty-state">Abhi kuch save nahi kiya. Research cards par "Save" dabayein.</div></div>');
    $('#backLive').onclick = () => { state.savedMode = false; renderResearch({ ...state.lastResult, items: state.lastItems }); };
  } catch (e) { toast(e.message, true); }
}

/* ------------------------------------------------------------------ models */
async function searchModel() {
  const q = $('#modelQ').value.trim();
  if (!q) { toast('Model number likhein', true); return; }
  const out = $('#modelOut'); out.innerHTML = '<div class="card"><div class="skeleton"></div></div>';
  const live = $('#modelLive').checked ? '1' : '0';
  try {
    const r = await api('/api/model-brief?q=' + encodeURIComponent(q) + '&live=' + live);
    const c = r.card || {};
    const pkgs = r.packages.length ? r.packages.map(p =>
      `<div class="issue info"><div class="it">${esc(p.name)} — health ${p.health}%</div>
       <div class="id">${esc(p.platform||'?')} / ${esc(p.chipset||'?')} / ${esc(p.storage||'?')}</div></div>`).join('')
      : '<p class="muted small">Is model ka koi scanned package nahi.</p>';
    const news = (r.live && r.live.items || []).map(i =>
      `<div class="mn"><div class="mt">${linkHtml(i.url, i.title)}</div>
       <div class="mk">${esc(i.khulasa)}</div></div>`).join('') || '<p class="muted small">Koi live khabar nahi mili.</p>';
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
          <button class="btn primary" id="mcSave">Model card save karein</button>
          <span class="muted small" style="margin-left:10px">Ye aap ka apna local knowledge base hai — jitna bharein utna behtar brief banega.</span>
        </div>
        <div class="card"><div class="card-head"><h2>Live information</h2><span class="tag green">${esc(r.live?.fetched_at || 'offline')}</span></div>
          <div class="mini-news">${news}</div>
          <h3 style="margin:16px 0 8px">Related scanned packages</h3>${pkgs}
        </div>
      </div>
      <div class="card"><div class="card-head"><h2>Account / activation issues ke official routes</h2></div>
        ${officialRoutesHtml(r.official)}</div>`;
    $('#mcSave').onclick = async () => {
      try {
        await post('/api/models', { model:q, oem:$('#mcOem').value, chipset:$('#mcChip').value,
          platform:$('#mcPlat').value === '(select)' ? '' : $('#mcPlat').value,
          storage:$('#mcStore').value === '(select)' ? '' : $('#mcStore').value,
          official_url:$('#mcUrl').value, notes:$('#mcNotes').value });
        toast('Model card save ho gaya'); refreshCounts();
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
  $('#jobRoute').innerHTML = '<option value="">(select karein)</option>' +
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
      : '<div class="empty-state">Register khaali hai. Upar pehla job add karain.</div>';
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
      $('#sahRoutes').innerHTML = `<div class="issue error"><div class="it">Sahulat data load nahi hua</div><div class="id">${esc(e.message)}</div></div>`;
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
      <span><b>${esc(c.label)}</b>${c.required ? ' <span class="tag amber">zaroori</span>' : ''}
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
        <button class="btn ghost sm" data-pick="${esc(r.id)}">Is route ko form mein chunein</button>
      </div>
    </details>`).join('');
  $$('#sahRoutes [data-pick]').forEach(b => b.onclick = () => {
    $('#sahBrand').value = b.dataset.pick;
    const r = o.routes.find(x => x.id === b.dataset.pick);
    if (r && !$('#sahIssue').value.trim()) $('#sahIssue').value = r.issue;
    toast('Route form mein select ho gaya');
  });
  $('#sahBoundary').innerHTML = `
    <div class="notice" style="margin-bottom:12px"><div class="notice-icon">i</div>
      <div><strong>${esc(o.policy.canonical)}</strong></div></div>
    <h3 class="sah-h3">✓ Hum kya madad karte hain</h3>
    <ul class="do-list">${o.policy.helps.map(x => `<li>${esc(x)}</li>`).join('')}</ul>
    <h3 class="sah-h3">✕ Service boundary (barqarar)</h3>
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
  if (!txt) { toast('Pehle text tayyar karain', true); return; }
  const fallback = () => {
    const ta = document.createElement('textarea');
    ta.value = txt; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); toast(okMsg); }
    catch { toast('Copy nahi hua — text ko select karain', true); }
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
        <div class="it">${r.blocked ? 'Boundary request — official raasta diya gaya' : 'Ye kaam app ke andar hai'}</div>
        <div class="id">${esc(r.reason)}</div></div>
      ${r.blocked ? `<div class="small muted"><b>Official route:</b> ${esc(r.official_route)}</div>${links}${docs}` : ''}
      <ol class="sr-steps">${r.safe_next_steps.map(s => `<li>${esc(s)}</li>`).join('')}</ol>
      ${r.refusal_line ? `<div class="notice" style="margin-top:10px"><div class="notice-icon">i</div><div><p>${esc(r.refusal_line)}</p></div></div>` : ''}
      <div class="small muted">Policy: ${esc(r.policy)}</div>`;
  } catch (e) { out.innerHTML = `<div class="issue error"><div class="it">Check fail</div><div class="id">${esc(e.message)}</div></div>`; }
}

async function sahLetter() {
  const btn = $('#sahLetterBtn'); busy(btn, true, 'Letter ban raha hai…');
  try {
    const r = await post('/api/sahulat/letter', sahFormData());
    $('#sahLetter').textContent = r.letter;
    sahMsg('✓ Letter preview tayyar. Abhi case save nahi hua — neeche wala button dabayein.');
  } catch (e) { sahMsg(e.message, true); toast(e.message, true); }
  finally { busy(btn, false); }
}

async function sahSaveCase() {
  const btn = $('#sahCaseBtn'); busy(btn, true, 'Case save ho raha hai…');
  try {
    const r = await post('/api/sahulat/case', sahFormData());
    if (r.letter) $('#sahLetter').textContent = r.letter;
    sahMsg(r.letter_error
      ? '✓ Case save (' + r.case.status + '). Letter ke liye: ' + r.letter_error
      : '✓ Case ' + r.case.case_no + ' save ho gaya aur letter tayyar hai.', false);
    toast('Case ' + r.case.case_no + ' save ho gaya');
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
      : '<div class="empty-state">Case register khaali hai. Upar form bhar kar pehla case save karain.</div>';
  } catch (e) { box.innerHTML = `<div class="issue error"><div class="it">${esc(e.message)}</div></div>`; }
}

/* ------------------------------------------------------------------ knowledge */
function renderKnowledge() {
  const k = state.knowledge; if (!k) return;
  const b = k.boundary;
  $('#knowledgeOut').innerHTML = `
    <div class="card"><div class="card-head"><h2>${esc(b.title)}</h2><span class="tag green">${esc(b.policy_name || 'Service Policy')}</span></div>
      <div class="notice soft" style="margin-bottom:14px"><div class="notice-icon">✓</div>
        <div><strong>${esc(b.lead || '')}</strong>
        <p>${esc(b.canonical || '')}</p></div></div>
      ${(b.helps || []).length ? `<div class="focus-grid" style="margin-bottom:14px">${b.helps.map(x => `<div class="focus-item"><div class="fd">${esc(x)}</div></div>`).join('')}</div>` : ''}
      <div class="two-col" style="gap:14px">
        <div><h3 style="color:var(--green);margin-bottom:6px">✓ Karta hai</h3>
          <ul class="do-list">${b.does.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>
        <div><h3 style="color:var(--red);margin-bottom:6px">✕ Nahi karta</h3>
          <ul class="do-list no">${b.does_not.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>
      </div>
      <div class="notice" style="margin:16px 0 0"><div class="notice-icon">i</div><div>
        <strong>Kyun?</strong><p>${esc(b.why)}</p></div></div>
      <div class="small muted" style="margin-top:10px">${esc(k.security_note)}</div>
    </div>

    <div class="card"><div class="card-head"><h2>Paid tools kaisy kaam karte hain — research summary</h2><span class="tag">deep research</span></div>
      ${k.tool_arch.map(a=>`<details class="acc"><summary>${esc(a.h)}</summary><div class="ab">${esc(a.b)}</div></details>`).join('')}
    </div>

    <div class="two-col">
      <div class="card"><div class="card-head"><h2>Glossary</h2></div>
        <table class="gloss">${k.glossary.map(g=>`<tr><td>${esc(g.term)}</td><td>${esc(g.def)}</td></tr>`).join('')}</table></div>
      <div class="card"><div class="card-head"><h2>Setup / Madad</h2></div>
        ${k.help.map(h=>`<details class="acc"><summary>${esc(h.title)}</summary><div class="ab">${esc(h.body)}</div></details>`).join('')}
      </div>
    </div>

    <div class="card"><div class="card-head"><h2>Official routes (verified links)</h2></div>
      ${officialRoutesHtml(k.official_routes)}</div>`;
}

/* ------------------------------------------------------------------ settings */
async function loadSettings() {
  try {
    const s = await api('/api/settings');
    $('#setTech').value = s.technician || ''; $('#setShop').value = s.shop || '';
    $('#setEndpoint').value = s.llm_endpoint || ''; $('#setKey').value = '';
    $('#setModel').value = s.llm_model || ''; $('#setCache').value = s.cache_minutes || '15';
    const st = state.status || await api('/api/status');
    $('#statusOut').innerHTML = Object.entries({
      'App version': st.version, 'Python': st.python, 'Local URL': st.web,
      'Database': st.db, 'Live sources': st.sources, 'Security': st.security_note,
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
      loadJobs(); refreshCounts(); toast('Job register ho gaya');
    } catch (e) { toast(e.message, true); }
  };
  $('#jobReload').onclick = loadJobs;

  $('#sahCheckBtn').onclick = sahCheck;
  $('#sahCheckQ').addEventListener('keydown', e => { if (e.key === 'Enter') sahCheck(); });
  $('#sahLetterBtn').onclick = sahLetter;
  $('#sahCaseBtn').onclick = sahSaveCase;
  $('#sahReload').onclick = loadSahCases;
  $('#sahLetterCopy').onclick = () => copyText($('#sahLetter').textContent, 'Letter copy ho gaya');
  $('#sahConsentCopy').onclick = () => copyText($('#sahConsent').textContent, 'Consent form copy ho gaya');

  $('#setSave').onclick = async () => {
    try {
      await post('/api/settings', { technician:$('#setTech').value, shop:$('#setShop').value,
        llm_endpoint:$('#setEndpoint').value, llm_key:$('#setKey').value,
        llm_model:$('#setModel').value, cache_minutes:$('#setCache').value });
      $('#setMsg').textContent = '✓ Save ho gaya'; $('#setKey').value = '';
      setTimeout(() => $('#setMsg').textContent = '', 3000);
      toast('Settings save ho gaye');
    } catch (e) { toast(e.message, true); }
  };
}

/* ------------------------------------------------------------------ boot */
async function init() {
  bind();
  renderFocus();
  try {
    const [status, sources, knowledge, sahulat] = await Promise.all([
      api('/api/status'), api('/api/sources'), api('/api/knowledge'), api('/api/sahulat/overview'),
    ]);
    state.status = status; state.sources = sources.sources;
    state.presets = sources.presets; state.categories = sources.categories;
    state.knowledge = knowledge;
    state.sahulat = sahulat; state.sahLoaded = true;
    const dbp = (status.db || '').replace(/[\\/]data[\\/]mobilelab\.db$/i, '');
    state.basePath = dbp ? (dbp.endsWith('\\') || dbp.endsWith('/') ? dbp : dbp + '\\') : '';
    renderStats(); renderPresets(); renderCategories(); renderJobRoutes(); renderKnowledge(); renderSahulat();
  } catch (e) { toast('Init fail: ' + e.message, true); }
  nav((location.hash || '').replace('#', '') || 'dashboard', false);
  loadPackages(); loadDashNews(); loadJobs(); loadSettings();
  const tick = () => { $('#clock').textContent = new Date().toLocaleString(undefined,
    { weekday:'short', day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit' }); };
  tick(); setInterval(tick, 30000);
}
init();
