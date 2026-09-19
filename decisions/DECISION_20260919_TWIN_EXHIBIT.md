# DECISION 2026-09-19 — 數位分身接上 vacant world：一個居民 ＝ 一條可驗的收據鏈

人類原話：「針對現在已知可附身的 **pi**，我需要你**接好 vacant world**，
我要把整個**數位分身**做好。」

本文記三件事：動手前查到的事實（三個問題的答案）、這一輪造了什麼、
以及**哪些話現在還不能說**。

---

## 一、三個問題，查過之後的答案

### Q1 展件要接哪一份原始碼？

**接 `cosmopig/vacant_hm`，而且不必改它。**

- `runs/s7b_dom/*.html` 是 DOM 快照，不是原始碼。產生器是
  `runs/s7b_interact_dom.py`（headless Chrome 掃互動狀態，QA 工具）。
- `world/` **從來沒有**在本 repo 的任何分支上存在過
  （`git log --all --diff-filter=D -- 'world/*'` 零筆）。
- 原始碼在另一個 repo：`cosmopig/vacant_hm`（本機 `/Users/cosmopig/Documents/GitHub/vacant_hm`，
  1003 上 `/d/vacant/vacant_hm`，分支 `main`）。裡面有三代：
  `world/`（three.js 黏土）、`world2/`、**`world3/`（現行，預渲染板＋影片精靈）**。
- **關鍵發現：電視端早就把接口寫好了。**
  `vacant_hm/world3/docs/LIVE_INTERFACE.md`（2026-09-05）定義了 world event 契約，
  而 `world3/index.html` 已經實作 `?live=<url>&poll=2000` 的活模式
  （第 1814–1867 行：輪詢、依 `ts|type|task_id|arm|reviewer` 去重、
  事件 → 可播紀錄）。同一份文件 §四**自己列了兩個缺口**：

  > 活模式尚未在真 agent 上跑過——只用 rows_to_events 的重放驗證過格式。
  > `verify_url`：讓觀眾自己重驗收據的頁面還沒做。

⇒ **兩個缺口都在生產端。** 本輪補的就是這兩個：`to_events.py`（真 agent 吐得出
那種事件）與 `examples/twin_viewer.html`（`verify_url` 指得到的那一頁）。
**電視一個字都不用改**，所以這條線不需要跨 repo 同時改兩邊。

### Q2 「數位分身」是誰的分身？

**設計上是觀眾的；現在是程序生成的假人；而中間那一步是人類未決事項。**

- `SPEC_v3 §四`：給觀眾一段提示詞 → 他把自己慣用 AI 的記憶匯出 → 貼回來 →
  **當場萃取成四類 persona（工作領域／興趣主題／風格特徵／需求類型）→ 原文即刻丟棄**。
- 同一節接著寫「**但這裡有一條線，我不會自己跨（待人類決定）**」。
  `HANDOFF.md §六-2` 把同一件事列進「待人類決定——不要自己決定」，
  並指出它擋住兩項功能：人格抽取、退場上鏈。
- `SPEC_v3 §七` 的施工順序：第 4 項（persona 萃取）依賴「待倫理定案」，
  第 5 項（退場與撤回上鏈）依賴第 4 項。
- `vacant_hm/world/js/persona.js` 的檔頭已經做過同一個決定：
  「真的 persona 要等倫理定案……在那之前用假的餵世界——之後接真資料只是換這一個檔案的輸出來源。」

⇒ **這個 repo 裡沒有任何真人資料，而取得它的邊界是人類未決事項。本輪不跨。**
本輪的居民是 `ops/exhibit/twin/roster.py` 程序生成的，欄位形狀與
`persona.js` 逐字對齊，每一張卡上都標著「程序生成，不是任何人的分身」。

**但第 5 項的機制不依賴真人資料**——它只需要「有一份東西、它有 commitment、
它被刪了」。所以本輪把第 5 項的機制先做出來並真的跑過（見 §三）。

### Q3 秒級互動要預跑幾格？

現場**零模型呼叫**。頁面只做兩件事，兩件都是毫秒到秒級：
重算 sha256／驗 Ed25519（r454 那一頁已實測 5579 筆可用），與讀已落盤的 JSON。

格數由**敘事**決定，不是由算力決定。算出來的數字：

