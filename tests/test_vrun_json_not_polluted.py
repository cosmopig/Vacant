"""`--json` 的 stdout 不准被 agent 汙染。

這支在架構裡承重什麼
────────────────────
`--json` 的唯一用途是**機器讀**。而 launcher 原本讓 agent 繼承 stdout，
於是 agent 自己印的話會出現在 summary JSON **前面**：

```
$ vacant run … --json -- opencode run "…"
I have created solution.py with the requested add and multiply functions.
{
  "task_id": "…",
```

⇒ 呼叫端 `json.load(stdout)` 直接 `JSONDecodeError`。

**一個會被任意子行程汙染的機器輸出是壞的。** 而且這一條正好是
`.claude/commands/goal.md` §三-2 點名的那一類——**功能在，但使用者構不到**：
照文件用 `--json` 的人第一步就撞牆，而我們的文件到處都寫著 `--json`。

2026-09-19 由 OpenCode 升 L-real 時踩到並回報（它得改讀 `run_RUN-ON.json` 才繞過）。

修法：`--json` 下把 agent 的 stdout 導進 `<run_dir>/agent_stdout.log`。
**一個位元組都沒丟**，而且 stderr 照樣繼承（進度與錯誤看得見）。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

NOISE = "I have created solution.py with the requested functions."

SUITE = """def check_add():
    from solution import add
    assert add(2, 3) == 5
"""


@pytest.fixture()
def bed(tmp_path):
    ws = tmp_path / "ws"
    suite = tmp_path / "suite"
    ws.mkdir()
    suite.mkdir()
    (suite / "test_visible.py").write_text(SUITE, encoding="utf-8")
    (ws / "solution.py").write_text("def add(a, b):\n    return a + b\n",
                                    encoding="utf-8")
    return ws, suite, tmp_path / "rd"


def _run(ws, suite, rd, *, agent_cmd: str, json_flag: bool):
    argv = [sys.executable, "-m", "vacant.vrun.launcher",
            "--workspace", str(ws), "--suite", str(suite),
            "--run-dir", str(rd), "--sandbox", "none"]
    if json_flag:
        argv.append("--json")
    argv += ["--", "bash", "-lc", agent_cmd]
    return subprocess.run(argv, capture_output=True, text=True, timeout=300)


def test_json_stdout_is_pure_json_even_when_the_agent_talks(bed):
    """**這一條就是那個 bug 的形狀。**"""
    ws, suite, rd = bed
    r = _run(ws, suite, rd, agent_cmd=f'echo "{NOISE}"', json_flag=True)
    assert r.returncode == 0, r.stderr[-400:]
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError as e:  # pragma: no cover - 失敗時給人看
        pytest.fail(f"stdout 不是純 JSON（{e}）：\n{r.stdout[:300]}")
    assert d["accepted"] is True
    # ⚠ 不能斷言 `NOISE not in stdout`——summary 本來就**記錄了 agent 的 argv**，
    #   而 argv 裡有那句 echo。那是應該的。要斷言的是**位置**：
    #   stdout 的第一個非空白字元必須是 `{`，也就是前面沒有任何東西。
    assert r.stdout.lstrip().startswith("{"), (
        f"JSON 前面有東西：{r.stdout[:120]!r}")
    assert r.stdout.rstrip().endswith("}"), "JSON 後面有東西"


def test_the_agent_output_is_kept_not_thrown_away(bed):
    """⚠ 導走不是丟掉。丟掉就變成另一種「沒量到」。"""
    ws, suite, rd = bed
    _run(ws, suite, rd, agent_cmd=f'echo "{NOISE}"', json_flag=True)
    log = rd / "agent_stdout.log"
    assert log.exists(), "agent 的 stdout 不見了"
    assert NOISE in log.read_text(encoding="utf-8")


def test_without_json_the_agent_still_writes_to_our_stdout(bed):
    """沒給 `--json` 時行為**逐字不變**——那是既有使用者看進度的方式。"""
    ws, suite, rd = bed
    r = _run(ws, suite, rd, agent_cmd=f'echo "{NOISE}"', json_flag=False)
    assert r.returncode == 0, r.stderr[-400:]
    assert NOISE in r.stdout, "不給 --json 時不該導走 agent 的輸出"


def test_multiline_and_json_looking_noise_still_parses(bed):
    """agent 印出**長得像 JSON** 的東西也不能騙過去。"""
    ws, suite, rd = bed
    noise = 'printf \'{"accepted": false}\\nhello\\n\''
    r = _run(ws, suite, rd, agent_cmd=noise, json_flag=True)
    d = json.loads(r.stdout)
    assert d["accepted"] is True, (
        "解到的是 agent 印的假 JSON，不是 summary——比解不動更糟")


def test_summary_on_disk_matches_stdout(bed):
    """落盤那份與 stdout 那份要一致，否則兩個真相。"""
    ws, suite, rd = bed
    r = _run(ws, suite, rd, agent_cmd=f'echo "{NOISE}"', json_flag=True)
    on_disk = json.loads(
        (rd / "run_RUN-ON.json").read_text(encoding="utf-8"))
    assert json.loads(r.stdout)["verdict_sha256"] == on_disk["verdict_sha256"]
