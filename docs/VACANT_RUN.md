# `vacant run -- <任何 agent 命令>`（V0）

> 一句話：把任意 agent 包起來，中介它的模型通道，**在它的行程結束那一刻**
> 跑客戶的驗收、簽一張可驗證收據、沒過就擋下交付。

程式碼：[`vacant/vrun/`](../vacant/vrun/)
（[`launcher.py`](../vacant/vrun/launcher.py)、
[`wireproxy.py`](../vacant/vrun/wireproxy.py)、
[`envmap.py`](../vacant/vrun/envmap.py)、
[`demo.py`](../vacant/vrun/demo.py)、
[`verify_receipts.py`](../vacant/vrun/verify_receipts.py)）
· 維運側留在 repo：[`ops/vacantrun/`](../ops/vacantrun/)
（[`selftest.py`](../ops/vacantrun/selftest.py)、
[`block_egress.sh`](../ops/vacantrun/block_egress.sh)）
· 測試：[`tests/test_vacant_run.py`](../tests/test_vacant_run.py)、
[`tests/test_vrun_reexport.py`](../tests/test_vrun_reexport.py)

> **2026-09-18 搬家**：判斷層原本住在 `ops/vacantrun/` 與 `ops/gain/r530/`，而 `ops/`
> 不進 wheel ⇒ `pip install vacant-network` 的人跑不動 `vacant run`。改成**搬家＋反轉
> 依賴**：實作進 `vacant/vrun/`，`ops/gain/r530/*` 與 `ops/vacantrun/*` 留 re-export
> （`sys.modules` 指過去，**同一個 module 物件**）。所以既有的 83 處 `ops.gain.r530.*`
> 引用一行都沒改，而且**判準仍然只有一份**。理由與清單見
> [`vacant/vrun/__init__.py`](../vacant/vrun/__init__.py)。

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

`wireproxy.WireProxy.on_wire()` 是那個掛鉤的位置，**V0 恆回 `None`（永不改寫）**。

---

## 2. 用法

```bash
# 先看一次它擋下來：零設定、零模型端點、零 API key、零網路，約 2 秒
vacant demo gate                       # vacant/vrun/demo.py

# 最小：把 agent 包起來，用 tests_visible/ 當驗收
vacant run --suite tests_visible --run-dir ~/.vacant-run/demo -- \
    pi -p "把 solution.py 寫完"

# 純觀測（不 gate），但 wire 照樣逐字落盤
VACANT=0 vacant run --run-dir ~/.vacant-run/demo -- <cmd>

# 不透過 CLI（模組形式，pip 裝完就能用）
python3 -m vacant.vrun.launcher --suite tests_visible --run-dir /tmp/r -- <cmd>
# repo checkout 裡這一行是同一支（re-export）
python3 ops/vacantrun/launcher.py --suite tests_visible --run-dir /tmp/r -- <cmd>
```

退出碼**反映裁決**，不是 agent 自己的退出碼：

| 退出碼 | 意思 |
|---|---|
| `0` | `visible_pass`／`ungated`（`--allow-no-suite`）⇒ 交付 |
| `20` | `visible_fail`／`no_suite` ⇒ **拒交** |
| `22` | `infra_void`（TOCTOU、agent 起不來）⇒ 不判交付也不判拒交 |
| 其他 | `VACANT=0` 那一臂：透傳 agent 自己的退出碼 |

落盤形狀（`--run-dir`）：

```
rows.jsonl                    一臂一列（arm ∈ {RUN-ON, RUN-OFF}）
receipts_RUN-ON.ndjson        Ed25519 簽章鏈（ws_attempt + ws_verdict）
receipts_RUN-ON.pub.json      公鑰（私鑰不落盤，RECORD_SPEC §7）
wire_RUN-ON/index.jsonl       一通一列的 wire 索引（含 body sha256）
wire_RUN-ON/<call>.req.bin    request body **原始位元組**
wire_RUN-ON/<call>.resp.bin   response body **原始位元組**
visible_RUN-ON.json           驗收的完整結果
run_RUN-ON.json               summary（含 env 改了哪些、拿掉哪些）
_frozen_RUN-ON/               驗收跑的那份凍結快照
```

收據用**既有的那把尺**驗，不准另寫第二把：

```bash
python3 -m vacant.vrun.verify_receipts --selftest                 # 先證明它抓得到壞鏈
python3 -m vacant.vrun.verify_receipts --glob 'runs/<你的 run 目錄>'
python3 -m vacant.vrun.verify_receipts --glob ~/.vacant-run/demo-gate/receipts
# repo checkout 裡這一行是同一支（re-export，R460R／R529／R532 的鏈驗的就是它）
python3 ops/gain/replay/verify_run_receipts.py --glob 'runs/<你的 run 目錄>'
```

`--glob` 的相對 pattern：在 repo checkout 裡以 **repo 根**為基準（`runs/g_*` 那種寫法
照舊），`pip install` 之後以 **cwd** 為基準（`vacant/vrun/verify_receipts.py::_glob_base`）。
搬進套件之後不能再無條件往上數四層——那會指到 site-packages，而那裡沒有 `runs/`，
於是 `--glob 'runs/…'` 會**靜靜地零筆命中**，零筆命中在本檔的判準裡是 `UNVERIFIABLE`
不是錯誤。**絕對 pattern 兩種情況都照絕對解**——`--run-dir` 本來就多半落在 repo 外
（預設 `~/.vacant-run/<task_id>`），少了這條，畫面上印給使用者複製的那行驗證指令
就是一行跑不動的字。

