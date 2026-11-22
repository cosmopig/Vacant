# rc5 compared with rc4 / wheel 37005ec2 — what changed in `vacant do` restart mode

- rc4 is `652c50d36`. Its code is identical to the release candidate wheel `37005ec2aa91…`, which the running confirm2, confirm2c and atimeout batches measure.
- rc5 was first frozen at `83e84da29`. It was reopened twice for the independent verification: first for P1/P5, refrozen with product code at `4457b3ecb`; then for N1/N2. **The final product code is on `redo/rc5` at the commit tagged `rc5-final`.** After N1/N2 there was one more small closing fix: the non-package test-dir import order, plus the load-error line in the message. Later commits on `redo/rc5` change only tests, reference material and docs. The final freeze is tagged `rc5-final` on `redo/rc5`. The release branch's commits are listed in RELEASE_PREP. It came out of five rounds of adversarial review by Devin, written up in `tests/adversarial_rc5_repro/` (round 1 and round2–round5).
- The fixes were written by agy and reviewed by Claude. Every round reran the full test suite and the policy differential.

## The delivery policy did not change (evidence)

`tests/adversarial_rc5_repro/policy_diff_rc4_rc5.py` runs the same scenarios with the same scripted agent through rc4 and rc5 and compares:
- the exit code;
- `accepted` and `delivered_attempt`;
- each attempt's (accept, passed, run);
- the number of agent calls;
- a sha256 of every file in the project tree afterwards.

Result at the final freeze: **10/10 identical, plus 3/3 expected differences correct** (see P1 and N1 below). The 10 identical scenarios are:
- passes on the first attempt;
- fails, then passes on the second;
- never passes, so the best attempt is delivered;
- the agent edits the test file;
- the agent exits non-zero but the tests pass;
- a deletion in a subdirectory;
- a new module the tests import (`solution.py` does not exist at start);
- no tests;
- `--check`;
- npm.

The two expected differences are bug fixes:
- `py_stdlib_name_fixed`: rc4 rejected a correct fix; rc5 accepts it.
- `py_stdlib_name_broken`: rc4 accepted a broken module; rc5 rejects it.
- `py_tests_package` (N1): rc4 rejected a correct fix when the tests live in a `tests/` package; rc5 accepts it.

Not covered by the differential: cargo and go (not installed on the test machine), and a real 600 s time-limit cut. pytest was exercised by the independent verification inside a project `.venv`.

## Behaviour changes, all outside a normal run
These only take effect when something abnormal happens: an escape, a concurrent edit, tampering, or an odd filename.

1. **node_modules.** The agent gets its own copy of `node_modules` (reflink when the filesystem supports it, otherwise a plain copy) instead of a symlink to the project's copy. Symlinks that point outside are replaced by real files in the copy. The original is checked with an lstat manifest (size, mtime, ctime, inode, mode, link target) at start, before each check and at the end. A change stops the run with exit 43 (as in rc4) and nothing is written back.
   This also changes the agent's environment in ordinary npm runs: it now works on a copy, which costs time to make (recorded as `copy_s`). The npm scenario in the differential is identical.
2. **The check is pinned more widely.** More files are kept fixed: restored to their start content before each check and never written back.
   - manifests reached by the check: `package.json`, Makefile, Cargo.toml, go.mod and others, including nested ones and npm `--prefix`;
   - files named in the check command or in a shell or Makefile check script;
   - `python -m` modules;
   - runner configs, including `.npmrc`, `.yarnrc*`, babel/swc/tsconfig, `.cargo/config*`, playwright/cypress/wdio/ava/nyc/nox configs, and files referenced from jest/mocha config keys in `package.json`;
   - files matched by `unittest discover` patterns.

   Agent-created files of these kinds are left out of the check copy and not written back. The same applies to new `__init__.py` files in test directories, and to new files that would shadow a module that already resolved at start (stdlib, an installed package, or an existing project module).
3. **The check runs against the start snapshot.** Before each check, the files the attempt did not touch are copied from the start snapshot, not from the live project. An agent writing directly into the real project therefore cannot make the check pass.
4. **Write-back against the start snapshot.**
   - Only files that existed at start and were deleted by the delivered attempt are deleted. Files that appear during the run are left alone and listed.
   - If a path changed in the project during the run AND the delivered attempt also changes it, **nothing is written back and the exit code is 43**. The message lists the conflicting paths and where the accepted attempt's files are kept. **This is a new exit-43 condition.**
   - Every file is re-checked just before it is replaced.
