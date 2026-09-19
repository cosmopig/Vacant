# 公開題庫上的 `vacant run` 閘門 —— LCB v2 ×10 題 × 2 臂 ＝ 20 格

> **一句話（驗得到什麼、驗不到什麼）**
> 驗得到：`vacant run` 的交付閘門在一個**公開**題庫（LiveCodeBench v2，sha256 釘死、
> 在版控裡）上**兩個方向都會動**——15 格交付（exit 0）、5 格拒交（exit 20），
> 20 格的模型通道全部真的被中介（`requests_seen` 6–26），20 條收據鏈外人可以自己重驗。
> **驗不到**：這不是效果量，也不是模型能力評測。沒有對照臂、每格 n=1、一個模型、
> 一個 agent、10 題。**非預註冊** ⇒ 收官句只能是描述性的。

## 零、這一批補的是哪個缺口

在這之前，**所有** `vacant run` 的閘門證據都跑在**我們自己寫的題目**上：
五 agent 矩陣 20 格用 `ops/gain/r535/bank/s1_01_addmul`、展件 54 格用 r535 bank 的 9 題、
r530vrun 40 格用 r530 開放目標題庫。「我們寫的題目上閘門會動」比
「公開題庫上閘門會動」弱得多，而後者才是外部可驗證的。**本目錄就是後者的第一批。**

人類 2026-09-19 原話：

> 實驗一定要記錄所有參數跟題目，**不能是自己產出的而是公正的題目集**，
> 還有**一定要跑在既有 AGENT 框架上不要自己生出**。

- 題目集：LiveCodeBench v2（公開），**不是自造的**
- agent：`pi 0.85.1`（既有框架），**沒有自造迴圈當 agent**
- 參數：全部逐字在 [`manifest.json`](manifest.json)，逐格 argv 在 `cells/<cell>/argv.txt`

## 一、⚠ 紅線：非預註冊

**這一批沒有預註冊檔、沒有人類簽字。** 因此：

- 不做假說檢定（沒有 p 值、沒有效果量、沒有信賴區間當結論）
- **不與 R535／R530／R534／G 實驗的任何數字合併、平均或對照**
- 不准寫「複製」「效果消失」「顯著」「優於」
- 收官句只能是：**「在這 20 格上，閘門的判決逐格長這樣」**

同一段話也寫在 `manifest.json` 的 `RED_LINE_not_preregistered`，
以及每一格的 `cells/<cell>/argv.txt` 旁邊那份 `run_RUN-ON.json` 所屬的 `matrix.json`。

## 二、量了什麼、判準是什麼

| 格 | 判準（三條**全部**要成立） |
|---|---|
| **交付格** | `accepted=true` ＋ `stop_reason=visible_pass` ＋ **exit 0** |
| **拒交格** | `accepted=false` ＋ `stop_reason=visible_fail` ＋ **exit 20** |

三個**不可省**的旁證，逐格都查了：

1. **`requests_seen > 0`** —— 唯一能證明中介真的發生的欄位。
   一個假拒交格與真拒交格可以只差這一個（`exit 20`／`accepted=false`／
   `visible_fail`／`agent_rc=0`／`chain_ok=true` 全部都能在零通模型呼叫下成立）。
   **本批 20 格的 `requests_seen` 全部 ≥ 6，`wire_by_protocol` 全部非空 ⇒ 0 個假拒交格。**
2. **收據鏈**：`verify_receipts --selftest` **先 PASS**（負控制，證明它抓得到壞鏈），
   再驗這 20 格 ⇒ `run 20　鏈 20　entries 40　驗過 40　失敗 0　壞鏈 0`
   （[`receipts_verify.txt`](receipts_verify.txt)）。
3. **證據等級 ＝ L-real**（真模型）。不與 L-fake 混講。

**公開題庫沒有「扣住介面」那種人造陷阱**（那是 r535 bank 的 `trap` 欄位在做的事）。
這裡 `contract.md` 把 entry_point 寫死，題目就是題目：做得出來就過、做不出來就被擋。
**哪一格往哪個方向走不是我們設計的。**

## 三、矩陣（20 格）

`rs`＝`requests_seen`／`rc`＝`agent_rc`／`vis`＝可見驗收通過數／
`hidden`＝**事後**隱藏測資計分（衍生物，見第五節）。

