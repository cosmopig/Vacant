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
⇒ 人類裁決（同日）：迴圈跑在 VM，見下一節「VM 跑法」。
沒有 pi 時 loop 會印一行 ⚠ 並**誠實地**退到直打模型（`engine=lmstudio:*`、
`degrade_kind=agent_unavailable`、沒有收據）——畫面照實標，不會假裝在真跑。

| 環境變數 | 預設 | 意思 |
|---|---|---|
| `VACANT_TWIN_ENGINE` | `agent` | `chat` ＝ 舊路徑 |
| `VACANT_TWIN_PARALLEL` | `2` | 同時跑幾位（1003 吞吐 4 串封頂） |
| `VACANT_EVENTS` | 庫旁邊的 `twin_lifecycle.jsonl` | lifecycle 事件檔（B 線 `--live` tail 這一份） |
| `VACANT_TWIN_AGENTRUNS` | 庫旁邊的 `<庫名>.agentruns/` | 工作區與 run-dir。**loop 與 serve 兩邊要一致**，撤回才刪得到 |

## VM 跑法（2026-09-24 人類裁決：分身迴圈跑在 vacant-dev）

1003（Windows）本機沒有 pi；pi 0.85.1 在 1003 上的 VM **vacant-dev**（Ubuntu 24.04）。
所以**整條分身線搬進 VM**，1003 只剩三件事：跑模型、顯示電視、把手機那一個埠轉進 VM。

```
                1003（Windows，展場機）                         vacant-dev（VM，VMnet8 192.168.76.135）
┌──────────────────────────────────────────┐        ┌───────────────────────────────────────────────┐
│ LM Studio 127.0.0.1:1234 ◀───────────────┼─VMnet8─┼─ 圍牆的門（每位分身一扇，twinenclose）          │
│   （VM 看到的是 192.168.76.1:1234）       │        │ vacant-twin-loop.service：twin_loop.sh         │
│ kiosk 瀏覽器 ──▶ http://<VM>:8420 電視頁  │───────▶│   庫、檔案庫、run 產物、lifecycle 檔（本機碟） │
│              ──▶ http://<VM>:8899 事件流  │───────▶│ vacant-exhibit.service：exhibit_boot.sh        │
│              ──▶ http://<VM>:8901 分身    │───────▶│   8420 靜態站／8899 serve_twin --live／8901 唯讀│
│ 區網 IP:8899 ──轉送──▶ <VM>:8899          │───────▶│   （serve_twin tail 的是**同一台**上的檔）     │
└──────────────────────────────────────────┘        └───────────────────────────────────────────────┘
        ▲ 觀眾手機（展場 hotspot）掃 QR ＝ http://<1003 區網 IP>:8899/phone.html
```

**為什麼 serve_twin 也在 VM、不在 1003**：它要 `--live` tail lifecycle 檔、要讀 run 目錄打包收據頁
（`/r/<cell>`）。跨機 tail 一個 append-only 檔沒有好做法（同步會延遲、會半行、斷線要補），
而把 serve_twin 放在檔案所在的那一台，**這三樣都變成同一個碟上的讀**。1003 上只剩瀏覽器，
瀏覽器本來就是走 HTTP。代價是手機那一個埠要 1003 轉進 VM（見下）。

**為什麼迴圈不在 1003**：pi 在 VM；而且 VM 是 Linux ⇒ 圍牆（bwrap）存在，Windows 上不存在。

### 一份唯讀簽出，不要每位分身 clone

vacant-dev 只有 38 G（memory：vacant-dev 磁碟陷阱，每份 clone 786 M）。**整台只放一份
checkout**（建議 `git clone --filter=blob:none --sparse` 後 `git sparse-checkout set
vacant_network ops/exhibit/twin ops/vacantrun examples`，不帶 `runs/`）。每位分身的
工作區只放 `TRAITS.md`，run-dir 只放那一跑的產物；**沒有任何一步會 clone repo**。

