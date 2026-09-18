# 2026-09-18 對抗性稽核與附身級研究——歷程文原料

**這份文件是什麼**：不是歷程文，是**歷程文的原料**。目標是讓未來寫歷程文的人（或 agent）
不必重跑任何一項調查就能引用，所以每一條都指得到**檔案:行號／commit sha／落盤 JSON 路徑／
可重跑指令**。參考形狀是 `docs/JOURNEY_2026-09-13.md`（那一份約 12,000 CJK 字，
每個數字都標「（來源：檔名 §節）」）。

**這份文件不是什麼**：不是裁決，不預註冊任何東西，不宣告任何新結果成立。
它記的是 2026-09-18 這一天**對我們自己做的六項稽核**，其中三項推翻了我們自己先前講過的話。

**口徑紀律**（違反＝重寫，沿用 `CLAUDE.md`§鐵律 與 `AGENTS.md`§9 `banned_phrasings_for_results`）：

- 描述機制一律用**可究責**，不用「信任」；必須討論「信任」這個詞本身時標明是在引用定義。
- 差值就寫差值與 pp，不寫 improvement／提升；不寫「複製失敗」「效果消失」「多數支持」。
- 沒量到 ≠ 量到 0（`infra_void`，09 §3.5）。沒檢查 ≠ 沒違規。
- 文獻只列可查證的（DOI／arXiv id）；只有書目沒讀全文的逐條標明。

---

## 〇、貫穿的線

六件事看起來是六個主題，其實是**同一件事的六個切面**：

> **把宣稱降到可驗證的程度，然後把可驗證的部分做硬。**

六個切面各自降的是哪一句宣稱：

| # | 原本的宣稱 | 降到什麼 | 硬在哪 |
|---|---|---|---|
| 一 | 「Vacant 包住 agent」 | 「四種形態裡只有兩種有約束力，而且都要外加 OS 邊界」 | 七階量表 ＋ `AGENTS.md`§1 的逐點對照表 |
| 二 | 「鏈驗得過＝紀錄完整」 | 「integrity 有，completeness 沒有」 | 五條實測 ＋ 正式名字（truncation attack） |
| 三 | 「R532 V/GT 43/43 CLEAN」 | 「H-MIX 那一臂 43/43 CLEAN，另兩臂未稽核」 | 擴到十臂 ＋ 逐臂 fail-closed ＋ 回溯 179 份 |
| 四 | 「驗收套件過了量具＝套件夠強」 | 「擋得住 1 種錯」→「擋得住 N 種造得出來的錯裡的幾種」 | 變異致死率，刻度從 1 細到 N |
| 五 | 「把 Vacant 附身到任何 agent 上」 | 「攔交付比攔對話便宜，而且 proxy 單獨只有 L3」 | 五個附身面比較 ＋ R534 真跑接線 |
| 六 | 「外部裝得起來就能用」 | 「能用的前提是他手上已經有這個 wheel」 | 乾淨室 ＋ 三個阻擋項落地 |

第三與第六是**自我糾錯**：我們對外講過的兩句話，當天被自己推翻。
這一天的價值不在於做出了什麼新東西，而在於**它留下了我們抓到自己錯的紀錄**——
而那正是可究責這件事本身唯一能被示範的方式。寫歷程文時這一句應該是本節的收尾。

**這一天的三個 commit（⚠ 每個都有兩個 sha）**：見 §七-4。

---

## 一、對抗性稽核：Vacant 到底是強制還是自願

### 1.1 七階強制量表

稽核時用的刻度（本次調查自訂，**尚未寫進任何程式或文件**，見 §一-5 的落盤缺口）：

| 階 | 意思 | 一句話判準 |
|---|---|---|
| L0 | 不存在 | 不呼叫就完全不涉及；沒有任何東西會知道你沒呼叫 |
| L1 | 勸 | 有一個「建議走這條路」的介面，忽略它不會被攔也不會被記 |
| L2 | 側錄 | 經過的東西會被記下來，但一個字都不會被擋 |
| L3 | 自願中介 | 走這條路的一定被檢查，但有別條路可以不走 |
| L4 | 迴圈擁有 | 迴圈本身是我們寫的，agent 沒有跳過閘門的路徑 |
| L5 | kernel／OS 邊界 | 由核心強制，程式自己繞不掉 |
| L6 | 外生錨點 | 由另一個利害關係不同的主體持有，我方繞不掉（口徑：不寫「信任根」） |

### 1.2 九個整合點落在哪（可引用的逐點對照）

`AGENTS.md`:58-61 已經把其中四個寫成committed 的表（**這是唯一落盤的版本**，
用的是「四種形態」不是七階）：

| 形態 | 入口（逐字引 `AGENTS.md`） | 有沒有約束力 | 本次判階 |
|---|---|---|---|
| Library | `vacant.agent.Vacant`（`vacant/agent.py:51-103`） | **No — voluntary** | L0 |
| MCP tool | `vacant.mcp_server`（`vacant/mcp_server.py:184-210`） | **No — persuasion only** | L1 |
| Controller | `VacantFirstController.delegate_then_run`（`vacant/controller.py:304-530`） | **Yes — 只對它自己 spawn 的子行程** | L3 |
| Harness owns the loop | `ops/gain/r530/openwork_arms.py:642-696` | **Yes — the harness *is* the loop** | L4 |

補上另外幾個（本次調查另行查證，未進 `AGENTS.md`）：

- **L1 的逐字證據**：`vacant/mcp_server.py:184` 是 `@mcp.tool()`、:185 是 `def delegate(...)`，
  :186 的 docstring 第一句是 `"""THE PREFERRED PATH for any coding subtask with an objective check.`
  ——「PREFERRED」這個字本身就是自認的 L1。⚠ 這段 docstring **會進 agent 的 prompt**，
  所以 2026-09-18 的禁語清理**刻意沒有動它**（改它是改行為、會影響既有實驗的可比性，
  見 commit 訊息「`vacant/mcp_server.py` 的工具 docstring **刻意沒動**」）。
- **L2**：`vacant/mcp_trace.py:24-46` 的 `_pump()`。逐行原樣轉送到 `dst`，同時把該行
  JSON-RPC 記到 `logf`——**一個字都不擋**，這是側錄的定義。全檔 75 行。
- **L4 的逐字證據**：`openwork_arms.py:642-696` 是「送 propose → 收 tool_calls → 進沙箱跑」
  那一整段；:699-700 才是「宣告完成」。閘門在 :721 的 `acceptance.run_suite(..., suite="visible")`。
  A-SOLO 臂在 :714-720 直接 `accepted = True` 且註解逐字寫「**收。** 沒有閘門、沒有回饋、
  不存在拒交」——同一支檔案裡同時存在 L4 與 L0，這是對照組的設計本身。
- **L5**：`ops/gain/r530/sandbox.py:377-421` 的 `class BwrapSandbox`。
  `SYSTEM_RO = ("/usr","/bin","/sbin","/lib","/lib32","/lib64","/etc")` 加
  `--unshare-all --die-with-parent --new-session`，註解逐字：「沒有 `/home`、沒有 `/var`、
  沒有 repo ⇒ `ops/gain/r530/hidden/` 在沙箱的檔案系統裡**不存在**，而不是『存在但我們不准它讀』」。
  ⚠ 同一支檔案的 :371-374 是 `class NoneSandbox`，docstring 逐字「**沒有隔離**，名字就這樣寫」——
  量表的 L5 與 L0 並存，退階是可能的，所以 R534 的預檢 P4 才要**實測三條隔離**
  （`ops/gain/r534/preflight.py`§docstring）。
- **L6**：**我們一個都沒有。** 見 §二-6。

### 1.3 學理名字：complete mediation

正式名字是 **complete mediation**（完整中介），出自 Saltzer & Schroeder 1975,
*The protection of information in computer systems*, Proceedings of the IEEE,
**DOI 10.1109/PROC.1975.9939**（取得層級 `C_僅書目`，查證來源 crossref-doi；
見 `docs/LITERATURE_GAP_2026-09-18.md`§限制 4）。

reference monitor 的三個條件與我們的對照，已經寫進 `AGENTS.md`:51-53 與 §9 的機器可讀事實區：

