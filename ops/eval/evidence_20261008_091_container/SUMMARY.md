# Vacant 0.9.1 容器端到端結果彙整（L-fake，2026-10-08）

重跑：`docker build --network host -t vacant091-e2e .`（`Dockerfile`；ctx 要放 proxy CA 與 branch 的 wheel），
各 agent 的驅動程式在 `drivers/`（`pi_drv/run.sh BUILD SCN MODE` 等）；假模型是 `ops/intake/mock_model.py`。
`runs/` 只留紀錄性檔案（events.jsonl、delivery.md、畫面、假模型請求紀錄、stdout/stderr）；
容器裡產生的假金鑰、trace 物件庫、外掛副本都刪掉了。

## 事後更新（本彙整之後）

- 問題 4（`$HOME` 寫法的唯讀 `python3 -c` 被誤擋）已修（`hookpolicy._expand_home`，只展開 `$HOME`／`${HOME}`），
  重建映像後重跑 pi Z3（`pi -p` 與 TUI）：讀 install.json **allow**、`cat …/identity.key` **deny protect_keys**
  （`runs/pi/v091_Z3_{p,tui}/`）。
- 問題 1–3（OpenCode 2.x）沒有改：2.x 的伺服器端外掛 API 沒有給人看的通道；`run` 的用戶端在伺服器端外掛看不到。
  寫進 CHANGELOG 0.9.1 的已知限制。


本報告只彙整既有證據，未在此步驟重跑容器。各代理的結果為其自行回報，我只確認了證據目錄存在（見末節），未逐一核對內容。全部為腳本化假模型（L-fake），不代表真模型的品質。

## 映像與版本

- 映像：`vacant091-e2e:latest`，由 `Dockerfile` 與 build context `/tmp/claude-0/e2e091/ctx` 建置，建置紀錄 `build.log`。基底 `node:22-bookworm`（node v22.23.3）。Image config sha256 `010a98b4b094…`，manifest list sha256 `7f6cc222398c…`。
- vacant-network 0.9.1：wheel `/tmp/claude-0/e2e091/dist/vacant_network-0.9.1-py3-none-any.whl`，來自分支 `fix/zero-config-adapters-0.9.1` HEAD `f6ea05e3`。
- vacant-network 0.9.0：PyPI。
- OpenCode 2.x：@opencode/cli 2.0.24。OpenCode 1.x：opencode-ai 1.18.35。
- pi：@earendil-works/pi-coding-agent 0.87.1。Claude Code：2.1.293。Codex：0.161.0。
- 每個 agent 執行時所有容器皆為 `--network none`、獨立 HOME，只做 `vacant install`，未給契約、金鑰或 VACANT_* 環境變數。

## 結果表（agent × 情境 × 版本）

PASS／FAIL 表示該情境的預期是否達成（L-fake）。