5. **Detached processes are killed.** On Linux, a subreaper catches descendants that detach. They are killed after each attempt, after each check and at the end, and recorded with their pid and command line. On other platforms this layer does not exist, and the message says so.
6. **Upfront refusal.** If the project directory is not writable, the run stops before the agent runs (exit 43). The agent's copy is always writable.
7. **State and work roots** (`VACANT_HOME`, `VACANT_WORK`) are never copied into the agent's workspace, even when they sit inside the project. This keeps the signing keys out of the workspace and stops the recursive-copy crash.
8. **Receipts and audit.**
   - Every string is byte-safe, so non-UTF-8 file names or prompts no longer suppress the receipt.
   - Before writing the receipt, permissions on Vacant's own state are repaired. If it still fails, the message starts with a WARNING.
   - `vacant audit list --strict` now fails on restart runs that have no signed receipt.
   - New fields: `acceptance_integrity` (traced/untraced) with reasons; `outside_changes`, `appeared_during_run` and `write_back_conflicts`; `detached_processes`; `acceptance_dependencies_changed`; `not_delivered`; `time_limit_s` per attempt; and timing fields.
9. **Messages state facts only.**
   - `kept fixed (restored to their start content before each check): …` replaces "protected".
   - Untraced checks get a short tag on the acceptance line.
   - A `NOTE:` line appears only when the delivered attempt changed a file the check reads or runs that was not kept fixed.
   - Each time an attempt was cut at its time limit, the message says so, and suggests raising the limit when every attempt was cut.
   - Changes made to the project outside the delivered attempt are listed, with prominent lines for `.git/hooks`, refs, `.pth` files and `.git/objects`.
10. **Mode bits.** Restored files keep their mode bits, so `./verify.sh` stays executable. The original `node_modules` is no longer chmod-ed, so killing Vacant can no longer leave it read-only. Both were regressions introduced inside rc5 and fixed before the freeze.

## P1: a project module named like a stdlib module (fixed when the freeze was reopened)
- In rc4 (`37005ec2`) and in rc5 up to `83e84da29`, the isolated Python runners appended the project dir to `sys.path`, so it came after the stdlib.
- Effect: a project's own `queue.py` or `statistics.py` was shadowed by the stdlib module of the same name during the check. A correct fix was judged FAIL, and a broken module could be judged PASS.
- The runners now put the project dir first, which is what `python -m unittest` / `pytest` do in the project. New files that would shadow a name that already resolved at start are still left out (rc5e).
- **Effect on measured batches: none.** The modules of all 206 Python tasks used with rc1+ wheels were checked against `sys.stdlib_module_names`:
  - polyglot_py: 34;
  - exercism_py_unused: 40;
  - exercism_py_hard: 26;
  - exercism_py_pool: 106.

  None collides. The JS batches use relative imports and are not affected.

Also changed when the freeze was reopened:
- **P5:** unreadable project files now stop the run before the agent starts, with exit 43, a message and a receipt, instead of a traceback.
- Dynamic imports in kept-fixed files make the run `untraced`.
- `vacant audit list` / `show` mark a write-back conflict run as "accepted, not written back (conflict)".
- Shadowing files get their own wording.

## N1 and N2 (fixed when the freeze was reopened the second time)
- **N1.** On the `python_unittest` path, tests in a `tests/` package that import a module at the project root (`tests/test_mycal.py` doing `import mycal`) failed with `ModuleNotFoundError`, even when the fix was correct. The project root is now on the path, matching `python3 -m unittest` run at the project root.
  - Flat projects are unchanged; every measured batch is flat.
  - For a non-package `tests/` dir, the import order is: **test dir first, project root second**. This is the same order as `python3 -m unittest discover -s tests` and pytest, so a module in `tests/` (e.g. a kept-fixed `tests/expected.py`) wins over a same-named module at the root. This order was corrected after the third verification; for a short while N1 had the root first.
  - Where rc5 is more lenient than plain `python3 -m unittest` run at the root: default discovery does not descend into a non-package `tests/` dir, so it would run no tests at all. rc5 still runs those collected test files.
  - The `src/` layout (`src/pkg` plus `tests/`) is NOT given an extra path entry: it fails just as running unittest directly would without PYTHONPATH.
  - **Effect on measured batches: none.** All measured Python banks are flat; their test files sit at the workspace root.
- **N2.** A dynamic import inside a helper module the tests import, up to depth 2, now makes the run `untraced` with reason `dynamic-import:<file>`. The module under test itself is not scanned.

