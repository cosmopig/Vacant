# CONCLUSION 2026-11-24 — HARDJS34（rc4 `vacant do pi` 對原生 pi，gemma-4-12b QAT，1003 llama.cpp jobs 1，exercism JavaScript difficulty ≥4 的 34 題×5）

計畫：`ops/redo/plans/hardjs34_vacantdo_rc4_pi_gemma12b_1003.json`（第一通模型呼叫前 commit）；REPORT：`ops/redo/results/hardjs34_REPORT.{md,json}`（原樣複製自 run root）。

P 臂＝rc4（`redo/rc4` `652c50d36`，wheel `28e5480c…`，`~/dev/ops/rc4_dist`）；pi 不載入任何 Vacant 擴充。

**量的是 rc4（`28e5480c`），要發的是 rc6-final（`release/0.9.2-prep` tag `rc6-final`＝`b1ca9b1ff`，wheel `a575c661…`）。** rc5 相對 rc4、rc6 相對 rc5-final 的改動與政策等價的證據見 `docs/RC5_CHANGES_VS_RC4.md`。

## 0. 一句話

**EFFECTIVE**：原生 pi 124/170 → `vacant do pi` 140/170，b＝1、c＝17，精確 McNemar 雙尾 p＝0.000145；170/170 對完成、infra_void 0、放行卻錯 0。JS 產品臂在快後端上的依據就是這一批（W3-5 JS 的 Colab 確認批兩次都作廢）。

## 1. REPORT.md（原樣）

## hardjs34_vacantdo_rc4_pi_gemma12b_1003 — EFFECTIVE

計畫 sha256 `1c93d0cec8d53709…`　完成 170/170 對（有效 170，infra_void 0）　產生於 2026-11-23T05:56:43Z

| 臂 | 通過／有效格 | 比率 | 平均嘗試數 | 平均 agent 牆鐘 | 逾時次數 | 驗收放行卻錯 | 平均模型呼叫 |
|---|---|---|---|---|---|---|---|
| A | 124/170 | 0.7294 | 1.0 | 372.9s | 22 | 0 | 44.2 |
| P | 140/170 | 0.8235 | 1.0 | 400.3s | 0 | 0 | None |

**配對（A 對 P）**：只有對照過 b＝1、只有處理過 c＝17、都過 123、都沒過 29；精確 McNemar 雙尾 p＝0.000145；差 9.41 個百分點；題數上淨正 8／淨負 0。

| rep | 對數 | 對照過 | 處理過 | b | c | p |
|---|---|---|---|---|---|---|
| 1 | 34 | 25 | 30 | 1 | 6 | 0.125 |
| 2 | 34 | 26 | 28 | 0 | 2 | 0.5 |
| 3 | 34 | 26 | 29 | 0 | 3 | 0.25 |
| 4 | 34 | 23 | 26 | 0 | 3 | 0.25 |
| 5 | 34 | 24 | 27 | 0 | 3 | 0.25 |

**驗收訊號對評分器（每一次嘗試）**：放行且對 264、放行卻錯 0、擋下卻對 0、擋下且錯 76。

引用規則：只有 state=EFFECTIVE 且 harness_changed_mid_run=false 的整批數字可以引用；引用時要同時講：模型、agent、題庫、對數、等預算的定義、mean_attempts。INCOMPLETE／UNRESOLVED 不是負結果。


## 2. 可以說的句子（逐字抄自 `prereg.states.EFFECTIVE`，數字照本批填）

全部對完成（扣 infra_void）、c > b 且 p < 0.05、驗收放行卻錯＝0。可以說：「在這 34 題 JavaScript（exercism，difficulty ≥ 4，事先固定規則選出）、pi、gemma-4-12b（1003，llama.cpp 2.73.0）、同樣 1800 秒上限下，發布候選版 `vacant do pi`（rc4 0.9.2，零設定重開；pi 不載入任何 Vacant 擴充）交出通過的成果，比原生 pi 一次跑到底多（數字、P 的內層平均嘗試數、模型呼叫數一起講）」。不可以說：不帶條件的「Vacant 讓 agent 更好」、外推到別的模型／語言／沒有可執行測試的工作。

