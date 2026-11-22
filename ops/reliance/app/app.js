/* 離線、無追蹤；動畫呈現紀錄比對，不替人裁定答案。 */
(() => {
  'use strict';
  const data = window.RELIANCE_CASES;
  const app = document.querySelector('#app');
  const key = 'vacant-reliance-study-v1';
  let state = null;
  let storageOK = true;
  try { state = JSON.parse(localStorage.getItem(key)); } catch (_) { storageOK = false; }
  if (state && (state.schema_version !== 1 || state.case_version !== data.version)) state = null;
  const esc = x => String(x).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const conditionName = x => x === 'record' ? '加看 Vacant 紀錄' : '只看 agent 說的';
  const paths = {
    doc:'M6 3h8l4 4v14H6z M14 3v5h4 M9 12h6 M9 16h5',
    bash:'M3 5h18v14H3z M7 9l3 3-3 3 M13 15h4',
    write:'m5 16 10-11 4 4L8 20l-5 1z M13 7l4 4',
    eye:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
    chat:'M3 4h18v13H9l-6 4z M7 9h10 M7 13h6',
    check:'m5 12 4 4L19 6', back:'m9 5-6 6 6 6 M3 11h11a6 6 0 0 1 6 6v3',
    cross:'m6 6 12 12 M18 6 6 18',
    robot:'M5 7h14v13H5z M12 3v4 M9 12h.1 M15 12h.1 M9 16h6 M2 11v5 M22 11v5',
    arrow:'M4 12h16 M14 6l6 6-6 6', search:'m16 16 5 5 M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0'
  };
  const icon = name => `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] || paths.doc}"/></svg>`;
  const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const reasonZH = p => {
    if(p.kind==='consistently')return '期間是否一貫，需要領域語意判讀，未自動裁定。';
    if(p.status==='UNCHECKABLE')return '紀錄不足以支持或反駁這句話；保留未核對。';
    if(p.kind==='file_read')return p.status==='SUPPORTED'?'成功讀取型指令具名提及檔案，不等於讀懂。':'未見成功的具名直接讀取；可能漏掉間接腳本。';
    if(p.kind==='quantity')return p.status==='SUPPORTED'?'各數值出現在工具輸出；未核對語意。':'有數值未精確匹配輸出；四捨五入也可能被誤標。';
    if(p.kind==='verified')return p.status==='SUPPORTED'?'答案出現後，不同指令再次輸出答案；僅為獨立核對代理。':'至多一道不同計算指令，未見第二道核對。';
    return p.status==='SUPPORTED'?'紀錄有符合的成功指令代理；未核對完整算法或測試覆蓋。':'未見符合的成功指令，需人工核對。';
  };
  function rng(seed) {
    return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t ^= t + Math.imul(t ^ t >>> 7, 61 | t); return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  }
  function shuffle(items, rand) { const a = [...items]; for (let i=a.length-1;i>0;i--) { const j=Math.floor(rand()*(i+1)); [a[i],a[j]]=[a[j],a[i]]; } return a; }
  function assignment(seed) {
    const rand = rng(seed), rounds = [];
    for (const reward of [0,1]) {
      shuffle(data.cases.filter(c => c.reward === reward), rand).slice(0,4).forEach((c,i) => rounds.push({case_id:c.id,condition:i<2?'record':'plain'}));
    }
    return shuffle(rounds,rand);
  }
  function save() { try { localStorage.setItem(key,JSON.stringify(state)); } catch (_) { storageOK=false; } }
  function start() {
    const seed = crypto.getRandomValues(new Uint32Array(1))[0];
    state = {schema_version:1,case_version:data.version,selection_seed:data.selection_seed,participant_id:`p-${seed.toString(16)}-${Date.now().toString(36)}`,seed,started_at:new Date().toISOString(),phase:'round',rounds:assignment(seed),responses:[],active_start:Date.now()};
    save(); render();
  }
  function progress(fresh=false) {
    const n = fresh ? 0 : state.responses.length;
    const current = !fresh && state.phase==='round' ? n : -1;
    const el = document.querySelector('#progress');
    el.innerHTML = Array.from({length:8},(_,i)=>`<span class="dot ${i<n?'done':''} ${i===current?'current':''}"></span>`).join('');
    el.setAttribute('aria-label',fresh?'8 回合，尚未開始':state.phase==='end'?'8 / 8 完成':`第 ${Math.min(n+(state.phase==='round'?1:0),8)} 回合，共 8 回合`);
  }
  function sheet(title, html) {
    const dialog = document.querySelector('#sheet');
    document.querySelector('#sheet-title').textContent = title;
    document.querySelector('#sheet-body').innerHTML = html;
    if (!dialog.open) dialog.showModal();
    dialog.scrollTop = 0;
  }
  const infoButton = (name, id) => `<button class="info" id="${id}" aria-label="${name}">ⓘ</button>`;
  function intro() {
    progress(true);
    app.innerHTML = `<section class="intro"><span class="archive-badge"><i></i>真實歸檔資料</span><div class="hero" role="img" aria-label="AI 帶著交件說做完了；由你選擇收下或退回"><div class="hero-orbit"></div><div class="hero-agent"><div class="hero-speech">做完了！<span>✦</span></div><div class="avatar">${icon('robot')}</div><div class="hero-paper">${icon('doc')}<i></i><i></i><b>✓</b></div></div><span class="hero-stamp accept">✓ 收下</span><span class="hero-stamp reject">↩ 退回</span><span class="hero-spark one">✦</span><span class="hero-spark two">＋</span></div><h1>AI 說做完了。<br>你收不收？</h1><p class="intro-line">8 次選擇，看見多一份紀錄的差別。</p><button class="primary full" id="start">我願意參與，開始 ${icon('arrow')}</button>${state?'<button class="full secondary" id="resume">繼續這台裝置上的進度</button>':''}<button class="intro-info" id="study-info">ⓘ 參與說明・資料來源・只存本機</button></section>`;
    document.querySelector('#start').onclick = () => { if (!state || confirm('開始新一輪會取代本機舊進度。尚未匯出的結果會遺失，確定嗎？')) start(); };
    if (state) document.querySelector('#resume').onclick = render;
    document.querySelector('#study-info').onclick = () => sheet('參與前，看這裡', `<div class="info-tiles"><span>8 回合</span><span>4 只看說法</span><span>4 加看紀錄</span></div><p>參與自願，可隨時關閉。請決定收下或退回，並選擇 50–100% 把握程度；每回合後揭曉題庫評分。</p><h3>只留在這台裝置</h3><p>約 5–10 分鐘。沒有上傳或追蹤；只有主動匯出才會產生結果檔。未匯出前清除瀏覽器資料會遺失回答。</p><h3>真實歸檔資料</h3><p>真實歸檔資料（DABstep、pi＋本地模型、2026-09-25）；對錯由題庫評分器判定。</p><p>原始題目與 agent 訊息保留英文；題目經挑選，並非一般任務的失敗率。紀錄只是摘錄，數值匹配不代表答案正確。</p><p>每回合揭曉可能影響之後的判斷。這是可究責性的小實驗，不是成效裁決。</p>`);
  }
  function conditionBadge(condition) {
    return `<span class="condition ${condition}" aria-label="${conditionName(condition)}">${condition==='record'?icon('eye')+icon('doc'):icon('chat')}<span>${condition==='record'?'加看紀錄':'只看說法'}</span></span>`;
  }
  function track(c) {
    const points = c.steps.map((s,i)=>({x:34+(Math.floor(i/4)%2?3-i%4:i%4)*84,y:36+Math.floor(i/4)*76}));
    const height = Math.ceil(points.length/4)*76+20;
    const sourceIndex = c.answer_source_index ?? -1;
    const target = sourceIndex>=0?{x:points[sourceIndex].x-20,y:points[sourceIndex].y-23}:{x:160,y:height-10};
    const line = points.map(p=>`${p.x} ${p.y}`).join(' L ');
    const route = sourceIndex>=0 ? `M160 0 L310 0 L310 ${points.at(-1).y} L${points.slice(sourceIndex).reverse().map(p=>`${p.x} ${p.y}`).join(' L ')} L${target.x} ${target.y}` : `M160 0 L${line} L${target.x} ${target.y}`;
    const delay = points.length*.15+.25;
    const names = {file_read:'讀檔',computed:'計算',verified:'再核對',quantity:'數值',ran:'執行',consistently:'一貫性'};
    return `<section class="record-card" aria-label="Vacant 紀錄"><div class="section-label"><span>${icon('eye')} 過程軌跡</span><button class="text-button" id="receipt">原始收據 ↗</button></div><div class="source-marker ${sourceIndex<0?'missing':''}"><span>${sourceIndex>=0?`↳ 輸出首次匹配：第 ${c.answer_source} 步`:'⌕ 輸出未找到這個答案'}</span>${infoButton('答案匹配規則','source-info')}</div><p class="source-cue">有出處 ≠ 答對；未找到 ≠ 答錯</p><div class="process-track" style="aspect-ratio:320/${height};--arrival:${delay+1.4}s" data-source="${sourceIndex>=0?'found':'none'}"><svg class="track-lines" viewBox="0 0 320 ${height}" aria-hidden="true"><path class="rail" d="M${line}"/>${sourceIndex<0?`<path class="broken-rail" d="M${points.at(-1).x} ${points.at(-1).y} L160 ${height-10}"/>`:''}<g class="moving-token"><circle r="6"/><g class="token-value"><rect x="-70" y="-32" width="140" height="22" rx="11"/><text x="0" y="-17" text-anchor="middle" textLength="${Math.min(124,c.answer.length*5)}" lengthAdjust="spacingAndGlyphs">${esc(c.answer)}</text></g><animateMotion path="${route}" dur="1.4s" begin="${delay}s" fill="freeze"/></g><circle class="rest-token" cx="${target.x}" cy="${target.y}" r="6"/></svg>${c.steps.map((s,i)=>`<button class="node ${i===sourceIndex?'origin':''}" data-step="${i}" style="left:${points[i].x/3.2}%;top:${points[i].y/height*100}%;--delay:${i*.15}s" aria-label="第 ${s.step} 步，${s.tool}，查看指令與輸出">${icon(s.tool==='read'?'doc':s.tool)}<small>${s.step}</small>${s.files_read.length?`<span class="file-pop" aria-label="讀取 ${s.files_read.length} 個具名檔案">${icon('doc')}<b>${s.files_read.length}</b></span>`:''}</button>`).join('')}${sourceIndex<0?`<span class="broken-marker" style="top:${(height-10)/height*100}%" aria-label="輸出未找到答案，不代表答錯">${icon('search')}未找到</span>`:''}</div>${c.process_claims.length?`<div class="claim-pills" aria-label="流程主張，規則線索並非事實裁決">${c.process_claims.map((p,i)=>`<button class="claim ${p.status.toLowerCase()}" data-claim="${i}" aria-label="${names[p.kind]}：${p.status==='SUPPORTED'?'規則支持':p.status==='CONTRADICTED'?'待人工核對':'未核對'}，查看詳情"><b>${p.status==='SUPPORTED'?'✓':p.status==='CONTRADICTED'?'✗':'?'}</b>${names[p.kind]}<span>↗ ${p.steps.length?p.steps.join('·'):'?'}</span></button>`).join('')}</div>`:''}</section>`;
  }
  function stepSheet(c, index) {
    const s = c.steps[index];
    sheet(`第 ${s.step} 步 · ${s.tool}`, `${s.error?'<span class="error-label">工具回報錯誤</span>':''}<div class="file-chips">${s.files_read.map(f=>`<span>${icon('doc')}${esc(f)}</span>`).join('')}</div><h3>指令</h3><pre>${esc(s.command||'（無指令文字）')}</pre><h3>輸出摘錄</h3><pre>${esc(s.output||'（無輸出文字）')}</pre><small>指令最多 200 字，輸出最多 300 字；具名讀檔只是代理。</small>`);
  }
  function bindRecord(c) {
    document.querySelectorAll('[data-step]').forEach(b=>b.onclick=()=>stepSheet(c,Number(b.dataset.step)));
    document.querySelector('#receipt').onclick=()=>sheet('原始交件收據',`<pre>${esc(c.delivery_lines.join('\n'))}</pre>`);
    document.querySelector('#source-info').onclick=()=>sheet('匹配，不是正確性裁決', '<p>動畫只重放凍結的值重疊比對，不是新的計算或因果追溯。</p><p>數值答案要求所有數值匹配；文字答案匹配完整文字。只看成功且合條件的 bash 輸出，排除答案檔讀回與開頭 ls／find／echo。</p><p>最早匹配可能只是原始資料裡的巧合。沒有匹配也可能是缺少輸出，不代表答案錯誤。</p>');
    document.querySelectorAll('[data-claim]').forEach(b=>{
      const p=c.process_claims[Number(b.dataset.claim)];
      b.onfocus=b.onpointerenter=()=>document.querySelectorAll('[data-step]').forEach(n=>n.classList.toggle('pointed',p.steps.includes(c.steps[Number(n.dataset.step)].step)));
      b.onblur=b.onpointerleave=()=>document.querySelectorAll('.pointed').forEach(n=>n.classList.remove('pointed'));
      b.onclick=()=>{
        sheet('這句話，對照哪一步？',`<blockquote>${esc(p.text)}</blockquote><p>${esc(reasonZH(p))}</p><div class="sheet-links">${p.steps.map(s=>`<button data-evidence="${c.steps.findIndex(n=>n.step===s)}">↗ 第 ${s} 步</button>`).join('')}</div>${c.manual_note?`<p>${esc(c.manual_note)}</p>`:''}<small>規則候選，不是事實裁決；舊版人工保留 6/20，修正後尚未重估。</small>`);
        document.querySelectorAll('[data-evidence]').forEach(n=>n.onclick=()=>stepSheet(c,Number(n.dataset.evidence)));
      };
    });
  }
  function round() {
    const i = state.responses.length, r = state.rounds[i], c = data.cases.find(c=>c.id===r.case_id);
    const preview = c.message.replace(/[*`#]/g,'').trim();
    app.innerHTML = `<div class="round-content"><div class="round-top">${conditionBadge(r.condition)}<span class="round-hint">你收不收？</span></div><h2 class="question">${esc(c.question)}</h2><div class="agent-message"><div class="mini-avatar">${icon('robot')}</div><div class="bubble"><div class="message-preview">${esc(preview.slice(0,160))}${preview.length>160?'…':''}</div><div class="answer-chip"><small>交付答案</small><strong>${esc(c.answer)}</strong></div><button class="message-toggle" id="agent-full" aria-haspopup="dialog">閱讀完整交件訊息 <span>展開 ↗</span></button></div></div>${r.condition==='record'?track(c):''}</div><form class="decision"><div class="choices"><button type="button" data-choice="accept" aria-pressed="false">${icon('check')} 收下</button><button type="button" data-choice="reject" aria-pressed="false">${icon('back')} 退回</button></div><div class="confidence-meter" style="--level:50%"><label for="confidence">把握程度</label><output id="confidence-value" for="confidence">75<span>%</span></output><input id="confidence" type="range" min="50" max="100" step="1" value="75" aria-label="把握程度，50 到 100 百分比"><div class="meter-ends"><span>50 像猜的</span><span>100 很確定</span></div></div><button class="primary full" id="submit" disabled>確定 ${icon('arrow')}</button></form>`;
    document.querySelector('#agent-full').onclick=()=>sheet('agent 的完整交件訊息',`<p class="original-message">${esc(c.message)}</p>`);
    if(r.condition==='record')bindRecord(c);
    let decision = null;
    document.querySelectorAll('[data-choice]').forEach(b=>b.onclick=()=>{decision=b.dataset.choice;document.querySelectorAll('[data-choice]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));document.querySelector('#submit').disabled=false;});
    document.querySelector('#confidence').oninput=e=>{
      document.querySelector('#confidence-value').innerHTML=`${e.target.value}<span>%</span>`;
      document.querySelector('.confidence-meter').style.setProperty('--level',`${(Number(e.target.value)-50)*2}%`);
    };
    document.querySelector('form').onsubmit=e=>{
      e.preventDefault(); if (!decision || state.phase!=='round') return;
      state.responses.push({case_id:c.id,condition:r.condition,decision,confidence:Number(document.querySelector('#confidence').value),time_ms:Math.max(0,Date.now()-state.active_start),reward:c.reward,correct:(decision==='accept')===(c.reward===1)});
      state.phase='reveal';save();render();
    };
  }
  function reveal() {
    const r=state.responses.at(-1), c=data.cases.find(c=>c.id===r.case_id);
    app.innerHTML=`<section class="reveal ${r.correct?'right':'mistake'}"><div class="stamp-scene"><div class="burst">${Array.from({length:10},(_,i)=>`<i style="--i:${i}"></i>`).join('')}</div><div class="result-stamp">${icon(r.correct?'check':'cross')}<b>${r.correct?'判斷正確':'再想想'}</b></div></div><div class="verdict-pair"><div><small>你選擇</small>${icon(r.decision==='accept'?'check':'back')}<b>${r.decision==='accept'?'收下':'退回'}</b></div><span>／</span><div><small>題庫評分</small>${icon(r.reward?'check':'cross')}<b>${r.reward?'答案正確':'答案錯誤'}</b></div></div><p class="record-reveal">${c.answer_source?`↳ 輸出在第 ${c.answer_source} 步匹配答案`:'? 紀錄沒有匹配答案的輸出'}</p><small>匹配與否不裁定對錯，以題庫評分為準。</small><button class="primary full" id="next">${state.responses.length===8?'看我的結果':'下一回合'} ${icon('arrow')}</button></section>`;
    document.querySelector('#next').onclick=()=>{state.phase=state.responses.length===8?'end':'round';state.active_start=Date.now();if(state.phase==='end')state.completed_at=new Date().toISOString();save();render();};
  }
  function bar(name,value,label,cls='') {return `<div class="chart-label"><span>${name}</span><b>${label}</b></div><div class="bar-track"><div class="bar-fill ${cls}" style="width:${value*100}%"></div></div>`;}
  function confidenceChart(responses, condition) {
    const rows = responses.filter(r => r.condition === condition);
    const bins = [[50,69],[70,89],[90,100]].map(([lo,hi]) => {
      const band = rows.filter(r => r.confidence >= lo && r.confidence <= hi);
      const correct = band.filter(r => r.correct).length;
      return band.length ? bar(`${lo}–${hi}%`,correct/band.length,`${correct}/${band.length} 正確`,condition==='plain'?'without':'') : `<p class="muted empty-band">把握 ${lo}–${hi}%：無回答</p>`;
    }).join('');
    return `<section class="card confidence-card" data-confidence="${condition}">${conditionBadge(condition)}<h3>把握 vs 判斷</h3>${bins}</section>`;
  }
  function lane(condition) {
    const rows=state.responses.filter(r=>r.condition===condition), correct=rows.filter(r=>r.correct).length;
    const wrong=rows.filter(r=>!r.reward&&r.decision==='accept').length;
    return `<section class="lane ${condition}">${conditionBadge(condition)}<div class="lane-result"><strong data-count="${correct}">${correct}</strong><span>/ 4 判斷正確</span></div><div class="round-tokens">${rows.map((r,i)=>`<span class="round-token ${r.correct?'solid':'hollow'} ${!r.reward&&r.decision==='accept'?'accepted-wrong':''}" style="--delay:${i*.16}s" role="img" aria-label="第 ${state.responses.indexOf(r)+1} 回合，${r.correct?'判斷正確':!r.reward&&r.decision==='accept'?'收下錯答':'判斷錯誤'}">${icon(r.correct?'check':'cross')}</span>`).join('')}</div><div class="wrong-count"><i></i>收下錯答 <b data-count="${wrong}">${wrong}</b><span>/ 2</span></div></section>`;
  }
  function countUp() {
    if(reducedMotion() || !window.requestAnimationFrame)return;
    document.querySelectorAll('[data-count]').forEach(el=>{
      const target=Number(el.dataset.count);let start=null;
      el.textContent='0';
      function tick(time) { start ??= time; const p=Math.min((time-start)/650,1);el.textContent=String(Math.round(target*(1-(1-p)**3)));if(p<1)window.requestAnimationFrame(tick); }
      window.requestAnimationFrame(tick);
    });
  }
  function end() {
    const rs=state.responses, maxTime=Math.max(...rs.map(r=>r.time_ms),1);
    app.innerHTML=`<div class="end-heading"><span class="archive-badge">8 次選擇，完成</span><h1>多一份紀錄。<br>你的判斷呢？</h1></div><div class="comparison-lanes">${lane('record')}${lane('plain')}</div><div class="token-legend"><span>● 正確</span><span>○ 錯誤</span><span class="red">● 收下錯答</span></div><div class="confidence-panels">${confidenceChart(rs,'record')}${confidenceChart(rs,'plain')}</div><section class="card time-card"><h3>每回合的時間 <small>秒</small></h3><div class="time-chart" role="img" aria-label="各回合秒數：${rs.map(r=>Math.round(r.time_ms/1000)).join('、')}">${rs.map((r,i)=>`<div class="time-col ${r.condition==='plain'?'without':''}" style="height:${Math.max(3,r.time_ms/maxTime*100)}%;--delay:${i*.08}s" title="${(r.time_ms/1000).toFixed(1)} 秒"><span>${i+1}</span></div>`).join('')}</div><div class="time-legend"><span><i></i>加看紀錄</span><span><i class="gray"></i>只看說法</span>${infoButton('各回合秒數與時間定義','time-info')}</div></section><p class="small-caveat">n 很小，只是你一個人的結果。<br>挑題與逐題揭曉會影響判斷，不代表一般任務效果。</p><details class="export-panel"><summary>把結果帶走 ${icon('arrow')}</summary><p>只在本機。匯出含隨機種子、判斷、把握、時間與評分，不含姓名；分享前請先看內容。</p><div class="actions"><button id="copy">複製結果</button><button id="download">下載 JSON</button></div><details id="json-fallback"><summary>檢視／手動複製 JSON</summary><textarea readonly aria-label="匯出結果 JSON">${esc(exportJSON())}</textarea></details><p id="status" role="status"></p></details><button class="restart" id="restart">清除本機結果，重新開始</button>`;
    document.querySelector('#time-info').onclick=()=>sheet('每回合秒數',`<p>包含停留與離開頁面的時間。</p><div class="time-values">${rs.map((r,i)=>`<span>${i+1}<b>${(r.time_ms/1000).toFixed(1)} 秒</b></span>`).join('')}</div>`);
    document.querySelector('#copy').onclick=async()=>{try{await navigator.clipboard.writeText(exportJSON());document.querySelector('#status').textContent='已複製。';}catch(_){document.querySelector('#json-fallback').open=true;document.querySelector('textarea').select();document.querySelector('#status').textContent='請手動複製上方 JSON。';}};
    document.querySelector('#download').onclick=()=>{const url=URL.createObjectURL(new Blob([exportJSON()],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=`reliance-${state.participant_id}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
    document.querySelector('#restart').onclick=()=>{if(confirm('已匯出了嗎？清除後無法復原。')){try{localStorage.removeItem(key);}catch(_){}state=null;intro();window.scrollTo(0,0);}};
    countUp();
  }
  function exportJSON() { return JSON.stringify({...state,storage_persisted:storageOK,study_label:'exploratory-single-person',responses:state.responses},null,2); }
  function render() {
    progress();
    if(state.phase==='round')round();else if(state.phase==='reveal')reveal();else end();
    if(!storageOK)app.insertAdjacentHTML('afterbegin','<div class="storage-warning">無法儲存：請在關閉前匯出結果。</div>');
    window.scrollTo(0,0);
  }
  const dialog = document.querySelector('#sheet');
  document.querySelector('#sheet-close').onclick=()=>dialog.close();
  dialog.onclick=e=>{if(e.target===dialog)dialog.close();};
  intro();
})();