```
"reference_monitor_Saltzer_Schroeder_1975": {
  "tamper_proof": true,
  "small_enough_to_verify": true,
  "complete_mediation": false
}
```

`README.md`:206-207 的中文版逐字：「Vacant 滿足**防竄改**與**小到可被驗證**，
**不滿足 complete mediation（完全中介）**。這不是 bug，是『可選的東西不可能完全中介』
的必然後果。把它寫成強制層就是在說謊。」

**這一條對展場的用處**：觀眾問「那 agent 不用它怎麼辦」時，正確答案不是解釋我們有多嚴，
而是 1975 年就有名字的那個條件我們不滿足，以及為什麼那是**可選**的必然代價。

### 1.4 自陳逐字（`vacant/controller.py:7-8`）

```
誠實邊界：保證只涵蓋透過本 controller 啟動的子行程；無法阻止同一 OS 使用者繞過
本命令直接執行 agent。需要強制全機唯一出口時，仍須容器、ACL 或 egress policy。
```

`AGENTS.md`:63-72 把這兩行逐字引進去，並且加了一句「which nothing in this file may
be read as softening」。⚠ 這是 `CLAUDE.md`§慣例「誠實邊界句（raises-cost 非 prevents 等）
是規格的一部分，改碼時保留」的具體實例，寫歷程文時可以拿來當「規格層級的誠實」的例子。

### 1.5 可引用事實與落盤缺口

- **最強的一句**：Vacant 滿足 reference monitor 三條件中的兩條，**不滿足完全中介**
  （`AGENTS.md`:51-53；Saltzer & Schroeder 1975, DOI 10.1109/PROC.1975.9939）。
- **無條件成立的反面**（`AGENTS.md`:74-80）：收據**進料檢查**本身繞不掉——
  `vacant/receipt.py` ＋ `controller.verify_delivery` 重算五個 sha256（request／task／
  tests／answer／trust card）、驗 Ed25519、把 `chain_head`／`stream_id`／`branch_id` 對
  **當下的鏈**比對，`vacant/controller.py:372` 用 `os.O_EXCL` 搶發射權 ⇒ **一張收據只能用一次**。
  「不能強制它走進來」與「走進來的一定被檢查」是兩件事，不要混講。
- ⚠ **落盤缺口**：七階量表（L0–L6）目前只存在於本文件。若要拿去展場或歷程文，
  必須先寫進 `AGENTS.md`§1 或另開一支，否則它是一個沒有單一真相來源的刻度。
- ⚠ **轉述更正**：`vacant/agent.py:56` 指的是 `infra_void` property 的 docstring 首行
  （`def infra_void` 在 :55），**不是** library 形態的入口。落盤版本的正確引法是
  `vacant/agent.py:51-103`（`AGENTS.md`:58）。同理 `controller.py:304-584` 的正確引法是
  `:304-530`（`AGENTS.md`:60；全檔 584 行，但 `delegate_then_run` 到 :530）；
  `sandbox.py:376-421` 的 `class BwrapSandbox` 起點是 **:377**（:376 是空行）。

---

## 二、收據鏈的三個洞

### 2.1 實測（本文件作者當天親手重跑，逐字輸出）

重跑腳本邏輯：`Identity.generate()` 造一把金鑰 → `Logbook.append()` 連簽 5 筆
`episode` → 對四種竄改各驗一次 `verify_chain(pub)`。零網路、零模型呼叫、約 1 秒。

```
原鏈 5 筆        -> verify_chain = True
砍掉尾巴 2 筆    -> verify_chain = True   ← 沒抓到
抽掉中間 1 筆    -> verify_chain = False
竄改中間內容     -> verify_chain = False
砍掉創世那筆     -> verify_chain = False
```

同一份輸出已經被寫進 `AGENTS.md`:398-411（英文版）與 `README.md`:60-85（中文版，
連同可貼可跑的 4 步程式碼）。⚠ `README.md`:82-85 那一段逐字說明「第 4 步不是 bug 的示範，
是**這條鏈的地界**」——引用時不要只引表格不引這句。

### 2.2 原因：沒有長度承諾、沒有外部錨

`vacant/logbook.py:168-195` 的 `verify_chain` 只做四件事：
① `genesis.stream_id != GENESIS_STREAM_ID` 就 False；② `seq` 從 1 開始逐一遞增；
③ `prev_hash` 串接；④ 每一筆 Ed25519 驗簽。docstring 逐字：
「完整驗鏈：seq 連續、prev_hash 串對、stream/branch 一致、每筆簽章過。」

**這四條對一個「合法前綴」全部成立**。沒有第五條「總共應該有幾筆」，也沒有任何一個
外部持有的錨點。

### 2.3 同一個洞在上一層複製了一份

`vacant/checkpoint.py:144-155` 的 `verify_checkpoint_chain` 只往回走
`prev_checkpoint_sig`，並要求首枚為 null。實測（同一次重跑）：

```
存檔點鏈 4 枚    -> (True, 'ok')
砍掉尾巴 2 枚    -> (True, 'ok')            ← 沒抓到
抽掉中間 1 枚    -> (False, '存檔點鏈斷在第 1 環（prev_checkpoint_sig 不接續）')
砍掉第一枚       -> (False, '首枚存檔點的 prev_checkpoint_sig 應為 null（鏈頭被嫁接）')
```

⚠ 這一條的意義比第一條大：`checkpoint.py` 的 docstring（:145-148）寫的是
「斷點（缺一枚、順序被調換、頭被拔掉）即失敗——『沿鏈累積』若可抽掉中間一段，
垂直信任史就不成立」——**它自己列舉的三種斷法裡沒有「砍尾巴」**，
所以這不是被承認的取捨，是同一個盲點在第二層被複製。
`AGENTS.md`§9 已記為 `"also_affects": "vacant/checkpoint.py:144-155 verify_checkpoint_chain"`。

### 2.4 要破除的誤解：把筆數簽進每一筆**擋不住**

直覺的修法是「每一筆都把當前總筆數簽進去」。這**沒有用**，理由兩句話：

1. `seq` 已經是筆數——`vacant/logbook.py:145` 的 `seq = last.seq + 1`，所以那份資訊早就在裡面了。
2. 截斷後的前綴**每一筆都仍然自洽**：第 3 筆並不知道自己後面本來還有第 4、5 筆。

`AGENTS.md`:417-419 的逐字結論：「A length commitment only works if it is **exogenous** —
held by another party, or timestamped before the truncation could have happened.」
⇒ **長度承諾必須是外生的**：要嘛把鏈頭（`Logbook.head()`）對外公示，要嘛找人會簽。
Vacant 目前兩件都不做，`README.md`:85 逐字「Vacant 不會替你做」。

### 2.5 金鑰託管：收據由交付方自己簽，私鑰同 uid 可讀

- **自簽**：`vacant/ecosystem.py:641-642`——`receipt = make_delegation_receipt(` 的第一個
  參數是 `deliverer.body.identity`。交付方自己簽自己的交付收據。
- **私鑰明文**：`vacant/body.py:160` 是 `self.identity.save(self.trust_dir)`，
  **沒有傳 `passphrase`**；而 `vacant/identity.py:42-50` 的 `save()` 簽章明明是
  `def save(self, dir_path, *, passphrase: bytes | None = None)`，:47 也確實把 passphrase
  轉給 `crypto.priv_to_pem`。⇒ 支援加密但產品路徑沒有用，落盤的是明文 PEM，
  目錄 0700、檔案 0600，**同一個 OS uid 讀得到**。
- **簽章的語意上界**：`vacant/peerexec.py:117-120` 逐字：
  「**簽章指認的是金鑰，不是人。** …所以收據能證明『這筆證言事後沒被改過、且與同一把
  金鑰的其他證言同源』，**不能**證明背後是哪一個主體。」

這三條合起來寫進 `AGENTS.md`:427-434（H-4），結尾逐字：
「Key custody is a deployment assumption; software cannot *prevent* forgery by root.」

### 2.6 對帳是同源的 ⇒ 抓得到 bug，抓不到 malice

`ops/gain/replay/verify_run_receipts.py` 的三條對帳規則（verdict 數＝row 數、
task_id 集合相等、attempt 數 ≥ verdict 數）比對的**兩份紀錄是同一個行程寫的**。
`AGENTS.md`:458-464（H-11）逐字：

