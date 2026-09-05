# R481：認證漂移擋門的**掃描範圍**——第三型「安靜量不到」的最後一個洞

前置：`DECISION_20260905_R477_CERT_DRIFT_EXECUTABLE_GATE.md`（§10.5.2 第二個洞）、
`DECISION_20260905_R478_CERT_SELF_RECORDED_SHA.md`（§本輪不改 第 113 行：
「掃描範圍仍只有 repo 根 `DECISION_*.md`，R477 §10.5.2 的第二個洞留給後輪」）。

R477 §217–218 逐字：「掃描範圍只有 repo 根目錄的 `DECISION_*.md`（138 份）。`ops/` 底下的
說明、`GAIN_STATE.md`、`SPEC_GAIN.md` 裡若有認證語句，**今天掃不到**」。

⇒ 這是 memory 記的**第三型「安靜量不到」：掃描掃到 0 個目標**。今天 `docs_scanned` 是
掃到的份數，但「**應該**掃幾份」從來沒有被算過。連續三輪（R478／R479／R480）記為待辦。

**本輪只改範圍，判決語意（四種 verdict、rc、豁免、自記 sha 優先）一個字都不改。**

## 一、範圍怎麼定（新增可調參數零）

新範圍 ＝ **舊範圍 ∪ `git ls-files '*.md'`**：

- 舊範圍：`ROOT.glob("DECISION_*.md")`（檔案系統，含未追蹤檔）——**原樣保留**。
- 新增：repo 內所有 **git 追蹤**的 `*.md`。不是我挑的清單，是 repo 自己的內容 ⇒ 沒有旋鈕。
- 取聯集（不是取代）⇒ **新版不可能比舊版少掃**，加法性由構造保證（見 §三 P-3）。

**具名排除（不是安靜跳過）**：
1. `~/vacant/GAIN_STATE.md` —— 在 `ROOT`（`~/vacant/Vacant`）**之外**，且不在 git ⇒
   沒有 blob 可比、沒有認證時刻可反推。本擋門對它**結構上不可能**判 FRESH/STALE。
   ⇒ 輸出要記 `out_of_scope_named`，收官若要引用 GAIN_STATE 裡的認證數字，**本擋門不覆蓋**。
2. 未追蹤的**非** root-DECISION `.md`（例如新寫還沒 commit 的 ops 文件）——沒有 commit
   就沒有認證時刻，掃了也只會吐 `BROKEN_NO_CERT_COMMIT`。刻意不納入。

## 二、順帶要修的一個真缺陷（範圍一擴張就會咬人）

現行 `judge_group` 用 `g["doc"] = doc.name`（**basename**）去 `git log -- <doc>`。
單一目錄時 basename ≡ 相對路徑；**多目錄之後兩份同名 `.md` 會互相污染**
（同 memory：`endswith("paired_ci.py")` 會吃掉 `pooled_paired_ci.py`）。
⇒ 新增 `g["path"]` ＝ **repo 相對路徑**，`git log` 一律用它；`g["doc"]` 原值不動（加法性）。
root DECISION 的 `path == doc` ⇒ 舊格逐字不變。

## 三、事前預測（**落筆時尚未量測**；每條標 intent）

| 代號 | 預測 | intent |
|---|---|---|
| P-1 | 新版 `docs_scanned` **>** 舊版（141） | guard |
| P-2 | root `DECISION_*.md` **之外**含**認證標題行**的文件數 ＝ **0**（這個洞今天是空的） | evidence |
| P-3 | 舊版工具的 `counts`／`cert_headings`／`rc` 與新版限縮到舊範圍的 `legacy_*` **逐鍵相同** | evidence |
| P-4 | 新版 `rc` ＝ 舊版 `rc` ＝ 1（`paired_ci.py`／`r447_gauge_capability.py` 仍 STALE） | guard |
| P-5 | `live_run_reads` ＝ 0 | guard（主 run 未追蹤 ⇒ 結構強制綠燈，**事前就標**） |
| P-6 | 新掃到的文件中，含 `原樣跑過` **字面**（散文亦算）的份數 **≥ 1** | evidence |