## The measured path: zero-config `python_unittest`
- The confirm and unused40 batches measured this path. rc5 changes it only in abnormal cases: shadow files and new test-directory `__init__.py` are left out of the check; a changed package `__init__.py` prints a NOTE; the check runs against the start snapshot.
- A normal run of this path is covered by the differential and is identical.
- In every batch run so far, the native arm and the product arm both have **accepted_but_wrong = 0** and per-attempt `signal.accept_fail = 0`. The batches are confirm1, confirm1c, unused40, hardpy26, W3-5 (screen and confirm), redo1_pi, redo1_opencode, the screen16 runs, and confirm2 partial. Source: each batch's REPORT.json. The grader is the task's pristine visible tests (`grader_kinds = visible_tests_pristine`). So the 0 means "nobody got a pass by tampering with the tests". It does NOT mean "the answers are correct beyond the tests".

---

## rc6 相對 rc5-final：只有訊息、輸出與中斷處理

基於 rc5-final（`1d764cc69`）的 11 次新使用者實測（`~/dev/ops/ux_rc5final/logs/`），rc6 在 `redo/rc6` 分支只調整**訊息、輸出、中斷處理與三語 README**；選哪一次、交什麼、次數與時限、驗收執行方式、結束碼 `0`／`40`／`43` 條件全部維持不變。

### 九項變動摘要

1. **Ctrl-C／SIGTERM 中斷處理（`b3d380380`）**：收到 `SIGINT`／`SIGTERM` 時，忽略重複訊號、砍掉 agent 行程群組並沿用既有 Linux subreaper／`/proc` 機制清理脫離子孫，不改動原專案，印出單行中斷與工作目錄可刪提示，寫入標為 `interrupted` 的 Ed25519 簽章收據（`vacant audit list/show` 亦識別為 `result=interrupted`），以 `130` 結束、無 Python traceback。
2. **執行中可視性與 `--stream`（`6f78d71cc`）**：每次嘗試開始時印出 `attempt_N/logs/agent_stdout.log` 路徑與 `tail -f` 指令；新增 `--stream`（預設關閉）即時串流 agent stdout／stderr 至終端機並同步寫入日誌檔。
3. **未全過時的失敗摘要（`983c0104f`）**：明寫 `passed/total tests`、列出各次嘗試的通過數與 `[delivered]` 標記、摘錄第一個失敗測試名稱與 1–2 行原因（`first_problem`）、明講交回的那次已寫入專案，並補一行 `exit code 40` 說明。
4. **基線已通過標題（`27d2cbb30`）**：政策不變（agent 照跑 1 次），但標題改為先講 `tests were already passing before the agent ran`，再說明 agent 改了檔案或未做改動。
5. **降噪與符號說明（`fd8205c09`）**：`not delivered` 裡的 `__pycache__`／`.pytest_cache` 快取檔於人讀摘要折成單一數量（`result.json` 保留完整清單、非快取未交回檔照列）；於 `changed files` 行內與 `vacant do --help` 說明 `+`／`~`／`-` 含義。
6. **npm／`node --test` 人話說明（`262074d8a`）**：保留既有的 untraced 判定（不動保護／寫回政策），於人讀摘要將 `[unsupported-option:node:--test]` 換成說明 `node --test` 動態探索測試檔、Vacant 無法靜態追蹤全部輸入的句子；並對僅看退出碼的驗收（含 `npm`）明講只回報通過或不通過、無分項數。
7. **`vacant demo gate` 尊重 `VACANT_HOME`（`64c16ce8f`）**：未給 `--root` 且設了 `VACANT_HOME` 時寫入 `$VACANT_HOME/demo-gate`（不再寫進真實 `~/.vacant-run/demo-gate`），並於輸出開頭明講寫入目錄。
8. **`vacant audit show` 顯示逐次嘗試與第一個失敗測試（`c4b8d3f15`）**：簽章收據的每次嘗試保留 `first_problem`（有失敗時）；`vacant audit show` 列出每次嘗試的結果、`[delivered]` 與收據裡記載的 `first_problem`（舊收據無該欄時只顯示收據裡有的欄位）。
9. **三語 README 同步（`b866187d6`）**：`README.md`、`README.en.md`、`README.ja.md` 首屏加入 `vacant do claude` 範例，首屏後補上 `vacant do` 專節（常用參數、兩組時限、結束碼表 `0`/`40`/`43`/`130`、看輸出與收據位置、`N/M` 與 `+`/`~`/`-`、以及強雲端 agent 與弱本機模型的誠實邊界），並將 `vacant selftest` 範例輸出由過時的 `4/6` 更新為實測 `1/6`。

### 政策差分（`rc5-final` vs `rc6`）