> They catch asymmetric omissions, which is to say **bugs**; they cannot catch both sides
> failing to write together, which is to say **malice**. Real reconciliation requires at
> least one end to be held by a party with different interests. **That is not in place.**

⚠ 這就是 §一-1.1 量表裡 **L6 一個都沒有**的具體後果。
`AGENTS.md`:481 另有一條 common mistake：「Treating `verify_run_receipts.py` reconciliation
as an independent audit」→「Treat it as a same-origin self-check」。

**可引用的反面**（不要只引壞消息）：`AGENTS.md`:96 記載
R532 跑 `verify_run_receipts.py --selftest` 再 `--glob 'runs/g_r532_*'`：
**86 條鏈、3,895 筆、0 失敗**，而且 selftest 先跑負向控制（先證明驗證器抓得到壞鏈，
才拿它去指真鏈）。同源限制不會讓這個數字消失，只會限制它能撐住哪一句話。

### 2.7 正式名字與文獻

- **truncation / omission attack**：Di Ma & Gene Tsudik, *A new approach to secure logging*
  (2009), ACM Transactions on Storage, **DOI 10.1145/1502777.1502779**。
  `docs/LITERATURE_GAP_2026-09-18.md`§限制 2 的逐字對應：「定義為『刪除尾端一段連續的
  log 紀錄』，並明說一般的 hash-chain／forward-secure MAC 方案擋不住它，要靠
  forward-secure sequential aggregate 簽章。**我們量到的行為是教科書案例，不是新發現。**」
  （取得層級 `C_僅書目`，crossref-doi）
- 機制面來源：Ma & Tsudik, *Forward-Secure Sequential Aggregate Authentication* (2007),
  IEEE S&P。**無 DOI／arXiv**，取得層級 `C_僅書目`（openalex），**未讀全文**。
- 祖先：Schneier & Kelsey, *Secure audit logs to support computer forensics* (1999),
  ACM TISSEC, **DOI 10.1145/317087.317089**（`C_僅書目`，crossref-doi）。
- **integrity ≠ completeness** 這一組對立已寫進 `AGENTS.md`§9：
  `"chain_guarantees": {"integrity": true, "completeness": false, ...}`。

**展場用法**（這一條直接影響展件文案）：`examples/receipt_viewer_multiparty.html`
展示的「從創世驗到鏈頭」是 integrity。**它不證明沒有被砍掉尾巴。**
展件旁邊若要寫「這條鏈完整」，那句話是錯的；正確講法是「這條鏈沒有被改過」。

---

## 三、V/GT 稽核涵蓋缺口——本日最重要的自我糾錯

### 3.1 那句話當時是錯的

我們對外寫過 R532「V/GT 紅線 43/43 CLEAN」。**那句話是錯的。**

- `ops/gain/harness_vgt_audit.py:746`（**修補前**）逐字：`if arm not in VARIANTS:` 接 `continue`。
- `ops/gain/harness_arms.py:65` 逐字：`VARIANTS = ("HPI", "HOC", "HMIX")`。

⇒ `OFF`／`OFF5`／`CONFORM`／`EQ5`／`ON`／`ONR`／`CALIBRATION` 七條臂**從來沒有被掃過**。
已落盤的 37 份 `ops/gain/replay/r529/vgt_v2_*.json`，每一份的 `per_arm` 都只有 `{'HMIX': N}`。

**正確講法**：「**H-MIX 那一臂 43/43 CLEAN，另外兩臂未稽核**」。
已寫進 `README.md`:208-215（中文，第 3 條）與 `AGENTS.md`:376-385（英文，H-0）。

### 3.2 洞的形狀：**靜音的跳過**

修補 commit 的訊息逐字（這一段是整天最值得引進歷程文的方法論）：

> **為什麼會躲這麼久**：跳過是**靜音**的。`per_arm` 只記「掃到的」，不記「在檔案裡但沒掃的」，
> 所以輸出裡沒有任何一格會因為少掃一臂而變紅。這與 round460e 那次是同一個形狀的錯
> （「沒有檢查」冒充「沒有違規」），只是換了一個維度：那次是 needle 被跳過，
> 這次是**整條臂**被跳過。

⚠ 還有一句要一起引，它是對自己最不留情的那句：
「本模組的標題寫的是『H 臂的 V/GT 洩漏動態稽核』，所以那句 filter 在**寫的當下**是自洽的；
不自洽的是後來拿它的輸出去講**整個 run** 的話。」
⇒ **bug 不在程式碼裡，在引用程式碼輸出的那句話裡。** 這是本日最可引用的一句方法論。

### 3.3 方向不是中性的（影響要寫清楚）

Δ_C ＝ HMIX − CONFORM。沒被驗過的是**被減數那一側**（CONFORM）。
若 CONFORM 有洩漏，它的分數會偏高 ⇒ Δ_C **更負** ⇒ 與觀察到的方向**同向**。
所以在回溯補掃結果出來以前，這個可能性**排除不掉**。
（來源：`harness_vgt_audit.py` 模組 docstring 的 round534 區塊；`AGENTS.md`:376-385）

### 3.4 修法：三件事，而且預設值改成完整稽核

新增 `--scope v3`（`audit_run()` 與 CLI 的**預設**）：

1. **臂的範圍改成 `AUDITED_ARMS`** ＝ `CLASSIC_ARMS + tuple(VARIANTS)`，
   其中 `CLASSIC_ARMS = ("OFF","OFF5","CONFORM","EQ5","ON","ONR","CALIBRATION")`。
   ⚠ `CALIBRATION` 一定要在裡面，原始碼註解逐字：「`gain_run.calibrate_pool` 的 `run_one`
   是一條**真的送 prompt 出去**的路徑（`role="calibration"`），它與六個臂共用同一份
   `task["prompt"]`，沒有理由不掃。**漏掉它就是把同一個洞留一個小號。**」
2. **逐臂 fail-closed**：`arms_present` 逐臂落盤；某一臂在 `calls.jsonl` 裡有紀錄卻 0 筆
   進稽核 ⇒ verdict 是 `UNVERIFIABLE` **不是** `CLEAN`；`records_audited == 0` 同理。
   `AUDITED_ARMS` 的註解逐字：「**這份名單是 fail-closed 的分母**：`calls.jsonl` 裡出現了
   不在這份名單上的臂（例如 R530 的 `A-SOLO`），v3 會判 `UNVERIFIABLE` 而不是安靜跳過
   ——那代表 scope 拿錯了，不是通過。」
3. **多一條豁免 `model_own_output_quoted`，只為 `ON` 臂而存在**，而且判準比既有的
   SELFTEST 那條更緊：needle 的**每一次出現**都必須落在「與本 run 稍早同臂同題某筆
   模型回覆（或其 `extract_code`）逐字相等」的區間之內。`quoted_spans()` 用**區間**
   不用 replace，理由逐字：「replace 會把區間邊界上的字接起來，可能憑空造出或抹掉一個
   needle 命中」。豁免**逐筆留證**（`excused`），不靜音。

**兩條紀律要一起記**：
- **預設值改成完整稽核**。這是修補裡最重要的設計決定：靠忘了給參數而拿到只掃一臂的
  綠燈，正是這個洞能存在的條件。
- **v1／v2 的判準與臂範圍維持凍結**（R460 收官的 90／0 逐筆對帳表釘在上面），
  但兩者現在照樣吐 `arms_present_not_audited`——原始碼 docstring 逐字：
  「**舊判準可以凍結，但不准繼續靜音。**」

`scope_arms()` 的 docstring 逐字：「**v1／v2 只掃 H 臂是凍結的歷史，不是完整稽核。**」

### 3.5 回溯 179 份結果

落盤：`ops/gain/vgt_retro_audit_20260918.json`（136,117 bytes，`generated_at`
2026-09-18T11:58:32+0800，`wall_s` 289.6，零機時、零模型呼叫）。
產生器：`ops/gain/vgt_retro_audit.py`。

```
runs  : 179
tally : {'CLEAN': 165, 'UNVERIFIABLE': 10, 'VIOLATION': 4}
needles_checked 合計 : 3,486,403
```