| Agent | 情境 | v0.9.0 | v0.9.1 |
|---|---|---|---|
| OpenCode 2.x (2.0.24) | 外掛載入 | FAIL（重現使用者回報的 "Plugin must export a default definition"） | PASS |
| OpenCode 2.x | Z1 TUI：缺 answer.txt → 回饋 → 重做 → 第 2 輪 | FAIL（外掛未載入，沒有任何回饋） | PASS |
| OpenCode 2.x | Z1 headless `opencode run` | FAIL（同上） | PASS（有保留：回饋在用戶端結束後才於背景發生） |
| OpenCode 2.x | Z2 cwd=/ 與 $HOME：不回饋、請求與對照組相同 | PASS（僅因外掛未載入，屬於無聲的未檢查） | PASS |
| OpenCode 2.x | Z2 人是否看到「Vacant 沒有檢查這份工作」 | FAIL（無聲） | FAIL（hook 有產生 note，但 2.x 外掛無 UI API，被丟掉） |
| OpenCode 2.x | Z3 讀 install.json 放行、讀 identity.key 擋下 | FAIL（沒有 hook，金鑰未建立） | PASS |
| OpenCode 1.x (1.18.35) | Z1 TUI：回饋進模型、重做、delivery.md、toast | PARTIAL → FAIL（回饋有到，但重做後的 stop 沒跑，delivery.md 過期，沒有 toast） | PASS |
| OpenCode 1.x | Z1b 第一次修錯，第 2 輪 | FAIL（第 2 次 idle 被吞掉） | PASS（第 2 輪執行，最後 allow 並寫 left_open=1） |
| OpenCode 1.x | Z1 headless `opencode run` | PASS（文件化限制：無回饋，兩版相同） | PASS（同左） |
| OpenCode 1.x | Z2 cwd=/ 與 $HOME（TUI） | FAIL（請求相同，但完全沒有任何提示） | PASS（TUI 顯示 toast） |
| OpenCode 1.x | Z3 讀 install.json 放行、讀金鑰擋下 | FAIL（install.json 讀取被 protect_write 誤擋） | PASS |
| pi (0.87.1) | Z1 TUI 與 `pi -p`：回饋、重做、delivery.md | PASS | PASS（-p 的 stdout 看不到 Vacant 文字） |
| pi | Z2a/Z2b cwd=/ 與 $HOME | FAIL（沒有任何提示，即事故情境） | PASS（TUI 顯示提示；-p 無聲） |
| pi | Z3（指令用 `$HOME` 字面寫法）讀 install.json 放行、讀金鑰擋下 | FAIL（讀取被誤擋） | FAIL（讀取仍被誤擋；金鑰正確擋下） |
| pi | Z3abs（同一指令用絕對路徑） | FAIL（讀取被誤擋） | PASS |
| Claude Code (2.1.293) | Z1 `claude -p` 與 TUI：回饋、重做、delivery.md | PASS | PASS（TUI 顯示 Stop 審查與「已重做」摘要） |
| Claude Code | Z2 cwd=/ 與 $HOME：請求與對照相同 | PASS（但人看不到提示） | PASS（TUI 與 hook 事件顯示「沒有檢查」） |
| Claude Code | Z3a 讀 install.json | FAIL（被誤擋） | PASS |
| Claude Code | Z3b 讀 identity.key | PASS | PASS |
| Codex (0.161.0) | Z1 headless（json 與純文字）與 TUI | PASS | PASS（headless 只看得到 "Done"；TUI 看得到審查與摘要） |
| Codex | Z2 cwd=/ 與 $HOME（TUI） | PASS（無聲） | PASS（TUI 顯示「沒有檢查」；headless 無聲） |
| Codex | Z3 讀 install.json 放行、讀金鑰擋下 | FAIL（讀取被 protect_write 誤擋） | PASS（絕對路徑） |

補充（Claude Code）：hook 合成負載計時，PreToolUse 每次約快 20–35%（v0.9.1 約 112–121 ms，v0.9.0 約 146–162 ms）。這是行程啟動成本量測，不是真實工作階段。

## 發現的問題（v0.9.1）

Vacant 程式碼位置依 OpenCode 代理的唯讀原始碼審查（`vacant_network/adapters/agents.py`，commit `f6ea05e3`）。

