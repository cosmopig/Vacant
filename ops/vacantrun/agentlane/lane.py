"""agentlane —— 長時間跑 `vacant on <agent>`，量**每一格**中介成不成立。

回答的問題只有一個：**使用者透過 `vacant on` 開 agent 做事，
每一通模型呼叫是不是都經過 Vacant？**

## 判準（不接受「我設了設定檔」）

一格算通過要同時滿足：

1. `requests_seen >= 1` —— 真的有通過中介的呼叫
2. `wire_*/index.jsonl` 行數 == `requests_seen` —— 兩個獨立來源對得上
3. `agent_rc` 有值 —— agent 真的跑過（不是 spawn 就死）

⚠ **`accepted` 不是判準。** 模型寫不寫得對是另一件事，這一批量的是通道。
  混在一起會讓「模型今天比較笨」看起來像「中介壞了」。

## 三態

`None` ＝沒量到，不是 0，也不是 False。一格炸掉就記 `error` 與原因，
**不要補一個 0 上去**——那會讓失敗的格子在統計裡看起來像「跑了但都沒呼叫」。

## 負控制（每一輪都跑，不是只跑一次）

每個 agent 每一輪額外跑一格**假上游**（指到一個關著的埠）。要求：

  · `requests_seen >= 1`（呼叫有到中介）
  · **每一通的 status 都不是 2xx**（中介打不到上游）
  · agent 的輸出裡**沒有** `api.openai.com` / `anthropic.com`
    ⇒ 沒有偷偷落回真的 API

負控制沒過的那一輪，**正控制那幾格也不算數**——因為那表示量具當下分不出
「被中介」與「沒被中介」。

## 跑法

    python3 ops/vacantrun/agentlane/lane.py --agents opencode,codex \\
        --rounds 20 --out ops/vacantrun/agentlane/evidence
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[3]
PY = str(ROOT / ".venv" / "bin" / "python")
if not pathlib.Path(PY).exists():           # pip 裝的環境沒有 .venv
    PY = sys.executable

#: 題目。刻意小而確定——這一批量的是**通道**不是模型能力，
#: 題目太難會讓 agent 亂繞、把量測時間拖成隨機變數。
TASKS: tuple[tuple[str, str, str], ...] = (
    ("sum_even", "寫一個檔案 solution.py，裡面一個函式 `sum_even(xs)` 回傳串列裡所有偶數的和。",
     "from solution import sum_even\n"
     "def test_basic():\n"
     "    assert sum_even([1,2,3,4]) == 6\n"
     "    assert sum_even([]) == 0\n"
     "    assert sum_even([1,3]) == 0\n"),
    ("rev_words", "寫一個檔案 solution.py，裡面一個函式 `rev_words(s)` 把句子裡的字詞順序反過來（用空白分隔）。",
     "from solution import rev_words\n"
     "def test_basic():\n"
     "    assert rev_words('a b c') == 'c b a'\n"
     "    assert rev_words('hi') == 'hi'\n"),
    ("count_vowels", "寫一個檔案 solution.py，裡面一個函式 `count_vowels(s)` 回傳字串裡英文母音的數量（不分大小寫）。",
     "from solution import count_vowels\n"
     "def test_basic():\n"
     "    assert count_vowels('Hello') == 2\n"
     "    assert count_vowels('xyz') == 0\n"),
)

DEAD_UPSTREAM = "http://127.0.0.1:59998/v1"
EXTERNAL = ("api.openai.com", "anthropic.com", "api.anthropic.com")


def _one(agent: str, task: tuple[str, str, str], upstream: str,
         model: str, timeout: float) -> dict:
    """跑一格。**任何失敗都回一筆有 `error` 的紀錄，不要丟例外**——
    一格炸掉不該讓整條 lane 停下來（展場那條紀律的同一個理由）。"""
    tid, prompt, test_src = task
    ws = pathlib.Path(tempfile.mkdtemp(prefix=f"lane-{agent}-{tid}-"))
    rd = pathlib.Path(tempfile.mkdtemp(prefix=f"lanerun-{agent}-{tid}-"))
    suite = ws.parent / (ws.name + "-suite")
    suite.mkdir(parents=True, exist_ok=True)
    (suite / "test_visible.py").write_text(test_src, "utf-8")
    env = {**os.environ,
           "VACANT_RUN_UPSTREAM_OPENAI": upstream,
           "VACANT_RUN_UPSTREAM_ANTHROPIC": upstream.rsplit("/v1", 1)[0],
           "VACANT_AGENT_MODEL": model,
           "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    cmd = [PY, "-m", "vacant_network.cli", "run",
           "--workspace", str(ws), "--run-dir", str(rd),
           "--suite", str(suite), "--json", "--timeout", str(int(timeout)),
           "--", PY, "-m", "vacant_network.vrun.agentwrap", agent, prompt]
    t0 = time.time()
    rec: dict = {"agent": agent, "task": tid, "upstream": upstream,
                 "at": time.time(), "wall_s": None,
                 # 三態：跑之前全部是「沒量到」
                 "requests_seen": None, "wire_lines": None, "agent_rc": None,
                 "accepted": None, "statuses": None, "external_hits": None,
                 "error": None}
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout + 120, env=env)
        rec["wall_s"] = round(time.time() - t0, 1)
        try:
            d = json.loads(p.stdout)
        except Exception:                                   # noqa: BLE001
            rec["error"] = f"launcher 沒回 JSON（rc={p.returncode}）：{p.stdout[:160]!r}"
            return rec
        rec["requests_seen"] = d.get("requests_seen")
        rec["agent_rc"] = d.get("agent_rc")
        rec["accepted"] = d.get("accepted")
        idx = list(rd.rglob("index.jsonl"))
        if idx:
            lines = [json.loads(x) for x in idx[0].read_text("utf-8").splitlines() if x.strip()]
            rec["wire_lines"] = len(lines)
            rec["statuses"] = [x.get("status") for x in lines]
        # agent 自己講的話裡有沒有外部網域 ⇒ 有就是偷偷連出去了
        blob = (p.stdout or "") + (p.stderr or "")
        rec["external_hits"] = sum(blob.count(e) for e in EXTERNAL)
    except subprocess.TimeoutExpired:
        rec["wall_s"] = round(time.time() - t0, 1)
        rec["error"] = "timeout"
    except Exception as e:                                  # noqa: BLE001
        rec["wall_s"] = round(time.time() - t0, 1)
        rec["error"] = f"{type(e).__name__}: {e}"
    finally:
        for d_ in (ws, rd, suite):
            shutil.rmtree(d_, ignore_errors=True)
    return rec


def judge(rec: dict) -> str:
    """一格的判決。**「沒量到」自成一類**，不併進 fail。"""
    if rec.get("error"):
        return "error"
    rs, wl = rec.get("requests_seen"), rec.get("wire_lines")
    if rs is None or wl is None:
        return "unmeasured"
    if rec["upstream"] == DEAD_UPSTREAM:
        # 負控制：要有呼叫、要全部打不到、而且沒有偷偷連出去
        ok = (rs >= 1 and wl == rs
              and all(not (isinstance(s, int) and 200 <= s < 300)
                      for s in (rec.get("statuses") or []))
              and (rec.get("external_hits") or 0) == 0)
        return "negctl_ok" if ok else "negctl_FAIL"
    return "ok" if (rs >= 1 and wl == rs and rec.get("agent_rc") is not None) else "FAIL"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agents", default="opencode",
                    help="逗號分隔。只列你機器上真的有的")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--upstream", default="http://100.119.113.56:1234/v1")
    ap.add_argument("--model", default="gemma-4-12b-it-qat")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--out", default=str(pathlib.Path(__file__).parent / "evidence"))
    a = ap.parse_args(argv)

    agents = [x.strip() for x in a.agents.split(",") if x.strip()]
    missing = [x for x in agents if shutil.which(x) is None]
    if missing:
        # 🔴 fail-closed：少一個 agent 就講出來，不要安靜地少跑一條臂。
        sys.stderr.write(f"🔴 這些不在 PATH 上，拒跑：{', '.join(missing)}\n")
        return 2

    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    jl = out / f"lane_{int(time.time())}.jsonl"
    print(f"[lane] agents={agents} rounds={a.rounds} → {jl}", flush=True)

    for rnd in range(1, a.rounds + 1):
        for agent in agents:
            for task in TASKS:
                for up in (a.upstream, DEAD_UPSTREAM):
                    rec = _one(agent, task, up, a.model, a.timeout)
                    rec["round"] = rnd
                    rec["verdict"] = judge(rec)
                    with jl.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    arm = "NEG" if up == DEAD_UPSTREAM else "POS"
                    print(f"  r{rnd} {agent:9s} {task[0]:13s} {arm} "
                          f"{rec['verdict']:11s} rs={rec['requests_seen']} "
                          f"wire={rec['wire_lines']} {rec['wall_s']}s", flush=True)
    print(f"[lane] 完成 → {jl}", flush=True)
    return 0


if __name__ == "__main__":   # pragma: no cover
    raise SystemExit(main())
