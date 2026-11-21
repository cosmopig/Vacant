/* 離線、無追蹤；交件紀錄不替人裁定答案。 */
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
  const pct = x => `${Math.round(x * 100)}%`;
  const reasonZH = p => {
    if(p.kind==='consistently')return '期間是否一貫，需要領域語意判讀，未自動裁定。';
    if(p.status==='UNCHECKABLE')return '紀錄不足以支持或反駁這句話；保留未核對。';
    if(p.kind==='file_read')return p.status==='SUPPORTED'?'成功讀取型指令具名提及檔案（不等於讀懂）。':'未見成功的具名直接讀取；可能漏掉間接腳本。';
    if(p.kind==='quantity')return p.status==='SUPPORTED'?'各數值出現在工具輸出；未核對語意。':'有數值未精確匹配輸出；四捨五入也可能被誤標。';
    if(p.kind==='verified')return p.status==='SUPPORTED'?'答案出現後，不同指令再次輸出答案；僅為獨立核對代理。':'只有至多一道不同計算指令，未見第二道核對。';
    return p.status==='SUPPORTED'?'紀錄有符合的成功指令代理；尚未核對完整算法／測試覆蓋。':'未見符合的成功指令，需人工核對。';
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
  function intro() {
    app.innerHTML = `<div class="eyebrow">一個關於交付的選擇</div><h1>AI 說它做完了。<br>你收不收？</h1><p class="lead">同一份答案，多一份過程紀錄，會改變你的判斷嗎？</p><div class="card"><h3>8 回合，兩種視角</h3><p>4 回合只看 agent 說的；4 回合加看 Vacant 紀錄。請決定收下或退回，並選擇把握程度。每回合後揭曉題庫評分。</p><small>約 5–10 分鐘。參與自願，可隨時關閉；回答只留在這台裝置。只有你主動匯出才會產生結果檔，沒有上傳。</small></div><p><span class="pill">真實歸檔資料</span></p><p class="muted">DABstep、pi＋本地模型、2026-09-25；對錯由題庫評分器判定。</p><small>原始題目與 agent 訊息保留英文。題目經挑選，並非一般任務的失敗率。紀錄只是短摘錄，不是完整資料集。</small><button class="primary full" id="start">我願意參與，開始 8 回合 →</button>${state?'<button class="full" id="resume">繼續這台裝置上的進度</button>':''}<footer>讓依賴有根據，而不是讓紀錄替你決定。</footer>`;
    document.querySelector('#start').onclick = () => { if (!state || confirm('開始新一輪會取代本機舊進度。尚未匯出的結果會遺失，確定嗎？')) start(); };
    if (state) document.querySelector('#resume').onclick = render;
  }
  const icons = {bash:'⌘',read:'▤',write:'✎',edit:'↔'};
  function record(c) {
    const origin = c.answer_source ? `答案「${esc(c.answer)}」第一次出現在第 ${c.answer_source} 步的輸出` : '紀錄裡沒有任何一步的輸出出現這個答案';
    return `<section aria-label="Vacant 紀錄"><h2>把說法放回過程裡</h2><div class="notice ${c.answer_source?'source':''}">${origin}<br><small>依凍結值重疊規則：只比對合條件 shell 輸出，排除答案檔讀回；不是正確性或因果來源判定。</small></div><p class="muted">以下是原始紀錄短摘錄。點每一步展開；指令最多 200 字、輸出最多 300 字。檔案標籤為具名讀取代理。</p><div class="timeline">${c.steps.map(s=>`<details class="step ${s.step===c.answer_source?'origin':''}"><summary><b>${icons[s.tool]||'·'}</b>第 ${s.step} 步 · ${esc(s.tool)}<small>${s.error?'工具錯誤':'展開'}</small></summary>${s.files_read.map(f=>`<span class="chip">${esc(f)}</span>`).join('')}<pre>${esc(s.command||'（無指令文字）')}</pre><pre>${esc(s.output||'（無輸出文字）')}</pre></details>`).join('')}</div>${c.process_claims.length?`<details class="card claims"><summary>agent 的流程說法 ↔ 紀錄線索</summary><p>規則候選，尚非事實裁決；舊版人工保留 6/20，修正後尚未重估。</p>${c.process_claims.map(p=>`<blockquote>${esc(p.text)}</blockquote><p>紀錄規則：${esc(reasonZH(p))}${p.steps.length?`（第 ${p.steps.join('、')} 步）`:''}</p>`).join('')}${c.manual_note?`<p><b>${esc(c.manual_note)}</b></p>`:''}</details>`:''}<details class="card"><summary>原始交件說明 delivery.md</summary><pre class="receipt">${esc(c.delivery_lines.join('\n'))}</pre></details></section>`;
  }
  function round() {
    const i = state.responses.length, r = state.rounds[i], c = data.cases.find(c=>c.id===r.case_id);
    app.innerHTML = `<span class="pill ${r.condition==='plain'?'plain':''}">${conditionName(r.condition)}</span><div class="card"><span class="eyebrow">任務問題 · ${i+1} / 8</span><h2>${esc(c.question)}</h2><small>你不需要重做整份資料分析；請依目前可見資訊決定是否收下。</small></div><div class="eyebrow">AGENT 的交件訊息</div><div class="bubble"><p>${esc(c.message)}</p><span class="answer">交付答案　<mark>${esc(c.answer)}</mark></span></div>${r.condition==='record'?record(c):'<p class="muted">這回合不提供過程紀錄。請只依交件訊息判斷。</p>'}<form class="decision"><h3>這份交件，你收不收？</h3><div class="choices"><button type="button" data-choice="accept" aria-pressed="false">收下</button><button type="button" data-choice="reject" aria-pressed="false">退回</button></div><label for="confidence">你的把握程度 <b id="confidence-value">75%</b></label><input id="confidence" type="range" min="50" max="100" step="1" value="75"><small>50%＝像猜的，100%＝非常確定</small><button class="primary full" id="submit" disabled>送出判斷 →</button></form>`;
    let decision = null;
    document.querySelectorAll('[data-choice]').forEach(b=>b.onclick=()=>{decision=b.dataset.choice;document.querySelectorAll('[data-choice]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));document.querySelector('#submit').disabled=false;});
    document.querySelector('#confidence').oninput=e=>document.querySelector('#confidence-value').textContent=`${e.target.value}%`;
    document.querySelector('form').onsubmit=e=>{
      e.preventDefault(); if (!decision || state.phase!=='round') return;
      state.responses.push({case_id:c.id,condition:r.condition,decision,confidence:Number(document.querySelector('#confidence').value),time_ms:Math.max(0,Date.now()-state.active_start),reward:c.reward,correct:(decision==='accept')===(c.reward===1)});
      state.phase='reveal';save();render();
    };
  }
  function reveal() {
    const r=state.responses.at(-1), c=data.cases.find(c=>c.id===r.case_id);
    app.innerHTML=`<div class="eyebrow">第 ${state.responses.length} 回合揭曉</div><div class="reveal-icon">${r.correct?'✓':'↗'}</div><h1>${r.correct?'這次判斷正確。':'這次可以再想想。'}</h1><div class="card"><span class="pill">題庫評分：${r.reward?'答案正確':'答案錯誤'}</span><p>你選擇${r.decision==='accept'?'收下':'退回'}，把握 ${r.confidence}%。</p><p>${c.answer_source?`紀錄中第 ${c.answer_source} 步的合條件輸出出現答案；出現過仍可能算錯或誤解題意。`:'合條件輸出未出現答案；缺席也不等於答案錯誤。'}</p></div><small>本回合以題庫評分為準，不是 Vacant 對成果的獨立驗收。</small><button class="primary full" id="next">${state.responses.length===8?'看看我的結果':'下一回合'} →</button>`;
    document.querySelector('#next').onclick=()=>{state.phase=state.responses.length===8?'end':'round';state.active_start=Date.now();if(state.phase==='end')state.completed_at=new Date().toISOString();save();render();};
  }
  function bar(name,value,label,cls='') {return `<div class="chart-label"><span>${name}</span><b>${label}</b></div><div class="bar-track"><div class="bar-fill ${cls}" style="width:${value*100}%"></div></div>`;}
  function end() {
    const rs=state.responses, stats=condition=>{const rows=rs.filter(r=>r.condition===condition);return {accuracy:rows.filter(r=>r.correct).length/4,wrong:rows.filter(r=>!r.reward&&r.decision==='accept').length};};
    const a=stats('record'), b=stats('plain'), maxTime=Math.max(...rs.map(r=>r.time_ms),1);
    app.innerHTML=`<div class="eyebrow">8 回合完成 · 你的單人結果</div><h1>多一份紀錄，<br>你改變了多少？</h1><p>這是可究責性的一小步：讓依賴有根據，並看見自己的判斷。</p><section class="card"><h3>判斷正確率</h3>${bar('加看紀錄',a.accuracy,`${a.accuracy*4}/4 · ${pct(a.accuracy)}`)}${bar('只看說法',b.accuracy,`${b.accuracy*4}/4 · ${pct(b.accuracy)}`,'without')}</section><section class="card"><h3>收下了多少錯誤交件？</h3><small>過度依賴：每組各遇到 2 份錯誤交件；越少越好。</small>${bar('加看紀錄',a.wrong/2,`${a.wrong}/2`,'wrong')}${bar('只看說法',b.wrong/2,`${b.wrong}/2`,'wrong')}</section><section class="card"><h3>把握程度 vs 實際正確率</h3>${[[50,69],[70,89],[90,100]].map(([lo,hi])=>{const rows=rs.filter(r=>r.confidence>=lo&&r.confidence<=hi);return rows.length?bar(`把握 ${lo}–${hi}%`,rows.filter(r=>r.correct).length/rows.length,`${rows.filter(r=>r.correct).length}/${rows.length} 正確`):`<p class="muted">把握 ${lo}–${hi}%：無回答</p>`;}).join('')}</section><section class="card"><h3>每回合花的時間</h3><div class="time-chart" role="img" aria-label="各回合秒數：${rs.map(r=>Math.round(r.time_ms/1000)).join('、')}">${rs.map((r,i)=>`<div class="time-col ${r.condition==='plain'?'without':''}" style="height:${Math.max(3,r.time_ms/maxTime*100)}%" title="${Math.round(r.time_ms/1000)} 秒"><span>${i+1}</span></div>`).join('')}</div><p class="time-label">綠＝加看紀錄；灰＝只看說法。每回合含停留／離開頁面的時間。</p><p>${rs.map((r,i)=>`${i+1}：${(r.time_ms/1000).toFixed(1)} 秒`).join(' ／ ')}</p></section><div class="notice">n 很小，這只是你一個人的結果，不代表一般人或真實任務的效果。每回合揭曉可能影響後續判斷；題目經刻意平衡，不能推算真實失敗率。</div><h2>把結果帶走</h2><p class="muted">匯出包含隨機種子、案例 ID、判斷、把握、時間與評分；不含姓名。分享前請先看內容。</p><div class="actions"><button id="copy">複製結果</button><button id="download" class="primary">下載 JSON</button></div><details><summary>檢視／手動複製 JSON</summary><textarea readonly aria-label="匯出結果 JSON">${esc(exportJSON())}</textarea></details><p id="status" role="status"></p><button class="full" id="restart">清除本機結果，重新開始</button>`;
    document.querySelector('#copy').onclick=async()=>{try{await navigator.clipboard.writeText(exportJSON());document.querySelector('#status').textContent='已複製。';}catch(_){document.querySelector('details:last-of-type').open=true;const t=document.querySelector('textarea');t.select();document.querySelector('#status').textContent='瀏覽器不允許自動複製，請手動複製上方 JSON。';}};
    document.querySelector('#download').onclick=()=>{const url=URL.createObjectURL(new Blob([exportJSON()],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=`reliance-${state.participant_id}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
    document.querySelector('#restart').onclick=()=>{if(confirm('已匯出了嗎？清除後無法復原。')){try{localStorage.removeItem(key);}catch(_){}state=null;intro();window.scrollTo(0,0);}};
  }
  function exportJSON() { return JSON.stringify({...state,storage_persisted:storageOK,study_label:'exploratory-single-person',responses:state.responses},null,2); }
  function render() {
    document.querySelector('#progress').textContent=state.phase==='end'?'8 / 8 完成':`${Math.min(state.responses.length+(state.phase==='round'?1:0),8)} / 8`;
    if(state.phase==='round')round();else if(state.phase==='reveal')reveal();else end();
    if(!storageOK)app.insertAdjacentHTML('afterbegin','<div class="notice">瀏覽器無法儲存；關閉或重新載入會遺失進度，完成後請立即匯出。</div>');
    window.scrollTo(0,0);
  }
  intro();
})();
