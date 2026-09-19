# `vacant run -- <任何 agent 命令>`（V0 ＋ V1 迴圈 ＋ V2 回饋進 prompt）

> 一句話：把任意 agent 包起來，中介它的模型通道，**在它的行程結束那一刻**
> 跑客戶的驗收、簽一張可驗證收據、沒過就擋下交付——
> **V1 再多一件事：沒過就重置或回饋，再 spawn 一次。**
> **V2 再多一件事：那份回饋可以直接接在下一次 spawn 的 prompt 尾端（§8）。**

程式碼：[`vacant_network/vrun/`](../vacant_network/vrun/)
（[`launcher.py`](../vacant_network/vrun/launcher.py)、
[`retry.py`](../vacant_network/vrun/retry.py)、
[`wireproxy.py`](../vacant_network/vrun/wireproxy.py)、
[`envmap.py`](../vacant_network/vrun/envmap.py)、
[`demo.py`](../vacant_network/vrun/demo.py)、
[`verify_receipts.py`](../vacant_network/vrun/verify_receipts.py)）
· 維運側留在 repo：[`ops/vacantrun/`](../ops/vacantrun/)
（[`selftest.py`](../ops/vacantrun/selftest.py)、
[`block_egress.sh`](../ops/vacantrun/block_egress.sh)、
[`wrap_agent.sh`](../ops/vacantrun/wrap_agent.sh)）
· 測試：[`tests/test_vacant_run.py`](../tests/test_vacant_run.py)、
[`tests/test_vacant_run_retry.py`](../tests/test_vacant_run_retry.py)、
[`tests/test_vrun_reexport.py`](../tests/test_vrun_reexport.py)
· **哪些 agent 真的接得上（逐格實測）：[`docs/AGENT_COMPAT.md`](AGENT_COMPAT.md)**

> **2026-09-18 搬家**：判斷層原本住在 `ops/vacantrun/` 與 `ops/gain/r530/`，而 `ops/`
> 不進 wheel ⇒ `pip install vacant-network` 的人跑不動 `vacant run`。改成**搬家＋反轉
> 依賴**：實作進 `vacant_network/vrun/`，`ops/gain/r530/*` 與 `ops/vacantrun/*` 留 re-export
> （`sys.modules` 指過去，**同一個 module 物件**）。所以既有的 83 處 `ops.gain.r530.*`
> 引用一行都沒改，而且**判準仍然只有一份**。理由與清單見
> [`vacant_network/vrun/__init__.py`](../vacant_network/vrun/__init__.py)。
> V1／V2 的政策層 `retry.py` 跟著 `launcher.py` 一起搬——套件不准依賴 `ops/`
> （`tests/test_vrun_reexport.py::test_vrun_is_self_contained`），
> 舊路徑 `ops/vacantrun/retry.py` 同樣是 re-export。

---

## 1. 承重的洞察

> **「宣告完成」之所以難偵測，是因為只有要「注入回對話」時才需要它。
> 如果只是要攔下交付，觸發點根本不在 wire 上——在 agent 行程結束的那一刻。**

那個訊號 100% 可靠、零協定知識、零 token 成本、跨所有框架（連走文字協定的也涵蓋）。

### 為什麼 V0 不做「注入回對話」

兩個理由，任何一個都足夠：

1. **全世界都沒有先例。** 外部調查 13 個 LLM proxy／gateway
   （LiteLLM、Portkey、NeMo Guardrails、Kong AI Gateway、Invariant、OpenRouter、
   Envoy AI Gateway…）**沒有任何一個做到**「在 agent 宣告完成時把驗收回饋
   注入回它的對話並讓它繼續」。沒有先例不等於不能做，但等於那是一整塊研究，
   不是一個 V0 的功能。
2. **它會傷到 Vacant 自己的立論根基。** 注入等於**偽造模型發言或使用者發言**。
   一個把「紀錄忠實」當作全部主張的系統，第一版就先在自己的紀錄裡放一句
   沒有人說過的話，那是自毀。真要做，必須先有一個「這一則是 Vacant 插進去的」
   的可驗證標記，而那個標記的設計本身要另外裁決。

`wireproxy.WireProxy.on_wire()` 是那個掛鉤的位置，**V0／V1 都恆回 `None`（永不改寫）**。

### V1 怎麼在不注入的前提下拿到迴圈

上面那兩個理由**一個字都沒有鬆動**。V1 靠的是同一個洞察再走一步：
既然觸發點是**行程結束**，重試就不必在對話裡發生——
**重置工作區或把失敗原文寫成一個檔，然後再 spawn 一次 agent 就好。**
零協定破解、零偽造發言、跨所有框架。完整規格見 §7。

---

## 2. 用法

```bash
# 先看一次它擋下來：零設定、零模型端點、零 API key、零網路，約 2 秒
vacant demo gate                       # vacant_network/vrun/demo.py

# 最小：把 agent 包起來，用**工作區外**的 tests_visible/ 當驗收
vacant run --suite ../tests_visible --run-dir ~/.vacant-run/demo -- \
    pi -p "把 solution.py 寫完"

# V1：沒過就重試（兩條臂，見 §7）
vacant run --suite ../tests_visible --retry revise   --max-attempts 3 -- <cmd>
vacant run --suite ../tests_visible --retry resample --max-attempts 3 -- <cmd>

# V2：回饋接到下一次 spawn 的 prompt 尾端（見 §8；placeholder 必須在結尾）
vacant run --suite ../tests_visible --retry revise --feedback-into prompt -- \
    pi -p "把 solution.py 寫完{VACANT_FEEDBACK}"

# 純觀測（不 gate），但 wire 照樣逐字落盤
VACANT=0 vacant run --run-dir ~/.vacant-run/demo -- <cmd>

# 不透過 CLI（模組形式，pip 裝完就能用）
python3 -m vacant_network.vrun.launcher --suite ../tests_visible --run-dir /tmp/r -- <cmd>
# repo checkout 裡這一行是同一支（re-export）
python3 ops/vacantrun/launcher.py --suite ../tests_visible --run-dir /tmp/r -- <cmd>
```

⚠ **`--suite` 與 `--run-dir` 都不可以在工作區底下**，兩條擋門都是 `SystemExit`，
理由各自不同：`--run-dir` 是收據自己在長大，放進去會讓 `ws_end_sha256` 變成
「收據寫了多少」的函數；`--suite` 是**agent 改得到的驗收不是驗收**——那不是
「可能被繞過」，是量具與被量的東西放在同一個人手上，`accepted=True` 會退化成
「它讓自己過了」。要給 agent 看驗收就**另外複製一份**進工作區
（`vacant_network/vrun/demo.py::scaffold` 就是這樣做的：權威的那一份在外面）。

退出碼**反映裁決**，不是 agent 自己的退出碼：

| 退出碼 | 意思 |
|---|---|
| `0` | `visible_pass`／`ungated`（`--allow-no-suite`）⇒ 交付 |
| `20` | `visible_fail`／`attempts_exhausted`／`no_suite` ⇒ **拒交** |
| `22` | `infra_void`（TOCTOU、`ws_reset_failed`、`ks1_violation`、agent 起不來）⇒ 不判交付也不判拒交 |
| 其他 | `VACANT=0` 那一臂：透傳 agent 自己的退出碼 |

落盤形狀（`--run-dir`）：

