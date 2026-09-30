# 預註冊：迴圈歸父行程之後的效果量測（R535 三臂）

日期：2026-09-29
分支：`design/loop-without-possession`
對應裁決：`decisions/DECISION_20260929_LOOP_WITHOUT_POSSESSION.md`
狀態：**未執行**（免費模型每日 1000 請求於 2026-09-29T00:00Z 重置）

本文件在跑之前寫下。**跑完之後不得改判準**；要改就新開一份預註冊。

---

## 一、為什麼要換題庫（wave 1 的天花板）

Wave 1 用 R534 題庫 20 題，沒裝 Vacant 的 A 臂 19/20（95.0%）隱藏檢查全對。
**閘門能改善的空間是 0**，量到的 −10 pp 全部來自 opencode 沒交出檔案，不是 Vacant。
這是題庫的性質，不是機制的性質。

R535 題庫就是為了這個天花板造的。它的 `bank_manifest.json::strata` 逐字寫著：

- **S1**（`介面未給`，50 題）：`TASK.md` 用白話講功能，不給函式名／簽名／回傳形狀；
  可見套件 2–3 條 `check_*` 釘死名字與形狀。
  `expected_first_attempt_visible_fail >= 0.8`。
  角色是**管道的正控制**：回饋充分決定修法，任何會消費回饋的 agent 都救得回。
- **S2**（40 題）：`expected_first_attempt_visible_fail 0.4–0.8`。

⚠ `honesty_bounds` 逐字：**預期失敗率是設計意圖不是量測值。收官時要把實測失敗率跟這個
預期並排報，不可以只報一個。** 本文件遵從。

## 二、量具（跑之前必須全綠，已量）

`python3 ops/gain/r535/gauge_bank.py` → 7 項 × 90 題全綠：

```
1_reference_passes 90/90      2_stakes_blocked 90/90
3a_wrong_name_feedback_names_it 90/90
3b_wrong_behaviour_feedback_has_args_want 90/90
4_no_hidden_in_workspace 90/90
5_task_md_withholds 90/90    6_explicit_diff_is_the_block_only 90/90
```

第 6 項是 PC 臂的閘門：兩份 TASK 若在別處也不一樣，PC 就不再是同一題的天花板。

## 三、三臂

| 臂 | 工作區任務檔 | 嘗試 | 閘門 | 角色 |
|---|---|---|---|---|
| **PC** | `TASK_explicit.md` 改名成 `TASK.md` | 1 | 無 | **天花板** |
| **RP0** | `TASK.md`（介面未給） | 1 | 無 | **地板** |
| **RPL** | `TASK.md`（介面未給） | ≤3 | bridge judge／release | **治療** |

RPL 每次嘗試：凍結候選 → 內容定址 → 在**釘住的**可見套件上重驗 → 簽裁決；
非 accept 時，下一個**全新原生 session** 的提示詞帶上**可見套件自己的失敗原文**。
隱藏樹永不進工作區、永不進提示詞。

⚠ **RPL 的嘗試數是成本，不是本事。** 報告必須同時列出三臂的嘗試數、wall 與 token，
「花了三倍錢換到對」不是結論。

## 四、主要檢定與共同主要

- **主要**：`released AND hidden_pass`，RPL 對 RP0，**精確 McNemar 雙側**。
- **共同主要**（Holm 校正，family = 下列兩條）：RPL 對 PC 的收斂幅度；PC 本身的比率。
- S1 與 S2 **分開報，不合併、不加權**（R535 裁決的 `report_rule`）。

## 五、否證條件（任一成立即撤回「有效」宣稱）

1. **PC < 0.5** ⇒ 該層 `CEILING_TOO_LOW`。題目對這顆模型太難，管道問題根本沒被提出來，
   該層不作任何效果結論。
2. **`discordant_total < 6`**（RPL-對-RP0）⇒ 記為 **unresolved**。
   不是負結果，不是正結果，不是「沒有差異」。
3. **RPL ≈ RP0**（差距 0 pp）⇒ 裁決退回「只做閘門，不做迴圈」。
4. **RPL 的 wall 或 token 明顯高於 PC，但沒有把 RP0 拉到 PC** ⇒ 「迴圈只是燒錢」，
   同樣退回。
5. **PC 與 RP0 幾乎一樣**（差距 ≤ 5 pp）⇒ 這個介面在這顆模型上不構成瓶頸，
   題庫要重挑，不是機制要重寫。
6. 任何隱藏檢查內容出現在工作區或提示詞 ⇒ **整批作廢**（紅線 A4），不是扣一格。

## 六、檢定力（事前算，不是事後說）

repo 自己的審查結論：每題一次、920 題、不一致率約 11.7% ⇒ 80% 檢定力只看得到 +3.2 pp。

本批次是 **90 題 × 1 次**（每臂每題一個觀測，無重複）⇒ 不一致對的期望個數遠小於
90 × 0.117 × (1−arm_correlation)。**所以本批次的規模只夠分辨「整層有沒有動」，
不夠分辨 +2 pp。** 這一條寫在前面，是為了不讓事後的 p 值被讀成比它能承載的更精確。

若要把 RPL 對 RP0 的效應量到 ±2 pp，需要的不只是更多題，而是**每題多次重複**
（`random.Random(seed)` 事先寫死），否則不一致對太少。

## 七、執行環境（全部記錄在 raw data）

- 平台：Ubuntu 24.04，8 core，7.7 GB RAM，無 GPU
- agent：opencode 1.18.33，`--dir <workspace>`，工作區 `git init`
- 模型：`openrouter/stealth/space-bunny-alpha`（定價 0/0）
- Vacant：`fix/native-acceptance-bridge-audit-20260928`（3.7）從原始碼 `pip install`
- 閘門：`ops/eval/native_acceptance_bridge.py` 的 `prepare`／`judge`／`release`
- 收據：`--insecure-same-account`（**明講的例外**：receiver 與 agent 同一個 OS 帳號，
  隔離靠路徑與雜湊重算，不靠跨帳號權限）
- 評分尺：`vacant_network.vrun.acceptance.run_suite`，`suite="hidden"`。**沒有第二把尺。**

## 八、成本事前估算

免費模型帳戶層每日 1000 請求（`X-RateLimit-Limit: 1000`，2026-09-29T00:00Z 重置）。
每次 opencode 執行約 15–20 請求 ⇒ **每日約 50–65 次 agent 執行**。

90 題 × 3 臂 = 270 次執行，**約需 4–5 天**才能跑完。若要更快，唯一辦法是提高額度
或改用付費模型（那把 key 的 `limit_remaining=0`，需先在 OpenRouter 調整）。

**本文件不因為跑不完而縮題庫。** 縮了就要重寫預期失敗率，而那個預期是題庫的性質。
