# `vacant install` 逐格落盤（2026-09-19，macOS）

裁決檔：[`decisions/DECISION_20260919_DEFAULT_ON_INSTALL.md`](../../../decisions/DECISION_20260919_DEFAULT_ON_INSTALL.md)

⚠ **這裡只有摘要與索引，沒有原始 bytes。** `*.req.bin`／`*.resp.bin` 與備份檔
都留在 session 的 scratchpad（會被清掉），需要原始 bytes 要重跑。
`resident_journal_index.jsonl` 是常駐 proxy 的**索引**，body 不進 repo。

## 檔案

- `detect_macos_20260919.json` — 偵測結果。**注意 `pi`：`binary: null`、
  `config_dir` 有值、`present: true`** ——那就是「只看 PATH 會判沒裝」的那一格。
- `possess_codex_*.possess.json` — shim 落的那一份（`suite_source`、`gate`、
  `shim_exit`、原始 `argv`）
- `possess_codex_*.run.json` — `run_RUN-ON.json` 的關鍵欄位
- `resident_journal_index.jsonl` — 常駐 proxy 的 6 通（codex／opencode／
  Claude Code 三家，命令列上零個 vacant）

## 六格對照

| task_id 尾碼 | 格 | shim exit | stop_reason | suite_source | rs |
|---|---|---|---|---|---|
| `4cdced` | refuse（舊套件格式） | 20 | `visible_fail` | `dir:tests_visible` | 3 |
| `d1e80b` | deliver（舊套件格式，**driver_error**） | 20 | `visible_fail` | `dir:tests_visible` | 3 |
| `7011cd` | nosuite | **21** | `ungated` | `none` | 4 |
| `040380` | refuse | 20 | `visible_fail` | `dir:tests_visible` | 3 |
| `2a405b` | deliver | **0** | `visible_pass` | `dir:tests_visible` | 3 |
| `afc98c` | rs0 負控制（`/bin/echo`） | **23** | — | `dir:tests_visible` | **0** |

⚠ `d1e80b` 那一格**不是閘門的功勞**：agent 其實寫對了 `solution.py`，
是**我們的測試檔寫成 pytest 風格**（`test_*()`）而 `acceptance.py` 只吃
`check_*()`／`main()` ⇒ `driver_error` ⇒ 判 `visible_fail`。
**一份壞掉的驗收套件在收據上長得跟一個真的拒交一模一樣**——留在這裡
因為那是這一輪學到的東西，不是要刪掉的髒資料。