```
rows.jsonl                    一臂一列（arm ∈ {RUN-ON, RUN-OFF}）
receipts_RUN-ON.ndjson        Ed25519 簽章鏈（ws_attempt ×N + ws_verdict ×1）
receipts_RUN-ON.pub.json      公鑰（私鑰不落盤，RECORD_SPEC §7）
wire_RUN-ON/index.jsonl       一通一列的 wire 索引（含 body sha256）
wire_RUN-ON/<call>.req.bin    request body **原始位元組**
wire_RUN-ON/<call>.resp.bin   response body **原始位元組**
visible_RUN-ON.json           第 1 次嘗試的驗收結果
visible_RUN-ON_a2.json        第 2 次以後（V1）
run_RUN-ON.json               summary（含 env 改了哪些、拿掉哪些、`attempts` 陣列）
_frozen_RUN-ON/               第 1 次嘗試驗收跑的那份凍結快照
_frozen_RUN-ON_a2/            第 2 次以後（V1）
_origin/                      `--retry resample` 的起點完整副本（含 `.git`）
```

**第 1 次嘗試的檔名與 V0 逐字相同**，第 2 次以後才加 `_a<n>` 後綴。
哪一次是最後一次由 `run_RUN-ON.json` 的 `attempts` 陣列說了算，不要用檔名猜。

收據用**既有的那把尺**驗，不准另寫第二把：

```bash
python3 -m vacant_network.vrun.verify_receipts --selftest                 # 先證明它抓得到壞鏈
python3 -m vacant_network.vrun.verify_receipts --glob 'runs/<你的 run 目錄>'
python3 -m vacant_network.vrun.verify_receipts --glob ~/.vacant-run/demo-gate/receipts
# repo checkout 裡這一行是同一支（re-export，R460R／R529／R532 的鏈驗的就是它）
python3 ops/gain/replay/verify_run_receipts.py --glob 'runs/<你的 run 目錄>'
```

`--glob` 的相對 pattern：在 repo checkout 裡以 **repo 根**為基準（`runs/g_*` 那種寫法
照舊），`pip install` 之後以 **cwd** 為基準（`vacant_network/vrun/verify_receipts.py::_glob_base`）。
搬進套件之後不能再無條件往上數四層——那會指到 site-packages，而那裡沒有 `runs/`，
於是 `--glob 'runs/…'` 會**靜靜地零筆命中**，零筆命中在本檔的判準裡是 `UNVERIFIABLE`
不是錯誤。**絕對 pattern 兩種情況都照絕對解**——`--run-dir` 本來就多半落在 repo 外
（預設 `~/.vacant-run/<task_id>`），少了這條，畫面上印給使用者複製的那行驗證指令
就是一行跑不動的字。

### 總判有四種，`VOID` 是 2026-09-19 加的

`verdict ∈ {OK, VOID, BROKEN, UNVERIFIABLE}`，退出碼分別是 `0 / 3 / 1 / 1`。

| 值 | 意思 |
|---|---|
| `OK` | 鏈完整，而且每一格 `requests_seen > 0` |
| **`VOID`** | **鏈完整，但有格子 `requests_seen == 0`** ⇒ 那一格沒有中介發生過 |
| `BROKEN` | 鏈本身壞了（簽章／seq／prev_hash／條數對帳） |
| `UNVERIFIABLE` | 沒有公鑰、空鏈、或 glob 零筆命中 |

為什麼要有 `VOID`：2026-09-19 的負控制把 `/bin/true` 放在 agent 的位置，
**一通模型都不打**，而**退出碼、`accepted`、`stop_reason`、`agent_rc`、`chain_ok`
五個欄位全部成立**，驗章器當時的總判是乾淨的 `OK`
（`runs/v1_five_agent_matrix_20260919/controls_receipts_verify.txt` 逐字留著那一行）。
⇒ 尺說得出「這張收據沒被改過」，說不出「這張收據底下有沒有發生過中介」。

**`chain_ok` 一個字都沒改**——零請求的那一格鏈確實是完整的，把它說成壞掉是
另一種說謊。新增的是一個正交的維度：`mediated`（`true`／`false`／**`null`**）
與 `void_reason`。

⚠ **`mediated: null` ＝「這條鏈沒記這件事」**（R460R／R529／R530 的舊鏈都沒有
`requests_seen` 欄位）——**沒量到 ≠ 量到 0**，所以舊鏈一律判 `OK`，
已歸檔 6,468 筆 verdict 的可比性一個字都沒變。

⚠ **誠實邊界**：這個維度擋得住「**完全沒打**」，**擋不住「打了但打到別的地方」**
——那要看 `run_<ARM>.json` 的 `wire_by_protocol` 與 `upstreams`，
而**那兩個欄位不在簽章鏈上**。

⚠ `--allow-no-suite` 那種**刻意沒有驗收**的跑不是假拒交格（它明講「這一次不量」，
而且模型通道照樣可能有流量）⇒ 兩個維度正交，不會互相誤殺。

⚠ **`vacant demo gate` 自己的總判就是 `VOID`**，而且那是規格：那隻假 agent
一通模型都沒打。demo 拿自己當那條負控制。

### 自檢：你的 agent 真的被中介到了嗎

**「我設了環境變數」不是證據，`requests_seen` 才是**（§4.5）：

```bash
vacant run --allow-no-suite --run-dir /tmp/vr -- <你的 agent 命令>
python3 -c "import json;print(json.load(open('/tmp/vr/run_RUN-ON.json'))['requests_seen'])"
# 非 0 ⇒ 模型通道真的經過 Vacant；0 ⇒ 沒被中介到（框架用設定檔，或那一跑根本沒呼叫模型）。
```

可執行證明在 `tests/test_demo_gate.py::test_selfcheck_requests_seen_is_the_evidence`；
零請求那一格被驗章器抓到的可執行證明在
`tests/test_vrun_receipt_mediation.py`（含交付格與拒交格兩種）。

### 沒指定的 upstream ⇒ fail-closed 本機 sink（2026-09-19）

沒有人指定上游的那條 wire ~~會落到公開 API~~ **現在指到
`envmap.SINK_UPSTREAM`**（一個 `.invalid` 主機名）。`wireproxy` 在**開任何連線
之前**就回 502 ⇒ 不解析 DNS、不送任何 bytes、離線也成立。

```bash
# 要走公開 API 得明講（兩個入口等價）
vacant run --allow-public-upstream -- <你的 agent 命令>
VACANT_RUN_ALLOW_PUBLIC_UPSTREAM=1 vacant run -- <你的 agent 命令>
```

逐跑落盤：`upstreams`（含 `fallback: null|sink|public`）、`upstreams_defaulted`、
`upstreams_sinked`、`wire_blocked`。

⚠ **兩條上游都釘死的跑完全不受影響**；那條路上沒有流量的跑也逐位元不變。
⚠ **這擋的是「沒人指定的那條路由」，不是「出網」**——使用者自己指到公開 API
照樣放行，agent 繞過 proxy 直連也照樣擋不住（§5 `block_egress.sh`）。

---

## 3. 開關＝ `VACANT=0|1`

- `VACANT=0` → proxy 走**純 tee**（bytes 原樣轉送、**不 parse 不重序列化**），
  body **逐位元相同**，但**仍然逐字落盤**（鐵律 3 對兩臂都成立）。
