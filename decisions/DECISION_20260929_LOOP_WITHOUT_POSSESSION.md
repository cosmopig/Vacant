# 裁決：迴圈放在父行程，不要放在掛鉤裡

日期：2026-09-29
分支：`design/loop-without-possession`（從 `main` 開出）
量測來源：`ab_raw/`（60 格 wave 1 + 12 格 wave 2 pilot，R534 與 R535 兩個題庫，opencode 1.18.33，
模型 `stealth/space-bunny-alpha`）
狀態：**設計裁決。效果未量到** —— 免費模型每日 1000 請求在批次中途用盡（見 §六）。

---

## 一、這一份要回答的問題

用戶的目標是一句可證偽的話：

> 下載 pi、下載 vacant ⇒ agent 變強。

而現有形狀在兩個地方做不到，本文件量到了：

| 量到的障礙 | 證據 | 後果 |
|---|---|---|
| **W1 通道中介只支援兩種金鑰變數** | `vacant_network/vrun/envmap.py:272-281` 把 `OPENROUTER_API_KEY` 整個刪掉，只給 `OPENAI_API_KEY`／`ANTHROPIC_API_KEY` sentinel；`discover_keys()`（`:485-489`）只讀 `KEY_VARS` 的 openai／anthropic 兩條 | opencode 的 openrouter provider 在本機就失敗，**1.2 秒內 rc=1，一次 wire 都沒發**（`requests_seen=0`） |
| **W2 opencode 沒有 stop 事件** | `~/.config/opencode/plugin/vacant.js` 只註冊 `chat.message`／`tool.execute.before`／`tool.execute.after`；pi 的同名模板有 `ask("stop", …)`（`adapters/agents.py` 的 PI 模板第 406 行附近），opencode 模板沒有 | 3 個 session、37 個 step 都記進簽章鏈，但**沒有 `stop`／`finding`／`feedback` 事件、沒有 `delivery.md`**。`trace/zerostop.py` 不可達 |
| **W3 我自己的 harness 沒用 `--dir`** | agent 原話：「There is no `TASK.md` in the working directory (`/home/user1/ab-20260928`)」 | 工作區只有一個檔時 100% 失敗；檔多時僥倖成功。arm C 三格崩潰（3 個 `step_start` 後 rc=1，無 stderr，無 429） |

W3 是我自己的錯，已修（`--dir` + `git init workspace`，與 repo 自己的 `opencode_build` 同一形狀）。
W1 與 W2 是 repo 的真實狀況。

## 二、為什麼 W1 與 W2 是同一個設計錯誤

兩者都在做同一件事：**把裁決點放進 agent 行程裡**。

- W1 的裁決點在 agent 的**網路層**（wire proxy），所以 agent 必須用一種 Vacant 看得見的方式取得金鑰。
- W2 的裁決點在 agent 的**回合邊界**（Stop hook），所以平台必須提供回合結束這個事件。

兩者都要求**平台配合**。而平台不配合的時候，整條路徑不是「效果較小」，是**靜默無效**：
W2 的量測是 37 個 step 的完整病歷、簽章鏈驗得過、零個裁決。這比不做還危險，因為
receipt 會看起來是對的。

repo 自己的 launcher docstring 已經預見過 W1 的同型問題並給了判準：

> `requests_seen == 0` 的那一格，收據上與一個真的拒交格只差這一個欄位……所以
> `verify_receipts.py` 現在把它判成 **VOID**。（`vrun/launcher.py` docstring §3）

W2 目前**沒有**同型的判準。這是本裁決要補的第一個東西。

## 三、裁決：迴圈是父行程的，不是掛鉤的

`native_acceptance_bridge.py`（3.7 branch，`ops/eval/`）已經證明了裁決點可以在 agent 行程**之外**：

```
prepare   釘住可見套件、簽契約鎖        ← agent 還沒看到提示詞
（agent 原生跑，完整行為，無 wire 中介）
judge     凍結候選 → 內容定址 → 在凍結副本上重算釘住的套件 → 簽裁決
release   收件端重驗 → 寫入 → 讀回比對
```

量測：20 格中 17 格 accept、3 格 reject，17 格 release 全部 `readback_ok=true`。
**閘門本身不需要 wire，也不需要 Stop hook。** 缺的只有一件事：**迴圈**。
bridge 的 CONFORM 模式把重試交給「外層 harness 開一個新的完整 session」，
但回饋怎麼送到下一個 session 的提示詞裡，bridge 沒有定義 —— 因為它假設了 repair 模式
的 Stop hook，而 W2 說明那條路在 opencode 上不存在。

**所以：把迴圈從掛鉤搬到父行程。**

父行程就是呼叫 agent CLI 的那個行程。任何「是一個可以 spawn 的 CLI」的 agent 平台
都自動獲得 T3 能力，不需要掛鉤、不需要 wire、不需要金鑰變數白名單。
掛鉤從**必要條件**降級成**加速器**（回合內中途回饋），沒有掛鉤也不掉級。

