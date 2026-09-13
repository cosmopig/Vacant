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

---

# 附錄 A：事後（實測；工具 commit `f521117`，判準 commit `6d59c906`）

## A.1 預測帳（§三 落筆時未量）

| 代號 | 預測 | 實測 | 判 |
|---|---|---|---|
| P-1 | `docs_scanned` 變多 | **142 → 252（+110）** | **HIT** |
| P-2 | root DECISION 之外的認證標題 ＝ 0 | **0**（`cert_headings_new_scope=0`、`groups_new_scope=[]`） | **HIT** |
| P-3 | 舊範圍逐鍵相同 | `counts`／`cert_headings`(8)／`docs_scanned`(142)／`rc`(1) 全同，**逐格 6/6 完全相同** | **HIT** |
| P-4 | rc 不變 ＝ 1 | 1 → 1 | HIT（**guard；P-2＝0 之下這條不帶資訊**） |
| P-5 | `live_run_reads` ＝ 0 | 0（`live_paths_skipped` 也 0） | HIT（**事前標為強制綠燈**） |
| P-6 | 新範圍內含 `原樣跑過` **字面**的文件 ≥ 1 | **0**（`git ls-files '*.md'` 扣掉 root DECISION 後，110 份**一份都沒有**） | **MISS** |

⚠ §三 表格把 P-1 的基準寫成「141」，那是抄上一輪 GAIN_STATE 的快照；本輪開場實測舊工具
是 **142**（我自己剛 commit 的判準檔就是第 142 份）。判定改用**同一次實測**的 142 為基準，
結論方向不變。**釘死的數字會過期，這是第二次踩到（R480 G.3 快照也過期）。**

## A.2 推翻條件 4 觸發（照 §四 照實寫，**沒有**當場補判準）

P-2 ＝ 0 ⇒ **本輪的範圍擴張在真資料上一次都沒有被行使**。
⇒ 牙齒**只**由合成夾具與突變體證明：`F1`（非 root 檔的認證標題必須被收進來，heads 8→9、
工具進 `distinct_tools`）、`F2`（同一份檔、標記只在散文 ⇒ 群組 0，標題行錨定沒被順手放寬）、
`M13_ROOT_ONLY`（`docs_scanned` 252→142）、`M14_BASENAME`（見 A.3）。
⇒ **收官不准寫「已證明沒有漏掉的認證」，只准寫「新範圍今天是空的」。**

P-6 也是 0（比 P-2 更強：那 110 份文件裡連**散文**都沒提過這四個字）⇒ 認證這件事至今
100% 集中在 root `DECISION_*.md`。**這是「今天的分佈」，不是規則**——新範圍已涵蓋
`CONCLUSION_*.md`／`CRITERION_*.md`／`ops/**.md`，也就是**收官自己會寫的那些檔**。

## A.3 §二 的 basename 缺陷是真的（不是假想）

`git ls-files '*.md' | xargs -n1 basename | sort | uniq -d` ⇒ repo 內確實有同名 `.md`：
`README.md`／`summary.md`／`CRITERION.md`／`FINDINGS.md`／`RESULT.md`／`anomalies.md`。
今天它們都沒有認證標題，所以 M14 需要合成夾具（§五事前已寫明這一點）。實測：

```
M14_basename_fabricates_cert_commit  PASS
  clean cert_commit=[None,None,None,None] -> M14=['a6ecb9b1','87aec70d','f5cf02db','20bf4a9f']
```

＝ 用 basename 時，子目錄裡的同名檔會**撿到 root 那份的認證時刻**（憑空生出四個認證 commit），
然後拿它去比 blob ⇒ 判決完全是假的。相對路徑版本則老實吐 `BROKEN_NO_CERT_COMMIT`。

## A.4 兩個非預期發現（事前判準沒有涵蓋，照實記）

**A.4.1 ⚠ 本擋門的自檢在**改動前**就已經是紅的（19/20），而且不是本輪造成的。**
釘 `6d59c906`（改動前）把舊工具原始碼 `git show` 出來、放回**同一個 import 環境**重跑：

```
selftest SELFTEST_FAIL 19/20      ← 唯一紅的是 B_realdata_positive_control_stale
  B  FAIL  paired_ci=['CERT_FRESH','CERT_STALE']
```

根因：正對照寫成 `pos == ["CERT_STALE"]`，隱含「**只有一個附錄引用 `paired_ci.py`**」這個
**文件事實**。R478 之後附錄 H 也引用它、且那一格 FRESH ⇒ 夾具安靜衰減成永遠紅
（memory：「fixture 寫死絕對數字 ⇒ 安靜衰減成永遠紅」，這次的分母是**文件**不是 run）。
修法是**提高解析度**、不是放寬：逐 `(附錄, 工具)` 釘死 `C→CERT_STALE`、`H→CERT_FRESH`，
兩個方向都留著。舊寫法與新寫法的原始輸出都貼在上面，後輪可收回仲裁權。

> **這條對收官有直接後果**：R461 附錄 G 的義務是「引用被認證的數字之前先跑 `cert_drift_gate.py`」。
> 那支的 `--selftest` 自 R478 起一直是 `rc=3`。**主判決（`rc=1`、哪兩支 STALE）不受影響**
> ——A.1 P-3 證明逐格判決一格都沒變——但「跑過而且是綠的」這句話在今天之前不成立。

**A.4.2 本輪自己造出過一個回歸，被既有的 M4 抓到。**
範圍擴張後 `M4_NO_DOCS`（第三型「掃到 0 個目標」的安全網）只歸零舊 glob，新範圍還剩 110 份
⇒ 它從 `UNSCANNED/rc=2` 變成 `STALE/rc=1`。**安全網被我拆掉了，而且會印成綠燈那一側。**
已修（M4 同時歸零兩邊），並把它釘成接線測試 `test_third_type_safety_net_survives_wider_scope`。

## A.5 收尾證據

```
selftest SELFTEST_PASS 25/25          （改動前 19/20；新增 H_scope_extended、M13、F1、F2、M14）
verdict STALE_CERTS_PRESENT  rc=1  docs=252  cert_headings=8
  counts={'CERT_FRESH':3,'CERT_STALE':2,'TRIAGED_NOT_A_CERT':1}
  legacy_counts=（同上，逐鍵相同）  docs_scanned_legacy=142  docs_new_scope=110
  cert_headings_new_scope=0  live_run_reads=0  live_paths_skipped=0
tests/test_cert_drift_gate_r477.py   3/3 PASS
tests/test_cert_selfrecorded_sha_r478.py 5/5 PASS
tests/test_cert_scope_r481.py        4/4 PASS
  接線的植入缺陷測試：R477_MUTANT=M13_ROOT_ONLY ⇒ 2/4 FAIL（乾淨版 4/4）＝接線有牙齒
```

**今天 STALE 的仍是 `paired_ci.py`（附錄 C 那一格）與 `r447_gauge_capability.py`**
⇒ 引用 R461 附錄 C.4／E.3／E.4 的數字前，仍要先重跑那兩支。**一個門檻都沒動。**