- `VACANT=1` → 加驗收＋收據＋拒交。

**設計鐵律：OFF 模式不准 parse-and-reserialize。** 重序列化會改 key 順序與空白
⇒ body sha256 變掉 ⇒「只差一個開關」那條可比性證據就沒了。
R534 已經證過這個性質（四格第一通請求 body 拿掉 `reasoning_effort` 與
cache key 之後 sha256 逐位元相同），這裡沿用。

可執行證明（**這一條紅了就代表設計破了**）：

```
$ python3 ops/vacantrun/selftest.py
[A] VACANT=0（tee）vs VACANT=1（act）：request body 必須逐位元相同
      RUN-OFF  mode=tee  body_sha256=978941442f3d68cc…  bytes=99  stop=ungated
      RUN-ON   mode=act  body_sha256=978941442f3d68cc…  bytes=99  stop=visible_pass
  OK   A1_sha256_identical
  OK   A2_raw_bytes_identical
  OK   A3_upstream_received_the_same_bytes
```

同一條也在 `tests/test_vacant_run.py::test_body_bytes_identical_off_vs_on`。

---

## 4. 誠實邊界（**不准淡化**）

### 4.1 proxy 單獨只有 L3

「agent 一旦被接上就逃不掉」**只有加上出網封鎖才是真的**。
`vacant_network/controller.py:7-8` 原本就寫著：

> 保證只涵蓋透過本 controller 啟動的子行程；無法阻止同一 OS 使用者繞過本命令
> 直接執行 agent。

同一句對 `vacant run` 逐字適用。proxy **records，不 verifies**：它證明
「這些 bytes 經過我」，不證明上游照著跑，也不阻止 agent 自己開一條連線。
要變成 L4 見 §5。

### 4.2 中介的是「模型通道」不是「agent 的行為」

框架自己發起的動作——自動 lint、git checkpoint、內建重試、本機工具呼叫——
**不經過模型通道**，proxy 看不到也擋不到。收據能說的是「模型通道上發生了什麼」
與「工作區最後長這樣」，不能說「agent 做了什麼」。

### 4.3 原理上的洞（三個，都沒補）

1. **不走 HTTP 的模型通道**：兩種都見過。
   (a) **WebSocket**——Codex CLI 用 `codex login`（ChatGPT 帳號）時，模型通道是
   **寫死的 `wss://chatgpt.com/backend-api/codex/responses`**，
   `OPENAI_BASE_URL` 無效、`chatgpt_base_url` 也只搬得動它的外掛／遙測／設定
   那幾條 HTTP 請求（2026-09-18 實測，`RUST_LOG` trace 留檔）。
   一個 request/response 一來一回的反向代理在那條路上**不存在**。
   (b) **權重載進 agent 自己的行程**——llama.cpp in-process、MLX：
   **根本沒有 wire**。
   ⇒ 兩種都讓鐵律 3 的逐字落盤在那條路上不成立。
   唯一的結構性補法是出網封鎖（§5）：封鎖之後那條路會**連不上**
   而不是**偷偷連上**。
2. **Bedrock SigV4**：請求用 body 算簽章，換 Authorization header 會毀簽章。
   本工具不改 body，但金鑰替換那一步在 SigV4 上不成立。
3. **`requests_seen` 會把非模型流量也算進去**。上面 (a) 那一格實測時，假上游
   收到 **16 通**（外掛清單、遙測、使用者設定），**但沒有一通是模型請求**。
   ⇒ 「proxy 有流量」不等於「模型通道被中介到」；要下那個結論得看
   `wire_*/index.jsonl` 的 `path`。

> ⚠ **舊版這裡寫的是「OpenAI Responses API ＋ `store:true` ＋
> `previous_response_id` ⇒ 逐字落盤破功（Codex CLI 走這條）」。那個描述量錯了。**
> 2026-09-18 實測 codex-cli 0.153.2（自訂 provider ＋ API key）：
> `store=false`、沒有 `previous_response_id`、**每一通都重放完整上文**
> （第 2 通 input 有 5 個 item，含 `function_call` 與 `function_call_output`）。
> 在那條路上**逐字落盤是成立的**。真正破功的是上面 1(a)，
> 而它比原本預期的更硬——不是「只看得到 delta」，是**什麼都看不到**。
> 逐格證據見 [`docs/AGENT_COMPAT.md`](AGENT_COMPAT.md)。

### 4.4 「一個開關」有一個星號

開關確實只有一個（`VACANT=0|1`），但 proxy 內部仍需要
**per-wire-protocol adapter（約 4 個：OpenAI Chat Completions／OpenAI Responses／
Anthropic Messages／Google GenAI）**。V0 只實作前面兩條路由的**轉送**
（`wireproxy.route()`，`/v1/messages` ↔ 其餘），因為 V0 不 parse body，
所以轉送不需要懂協定；**一旦要做 §1 的注入，四個 adapter 就都要真的寫出來。**
比 per-framework（幾十個）小一個量級，**但不是零**。

### 4.5 環境變數名單擋不到用設定檔的框架

`envmap.REDIRECT_VARS` 認的是「讀環境變數決定 base url」的框架。
**pi（`@earendil-works/pi-coding-agent`）不是那種**：它的 provider `baseUrl`
寫在 `models.json` 裡，內建 provider 的 baseUrl 甚至是編進 bundle 的常數
（實測：bundle 裡的 `OPENAI_BASE_URL` 只出現在它內嵌的 OpenAI SDK
`readEnv` 預設值上，provider 設定一旦給了 `baseUrl` 就蓋過它）。
那種框架要嘛把設定檔指向 proxy（`--port` 給一個固定埠就是為了這個），
要嘛就**沒被中介到，而且不會有任何錯誤訊息**。

⇒ **「我設了環境變數」不是證據。** 證據是 `run_*.json` 裡的 `requests_seen`
與 `wire_*/index.jsonl` 有沒有東西。這個殘餘風險唯一的結構性補法是 §5：
封鎖之後，沒被中介到的那條路會**連不上**，而不是**偷偷連上**。

2026-09-18 把這一條**兩個方向都量出來了**（[`docs/AGENT_COMPAT.md`](AGENT_COMPAT.md)）：

- **確認**：pi 0.85.1 只設 `OPENAI_BASE_URL` ⇒ 假上游 **0 通**，它跑去
  `api.openai.com` 拿了一個 401。Codex 0.153.2 同樣 0 通。
- **打臉靜態推論**：OpenCode 1.18.31 的 binary 裡 grep 不到 `OPENAI_BASE_URL`，
  照字串判會寫「不吃環境變數」——**實測它吃**（讀變數的是 runtime 才載入的
  `@ai-sdk/openai`，不是 opencode 自己）。**掃 binary 不算量。**
- **好消息**：設定檔框架也不必動使用者的檔案。pi 有 `PI_CODING_AGENT_DIR`、
  Codex 有 `CODEX_HOME`、OpenCode 有 `OPENCODE_CONFIG_CONTENT`——
  一支讀 `$VACANT_RUN_PROXY` 的 wrapper 就接得上，連 `--port` 都不必。
  這份名單在 `envmap.CONFIG_ROUTE`。

### 4.6 TOCTOU