🔴 **庫與 run 產物一定要放在 checkout 外面**（例如 `/var/lib/vacant-twin/`）。圍牆把 repo
整份唯讀綁進去；庫若在 repo 底下，別的分身的 wire log 在圍牆裡讀得到——`twin_loop.sh`
開機就擋（exit 2），`twinenclose.run_enclosed` 逐跑也擋。

### `/etc/vacant/twin-paths.env`（兩支 unit 都讀；沒有機密，644）

```bash
VACANT_TWIN_DB=/var/lib/vacant-twin/twinstore.sqlite3
VACANT_EVENTS=/var/lib/vacant-twin/twin_lifecycle.jsonl   # serve_twin --live 也 tail 這一個
VACANT_TWIN_AGENTRUNS=/var/lib/vacant-twin/twinstore.agentruns
VACANT_TWIN_OUT=/var/lib/vacant-twin/visitors.json
VACANT_TWIN_PI=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin/pi
VACANT_TWIN_ENCLOSE=on           # 起不來圍牆就不起 pi（不是安靜地不圍）
VACANT_TWIN_REQUIRE_TIER=B       # 收據級別低於 B 的那一跑不算分身做的
VACANT_TWIN_MIN_FREE_MB=2048     # 磁碟水位
VACANT_TWIN_ENDPOINT=http://192.168.76.1:1234/v1
VACANT_EXHIBIT_BIND_ALL=1        # 8420／8901 綁 0.0.0.0（電視的瀏覽器在 1003）
VACANT_QR_HOST=<1003 在展場 hotspot 上的 IP>   # QR 編這個，不是 VM 的位址
```
token 仍然只在 `/etc/vacant/twin.env`（600，只有 loop 那一支讀；電視那一支讀到 token
會自己再起一個 loop）。

### 圍牆：pi 行程本身被圈住了（B 級，不是 A）

`VACANT_TWIN_ENCLOSE=on` ⇒ 每位分身那一跑（launcher＋pi）整個跑在
`ops/vacantrun/enclosure_20260920/bin/enc.sh`（bwrap `--unshare-all`＋最小 rootfs）裡，
唯一的網路出口是一扇 Vacant 門（`WireProxy --unix`，path_policy=model，逐通落盤）。
實跑證據 `evidence_vm_20260924/probe_twin_enclosure.json`（**負控制先跑**，mismatched=0）：
站在 pi 的位置，直連模型上游／1.1.1.1／DNS／主機 loopback／主機路徑型 unix socket／
別的分身的 TRAITS.md／庫／家目錄／寫出 work_root **不圍時九條全通、圍了九條全斷**；
經過 Vacant 的模型呼叫與寫自己的工作區兩條都通。收據簽的 `tier` 從 **C → B**
（`enclosure.applied=true`、`ns_differs_from_outer=true`）。繞過 launcher 直接敲門的那一通
會讓 `door_excess=1` ⇒ `door_unreconciled`，不算分身做的。

**不是 A**：A 還要框架掛鉤 canary（分身的 pi 是 `--no-extensions`，沒有裝 Vacant 的 pi 掛鉤）。
**不准在展場講 A。** 圍牆**外面**（loop、serve_twin）什麼都連得到。

### 磁碟：估算與水位閘門

實測（VM 冒煙，gemma-4-12b、4–5 通模型呼叫、圍牆模式）：一位分身在碟上
**約 0.36–0.40 MB**（run-dir 190–207 KB，其中 wire log 171–187 KB；門的 journal 173–189 KB
——它跟 wire log 是同一批位元組的第二份；工作區 1–2 KB）。收據三檔幾 KB，閉展後只剩這些。

| 規劃值 | 算式 | 結果 |
|---|---|---|
| 每位（留 2.5 倍給長跑） | 1 MB | — |
| 每日人數（假設尖峰） | 300 | 300 MB／天 |
| 展期 | 14 天 | **≈ 4.2 GB** |
| 可用 | 目前剩 ≈ 8.7–9.0 GB − 水位 2 GB | ≈ 6.7 GB ⇒ ≈ 6,700 位（實測大小下 ≈ 17,000 位） |