逐批（本文件作者獨立從 `rows` 重算過，不是抄 commit 訊息）：

| 批 | CLEAN | UNVERIFIABLE | VIOLATION |
|---|---|---|---|
| R460 | 6 | 0 | 0 |
| R460R | 30 | 0 | 0 |
| R529 | 37 | 0 | 0 |
| R532 | 43 | 0 | 0 |
| R530 | 8 | 0 | **4** |
| 其他（探索／冒煙） | 41 | 10 | 0 |

**R532 的 CONFORM 1,122 筆首次被掃、零違規**（逐臂合計 `{'OFF': 836, 'CONFORM': 1122,
'HMIX': 1144}`）。R529 逐臂合計 `{'OFF': 717, 'CONFORM': 936, 'HMIX': 844}`。
⇒ §3.3 那個「排除不掉」的可能性，**現在排除掉了**——但要注意這是**事後**排除，
不是當時就知道。歷程文要寫的是這個時序，不是結論。

`UNVERIFIABLE` 10 份全是只有 preflight 的中止 run。
⚠ `UNVERIFIABLE` 的語意寫在落盤檔的 `honest_bounds[0]` 逐字：
「不是『乾淨』也不是『髒』——它是『這一份在這套量具下沒有可稽核的對象』」。

### 3.6 四個 VIOLATION 的開封比對

四份全在 R530、全是同一條既有結構規則 `hidden_file_in_workspace`，各 1 筆：
`runs/g_r530_s1_1004_1`、`runs/g_r530_s2_1003_1`、`runs/g_r530_s2_1004_2`、`runs/g_r530_s3_1003_1`。

逐份開封比對後判定為**量具假陽性**，三條獨立證據（commit 訊息逐字）：
① 與釘死的隱藏驗收 **sha256 不同**；② **非瑣碎行零重疊**；
③ 同一題跨 run 內容不同——**真的 GT 會一樣**。
⇒ 結論是「模型自己建的同名檔案」，**規則不動**。

⚠ 這裡的紀律值得引：發現 VIOLATION 之後**沒有**去放寬規則，而是逐份開封留證、
規則原封不動。放寬規則是讓紅燈消失最省事的方法，也是讓量具失去意義最快的方法。

### 3.7 誠實邊界（引用時必須一起帶）

落盤檔 `honest_bounds[1]` 逐字：

> `CLEAN` 只保證：`hidden \ visible` 的**字面 repr** 沒有出現在 harness 自己寫的
> system／user 文字裡。語意等價的改寫、以及 `excused` 裡那些作者歸屬豁免，這支都認不出來。

`honest_bounds[2]`：bank 是**推斷**出來的（`bank_inference` 欄位），不是 run 自己記的；
R529 之前的 run 沒有 `--record-bank-field`。

另一條已知弱點，照 R530 tool 回聲那條逐字沿用：
「『模型自己算出同一個值』與『模型看到了那個值』在字面比對下同形。」

### 3.8 ⚠ 尚未處理的下游（下一個 agent 的第一件事）

`README.md`:212-213 與 `AGENTS.md`:384-385 目前仍寫著
「179 個已歸檔 run 的回溯補掃**正在進行、結果未定**」／「A retroactive sweep of 179
archived runs **is in progress and its result is not in**」。
但 `ops/gain/vgt_retro_audit_20260918.json` 已經在同一棵樹裡（`git ls-files` 有它），
`generated_at` 11:58:32。⇒ **這兩份對外文件落後於自己的證據**，要更新。
在更新之前，**不得**在任何地方寫「V/GT 全臂乾淨」——因為對外文件自己還寫著結果未定。

---

## 四、驗收套件強度：量具只有一個變異體

### 4.1 量具自認的下界

`vacant/suitegauge.py:30-33`（單邊保證，逐字）：

> **單邊保證。** 壞樁擋得住只證明「這套驗收不是對什麼都放行」，**不證明**它涵蓋真需求。
> 一套「通過量具、但把三條 assert 刪到只剩一條」的套件照樣通過本量具

而量具實際用的壞解集合只有**一個**變異體：`vacant/suitegauge.py:112-122` 的 `broken_stub()`，
回傳 `f"def {entry_point or '_f'}(*a, **k):\n    return None\n"`。
（⚠ 這一行與 `gain_run.probe_instrument` 裡的 `stub = ...` **必須逐字相同**，
防漂移的測試是 `tests/test_peerexec.py::test_default_broken_stub_matches_probe_instrument`。）

### 4.2 負向控制實測（本文件作者當天親手重跑）

同一題（`is_prime`）、同一份參考解、同一組變異體，比較 8 條 assert 的強套件與
1 條 assert 的弱套件。重跑輸出逐字：

```
STRONG(8 asserts)    suitegauge.ok=True   mutation 23/23 = 1.000
WEAK(1 assert)       suitegauge.ok=True   mutation 10/23 = 0.435
```

⇒ **量具對兩者都給 `ok=True`；變異致死率把它們分開 23/23 對 10/23。**
釘住這件事的兩條測試在 `tests/test_suitemutate.py`：
`test_weak_suite_scores_low_strong_suite_scores_high` 與
`test_the_gauge_cannot_tell_those_two_apart`（後者的 docstring 逐字：
「這條會紅只有一種可能——有人改了 `suitegauge` 的合格語意。」）

### 4.3 三個題庫實跑（落盤數字）

產生器 `ops/gain/mutation_score_banks.py`；落盤
`ops/gain/data/suite_mutation_{lcb2,mbppplus,humanevalplus}.json`
（seed 全部是 `r535_mutation`，`limit=20`）。

| 題庫 | 有參考解題數 | 中位數 | 最低 | 最高 | 滿分題數 | 沙箱次數 |
|---|---|---|---|---|---|---|
| LCB v2 | 12 | **0.7836** | **0.600** | 1.000 | **1/12** | 224 |
| MBPP+ | 10 | 1.000 | 0.6111 | 1.000 | 7/10 | 89 |
| HumanEval+ | 10 | 0.9667 | 0.6875 | 1.000 | 5/10 | 154 |
| 三者合計 | 32 | 0.931 | 0.600 | 1.000 | 13/32 | 467 |

**最可引用的一句**：**LCB v2 有參考解的 12 題，中位數 0.784、最低 0.600，
12 題裡 11 題不滿分。**⇒ 每五個造得出來的錯，約一個能通過出貨閘門。
（32 題合計有 **12 題低於 0.80**。）

**與已量到的殘餘對得起來**（不是因果宣稱，是兩個獨立量到的數字方向一致）：
`AGENTS.md`:391-397（H-2）記載 R532 的實測——閘門接受的 811 筆交付裡，
**120 筆（14.8%）過了可見驗收卻沒過隱藏驗收**；未設閘門是 25.2%、設了閘門是 14.8%。
逐字：「The gate roughly halves false delivery…**it does not remove it.**」
⇒ §四量的是**為什麼**移不掉：可見驗收本身漏得掉某些錯，而且漏的比例在 LCB v2 上
中位數就有約 0.22。兩個數字量的是不同東西（一個是題庫層的殘餘率、一個是套件層的
致死率下界），**不可相加、不可互推**，但它們指向同一個地方。

### 4.4 最刺眼的一條：`return None` 在某些分支上活著

量具自己用的那個壞樁（整支函式回 `None`）**會被擋**；但變異器只把**某一條分支**
改成回 `None` 時，有三題擋不住（`survivors` 欄位逐筆，operator 都是 `return_const`）：

| 題目 | 行 | 變異前 → 變異後 |
|---|---|---|
| `mbppplus_Mbpp/260` | L3 | `return 1` → `return None` |
| `humanevalplus_HumanEval/154` | L12 | `return True` → `return None` |
| `humanevalplus_HumanEval/154` | L14 | `return True` → `return None` |
| `humanevalplus_HumanEval/106` | L11 | `return []` → `return None` |
| `humanevalplus_HumanEval/106` | L15 | `return [1, 2]` → `return None` |

⇒ **整支函式回 None 會被擋，某一條分支回 None 擋不住。**
這句話是把「量具只有一個變異體」這個抽象問題變成可見損害的最短路徑，
歷程文寫這一節時應該用它當開頭。