驗收**必須**跑在凍結的工作區快照上，`ws_end_sha256` 綁進收據（R534 已這樣做，照抄）。
`launcher._freeze()` 複製完會**再量一次活的工作區**，兩個雜湊不等 ⇒
判 `infra_void`（`ws_moved_during_freeze`），**不判拒交也不判通過**。

另外：`--run-dir` **不可以在工作區底下**（launcher 會擋）。收據自己在長大，
放在工作區裡會讓 `ws_end_sha256` 變成「收據寫了多少」的函數。

⚠ **孫行程是同一條漏洞的另一個入口。** `proc.wait()` 只等**直接子行程**；
框架把真正的工作 fork 出去（背景 lint、watcher、自己的 worker）時，那些孫行程
不會被等到，於是它們可以在我們**凍結之後**繼續寫工作區。所以 agent 用
`start_new_session=True` spawn（自成一個行程群組），`wait()` 回來就 `killpg`
整組，**在凍結之前**。那一格落 `attempts[i].orphans_killed`：`true` ＝直接
子行程都結束了、群組裡**還有東西活著**（這個框架真的會留孤兒）。
`--stdin inherit` 是例外——分家會讓互動式 agent 失去控制終端——那一格
`orphans_killed` 落 `null`＝**沒量**，不是 `false`＝沒有。
可執行證明：`tests/test_vacant_run_retry.py::test_grandchildren_are_killed_before_the_freeze`
（孫行程睡 1.5 秒之後才往工作區寫，測試等 2.5 秒再看那個檔在不在）。

### 4.7 驗收是單邊保證

`vacant_network/suitegauge.py` 的那條，逐字適用：**擋得住已知壞解 ≠ 涵蓋真需求**。
`accepted=true` 只代表「客戶給的那幾條過了」，不代表做對了。

### 4.8 「沒量」與「量到過」不可以同形

`VACANT=1` 而沒有驗收套件 ⇒ **fail-closed**，判 `no_suite`＝拒交。
要放行必須明講 `--allow-no-suite`，那一格的 `accepted` 落成 `null`
（收據裡另有 `accepted_is_null: true`），不是 `true`。

### 4.9 收據裡的 `conversation_sha256` 不是對話的摘要

V0 刻意不 parse body（見 §3），所以算不出 provider 訊息陣列的摘要。
這個欄位放的是**依序的 (request body sha256, response body sha256) 清單**的
sha256，收據裡另有 `conversation_digest_kind: "wire_bytes"` 標明。
它與 R530／R534 sidecar 版本（簽 role/content）**不可互相替代**。

### 4.10 一律 base_url 轉向，不做透明 MITM

不需要裝 CA。透明攔截會系統性削弱 TLS，而且會把「被中介到」與
「TLS 被削弱」綁在一起——那是一個沒有人會想要的交換。

---

## 5. V3：出網封鎖（L3 → L4）

```
iptables -m owner --uid-owner <agent-uid> ! --dport <proxy-port> -j REJECT
```

腳本：[`ops/vacantrun/block_egress.sh`](../ops/vacantrun/block_egress.sh)
（`--dry-run` 不需要 root）
負向控制：[`ops/vacantrun/verify_egress_block.py`](../ops/vacantrun/verify_egress_block.py)

⚠ **要 root，而且工具不代跑。** 請人類讀過、確認 uid 與埠、自己 `sudo`。
工具自己 sudo 等於把「需要人類同意」做成一個沒有人在看的步驟。

⚠ **封鎖生效 ≠ 封鎖有效。** 一定要跑負向控制：從 agent 的 uid 直連真上游
**必須失敗**；同時正向控制（連 proxy 埠）**必須成功**，否則那不叫封鎖叫壞掉。

```bash
# 1) 先看規則長什麼樣（不需要 root）
ops/vacantrun/block_egress.sh --uid 1234 --port 8899 --dry-run

# 2) 封鎖之前先量一次——這時候 verdict 必須是 NOT_BLOCKED。
#    這一步是在驗**量具自己有沒有牙齒**：一個永遠回 BLOCKED 的驗證器沒有用。
sudo -u '#1234' python3 ops/vacantrun/verify_egress_block.py \
    --proxy-port 8899 --upstream 100.119.113.56:1234

# 3) 人類自己封鎖
sudo ops/vacantrun/block_egress.sh --uid 1234 --port 8899

# 4) 封鎖之後再量一次
#    ⚠ 舊版這裡寫「verdict 必須是 BLOCKED」。**2026-09-19 實測那句話在預設
#      Ubuntu 上永遠不成立**——見下面的 §5.1 第 3、4 條。要看的是
#      `negative_control_direct_upstream reached=False`
#      ＋ `positive_control_proxy_port reached=True` 這兩條，不是 verdict。
sudo -u '#1234' python3 ops/vacantrun/verify_egress_block.py \
    --proxy-port 8899 --upstream 100.119.113.56:1234 --json block_check.json

# 5) 拆掉（⚠ 套幾次就要拆幾次，見 §5.1 第 8 條）
sudo ops/vacantrun/block_egress.sh --uid 1234 --port 8899 --undo
```

### 5.1 **量過了**（2026-09-19，vacant-dev）——量到什麼、擋不住什麼

舊版這裡寫的是「IPv6、既有的長連線、raw socket 都要另外量」。
**已經量了**：裁決 [`decisions/DECISION_20260919_BLOCK_EGRESS_V3.md`](../decisions/DECISION_20260919_BLOCK_EGRESS_V3.md)，
逐字證據 `ops/vacantrun/egress_v3_20260919/`。
Ubuntu 24.04.4 × iptables 1.8.10（nf_tables）× 專用 uid 1001 × Hermes 0.19.0。

**擋得住**（負向控制：封鎖前每一條都實測通得過、封鎖後每一條都實測失敗、
拆掉後每一條又通）：對外 TCP（IP 字面值與經 DNS 的域名都一樣）、
完整 TLS 到第三方、直接打外部 DNS 伺服器的 UDP、ICMP。
**正向控制也過**：封鎖之下接線正確的那一格照樣 `accepted=true`、`requests_seen=6`。

**活體標本**：Hermes 漏設 `CUSTOM_BASE_URL` ⇒ 無封鎖時真的打到編死的
`https://openrouter.ai/api/v1`（agent stdout 是 openrouter 回的
`HTTP 401: Missing Authentication header`）；**封鎖之後變成
`API call failed after 3 retries: Connection error.`** ⇒ 洩漏被擋住了。

⚠ **但收據看不出差別。** 那兩格的 `run_*.json` **26 個判斷欄位逐字相同**
（`accepted`／`stop_reason`／`requests_seen`／`agent_rc`／`wire_by_protocol`／
`ws_end_sha256` 全部一樣），差異只在 `agent_stdout.log` 與耗時。
⇒ **V3 改變的是世界，不是收據。** 想讓「有沒有人試圖繞過中介」變成一個欄位，
最小改動是把 REJECT 規則的封包計數器差值寫進收據（實測該計數器會動：73 封包）。

**它擋不住什麼**（每一條都實測，不是推論）：

1. **同機另一個 uid 的任何 listener。** 規則 1 是 `-o lo -j ACCEPT`＝**放行整條
   迴圈**，不是只放行 proxy 埠（規則 3 實測 0 封包＝死碼）。實測：user1 起一支
   127.0.0.1 的中繼，被封的 uid 經它做完整 TLS 到 openrouter，`HTTP/1.1 200 OK`。
   ⇒ 腳本說的「只留 proxy 那個埠」**名實不符**。
