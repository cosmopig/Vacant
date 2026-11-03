# DECISION 2026-11-03：e016 host-env 洩漏修訂（cell.py／labd.py 明確 per-cell env）

> 紅線要求：改 `/srv/vlab` 共享量具（cell.py、labd.py）必須有 DECISION。本檔即之。
> 前件：`DECISION_20261103_E016_CNF_MEASUREMENT.md`（round 903，引入盲掃 host env 的量具）。
> 證據：round 905 實測（見 §1）；審批：senior round-905 指示 #1（驗收條款＝T5）。

## 0. 一句話

round 903 的量具盲掃 `cell.py` 自己的 `os.environ` 裡的 `VACANT_*`，把**分派者 host 的
session 變數（`VACANT_PI_PARENT`／`VACANT_PI_SELF`）注入所有臂**（含 A 臂）並寫進
`cell.json.agent_env`——違反 e016 預註冊臂定義（A＝無 Vacant、`agent_env` null）與
e014 gate-5 先例。修法：`cell.py` 只認 labd 以 `--agent-env` 傳入的「本 cell 在 queue
JSON 中明確指定的 env dict」，**完全不讀 host `os.environ` 的 VACANT_***；A/C 臂零注入，
C-nf 臂只有 `VACANT_FAILED_STEP_REVIEW=0`。

## 1. 發現（round 905，逐條可核）

1. **洩漏事實**：e016 full 102 格（14:34:40 發射）截至 15:36 已跑 15 格；其 A 臂
   `cell.json.agent_env` 全部含 `VACANT_PI_PARENT`＋`VACANT_PI_SELF`（例：
   `runs/e016_failed_step_ablation/polyglot_py-pg_affine_cipher-pi-A-r1/cell.json`，
   值指向已不存在的 pi session `01a1a112…`／pid 733374）；bwrap argv 同含
   `--setenv VACANT_PI_PARENT …`。C-nf 臂另含該臂變數（正確部分）＋同樣的 host 變數（違規部分）。
2. **根因（雙層）**：
   - `cell.py:66-77`（round 903 版）`vacant_env_passthrough()`／`recorded_agent_env()`
     盲掃 `os.environ` 的 `VACANT_*`（前件 DECISION §1 自己寫明「host 上的
     `VACANT_PI_PARENT/SELF` 會一併被帶入並記錄」＝已預見但當時判為「記錄即真相」）；
   - 分派者 env 污染：**兩個 labd daemon 同搶一個 queue**——pid 734514（官方、ppid=supervisor、
     env 零 `VACANT_*`）與 pid 734502（stray、11:15 由 pi session shell 啟動、env 帶
     `VACANT_PI_PARENT/SELF`）。smoke 3 格（14:12，`agent_env` 全合規）由 734514 分派；
     full run 由 734502 分派⇒全洩漏。`/proc/<pid>/environ` 可核。
3. **行為影響評估（誠實邊界）**：按 `vacant_network/adapters/agents.py` hook 碼
   （`loadParent()` 要求被標 pid 為活祖先＋cwd 包含關係），沙箱 PID namespace 內
   `VACANT_PI_PARENT` 的 pid 733374 不可能是祖先⇒hook 視沙箱 pi 為 root session⇒
   **C／C-nf 臂行為未被該洩漏改變**（`failed_step_review_on()` 讀的
   `VACANT_FAILED_STEP_REVIEW` 路徑不受影響）。洩漏的違規面＝**A 臂臂定義與 agent_env
   稽核**（預註冊 gate-5 要求 A 臂 `agent_env` null）＋C-nf 臂 env 不純（多帶未預註冊變數）。
   故本修訂是**臂純度／量具合規**修訂，不是行為修正；attempt-1 的 15 格結果保留為描述性
   證據、**不進入裁決管線**。
4. **併發發現（同輪記錄）**：`pg_book_store` C 臂 rc=-15（SIGTERM，15:31:35，非 124 逾時、
   非 -9 OOM、gemmawatch 無 kill 邏輯、模型前後皆健康）⇒原因**未明（UNKNOWN）**、該格
   缺分數；重發後自然重跑（cell.py 跳過條件＝`score.json` 存在，此格無）。

