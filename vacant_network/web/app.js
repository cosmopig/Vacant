/* Vacant 觀測台 — 純原生 JS，無框架、無 CDN、無 build step。
 *
 * 資料流：/api/state 一次載入全景（首屏），/events (SSE) 推增量事件，
 * 事件到達即重抓受影響的切面。所有顯示值都直接來自 API，前端不做任何
 * 推斷或補值——沒有的資料顯示「—」，不顯示 0。
 */
'use strict';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const state = { sys: null, ids: [], acts: [], integrity: null, sb: null, counters: {}, cost: null };

/* ── 小工具 ─────────────────────────────────────────────── */
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const pct = (num, den) => den ? `${(100 * num / den).toFixed(0)}%` : '—';
const clock = (ms) => ms ? new Date(ms).toLocaleTimeString('zh-TW', { hour12: false }) : '—';

/** 雜湊顯示：中間省略（前 6 後 4），保留頭尾才有比對價值；點擊複製全文。 */
function hash(v, head = 6, tail = 4) {
  const s = String(v ?? '');
  if (!s) return '<span style="color:var(--ink-3)">—</span>';
  const txt = s.length <= head + tail + 1 ? s : `${s.slice(0, head)}…${s.slice(-tail)}`;
  return `<button class="hash" data-copy="${esc(s)}" title="${esc(s)}（點擊複製）">${esc(txt)}</button>`;
}
document.addEventListener('click', async (e) => {
  const b = e.target.closest('.hash[data-copy]');
  if (!b) return;
  try {
    await navigator.clipboard.writeText(b.dataset.copy);
    const old = b.textContent;
    b.textContent = '已複製';
    b.classList.add('copied');
    setTimeout(() => { b.textContent = old; b.classList.remove('copied'); }, 900);
  } catch { /* 無剪貼簿權限：title 仍可看全文 */ }
});

/** 三態：已驗 / 未驗 / 驗失敗。
 *  色 ＋ 形 ＋ 字三種訊號同時給（色盲可讀），且「未驗」是中性灰不是警告色——
 *  未驗證不是壞事，但**絕不可留白**，留白會被讀成「沒問題」。 */
function tri(v, labels = ['通過', '未通過', '未稽核']) {
  if (v === true) return `<span class="tri pass"><i class="mark"></i>${labels[0]}</span>`;
  if (v === false) return `<span class="tri fail"><i class="mark"></i>${labels[1]}</span>`;
  return `<span class="tri none"><i class="mark"></i>${labels[2]}</span>`;
}

function meter(v) {
  const p = Math.max(0, Math.min(1, Number(v) || 0));
  const cls = p < 0.4 ? 'low' : p < 0.65 ? 'mid' : '';
  return `<div class="meter"><div class="track">
    <div class="fill ${cls}" style="width:${(p * 100).toFixed(1)}%"></div></div>
    <span class="n">${p.toFixed(3)}</span></div>`;
}

function flagBadges(flags, probation) {
  const out = (flags || []).map((f) => {
    const cls = f === 'AUDIT_FAIL' ? 'bad' : 'warn';
    return `<span class="badge ${cls}">${esc(f)}</span>`;
  });
  if (probation && !(flags || []).includes('PROBATION')) out.push('<span class="badge warn">PROBATION</span>');
  if (!out.length) out.push('<span class="badge ok">無旗標</span>');
  return `<div class="badges">${out.join('')}</div>`;
}

