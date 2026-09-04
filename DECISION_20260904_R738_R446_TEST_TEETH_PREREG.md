# R738 判準（事前）：`tests/test_equal_budget_rules_r446.py` 有沒有牙齒

**寫在任何量測之前 commit。** r737 交棒 #3：這支是**鐵律 1（等預算）**唯一的單元測試，
R446 收官（round700：+4.04pp CI [+0.80,+6.53]）就靠 `_pick` 那幾行的語意。
r737 把它從「收集 0」修成「12/12 PASS」，但 **12 條全綠只證明它會跑，不證明它會叫**。
memory 記著「乾淨 PASS、植入缺陷仍 PASS 的假測試在這個 repo 真的存在」。

## 一、施工環境（不准碰活著的 run）

`runs/g_r461_lcb3_three_arm`（PID 2895311）活著，落盤檔就在工作區。
⇒ **一律在 `git worktree add --detach ~/vacant/wt_r738 HEAD` 的獨立工作區裡突變**，
主工作區一個位元組都不動。⛔ 全程不得 `git stash` / `git checkout -- .` / `reset --hard`。
`.vacant-private` 用 symlink 借過去（它 gitignore、不在 worktree 裡）。

## 二、突變體的造法（memory 的三條硬規則）

1. **突變一律在被測函式內部生效**——直接改原始碼字串，不用 env 旗標
   （memory：`MUTANT` 寫在模組層永遠不生效，輸出長得跟「沒牙齒」一模一樣）。
2. **突變體要跟正式測試在同一個 import 環境**（worktree 是完整 repo 的 checkout）。
3. **判準不准只寫 `rc≠0`**——每個突變體要事前指名**該由哪一條測試叫**。

每個突變體＝一次精確字串替換；**替換前先驗舊字串存在且唯一**，不存在或不唯一 ⇒ 記 `BROKEN`。

## 三、突變體清單與事前指名（誰該叫）

| # | 改什麼（語意） | 事前指名該叫的測試 |
|---|---|---|
| M1 | `FILTER_FIRST` 取 `passers[-1]` 而非 `passers[0]` | `test_filter_first_takes_earliest_visible_passer` |
| M2 | `_buckets` 把未知簽名 `None` **併成同一桶** | `test_unknown_signature_does_not_merge_buckets` |
| M3 | `_vote_first` 平手取**最後者**（`max(max(...))`） | `test_filter_vote_prefers_the_majority_behaviour_among_passers` |
| M4 | `_vote_dist` 對**所有**桶給機率（不限平手桶） | `test_vote_dist_matches_arm_off5_two_stage_uniform` |
| M5 | `_score` 拒交**算通過** | `test_score_counts_refusal_as_failure` |
| M6 | `FILTER_VOTE_FB` 全不過時**拒交**（退化成 FILTER_VOTE） | `test_filter_vote_fallback_never_refuses` |
| M7 | `DEPTH_BEST` 平手取**最後者** | `test_depth_best_picks_deepest_prefix_and_never_refuses` |
| M8 | `OFF5_REPLAY` **偷看 visible**（有 passers 就只在 passers 裡投票） | `test_off5_replay_is_plain_majority_ignoring_visible` |
| M9 | `_pick` 開頭讀一次 `view[i]["hid"]`（**V/GT 洩漏**，其餘語意不變） | `test_pick_never_sees_hidden`（**且其餘 11 條必須仍 PASS**） |
| M10 | `mcnemar` 回**單尾** p（少乘 2） | `test_mcnemar_exact_two_sided` |
| M11 | `boot_ci` 的 `random.Random(seed)` 改成無 seed | `test_boot_ci_is_deterministic_and_brackets_the_point_estimate` |

### 負對照（**必須不被抓到**，否則整組校準無效）

| # | 改什麼 | 要求 |
|---|---|---|
| N1 | `passers` 的 list comprehension 改寫成等價的 `filter(lambda ...)` | **12/12 PASS** |

