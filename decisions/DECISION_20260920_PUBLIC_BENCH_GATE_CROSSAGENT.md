# DECISION 2026-09-20 — 公開題庫上的閘門，**換三個 agent 框架**再跑一次

> **狀態：非預註冊。** 這一份記的是一批**描述性**觀測，不是假說檢定。
> 不准與 R535／R530／R534／G 實驗的任何數字合併、平均或對照；
> **也不准與 `runs/pbgate_lcb2_20260919` 相減當成效果量**——兩批都是非預註冊，
> 兩個描述性觀測相減不會變成檢定。
> 不准寫「複製」「效果消失」「顯著」「優於」。

- run：[`runs/pbgate2_agents_lcb2_20260920/`](../runs/pbgate2_agents_lcb2_20260920/)
- 發射窗（UTC）：**2026-09-19 18:19:56 → 19:14:12**（約 54 分鐘，**3 條 lane 並行**）
- 執行端：vacant-dev `user1@100.124.254.83`；repo 子集 commit `b5654eac`
- 後端：**1003** `http://100.119.113.56:1234`，`gemma-4-12b-it-qat`，
  LM Studio **0.4.24+1**，**thinking 模式**（量過，見 §五）
- 證據等級：**L-real**（真模型）

## 一、為什麼開這一批：擴大 `c606132d`

`c606132d`（`runs/pbgate_lcb2_20260919`）第一次把 `vacant run` 的閘門放到**公開題庫**上，
20 格。它自己在誠實邊界第 7 條列了「沒量到」清單，其中兩條是：

> 沒量其他四個 agent、沒量 1003（thinking）

**本輪兩條一起補。** 三個擴大方向的取捨：

| 方向 | 補的缺口 | 判斷 |
|---|---|---|
| (a) 同題庫加題數 | 樣本數 | ✗ 缺口不是樣本數。非預註冊本來就不做檢定 |
| (b) 換另一個公開題庫（LCB v3／MBPP+／HumanEval+） | 「只在一個題庫上成立」 | △ 真缺口，但**閘門本身跟題目無關**——它讀的是 `--suite` 渲染出來的驗收結果，換題庫主要換的是題目難度 |
| (c) **換另一個 agent** | 「只在一個 agent 上成立」 | ✓ **選這個** |

(c) 之所以是最貴重的那一個：閘門要成立，前提是**模型通道真的被中介**，
而那一層**是逐框架的**——協定不同、接線位置不同、失效模式不同。
這正是三條原則裡第一優先那條（`.claude/commands/goal.md`：「Vacant 要能附身在任何 agent 上」）
直接要的東西。本輪三個 agent 涵蓋**兩條不同的 wire 協定**：

| agent | 版本 | wire | 接線 | 輸出上限（request body 實測） |
|---|---|---|---|---:|
| **pi** | 0.85.1 | `POST /v1/chat/completions` | `wrap_agent.sh` 換設定目錄 | `max_completion_tokens` **16384**（**我們設的**） |
| **Claude Code** | 2.1.278 | `POST /v1/messages?beta=true`（**Anthropic Messages**） | **零接線** | `max_tokens` 32000（框架預設） |
| **OpenCode** | 1.18.31 | `POST /v1/chat/completions` | `wrap_agent.sh` 自訂 provider | `max_tokens` 32000（框架預設） |

三條原則逐條對照：

| 原則 | 本輪怎麼滿足 |
|---|---|
| 具體成果、低 token | 30 格、54 分鐘、23.9 萬 completion tokens。**不跑滿**：10 題不是 118 題、3 個 agent 不是 5 個、n=1、只跑 V 臂 |
| 可被外部驗證 | 題庫公開且在版控裡、sha256 釘死、逐題 id 列出、30 條收據鏈可重驗、逐格 argv 落盤、收尾原因普查可從 `wire.tar.gz` 重算 |
| 跑在既有 agent 框架上 | pi 0.85.1／Claude Code 2.1.278／OpenCode 1.18.31，進入點都是 `ops/vacantrun/wrap_agent.sh`。**沒有自造迴圈當 agent** |