async function api(path) {
  const r = await fetch(path, { cache: 'no-store' });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

/* ── 視圖切換 ───────────────────────────────────────────── */
const TITLES = {
  overview: '總覽', identities: '身份', activity: '活動',
  chain: '鏈完整性', claims: '宣稱階梯',
};
function show(view) {
  $$('.view').forEach((v) => { v.hidden = v.id !== `view-${view}`; });
  $$('#nav button').forEach((b) => b.setAttribute('aria-current', String(b.dataset.view === view)));
  $('#view-title').textContent = TITLES[view] || view;
  location.hash = view;
}
$('#nav').addEventListener('click', (e) => {
  const b = e.target.closest('button[data-view]');
  if (b) show(b.dataset.view);
});

/* ── 繪製 ───────────────────────────────────────────────── */
function renderTiles() {
  const c = state.counters || {};
  const delivered = c.DELIVERED || 0;
  const audits = c.AUDIT || 0;
  const acts = state.acts || [];
  const auditRan = acts.filter((a) => a.audit_performed);
  const auditPass = auditRan.filter((a) => a.audit_passed === true).length;
  const faults = c.SLASH || 0;

  const tiles = [
    { label: '身份', value: state.ids.length, sub: `${state.ids.filter((i) => i.genesis_proven).length} 條記憶鏈已證明擁有權`, cls: 'accent' },
    { label: '交付', value: delivered, sub: `ledger 共 ${state.integrity?.ledger_seq ?? '—'} 筆事件` },
    { label: '稽核通過率', value: auditRan.length ? pct(auditPass, auditRan.length) : '—',
      sub: auditRan.length ? `${auditPass} / ${auditRan.length} 已稽核` : '尚無稽核紀錄',
      cls: auditRan.length && auditPass === auditRan.length ? 'ok' : auditRan.length ? 'warn' : '' },
    { label: '稽核事件', value: audits, sub: `抽樣率 ${state.sys ? state.sys.audit_rate : '—'}` },
    { label: 'SLASH', value: faults, sub: faults ? '信用已被扣減' : '尚未發生', cls: faults ? 'bad' : '' },
    { label: '互審', value: c.REVIEW || 0, sub: `每筆 K=${state.sys ? state.sys.k_reviewers : '—'}` },
  ];
  $('#tiles').innerHTML = tiles.map((t) => `
    <div class="tile ${t.cls || ''}">
      <div class="label">${esc(t.label)}</div>
      <div class="value">${esc(t.value)}</div>
      <div class="sub">${esc(t.sub)}</div>
    </div>`).join('');
}

function renderIdentities() {
  $('#nav-ids').textContent = state.ids.length;
  $('#id-rows').innerHTML = state.ids.map((i) => `
    <tr class="clickable" data-id="${esc(i.vacant_id)}">
      <td>
        <div style="font-weight:500">${esc(i.name)}</div>
        <div style="font-size:0.72rem">${hash(i.vacant_id, 8, 6)}</div>
      </td>
      <td>
        <div style="font-size:0.72rem">${hash(i.stream_id, 8, 6)}</div>
        <div style="margin-top:3px">${i.genesis_proven
          ? '<span class="badge ok">擁有權已證明</span>'
          : '<span class="badge idle">先占（未附證明）</span>'}</div>
      </td>
      <td style="min-width:150px">
        ${meter(i.credit)}
        ${(i.n_obs === 0 && (i.other_substrates || []).length)
          ? `<div style="font-size:0.68rem;color:var(--warn);margin-top:3px">
               此 substrate 尚無觀測；另有 ${i.other_substrates.length} 個 substrate 有紀錄</div>`
          : ''}
      </td>
      <td class="num">${Number(i.n_obs).toFixed(1)}</td>
      <td class="num">${i.deliveries}</td>
      <td class="num">${i.episodes}</td>
      <td>${flagBadges(i.flags, i.probation)}</td>
    </tr>`).join('') || '<tr><td colspan="7" class="empty">尚無身份</td></tr>';
}

function renderActivity() {
  $('#nav-acts').textContent = state.acts.length;
  $('#act-rows').innerHTML = state.acts.map((a) => `
    <tr class="clickable" data-task="${esc(a.task_id)}">
      <td class="mono" style="color:var(--ink-3)">${esc(clock(a.ts_ms))}</td>
      <td>${hash(a.task_id, 6, 4)}</td>
      <td>${esc(a.deliverer || '—')}</td>
      <td class="mono">${a.reviews_total
        ? `${a.reviews_pass}/${a.reviews_total} <span style="color:var(--ink-3)">w=${a.review_weight}</span>`
        : '<span style="color:var(--ink-3)">未互審</span>'}</td>
      <td>${a.audit_performed ? tri(a.audit_passed) : tri(null)}</td>
      <td>${a.retro_audit ? tri(a.retro_audit.passed, ['已回溯通過', '回溯未通過', '—'])
        : '<span class="tri none"><i class="mark"></i>待回溯</span>'}</td>
      <td>${hash(a.chain_head, 6, 4)}</td>
    </tr>`).join('') || '<tr><td colspan="7" class="empty">尚無交付紀錄</td></tr>';
}

function renderChain() {
  const g = state.integrity;
  if (!g) return;
  $('#chain-rows').innerHTML = (g.chains || []).map((c) => `
    <tr>
      <td>${esc(c.name)}</td>
      <td>${c.chain_ok ? '<span class="badge ok">簽章鏈可驗</span>' : '<span class="badge bad">驗鏈失敗</span>'}</td>
      <td class="num">${c.len}</td>
      <td>${hash(c.head, 8, 6)}</td>
    </tr>`).join('') || '<tr><td colspan="4" class="empty">—</td></tr>';
  $('#ledger-kv').innerHTML = `
    <dt>事件數</dt><dd>${g.ledger_seq}</dd>
    <dt>滾動雜湊</dt><dd>${hash(g.ledger_head, 12, 8)}</dd>
    <dt>全部鏈可驗</dt><dd>${g.all_chains_ok ? '是' : '否'}</dd>`;
}

function renderScoreboard() {
  const sb = state.sb;
  if (!sb) { $('#scoreboard').innerHTML = '<div class="empty">尚無資料</div>'; return; }
  const row = (k, d) => `
    <div class="dim-row">
      <span class="k">${k}</span>
      ${d.n ? meter(d.pass / d.n) : '<span style="color:var(--ink-3);font-size:0.78rem">尚無試次</span>'}
      <span class="obs">${d.pass}/${d.n}</span>
    </div>`;
  const delta = sb.paired_delta;
  $('#scoreboard').innerHTML = `
    <div class="dims">
      ${row('可究責層 關', sb.off)}
      ${row('可究責層 開', sb.on)}
    </div>
    <div style="margin-top:var(--s4);font-size:0.78rem;color:var(--ink-3)">
      池化差 ${delta === null || delta === undefined ? '—' : (delta > 0 ? '+' : '') + delta}
      ・呼叫數 off ${sb.off.calls} / on ${sb.on.calls}
      <br>這是兩池通過率之差，<b style="color:var(--ink-2)">不是同題配對統計</b>；
      配對檢定屬批次實驗，不在此面板宣稱。
    </div>`;
}

function renderCost() {
  const c = state.cost;
  const box = $('#cost');
  if (!c) { box.innerHTML = '<div class="empty">尚無成本資料</div>'; return; }
  const row = (k, d) => `
    <tr>
      <td>${k}</td>
      <td class="num">${d.deliveries}</td>
      <td class="num">${d.passed}</td>
      <td class="num">${d.calls}</td>
      <td class="num">${d.calls_per_delivery ?? '—'}</td>
      <td class="num">${d.calls_per_pass ?? '—'}</td>
    </tr>`;
  box.innerHTML = `
    <table>
      <thead><tr>
        <th>臂</th><th class="num">交付</th><th class="num">通過</th>
        <th class="num">呼叫</th><th class="num">呼叫/交付</th><th class="num">呼叫/通過</th>
      </tr></thead>
      <tbody>${row('可究責層 開', c.on)}${row('可究責層 關', c.off)}</tbody>
    </table>
    <div style="padding:var(--s3) var(--s4);font-size:0.76rem;color:var(--ink-3);
                border-top:1px solid var(--line)">
      可究責層不是免費的：互審與稽核都要花呼叫。
      <b style="color:var(--ink-2)">呼叫／通過</b>是「單位成本品質」的可觀測代理量——
      要主張可究責層有價值，這一欄必須跟品質一起看，不能只報品質。
    </div>`;
}

function renderSys() {
  const s = state.sys;
  if (!s) return;
  const pairs = [
    ['root', s.root], ['模式', s.root_mode || '—'], ['基座', s.brain],
    ['substrate', s.substrate], ['互審 K', s.k_reviewers], ['互審模式', s.review_mode],
    ['稽核抽樣率', s.audit_rate], ['見習門檻 m', s.probation_m], ['記憶預算 B', s.b_memory],
  ];
  $('#sysinfo').innerHTML = pairs.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('');
  $('#foot-root').textContent = String(s.root).split('/').slice(-2).join('/');
  $('#foot-ver').textContent = `${s.n_identities} 身份 · ${s.substrate}`;
  $('#chip-trust').innerHTML = `可究責層 <b>${s.trust_on ? '開' : '關'}</b>`;
  $('#chip-trust').className = 'chip' + (s.trust_on ? ' on' : '');
}

function renderTop() {
  const g = state.integrity;
  if (!g) return;
  $('#chip-chain').innerHTML = `chain <b>${g.all_chains_ok ? 'OK' : 'FAIL'}</b>`;
  $('#chip-chain').className = 'chip ' + (g.all_chains_ok ? 'ok' : 'bad');
  $('#chip-head').innerHTML = `head ${hash(g.ledger_head, 6, 4)}`;
}

/* ── 宣稱階梯：這一頁的內容由後端給，不由前端寫死 ───────────── */
function renderLadder(rungs) {
  $('#ladder').innerHTML = (rungs || []).map((r) => `
    <div class="rung ${r.met ? 'pass' : 'blocked'}">
      <div class="step">${esc(r.step)}</div>
      <div>
        <div class="claim">${esc(r.claim)}</div>
        <div class="ev-note">${esc(r.evidence)}</div>
      </div>
      <div>${r.met ? '<span class="badge ok">已達</span>' : '<span class="badge idle">未達</span>'}</div>
    </div>`).join('');
}

/* ── 事件流 ─────────────────────────────────────────────── */
/* 暫停鍵是必要的：事件持續湧入時，人正在讀的那一行會被推走。
   暫停時新事件進緩衝區並顯示計數，恢復後一次補上。 */
const MAX_EVENTS = 300;
let paused = false;
const buffer = [];

function evNode(ev) {
  const d = document.createElement('div');
  d.className = `ev ${esc(ev.type || '')}`;
  const detail = [];
  for (const [k, v] of Object.entries(ev)) {
    if (['type', 'ts_ms', 'seq'].includes(k)) continue;
    detail.push(`${k}=${typeof v === 'object' ? JSON.stringify(v) : v}`);
  }
  d.innerHTML = `<span class="t">${esc(clock(ev.ts_ms))}</span>
    <span class="ty">${esc(ev.type || '?')}</span>
    <span class="d">${esc(detail.join(' '))}</span>`;
  return d;
}

function pushEvent(ev) {
  if (paused) {
    buffer.push(ev);
    if (buffer.length > MAX_EVENTS) buffer.shift();
    $('#pending').textContent = `${buffer.length} 筆新事件`;
    $('#pending').hidden = false;
    return;
  }
  const box = $('#stream');
  box.prepend(evNode(ev));
  while (box.childElementCount > MAX_EVENTS) box.lastElementChild.remove();
}

function togglePause() {
  paused = !paused;
  $('#pause').textContent = paused ? '▶ 繼續' : '❚❚ 暫停';
  $('#pause').classList.toggle('active', paused);
  if (!paused) {
    const box = $('#stream');
    while (buffer.length) box.prepend(evNode(buffer.shift()));
    while (box.childElementCount > MAX_EVENTS) box.lastElementChild.remove();
    $('#pending').hidden = true;
  }
}
$('#pause').addEventListener('click', togglePause);

/* ── 身份詳情抽屜 ───────────────────────────────────────── */
async function openIdentity(vid) {
  const d = await api(`/api/identity?id=${encodeURIComponent(vid)}`);
  if (!d) return;
  $('#dw-title').textContent = d.name;
  $('#dw-badges').innerHTML =
    (d.chain_ok ? '<span class="badge ok">簽章鏈可驗</span>' : '<span class="badge bad">驗鏈失敗</span>') +
    (d.genesis_proven ? '<span class="badge ok">擁有權已證明</span>' : '<span class="badge idle">擁有權先占</span>') +
    (d.probation ? '<span class="badge warn">見習中</span>' : '');

  const dims = Object.entries(d.dims || {}).map(([k, v]) => `
    <div class="dim-row">
      <span class="k">${esc(k)}</span>${meter(v)}
      <span class="obs">n=${(d.dim_obs || {})[k] ?? '—'}</span>
    </div>`).join('');

  const entries = (d.entries || []).slice().reverse().slice(0, 40).map((e) => `
    <div class="ev">
      <span class="t">#${e.seq}</span>
      <span class="ty">${esc(e.type)}</span>
      <span class="d">${hash(e.hash, 8, 6)}</span>
    </div>`).join('') || '<div class="empty">鏈上尚無事件</div>';

  const ckpts = (d.checkpoint_chain || []).map((c) => `
    <div class="ev">
      <span class="t">#${c.seq}</span>
      <span class="ty">CKPT</span>
      <span class="d">window ${JSON.stringify(c.window)} · 回溯 ${Object.keys(c.retro_audits || {}).length} 筆 · 缺料 ${(c.retro_missing || []).length}</span>
    </div>`).join('') || '<div class="empty">尚未簽發存檔點</div>';

  $('#dw-body').innerHTML = `
    <div class="sec">
      <div class="sec-head"><h2>密碼學身份</h2></div>
      <dl class="kv">
        <dt>vacant_id</dt><dd>${esc(d.vacant_id)}</dd>
        <dt>記憶鏈 stream</dt><dd>${esc(d.stream_id)}</dd>
        <dt>branch</dt><dd>${esc(d.branch_id)}</dd>
        <dt>鏈頭</dt><dd>${esc(d.chain_head)}</dd>
        <dt>鏈長度</dt><dd>${d.chain_len}</dd>
      </dl>
    </div>
    <div class="sec">
      <div class="sec-head"><h2>五維信用</h2>
        <span class="note">credit ${Number(d.credit).toFixed(3)} · 有效觀測 ${Number(d.n_obs).toFixed(1)}</span></div>
      <div class="card"><div class="card-body"><div class="dims">${dims}</div></div></div>
    </div>
    <div class="sec">
      <div class="sec-head"><h2>它的記憶鏈</h2><span class="note">最近 40 筆</span></div>
      <div class="card"><div class="stream">${entries}</div></div>
    </div>
    <div class="sec">
      <div class="sec-head"><h2>存檔點鏈</h2></div>
      <div class="card"><div class="stream">${ckpts}</div></div>
    </div>`;
  $('#drawer').classList.add('open');
  $('#scrim').classList.add('open');
}
/** 交付憑據本體：這是「做了什麼」的最終證物，介面必須讓人看得到全文。
 *  卡上的每個欄位都能被第三方獨立重驗（簽章、公鑰、鏈頭都存全文）。 */
async function openTask(taskId) {
  const card = await api(`/api/task?id=${encodeURIComponent(taskId)}`);
  if (!card) return;
  const d = card.deliverer || {};
  const audit = card.audit || {};
  const reviews = card.reviews || [];

  $('#dw-title').textContent = `交付 ${String(taskId).slice(0, 10)}`;
  $('#dw-badges').innerHTML =
    (card.trust_on ? '<span class="badge ok">可究責層 開</span>'
                   : '<span class="badge idle">可究責層 關</span>') +
    (audit.performed
      ? (audit.passed ? '<span class="badge ok">稽核通過</span>'
                      : '<span class="badge bad">稽核未通過</span>')
      : '<span class="badge idle">未稽核</span>') +
    (card.retro_audit ? '<span class="badge ok">已回溯</span>'
                      : '<span class="badge idle">待回溯</span>');

  const reviewRows = reviews.map((r) => `
    <div class="ev">
      <span class="t">${esc(String(r.reviewer || '').slice(0, 8))}</span>
      <span class="ty" style="color:${r.verdict === 'PASS' ? 'var(--ok)' : 'var(--bad)'}">
        ${esc(r.verdict || '?')}</span>
      <span class="d">weight ${esc(r.weight)} · sig ${esc(String(r.sig || '').slice(0, 12))}…</span>
    </div>`).join('') || '<div class="empty">未互審（可究責層關閉時不互審）</div>';

  const flags = (d.credit && d.credit.flags) || [];
  $('#dw-body').innerHTML = `
    <div class="sec">
      <div class="sec-head"><h2>交付者</h2></div>
      <dl class="kv">
        <dt>名稱</dt><dd>${esc(d.name)}</dd>
        <dt>vacant_id</dt><dd>${esc(d.vacant_id)}</dd>
        <dt>記憶鏈</dt><dd>${esc(d.stream_id)}</dd>
        <dt>交付時信用</dt><dd>${esc((d.credit || {}).score)} · n=${esc((d.credit || {}).n_obs)}</dd>
        <dt>風險欄</dt><dd>${flags.length ? flags.map(esc).join('、') : '無旗標'}</dd>
      </dl>
      <div style="margin-top:var(--s3);font-size:0.76rem;color:var(--ink-3)">
        風險欄是被斷言的內容，不是可省略的欄位——沒有旗標時會明說「無旗標」，
        而不是留白。
      </div>
    </div>
    <div class="sec">
      <div class="sec-head"><h2>同儕互審</h2>
        <span class="note">每筆都是簽章物件，可獨立重驗</span></div>
      <div class="card"><div class="stream">${reviewRows}</div></div>
    </div>
    <div class="sec">
      <div class="sec-head"><h2>稽核</h2>
        <span class="note">沙箱重跑客觀檢查，非再問一次模型</span></div>
      <div class="card"><div class="card-body">
        ${audit.performed
          ? tri(audit.passed)
          : '<span class="tri none"><i class="mark"></i>本件未被抽中稽核</span>'}
        ${card.retro_audit
          ? `<div style="margin-top:var(--s3);font-size:0.78rem;color:var(--ink-2)">
               存檔點 #${esc(card.retro_audit.checkpoint_seq)} 回溯：
               ${card.retro_audit.passed ? '通過' : '未通過'}</div>`
          : `<div style="margin-top:var(--s3);font-size:0.78rem;color:var(--ink-3)">
               尚未回溯稽核（此欄恆在，「仍待回溯」是被斷言的，不是被省略的）</div>`}
      </div></div>
    </div>
    <div class="sec">
      <div class="sec-head"><h2>鏈錨</h2></div>
      <dl class="kv">
        <dt>交付時鏈頭</dt><dd>${esc(card.chain_head)}</dd>
        <dt>spec digest</dt><dd>${esc(card.spec_digest)}</dd>
        <dt>簽章</dt><dd style="word-break:break-all">${esc(String(card.host_sig || '').slice(0, 96))}…</dd>
      </dl>
    </div>`;
  $('#drawer').classList.add('open');
  $('#scrim').classList.add('open');
}
$('#act-rows').addEventListener('click', (e) => {
  const tr = e.target.closest('tr[data-task]');
  if (tr && !e.target.closest('.hash')) openTask(tr.dataset.task);
});

function closeDrawer() {
  $('#drawer').classList.remove('open');
  $('#scrim').classList.remove('open');
}
$('#dw-close').addEventListener('click', closeDrawer);
$('#scrim').addEventListener('click', closeDrawer);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawer(); });
$('#id-rows').addEventListener('click', (e) => {
  const tr = e.target.closest('tr[data-id]');
  if (tr) openIdentity(tr.dataset.id);
});