本批數字：**124/170 → 140/170（b＝1、c＝17，p＝0.000145）；P 的內層平均嘗試 1.47；平均模型呼叫 A 44.2、P 36.9（p_model_calls 補算，170/170 格可算）。**

## 3. 代價

- A：平均模型呼叫 44.2、平均 agent 牆鐘 372.9 秒、逾時 22 次。
- P：補算 170/170 格可算；平均模型呼叫 **36.9**（中位數 10.0）、平均內層嘗試 **1.47**；平均 agent 牆鐘 400.3 秒、外層逾時 0。A 的逾時多（22），P 的平均呼叫反而比 A 少——原生 pi 卡住的題一跑到底燒到 1800 秒，P 用 600 秒切掉重開。

## 4. 後端速度（`ops/redo/analysis/turn_latency.py <run root>`，本批自己的數字）

- 每輪模型回應：中位 3.4／平均 8.2／p90 18.7 秒（n＝13774；A 3.9／7.4／16.4，P 2.4／9.3／20.3）。
- P 內層撞 600 秒上限：**75/249（30.1%）**；至少一次 37/170 格、每次都撞 15 格。
- A 單次：中位牆鐘 35.7 秒、逾時 22/170。
- 並列：本機 confirm1c 每輪 5.6／11.8／21.8 秒、P 撞上限 36%；Colab 12B confirm2c 平均 46.7 秒、75%。

## 6. 已知限制（逐字抄自 `prereg.known_limits`）

- P 臂是 rc4（redo/rc4 652c50d36，wheel sha256 28e5480c84aa…，~/dev/ops/rc4_dist 唯讀）裝在獨立 venv；config_dir 只複製 models.json，不載入 Vacant 的 pi 擴充：量的是零設定重開模式＋產品自己的驗收。
- P 的模型呼叫數 harness 量不到（usage=none），結案時用 ops/redo/analysis/p_model_calls.py 從 {logs}/vacant-work 補算。
- 選題規則只用 exercism 自己的 difficulty 標籤（≥4）與事先寫死的 sha256 排序；從沒給任何模型跑過。
- 數字不與其他批併表、不合併 p 值。
- 評分＝原件 *.spec.js（visible_equals_grader；harness 驗收前還原）；P 臂的產品另外用自己的 npm 驗收決定要不要重開。
- node_modules 是共用快取的 symlink；agent（兩臂）都寫得到它。批前雜湊記在 ops/redo/results/js_node_modules_hash_pre.md，結案時重算。
- 9 題與 exercism_js（舊選題）重疊：overlap 見 ops/redo/banks/exercism_js_d4.json。
- harness 是 redo/nonpy-bank 的 redo.py（command 驗收），1003 的 llama.cpp 2.73.0。
- rc4 起 P 臂在嘗試與驗收期間把 node_modules（共用快取）設成唯讀、前後比清單；A 臂沒有這層，A 的 agent 寫得到快取。另有 ~/dev/ops/nm_watch_js.log 每分鐘比對快取清單，結案時逐筆對到格子；有變動的格照 infra 規則處理並回報。

### 結案時補記

- **脫離的測試行程（孤兒）**：P 臂的 jest／`npm test` 有時在格子結束後還活著（rc4 沒有 subreaper；rc5 起有）。11/22 起孤兒看門每 10 分鐘掃一次，在這批的格目錄裡砍了 30 個（工作目錄所屬的格已經有 cell.json），都是格子結束之後才砍，不影響該格結果；砍之前它們佔 CPU、可能拖慢後面的格（兩臂都受影響）。

## 7. 中斷與作廢紀錄

- 11/21 17:09Z 由 1003 佇列發射、11/23 05:56Z 完成；infra_void 0。
- 結束後佇列發射 atimeout 冒煙時，因冒煙在 5 秒內就結束而誤判「找不到 runner」BLOCKED（gpu_queue.sh 已修）；冒煙本身因題庫唯讀而 4 格 exit 43（題庫權限已修、冒煙重跑，見 atimeout 的紀錄）。