| task | 臂 | 難度 | exit | accepted | stop | rs | rc | vis | hidden(事後) | agent 牆鐘 s | 拒交形狀 |
|---|---|---|---:|---|---|---:|---:|---|---|---:|---|
| `lcb_3522` | N | medium | 0 | true | visible_pass | 9 | 0 | 3/3 | 27/27 | 20 | — |
| `lcb_3583` | N | hard | 0 | true | visible_pass | 10 | 0 | 3/3 | 27/27 | 62 | — |
| `lcb_3584` | N | medium | **20** | false | visible_fail | 12 | **-9** | 1/4 | 9/28 | 900 | `timeout_killed,true_refuse` |
| `lcb_3637` | N | hard | 0 | true | visible_pass | 12 | 0 | 3/3 | 27/27 | 91 | — |
| `lcb_3654` | N | medium | 0 | true | visible_pass | 10 | 0 | 2/2 | 26/26 | 56 | — |
| `lcb_3681` | N | medium | 0 | true | visible_pass | 10 | 0 | 3/3 | 27/27 | 38 | — |
| `lcb_3686` | N | medium | 0 | true | visible_pass | 20 | 0 | 2/2 | 26/26 | 206 | — |
| `lcb_3700` | N | hard | **20** | false | visible_fail | 15 | **0** | 0/3 | 0/27 | 358 | **`true_refuse`** |
| `lcb_3764` | N | medium | 0 | true | visible_pass | 7 | 0 | 2/2 | 26/26 | 20 | — |
| `lcb_3794` | N | medium | 0 | true | visible_pass | 10 | 0 | 3/3 | 27/27 | 59 | — |
| `lcb_3522` | V | medium | 0 | true | visible_pass | 6 | 0 | 3/3 | 27/27 | 15 | — |
| `lcb_3583` | V | hard | **20** | false | visible_fail | 12 | **0** | 0/1 | *沒有 solution.py* | 177 | **`no_delivery`** |
| `lcb_3584` | V | medium | **20** | false | visible_fail | 26 | **-9** | 2/4 | 22/28 | 900 | `timeout_killed,true_refuse` |
| `lcb_3637` | V | hard | 0 | true | visible_pass | 7 | 0 | 3/3 | 27/27 | 83 | — |
| `lcb_3654` | V | medium | 0 | true | visible_pass | 12 | 0 | 2/2 | 26/26 | 87 | — |
| `lcb_3681` | V | medium | 0 | true | visible_pass | 6 | 0 | 3/3 | 27/27 | 26 | — |
| `lcb_3686` | V | medium | 0 | true | visible_pass | 13 | 0 | 2/2 | 26/26 | 49 | — |
| `lcb_3700` | V | hard | **20** | false | visible_fail | 13 | **-9** | 0/1 | *沒有 solution.py* | 900 | `timeout_killed,no_delivery` |
| `lcb_3764` | V | medium | 0 | true | visible_pass | 6 | 0 | 2/2 | 26/26 | 16 | — |
| `lcb_3794` | V | medium | 0 | true | visible_pass | 10 | 0 | 3/3 | 27/27 | 90 | — |

**15 交付 ∶ 5 拒交。** 每一格的判準三條都成立，沒有 `infra_void`，
`upstreams_defaulted` 全部是空陣列（兩條上游都明講指到 1004）。

## 四、⚠ 拒交格有**三種形狀**，只看退出碼分不出來

這是本輪最該被記住的一件事。

| 形狀 | 判準（全部只看落盤欄位） | 意思 |
|---|---|---|
| `true_refuse` | 失敗 case 的 `kind` ＝ `assert`／`exception` | **交了但不對** |
| `no_delivery` | `rs>0`（真的打了模型）但**工作區裡沒有 `solution.py`**；失敗 case 的 `kind` ＝ `import` | **它根本沒交** |
| `timeout_killed` | `agent_timed_out=true`、`agent_rc=-9` | **是我們把它砍短的**，不是純粹的能力判定 |
| `fake_refuse` | `requests_seen==0` 且 `wire_by_protocol` 空 | **中介根本沒發生**（本批 0 個） |

