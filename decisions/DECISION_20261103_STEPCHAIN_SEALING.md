# DECISION 20261103 — 步鏈無界增長治理：分卷封印＋冷壓縮＋預算回收（UNKNOWN 語義）

**日期**：2026-11-03（round 889）
**由來**：資深審查 20261103 第 3 條：「真機專案 trace/projects 已累積 38.02 MB，單檔突破 22 MB，
GC 估算僅能清理 433 KB，對步鏈完全無能為力。驗收判準：提出在**不破壞 Ed25519 鏈式校驗**
前提下的長效歸檔/封裝設計方案（如冷資料壓縮、分卷封裝），終止 chain.ndjson 單調膨脹之隱患。」
**決定**：採納本文 §3 三層設計（分卷封印／冷壓縮／預算回收）為步鏈長效歸檔的目標形態，
**設計凍結於此輪**。本輪不實作——本輪迴路規則是「不改產品行為」；實作輪按「先寫失敗測試
再實作」排程，分期 §6。

---

## 1. 現狀與數據（證據鏈，全部可重現）

實測（2026-11-03 00:48 UTC，本機，只讀）：

| 項 | 值 | 來源 |
|---|---|---|
| `~/.vacant` 總計 | 100M（10-28 清零後 6 天） | `du -sh ~/.vacant` |
| `trace/projects` | 39M | `du -sh`（資深審 38.02 MB，一致） |
| `trace/objects` | 33M | `du -sh` |
| 單檔最大 | `projects/b0a568dfe7dbe3b0/chain.ndjson` = **21.6 MB / 21,216 筆**（均 1.02 KB/筆） | `wc -l`（資深審 22 MB，一致） |
| 第二 | `projects/535f1510326fb03a/chain.ndjson` = 15M | `du` |
| 增速 | 該鏈 lock 檔 10-28 08:16 建、最後 step 11-03 00:42 ⇒ **≈3.8 MB/天、≈3,700 筆/天**（5.7 天窗口） | `stat` |

最大那條鏈的 genesis 載明 `workspace: /home/user1/dev/Vacant`——**就是本倉庫自己的 dogfood
專案**：這個迴路自己在喂大它。不治理的外推：≈120 MB/月、≈1.5 GB/年/專案。

架構事實（auto/qwen27b HEAD `c84ee590`，file:line）：

- 鏈＝每專案**單一個** append-only NDJSON Logbook 檔：`vacant_network/trace/recorder.py:219`
  （`class Recorder`）、`:222-235`（`chain_path=dir/chain.ndjson`）、`:300-340`
  （`_append`：持鎖→`_tail` O(1) 讀創世+尾筆→追加→`fsync`→原子寫 `head.json`，`:338`）。
- 校驗＝全鏈 walk＋`head.json`＋（可選）收件端帳本錨點：`recorder.py:1026-1065`（`verify`）；
  增量：`recorder.py:1067-1113`（`verify_since`，記號對不上即回退全驗）；
  錨點：`vacant_network/trace/stopcheck.py:247`（`verify_anchored`）。
- 單簽章者規則：genesis 記 signer，異金追加即拒（`MixedSignerRefused`）：`recorder.py:211`、`:311-320`。
- 大 payload 卸進 `objects/`（內容定址 blob，鏈留 sha256+計數）：`recorder.py:93-107`（`_fit`）。
- GC 明確「不動 `chain.ndjson` 與 `head.json`」：`vacant_network/retention.py:537`（docstring）、
  `:149`、`:169`（「步鏈是記責記錄，GC 向來不碰 chain.ndjson」）；只清 set-aside 過量
  （keep=3，`retention.py:78`、`:600-616`）與未引用 blob（`target_bytes` 有序回收，`:331+`）。
- `SUBDIR_TOTAL_CAPS['trace/projects']=32 MiB` **只報告、不刪除**：`retention.py:170`、`:234`；
  報表出口 `envelope_accounting.sub_overrun`：`:258-289`。

**為何 GC「完全無能為力」**：步鏈檔不在任何回收路徑上（定位上是記責記錄，見上引文）；
objects 已回收得只剩 433 KB（資深審實測）；32 MiB 子上限是報告性的。於是步鏈的增長
**按設計無上界**，且「單檔」形態使校驗成本 O(全鏈筆數)、單檔位元組數無界——本設計
終止的正是這兩個「單調膨脹」。

## 2. 必須守住的約束（設計前提）

1. Ed25519 鏈式校驗不破壞：逐筆簽章、`prev_hash` 連結、單簽章者、`head.json`、
   收件端帳本錨點——五者一個都不許弱化。
2. 回收後 tracing 回 **UNKNOWN**——不 crash、不 PASS（ASSIGNMENT 最高優先 #3 的既有語義）。
3. fail-open：封印/壓縮/回收任一步失敗 → 檔案原封不動、誠實報告、不擋 agent。
4. 零新增**必選**設定（`pip install`＋`vacant install` 即用；選用參數可以有）。
5. H-3（AGENTS.md）：integrity ≠ completeness；exogenous 錨定（收件端帳本）仍是唯一的
   完整性機制——本設計可以**加**每卷長度承諾，但不取代、不宣稱解決 H-3。
