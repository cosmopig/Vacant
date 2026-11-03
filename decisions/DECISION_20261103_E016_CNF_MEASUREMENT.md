# DECISION 2026-11-03 — e016 C-nf 消融臂的共用量具改動：cell.py 的 VACANT_* env 明確通過＋記錄

> 共用量具改動（`/srv/vlab/bin/cell.py`）。依 `ASSIGNMENT.md` 紅線：
> 「cell.py/labd.py/report.py 是共用量具：要改就寫 DECISION 檔說明理由；不許因為這次改動過去實驗結果變掉。」

## 1. 改動內容（最小、純增量）

`/srv/vlab/bin/cell.py` 新增兩個純函式＋兩行接入（diff 見 §4）：

1. `vacant_env_passthrough() -> list[str]`：把 cell.py 行程環境裡的 **`VACANT_*` 變數**以
   **明確 `--setenv`** 加入 bwrap 命令線（`bwrap()` 內、venv 區塊之後）。
2. `recorded_agent_env() -> dict`：同一批變數寫進該格 `cell.json` 的 `agent_env` 欄位。

**動機**：bwrap 的預設 env 繼承「剛好」能傳進這些變數（2026-11-03 實測：父層
`FOO_TEST=123` 在沙箱內可見），但共用量具不能把臂的行為建立在「剛好」上：
- 明確 `--setenv`＝命令線可稽核（`events`/`argv` 層）、不依賴 bwrap 版本行為；
- `cell.json.agent_env`＝臂行為可自格子證據驗證（e014 gate-5 先例：「C 格 vacant_sha==
  b8b715af、A 格 null」——同一稽核精神）。

## 2. 對過去實驗的影響：**零**

- 純增量：無刪除、無既有函式簽名改動；`bwrap()` 新增一行 `b += vacant_env_passthrough()`。
- 既有臂（A/C/CB、e001–e015 全部）發射時 cell.py 行程環境**沒有** `VACANT_*` 變數
  （labd 的 `env` 欄位過去只載 `VLAB_APPEND_SYSTEM` 等 `VLAB_*`）⇒ 兩函式皆回空 ⇒
  bwrap 命令線與 `cell.json` 與舊碼**位元組級一致**。
- 已完成 run 的格子目錄是唯讀證據、不受影響；此改動只影響**今後**發射的格子。
- 測試：`~/dev/ops/audits/vlab_cell_env_passthrough_test.py` T1–T4（T4＝零影響斷言、
  T3＝bwrap 沙箱端對端）；RED（`AttributeError`）→ GREEN（ALL OK）。

## 3. 邊界（誠實）

- 過濾式是 **`VACANT_` 前缀**：任何 `VACANT_*` 變數都會通過並被記錄——包括非實驗的
  （例如 pi 工作階的 `VACANT_PI_PARENT`/`VACANT_PI_SELF`，本機 shell 就有）。
  這是**特性**（記錄即真相），但意味着：今後發射臂時，環境裡的 `VACANT_*` 變數即臂定義的一部分，
  必須寫進 packet 與 queue 檔（e016 已如此：C-nf 臂＝`VACANT_FAILED_STEP_REVIEW=0`，
  queue 檔 per-cell `env`＋packet §2.2 明載）。
- 本改動**不改變** `VACANT_FAILED_STEP_REVIEW` 的產品語義（那是 round 902 產品改動、
  commit b8b715af、TDD `tests/test_failed_step_switch.py` 6/6；預設未設＝位元組級相同、fail-open）。
- labd.py 的 per-cell `env` 支援是 round 900 既有（`run_cell` 的 `env` dict、r900 .bak 在案），
  本 DECISION 不重複涵蓋。

## 4. 稽核資料

- 改動前備份：`/srv/vlab/bin/cell.py.bak_r903`
- 改動後 `sha256(/srv/vlab/bin/cell.py)`＝`ee10ca02512b798197efb88cafec8b051adb4d3e32ab21f254e7d1f41d4149af`
- 測試：`python3 ~/dev/ops/audits/vlab_cell_env_passthrough_test.py` → `ALL OK`
- 引用方：`~/dev/ops/packets/e016_failed_step_ablation.md` §2.2、§6 gate 5