2. **unix domain socket。** iptables 看不到，實測 0.038 秒拿到 `200 OK`。
   把迴圈規則收緊也堵不住這一條。
3. **DNS。** 腳本誠實邊界 3 寫「DNS 預設也被擋掉」，**在 systemd-resolved 機器上
   是錯的**：`/etc/resolv.conf` 指向 `127.0.0.53`＝迴圈 ⇒ 被放行。實測封鎖後
   `gethostbyname` 照樣回答。一條低頻寬外洩通道完整保留。
4. **`verify_egress_block.py` 的 verdict 因此永遠是 `NOT_BLOCKED`**（它把
   `negative_control_dns` 的期望寫死成 `False`）。錯的方向是安全的，但量具失去鑑別力。
   附帶：該檔抓 `iptables -S` 旁證時**只接例外不看 returncode** ⇒ 在它自己規定的
   執行方式（agent 的 uid）下 `iptables_S` 恆為 `''`，不是它承諾的「記下拿不到」。
5. **IPv6 完全沒被碰**（腳本一行 `ip6tables` 都沒有）。實測封鎖之下 ICMPv6 照樣通。
   ⚠ 「IPv6 上的 TCP 出網」**沒量**——那台機器沒有公網 v6 路由。**沒量不是沒有。**
6. **已經送出去的位元組收不回來。** 封鎖前建好的連線，送出方向在一個週期內斷
   （`BrokenPipeError`），但**核心接收緩衝區裡的殘料照樣讀得完**（實測四次）。
7. **`--uid-owner` 只認送出封包的 uid**（腳本原有的邊界 2 成立）：agent 能 `sudo`、
   能寫 setuid、能請別的 uid 代發就繞得過。⇒ 它**必須**跟「agent 跑在一個專屬、
   不能提權的 uid」一起用，而那個前提**不是這支腳本提供的**。
8. **操作危害三條**：套兩次拆一次 ⇒ 仍在封鎖但畫面說「已拆除」（實測仍
   `No route to host`）；沒套用時 `--undo` 也印「已拆除」（`|| true` 吞掉四行
   `Bad rule`）；**`--dry-run` 什麼都沒做也照樣印「已對 uid=… 封鎖出網」**。
9. **不持久化**（機器上沒有 `iptables-persistent`）⇒ **重開機規則自動消失**。
   展場機器開機後要重套。
10. 只擋**網路層出口**：不擋寫共享檔案系統、不擋 agent 的本機動作、不擋非 IP 的 IPC。
    agent 看到的是 `No route to host`／`Network is unreachable`／`EPERM`
    ⇒ **它分不出「被管制」與「網路爛掉」**。

### 5.2 ⚠ 要真的用 V3，`vacant run` 本身還缺兩件

`vacant_network/vrun/launcher.py` 的 proxy 與 agent **同行程樹、同 uid**，而 `--uid-owner`
只認 uid ⇒ 整支 `vacant run` 跑在被封的 uid 上，**proxy 自己的上游也會被封死**。
launcher 沒有 `--agent-uid`。2026-09-19 那次是手工包一層
`sudo -n -u '#<uid>'` 把 agent 降權、proxy 留在操作者 uid 才量得成。

降權之後還會撞到第二件：**Hermes 以 0600 建檔（不吃 umask）**，launcher（另一個
uid）讀不到 ⇒ `_frozen_*` 的 `copytree` 直接 `PermissionError` 把整跑炸掉、
**沒有收據**。當時在 wrapper 收尾 `chmod -R a+rwX` 繞過。

⇒ **「V3 可用」≠「`block_egress.sh` 存在」。** 這兩個缺口都**還沒補**。

展場機器是 Linux VM（`user1@100.124.254.83` 可測）。
展場說法的正確版本不是「agent 逃不掉」，是
「**它只能走這一條路出去，而這條路上的每一個位元組都留了下來**」，
後面接上面那十條，一條都不能省。

---

## 6. 複用了哪幾支（不是新寫的）

| 複用 | 用在哪 |
|---|---|
| `vacant_network/vrun/acceptance.py` | 目錄級驗收（`run_suite(suite="visible")`、`render_failures`）。舊路徑 `ops/gain/r530/acceptance.py` 是 re-export |
| `vacant_network/vrun/receipts.py` | `ws_attempt`／`ws_verdict` 兩種事件別，**判準一個字沒改**（舊路徑 `ops/gain/r530/receipts.py`） |
| `vacant_network/vrun/wshash.py` | 工作區樹雜湊（起點／終點）（舊路徑 `ops/gain/r530/wshash.py`） |
| `vacant_network/vrun/sandbox.py` | 驗收跑在沙箱裡（`make_sandbox`）（舊路徑 `ops/gain/r530/sandbox.py`） |
| `ops/gain/r534/wire_tap.py` | `wireproxy.py` 的前身（本檔 §3 那條鐵律的來源） |
| `ops/gain/r534/piarms.py` | `FEEDBACK_TEMPLATE` 的形狀（§7.3 逐字沿用） |
| `ops/gain/harness_arms.py` | 回饋迴圈的做法（`render_feedback`／截斷／落全文簽雜湊） |
| `vacant_network/vrun/verify_receipts.py` | 驗收據——**唯一那把尺**（舊路徑 `ops/gain/replay/verify_run_receipts.py` 是 re-export，仍可直接執行） |
| `vacant_network/memory.py::assert_ks1_clean` | KS-1 可執行防呆（鐵律 1） |
| `vacant_network/logbook.py`、`vacant_network/identity.py`、`vacant_network/crypto.py` | 簽章鏈 |

`ops/gain/r534/sidecar.py` 的**判斷層**（`hello`／`turn_end`／`settled`／
`message`／`event`／`final` 六個 op）與 pi 無關、可原封不動搬過來——但**用不到**：
那六個 op 全都需要一個會主動來問的框架擴充，而整個重點是
**不需要框架配合**。V1 的迴圈也沒有讓它們回到場上——重試靠的是重新 spawn，
不是在對話裡插話（§7）。實際沿用的是 sidecar 的形狀：判斷全在 Python 這一邊、
`final` 簽一筆 `ws_verdict`、鏈上放雜湊全文放檔案。

---

## 7. V1：閘門的重試迴圈

V0 只能「跑一次 → 驗收 → 過或拒交」。**那只是收件口，不是 Vacant 的機制。**
R530／R532 量到增益的那個東西是**閘門＋重抽／重改**（CONFORM 對單發
+14～+19 pp、五次複製都過 Holm）。沒有迴圈，`vacant run` 交付不出那個增益。

V1 便宜的原因只有一句：**觸發點是行程結束，所以重試不用碰協定**（§1）。

### 7.1 兩條臂

| 臂 | 沒過之後 | 對應既有實驗 |
|---|---|---|
| `--retry resample` | **全新工作區**（整個重置回起點）、全新 agent 行程，**不給失敗原文** | R530 A-CONF／R532 CONFORM |
| `--retry revise` | **保留工作區**、把失敗原文寫進 `VACANT_FEEDBACK.md`、再跑一次 | R530 A-GATE／R532 HMIX |
| `--retry none` | 不重試（**預設**，＝V0 的行為逐字不變） | — |