### 4.5 MBPP+ 的 1.000 是低解析度，不是強度證據

32 題裡有 **6 題的變異體總數 ≤ 2**，**全部**在 MBPP+：
`Mbpp/725`(2)、`Mbpp/273`(2)、`Mbpp/251`(1)、`Mbpp/623`(2)、`Mbpp/90`(1)、`Mbpp/723`(1)。
原因寫在 commit 訊息：MBPP+ 的參考解多為一行。
⇒ 「10 題裡 7 題滿分」這個數字**不能**拿來說 MBPP+ 的套件比較強；
分母只有 1～2 個的滿分，解析度本來就低。

⚠ **轉述精確化**：那個「20 題」是 **MBPP+ ＋ HumanEval+ 合計**（`n_tasks` 各 10），
不是 MBPP+ 一家；合計 20 題的中位數 1.000、最低 0.6111。
而 **6 題低解析度全部落在 MBPP+ 這一半**。
`limit=20` 是每題的變異體上限參數，與題數同號但不是同一件事。
（`CLAUDE.md`§程式碼地圖 的 `vacant/suitemutate.py` 條目寫的是合計版「抽樣 20 題」，
與本節一致；引用時別把它讀成 MBPP+ 單獨 20 題。）

### 4.6 誠實邊界與正式名字

`vacant/suitemutate.py` 模組 docstring §1-§4 的四條（改碼不得刪）：

1. **致死率永遠是下界，而且是雙重下界**：(a) 分母只有「我們造得出來的那 N 種錯」，
   變異運算子是一張有限的表；(b) 程式等價性是停機問題的一個實例，**語義未改的變異體
   （文獻稱 equivalent mutant）不可判定**，它們活下來時被算進「沒擋住」，
   所以真值只會**高於**回報值。便宜過濾只做得到「正規化後與基準逐字相同就丟掉」。
2. **致死率 100% ≠ 驗收涵蓋需求**。「這與 suitegauge §3 是同一條保證，只是刻度變細；
   **不准**讀成套件固定點已解。」
3. **正規化基準要自己先過**：`ast.unparse` 往返若改了語義，每個變異體都會「被擋住」
   而分數假性衝到 1.0 ⇒ `verify_baseline=True` 讓它變成可見的 `normalized_passed=False`
   （本次三個題庫 32 題**全部** `normalized_passed=True`，`n_norm_fail=0`）。
4. **只動參考解，不動驗收碼**；`hidden_check` 一處都沒有出現（V/GT 分離）。

**紅線**：致死率**不綁** `GaugeOutcome.ok`。把變異體接成 `commit_suite` 的 `broken_stubs`
會改掉閘門語意、讓 r452c 那批歸檔資料失去可比性。釘住這條的測試是
`tests/test_suitemutate.py::test_outcome_has_no_pass_fail_verdict`。

**正式名字**：**mutation testing**。`suitegauge` 就是只有一個變異體的手工版。
- Yue Jia & Mark Harman, *An Analysis and Survey of the Development of Mutation Testing*
  (2011), IEEE TSE, **DOI 10.1109/TSE.2010.62**（`C_僅書目`，crossref-doi）。
  `docs/LITERATURE_GAP_2026-09-18.md` 逐字：「**確認了 caller 的猜測**——我們 `suitegauge`
  的『已知壞樁』在方法論上就是**手工的變異體（mutants）**…應該直接改用這個術語。」
- René Just et al., *Are mutants a valid substitute for real faults in software testing?*
  (2014), FSE, **DOI 10.1145/2635868.2635929**（`C_僅書目`）——實證 mutant 與 real fault
  的偵測相關性優於覆蓋率，替壞樁法提供「它確實量到東西」的背書。
- Petrović & Ivanković, *State of mutation testing at Google* (2018), ICSE-SEIP,
  **DOI 10.1145/3183519.3183521**（`C_僅書目`）——工業規模實踐。
- ⚠ **反駁/邊界**：Inozemtseva & Holmes, *Coverage is not strongly correlated with test
  suite effectiveness* (2014), ICSE, **DOI 10.1145/2568225.2568271**（`C_僅書目`）。
  逐字對應：「我們若在展場用任何『覆蓋/通過比例』當品質代理，這篇會打臉；
  量具只能講『擋住了哪些具體壞樁』，不能升格成品質分數。」
- Zhu, Hall, May, test adequacy 經典框架，**DOI 10.1145/267580.267590**（`C_僅書目`）——
  「單邊保證」在術語上就是 adequacy criterion 的已知弱點，不是新概念。

**效能**（展場排程用得到）：0.14 s／變異體（空 check 基準 0.138 s ⇒ 行程啟動主導）；
一題 20 個變異體＝22 次沙箱＝3.13 s。**並行有幫助**：同樣 20 次，4 執行緒 0.81 s、
8 執行緒 0.70 s ⇒ 先前「並行沒幫助」的說法在本機不成立（子行程等待會放掉 GIL）。

### 4.7 這一節與第三節的關係（寫歷程文時要接起來）

§三 問的是「稽核**掃**了誰」，§四 問的是「稽核**用什麼尺**量」。
兩個都是同一個錯的兩種型態：**「沒有檢查」冒充「沒有違規」**。
§三是範圍漏了（少掃七條臂），§四是刻度太粗（只有一個變異體）。
`suitegauge` 的 docstring §3 早就把刻度太粗寫下來了——那句話從 R449 就在，
這一天做的事只是**把它從一句誠實邊界變成一個可量的數字**。

---

## 五、附身級研究：最小可行是 launcher 不是 proxy

### 5.1 核心洞察

> **「宣告完成」只有要注入回對話時才需要偵測；只要攔交付，觸發點是 agent 行程結束。**

這一句把整個問題的成本結構翻過來。要在對話中途插話，你必須理解 agent 的迴圈狀態
（它現在在第幾輪、下一則訊息要接在哪裡、有沒有待處理的自動重試）；
要攔交付，你只需要知道行程什麼時候結束、工作區長什麼樣。
前者要附身在 agent 裡面，後者只要包住 agent。

R530 的原始碼就是這個形狀的存在證明：`openwork_arms.py:699-700` 的「宣告完成」判定，
用的是 `wshash.tree_manifest(paths.cell_dir)` 的 `ws_sha256` 有沒有變——**看工作區，
不看模型說了什麼**。

### 5.2 五個附身面的比較

| 面 | 涵蓋率 | 七階 | 一個開關切不切得動 | 主要成本 |
|---|---|---|---|---|
| 模型端點 proxy | 所有走該端點的推論 | **L3**（加 `iptables -m owner` 出網封鎖才到 L4） | 切得動（換 base_url） | 不擁有迴圈狀態，見 §5.3 |
| MCP gateway | 只有走 MCP 的工具呼叫 | L2–L3 | 切得動 | 不走 MCP 的路徑完全看不到 |
| 框架擴充 API（pi／OpenCode 的 extension） | 該框架的全部迴圈事件 | **L4** | 切得動（`--no-extensions`） | 綁定單一框架；換框架要重寫 |
| 行程／OS 層（launcher＋沙箱） | 該行程的全部檔案與網路行為 | **L4–L5** | 切不動（由外部 spawn） | 要自己起行程；看不到對話內容 |
| 驗收期收件口（controller） | 只有走進來的交付 | L3 | 切得動（不走進來就好） | 完全不涵蓋沒走進來的 |

**結論**：要「不能出貨未驗證的東西」，最小可行是**攔交付的 launcher**（第四列），
不是 proxy（第一列）。proxy 單獨只有 L3。

### 5.3 外部調查：13 個 LLM proxy／gateway，沒有一個做到那件事

調查對象：LiteLLM、Portkey、NeMo Guardrails、Kong（AI Gateway）、Invariant、
Cloudflare（AI Gateway）、OpenRouter、agentgateway、Envoy（AI 擴充）、Helicone、
Langfuse、LlamaFirewall、mitmproxy。

**結論**：**沒有任何一個做到「偵測完成 → 驗收 → 注入讓 agent 繼續」。**
它們做的是計費、路由、快取、觀測、內容過濾、拒絕單次請求。

**架構理由（這一句是本節最可引用的）**：

> **proxy 只擁有一次 HTTP 往返的讀寫權，不擁有 agent 的迴圈狀態。**