| 量 | 值 | 來源 |
|---|---|---|
| 真模型每題 | 約 114 秒 | E10 實測（CLAUDE.md） |
| 1003 併發 | 4 串封頂 | 記憶：G 實驗算力拓撲 |
| 一格重放 | 約 4 秒 | 機制模擬「一件交付在途 2.2–4.5 秒」（HANDOFF §七） |
| 一位居民的一天 | **6 格**（3 題 × 扣住／寫明） | 本文 §二 |
| 一圈 | 3 位 × 6 格 ＝ **18 格** | ≈ 72 秒重放 ＋ 觀眾自己驗一格（約 15 秒）＋ 竄改示範（約 10 秒）⇒ **單次互動 90–110 秒** |
| 預跑機時 | 18 × 114 ÷ 4 ≈ **9 分鐘**（無重試）；`--retry revise --max-attempts 3` 最壞 ≈ 26 分鐘 | 算術 |

**綁定約束不是「重放夠不夠久」，是「觀眾看不看得到兩種結局」。**
`bank_manifest.json` 的 S1 分層寫著 `expected_first_attempt_visible_fail >= 0.8`
——拒交格是多數，**交付格才是稀有的那一種**。所以排程刻意是
「同一題 × 扣住介面／寫明介面」兩格一組：兩格的差別只有一件事，
就是它知不知道客戶要的介面叫什麼。這比「換一題比較簡單的」誠實。

要撐一整天無人值守，18 格輪播足夠（觀眾會換人）；真正不准重複的是
**同一位觀眾的一次互動之內**。要擴充就加題不加機制：`--tasks` 逗號分隔即可。

---

## 二、造了什麼

```
vacant/consent.py                         同意／撤回／刪除證明（長在 logbook 上，零新機制）
ops/exhibit/twin/roster.py                居民名冊（程序生成，零真人資料）
ops/exhibit/twin/run_twin.py              一格 ＝ 一次 vacant run 的驅動器
ops/exhibit/twin/pack.py                  run 目錄 → 展件資料包（證據等級 fail-closed）
ops/exhibit/twin/make_consent_demo.py     同意鏈產生器（產物進版控）
ops/exhibit/twin/to_events.py             **接電視**：run 目錄 → world event JSONL
ops/exhibit/twin/build_viewer.py          組裝／--check
ops/exhibit/twin/twin_viewer_node_check.mjs  跑「真的那一份 JS」
examples/twin_viewer.html                 離線收據頁（0.73 MB，file:// 直開）
tests/test_consent.py · test_twin_viewer.py · test_twin_events.py   45 條
runs/twin_fixture_20260919/               18 格真跑（零模型）＋ events.jsonl
```

### 這一輪真的跑過的東西

18 格 `vacant run`，**交付 9／拒交 9**，全部由
`python3 -m vacant.vrun.verify_receipts --glob …` 判 OK（沒有另寫第二把尺）。
頁面端 13 條 node check 全過，其中兩條是這條線的重點：

- **N4**：把「它交出來的那份程式碼」照 `wshash.py` 的佈局重算樹雜湊，
  18/18 等於鏈上簽過的 `ws_end_sha256`
  ⇒ 展場那份程式碼是**綁在簽章上**的，不是頁面另外貼的。
- **N6**：翻掉 `accepted` ⇒ 那一筆 hash 變、簽章對不上、下一筆接不上。

拒交格長這樣（`s1_01_addmul`，介面被扣住）：它寫出了
`def add(a, b)` 與 `def multiply(a, b)`，兩個都對；驗收要的是 `mul`
⇒ `ImportError` ⇒ `visible_fail` ⇒ **exit 20**。
**觀眾看得到「它想交，但被擋下來」，而且那份程式碼看得懂。**

### 同意／刪除（SPEC_v3 §七 第 5 項的機制面）

`vacant/consent.py` 在既有 logbook 上加三個 entry type
（`CONSENT_GRANT`／`CONSENT_WITHDRAW`／`PERSONA_ERASED`），
沒有新的密碼學、沒有新的 wire-format。示範鏈 5 筆，真的把檔案寫到磁碟、
算 sha256、`unlink()`，再把 hash 簽上鏈。

四條誠實邊界各有一條可執行測試：

1. 鏈記的是「我們記下我們刪了、刪掉的位元組 sha256 是 X」，**不是「世上沒有副本」**。
2. 撤回上鏈 ≠ 撤回被執行。鏈讓「撤回了但沒刪」看得見（頁面上有一顆按鈕可以把
   刪除那一筆拿掉，狀態就變回「撤回了，還沒刪」）。
3. **commitment 的 hiding 全靠 nonce。** persona 的取值空間只有 ~2×10⁸
   （12×15×10×6 的清單，每類挑 1–3 個）——**沒有 nonce 的承諾等於明文**。
4. 由第 3 條推出：**刪除必須連 nonce 一起刪**。只刪原文而留著 nonce，
   任何人都能拿鏈上的 commitment 窮舉回原文。`erase()` 因此硬性要求
   nonce 出現在被刪清單裡，少列就報錯。

