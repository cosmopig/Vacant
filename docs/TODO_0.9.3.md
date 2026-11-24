# 0.9.3 待辦（2026-11-22 起；rc6 只動訊息、輸出、中斷處理與 README，下列一律不進 0.9.2）

每一項都要先完整設計，再加政策差分情境與一輪對抗審查；不擠進只動訊息的版本。

## 1. lockfile 要不要固定（cargo／go／npm）

- 現況（rc5-final／rc6）：`Cargo.lock`、`go.sum`、`package-lock.json` 都不在固定清單；`package.json`、`Cargo.toml`（只有根目錄）、`go.mod` 有固定；npm 的 `node_modules` 另外檢查。
- 不能單純把 lockfile 加進清單：agent **正當地**加一個相依套件時，本來就會改 `Cargo.lock`／`go.sum`／`package-lock.json`，固定住會讓合理的修改被拒交。
- 要設計的是「驗收用哪一份 lockfile、寫回時怎麼標示」，例如驗收用 agent 的版本但訊息標出 lockfile 有變、或 manifest 沒變時才固定 lockfile。重現：`~/dev/ops/cg_test` 的 `cargo_e`、`go_e`。

## 2. 巢狀 manifest 與 go.work（兩條路徑行為一致）

- cargo 自動偵測只固定根目錄 `Cargo.toml`，`--check` 路徑卻有固定巢狀的（`cargo_d2`）；agent 新增的 `go.work` 會進驗收副本（`go_i2`）。
- 要和「`--check` 與自動偵測兩條路徑行為一致」一起設計，不分開補。

## 3. 只在刻意作弊時出錯的兩項

- cargo 新增 `build.rs` 在編譯期改回被固定的測試檔（`cargo_i2`）；go 新增帶 `TestMain` 的 `*_test.go`（`go_f2`）。
- 至少：新增會影響編譯的檔（`build.rs`、`go.work`、build tag 檔、新測試檔）要像 `.cargo/config.toml` 一樣有專門的提示；`tests_tampered` 要涵蓋新增的測試檔。

## 4. 狀態目錄單一入口

- 產品碼有 5 處直接用 `Path.home()`：`cli.py`（`~/.vacant`、`~/.vacant-mcp`）、`vrun/gateshim.py` 與 `vrun/launcher.py`（`~/.vacant-run/<task>`）、`controller.py`（`~/.vacant-mcp`）。rc6 只修了 demo gate 那一處。
- 應該一律經過 `VACANT_HOME` 之類的單一入口（測試隔離 `tests/conftest.py` 目前靠把 HOME 換掉才蓋得到）。

## 5. 寫回途中 SIGKILL

- 寫回途中被 SIGKILL（或斷電）會留下寫一半的專案；備份在 run 目錄但沒有任何紀錄指過去（KNOWN_LIMITS 第 21 條）。
- 做法：寫回前寫一份 journal（要換哪些檔、備份在哪），下一次啟動或 `vacant audit` 時檢查未完成的 journal 並提示還原。
- `start-copy-*`（開始時的整份專案複本）在被 SIGKILL 的 run 裡**永遠不會被 gc 清**，大專案會一直佔空間；有了 journal 之後要定保留期限並讓 gc 能清（rc6 只保證不清，不處理佔用）。

## 6. 單次上限不只看牆鐘（原型在 proto/0.9.3-attempt-budget）

- 等 atimeout 的結果再接著量；接量測前先把每秒 `os.walk` 的成本處理掉（排除 node_modules／.venv／.git、拉長間隔），收據多出的 `cap_mode`／`cut_reason` 欄位寫進變更說明。

## 7. rc6 定案查證留下的小項

- 啟動期的 Ctrl-C：極少數情況（370 次裡 1 次，run 開始後約 31ms）SIGINT 被 Python 的 import 鎖吞掉，run 照常跑完交件——使用者按了 Ctrl-C 卻沒有停（KNOWN_LIMITS 20）。可能做法：入口更早裝上「只記下」的處理器、並在 run() 開始時檢查。
- `vacant audit show` 對語法錯誤（load_error）那一行沒有檔名與行號（交件訊息已有，audit 的格式化沒有跟上）。

## 8. 驗收與 agent 子行程的記憶體上限

- confirm2（11/23）：agent 寫出的 `encode()` 是沒有出口的 `while True`，agent 自己跑測試與驗收時各吃到 5–7 GB，全域 OOM 四次（KNOWN_LIMITS 22）。
- 做法：驗收子行程設 RLIMIT_AS 或放進有 MemoryMax 的 cgroup，超過就記成這一次嘗試「記憶體超限」、不放行，而不是讓整台機器 OOM；agent 的子行程同理（至少文件建議用 cgroup 跑）。