執行 `tests/adversarial_rc5_repro/policy_diff_rc5_rc6.py`（比對 `~/dev/ops/rc5final_venv/bin/vacant` 與 `redo/rc6`，完整輸出見 [`tests/adversarial_rc5_repro/POLICY_DIFF_RC6_RESULT.md`](../tests/adversarial_rc5_repro/POLICY_DIFF_RC6_RESULT.md)）：

- **原有 13 個情境**：**13/13 完全相同**（結束碼、`accepted`、`delivered_attempt`、每次嘗試 `(accept, passed, run)`、agent 呼叫次數、專案樹逐檔 sha256 全部一致）。
- **新增情境 14（`py_baseline_already_pass`）**：**1/1 政策與寫回結果完全相同**，僅摘要標題改為先講測試原本已全過。
- **新增情境 15（`ctrl_c_interrupt`，前景行程群組 `SIGINT`）**：**1/1 預期不同**——rc5-final 拋出 traceback 且無收據；rc6 以 `130` 結束、無 traceback、印出中斷與工作目錄訊息、專案逐位元組不變、寫出標為 `interrupted` 的簽章收據。

### 回歸測試摘要

- `PYTHONPATH=. /home/user1/dev/Vacant/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_restart*.py`：**247 passed, 1 skipped, 0 failed**（共 248）。
- 完整 `PYTHONPATH=. /home/user1/dev/Vacant/.venv/bin/python -m pytest -q -p no:cacheprovider tests/`（單行程、未用 `-n auto`）：**5789 passed, 69 skipped, 5 failed, 0 errors**（共 5863）。5 個失敗皆為與 rc6 無關的既有／本機環境失敗（未修動）：
  - `tests/test_reqloop_freeze_check.py::test_freeze_check_verdict_ok`、`test_freeze_check_covers_all_mandated_checks`（2 項）：本機 `auto/worker`／`NOW.md`／`auto/qwen27b` 凍結狀態既有不符。
  - `tests/test_retention.py::test_auto_gc_dry_run_missing_dir_safe`、`test_retention_main_auto_dry_run_human_output_safe`、`test_retention_main_gc_dry_run_human_output_safe`（3 項）：測試未隔離 `VACANT_WORK`，掃到本機 `~/.vacant-work/` 中既有（2026-11-21 22:34 留下）的 4 個舊目錄共 490 B／8 檔；以空 `VACANT_WORK` 單獨執行該 3 項全過。

### 審查後的補充（Claude，2026-11-22）

- **寫回途中的 Ctrl-C（`729ae83fe`）**：agy 的第 1 項把整段執行都包在「中斷 ⇒ 專案沒有被改動」裡；寫回途中按 Ctrl-C 會讓專案寫到一半，訊息卻說沒改動、收據記成沒交件。改成寫回開始到 `result.json` 寫完是臨界區：期間的 `SIGINT`／`SIGTERM`（第一次、第二次或更多）延後到寫回完成，照常交件（原本的結束碼），訊息最後說明收到過中斷。回歸：`test_sigint_during_write_back_is_deferred_and_project_not_half_written`（關掉延後時會失敗）、`test_second_sigint_and_sigterm_during_write_back_still_wait`。SIGKILL 擋不住，見 KNOWN_LIMITS 第 21 條。
- **沒過時的原因行（`47e442797`）**：略過只有 `^`／`~` 的 traceback 位置標記行。
- **測試隔離（`0fb0a9e12`，只改測試）**：`tests/conftest.py` 讓每個測試的 `HOME`、`VACANT_HOME`、`VACANT_WORK` 都指到自己的暫存目錄（獨立的 MonkeyPatch，測試裡的 `monkeypatch.undo()` 撤不掉）。上面那 3 個 retention 失敗就是沒隔離造成的。驗收：全套跑兩次（真家目錄／空家目錄），失敗集合相同，只剩 2 個依賴活 repo 狀態的 freeze-check；真家目錄那次前後 `~/.vacant`、`~/.vacant-work`、`~/.vacant-run`、`~/.vacant-mcp` 清單 0 差異。
- **cargo／go 實測**（`~/dev/ops/cg_test`）：README 三語標成實驗性支援，五個會算錯的情況寫進 KNOWN_LIMITS 第 15–19 條；保護集合不動，修正排到 0.9.3（`docs/TODO_0.9.3.md`）。
- 收據的變化：中斷的 run 多一筆 `interrupted` 收據；每次嘗試多記 `first_problem`；寫回途中收到訊號時 `result.json` 多 `interrupt_deferred`（不進收據）。既有欄位意義不變。
