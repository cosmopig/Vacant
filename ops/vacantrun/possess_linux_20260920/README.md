# `vacant install` 的 Linux 路徑逐格落盤（2026-09-20，vacant-dev）

裁決檔：[`decisions/DECISION_20260919_DEFAULT_ON_INSTALL.md`](../../../decisions/DECISION_20260919_DEFAULT_ON_INSTALL.md) §六.4／§七-5

補的是那一檔 §七-5 原本寫著的「**不能說 Linux 那邊也成立**——`systemd --user` ＋
`enable-linger` 那條路一次都沒跑過」。

- 機器：vacant-dev（Ubuntu 24.04.4、systemd 255.4-1ubuntu8.17、Python 3.12.3）
- 上游：**1004** `http://100.86.226.21:1234`（非 thinking），`gemma-4-12b-it-qat`
- 版本：**codex-cli 0.147.0**、**Claude Code 2.1.259**
  ⚠ 跟 macOS 那一輪（codex 0.153.2／Claude Code 2.1.278）**不是同一組版本號，不可混寫**
- 套件放在 `/opt/vacant-possess-20260920`（`git archive a8fb56ff`），收工已刪

⚠ **這裡只有摘要、索引與 stdout／stderr，沒有原始 bytes。** `*.req.bin`／`*.resp.bin`
與備份檔留在 vacant-dev，收工時連同 `~/.vacant`／`~/.vacant-run` 一起刪了，
要原始 bytes 要重跑。`resident_journal_index.jsonl` 是常駐 proxy 的**索引**，body 不進 repo。
本目錄掃過 `authorization`／`x-api-key`／`Bearer`／`sk-ant`：**零命中**。

## 檔案

- `baseline/` — 動任何東西之前的 sha256 與「這幾個檔應該不存在」清單
- `detect_nopathprobe.json`／`detect_shellprobe.json` — 偵測。**兩份結果相同**：
  `~/.local/bin` 不在非互動 PATH 上，`claude`／`codex` 仍然被 `bin_hints` 掃到
  （`binary_via: "hint"`）⇒「偵測不能只靠 PATH」在 Linux 上也成立
- `dryrun_no_upstream.json` — 不給 `--upstream` 時**兩條 wire 都落到 `SINK_UPSTREAM`**
- `install_stdout.json`／`install2.json` — 兩次 install 的完整 state
- `uninstall_report.json`／`uninstall_report_state.json` — 逐檔還原＋自驗 sha256
- `channel/` — 通道層三次呼叫的 stdout／stderr（`codex_try1` ＝ 沒有
  `OPENAI_API_KEY` 的那一次，**journal +0**）
- `gate/` — 閘門層四格的 `possess.json`／`run_*.json`／stdout／stderr
- `resident_journal_index.jsonl`、`proxyd_heartbeat.json` — 常駐 proxy 的 13 通

## 四格對照（Linux，codex 0.147.0）

| task_id 尾碼 | 格 | shim exit | stop_reason | suite_source | rs |
|---|---|---|---|---|---|
| `a28b29` | refuse | **20** | `visible_fail` | `dir:tests_visible` | 6 |
| `54e187` | deliver | **0** | `visible_pass` | `dir:tests_visible` | 5 |
| `8f52d9` | nosuite | **21** | `ungated`（`accepted=null`） | `none` | 5 |
| `a6dee1` | rs0 負控制（`/bin/echo`） | **23** | `visible_fail` | `dir:tests_visible` | **0** |

`a28b29` 是**真的拒交**（agent 只寫了 `add`，`check_mul` 丟
`AttributeError: module 'solution' has no attribute 'mul'`），不是 macOS 那一輪
`d1e80b` 的 `driver_error` 假拒交。

`a6dee1` 逐字重現 macOS 量到的那個病理：`refused=true`、`stop_reason=visible_fail`、
`agent_rc=0`、`visible_total=2` —— **除了 `requests_seen`，每個欄位都跟一個合法的
拒交格一模一樣**，所以 23 蓋過 20 是必要的。

## 收工狀態

五個使用者設定檔 sha256 **逐位元回到基線**、`~/.config/systemd`（install 建的）
已刪、8787 已釋放、`loginctl disable-linger user1` 已手動補回 `Linger=no`
（⚠ **`uninstall` 不做這一步**，見裁決檔 §六.4-F）、`/tmp/vacant-possess-*` 共
**400 MB** 已刪（⚠ **`gateshim` 也不做這一步**，同節 G）、孤兒行程 0、
`vacant-exhibit.service` 全程 `active`、人類的 17 天 session 全程存活。
