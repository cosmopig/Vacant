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