6. 本輪不改產品行為（迴路規則）→ 本文只是設計凍結。

## 3. 設計：三層（各自可獨立實作，侵入性遞增）

### 3.1 分卷封印（sealing，L1）——終止「單檔」單調膨脹

- 活動卷永遠叫 `chain.ndjson`（名稱不變，現行讀寫端無縫相容）；封印後改名
  `chain-NNNNNN.ndjson`（卷序號單調遞增，同目錄）。
- **封印時機（lazy，append 觸發）**：某次 `_append` 發現活動卷已 ≥ `VOLUME_MAX_BYTES`
  （預設 2 MiB）或 ≥ `VOLUME_MAX_ENTRIES`（預設 2,000），則先封印、再追加：
  1. 在活動卷尾追加一筆 `volume_seal` 事件（新 EVENT_TYPES，擴充 `recorder.py:49`），
     payload：`{sealed_file, sha256_prefix, first_seq, last_seq, entry_count,
     last_entry_hash, sealed_at_ms}`——`sha256_prefix`＝**除 seal 行外**整卷字節流的
     sha256（避免自指）；
  2. `fsync`；3. `os.replace` 改名（同 FS 原子）；
  4. 下一次 append 建新 `chain.ndjson`，其首筆 `prev_hash`＝該 seal 筆的 hash
     ——**邏輯鏈不斷**，卷只是檔案邊界。
- `trace_genesis` 永遠在卷 1（`recorder.py:321-325` 現行為創世）；新卷首筆不是創世，
  接在 seal 筆上。`stream_id`（創世 hash）、`branch_id` 語義不變。
- 相容性：舊格式（單 `chain.ndjson`、無 seal 筆）＝單一活動卷，讀寫行為完全不變。
  本輪實測的 21.6 MB / 21,216 筆檔就是舊格式——升級後第一次 append 時先封印它
  （卷 1），零遷移。
- 封印全程在既有檔案鎖內（`_lock`，`recorder.py:249-257`）；半行撕裂由現行
  `_repair_tail`（`recorder.py:285-299`）照樣兜底。

### 3.2 校驗語義（隨 L1 同批實作）

- `verify`：按卷序（卷 1→…→活動卷）逐卷 walk：逐筆簽章＋跨卷 `prev_hash` 連結；
  每個已封印卷驗其尾筆 seal：`entry_count`、`last_entry_hash`、`sha256_prefix`
  （＝每卷的檔案級完整性＋長度承諾）；`head.json` 仍對活動卷尾；帳本錨點邏輯不變
  （錨的 `(seq,hash)` 可落在任何一卷）。
- `verify_since`：用各卷尾筆定位 mark 所在卷（O(1) 尾讀，同 `_tail` 技法，
  `recorder.py:258-284`），再照舊驗 mark→活動尾。
- **新裁定 UNKNOWN（reclaimed/missing）**：應存在的卷缺失 ⇒ 回
  「無法驗證（UNKNOWN）」，與 BROKEN（驗出遭篡改）區分；**絕不返回 True**。
  用詞守「回收後 tracing 回 UNKNOWN，不 crash 不成 PASS」既有語義。
- 負控制（實作輪先寫失敗測試）：改 sealed 卷中任一筆 ⇒ 簽章失敗 BROKEN；
  刪 seal 行 ⇒ `sha256_prefix`/計數失配 BROKEN（**不是** UNKNOWN）；活動卷截尾 ⇒
  `head.json` 對不上（現行機制，不變）。

### 3.3 冷壓縮（L2）——純空間優化、零語義變化

- 只壓**已封印**卷（不可變）：`chain-NNNNNN.ndjson` → `chain-NNNNNN.ndjson.gz`；
  活動卷永不壓。seal 筆已含未壓縮流的 `sha256_prefix` ⇒ 驗章端 gunzip 後照舊驗，
  不符 ⇒ BROKEN。
- gzip 為 stdlib（零新依賴）；JSON 鏈預期 3–8× 壓縮比（實作時實測，C3）。
- fail-open：壓縮失敗 → 留原檔、記錄原因、不擋。

### 3.4 預算回收（L3）——只在明確預算下，永不預設

- 觸發：僅當給定明確預算（現行 `target_bytes` 機制，`retention.py:537+`；或明確 flag），
  且現有回收（objects→set-aside）之後仍超。無預算 ⇒ 零刪除（預設行為不改變）。
- 順序：只回收**最舊的已封印卷**；**永不動**活動卷、卷 1（創世）、最近 N 卷
  （預設 N=3，鏡 `DEFAULT_KEEP_SET_ASIDE=3`，`retention.py:78`）。
- 每次回收在活動鏈上簽一筆 `volume_reclaimed` 事件（哪卷、`first_seq`–`last_seq`、
  原因、預算）——**回收動作本身也入鏈記責**。
- 回收後 `verify` 誠實報缺口：「卷 2–5 已回收（見事件 …）；該區間 UNKNOWN」；
  收件端帳本錨點落在已回收卷 ⇒ UNKNOWN（誠實），不 PASS 不 crash。