它可以改一則 request／response，但它不知道「這一輪之後 agent 會不會再問一次」，
也沒有地方把一則新的 user 訊息塞進 agent 的訊息陣列。那個陣列在 agent 行程的記憶體裡。

⚠ **落盤缺口（必須先補才能引用）**：這 13 個產品的調查是當天線上做的，
**repo 內沒有任何落盤證據**。依 `CLAUDE.md`§對外發布與存證，
「用過、引用過的東西都要有落盤證據」（A 全文／B 僅摘要／人工核對引文三級，含 sha256），
所以引用進歷程文或展場之前，要先跑一次 `examples/archive_citations.py` 把這 13 筆
（官方文件頁）落盤，拿不到的也要記下拿不到。**在補上之前，這一節只能當工作筆記。**

### 5.4 為什麼不做注入

技術上做得到（`pi.sendUserMessage(..., deliverAs:"followUp")` 就是），**但我們刻意不從
proxy 那一側做**。理由不是工程上的，是立論上的：

> 從 proxy 注入會**在 agent 的歷史裡留下模型從未說過的話**，直接傷害 Vacant
> 「紀錄忠實」的立論根基。

一個宣稱「每一步都可究責」的系統，如果它自己會在被記錄者的紀錄裡偽造訊息，
那條鏈驗得再乾淨也沒有意義。**這一條應該進展場文案**——它是「為什麼我們不做某件
做得到的事」的最好例子，而那類例子比能力展示更能說明可究責。

⚠ 區別要講清楚：R534 的 `vacant_gate.ts` **也會**送 user 訊息回去（§5.5 的第 3 步），
但那是**掛在 agent 自己的擴充點上、以擴充的身分送的**，pi 的 session 紀錄裡它就是一則
外部 user 訊息，沒有偽裝成模型輸出。**差別在於身分有沒有被偽造，不在於有沒有插話。**

### 5.5 R534 的硬資料（pi ＝ 別人的 agent harness）

預註冊正文：`DECISION_20260918_R534_PI_VACANT_VS_PLAIN_PREREG.md`（28,017 bytes，
**狀態：待凍結**——發射前要 Fable 核、人類簽字、ledger 簽入、§九 發射前置全綠）。
⚠ 該檔與 `ops/gain/r534/` 在 2026-09-18 當下**還是未追蹤檔案**（`git status` 的 `??`），
引用前要確認它們已經進版控。

**接線點（逐字可查）**——`ops/gain/r534/pi_ext/vacant_gate.ts`：

- `:35` `import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";`
- `:115` `export default function (pi: ExtensionAPI) {`
- `:205` `pi.on("before_provider_request", (event, ctx) => {`——控推論模式，
  「一通不對就作廢那一格」（`preflight.py` docstring 逐字）。
- `:316` `pi.on("agent_settled", async (_event, ctx) => {`——**閘門點**。
  為什麼不是 `agent_end`，原始碼 :313-315 逐字：「`agent_settled` 的語意就是
  『沒有待處理的自動重試、壓縮或排隊訊息了』…`agent_end` 還可能自動重試，
  所以不能掛在那裡。」

**擴充的四件事（`:1-31` docstring）**：「這支只做四件事：接線、斷言、落盤、轉交」——
**一件判斷都不自己做**。理由逐字：「沙箱、DENY 正則、驗收判準、預算判準在 Python 各只有
一份。在 TS 再寫一份就是第二把會漂的尺，而且漂掉那天沒有人會發現，因為兩份各自都
『看起來對』。」

**誠實邊界（`:28-31`，改碼請保留）**：
「本支 records、asserts and gates，不 proves。它證明『宣告完成之後可見驗收先跑了一次、
沒過就沒出貨』，不證明模型沒有別的路徑繞過 harness，也不證明可見驗收涵蓋真需求（單邊保證）。」

**四格設計**（`ops/gain/r534/piarms.py:55-61`）：

```
"A1": {"arm": "vacant", "think": True},    "A2": {"arm": "vacant", "think": False},
"B1": {"arm": "plain",  "think": True},    "B2": {"arm": "plain",  "think": False},
```

`VACANT_MAX_ATTEMPTS = 2`（凍結）；`PLAIN` **永遠交付**（`asserted = True`），
即使那份碼連 `tests_visible/` 都不過——預註冊 §一逐字「這正是本輪要量的東西」。

**閘門的量具**：`ops/gain/r534/gate_selftest.py`，六條路徑、**零模型呼叫**、合成題目
（刻意不用真題庫，docstring 逐字：「用真題會讓量具的紅綠取決於那一題的細節，
而那正是量具最不該有的性質」）。它自己的誠實邊界也寫死了：
「它**不**證明 pi 那一側真的會照著做——那條由 `run_r534.py` 的真跑與 `pi_ext.jsonl`
的逐筆紀錄承接。兩件事分開量，不要拿這一支的綠當成那一件的綠。」

**冒煙結果（⚠ 未落盤，見下）**：四格第一通 request body 拿掉 `reasoning_effort` 與
cache key 之後 sha256 **逐位元相同**（＝四格的 prompt 面確實只差那一個旗標）；
但 6 個格次裡，「沒過→重改」與拒交在**真模型上 0 次**——2 次宣告完成都第一輪就過、
2 次燒光 token、2 次撞脈絡上限。

**最有資訊量的一筆**：對照組 `B2`（plain＋nothink）**自己跑了 `sh run_tests.sh`**。
偵測它的是 `ops/gain/r534/sidecar.py:78` 的 `looks_like_self_ran_visible()`
（沿用 R530 §四-1 P-W7 的操作型定義，`:378-380` 把 `self_ran_visible` 設起來）。
⇒ **「沒有 Vacant」＝「沒有強制」，不是「沒有測試」。**
這一句對四格對照的解讀是硬約束：兩臂的差不是「有沒有跑測試」，是「跑了之後不過會怎樣」。

⚠ **落盤缺口**：`runs/` 底下沒有任何 `*r534*` 目錄，repo 內也找不到 `pi_ext.jsonl`
或 wire tap 的 JSONL。冒煙是在 1003 上跑的（執行端 2026-08-15 起移到 1003）。
**上面三個數字在本機無法覆核**，引用前要到 1003 取回並落盤。
另：「pi `ExtensionAPI` 12 個 hook」這個數字**在本機無法核回**——
pi 套件沒有 vendored 進 repo，`@earendil-works/pi-coding-agent` 在本機的 bun cache 裡
也找不到（找到的是 `@oh-my-pi/pi-coding-agent@18.2.3`，不是同一個套件名）。
本文件因此**只記我們實際掛的兩個 hook**，不寫 12 這個數字。

---

## 六、外部可用性：乾淨室驗證

### 6.1 PyPI 上放著的是舊架構

`CHANGELOG.md`:5-8 逐字：「**Breaking: this is not an upgrade of 0.6.0, it is a different
codebase.** Anything that imported `vacant.core`, `vacant.protocol`, `vacant.runtime`,
`vacant.mvp`, `vacant.client` or `vacant.composite` will not work. Those modules are gone.」

0.6.0 沒有 `logbook`／`auditor`／`codebench`／`suitegauge`／`research`——
也就是說，**現在 PyPI 上那個版本不包含這個專題的任何一個承重件**。

依賴數字（`CHANGELOG.md`:15-18，逐字）：宣告的 `fastapi` / `anthropic` / `streamlit` /
`sqlmodel` / `alembic` 那一組，乾淨安裝是 **63 個套件**；0.7.0 砍到實際 import 的三個
（`cryptography`、`mcp`、`jsonschema`），**乾淨安裝 30 個**。
`AGENTS.md`:110-111 對外的講法：「`pip install vacant-network` pulls 30 packages
(`mcp` accounts for most of them)」。

⚠ **本機無法核回的兩個數字**：0.6.0 的**發布日期 2026-05-15** 與 **113 個檔案**。
repo 內沒有 0.6.0 的 wheel 或 sdist，`CHANGELOG.md` 也沒有 0.6.0 的條目
（該檔最舊的條目就是 0.7.0）。引用前要從 PyPI JSON API 取回並落盤。

### 6.2 乾淨室的結論

