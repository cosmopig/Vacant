# e005 研究包：OpenCode 五臂冒煙（A/C/H/M/S 各 1 格，預註冊）

> 預註冊：本包在發射前寫死假設、臂、判準。發射後不改判準；要改就開 e005b 並註明。
> 定位：本包是**冒煙 GO/NO-GO**——驗證「cell.py 機構修復後 H/M/S 前置指引路徑在 OpenCode 上可跑」＋「C 臂正確掛載並留下 trace 證據」＋「M 臂有真第二 agent 證據」；**不是**成效量測，不產成效結論。
> 量具：`/srv/vlab/bin/report.py`（共用量具，本輪不改動）。本包只含預註冊判準；實際結果待審計後另 commit 補入 §5，不預填。

## 0. 背景與假設

- e004 OpenCode 全盤五臂觸發**機構回退**：`/srv/vlab/bin/cell.py:158` 對非 pi agent 且設定 `VLAB_APPEND_SYSTEM` 直接 `SystemExit("VLAB_APPEND_SYSTEM 目前只支援 pi")`，H/M/S 102 格全落在此確定性失敗路徑（e004_opencode_polyglot.md §4「觸發事實」；佇列檔已移 done 為 `.fallback.json`）。
- 機構修復（本冒煙之前提，已落地）：
  - `c76ff988`（`DECISION_20261030_OPENCODE_APPEND_SYSTEM`）：cell.py 支援 OpenCode 前置指引——OpenCode CLI 無 `--append-system-prompt`，改為將指引文字前置於任務描述（`mode: "prepend"`）；pi 臂與既有結果不變。
  - `bf1a9f1a`（e002_M 臂檔）：第二 agent 審查指令改 `opencode run`（保留 `pi -p` 備選；環境提供 subagent 工具亦可用）。
- 假設（冒煙層，互相獨立）：
  - H-5arm：機構修復後 A/C/H/M/S 五臂皆能在 OpenCode 格子完成**執行流程**——皆正常結束、無 infra 崩潰；pass/fail 只記錄、不判定。
  - H-mnt：C 臂 `vacant install` 正確掛載並在該格 HOME 留下 trace 證據。
  - H-multi：M 臂留下**真第二 agent 證據**（不是提示文字而已）。

## 1. 實驗設定（5 格）

| 項 | 設定 |
|---|---|
| agent | opencode（真實 agent，`opencode run --format json`） |
| 臂 | `A`（無 Vacant、對照）／`C`（究責：`vacant install`）／`H`（自檢指引 e002_H.md）／`M`（第二 agent 審查 e002_M.md）／`S`（利害框架 e002_S.md） |
| 任務 | `polyglot_py`／`pg_affine_cipher`（每臂 1 格、同題配對） |
| 設計 | A/C/H/M/S × 1 題 × 1 rep ＝ **5 格** |
| 超時 | 900 s/格（冒煙預算；不套 e004 全盤的 1800 s） |
| 模型 | gemma-4-12b-it-qat（1004 本機，`http://100.86.226.21:1234/v1`） |
| vacant_sha | `bf1a9f1afb211460b48611f8f28b1d9433985c4a`（含 c76ff988、bf1a9f1a） |
| H/M/S 指引 | `VLAB_APPEND_SYSTEM` → `/srv/vlab/arms/e002_{H,M,S}.md`（cell.py prepend 模式） |
| A 臂 | 不裝 Vacant、不碰 `~/.vacant` |

## 2. 預註冊判準（發射前寫死）

**GO ⇔（五條全成立）**
1. **5 格皆正常結束、無 infra 崩潰**：每格有 `cell.json`（agent 有 rc、rc 可非零）與 `score.json` 且 `pass ∈ {true,false}`；infra（無 `score.json` 或 `pass=None`）＝ 0 格。
2. **H/M/S 臂不拋 SystemExit**：舊機構路徑 `cell.py:158 SystemExit("VLAB_APPEND_SYSTEM 目前只支援 pi")` 不再觸發——三格 `cell.json` 皆有 `append_system` 記錄且 agent 實際啟動（agent 啟動前無機構層例外）。
3. **C 臂留下 trace 證據**：`install_rc=0`，且該格 `vacant_home.tgz` 存在、非空、含 `.vacant/intake/hooks/events.jsonl`（Vacant 有真的記錄，不是只裝到 plugin）。
4. **M 臂有真第二 agent 證據**：M 格 `events.jsonl`/stderr 有啟動第二 agent 的證據（shell `opencode run`／`pi -p` 或 subagent 工具呼叫）；無證據 ⇒ 降級「提示式自檢」、記 **UNKNOWN**（量不到，不是負結果）。
5. **A 臂純對照**：該格 HOME 不產生 `~/.vacant` 資料（無掛載）。

**NO-GO（任一不成立）** ⇒ e004 H/M/S 重發射暫緩；先修機構/臂檔、複測冒煙、綠了再議。

**明言非判準**：通過率、臂間差異、成本指標——本包**只作描述**，不進 GO/NO-GO、不引成效結論
（1 題 × 1 rep 不足以支持任何成效主張；「各臂在 OpenCode 上有無成效」屬全盤盤、另包預註冊）。

## 3. 回退與邊界

1. **Fail-open**：Vacant 自身故障（plugin 錯、鏈寫入失敗）不得擋住 agent 交件——使用者任務照常結束、照常打分；但「靜默吞掉」（C 臂無任何 trace 證據）落入判準 3 的 NO-GO。
2. **版本**：vacant_sha 釘 bf1a9f1a；換版本重跑＝開 e005b 註明。
3. **模型邊界（H-12 類）**：gemma-4-12b 本地量化；結果不外推到其他模型／預算／任務庫。
4. **磁碟**：5 格 ×（`app_final.tgz`＋`vacant_home.tgz`＋events）量級與 e003 4 格相當；封頂/GC 政策照 disk_top_priority 不變。
5. **下一步（另包）**：GO ⇒ e004 H/M/S 臂重發射（或 OpenCode 全盤）另開獨立預註冊封包；本包不含其判準。

## 4. 可複現檔

- 佇列檔：`/srv/vlab/done/06_e005_opencode_five_arm_smoke.json`（5 格；頂層 vacant_sha=bf1a9f1a、timeout=900）。
- 原始格：`/srv/vlab/runs/e005_opencode_five_arm_smoke/polyglot_py-pg_affine_cipher-opencode-<arm>-r1/`（`cell.json`、`score.json`、`events.jsonl`、`app_final.tgz`、C 臂 `vacant_home.tgz`）。
- 機構修復：`c76ff988`（DECISION）、`bf1a9f1a`（`ops/vlab/arms/e002_M.md`）。
- 判準核對（發射後）：`report.py e005_opencode_five_arm_smoke` 出 `REPORT.{json,md}`；實際結果由 `opencode_cell_audit`/report 審計後補入 §5（另 commit，不預填）。
