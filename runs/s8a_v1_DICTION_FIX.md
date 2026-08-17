# S8a：把觀測台的紅線 B 修掉——28 → 4，而且那 4 條全是識別字

第 113 輪 · 2026-08-17 04:02–04:11 UTC · 零機時、零生圖

> **資料標籤（鐵律 6）**：本輪活體 DOM 的 40 筆交付是**機制模擬**
> （`runs/s7b_interact_dom.py:_FakeBrain` 確定性假腦），不是真模型實測。
> 本輪量的是「畫面上有沒有那個字」，不是品質。

---

## 一、為什麼是這一輪

第 111 輪的 S7i（commit `1ee175b`）把三個展件 × 三條紅線攤平之後量到一件事，
但**沒有人去修**：

```
展件              A 單邊句    B 可究責     C 允許講法   讀法
觀測台               22        0         1   A=單邊 · B=命中 · C=守線
                              ↑
                    可究責族分母＝0
```

S7i 自己的話：「**不是偶爾用錯詞，是整個口徑沒有對照組**。單看 --diction
只看得到 28。」

這一格的特別之處是**它不需要任何人拍板**。誠實邊界第 1 條
（「不准出現『信任』，用『可究責』『讓依賴有根據』」）與 CLAUDE.md §5
是人類已經下過的決定，執行它不是新決定；規則七的清單裡沒有「文案口徑」。

**第 108–112 連續五輪都在修量具、沒有改到任何一個觀眾看得到的像素。本輪有。**

## 二、量到什麼

判準寫在 `~/vacant/STATE.md` 第 113 輪【事前登記】，動手之前寫的，一條沒放寬。

| 格 | 判準 | 結果 | |
|---|---|---|---|
| `P0_yardstick_frozen` | 三個量具檔 diff 合計 0 行 | 0 行（指令印出空） | PASS |
| `P0b_yardstick_selftest` | `B1 口徑探針 fixture: 9/9` | 9/9 | PASS |
| `P1_positive_control` | 注入 ⇒ 主數字+1；移除 ⇒ 回到主數字且 sha256 逐位元還原 | 4 → **5** → 4，`sha256sum -c` OK | **PASS（承重）** |
| `P2_target` | 觀測台 B 逐條 28 → 4 | **4** | PASS |
| `P2b_residue_named` | 那 4 條全是識別字 | `#chip-trust`×2 · `<span id="trust">` · `trust_card` | PASS |
| `P3_denominator` | 分母 0 → ≥6，三檔各 ≥1 | **23**（app.html 8 · app.js 10 · dashboard.py 5） | PASS |
| `P4_other_exhibits` | 官網 `0 0 0`、動物園 `2 1 5`、觀測台 A／C 維持 0／0 | 逐值相同 | PASS |
| `P5_dom_clean` | 9 個活體狀態：信任 0 · 可信 0 · 可究責 ≥1 | 9/9 皆 `0 / 0 / 10–12` | **PASS（承重）** |
| `P5b_dom_alive` | 每檔 text_len >20000；`#id-rows`＝6、`#act-rows`＝40 | min **26420**；6／40 | PASS |
| `P6_contract` | 四個契約字串 grep 計數對 HEAD 逐值相同 | `chip-trust 3`／`id="trust" 1`／`trust_card 103`／`trust_on 53` — 全同 | PASS |
| `P7_tests` | ≥521 passed / 0 failed / 6 skipped，ERROR 仍只有 `test_mcp_v2.py` | **521 / 0 / 6**，ERROR 1 檔 `test_mcp_v2.py` | PASS |
| `S1_scope` | 只動 4 個檔＋`runs/s8a_dom/`；另兩個 repo status 不變 | 相符 | PASS |
| `S2_docstring_kept` | docstring 那 6 條一條都沒被改 | 「刻意排除」區塊仍列 **6 條** | PASS |

主數字：

```
展件             檔     語料字元  │    紅線A    紅線B    紅線C
官網             2     5654  │     0     0     0
人類動物園         45    12913  │     2     1     5
觀測台            3    16771  │     0     4     0        ← 改前 28
小計            50    35338  │     2     5     5        ← 改前 29

分母（可究責族）  觀測台  0 → 23
```