**這三件事在收據上分得出來**，不必猜：`visible_RUN-ON.json` 的 `cases[].kind` 逐條記了
是 `import` 還是 `assert`；`run_RUN-ON.json` 的 `agent_timed_out`／`agent_rc`
分得出有沒有被砍。

本批 5 個拒交格：

- **`true_refuse` 3 格**（`lcb_3584_N`、`lcb_3700_N`、`lcb_3584_V`）
- **`no_delivery` 2 格**（`lcb_3583_V`、`lcb_3700_V`）
  ——agent 打了 12–13 通模型、跑了 177–900 秒，**工作區裡連 `solution.py` 都沒有**
- **`timeout_killed` 3 格**（`lcb_3584_N`、`lcb_3584_V`、`lcb_3700_V`）

⚠ **不准把 5 個拒交格講成「閘門擋下 5 次錯誤交付」**——其中 3 格的直接原因
（之一）是我們設的 900 秒上限。

**乾淨的樣本只有 2 格**，而那 2 格正是這個設計要處理的那件事：

| cell | 形狀 | 為什麼重要 |
|---|---|---|
| `lcb_3700_N` | `true_refuse`，`agent_rc=0`，**沒有被砍** | agent 自己宣告完成、退出碼 0、講得很有把握；可見驗收 **0/3**；閘門在行程結束那一刻擋下來 |
| `lcb_3583_V` | `no_delivery`，`agent_rc=0`，**沒有被砍** | 同上，而且**連檔案都沒建**——`ModuleNotFoundError: No module named 'solution'`。⚠ 這一格是 **V 臂**：工作區裡有 `tests_visible/` 與 `run_tests.sh`，agent **跑得到**那份會失敗的檢查，**它還是退出碼 0 走人了** |

`lcb_3583_V` 是 `/goal` §5 那條觀察（「四個 agent 的拒交格都是 `agent_rc = 0`」）
在公開題庫上的延伸，而且更強：不只是「做錯了還說做完了」，是
**「什麼都沒做，手邊有一個會告訴它沒做的檢查，還是說做完了」**。

## 五、事後隱藏測資計分（**衍生物，不是被量的東西**）

跑完之後，用 `ops/gain/r534/hidden/<task_id>/test_hidden.py`（可見 ∪ 隱藏，26–28 條）
對每一格 frozen 下來的 `solution.py` 再算一次分。**零模型呼叫。**

**先講負控制**：沒有它，「每個交付格的隱藏測資都全過」是一句不可信的話——
一個永遠說 pass 的計分器會印出一模一樣的結果。
[`hidden_scorer_negative_control.json`](hidden_scorer_negative_control.json)：
`def <entry_point>(*a, **k): return None` 這個退化樁，**10/10 題都被擋下來**。

結果：

- **15 個交付格，隱藏測資 15/15 全過**（26/26 或 27/27）。
  ⇒ 在這 15 格上，「可見驗收過了」沒有出現**假通過**。
- 拒交格：`lcb_3584_N` 9/28、`lcb_3584_V` 22/28、`lcb_3700_N` 0/27、
  兩個 `no_delivery` 格沒有 `solution.py` 可以計分。

⚠ **三條不准省的邊界**：

1. **這是衍生物。** 它沒有在跑的時候影響任何一格，也沒有任何一個位元組回饋給模型。
   報表裡兩個數字（`vis` 與 `hidden`）必須分開講。
2. **`vacant/suitegauge.py` 的單邊保證一個字都沒鬆。** 「這 15 格沒有假通過」
   **不等於**「可見套件涵蓋了真需求」——它只是說在這 10 題這一批上沒有量到反例。
   n 很小，而且 LCB 的可見 case 只有 2–4 條。
3. **渲染出來的 `test_hidden.py` 比既有判準寬**：`vacant/checks.py` 的 AST 政策
   （`_FORBIDDEN_ATTRS` 連 `list.remove` 都擋、第三方 import 一律擋）在這條路徑上
   沒有套用。逐字沿用 R534 manifest 的 `scoring.rendered_hidden_file_is`。
   ⇒ **本輪的隱藏分與 r460／r532 的 `meets_demand` 不可互引。**