**沒跑 codex／hermes**：codex-cli 0.147.0 在 1003 上有已知的 thinking runaway
（`docs/AGENT_COMPAT.md` §10.7），唯一已驗的緩解 `VACANT_CODEX_REASONING_EFFORT=none`
會**把推理整個關掉** ⇒ 那 10 格就不是與另外三個同一個推論條件，跨 agent 的比較會
混進一個開關。**寧可少一個 agent 也不要多一個不可比的條件。**
hermes 0.19.0 這台**現在根本沒裝**（上一輪是 pip 裝進 `/var/tmp`，已被清）——
**沒量到，不是量到 0。**

## 二、判決：30 格，19 交付 ∶ 11 拒交

| agent | 交付 | 拒交 |
|---|---:|---:|
| pi 0.85.1 | 5 | 5 |
| Claude Code 2.1.278 | 7 | 3 |
| OpenCode 1.18.31 | 7 | 3 |

判準三條（`accepted` ＋ `stop_reason` ＋ 退出碼）逐格都成立。三個不可省的旁證：

1. **`requests_seen` 全部 ≥ 4**（4–14，合計 207 通），`wire_by_protocol` 全部非空
   ⇒ **0 個假拒交格**。
2. `verify_receipts --selftest` **先 PASS**（負控制）再驗這一批：
   `run 30　鏈 30　entries 60　驗過 60　失敗 0　壞鏈 0`，`中介：有 30　零請求 0`。
3. V/GT 分離掃描 **0 命中**；`infra_void` 0 格；`upstreams_defaulted` 全空。

事後隱藏測資計分（衍生物、零模型呼叫）：**19 個交付格 19/19 全過**，
**而且退化樁負控制 10/10 擋得住**——沒有那條負控制，前半句不可信。

## 三、⚠ 主要發現：**閘門三個框架都會動，但「哪一格會動」是逐框架的**

同一個題庫、同一個後端、同一組旗標、同一個 prompt、同一個臂，只換 agent：

**三家判決方向一致只有 4/10 題**（3 題全交付、1 題全拒交），**6/10 題至少有一家不一樣。**

| 可以講的 | 不可以講的 |
|---|---|
| ✅ **「閘門會動」跨框架成立**——三個框架各自都有交付格也有拒交格、每一格都真的被中介、30 條收據都驗得過 | ❌ **「閘門在第 N 題上會擋下來」不跨框架成立**。上一輪記下來的逐格判決，換一個框架就有 6/10 題會變 |

⇒ **任何「閘門擋下 X 格」的數字都是綁在那一個框架＋那一個後端上的，
不可以搬到另一個框架上講。** 這條直接約束展場文案：
`runs/pbgate_lcb2_20260919` 那個「15∶5」不是 `vacant run` 的性質，是 pi×1004 的性質。

拒交形狀（判準只看落盤欄位）：`no_delivery` **8**、`true_refuse` **3**、
`timeout_killed` **2**（都同時是上面某一種）、`fake_refuse` **0**。

⚠ **11 個拒交格裡只有 2 格是被 `--timeout 900` 砍掉的**，其餘 **9 格 `agent_rc=0`、
`agent_timed_out=false`** ——agent 自己宣告完成、退出碼 0 走人，閘門在行程結束那一刻
擋下來。這是 `/goal` §5 那條觀察（「拒交格都是 `agent_rc=0`」）在**三個框架上同時出現**。

## 四、⚠ 第二個發現：5∶7∶7 **不是能力排名**，是接線參數 × thinking 後端

這一條只在 wire 上看得到，`run_*.json` 的欄位裡沒有。逐位元重算 30 格的 `*.resp.bin`：

