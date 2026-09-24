# 展場開機：一頁

> 2026-09-22 實跑驗證過的版本。每一條都標了「量到什麼」，沒量到的直說。

## 一行起來（展場機 1003）

```bash
export VACANT_TWIN_CLOUD_TOKEN='<雲端的 VENUE_TOKEN>'   # 少了它 twinlink loop 不會起
export VACANT_TWIN_DB="$REPO/ops/exhibit/twin/store/twinstore.sqlite3"
bash ops/exhibit/twin/exhibit_boot.sh --lan --token '<區網 token>'
```

起來的三個埠：

| 埠 | 誰 | 給誰 |
|---|---|---|
| 8420 | `python3 -m http.server`（vacant_hm 靜態站） | 電視 |
| 8899 | `serve_twin.py`（事件流／`/state`／`/control`／手機頁） | 電視＋現場手機 |
| 8901 | `twinlink serve`（**唯讀**真相來源 `/visitors.json`） | 電視的 `&twin=` |

背景還有一支 `twin_loop.sh`：每 15 秒跑一輪 `ingest → generate → publish → export`。

⚠ **`--lan` 一定要配 `--token`**，否則同區網任何人都按得動電視。

## 電視播的是什麼（2026-09-24 起只有一條路）

```
vacant run --events ──lifecycle.jsonl──▶ live_events.Folder ──▶ /live/events.jsonl ──▶ 電視
```

| 情境 | 怎麼起 | 電視事件的 `mode` |
|---|---|---|
| 離線備援（預設） | 不加參數：重播 `ops/exhibit/twin/recordings/*.jsonl` | `replay` |
| 指定錄影 | `exhibit_boot.sh --recording <檔> [--recording <檔> …]` | `replay` |
| 現場真跑 | 另一邊 `run_twin.py --out runs/x --events runs/x/lifecycle.jsonl -- …`，這邊 `exhibit_boot.sh --live runs/x/lifecycle.jsonl --live-runs runs/x` | `live`（有真跑就先播；最後一行之後 20 秒沒動靜就回到重播） |

- 重播保留錄影裡事件的相對間隔，但一格**壓進 `dwell×0.8` 秒內**（只壓不拉）；
  壓縮比在 `/state.replay.compress`／`speedup`。**電視要用 `mode` 在畫面上標「重播」。**
- 電視事件的欄位與誠實規則：`ops/exhibit/twin/tv_contract.py`（模組 docstring 是契約表，
  `validate` 是可執行版）。新欄位 `mode`、新 type `working`（每一通經過中介的模型呼叫）。
- 從 run 目錄事後推事件的 `to_events.py` **已刪**。資料包只剩收據頁在用。
- 開機前驗錄影：`python3 ops/exhibit/twin/serve_twin.py --check`（preflight 會跑；
  有配對收據就連綁定一起驗）。

### 收據頁：每一份錄影配它自己那一批

| 收據從哪來 | `/r/<cell>` 轉去 | 綁定 |
|---|---|---|
| 錄影旁邊的 `X.pack.json`（`pair_receipts.py`，與錄影同一次 `run_twin.py`） | `/v/X.html` | 錄影 sha256 ＋ 逐格鏈頭（載入時驗，不過整份不收） |
| `--live-runs <run_twin --out>`：真跑那一格寫完就即時打包 | `/v/live.html` | 鏈頭＝`run_ended.verdict_hash` |
| `twin_pack.json`（舊的 54 格 L-real） | `/viewer.html` | 鏈頭相等 |

`/r/<cell>` 一律只轉到**鏈頭＝電視上演的那一跑**的那一頁；找不到就 404 並講明原因。
頁面都是同一份 `examples/twin_viewer.html`，只換內嵌的資料。

**1003 重跑 L-real 之後怎麼上架**（與 `record_fixture.sh` 同一條）：
```bash
python3 ops/exhibit/twin/run_twin.py --out runs/twin_real_X --events runs/twin_real_X/lifecycle.jsonl -- …
cp runs/twin_real_X/lifecycle.jsonl ops/exhibit/twin/recordings/real_X.jsonl
# 分身的旁註（OFF 臂事後稽核）要在 pair_receipts 之前就位，才會被綁進資料包
cp runs/twin_real_X/lifecycle.sidecar.jsonl ops/exhibit/twin/recordings/real_X.sidecar.jsonl
python3 ops/exhibit/twin/pair_receipts.py --recording ops/exhibit/twin/recordings/real_X.jsonl \
    --runs runs/twin_real_X        # 產 real_X.pack.json；鏈頭對不上就不寫
python3 ops/exhibit/twin/serve_twin.py --check
```

⚠ **目前只有 L-none 錄影**（`recordings/fixture_20260924.jsonl`，`record_fixture.sh` 產生：
腳本抄參考解／壞樁，零模型，畫面會照實說「交件是腳本寫的」）。
54 格 L-real 那一批是在 lifecycle 出現之前跑的，**沒有錄影**；要在 1003 用
`run_twin.py --events` 重跑才會有。不准寫「舊 run 目錄 → lifecycle」的轉換器。