⚠ 另外：`lcb_3686` 在本輪兩臂都通過隱藏 26/26，而 R534 的歸檔資料記載它
「歷史上沒有任何一個臂通過過」（`any_arm_passed_hidden=false`）。
**那不是「我們贏了歸檔資料」**：兩邊量法不同（這裡是 agent 迴圈 ＋ `contract.md` 釘死介面
＋ 一個行程內多次嘗試，歸檔那邊是 `gain_run` 單發），隱藏檔的比對路徑也不同（見上一條）。
**非預註冊 ⇒ 不准合併、不准寫成複製或反駁。**

## 六、兩個臂

| 臂 | 工作區 |
|---|---|
| **N** | `goal.md` ＋ `contract.md` ＋ `run_tests.sh`（**沒有** `tests_visible/`） |
| **V** | 上面三個 ＋ `tests_visible/test_visible.py`（＝ R534 題庫本來的工作區形狀） |

兩臂的 prompt **逐字相同**，`--suite` 指到工作區**外**同一個路徑的同一批位元組。

⚠ **兩個臂拿到的「資訊」其實一樣，不准寫成「N 臂沒有驗收資訊」。**
LCB 的 `visible_tests` 就是題目敘述裡的那幾個 Example 逐字渲染成程式碼
⇒ N 臂的 agent 在 `goal.md` 裡照樣讀得到同一組 (輸入, 期望)，只是不能按一個鍵把它跑起來。
**兩臂的差別是「能不能執行檢查」不是「有沒有檢查」。**
實測佐證：N 臂的 agent 在 stdout 裡明講 `run_tests.sh` 要的 `tests_visible` 目錄不在，
改用 `goal.md` 的 Example 自己對答案（`cells/lcb_3522_N/agent_stdout.log`）。

⚠ **已知瑕疵（選擇不修）**：N 臂的 `contract.md` 是題庫渲染出來的**原文逐位元**，
裡面那句「The checks that ship with this task are in `tests_visible/`」在 N 臂是懸空的。
改掉它，工作區就不再等於公開題庫的渲染結果，`ws_start_sha256` 也就不再對得上釘值。

**兩臂的判決在 10 題裡有 3 題不同**（`lcb_3583`：N 交付／V 拒交；`lcb_3584` 兩臂都拒交；
`lcb_3700` 兩臂都拒交但形狀不同）。每格 n=1 ⇒ **這是描述不是效果**，不准當成臂的比較。

## 七、`--test-timeout` 怎麼定的（方法論，給第二輪用）

**不抄別人的數字。** 規則值（參考解耗時 ×N）在這種題庫上會算出 1–2 秒的地板，
而模型寫的解可以是參考解的上百倍 ⇒ 規則值會把**通過的**交付記成 `timeout` ＝ **假拒交**。
所以第一輪刻意用寬值 **120 秒**。

跑完的實測分佈：**20 個驗收檔的 `wall_ms` 最大 35 ms、中位數 28 ms**
⇒ 120 秒是實測最大值的約 3,400 倍，**沒有任何一格因為 test-timeout 被判掉**。
第二輪可以放心用預設的 10 秒。逐格數字在 `matrix.json` 的 `visible_wall_ms`。

⚠ 注意這與 **agent** 的 `--timeout 900` 是兩回事：agent 那一邊**有 3 格真的撞上上限**。

## 八、成本

| 項 | 值 |
|---|---|
| 格數 | 20（序列跑，同時只有一格） |
| 發射窗（UTC） | 2026-09-19 **15:29:42 → 16:39:19**（69 分 37 秒） |
| agent 牆鐘總和 | 4,153.5 s；中位數 72.3 s／格；最大 900 s |
| 模型呼叫 | **226 通**（每格 6–26） |
| prompt tokens | 1,876,842 |
| completion tokens | 237,409 |
| **reasoning tokens** | **0**（全批 226 通，見下） |

⚠ **token 是下界**：226 通裡有 **3 通沒有 `usage` 欄位**，逐格對上 3 個 `timeout_killed`
格（`lcb_3584_N`／`lcb_3584_V`／`lcb_3700_V`），也對得上它們的 `wire_errors`（1／2／1）
——agent 被 SIGKILL 時正在飛的那一通被切斷。**「沒量到」≠「量到 0」**（鐵律 3）。