## 2. 改動（最小、可回退）

| 檔 | 改動 | 備份 |
|---|---|---|
| `/srv/vlab/bin/cell.py` | `vacant_env_passthrough(agent_env)`／`recorded_agent_env(agent_env)` 改收**明確 dict**（不再掃 `os.environ`）；`bwrap(…, agent_env=None)` 透傳；main 增 `--agent-env`（JSON dict、解析失敗即 exit、fail-closed）；兩處 bwrap 呼叫與 `agent_env` 記錄改走明確 dict | `cell.py.bak_r905` |
| `/srv/vlab/bin/labd.py` | 分派時若 queue JSON 該 cell 有 `env`，傳 `--agent-env <json>`（C-nf 臂）；A/C 臂不傳 | `labd.py.bak_r905` |

**改後 sha256**：cell.py `0210110a2359830a49e6550a6755d9e6f9b8ea1d161ccd43a30d30f66a2ae834`；
labd.py `33f97070b7c0ed3def94274343290facc4c9a67c0d92d782938c8e4539b36b5e`。
（備份：cell.py.bak_r905 `ee10ca02…`、labd.py.bak_r905 `f0b05b3a…`＝改前原碼。）

**對過去零影響**：既有 cell 目錄／score 不動；A/C 臂（queue env=null）`agent_env=None`⇒
空 passthrough，與舊碼在 host 無 VACANT_* 時位元組級一致；C-nf 臂只多「正確的那個」變數；
smoke 3 格（已合規）保留在 attempt-1 目錄作證據。

## 3. 測試（senior 驗收條款在內）

`audits/vlab_cell_env_passthrough_test.py`（T1–T5，round 905 全綠 ALL OK）：
- T1 passthrough 只取傳入 dict（C-nf：`--setenv VACANT_FAILED_STEP_REVIEW 0`）
- T2 記錄 dict→dict、None→`{}`
- T3 端對端：bwrap 沙箱內子程看得到（agent_env dict 傳入）
- T4 agent_env=None⇒零 VACANT_* 注入、記錄空（A/C 臂）
- **T5（senior round-905 #1 驗收）**：host 種下 `VACANT_PI_PARENT`/`VACANT_PI_SELF` 時，
  A 臂 passthrough（bwrap argv 來源）**不含有之**且 `recorded_agent_env` 為空；
  C-nf 臂 passthrough **只含** `VACANT_FAILED_STEP_REVIEW=0`、不含 host 變數。

## 4. 營運處置（保守、可逆、不刪檔）

1. 停 stray labd pid 734502（及其在跑 cell）；**保留官方 labd pid 734514**（env 乾淨）為唯一分派者。
2. attempt-1 目錄整體改名保留：`runs/e016_failed_step_ablation` →
   `runs/e016_failed_step_ablation_r905_attempt1_envleak`（15 格含 3 合規 smoke 格；
   描述性證據，不進裁決）。
3. 重發同一 job（queue JSON 不動、102 格、PAR＝daemon 現值 1）⇒新目錄
   `runs/e016_failed_step_ablation`＝全新合規 run；首格驗收＝A 臂 `agent_env` 無此欄、
   bwrap argv 零 VACANT_*；C-nf 臂 `agent_env` 恰為 `{"VACANT_FAILED_STEP_REVIEW":"0"}`。
4. 完成後走預註冊管線：`report.py --rescore` → `audits/e016_verdict_pipeline.py` →
   五態裁決表（L006 §4）→ L006／e016 audit／FINDINGS。

## 5. 邊界（不修飾）

- attempt-1 的 15 格**不構成 e016 裁決資料**（臂不純）；其中 pg_list_ops 三格（smoke、合規）
  方向（A pass／C pass／C-nf fail）與後 14 格（洩漏臂）混合存在於同一 attempt-1 目錄，
  引用時須帶「哪格是哪批」標註。
- 兩 daemon 並存＝**實驗室基建缺陷**（誰在 11:15 啟動 stray labd 未明；round 記錄無此啟動）；
  本輪處置＝停 stray、留官方；根因追查入 BACKLOG。
- `pg_book_store` C 的 rc=-15 原因未明（UNKNOWN）；重發後以新結果為準。