方法：**只給 wheel ＋ README，不給原始碼，在 repo 外的 Ubuntu 上跑**
（`CHANGELOG.md`:41-44 逐字：「An external agent was given the wheel and the READMEs
only — no source — and ran 0.7.0 on Ubuntu.」）。

結論一句話：**「能用，但前提是他手上已經有這個 wheel。」**
理由是 `pip install vacant-network` 裝到的是 0.6.0，README 的 quickstart 第一行就
`ModuleNotFoundError`。⇒ 文件與套件之間的落差不是文件寫錯，是**發布還沒做**。

三個阻擋項的共同形狀（`CHANGELOG.md`:44 逐字）：
**the failure looks exactly like a normal output.**
——與 §三（靜音的跳過）、§二（合法前綴照樣過）是同一個形狀。

### 6.3 最嚴重的發現：產品自己把「沒量到」講成「量到 0」

`vacant bench` 在端點關著時，每一次腦呼叫都失敗 ⇒ 全部被靜靜計成「答錯」⇒
渲染成「plain 0%、vacant 0%、**+0%**」並 **exit 0**。
而 `--base` 的預設值就是 `http://localhost:1234` ⇒ **外部使用者第一次跑就會踩到**。

這違反 `infra_void` 鐵律（09 §3.5；`CLAUDE.md`§鐵律 3）。
`vacant/agent.py:12-17` 的模組 docstring 早就把這條寫死了，逐字：

> `*_void`／`*_measured` 欄位就是為了讓呼叫端分得開「沒量到」與「量到 0」——
> 把前者渲染成後者，是拿一個沒發生的量測去支撐一個比較數字。

`vacant/agent.py:55-64` 的 `infra_void` property docstring 逐字：
「`verified is False` 有兩個完全不同的來源——『模型答錯』與『根本沒問到模型』。
前者是資料，後者是基建故障。**把後者混進分子或分母，等於用一個沒發生的量測去支撐
一個比較數字。**」

**規則在，執行的地方漏了**：`ops/gain/r530/acceptance.py` 與 `vacant record check`
早就是這樣寫的，`bench` 是漏的那一支。

修法（commit 見 §七-4）：三種結局分開（答對／答錯／沒量到）；任一臂成功量測數＝0 ⇒
**不輸出任何比較數字**、印說人話的診斷（端點、逐臂分母、第一個錯誤原文）、**exit 2**；
部分故障時數字照印但 `infra_void` 格數**單獨印**、分母講明。
`Vacant.bench` 多回 `plain_void`／`vacant_void`／`plain_measured`／`vacant_measured`／
`paired_measured`／`infra_void`／`first_error`；**三個比率在分母為 0 時是 `None` 不是 `0.0`**。

⚠ 另外兩個阻擋項（一樣是「錯誤長得跟正常輸出一樣」）：

- **禁語出現在自己的 CLI 輸出裡**：`vacant demo` 印「信任性質」「信任層淨貢獻」、
  `vacant init` 印「信任庫」、`vacant up` 印「只驗信任機制」。
  **只改印給人看的字串**，識別字 `trust_dir`／`trust_card`／`trust_on`／`--trust`／
  目錄名 `trust/` 是 API 表面，一個都沒動。`vacant/mcp_server.py` 的工具 docstring
  **刻意沒動**（那段字會進 agent 的 prompt，改它是改行為）。
  現在由 `tests/test_cleanroom_blockers.py` 掃每一個 argparse help 與
  `demo`／`init`／`up`／`bench` 的 stdout/stderr（`AGENTS.md`§9 `terminology.enforced_by`）。
- **`select_by_quorum` 的參數傳反會偽裝成拒交**：`drafts` 是 `(code, worker_id)`，
  兩格都是 `str`，順序寫在哪裡都沒有。傳反不會有型別錯誤：每一份「草稿」都跑不過驗收
  ⇒ 三方一致投沒過 ⇒ `refused=True`、三條簽章鏈全部驗得過——
  **與「機制正確地拒絕了爛交付」在畫面上一模一樣**，而拒交是本系統的合法輸出。
  加了一道**啟發式**形狀檢查丟 `DraftOrderError`，偽陰性寫在 docstring、寫在例外訊息裡，
  並且有一條測試把其中一個偽陰性釘住——**不准讀成「順序錯一定會被抓到」**。

負向控制：`tests/test_cleanroom_blockers.py` 共 **22 條**，每一項都有負向控制。

### 6.4 反向：19 條誠實邊界逐條去打，一條都沒打破

乾淨室**逐條去打** `README.md`§誠實邊界 的 19 條（`README.md`:192-263，編號 1–19；
`README.md`:420 逐字「上面 §誠實邊界 19 條全部適用」），**一條都沒打破**，
有兩處實際比文件寫的還嚴格。沙箱十個攻擊全擋。

原話（這一句是整個乾淨室最值得引的）：

> **「這份文件在講自己不行的地方上是可信的；問題全部集中在講自己怎麼用的地方。」**

⚠ **落盤缺口**：乾淨室的逐條打擊報告本身沒有進 repo，
「兩處比文件更嚴格」與「十個攻擊」的逐項清單在本機無法核回。
可以核回的是 19 這個數字（`README.md`§誠實邊界 確實是 1–19）。
⚠ 相對地，`AGENTS.md` 的清單是 **I-1…I-7 ＋ H-0…H-12 ＝ 20 條**，與 README 的 19 條
**不是同一份清單**，引用時不要混。

### 6.5 這一節怎麼接回主線

§六與§一是同一件事的兩端：§一問「別人能不能繞過我們」，§六問「別人能不能用我們」。
兩邊的答案都指向同一個結論——**Vacant 的宣稱強度受限於部署，不受限於程式碼**。
而§六多給了一條：**一個宣稱「沒量到不等於量到 0」的專案，自己的 CLI 在最外層違反了它。**
規則寫在 docstring 裡不等於規則被執行；這一天三次證明了同一件事
（§三的靜音跳過、§四的粗刻度、§六的 `bench`）。

---

## 七、給未來寫歷程文的人

### 7.1 六件事怎麼串成一節

建議的骨架（不是六篇流水帳）：

1. **開場**用§三：我們對外講過的一句話是錯的，而且是我們自己抓到的。
   （引 `README.md`:208-215 中文第 3 條，它已經是對外文件的一部分。）
2. **展開**成一個共同形狀：**「沒有檢查」冒充「沒有違規」**。
   三個實例：§三的整條臂被靜音跳過、§四的刻度只有一個變異體、§二的合法前綴照樣過。
3. **加一層**：§六說明這個形狀也會出現在**產品對外的第一個畫面**上
   （`bench` 把沒量到印成 +0%）。
4. **轉折**到§一：那為什麼不乾脆做強制？因為 complete mediation 不是我們選不選的問題，
   是「可選」這個性質的必然後果（Saltzer & Schroeder 1975）。
5. **收尾**用§五：所以下一步不是把 proxy 做大，是把**攔交付**這個最窄的面做硬；
   而且刻意不做注入，因為那會傷害紀錄忠實這個立論根基。
6. **總結句**回到§〇：把宣稱降到可驗證的程度，然後把可驗證的部分做硬。

### 7.2 這一天沒解決的（不要寫成已解決）

- **L6 一個都沒有**：沒有任何利害關係不同的外部主體持有我們任何一條鏈的錨（§二-6）。
- **長度承諾仍然沒有**：`Logbook.head()` 存在，但沒有任何流程把它對外公示（§二-4）。
- **`README.md`／`AGENTS.md` 仍寫著回溯補掃「結果未定」**，而結果已經落盤（§三-8）。
- **§五的 13 個 proxy 調查、§六的乾淨室報告、R534 的冒煙數字**三者都沒有落盤證據
  （§五-3、§五-5、§六-4）。
- **七階量表（L0–L6）沒有單一真相來源**（§一-5）。
- **R534 預註冊待凍結**、`ops/gain/r534/` 當天仍未追蹤（§五-5）。

### 7.3 可重跑清單（零機時、零模型呼叫）