這正是用戶說的那句「main 在無法附身 agent 的時候已經可以增效 loop and goal」：
loop 與 goal 由**收件端**擁有，agent 不需要被附身。

## 四、整合分層：平台給什麼，Vacant 就拿到什麼

| 層 | 平台提供 | Vacant 能做 | 量到的狀態 |
|---|---|---|---|
| **T3** | 可以被 spawn 成子行程，退出碼可讀 | 完整 accept／reject／release ＋重試迴圈 | **可用**（bridge 20 格） |
| **T2** | 會寫檔，事後可讀 | 事後 judge＋release；迴圈需要外部再呼叫一次 | 可用（本裁決） |
| **T1** | 只有 tool-call 掛鉤（opencode） | **只有病歷，沒有裁決、沒有迴圈** | **量到是死的** |
| **T0** | 什麼都沒有 |  手動 `vacant check` | 過時 |

新形狀把 T1 提到 T3（因為 T3 只需要「是個 CLI」），並且 **T1 必須自我宣告**：
掛鉤跑完但沒有裁決時，產出一份明講「本次沒有裁決」的記錄，而不是一份看起來正常的鏈。

## 五、這一份不准宣稱什麼

1. **效果未量到。** 免費模型每日 1000 請求（`X-RateLimit-Limit: 1000`,
   `X-RateLimit-Reset: 1790640000000` = 2026-09-29T00:00Z）在 wave 1 尾段用盡。
   arm B 有 2 格吃到 429，wave 2 pilot 全部 429。**任何跨 arm 的差異都不可歸因給 Vacant。**
2. **wave 1 是天花板效應，不是負效應。** 沒裝 Vacant 的 A 臂 19/20（95.0%）隱藏檢查全對。
   閘門能改善的空間是 0。負的 2 格是 opencode 沒交出檔案（lcb_3584、lcb_3654），
   其中 lcb_3584 的 arm C 對應格是 harness bug（W3）。
3. **同 OS 帳號。** receiver 與 agent 都是 `user1`，所以「工作區外的權威套件」靠的是
   路徑隔離 ＋ `chmod 0444`，**不是**跨帳號強制。bridge 預設拒絕同帳號
   （`--insecure-same-account`），本次是明講的例外。
4. **R535 的預期失敗率是設計意圖，不是量測值**（`bank_manifest.json::honesty_bounds` 逐字）。
   量到之後要與預期並排報。
5. 20 題的檢定力約只看得見 +3.2 pp（repo 自己的審查結論）。RPL 的預期效應量級在
   +2.2 pp 以下，**這批規模看不到**。S1 的 PC 天花板必須先過 0.5，否則整層判
   `CEILING_TOO_LOW`，等於管道問題根本沒被提出來。

## 六、要證偽這個裁決，需要量到什麼

預註冊在 `decisions/prereg/PREREG_20260929_LOOP_WITHOUT_POSSESSION.md`。
三臂，全部 90 題（S1 50 ＋ S2 40），**S1 與 S2 分開報不合併**（R535 裁決）：

- **PC**　`TASK_explicit.md` 當 `TASK.md`，1 次，不閘門不重試。**天花板。**
- **RP0**　`TASK.md`，1 次，不閘門不重試。**地板。**
- **RPL**　`TASK.md`，閘門（bridge judge/release）＋最多 3 次全新 session，
  每次提示詞帶上**可見套件自己的失敗原文**。隱藏檢查永不進提示詞。

主要檢定：`released AND hidden_pass`，RPL 對 RP0，精確 McNemar 雙側。
共同主要（Holm）：RPL 對 PC 的差距是否收斂。
否證條件（任一成立即撤回本裁決的「有效」宣稱）：

1. PC < 0.5 ⇒ 該層 `CEILING_TOO_LOW`，題目對這顆模型太難，本層不作結論。
2. RPL 對 RP0 的 `discordant_total < 6` ⇒ 記為 **unresolved**，不是負結果也不是正結果。
3. RPL 的 wall 與 token 明顯高於 PC，卻沒有把 RP0 拉到 PC ⇒ 「loop 只是燒錢」，
   裁決退回「只做閘門，不做迴圈」。

## 七、為什麼這個方向值得做

Wave 1 真正量到的不是效果，是**三個可以修的具體缺口**，而且其中兩個（迴圈歸父行程、
T1 自我宣告）不依赖任何模型的表現，是可以在 repo 裡直接改完並測的。
W1（金鑰變數白名單）則是純程式修正，量測已經定位到行號。

**下載 vacant 應該等於甚麼**，本裁決的答案是：等於一個不需要平台配合的收件口，
外加一個由收件端擁有的迴圈。平台自帶的掛鉤只讓它更快，不決定它有沒有。