## 三、逐條 before → after（給人類一眼否決用）

### 誠實邊界句（最容易改壞的三句，判準：改寫後仍須同時有「否定面板權威」＋「指向替代權威」）

| 檔:行 | before | after |
|---|---|---|
| `app.html:115` | 面板不是**信任來源**；以 ledger 與各自的簽章鏈為準 | 面板不是**究責依據**；以 ledger 與各自的簽章鏈為準 |
| `app.html:138` | 面板好看不代表**系統可信** | 面板好看不代表**依賴它就有根據** |
| `app.html:160`（註解） | 面板是唯讀視圖，不是**信任來源** | 面板是唯讀視圖，不是**究責依據** |
| `app.html:162` | 此面板為唯讀視圖，**不是信任來源**。一切以簽章事件鏈與 ledger 為準 | 此面板為唯讀視圖，**不是究責依據**。一切以簽章事件鏈與 ledger 為準 |

三句都保留了兩半：否定（不是…依據）＋替代權威（ledger／簽章鏈／重算）。

### 招牌與標籤

| 檔:行 | before | after |
|---|---|---|
| `app.html:6`／`dashboard.py:69` | `<title>Vacant — 信任觀測台</title>` | `可究責觀測台` |
| `dashboard.py:117` | `<h1>Vacant · 信任觀測台</h1>` | `可究責觀測台` |
| `app.html:15` | `Trust Observatory` | `Accountability Observatory` |
| `app.html:35` | `trust <b>—</b>` | `可究責層 <b>—</b>` |
| `app.html:62` | `<h2>信任開關對照</h2>` | `<h2>可究責層 開／關 對照</h2>` |
| `app.html:70` | 信任層要花錢 | 可究責層要花錢 |
| `app.html:100` | 每一筆都可回到它的**信任狀**與簽章鏈頭 | 每一筆都可回到它的**交付憑據**與簽章鏈頭 |
| `app.js:189–190` | `row('trust off')`／`row('trust on')` | `row('可究責層 關')`／`row('可究責層 開')` |
| `app.js:219` | 同上（成本表） | 同上 |
| `app.js:223/225` | 信任層不是免費的／要主張信任層有價值 | 可究責層不是免費的／要主張可究責層有價值 |
| `app.js:240` | `` `trust <b>${on?'ON':'OFF'}</b>` `` | `` `可究責層 <b>${on?'開':'關'}</b>` `` |
| `app.js:369`（註解） | **信任狀**本體 | **交付憑據**本體 |
| `app.js:380–381` | badge `trust ON`／`trust OFF` | `可究責層 開`／`可究責層 關` |
| `app.js:395` | 未互審（**trust off** 時不互審） | 未互審（**可究責層關閉**時不互審） |
| `dashboard.py:127–128` | `trust ON pass率`／`trust OFF pass率` | `可究責層 開 pass率`／`可究責層 關 pass率` |
| `dashboard.py:147` | 正值＝**信任層**有增益 | 正值＝**可究責層**有增益 |
| `tests/test_dashboard.py:50` | `assert "信任觀測台" in html` | `assert "可究責觀測台" in html` |

## 四、刻意不動的四類（每一類都要能被讀成「考慮過而排除」）

1. **識別字／選擇器／API 鍵**：`id="trust"`、`#chip-trust`、`trust_card`、
   `trust_on`、`/api/task`。它們是 DOM 與 JSON 的契約，改了會壞、觀眾看不到。
   `P6` 就是證明它們一個字沒動的那一格。**剩下的 4 條紅線 B 命中全部出自這一類。**
2. **`.py` docstring 與 `#` 註解**：S7 抽取器自己把它們定義成「工作紀錄，
   不是觀眾文案」；`dashboard.py` docstring 那句還是**誠實邊界句**
   （CLAUDE.md：誠實邊界句是規格的一部分，改碼時保留）。`S2` 驗證仍是 6 條。