```
finish_reason = "length" 出現在 6 格：
    lcb_3522_pi  lcb_3584_pi  lcb_3686_pi  lcb_3700_pi  lcb_3794_pi  lcb_3700_opencode
    ⇒ 這 6 格全部是拒交格；19 個交付格一格都沒有
```

pi 的 5 個拒交格逐格長一樣：**前 3 通 `tool_calls`、第 4 通 `length`，pi 就收工了**
（`rs=4`、`agent_rc=0`、工作區沒有 `solution.py`）。其中 4 格的 reasoning tokens
是 **16,406–16,421** ——**16,384 的輸出預算幾乎整份被思考吃掉，工具呼叫沒吐出來。**
而那個 16384 是 **`ops/vacantrun/wrap_agent.sh` 的 pi 段寫死的 `"maxTokens":16384`，
是我們的接線參數**；OpenCode 與 Claude Code 送的是 `max_tokens: 32000`（框架自己的預設）。

⇒ **不准讀成「pi 比較差」。** 上一輪同一個 pi、同一個 16384、同樣 10 題，
跑在**非 thinking** 的 1004 上，**一格都沒有撞到 `length`**。

這與 `docs/AGENT_COMPAT.md` §10.7（codex 在 1003 上的 thinking runaway）是**同一類**
失效——thinking 把預算吃掉、agent 看起來「做完了」而其實什麼都沒交——
但**不是同一個**（那邊是跑不完，這邊是撞上限收工）。兩個現象不要合寫成一句。

**這一條是可以拿去改碼的**（但本輪沒改，也不屬於本輪的授權範圍）：
`wrap_agent.sh` 的 pi `maxTokens` 是個會在 thinking 後端上咬人的常數。
要改的話要先決定「改了之後 r535／展件那批用 pi 的歸檔資料還比不比得起來」。

## 五、後端是量到的，不是宣稱的

- **thinking 判準**：`choices[0].message.reasoning_content` 非空 ＋ 巢狀
  `usage.completion_tokens_details.reasoning_tokens` > 0。
  發射前探針 1003 ＝ **523 字元／241 tokens**。
- **負控制**：同一支探針對 **1004** 跑一次 ＝ **0 字元／0 tokens**
  ⇒ 這支量具讀得出差別，1004 的那個 0 是量到的 0。
- ⚠ **頂層 `usage.reasoning_tokens` 兩台都是 `None`**。**讀它永遠 None，不可以當判準。**
  （memory「兩張卡共 8 串」那條，本輪再次確認。）
- 全批證據：207 通逐位元重算，OpenAI 那條 wire 上 reasoning tokens 合計 **93,095**。
- ⚠ **Claude Code 那 10 格的 `reasoning_tokens` 是 0，那是「這條 wire 沒有這個欄位」
  不是「思考是 0」**；同一批 wire 上數得到 **11 個** `thinking` 區塊。
  **兩個數不可換算、不可相加。**

## 六、跟 `c606132d` 對得起來嗎——**只差後端的那 10 格**

本輪的 **pi 10 格**與上一輪的 **pi/V 10 格**：同一個 agent、同一版本、同一組題目、
同一個臂、同一組旗標、同一個 prompt、同一個 `maxTokens`——**只差後端**
（1004 非 thinking → 1003 thinking）。

**方向相同 6/10，翻面 4/10**（舊 7 交付∶3 拒交 → 新 5∶5）。

一致的部分（可以拿來講）：

- 兩輪都是**兩個方向都會動**；兩輪都 **0 個假拒交格**
- 兩輪的收據鏈都 100% 驗得過（20/20、30/30）
- 兩輪的交付格**事後隱藏測資都全過**，兩輪的計分器負控制都 10/10
- 兩輪都出現「`agent_rc=0`、工作區連 `solution.py` 都沒有、還是退出碼 0 走人」

不一致的部分是「**哪一格**」，而歸因分得開：