⚠ fixture 錄影與 L-real 資料包**共用 cell_id**，但鏈不同。播 fixture 時 `/r/<cell>`
轉到 `/v/fixture_20260924.html`（它自己那一批），不會落到 `/viewer.html` 那一批。
fixture 那一頁的簽章 135/135 驗得過；但**扣住介面那 27 格的交付物樹雜湊在頁面上不重算**：
`VACANT_FEEDBACK.md` 裡有暫存目錄的絕對路徑，遮掉之後位元組不是 sha256 那一份，
頁面照實標「不可重算」。`twin_viewer_node_check.mjs` 對那一頁的 N13 會紅
（「OFF 臂零通數」——fixture 本來就零模型，那條判準是給 L-real 的）。

## 第一次布展

`twin_loop` **不會**替你建一個空庫（「我沒找到庫」不能長得跟「今天沒有人來」一樣）：

```bash
VACANT_TWIN_INIT=1 ...     # 只有第一次
```

## 真實運算接在哪

`twinlink loop` 不帶 `--endpoint` ⇒ 由 `resolve_endpoint()` **依序探測**：

```
1. http://127.0.0.1:1234/v1      本機（模型就跑在這台）      ← 展場機命中這個
2. http://192.168.76.1:1234/v1   VMware 主機介面（不出機殼）
3. http://100.119.113.56:1234/v1 1003 走 Tailscale（**要網路**）
```

實跑（2026-09-22，從 Mac）：1、2 失敗 → 3 成功。**在 1003 上第一順位就會中**
⇒ 打自己的 LM Studio，離線紅線成立。模型 `gemma-4-12b-it-qat`。

⚠ **端點一定要帶 `/v1`。** 少了它 LM Studio 回 **HTTP 200 ＋ error body**，
下游判成「模型回空的」並在收據上寫「thinking 吃光額度」——指向完全錯誤的方向。
`ENDPOINT_CANDIDATES` 全部已經帶了；自己手打 `--endpoint` 才會踩。

## 分身是真跑還是退化（2026-09-24 起）

`twin_loop.sh` 預設 `--engine agent`：每位分身在 `vacant run` 底下用 pi **真跑**、
自己決定任務（裁決 `decisions/DECISION_20260924_TWIN_AGENT_RUN.md`）。
**這台要有 pi 0.85.x**（`PATH` 上，或 `VACANT_TWIN_PI=<完整路徑>`）。

⚠ **1003（Windows）本機目前沒有 pi**（2026-09-24 查過）；pi 在 vacant-dev（1003 上的 VM）。
沒有 pi 時 loop 會印一行 ⚠ 並**誠實地**退到直打模型（`engine=lmstudio:*`、
`degrade_kind=agent_unavailable`、沒有收據）——畫面照實標，不會假裝在真跑。

| 環境變數 | 預設 | 意思 |
|---|---|---|
| `VACANT_TWIN_ENGINE` | `agent` | `chat` ＝ 舊路徑 |
| `VACANT_TWIN_PARALLEL` | `2` | 同時跑幾位（1003 吞吐 4 串封頂） |
| `VACANT_EVENTS` | 庫旁邊的 `twin_lifecycle.jsonl` | lifecycle 事件檔（B 線 `--live` tail 這一份） |
| `VACANT_TWIN_AGENTRUNS` | 庫旁邊的 `<庫名>.agentruns/` | 工作區與 run-dir。**loop 與 serve 兩邊要一致**，撤回才刪得到 |

## 開機之後一定要跑健檢

```bash
bash ops/exhibit/twin/venue_check.sh
```

⚠ **不要只看 boot 橫幅**：埠被佔 → `serve_twin` 炸掉，腳本照樣印出三個漂亮網址。

## 還沒解決的（不要當成沒有）

- 電視端 `world3/index.html` 與 `bridge.js` 對 `erased` **零引用**。
  一個 `card`/`arrival`/`working`/`handover` 全 `null` 的撤回者送過去會畫出什麼，
  **沒量過**。
- 整套**從沒在 1003 上完整布展過**（只有數位分身那條鏈跑過）。
- 沒真的用手機連過、沒測真人亂按／併發／斷電重開。
- 開機自動啟動（systemd／Windows 排程）沒做也沒測。
- 電視端（A 線，`vacant_hm/world3`）還沒實作 `mode` 的「重播」標示與 `working`；
  在那之前電視拿得到資料、畫面上還不會講。
- `postaudit`（OFF 臂事後稽核）與 `counters`（整批累計）2026-09-24 **補回來了，但不走
  lifecycle**（人類裁決「分身側自己記一份補回」）：`postaudit` 來自分身自己的旁註
  `X.sidecar.jsonl`（`sidecar.py`，`run_twin` 量完當下寫、配對收據綁它的 sha256），
  `counters` 是 `serve_twin` 依**已經播出去的格子**當場數的（重播／現場分開數）。
  沒有旁註的舊錄影照播，**電視上就沒有 postaudit**。電視端（`vacant_hm`）是否真的
  把這兩種畫出來、畫成什麼樣，**本機沒量過**。
- 真跑的收據要 `--live-runs` 才打包；沒給就 `/r/<cell>` 照實 404（「沒有給 --live-runs」）。
  `run_twin` 要等 OFF 那一臂跑完才寫 `twin_cell.json`，所以一格跑完到收據上架之間
  有一段空窗（那段時間 `/r/` 說「還在打包」）；等超過 900 秒就放棄並記在 `/state.live.errors`。
  **沒有在 1003 上實跑過這一段**，只在本機用 fixture 量過。