⚠ **`resample` 的重置連 `.git/` 一起清。** `wshash.EXCLUDED_DIRS` 把 `.git/`
排除在樹雜湊之外——但它排除不了 agent 的眼睛。上一次嘗試如果 commit 過，
留著 `.git` 就等於偷偷把失敗原文留在現場，那樣兩條臂的差別會消失，
**而且消失的方式在樹雜湊上完全看不出來**。還原完會再量一次樹雜湊，
對不回起點 ⇒ 判 `ws_reset_failed`（`infra_void`），不判拒交也不判通過。
可執行證明：`tests/test_vacant_run_retry.py::test_resample_really_resets_the_workspace`
（假 agent 把「我開始時看到什麼」寫到**工作區外**——工作區裡的證據會被重置一起清掉）。

### 7.2 `--max-attempts` 預設 3

R530 用的是「A-CONF 最多 3 份、A-GATE 最多 5 輪」。**V1 不照抄 5**：
那個 5 是給「同一段對話裡多說一輪」訂的，單位成本是幾則訊息；
V1 的一次嘗試是**整個 agent 行程重跑**（重讀任務、重建脈絡、重跑工具），
成本高一個量級。3 同時是 A-CONF 那條的下限，兩條臂都涵蓋得住。
展場與無人值守要的是一個**小**的成本上限。要更多就明講 `--max-attempts`。

`--retry none --max-attempts 3` 是**壞組合，一律 fail-visible**（`SystemExit`）：
安靜地當成 1 會讓一次不重試的跑看起來像重試過。

### 7.3 回饋檔逐字

寫到工作區的 `VACANT_FEEDBACK.md`（固定檔名——agent 命令是使用者給的，
我們沒辦法在它的 prompt 裡講「去讀某某檔」，所以這個名字必須是文件上的約定）：

```
<!-- Written by `vacant run` between attempts.
     This is machine output, not a person. It is not part of the deliverable. -->

# Acceptance feedback (attempt {attempt} of {max_attempts})

The checks that ship with this task were run against your
working directory. They did not all pass.

{block}

Fix the working directory. The checks run again when this process exits.
```

**正文（第 5 行起）逐字沿用 `ops/gain/r534/piarms.py::FEEDBACK_TEMPLATE`**，
連硬折行的位置都照抄——那一段已經在 R534 的真模型上跑過，換字就是引入一個
沒有被量過的變因。**唯一的改寫是最後一句**（R534 寫的是
`When you consider it finished, reply with a short plain-text summary and do not
call any tool.`）：那句話講的是 pi 在同一段對話裡怎麼宣告完成，
而 V1 的觸發點是行程結束，照抄會是對 agent 說一句在這裡不成立的話。
表頭是 V1 新加的，用意取自 `piarms.TOOL_RESULT_HEADER`
（"This is machine output, not a person."）——訊息可以靠位置說明自己是什麼，
檔案不行。`{block}` 由 `ops/gain/r530/acceptance.render_failures()` 渲染。

⚠ **`{block}` 裡的路徑指的是凍結快照**（`_frozen_RUN-ON_a2/solution.py`），
不是 agent 自己那個檔。這是 V0 就有的性質（README 印的 demo 輸出同款），
V1 沒有改 `render_failures`（凍結碼）。實測的 12B 沒有因此改對名字，
但**「路徑看起來不是它的檔」有沒有害到它，本輪沒有量**——寫成沒量，不要寫成沒有。

### 7.4 兩條紅線

1. **V/GT**：回饋只吃 `run_suite(suite="visible")` 的結果，
   隱藏驗收的存在、條數、內容一律不進這個檔。
   可執行防呆＝`tests/test_vacant_run_retry.py::test_feedback_file_never_contains_hidden_testdata`
   （canary 種在 hidden 側，掃 feedback 檔零命中）＋**負向控制**
   `test_vgt_canary_scan_has_teeth`（把 hidden 當成可見套件餵進去，
   同一支掃描必須翻紅）。沒有負控的「零命中」跟把掃描關掉在輸出上同形。
2. **KS-1（鐵律 1）**：回饋文字禁止「你有責任／會被懲罰」類措辭。
   `vacant_network/memory.py::assert_ks1_clean` 在 `vacant_network/vrun/retry.py` import 時
   就跑一次（模板），每次渲染再跑一次（**含插進去的失敗原文**）。
   責任修辭如果是從客戶測試的訊息帶進來的，判 `ks1_violation`＝`infra_void`
   ——鐵律 1 說的是「違反＝run 作廢」，不是「拒交」。

### 7.5 收據：`attempt 數 ≥ verdict 數`

**R530 踩過的坑**：只在 happy path 簽 attempt ⇒ 撞預算的格子 0 筆 attempt、
1 筆 verdict ⇒ **鏈沒壞，壞的是「鏈說得出這一格發生過什麼」**。
所以 V1 在**每一次嘗試結束時**就簽一筆 `ws_attempt`（含沒有驗收套件那一次，
`verdict_sha256=None` ＝這一輪沒跑驗收），最後簽**一筆** `ws_verdict`。
一次 `run()` 只交付一次 ⇒ `rows.jsonl` 也只有一列。

`infra_void` **整條鏈都不落盤**（V0 的語意：基建事件不是裁決）。
已經簽過的 attempt 不會憑空消失——全文在 `run_<ARM>.json` 的 `attempts` 陣列裡，
只是沒有簽章背書。理由是對帳規則：那一列 row 沒有 verdict，
鏈只要落盤就會被判 `verdict_count_ne_rows`，而那會把「基建壞了」報成「鏈壞了」。

```bash
python3 ops/gain/replay/verify_run_receipts.py --selftest      # 先證明它抓得到壞鏈
python3 ops/gain/replay/verify_run_receipts.py --glob ~/.vacant-run/<你的 run 目錄>
```

### 7.6 等預算＝上限相同、實際用量落盤

R530 的裁決是「**上限相同、實際用量落盤**」，不是強制用滿。
每一次嘗試的 `requests_seen`、`agent_wall_s`、`agent_rc`、
`ws_start_sha256`／`ws_end_sha256`、回饋的 sha256 全部逐次落進
`run_<ARM>.json` 的 `attempts`，並且簽進對應的 `ws_attempt`。

### 7.7 誠實邊界（**不准淡化**）

1. **重試不是免費的。** 每一次嘗試都燒一整個 agent 行程的 token 與時間。
   `--max-attempts` 是**成本上限不是目標值**。
2. **`revise` 會讓 agent 看到自己的失敗**，那是設計；
   但**它看不到隱藏測資**，這條由 §7.4 的 V/GT 測試守，不是由「我們很小心」守。
3. **R534 實測：真模型上「沒過→重改」與拒交出現 0 次**（6 格次裡 2 次宣告完成
   都第一輪過、2 次燒光 token、2 次撞脈絡上限）⇒ **V1 讓這條路存在，
   不代表它在你的工作負載上會被觸發。** 沒被觸發的迴圈不產生增益。
4. **本輪的數字不得與 R530／R532／R534 併表**：prompt 不是我們寫的
   （agent 命令由使用者給）、工具面由框架自己決定、預算形狀是「整個行程重跑」
   而不是「同一段對話多說一輪」。三個變因都不同。
