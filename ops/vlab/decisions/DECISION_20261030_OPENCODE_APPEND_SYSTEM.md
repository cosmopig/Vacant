# DECISION：cell.py 支援 OpenCode 的 VLAB_APPEND_SYSTEM——前置附加至 instruction（2026-10-30）

> 一頁：e004（OpenCode 全盤評測）H/M/S 臂 102 格在 `/srv/vlab/bin/cell.py` 的
> `VLAB_APPEND_SYSTEM` 分支對非 pi agent 拋 `SystemExit`，全部 infra 崩潰、觸發封包 §4
> 機構回退（STATE round 371，P20261030_2142-2）。本檔記錄複測前置的決定：
> OpenCode 臂改用「前置指引」機制，不改變 pi 臂行為、不改變任何既有實驗結果。

## 1. 事實（可重查）

- pi CLI 有 `--append-system-prompt`；cell.py 原本只在 `a.agent == "pi"` 時用它，
  其餘 agent 一律 `raise SystemExit("VLAB_APPEND_SYSTEM 目前只支援 pi")`（改前 L158）。
- OpenCode CLI **沒有** `--append-system-prompt`（或任何等價的系統提示旗標）：
  `/srv/vlab/tools/opencode/bin/opencode run --help` 的完整旗標表裡沒有該選項
  （2026-10-30 實查）。`opencode run` 只接受 `message`（positional）作為輸入。

## 2. 決定

- `VLAB_APPEND_SYSTEM` 指向的檔案內容，對 **OpenCode** 以**前置指引**方式附加：
  `f"{txt.strip()}\n\n---\n\n{instruction}"`，即
  `argv = ["opencode", "run", "--format", "json", <上述字串>]`。
  指引與原 instruction 之間以空行＋`---` 分隔，instruction 原文逐字保留在末尾。
- **pi 臂行為不變**：仍走 `["pi", "-p", "--mode", "json"] + ["--append-system-prompt", txt, instruction]`，
  `info["append_system"]` 記錄形狀（path/sha256）與改前逐位元組相同。
- 其他 agent（非 pi/opencode）仍 `raise SystemExit`，錯誤訊息更新為「目前只支援 pi 與 opencode」。
- 審計區分：OpenCode 格的 `info["append_system"]` 另加 `"mode": "prepend"` 欄位，
  讓 cell.json 可分辨附加機制（flag vs prepend）；pi 格不加該欄位。
  沒有任何程式碼讀取 `append_system`（2026-10-30 grep 全 repo 與 /srv/vlab 確認），
  既有 cell.json 資料不受影響。

## 3. 邊界與口徑

- **這是附加到 instruction 文字，不是系統提示。** OpenCode CLI 沒有系統提示入口；
  模型看到的是「指引＋分隔線＋原任務」一段文字。引用 OpenCode 臂結果時不得說
  「附加到系統提示」，口徑為「前置指引」（reviewer 審查臂 H/M/S 的指引以此生效）。
- 不改變 bwrap 隔離、scorer、`vacant install` 流程；不重新計分任何既有格子。
- 既有結果不受影響：e001/e002（pi 臂）與 e003（OpenCode、未設 `VLAB_APPEND_SYSTEM`）
  走的程式路徑與改前相同；e003 的 GO 結論與 2 格 C 組磁碟用量數值不因此改動。
- 本決定**不構成** e004 複測的授權：複測仍需 e003 級 smoke 先過（見 BACKLOG
  「e004 H/M/S 複測前置」），複測結果以 e004 封包 §3 預註冊判準判定，期間不預設結果。

## 4. 驗收

- 工單 P20261030_2157-1：`ast.parse` 語法檢查＋字串斷言（VLAB_APPEND_SYSTEM/opencode/pi
  皆在 cell.py），改前 L158 對 opencode 拋 SystemExit、改後不再拋。
- 影響面：cell.py 改動限 `if extra:` 分支（≤10 行）；本檔為新增 DECISION 記錄。