第 3、4 條是這一輪查出來的，不在任何既有文件裡。

---

## 三、哪些話現在不能說

1. **這 18 格沒有一格有模型參與**（`requests_seen = 0`，等級 L-none）。
   頁面上逐格標著，而且標籤是**推**出來的不是宣告的：
   `requests_seen == 0` 一律落成 L-none，`--evidence L-real` 蓋不過去
   （`pack.evidence_level`，有正反控制測試）。真跑落地之後標籤自己會改對，
   不必改一個字的文案——**這就是「那句話要逐格改對，不是整片拿掉」的實作**。
2. **`meets_demand` 一律 null。** 它要隱藏測資才答得出來，而隱藏測資不進展件。
   把 `accepted`（通過可見驗收）寫成 `meets_demand`（符合需求）是這條線上
   最容易犯、後果最大的一個錯，所以有一條測試釘住它。
3. **`basis` 寫死 `random`。** `vacant run` 沒有路由層——誰做這一格是人指定的。
   這個欄位不提供參數可改：一個可以用旗標改成 `reputation` 的欄位遲早會被改。
4. **驗收是單邊的量具**：擋得住已知的壞解，不等於涵蓋真需求。
5. **事件流沒有簽章**（`LIVE_INTERFACE.md §四` 已記）。可驗的那一份是收據頁，
   不是那條串流。電視是展示端不是證據端。

---

## 四、跨 repo 的兩個待辦（在 `vacant_hm`，本輪沒動）

1. **`liveAssemble` 把 `meets_demand` 用 `!!` 收斂**
   （`world3/index.html`：`meets_demand: !!v.meets_demand`）。
   `null` 與 `false` 因此同形 ⇒ 電視會把「不知道」畫成「不符合需求」。
   需要一行：`v.meets_demand === null ? null : !!v.meets_demand`。
2. **疑似欄位放錯**：`liveAssemble` 寫
   `prompt_sha256: get("receipt").sha256 || get("task_opened").prompt_sha256`
   ——優先取**收據**的 sha256 塞進名字叫 `prompt_sha256` 的欄位。
   在 `replay_371.json` 裡那個欄位是題面雜湊的前 16 碼。活模式下畫面會顯示鏈頭
   而不是題面雜湊。**先回報，不自己改**（那是另一個 repo）。

---

## 五、下一步（等人類通知才跑）

```bash
# 真跑：pi ＋ 1003（吞吐 4 串封頂，R535 跑完再插）
python3 ops/exhibit/twin/run_twin.py --out runs/twin_20260919 \
    --evidence L-real --upstream <endpoint> --model <id> \
    --retry revise --max-attempts 3 \
    -- ops/vacantrun/wrap_agent.sh pi "{TASK}"

python3 ops/exhibit/twin/pack.py --runs runs/twin_20260919
python3 ops/exhibit/twin/build_viewer.py
node ops/exhibit/twin/twin_viewer_node_check.mjs
python3 -m vacant.vrun.verify_receipts --glob 'runs/twin_20260919/runs/*'
```

**發射前檢核**：`requests_seen > 0` 才算中介發生；兩種結局都要有
（一個永遠拒交的閘門跟沒有閘門一樣沒用）；`verify_receipts --selftest` 先 PASS。

---

## 六、最可能做不出來的地方

**pi ＋ 12B 在 S1「介面被扣住」那一半上，可能連一格交付都生不出來。**
S1 的設計預期就是 first-attempt visible fail ≥ 0.8，而 12B 不思考版在 R533 的
同類題上並不強。拒交格會很多（那一半沒有風險），**稀有的是交付格**。

現在的排程已經先手處理了這件事：交付格走 `TASK_explicit.md`（PC 臂，介面寫明）
＋ `--retry revise`。若連 PC 臂都過不了，退路依序是
（a）換 S2 分層（給名字、扣行為細節）、
（b）換更強的模型（R532 的 qwen3-27b 路徑已經跑通）、
（c）保留 L-none 的腳本化格作為**機制展示**並在畫面上照實標。
(c) 仍然是一個誠實的展件，但它展示的是閘門與收據，不是分身的能力
——那是一個比較小的主張，不可以講成比較大的那個。

第二順位的風險是**素材**：本輪用的是 `vacant_hm/demo/sprites/` 既有的黏土人
（6 種體型 × portrait／write／wait／submit，已縮到 200px 內嵌成 data URI）。
它們是人的形象、剪影可辨，符合「不准抽象發光生物」。要換成 world3 的劇照級
素材才需要動生成管線（路線 B2，`ops/exhibit/PLAN.md`）；本輪不需要。