5. 迴圈**不改變**驗收是單邊保證這件事（§4.7）：重試到過，只代表
   「客戶給的那幾條過了」，不代表做對了。

### 7.8 真 agent 實跑一次（2026-09-18，vacant-dev）

pi 0.85.1 ＋ 1003 的 `gemma-4-12b-it-qat`（`http://100.119.113.56:1234/v1`）。
pi 不吃環境變數 ⇒ 用 `--port 8877` ＋ `PI_CODING_AGENT_DIR` 底下一份
`models.json` 把 provider `baseUrl` 指向 proxy（§4.5 講的那條路）。
**兩跑都零機時爭議：模型端點本來就在跑，一次 3 通 wire。**

| run | 任務敘述 | 結果 |
|---|---|---|
| `v1_real_pi` | TASK.md **只講白話**（「一個相加、一個相乘」），可見驗收在工作區外 ⇒ agent 看不到 | **拒交**（`attempts_exhausted`，3/3 次、9 通 wire、exit 20）。三次都寫成 `add_numbers`／`multiply_numbers` |
| `v1_real_pi_explicit` | TASK.md **明講** `add(a,b)`／`mul(a,b)` | **交付**（`visible_pass`，1/3 次、3 通 wire、exit 0） |

兩條鏈都過既有那把尺（`ws_attempt` 3+1 與 1+1、`verdict` 各 1、
`chain_ok` 與 `logbook_verify_chain` 一致）。

⚠ **這兩跑是機制示範不是量測**：任務是挑出來讓閘門有東西可擋的、零統計。
它證明的是「迴圈真的會跑、收據真的驗得過、拒交真的擋得住」，
**不證明 revise 在真模型上會提高通過率**。

#### 為什麼第一跑三次都沒改對——**它根本沒讀到回饋**

原本這裡寫「讀了回饋也沒改名」。**那句話與 wire 矛盾，已於 2026-09-19 更正。**
把兩跑全部 18 通請求逐一解開（`wire_RUN-ON/*.req.bin`）：

```
vr1_run : 9 個請求   含 "Acceptance feedback" 0   含 "VACANT_FEEDBACK" 0   含 "feedback"(不分大小寫) 0
run4    : 9 個請求   含 "Acceptance feedback" 0   含 "VACANT_FEEDBACK" 0   含 "feedback"(不分大小寫) 0
```

回饋檔**確實寫出來了**而且內容足以決定修法
（`_frozen_RUN-ON_a2/VACANT_FEEDBACK.md`，713 bytes，逐字點名
`ImportError: cannot import name 'add' from 'solution'`）。沒被讀到的是它。
原因在請求本身：三次嘗試各是**一段全新對話**（roles 都從 `system,user` 開始），
user 訊息三次逐字相同——

```
Read TASK.md and do what it says. Use your tools to write the file.
```

pi 讀 `TASK.md`、寫 `solution.py`、結束。**它沒有 `ls` 過工作區**，
所以工作區裡多一個檔案對它等於沒發生。

⚠ 這條的教訓比「模型不夠聰明」重要得多：**V1 的檔案投遞對「每次重試都是
新對話」的 agent 是結構性失效**——不是它讀了不改，是那份回饋從來沒進過
context。「我把回饋寫到工作區了」不是證據，**請求裡找得到那段文字才是**，
與 §4.5 `requests_seen` 同一條紀律。

⇒ 這正是 §8 V2（`--feedback-into prompt|both`，把同一份回饋放進 argv）
存在的理由：argv 一定會被 agent 的 CLI 吃進去，不依賴它自己想去看。
**引用第一跑時不可以寫成「重改沒用」**——那一跑沒有測到重改。

#### ⚠ 失效有**兩種**形狀，這兩跑只量到第一種（2026-09-19 補）

上面兩跑是 **THINK** 模式。把工具呼叫解出來，兩跑加起來只用了兩個工具：

```
read  {"path":"TASK.md"}
write {"content":"def add_numbers(a, b): …"}
```

**沒有 `ls`** ⇒ 那個 agent **連檔名都沒看到**。「從未讀到回饋」對這兩跑成立。

但 R535 的 **NOTHINK** 冒煙量到**另一種**形狀——同一個 pi、同一顆模型，
只是推論模式不同，它就會先列目錄：

```
RF 的 ls -F  ⇒  solution.py\nTASK.md\nVACANT_FEEDBACK.md
RS 的 ls -F  ⇒  TASK.md
```

**檔名逐字回到了模型的輸入裡，它還是沒有去讀**，回頭讀 `TASK.md`、
覆寫成同一份錯碼——最後交付的 `solution.py` 與**不給回饋**的那一臂
**sha256 逐位元相同**。

| | 這兩跑（THINK） | R535 冒煙（NOTHINK） |
|---|---|---|
| 有沒有 `ls` | **沒有** | 有 |
| 看到檔名了嗎 | 沒有 | **看到了** |
| 讀了回饋嗎 | 沒有 | 沒有 |

⚠ **兩種都不要寫成「agent 看不到工作區」。** 第二種尤其重要，因為它把失效的理由
講得更準：**「看到檔名」不構成「讀它」的理由**。R535 用
(`M7_name`, `M7_file`) 那一對把這件事量化。

⚠ 也**不要**反過來把第二種套到這兩跑上——它們是不同的推論模式，
而**工具使用形狀會隨推論模式改變**。這兩跑量到的就是「連看都沒看」。

另外有一跑因為 `--port` 給了 8878 而 pi 的 `models.json` 寫的是 8877，
**agent 完全沒被中介到**（`requests_seen` = 0），而畫面上只有 pi 自己的
`Connection error.`。那正是 §4.5 的現場版本：**「我設了設定」不是證據，
`requests_seen` 才是。**

---

## 8. V2：同一份回饋走 argv（`--feedback-into prompt|both`）

V1 的回饋是寫一個檔（`VACANT_FEEDBACK.md`）到工作區，而 §7.3 自己就承認了那條路
的洞：**我們沒有辦法在 agent 的 prompt 裡講「去讀某某檔」**（那條命令是使用者給
的）⇒ **模型可以不讀它**。V2 把同一份文字接到 agent 命令裡 `{VACANT_FEEDBACK}`
那個參數的**尾端**。

```bash
vacant run --suite ../tests_visible --retry revise --feedback-into prompt -- \
    pi -p "把 solution.py 寫完{VACANT_FEEDBACK}"
```

| `--feedback-into` | 回饋去哪 |
|---|---|
| `file` | 工作區的 `VACANT_FEEDBACK.md`（**預設**，＝V1 的行為逐字不變） |
| `prompt` | **只**接到下一次 spawn 的 argv 尾端，工作區一個檔都不多 |
| `both` | 兩邊都給 |

### 8.1 為什麼是 argv 而不是 wire

proxy **擁有一次 HTTP 往返的讀寫權，不擁有 agent 的迴圈狀態，也不擁有工具執行器**。
三條 wire 上的路各自撞死在那個邊界上：

* 改 `tools` ⇒ **L0**：proxy 宣告得了工具、**執行不了**——`tool_result` 只能由
  agent 自己的執行器產生，我們生不出來。
* 改 `system` ⇒ wire 上的紀錄會與框架自己的 transcript 講不同的話，
  **直接傷害「紀錄忠實」的立論根基**（§1）。
