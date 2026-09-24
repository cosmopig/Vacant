# DECISION 2026-09-24 — 分身迴圈搬進 VM、run 產物展期結束即刪（F 線落地紀錄）

人類裁決（2026-09-24，兩條）：

1. **分身迴圈跑在 VM（vacant-dev）裡**，不在 1003 Windows 上。
2. **wire log 等 run 產物：展期內保留、展期結束即刪**，收據鏈上的雜湊照留。

這一份記的是那兩條裁決**怎麼落地、量到什麼、還剩什麼**。前一份是
`decisions/DECISION_20260924_TWIN_AGENT_RUN.md`（C 線）——它的 §三 誠實邊界 1
「收住的是模型叫得到的工具，不是 pi 這個行程」與 §八 3／4 在 VM 圍牆模式下有了例外，
**原文不改**（紀錄描述的是當時的事實），例外寫在這裡與程式的 docstring。

---

## 一、拓撲（誰跑在哪、誰讀誰）

| 在哪 | 跑什麼 | 讀／寫 |
|---|---|---|
| 1003（Windows） | LM Studio `127.0.0.1:1234`（VM 看到 `192.168.76.1:1234`） | — |
| 1003 | kiosk 瀏覽器 | HTTP 讀 VM 的 8420（電視頁）、8899（事件流）、8901（分身） |
| 1003 | 埠轉送 8899 → VM（**人類布展時設**） | 觀眾手機只連這一個埠 |
| vacant-dev | `vacant-twin-loop.service` → `twin_loop.sh` | 寫庫、檔案庫、run 產物、lifecycle 檔（本機碟，checkout 外） |
| vacant-dev | `vacant-exhibit.service` → `exhibit_boot.sh --lan`（`VACANT_EXHIBIT_BIND_ALL=1`） | serve_twin **tail 同一台上的** lifecycle 檔；8901 唯讀讀庫 |

**選「serve_twin 也在 VM」而不是同步檔案**：`--live` 要 tail append-only 檔、`--live-runs`
要讀 run 目錄打包收據；跨機同步要處理半行、延遲、斷線補檔，放在同一台就全是本機讀。
兩支 unit 讀同一份 `/etc/vacant/twin-paths.env`（庫、事件檔、run 產物的路徑單一真相）。
`exhibit_boot.sh` 為此多兩個開關：`--bind-all`（8420／8901 綁 0.0.0.0、電視網址用 VM 位址）
與 `--qr-host`（QR 編 1003 的區網 IP）。**D 線的「lifecycle 路徑＝serve_twin --live 路徑」接線不在這裡。**

## 二、pi 行程本身被圈住了（`ops/exhibit/twin/twinenclose.py`）

* 整跑（launcher＋pi）進 `ops/vacantrun/enclosure_20260920/bin/enc.sh`（呼叫，不複製）：
  netns＋mount ns＋最小 rootfs；repo 與 node 唯讀、只有自己的工作區與 run-dir 可寫。
* 唯一出口：主機側一扇 `WireProxy(unix_path=…, path_policy="model")`（逐通落盤）。
  **launcher 也要在圍牆裡**：收據的 `tier` 是 launcher 行程自己量的，只圍 pi 的話收據照樣是 C。
* 事件不直接寫展場 live 檔：圍牆裡寫 `lifecycle_part.jsonl`，主機側逐行驗（schema、task_id、
  caller 逐字相等、沒有內容欄位、單行上限）才轉送。
* 主機側對帳：門的通數 > 收據的 `requests_seen` ⇒ `door_unreconciled`；收據主機側驗章不過 ⇒
  `receipt_unverified`；`tier` 低於 `VACANT_TWIN_REQUIRE_TIER` ⇒ `tier_below_required`。
  三者都退化成「不算分身做的」（twin 層的 `VACANT_ATTEST=fail`：launcher 只記級別、不拒發）。
* repo 是唯讀綁進去的 ⇒ **庫與 run 產物住在 repo 底下就等於沒圍檔案系統**：
  `twin_loop.sh` 開機擋（exit 2）、`run_enclosed` 逐跑擋。

