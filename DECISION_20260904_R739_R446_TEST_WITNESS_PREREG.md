# R739 判準（量測之前 commit）：給 `test_unknown_signature_does_not_merge_buckets` 一個看得見的 witness

接 R738（commit `02340d9`）。R738 的總判決是 `PARTIAL_TEETH`：11 個正對照突變體抓到 10 個，
**漏掉的正好是 M2**——`_buckets` 把未知簽名 `None` 併成同一桶時，12 條測試全綠。

根因（R738 已手算重現）：那條測試的 view 是 `[None, None, "s", "s", "s"]`，
併桶後未知桶 2 票、`s` 桶 3 票，**3 > 2，兩種語意同一個贏家** ⇒ 這個例子在結構上分辨不出來。
測試檔的註解「兩個 None 若被併成同一桶會變成 2 票」本身是對的，但沒有算下去看 2 票根本贏不了。

本輪要做的事只有一件：**把那條測試補到看得見它自己宣稱守的語意**，然後用同一支突變量具
（`ops/gain/mutation_test_r446_rules.py`）重跑全部對照，看 M2 會不會從 MISSED 變成 DETECTED。

## 一、施工範圍（越界就是違反本判準）

- 准改：`tests/test_equal_budget_rules_r446.py`（只在既有函式 `test_unknown_signature_does_not_merge_buckets`
  內部補 witness ＋ 改正誤導的註解）、`ops/gain/mutation_test_r446_rules.py`（見 §三）。
- **不准改產品碼**：`ops/gain/replay/equal_budget_rules.py` 全程 sha256 必須是
  `1396be786df221be73b1b51d397827d4b30ffc8e4719fe09860e040491204ae9`。
- **不准動活著的 run**（`runs/g_r461_lcb3_three_arm`，PID 2895311）：不殺、不 `git add`、
  不 `git stash` / `checkout -- .` / `reset --hard`。突變一律在 `git worktree` 的獨立 checkout 裡做。

## 二、witness（本判準先寫死，量測前已手算，量完不准改）

`_vote_first` 走 `_buckets` ⇒ 要分辨「併桶／不併桶」，必須讓**合併後的未知桶自己變成多數**，
而且它的最小 index **不是 0**（否則跟平手取最前者同一個答案，一樣分辨不出來）。

| # | 全部 `vis=True` 的 `sig` 序列 | 不併桶（正確） | 併桶（M2） |
|---|---|---|---|
| W1 | `["a", None, "b", None, "c"]` | `_pick(FILTER_VOTE)` → **0**（五桶各 1 票，平手取最前） | → **1**（未知桶 2 票獨大） |
| W2 | `["a", "a", None, None, None]` | → **0**（`a` 桶 2 票） | → **2**（未知桶 3 票） |
| W3 | W1 的 `_vote_dist` | 五桶各 1 票全平手 ⇒ 每人 **0.2** | 只有未知桶 2 票 ⇒ index 1、3 各 **0.5** |

W3 是第二條獨立的看見路徑（分佈而不是單一贏家），刻意跟 W1/W2 走不同的出口函式。

## 三、量具要一起修的一個坑（不是順手，是本輪必要）

`mutation_test_r446_rules.py` 目前寫死 `collected != 12 ⇒ BROKEN`。這是「fixture 寫死絕對數字」，
**測試檔一旦增減一條，14 個對照會全部安靜變成 BROKEN**。本輪改成：先跑一次乾淨基線、
把它的收集數當成期望值（來源是資料不是常數），基線收不到（0）就直接中止。

這個修法本身要有牙齒 ⇒ 新增一個**故意壞掉的對照 B1**（在被測模組插一行語法錯誤）：
它必須被判 **`BROKEN`**，**不准**被判 DETECTED。這是「安靜量不到」那一型的擋門——
沒有 B1，「衍生出來的期望值」有沒有在擋東西是看不出來的。

## 四、事前預測（量完逐條對帳，不准改）

| # | 預測 |
|---|---|
| P1 | 改完的乾淨基線：`collected == 12`（witness 補在既有函式內、不新增測試函式）且 12/12 PASS |
| P2 | **M2 → `DETECTED`**，且**變紅的恰好只有** `test_unknown_signature_does_not_merge_buckets` 一條 |
| P3 | M1、M3–M11 十個仍全部 `DETECTED`，且各自指名的那條測試仍在紅名單裡 |
| P4 | 負對照 N1（語意等價改寫）仍 `MISSED`；M12（桶序改字典序）、M13（`depth is None` 變最好）仍 `MISSED` |
| P5 | **B1（語法錯）→ `BROKEN`**（rc≠0 不算數，判準看的是收集數掉下來） |
| P6 | 產品碼 sha256 全程未變，15 次替換每次 `finally` 還原後都等於 `1396be78…` |
| P7 | 會多冒出一類事前沒預期到的事（照 P5 規則：人眼確認、照實寫、**不算進 P1–P6 的計數、不當場補判準去修**） |

## 五、總判決規則（先寫死，數字落地後照這張表念）

- **`HAS_TEETH`**：P1 ∧ P2 ∧ P3 ∧ P4 ∧ P5 ∧ P6 全部成立（＝M1–M11 十一個全 DETECTED、
  三個預期漏網仍 MISSED、B1 BROKEN、產品碼未動）。
- **`PARTIAL_TEETH`**：M1–M11 有任一 MISSED（要逐條寫出漏掉的是哪條語意）。
- **`BROKEN_HARNESS`**：B1 以外有任何一個對照被判 BROKEN，或 P6 不成立 ⇒ 本輪所有判決作廢，不准引用。
- **推翻條件**：若 M2 補了 witness 仍 MISSED，**不准再加 witness 硬湊到綠**——
  那代表我對 `_buckets` 語意的理解是錯的，要照實寫成 `PARTIAL_TEETH` 並把手算與實測的差異寫進交棒。

## 六、誠實邊界（收官引用時必須一起念）

1. 這支測試守的是**離線重放路徑** `ops/gain/replay/equal_budget_rules.py`。R738 已查證：
   **沒有任何收官文件引用過它算出的數字**（R446 的 +4.04pp 出自線上 run `runs/g_r446_eq5_mbpp`，
   分析工具是 `ops/gain/analyze_eq5.py`，兩條路）。⇒ 本輪修的是**活的死角**，不是已污染的結論。
2. `sig=None` 在已歸檔的 5 個 `equal_budget_facts_*.json`（3940 個候選）裡**出現 0 次**，
   但它在 `equal_budget_rules.py:110-113` 的 except 分支**可達** ⇒ 是「潛在」不是「已污染」。
3. 本輪不重跑任何線上 run，不動 `runs/`。`g_r461_lcb3_three_arm` 的數字只做唯讀同步。