/* ── 載入與即時更新 ─────────────────────────────────────── */
async function refresh() {
  try {
    const s = await api('/api/state');
    state.sys = s.system; state.ids = s.identities; state.acts = s.activity;
    state.integrity = s.integrity; state.sb = s.scoreboard; state.counters = s.counters;
    state.cost = s.cost;
    renderSys(); renderTop(); renderTiles(); renderIdentities();
    renderActivity(); renderChain(); renderScoreboard(); renderCost();
    renderLadder(s.claim_ladder);
  } catch (err) {
    setLive('err', '取數失敗');
  }
}

function setLive(cls, txt) {
  $('#live').className = `live ${cls}`;
  $('#live-txt').textContent = txt;
}

let pending = null;
function scheduleRefresh() {
  if (pending) return;
  pending = setTimeout(() => { pending = null; refresh(); }, 350);
}

function connect() {
  const es = new EventSource('/events');
  es.onopen = () => setLive('on', '即時連線');
  es.onmessage = (m) => {
    try { pushEvent(JSON.parse(m.data)); } catch { /* 非 JSON 行：略過 */ }
    scheduleRefresh();
  };
  es.onerror = () => {
    setLive('err', '連線中斷，重試中');
    es.close();
    setTimeout(connect, 3000);
  };
}

show((location.hash || '#overview').slice(1));
refresh();
/* ?nolive=1 關閉即時連線：截圖／端到端測試需要頁面能「結束載入」，
   而 SSE 是永不結束的連線。正常使用一律走即時模式。 */
if (!new URLSearchParams(location.search).has('nolive')) {
  connect();
  setInterval(refresh, 15000);  // 保底輪詢：SSE 斷線時面板仍會更新
} else {
  setLive('', '靜態模式');
}