memory：「只有正對照時，什麼都判 FORCED 也會全綠」⇒ 沒有 N1 這一格，
「11 個突變體全被抓」也可能只是「這支測試對任何編輯都會紅」。

### 事前點名的兩個**預期會漏**（雙向可證偽）

| # | 改什麼 | 事前預測 |
|---|---|---|
| M12 | `_buckets` 回傳順序改成 `sorted(b)`（不再是「各桶第一個成員的抽樣序」） | **MISSED**：`_vote_first` 用 `min(min(...))` 破平手、`_vote_dist` 的斷言轉成 dict ⇒ 桶序沒有任何斷言看得見，但它是 docstring 明文寫的契約 |
| M13 | `DEPTH_BEST` 的 `depth is None` 從「最差」改成「最好」 | **MISSED**：12 條測試沒有一條的 `depth` 是 `None` |

## 四、每個突變體的判決字串（不准事後改）

跑 `python3 ops/run_tests_nopytest.py tests/test_equal_budget_rules_r446.py`，讀**收集數**與逐條結果：

- `collected != 12` ⇒ **`BROKEN`**（＝「安靜量不到」型：突變害 import 壞掉／收集掉下來）。
  **即使 rc≠0 也不算偵測到**（memory：判準不能只寫 rc≠0；突變體放錯位置害 import 失敗也是 rc≠0）。
- 整支 harness crash、沒有逐條報告 ⇒ **`BROKEN`**（memory：crash 收場不算偵測到）。
- `collected == 12` ∧ 事前指名的測試出現在 fail/error 集合 ⇒ **`DETECTED`**。
- `collected == 12` ∧ 有測試紅了但**不是**指名那條 ⇒ **`DETECTED_OFF_TARGET`**，單獨列，**不計入命中**。
- `collected == 12` ∧ 12 條全 PASS ⇒ **`MISSED`**。

## 五、前置條件（任一不成立就停，不准在壞尺上判）

1. `ops/run_tests_selfcheck.py` 在 worktree 裡雙向自檢通過（good 全綠／bad 全被抓／empty `NOT_VERIFIED` rc=1）。
2. **乾淨基線**：未突變時 `collected == 12` ∧ `12/12 PASS`。
3. **每個突變體跑完立刻還原**，還原後檔案 sha256 必須與乾淨版**逐字元相同**；不同 ⇒ 停。

## 六、事前預測（收官逐條對帳）

| # | 預測 | 可能為假嗎 |
|---|---|---|
| P1 | M1–M11 **全部** `DETECTED`（11/11，且各由事前指名那條叫） | 可：任一條漏掉或 off-target 就假 |
| P2 | N1 **不被抓**（12/12 PASS） | 可：若這支對任何編輯都紅就假 |
| P3 | M12 與 M13 **都是 `MISSED`** | 可：被抓到就假（那是對這支測試有利的推翻） |
| P4 | 乾淨基線 `collected == 12` ∧ 12/12 PASS | 可 |
| P5 | 會多冒出一類事前沒預期到的狀況 | 可 |

**總判決**：`HAS_TEETH` ⟺ P1 ∧ P2 成立。P3 為假不影響總判決（只是這支比預期更強）。
P1 有任一 `MISSED` ⇒ 總判決 `PARTIAL_TEETH` ＋ **逐條寫出漏掉的是哪條語意**，
並在交棒明講「R446 的哪一行語意目前沒有測試釘住」。

## 七、本輪的邊界（不准越界）

1. **不改產品碼**：`ops/gain/replay/equal_budget_rules.py` 在主工作區零改動（sha 收尾要驗）。
2. **不改 `tests/`**：本輪只**判**這支有沒有牙齒，補測試是下一輪帶新判準的事。
   （即使 M12/M13 照預測漏了，也**不當場補**——memory：冒出來的照實寫、人眼確認、不當場補判準去修。）
3. **不碰活著的 run**：不殺、不另起、不 `git add` 它的目錄。
4. P5 冒出來的東西：照實寫、人眼確認、**不算進 P1 的計數**。