1. **OpenCode 2.x：「沒有檢查」與回饋說明沒有送到人眼前。** `zerostop.untraceable()` 回傳 `user_message`；`hook.py` 約 170–173 行放進 `note`；`agents.py` 約 759 行的 toast 候選（`ctx.ui.toast` 等）在 2.0.24 的外掛 context 中都不存在（見 `opencode2/plugin_ctx_probe_2.0.24.json`），所以在 `agents.py` 約 788 行的 stopCheck 中被丟掉。文件 `zerostop.py` 也自承 OpenCode 不顯示此說明。
2. **OpenCode 2.x：headless `opencode run` 在回饋輪之前就返回。** `agents.py:547-549` 的 NONINTERACTIVE 只認 `VACANT_OPENCODE_NONINTERACTIVE` 或 argv 含 `run`，但外掛跑在 `serve --service` 裡，argv 沒有 `run`，於是被當成互動模式；`agents.py:798` 執行 stop 檢查，`agents.py:809` 呼叫 `ctx.session.prompt`。用戶端已印出 "Done." 並以 0 退出，修正在背景完成（量到的請求：退出時 3 筆，之後 2 筆）。`--standalone` 下完全不跑 stop 檢查。
3. **OpenCode 2.x TUI：`/exit` 不會產生 session_end。** 清理只在 `serve --service` 結束時執行（`agents.py:822-825`），而服務比 TUI 活得久，因此「沒說做完就結束」的 zerostop.ended 在離開 TUI 時不會執行。
4. **`$HOME` 寫法的唯讀 `python3 -c` 被誤擋（v0.9.0 與 v0.9.1 都有）。** `hookpolicy.py:175-177` 的 `_single_py_c` 只要指令含 `$` 就回 False，於是 `hookpolicy.py:403-404` 的唯讀例外被跳過；指令落入 `_CODE_WRITE_HINT`（`hookpolicy.py:83`，`\bopen\s*\(` 一律算寫入），在 `hookpolicy.py:913-915` 被拒絕。絕對路徑形式則放行。這是過度阻擋，不是安全漏洞；金鑰保護仍有效。
5. **v0.9.0 的問題，v0.9.1 已修：** 外掛匯出形狀錯誤（OpenCode 2.x 報 "Plugin must export a default definition"；v0.9.0 寫的是裸函式匯出，v0.9.1 改為 `export default { id, server, setup }`，`agents.py:320`）；2 輪後第二次 idle 被吞掉；TUI 沒有 toast；協定讀取 install.json 被誤擋（protect_write）；cwd=/ 與 $HOME 無聲。

觀察（非錯誤）：`vacant --version` 不是有效旗標（argparse 要求 cmd）；`vacant install` 不受影響，回傳 0。

## 誠實的限制

- 全部是 L-fake：腳本化假模型（`ops/intake/mock_model.py`），不能代表真實模型的品質；不做任何真模型的效果主張。
- 「headless 看不到」是表面限制，不是 Vacant 的 bug：`pi -p`、`codex exec`、`claude -p` 預設不顯示 hook 的 systemMessage；OpenCode `run` 在第一個 idle 就結束，沒有回饋輪。
- Codex 以 `-s danger-full-access` 執行，因為 Docker 預設 seccomp 不允許 bwrap 建立 namespace；預設 workspace-write 沙箱與 hook 的互動未測。
- OpenCode 2.x 的受管服務會綁固定埠（49374），用 `--network host` 時平行容器會衝突；所有最終結果都用 `--network none`，第一次嘗試（`_attempt1_hostnet`）作廢、沒有收進來。
- OpenCode 1.x 的 TUI 首次啟動在 `--network none` 下約 80 秒才出第一個畫面；驅動程式改為等待第一個非空白畫面。
- Claude Code 以 root 執行，使用 `--permission-mode acceptEdits --allowedTools Bash`。其 Z3a 的指令形式在彙整報告中沒有記錄，因此無法判斷它是否也受 `$HOME` 寫法影響。
- 未測：OpenCode 1.x 的 `opencode run` 搭配 `VACANT_OPENCODE_NONINTERACTIVE`（只有 `vacant do` 會設）；OpenCode 2.x 的 TUI 在真實資料夾中的完整路徑外的情形。

## 證據目錄核對

以下路徑已用 `ls` 確認存在（本步驟未逐檔核對內容）：

- OpenCode 2.x：`runs/opencode2/`（存在）
- OpenCode 1.x：`runs/opencode1/`（存在）
- pi：`runs/pi/`（存在，含 `root_cause_single_py_c.txt`）
- Claude Code：`runs/claude/`（存在，含 `z2_body_compare.txt` 與 timing 目錄）
- Codex：`runs/codex/`（存在，含 `README.txt`）
- 建置：`build.log`、`Dockerfile`（存在）