- **不是題庫差異**：同一個題庫、同一個 10 題、渲染檔 sha256 逐位元相同。
- **不是 agent 差異**：同一個 pi 0.85.1、同一份 `wrap_agent.sh` 接線。
- 剩下能變的只有**後端**，而且 §四 量到了機制。
- ⚠ **一個沒排除的變數**：本輪三條 lane 並行、上一輪嚴格序列。它會讓牆鐘變長，
  但翻面的那幾格 `agent_timed_out=false`、`agent_rc=0`、死因是 token 上限不是牆鐘
  ⇒ **並行解釋不了這 4 格**。**牆鐘的跨輪比較仍然不可用。**

## 七、一個順手抓到的東西：**改名把 `build_bank.py --check` 弄壞了（資料沒壞）**

發射前照紀律先驗題庫樹，`python3 ops/gain/r534/build_bank.py --check` **FAIL**，
50 個檔對不上。查下去：**渲染器漂了不是資料漂了**。
commit `fb7f4bfb`（套件改名 `vacant` → `vacant_network`）的 sed 掃過 `build_bank.py`
的樣板字串，把它**未來**會渲染出來的註解從 `vacant/codebench.py` 改成
`vacant_network/codebench.py`；磁碟上 `templates/`＋`hidden/` 那 100 個檔還是舊字串，
而且與 `bank_manifest.json` 的釘值、與上一輪 manifest 記的 sha **逐位元相同**。

⇒ 本輪**用磁碟上那一份凍結的，沒有重新渲染**，並用 `verify_bank_tree.py` 比對 100 個
釘值（執行端實測 **OK**；負控制：副本改一個 byte → **FAIL** 且印出 MISMATCH）。

這與 commit `c7feccb4` 記的「改名打破了兩樣凍結的東西」是同一件事，**本輪沒有動手修**
（修它要先決定「重新渲染之後 R534／r460／r532 的歸檔資料還比不比得起來」，
那不是這一輪的授權範圍）。**但它現在有第二個目擊者了。**

## 八、誠實邊界（不准淡化）

1. **不是效果量。** 每格 n=1、10 題、一個模型、一台後端。
2. **5∶7∶7 不是框架能力排名**（§四）。
3. **不是模型能力評測。** 量的是通道與閘門。
4. **proxy records，不 verifies**；本輪**沒有出網封鎖**。
5. **中介的是模型通道不是 agent 的行為。**
6. **`--sandbox none`**：驗收沒有跑在沙箱裡。
7. **`--retry none`**：量的是閘門本身，不是 V1 重試迴圈的增益。
8. **三條 lane 並行** ⇒ 逐格牆鐘不可跨輪比。
9. **跨 agent 的結果與後端綁在一起**：三個 agent 全部只在 1003 跑過，
   **沒量** 1004 上的 Claude Code／OpenCode ⇒ 拆不開「框架差異」與「框架×thinking 差異」。
10. **LCB v2 的 `contest_date` 是 2023-08-26 → 2025-04-05**，**不能**宣稱晚於訓練截止。
11. **沒量到 ≠ 量到 0**：沒量出網封鎖、codex、hermes、N 臂、重試迴圈、A 層 10 題、
    MBPP+／HumanEval+／LCB v1／v3。

口徑用「**可究責性 / 讓依賴有根據**」，不用「信任」。

## 九、機器上留下了什麼、清了什麼

本輪在 vacant-dev 上自己建了五個路徑，收官後全部刪除：
`/var/tmp/vacant_pbgate2`、`/var/tmp/vacant_pbgate2_smoke`、`/var/tmp/pbgate2_repo.tgz`、
`/var/tmp/pbgate2_evidence.tgz`、`/var/tmp/verify_bank_tree2.py`。
**`/var/tmp` 底下其他 `vacant_*` 目錄是別輪的，一個都沒動；也沒有殺任何不是本輪起的行程。**
明細在 [`runs/pbgate2_agents_lcb2_20260920/NOT_IN_REPO.json`](../runs/pbgate2_agents_lcb2_20260920/NOT_IN_REPO.json)。