* 插一則 user 訊息 ⇒ 它**只存在於那一通 request**，agent 的歷史裡沒有，下一通就不一致。

**launcher 擁有 argv，而 argv 就是那一則 user 訊息。** 零協定破解、零偽造發言、
跨所有框架。`wireproxy.WireProxy.on_wire()` 在 V2 仍然**恆回 `None`（永不改寫）**
——**V2 一個位元都沒有碰 wire**（`wireproxy.py`／`envmap.py` 兩支這一輪零改動）。

### 8.2 三條規則，每一條都有理由

1. **placeholder 必須是那個參數的結尾**，否則 `SystemExit`。
   尾端 append 才保得住 provider 的**前綴快取**；插在中間會讓整段快取失效，
   **而那個成本不會出現在任何一個我們落盤的欄位裡**（同一個參數裡出現兩次也擋——
   前面那一次就不在結尾）。
2. **第 1 次嘗試把 placeholder 換成空字串** ⇒ 第一次的命令與「沒有 Vacant」時
   **逐位元相同**。這是兩臂可比性的基礎，形狀與 wire 那條「兩臂 body 逐位元相同」
   同一個用意。第 2 次起才換成 `"\n\n"` ＋ 回饋，所以**第 2 次的 argv 是第 1 次的
   逐位元前綴**。
3. 換了管道不放鬆鐵律 1：**我們接上去的那一段**再跑一次
   `vacant_network/memory.py::assert_ks1_clean`（髒了就判 `ks1_violation`＝`infra_void`
   ——鐵律 1 說的是「違反＝run 作廢」，不是「拒交」）。

   ⚠ **範圍是「我們寫的字」，不是整條命令**（2026-09-18 人類裁決）。
   KS-1 的立法意旨是「**我們的** prompt 模板不准用責任措辭」，因為那會污染實驗
   條件（三臂模板必須逐字相同，唯一差異是 MemoryManager 注入的記憶區塊）——
   **它不是內容審查**。使用者那條命令是他自己的業務：
   `-p "You are responsible for the migration"` 是一句完全正常的話，掃它等於
   **用一個誤判殺掉整跑**，代價與 KS-1 要防的東西不成比例。
   兩個方向各有一條測試——`test_v2_ks1_scope_is_our_text_not_the_users`
   （使用者那句話照常跑完、不作廢）與
   `test_v2_ks1_still_voids_when_our_own_feedback_is_dirty`
   （我們的回饋髒了仍然作廢）。**只證明「收得住」不夠，還要證明「沒收掉」。**

### 8.3 壞組合一律 fail-visible，**不准安靜退回檔案模式**

| 組合 | 結果 |
|---|---|
| `--feedback-into prompt` 而 argv 裡沒有 `{VACANT_FEEDBACK}` | `SystemExit` |
| argv 裡有 `{VACANT_FEEDBACK}` 而 `--feedback-into file` | `SystemExit`（那串字會原樣送給 agent 看） |
| `--feedback-into prompt --retry none` | `SystemExit`（沒有下一次 spawn，回饋永遠不會產生） |
| `--feedback-into` 給了不在 `{file, prompt, both}` 裡的字 | `SystemExit` |

安靜退回檔案模式會讓「我以為在 prompt 模式」的錯**在資料裡活著**：那一跑的收據
會寫 `feedback_delivery="prompt"`，而模型的輸入裡一個字都沒有。那種錯要死在畫面上。

⚠ **`--retry resample --feedback-into prompt` 刻意不擋。** 那一臂本來就不給失敗
原文，但兩條臂要能用**同一條命令**跑（第 1 次的 argv 才逐位元相同），所以它必須
吃得下 placeholder、把它換成空字串。那一格每一次的 `feedback_in_prompt_bytes`
都是 `0`——「政策上沒有回饋」與「以為有卻沒送到」因此在資料上分得開。

### 8.4 落盤與收據

每一次嘗試多落四個欄位（`run_<ARM>.json` 的 `attempts[i]`）：

```
argv                     這一次**真的 spawn 出去**的那條命令（頂層 `argv` 是使用者給的原文）
argv_sha256              它的指紋（NUL 分隔——空白分隔的話 ["a b"] 與 ["a","b"] 會同形）
feedback_delivery        file / prompt / both
feedback_in_prompt_bytes 回饋真的進了幾個位元組。**第 1 次恆為 0**
```

前兩個之中的 `argv_sha256` 與 `feedback_delivery` 也**簽進 `ws_attempt`**
（`ops/gain/r530/receipts.py::append_attempt` 收 `**extra`，**那一支一個字都沒改**）。
沒有它們的話，「回饋進了 prompt」這件事在鏈上完全沒有痕跡。

### 8.5 誠實邊界（**不准淡化**）

1. **不能說「不可忽略」。** 能說的是「**回饋一定出現在模型的輸入裡**」。
   **看得到 ≠ 照做**——V2 保證的是投遞，不是遵從；能強制的只有
   **「沒過就不出貨」**（閘門本身，§4.7 的單邊保證仍然逐字適用）。
2. **不能說 V2 提高了通過率。** V1 實跑三次都沒改對，但 wire 顯示回饋
   **從未進過 context**（§7.8）⇒ 那一跑沒有測到重改，不是重改無效；
   R534 真模型上「沒過→重改」與拒交出現 **0 次**。
   **V2 改的是機制性質（回饋一定在輸入裡），不是效果量測。** 本輪零真模型跑。
3. **不得與 R530／R532／R534 併表**：prompt 不是我們寫的（agent 命令由使用者給）、
   工具面由框架自己決定、預算形狀是「整個行程重跑」而不是「同一段對話多說一輪」。
   三個變因都不同，併表就是把三件事講成一件事。
4. `tests/test_vacant_run_retry.py` 裡那支「只看 argv 的假 agent」在 `prompt`
   模式會過、在 `file` 模式不會過——**那是可執行的機制差，不是效果量測**。
   它照做是因為我們寫死它照做（`code = GOOD if "check_add" in PROMPT else BAD`）。
   真模型看得到也可以不理，那正是第 1 條。
5. **預設仍是 `file`** ＝ V1 的行為逐字不變。要 argv 就要明講。

### 8.6 可執行證明

| 斷言 | 測試 |
|---|---|
| 第 1 次的 argv 與「沒有 Vacant」時逐位元相同（兩端都驗：收據的 `argv_sha256`、agent 行程真的收到的那條） | `test_v2_first_attempt_argv_is_byte_identical_to_no_vacant` |
| 第 2 次＝第 1 次的逐位元前綴 ＋ `"\n\n"` ＋ 回饋 | `test_v2_second_attempt_argv_is_the_first_plus_the_feedback` |
| 只看 argv 的 agent：`prompt` 會過、`file` 不會過（**負向控制**，且證明檔案模式不是因為檔沒寫出來才失敗） | `test_v2_an_agent_that_only_reads_argv_passes_in_prompt_mode_and_fails_in_file_mode` |
| 缺 placeholder ＋ `prompt` ⇒ `SystemExit`，連 run 目錄都不開始寫 | `test_v2_missing_placeholder_with_prompt_mode_is_a_hard_stop` |
| hidden 測資不出現在**任何一次的 argv**，**＋負向控制** | `test_v2_feedback_in_prompt_never_contains_hidden_testdata`、`test_v2_vgt_canary_scan_has_teeth_in_argv` |