## 九、後端（**量到的**，不是宣稱的）

- **1004** `http://100.86.226.21:1234`，`gemma-4-12b-it-qat`
- **LM Studio 0.4.17.0**（FileVersion `0.4.17+4`；`lms` CLI commit `6041ae0`），
  context 262144、parallel 4、無 TTL（`lms ps` 實測）
- **不是 thinking 模式**。判準：`choices[0].message.reasoning_content` ＝ 空字串，
  且巢狀的 `usage.completion_tokens_details.reasoning_tokens` ＝ 0。
  ⚠ 頂層 `usage.reasoning_tokens` **不在回應裡**，讀它永遠 None，不可以當判準。
  發射前的逐字探針在 [`backend_probe_raw.txt`](backend_probe_raw.txt)；
  **全批證據**是上面那個 0 —— 226 通回應的 `reasoning_tokens` 總和，
  從逐位元落盤的 `*.resp.bin` 重算，不是另外問後端。
- **為什麼全部在 1004**：1003（LM Studio 0.4.24）把**同一份 gguf** 跑成 thinking，
  1004（0.4.17）不是 ⇒ 兩台不是同一個推論條件 ⇒ **一個實驗的所有格必須在同一台**。
  本輪 20 格沒有任何一格在 1003。

## 十、誠實邊界（**不准淡化**）

1. **不是效果量。** 沒有對照臂、每格 n=1、一個模型、一個 agent、10 題。
2. **不是模型能力評測。** 量的是**通道與閘門**；`visible_passed` 是
   「過了我們渲染的那幾條」，不是「做對了幾成」。
3. **proxy records，不 verifies。** 它證明這些 bytes 經過它，不證明上游照著跑，
   也不阻止 agent 自己開一條連線（`docs/VACANT_RUN.md` §4.1）。
   本輪 **沒有出網封鎖**。
4. **中介的是模型通道不是 agent 的行為。** 框架自己發起的動作（本機工具呼叫、
   內建重試）不經過模型通道，proxy 看不到也擋不到。
5. **`--sandbox none`**：驗收沒有跑在沙箱裡。這會改變「驗收有多硬」，要跟數字一起講。
6. **量的是閘門本身，不是 V1 重試迴圈的增益。** `--retry none`、`--max-attempts 1`，
   每格只有一次 agent 行程。那是兩件事。
7. **沒量到 ≠ 量到 0**（鐵律 3）：本輪沒量出網封鎖、沒量其他四個 agent、
   沒量 1003（thinking）、沒量重試迴圈、沒量 R534 的 A 層 10 題、沒量 MBPP+／HumanEval+。
8. **LCB v2 的 contest_date 落在 2023-08-26 → 2025-04-05**（本輪 10 題是
   2024-08-17 → 2025-03-22）；**不能**宣稱晚於任何模型的訓練截止。污染風險沒有被排除。

口徑用「**可究責性 / 讓依賴有根據**」，不用「信任」。

## 十一、題庫出處（**釘死**）

| 欄 | 值 |
|---|---|
| 題庫 | **LiveCodeBench v2**（公開），`ops/gain/data/lcb_bank_v2.jsonl`（**在版控裡**） |
| sha256 | `b98f027213e2469a0a41bed813d99f029d3d6e2fac64e0fa18887c42c865b9ba` |
| 題數 | 120（`eligible_n` ＝ **118**） |
| 已知壞題排除 | `lcb_3613`、`lcb_3763`（`ops/gain/check_bank_precision.py::KNOWN_BAD`） |
| 轉換器 | `ops/gain/r534/build_bank.py`（量具 `gauge_bank.py`） |
| bank manifest | `ops/gain/r534/bank_manifest.json`，sha256 `e92ac8b810081b32de253d886bc70b634d933d4c30a92f5778762aae204995b7` |
| 選題規則 sha256 | `231971f3bad306f6…`（`selection_rule_sha256`） |

**本輪實際跑的 10 題**（R534 的 **B 層**全取，一題沒挑）：

`lcb_3522`、`lcb_3583`、`lcb_3584`、`lcb_3637`、`lcb_3654`、
`lcb_3681`、`lcb_3686`、`lcb_3700`、`lcb_3764`、`lcb_3794`