「evidence」＝收官可以拿來當佐證；「guard」＝防 infra，強制綠燈是設計如此，不准當證據。

## 四、推翻條件（事前寫死；觸發了照實寫，**不准當場補判準去修**）

1. **P-2 為假**（新範圍真的有認證標題）⇒ 逐條列出 `path`／`line`／`verdict`／工具，
   **不准**把它們排除掉讓 rc 回到舊值。GAIN_STATE 要寫「收官引用那些數字前必須重跑」。
2. **P-3 為假** ⇒ 這就不是加法性改動。必須指名哪一鍵變了、為什麼，寫進本檔的「事後」段，
   **不准改門檻或改判準去湊**。
3. `docs_scanned` 沒有變多 ⇒ 記 `BROKEN_SCOPE_NOT_EXTENDED`，rc=2（範圍擴張根本沒生效）。
4. P-2 若為 0 ⇒ **本輪的擴張在真資料上沒有被行使**。此時牙齒**只**由 §五 的合成夾具與
   M13 證明。收官不准寫「已證明沒有漏掉的認證」，只准寫「新範圍今天是空的」。

## 五、牙齒（判準指名「該看到哪個量變」）

- **F1 合成夾具（正方向）**：在 `ROOT` 底下（**非** root DECISION 檔名）寫一份臨時 `.md`，
  內含一行認證**標題**＋一行 `python3 ops/gain/<某工具>.py`。餵進新範圍 ⇒ 必須多出一個群組，
  且該工具出現在 `distinct_tools`。跑完刪除。
  （它未追蹤 ⇒ 認證時刻反推不到 ⇒ 預期 `BROKEN_NO_CERT_COMMIT`、rc=2。判準指名的量是
  **「該群組存在」**，不是 rc。）
- **F2 合成夾具（負對照）**：同一份臨時檔，`原樣跑過` 只出現在**散文**行 ⇒ 不准產生群組。
  （證明新範圍沿用標題行錨定，沒有順手放寬。）
- **M13_ROOT_ONLY**：把範圍改回舊 glob ⇒ **`docs_scanned` 必須掉回舊值**。
  ⚠ 判準指名的量是 `docs_scanned`，**不是** `counts`——若 P-2 ＝ 0，`counts` 在 M13 底下
  不會變（memory：突變體的判準要挑「那個會變的量」）。
- **M14_BASENAME**：把 §二 的 `path` 改回 basename ⇒ 只有在新範圍存在同名檔時才看得見。
  事前承認：**若 repo 內沒有兩份同名 `.md`，M14 沒有夾具看得見** ⇒ 那就用合成夾具，
  在臨時子目錄放一份與 root DECISION **同名**的 `.md`，兩者的 `path` 必須不同。
- 既有 14 條自檢（M1–M12＋A–G）**全部必須仍然 PASS**，且 `A`／`B` 真資料雙向校準不准變。

## 六、加法性

- 新欄位：`scope_globs`、`docs_scanned_legacy`、`legacy_counts`、`legacy_cert_headings`、
  `docs_new_scope`、`cert_headings_new_scope`、`out_of_scope_named`、`path`。
- **舊欄位一個都不改語意**（`counts`／`counts_raw`／`rc`／`verdict`／`cert_headings` 仍是
  **全範圍**的值——範圍變大它們本來就該跟著變，這才是擋門的目的）。
- R477 落盤的 `ops/gain/data/r477_cert_drift.json`、R478 的新檔**不覆寫**，本輪寫新檔
  `ops/gain/data/r481_cert_drift_scoped.json`。

## 七、誠實邊界

- 本擋門仍只回答「**引用前要不要重跑**」，不回答「那個數字對不對」（R477 §三，一字未放寬）。
- 本輪**沒有**重跑任何被認證的工具，也沒有動任何門檻／窗口／α／n／seed／bank。
- 主 run `g_r461_lcb3_three_arm` 本輪**一個 byte 都沒讀**（G-LIVE 擋門，`live_run_reads` 為證）。
- 本輪**不是盲測**：我在落筆前讀過 R477 §217–218 與 R478 §113 的原文，但**沒有**跑過任何
  擴張後的掃描 ⇒ P-2／P-6 的數字落筆時未知。