布展前建議（人類決定）：清 `/var/tmp/vacant_*` 裡已收工的目錄（2026-09-24 量到約 1.3 GB），
`~/vacant`（8.4 G）裡哪些能搬走。

**水位閘門**：剩餘空間低於 `VACANT_TWIN_MIN_FREE_MB` ⇒ 那一輪**不起新的 run**，排隊的人留在
`pending`（電視上是「正在抵達」）、已經在跑的照樣收成；每一輪 stderr 印一行
`{"twinlink_warning":"intake_paused",…}`（進 journal），`/visitors.json` 多一塊
`intake{accepting,free_bytes,min_free_bytes,reason}`（電視那一側要把它畫出來——A 線的事）。
**量不到剩餘空間 ⇒ 不收**（不是「夠」）。

### 展期結束即刪（人類裁決：展期內保留、展期結束即刪）

```bash
python3 ops/exhibit/twin/close_exhibition.py --db $VACANT_TWIN_DB --exhibition 2026-10-A --dry-run
python3 ops/exhibit/twin/close_exhibition.py --db $VACANT_TWIN_DB --exhibition 2026-10-A --yes-close 2026-10-A
```
刪工作區、wire log、門的 journal、凍結快照、agent log、pi_cfg、run json；**留**收據三檔
（`receipts_RUN-ON.ndjson`／`.pub.json`／`rows.jsonl`，驗章器要它們）。刪完**重新驗章**、
整棵 work_root 再掃一次殘留、拿檔案庫裡還在的原文掃 lifecycle 檔。抹除證明寫在
`<庫名>.close_<展期名>.jsonl`（每位一列＋總結），每位也在 twinstore 鏈上多一列 note。
撤回過的人略過（`already_erased`）、同名重跑不重複寫（`already_closed`）。
**不在 loop 裡、不會被任何排程觸發**（`tests/test_twin_vm_retention.py` 有一條擋）。
⚠ 檔案庫（twinvault）裡的卡片原文**不在這一支範圍內**——總結的 `vault_plaintext_subjects`
寫出還剩幾位，那一步要人類另外決定。

### 冒煙（2026-09-24，合成特質）與布展時要做的事

`bash ops/exhibit/twin/smoke_vm.sh`（證據 `evidence_vm_20260924/`）：systemd 暫態 unit 起兩支、
一位合成分身在圍牆裡真跑（tier B、門 5 通＝收據 5 通、收據 OK）、1003 敲得到 VM 的
18420／18899／18901、水位閘門擋下第二位、閉展 dry-run 零變動→真刪 38 檔 395 KB→收據仍 OK、
事件檔與兩支 journal 裡合成特質零命中；收尾 unit 0、暫存全刪。
⚠ 冒煙抓到並修掉：`exhibit_boot.sh` 的 `mktemp -t twinboot` 在 GNU mktemp 上直接 exit 1
（Mac 從沒紅過）。⚠ 報告裡的 `pi_version` 欄是量具自己的 PATH 錯（`env: node`），已修、未重跑；
pi 真的起得來的證據是那一跑本身。

布展時（人類）：
1. VM 的 VMnet8 位址**固定**（現在是 DHCP 發的 192.168.76.135；VMware NAT 的 DHCP 保留或 VM 內設靜態）。
2. 1003 把 8899 轉進 VM（二擇一）：VMware「虛擬網路編輯器」VMnet8 NAT 的連接埠轉送，或
   系統管理員 PowerShell `netsh interface portproxy add v4tov4 listenport=8899 listenaddress=0.0.0.0
   connectaddress=<VM 位址> connectport=8899`＋Windows 防火牆放行 8899。**用手機真的掃一次**
   （VM 從裡面驗不到這一段）。
3. 寫 `/etc/vacant/twin-paths.env`、`/etc/vacant/twin.env`，建 `/var/lib/vacant-twin`（owner user1），
   `sudo ./systemd/install.sh`；1003 的 kiosk 開 `exhibit_boot.sh` 橫幅上那一行電視網址（VM 位址）。
4. 展期結束：人按 `close_exhibition.py`（先 `--dry-run`）。

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