**證據**（`ops/exhibit/twin/evidence_vm_20260924/probe_twin_enclosure.json`，負控制先跑，
mismatched=0）：站在 pi 的位置（同一個父行程、同一份環境、同一個 namespace），九條別的路
（直連上游、1.1.1.1、DNS、主機 loopback、主機路徑型 unix socket、別的分身的 TRAITS.md、
庫、家目錄、寫出 work_root）**不圍時全通、圍了全斷**；經過 Vacant 的模型呼叫與寫自己的
工作區兩條正控制都通。收據 tier：不圍 **C**、圍 **B**。直接敲門繞過 launcher 那一格
`door_excess=1`。

**是 B 不是 A**：沒有框架掛鉤 canary（分身的 pi 是 `--no-extensions`）。補上 Vacant 的 pi 掛鉤
就有機會到 A，但那會改 pi 的工具面，要重跑 `probe_pi_tools.py`——**沒做**。

## 三、磁碟

實測一位分身（圍牆模式、4–5 通）約 0.36–0.40 MB（wire log 與門的 journal 各約一半）。
規劃值 1 MB／位；水位閘門 `VACANT_TWIN_MIN_FREE_MB`（預設 2048）：低於門檻那一輪不起新 run、
人留在佇列、stderr 與 `/visitors.json.intake` 都講；量不到剩餘空間 ⇒ 不收。算式在 START.md。

## 四、展期結束即刪（`ops/exhibit/twin/close_exhibition.py`）

刪清單與撤回同一份（`twinagent.erase_run_artifacts`，多了門的 journal）；留收據三檔；刪完重新驗章、
整棵 work_root 掃殘留、拿檔案庫裡還在的原文掃事件檔。抹除證明 `<庫名>.close_<展期名>.jsonl`＋
每位一列鏈上 note。`--dry-run` 或 `--yes-close <與 --exhibition 相同的名字>` 二擇一；不在 loop 裡。

**lifecycle 事件檔與錄影不含原文**：設計上如此（`lifecycle` 誠實邊界 3、C 線 §二），
這次在真跑上**量了**：VM 冒煙的事件檔、loop 與 exhibit 兩支 journal 裡合成特質零命中，
閉展的 `content_scan` 也是零命中；負控制（故意寫進事件檔）量得到。

**不在範圍內（照實寫進抹除證明）**：檔案庫（twinvault）裡沒撤回的人的卡片原文
（`vault_plaintext_subjects`）、雲端那一份、systemd journal。**檔案庫要不要在閉展時一起刪，是人類要決定的事。**

## 五、冒煙（`ops/exhibit/twin/smoke_vm.sh`，合成特質）

systemd 暫態 unit（`systemd-run --collect`，停了就沒有）起兩支；一位合成分身圍牆裡真跑：
`engine=vacant_run:pi:gemma-4-12b-it-qat`、tier B、門 5 通＝收據 5 通、收據 OK、lifecycle 9 筆過契約；
1003 敲 VM 的 18420／18899／18901 全 200、`/state.mode=live`；水位閘門擋下第二位（仍 pending）；
閉展 dry-run 零變動 → 真刪 38 檔 394,849 B → 只剩收據三檔、收據仍 OK。收尾 unit 0、暫存全刪。
埠用 184xx／188xx／189xx：vacant-dev 上 8420／8899 有別人的展件在跑，沒去動。

冒煙抓到並修掉一個會讓 Linux 開機直接失敗的缺陷：`exhibit_boot.sh` 的 `mktemp -t twinboot`
在 GNU mktemp 上 `too few X's` ⇒ `set -e` exit 1（macOS 從沒紅過）。

⚠ 這不是能力證據：n=1、合成特質、沒有評分（也不該有）。

## 六、布展時要人類做的

VM 的 VMnet8 位址固定；1003 把 8899 轉進 VM 並用手機實掃；寫兩份 env 檔、建 `/var/lib/vacant-twin`、
裝 unit；決定閉展時檔案庫要不要一起刪；清 vacant-dev 上已收工的暫存（約 1.3 GB）。