3. **`vacant/` 其他 26 個檔的「信任」**（`receipt.py`／`checkpoint.py`／
   `experiment.py`／`gateway.py`…）：全在 docstring／註解、不在 SCOPE。
   **不是靠推論**：第 101 輪歸檔的 9 個活體 DOM 逐檔數過，信任＝9、可信＝1，
   全部出自 `app.html`＋`app.js`，**一條都不是 API 生的**。
4. **實驗臂的內部名稱 `trust on/off`**：`router.py` 的開關名、
   `真模型_2026-07-26/E10/{on,off}` 的歸檔目錄名、ledger 欄位一律不動。
   本輪只改畫面上顯示的標籤。**沒有任何一筆既有資料被改寫或重新命名。**

## 五、事前預測對帳

- `G1131` `P2` 落在 4 — **中**（4，且逐條就是預測的那 4 個識別字）。
- `G1132` 語料字元會變動 — **中**（35226 → 35338）。
  其中 **觀測台 16775 → 16771（我改的）**，
  **人類動物園 12797 → 12913（不是我改的）**：第 112 輪 `b520f65` 給
  `world/js/clay/clay.js` 加了 `?pvar` 鉤子，而那個檔在 S7 的 SCOPE 裡。
  本輪 `vacant_hm` 的 `git status` 與開場逐字相同，可證不是本輪造成的。
- `G1133` 觀測台紅線 A 分母（單邊句 22）會變大 — **錯**：仍是 **22**，一格沒動。
  後半句（A 逐條命中必須維持 0）**中**：0 → 0，沒有不小心寫出因果句。

## 六、誠實邊界（寫在對自己不利的方向）

- **這一輪改的是字，不是機制。** 畫面上少了「信任」兩個字，
  **不代表系統多了任何可究責性**。分母從 0 變 23 量的是「有沒有講」，
  不是「講得對不對」。
- **本輪沒有做像素截圖驗收。** 這台機器沒有中日韓字型（第 69 輪查到），
  截圖只會是方框。所以 `P5` 驗的是 **DOM 文字**。
  **「DOM 裡沒有『信任』」不等於「觀眾在展場讀到的是可究責」**——
  後者要展場那台機器的字型與投影尺寸，本專案一次都沒量過。
- **觀測台會不會出現在展場，本輪沒有答案。** CLAUDE.md 的
  「展件可直接複用的」清單裡沒有它。紅線 B 是 repo 級規則所以照修，
  但不要把這一輪讀成「展件前進了」。
- **`--check-app` 有 4 個 FAIL，全部是既有的、第 101 輪自己記錄過判準寫錯**
  （`E0 chip_head` 是反向判準：渲染成功反而不會過；`E2` 三句其實就寫在靜態檔裡）。
  與歸檔結果**逐格相同**，不是本輪造成的；本輪的 `P5b` 只取
  `#id-rows`／`#act-rows`／`text_len` 三格，它們全 PASS。
- **`--summary` 的「讀法」欄現在把觀測台的 B 讀成「命中」**（因為還有 4 條），
  這是對的：量具沒有因為我改完就說我乾淨。要它變成「守線」得連
  識別字一起改，而那會壞掉 DOM 契約——**所以這一格留成 4，不是留成 0。**

## 七、怎麼重跑

```bash
cd ~/vacant/Vacant
git diff --numstat runs/s7_claim_audit.py runs/s7b_interact_dom.py examples/minitest.py
python3 runs/s7_claim_audit.py --diction-test
python3 runs/s7_claim_audit.py --summary
python3 runs/s7_claim_audit.py --diction
python3 runs/s7b_interact_dom.py --sweep-app runs/s8a_dom
python3 runs/s7b_interact_dom.py --check-app runs/s8a_dom
python3 examples/minitest.py
```

`P1` 正對照的重跑：把 `<p>信任探針</p>` 附到 `vacant/web/app.html` 尾端、
跑 `--summary` 看觀測台 B 是不是 5，再還原並 `sha256sum -c` 對回去。