| 要重現什麼 | 怎麼跑 | 約需 |
|---|---|---|
| §二 鏈的三個洞 | `Logbook.append()×5` → 對四種竄改各驗一次；`verify_checkpoint_chain` 對四種竄改各驗一次 | ~1 s |
| §二 README 版 | 直接貼 `README.md`:48-80 的四步程式碼區塊（`run_python_check` ＋ 收據鏈四步） | ~1 s |
| §三 回溯稽核 | `python3 ops/gain/vgt_retro_audit.py`；結果比對 `ops/gain/vgt_retro_audit_20260918.json` | 289.6 s |
| §三 逐臂防呆 | `tests/test_gain_vgt_all_arms.py`、`tests/test_gain_vgt_canary.py` | 秒級 |
| §四 強弱套件負向控制 | `tests/test_suitemutate.py::test_weak_suite_scores_low_strong_suite_scores_high` ＋ `::test_the_gauge_cannot_tell_those_two_apart` | ~10 s |
| §四 三題庫致死率 | `ops/gain/mutation_score_banks.py`；結果比對 `ops/gain/data/suite_mutation_*.json` | 114.6 s（三批合計） |
| §五 閘門六條路徑 | `python3 ops/gain/r534/gate_selftest.py` | 秒級 |
| §六 三個阻擋項 | `tests/test_cleanroom_blockers.py`（22 條） | 秒級 |
| 收據鏈對帳 | `python3 ops/gain/replay/verify_run_receipts.py --selftest` 再 `--glob 'runs/g_r532_*'` | 分鐘級 |

測試一律用 `.venv/bin/python -m pytest tests/ -q`（`CLAUDE.md`§慣例）。

### 7.4 ⚠ commit sha 對照表：每一個都有兩個

`chore/tidy-root` 把三份工作 rebase 過，所以**同一份改動存在兩個 sha**。
引用時要講清楚是哪一條線上的，否則對不上。

| 工作 | 原始 sha（agent worktree 分支） | rebase 後 sha（`chore/tidy-root` 線） | 原始時間 |
|---|---|---|---|
| V/GT 十臂＋回溯 179 份 | `08f570c`（`worktree-agent-ae30ba043177a8329`） | **`584df91`** | 2026-09-18 12:05:17 +0800 |
| 變異致死率 | `6cd3364`（`worktree-agent-a62f9877521127312`） | **`ade0aa3`** | 2026-09-18 11:00:54 +0800 |
| 乾淨室三個阻擋項 | `8b67b10`（`fix/cleanroom-blockers`） | **`9bcf7c6`** | 2026-09-18 12:25:06 +0800 |

⚠ rebase 後的**順序**與原始時間**不一致**（`chore/tidy-root` 上是
乾淨室 → 變異致死率 → V/GT，但原始時間是 變異致死率 → V/GT → 乾淨室）。
這就是為什麼 `README.md`／`AGENTS.md`（寫在乾淨室那一筆）會說回溯補掃「結果未定」，
卻與已經完成的 `vgt_retro_audit_20260918.json` 同在一棵樹裡（§三-8）。
**寫歷程文講時序時，用原始時間，不要用 git log 的順序。**

### 7.5 這一天沒有產生任何新的實驗結果

**沒有任何一個 run 被發射，沒有任何一個新數字進入 `examples/verdicts.py`。**
六件事全部是對既有東西的稽核與對外可用性的整備。
歷程文不要把這一天寫成「又量到了什麼」——寫成「我們檢查了自己的量具，發現三處它在說謊」。

---

## 附錄：本文件引用的所有落盤位置

**程式碼**
`vacant/agent.py:12-17,51-103,55-64` · `vacant/mcp_server.py:184-210` ·
`vacant/mcp_trace.py:24-46` · `vacant/controller.py:7-8,304-530,372` ·
`vacant/logbook.py:132-165,168-195` · `vacant/checkpoint.py:144-155` ·
`vacant/identity.py:42-50` · `vacant/body.py:160` · `vacant/ecosystem.py:641-642` ·
`vacant/peerexec.py:117-120` · `vacant/suitegauge.py:30-33,112-122` ·
`vacant/suitemutate.py`（模組 docstring §1-§4） ·
`ops/gain/harness_vgt_audit.py:746`（修補前）、`CLASSIC_ARMS`／`AUDITED_ARMS`／`scope_arms()`（修補後） ·
`ops/gain/harness_arms.py:65` · `ops/gain/r530/openwork_arms.py:642-696,699-700,714-721` ·
`ops/gain/r530/sandbox.py:371-374,377-421` · `ops/gain/r534/pi_ext/vacant_gate.ts:1-31,35,115,205,313-316` ·
`ops/gain/r534/piarms.py:55-61` · `ops/gain/r534/sidecar.py:78,378-380` ·
`ops/gain/r534/preflight.py`（模組 docstring、`p8_pi_wire`） · `ops/gain/r534/gate_selftest.py` ·
`ops/gain/replay/verify_run_receipts.py`

**落盤資料**
`ops/gain/vgt_retro_audit_20260918.json`（136,117 bytes） ·
`ops/gain/data/suite_mutation_lcb2.json` · `..._mbppplus.json` · `..._humanevalplus.json` ·
`ops/gain/replay/r529/vgt_v2_*.json`（37 份）

**文件**
`AGENTS.md`:51-53,58-61,63-72,74-80,96,99,110-111,365-369,376-385,391-397,398-426,427-434,458-464,481,497-560 ·
`README.md`:56-85,192-263,206-215,420 · `CHANGELOG.md`:3-60 ·
`docs/LITERATURE_GAP_2026-09-18.md`（109 筆；限制 2／限制 3／限制 4 三節） ·
`docs/JOURNEY_2026-09-13.md`（形狀參考） ·
`DECISION_20260918_R534_PI_VACANT_VS_PLAIN_PREREG.md`（28,017 bytes，待凍結、當時未追蹤）

**測試**
`tests/test_suitemutate.py` · `tests/test_cleanroom_blockers.py`（22 條） ·
`tests/test_gain_vgt_all_arms.py` · `tests/test_gain_vgt_canary.py` ·
`tests/test_peerexec.py::test_default_broken_stub_matches_probe_instrument`

**文獻（只列本文件實際引用、且有可查證識別碼的）**

| 引用點 | 書目 | 識別碼 | 取得層級 |
|---|---|---|---|
| §一-3 | Saltzer & Schroeder 1975, *The protection of information in computer systems* | DOI 10.1109/PROC.1975.9939 | `C_僅書目`（crossref-doi） |
| §一 | Lampson 1973, *A note on the confinement problem* | DOI 10.1145/362375.362389 | `C_僅書目` |
| §二-7 | Ma & Tsudik 2009, *A new approach to secure logging* | DOI 10.1145/1502777.1502779 | `C_僅書目` |
| §二-7 | Ma & Tsudik 2007, *Forward-Secure Sequential Aggregate Authentication* | **無 DOI／arXiv** | `C_僅書目`（openalex），**未讀全文** |
| §二-7 | Schneier & Kelsey 1999, *Secure audit logs to support computer forensics* | DOI 10.1145/317087.317089 | `C_僅書目` |
| §四-6 | Jia & Harman 2011, mutation testing 綜述 | DOI 10.1109/TSE.2010.62 | `C_僅書目` |
| §四-6 | Just et al. 2014, *Are mutants a valid substitute for real faults?* | DOI 10.1145/2635868.2635929 | `C_僅書目` |
| §四-6 | Petrović & Ivanković 2018, *State of mutation testing at Google* | DOI 10.1145/3183519.3183521 | `C_僅書目` |
| §四-6（反駁/邊界） | Inozemtseva & Holmes 2014, *Coverage is not strongly correlated…* | DOI 10.1145/2568225.2568271 | `C_僅書目` |
| §四-6 | Zhu, Hall & May, test adequacy 綜述 | DOI 10.1145/267580.267590 | `C_僅書目` |

⚠ 本表**全部是 `C_僅書目`**——經 crossref／openalex API 核回書目正確，
**沒有一篇讀過全文**（`docs/LITERATURE_GAP_2026-09-18.md`§取得層級：本批 A 級 0 筆）。
引用進展場文案前需要有人實際讀過。這一條依 `CLAUDE.md`§唯一交付物 第 3 條——
先行研究重要的理由是**不能對觀眾說錯話**，而只讀題名就轉述別人的結論，正是說錯話的方式。