- GC 的 blob keep-set 掃描（現只讀 `chain.ndjson`，`retention.py:659`）改為掃**全部
  殘存卷**：被回收卷引用的 blob 可隨之回收（不再被引用），殘存卷引用的必留。

## 4. 非目標與誠實邊界（引本設計時連同引用）

- **不宣稱解決 H-3（completeness）**：seal 筆與本鏈同一把金簽，非 exogenous；
  外生錨仍是收件端帳本＋`head.json`。封印加的是**每卷檔案級**完整性與長度承諾
  （擋檔案級截短/缺行），是增強，不是取代。
- 不引入新必選設定；L3 預算為選用，缺省零刪除。
- 不改單簽章者規則（`MixedSignerRefused`），不引入多簽章。
- **不保證「projects/ 總量必有界」**：預設只分卷＋壓縮、不刪——步鏈定位是記責
  記錄（`retention.py:169`），刪除只在用戶自給預算時發生。誠實的表述是：
  「單檔增長有界（卷上限）、總量增長速率有界（壓縮比）、總量有界需明確預算」。
- 本輪未實作（迴路規則「不改產品行為」）；§5 判準是實作輪的驗收，不是本輪的成績。

## 5. 驗收判準（pre-registered，可偽反；實作輪先寫失敗測試）

- **C1（分卷）**：合成 30k 步專案，無單檔 > `VOLUME_MAX_BYTES`；`vacant trace verify`
  OK；`verify_since` 跨卷 OK；負控制：改中間卷一筆 ⇒ BROKEN；刪 seal 行 ⇒ BROKEN。
- **C2（向後相容）**：本輪實測兩條真鏈（`b0a568dfe7dbe3b0` 21.6MB/21,216 筆；
  `535f1510326fb03a` 15MB）升級前後 `verify` 結果一致且仍可追加；舊格式讀路徑
  不觸發任何新程式碼。
- **C3（壓縮）**：壓縮比實測 ≥ 3×；壓後 verify OK；損壞 `.gz` ⇒ BROKEN（非 UNKNOWN）。
- **C4（回收）**：明確預算下只回收超出 recency 窗的封印卷（活動/卷 1/最近 3 卷
  不動）；回收後 verify ⇒ UNKNOWN（非 True、非例外）；其後事件仍逐筆可驗；
  `volume_reclaimed` 事件在鏈上且有簽章。
- **C5（零設定/fail-open）**：全新狀態目錄預設路徑全通；無預算 ⇒ 零刪除；
  封印失敗（如磁碟滿）⇒ 檔案原封＋報告，不擋 agent。
- **C6（成本）**：append P99 延遲增量 ≤ 10%（30k 步合成、前後對照）；30k 步鏈
  `verify` ≤ 5 s（實作時先定測試再調參）。

## 6. 實作分期（給實作輪的順序，非本輪）

1. **Phase A**：§3.1＋§3.2（C1、C2、C6）——純結構、零刪除，最保守。
2. **Phase B**：§3.3（C3）——只動已封印卷。
3. **Phase C**：§3.4（C4、C5）——動 GC 掃描與 UNKNOWN 裁定出口，最侵入，最後。

每期：先寫失敗測試 → 實作 → 全量測試 ≥ 基線（4,629 passed / 70 skipped）→ 提交。

## 7. 風險與開放問題

- **R1**：`logbook.py` 為 receipts/checkpoints 共用——卷讀取器必須實作在 trace 層
  （把專案目錄呈現為一條邏輯鏈的 adapter），不改 Logbook 核心。
- **R2**：GC blob keep-set 掃描漏改 ⇒ 該留的 blob 被收 ⇒ `materialize` 回 UNKNOWN
  （fail-safe 方向，但必須有測試接住，C4）。
- **R3**：最大那條真鏈是本迴路自己的 dogfood（§1）——實作後第一個真實驗章對象
  就是它，與 round 886（1003 備份）同法。
- **R4（開放）**：`VOLUME_MAX_BYTES` 預設 2 MiB 還是 4 MiB（校驗成本 vs 卷數）——
  以 C6 實測定，2 MiB 為起點。
- **R5**：專案目錄內另有工作狀態檔（本輪實測 `perf.jsonl` 1.9MB、`state.json` 99KB、
  `zero_state.json` 124KB、`delivery.*` 各 1.2KB），**不屬步鏈**、本文不涵蓋；
  若也需治理，另立研議。

## 8. 本輪（round 889）交付與狀態

- 交付：本文（設計凍結）。無產品代碼改動（守「不改產品行為」）。
- e014：`/srv/vlab/running/` 仍在（78 格）、`free 3.8G < 4.0G` 盤壓未解——
  授權內手段（gzip 三檔舊圓誌＋清 pycache，free 3.7G→3.8G）不足以過 4.0G 閾，繼續等監督者清
  /tmp（票 `R20261102_2025-1`）；不空轉、不刪權外。
- 真機 `~/.vacant` 100M（10-28 清零後 6 天），本設計 §1 即以其實測為據。