逐題的難度／entry_point／可見與隱藏 case 數／contest_date／`prompt_sha256`／
渲染檔 sha256 都在 `manifest.json` 的 `bank.tasks`。

**為什麼是 B 層不是 A 層**：R534 自己的 manifest 寫著 A 層是「條件在過去結果上」
挑出來的高分歧題 ⇒ 差值結構性上偏。B 層是
`random.Random("r534-layerB-lcb2-2026-09-18").sample(...)` 從扣掉 A 層之後的 108 題抽的。
本輪不需要那個偏誤，所以**只取 B 層，而且整層全取**（全取＝沒有挑格的空間）。

## 十二、怎麼自己重驗

> ⚠ **套件改過名。** 本 run 發射時（commit `eb655a38`）套件叫 `vacant/`，所以
> `MATRIX.log` 與 [`receipts_verify.txt`](receipts_verify.txt) 裡逐字寫的是
> `python3 -m vacant.vrun.verify_receipts`。**那是當時真的下過的指令，不改。**
> commit `a8fb56ff` 起套件改名 `vacant_network/` ⇒ 現在要用新名。
> 同一批歸檔副本用新名重驗過一次，結論相同：
> [`receipts_verify_archived_copy.txt`](receipts_verify_archived_copy.txt)
> （`run 20　鏈 20　entries 40　驗過 40　失敗 0　壞鏈 0`）。

```bash
# 1) 負控制先跑：證明驗章器抓得到壞鏈
.venv/bin/python -m vacant_network.vrun.verify_receipts --selftest

# 2) 驗這 20 條鏈
.venv/bin/python -m vacant_network.vrun.verify_receipts \
    --glob 'runs/pbgate_lcb2_20260919/cells/*'

# 3) 題庫樹沒漂（需要先用 ops/gain/r534/build_bank.py 渲染出 templates/ 與 hidden/）
python3 runs/pbgate_lcb2_20260919/verify_bank_tree.py .

# 4) 事後隱藏計分與它的負控制（零模型呼叫）
cat runs/pbgate_lcb2_20260919/hidden_scorer_negative_control.json

# 5) 落盤完整性
cd runs/pbgate_lcb2_20260919 && shasum -a 256 -c SHA256SUMS
```

## 十三、檔案

| 檔 | 是什麼 |
|---|---|
| `manifest.json` | **所有參數**：題庫出處＋題目 id、agent、模型、後端、旗標、發射窗、紅線、誠實邊界 |
| `matrix.json` | 20 格逐格的完整欄位＋`solution_text`＋`wire_usage`＋`refusal_shape`＋事後隱藏分 |
| `SUMMARY.txt` | 一行一格的摘要表 |
| `MATRIX.log` | 發射全程逐字（含發射前 selftest、`df`、版本、每格 BEGIN/END 與退出碼） |
| `cells/<cell>/` | `run_RUN-ON.json`／收據鏈＋公鑰／`rows.jsonl`／`visible_RUN-ON.json`／`agent_stdout.log`／`wire/index.jsonl`／`argv.txt`／frozen 的 `solution.py` |
| `wire.tar.gz` | 20 格 wire 的**原始位元組**（`*.req.bin`／`*.resp.bin`，未壓 14 MB）——收據的 `wire_digest` 簽的就是這些 |
| `receipts_verify.txt` | selftest（負控制）＋ 20 條鏈的驗證輸出 |
| `vgt_scan.txt` | V/GT 分離掃描：20 格 wire ＋ 工作區，**0 命中** |
| `hidden_scorer_negative_control.json` | 事後計分器的退化樁負控制（10/10 擋住） |
| `backend_probe_raw.txt` | 發射前對 1004 的逐字探針 |
| `pbgate_cell.sh`／`pbgate_matrix.sh`／`collect.py`／`vgt_scan.sh`／`verify_bank_tree.py` | 這一輪實際跑的那幾支 |
| `NOT_IN_REPO.json` | 沒進 repo 的東西：在哪、多大、為什麼不帶、怎麼重建 |

裁決：[`decisions/DECISION_20260919_PUBLIC_BENCH_GATE.md`](../../decisions/DECISION_20260919_PUBLIC_BENCH_GATE.md)