### 自檢：你的 agent 真的被中介到了嗎

**「我設了環境變數」不是證據，`requests_seen` 才是**（§4.5）：

```bash
vacant run --allow-no-suite --run-dir /tmp/vr -- <你的 agent 命令>
python3 -c "import json;print(json.load(open('/tmp/vr/run_RUN-ON.json'))['requests_seen'])"
# 非 0 ⇒ 模型通道真的經過 Vacant；0 ⇒ 沒被中介到（框架用設定檔，或那一跑根本沒呼叫模型）。
```

可執行證明在 `tests/test_demo_gate.py::test_selfcheck_requests_seen_is_the_evidence`。

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
`vacant/controller.py:7-8` 原本就寫著：

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

1. **OpenAI Responses API ＋ `store:true` ＋ `previous_response_id`**：
   對話狀態存在 OpenAI 的伺服器上，後續請求只帶一個 id。
   ⇒ **鐵律 3 的逐字落盤在那條路上直接破功**（Codex CLI 走這條）。
   proxy 會記到那一通請求，但記不到「上文是什麼」。
2. **不走 HTTP 的模型**：llama.cpp in-process、MLX、任何把權重載進 agent 自己
   行程的做法——**根本沒有 wire**，proxy 在那裡不存在。
3. **Bedrock SigV4**：請求用 body 算簽章，換 Authorization header 會毀簽章。
   本工具不改 body，但金鑰替換那一步在 SigV4 上不成立。

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

### 4.6 TOCTOU

驗收**必須**跑在凍結的工作區快照上，`ws_end_sha256` 綁進收據（R534 已這樣做，照抄）。
`launcher._freeze()` 複製完會**再量一次活的工作區**，兩個雜湊不等 ⇒
判 `infra_void`（`ws_moved_during_freeze`），**不判拒交也不判通過**。

另外：`--run-dir` **不可以在工作區底下**（launcher 會擋）。收據自己在長大，
放在工作區裡會讓 `ws_end_sha256` 變成「收據寫了多少」的函數。

### 4.7 驗收是單邊保證

`vacant/suitegauge.py` 的那條，逐字適用：**擋得住已知壞解 ≠ 涵蓋真需求**。
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

# 4) 封鎖之後再量一次——verdict 必須是 BLOCKED
sudo -u '#1234' python3 ops/vacantrun/verify_egress_block.py \
    --proxy-port 8899 --upstream 100.119.113.56:1234 --json block_check.json

# 5) 拆掉
sudo ops/vacantrun/block_egress.sh --uid 1234 --port 8899 --undo
```

**它擋不住什麼**（`verify_egress_block.py` docstring 有同一份）：
`--uid-owner` 只認發出封包的 uid ⇒ agent 如果能 `sudo`、能寫 setuid 執行檔、
或能請另一個 uid 的服務代發請求，這條規則就繞得過。
所以它必須跟「agent 用一個專屬的低權限 uid 跑」一起用。
IPv6、既有的長連線、raw socket 都要另外量；量不到就寫「沒量」，不要寫「沒有」。

展場機器是 Linux VM（`user1@100.124.254.83` 可測）。

---

## 6. 複用了哪幾支（不是新寫的）

| 複用 | 用在哪 |
|---|---|
| `vacant/vrun/acceptance.py` | 目錄級驗收（`run_suite(suite="visible")`、`render_failures`）。舊路徑 `ops/gain/r530/acceptance.py` 是 re-export |
| `vacant/vrun/receipts.py` | `ws_attempt`／`ws_verdict` 兩種事件別，**判準一個字沒改**（舊路徑 `ops/gain/r530/receipts.py`） |
| `vacant/vrun/wshash.py` | 工作區樹雜湊（起點／終點）（舊路徑 `ops/gain/r530/wshash.py`） |
| `vacant/vrun/sandbox.py` | 驗收跑在沙箱裡（`make_sandbox`）（舊路徑 `ops/gain/r530/sandbox.py`） |
| `ops/gain/r534/wire_tap.py` | `wireproxy.py` 的前身（本檔 §3 那條鐵律的來源） |
| `vacant/vrun/verify_receipts.py` | 驗收據——**唯一那把尺**（舊路徑 `ops/gain/replay/verify_run_receipts.py` 是 re-export，仍可直接執行） |
| `vacant/logbook.py`、`vacant/identity.py`、`vacant/crypto.py` | 簽章鏈 |

`ops/gain/r534/sidecar.py` 的**判斷層**（`hello`／`turn_end`／`settled`／
`message`／`event`／`final` 六個 op）與 pi 無關、可原封不動搬過來——但**V0 用不到**：
那六個 op 全都需要一個會主動來問的框架擴充，而 V0 的整個重點是
**不需要框架配合**。它們會在 V1（注入回對話）回到場上。
V0 實際沿用的是 sidecar 的形狀：判斷全在 Python 這一邊、
`final` 簽一筆 `ws_verdict`、鏈上放雜湊全文放檔案。
