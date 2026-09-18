"""`vacant run --retry resample|revise` 的擋門測試（V1 ＝ 閘門的重試迴圈）。

這一批測的是**承重件**不是便利函式。每一條對應規格裡的一句話：

  · `test_revise_retries_and_succeeds_after_reading_the_feedback_file`
      「revise 真的會重試而且真的會成功」。假 agent 第一次寫錯，
      **讀到 `VACANT_FEEDBACK.md` 裡的失敗原文之後**第二次寫對。
      判準不是「檔案存在」而是「那個檔提到了 `check_add`」——
      只驗存在的話，一支根本沒讀內容的 agent 也會讓測試變綠。
  · `test_resample_really_resets_the_workspace`
      「resample 真的重置工作區」。假 agent 每次都留下 `leftover.txt`
      **和 `.git/note.txt`**，下一次嘗試開始時兩個都必須不存在。
      ⚠ `.git/` **不進樹雜湊**（`wshash.EXCLUDED_DIRS`）⇒ 光看雜湊看不出
      它有沒有被清掉。所以假 agent 把「我開始的時候看到什麼」寫到
      **工作區外**的一份 trace，那份東西重置殺不掉，是唯一的證據。
  · `test_attempts_exhausted_is_a_refusal_with_its_own_name`
      用完額度仍沒過 ⇒ 拒交、退出碼非 0、收據記 `attempts_exhausted`。
  · `test_receipts_reconcile_for_every_ending`
      **R530 踩過的坑**：只在 happy path 簽 attempt ⇒ 0 筆 attempt、1 筆
      verdict ⇒ 鏈沒壞，壞的是「鏈說得出這一格發生過什麼」。
      這一條對**每一種收尾**都跑既有的那把尺
      （`ops/gain/replay/verify_run_receipts.py`，不准另寫第二把），
      並逐格斷言 `attempt 數 ≥ verdict 數`。
  · `test_feedback_file_never_contains_hidden_testdata`
      V/GT 紅線的可執行版本，形狀照抄 `tests/test_gain_vgt_canary.py`：
      canary 種在 hidden 側，掃 feedback 檔要零命中。**配一條負向控制**
      （把 hidden 當成可見套件餵進去，同一支掃描必須翻紅）——
      沒有負控的「掃描零命中」跟把掃描關掉在輸出上同形。
  · `test_ks1_*`
      鐵律 1 的可執行防呆接上了，而且**有負向控制**。
  · `test_retry_none_is_still_exactly_v0`
      預設不改既有使用者的行為。

V2（`--feedback-into prompt|both`，回饋接到**下一次 spawn 的 argv 尾端**）另外五條：

  · `test_v2_first_attempt_argv_is_byte_identical_to_no_vacant`
      第 1 次的 argv 與「沒有 Vacant」時**逐位元相同**（placeholder 換成空字串）。
      兩端都驗：收據落的 `argv_sha256`，與 agent 行程**真的收到**的那條 argv。
  · `test_v2_second_attempt_argv_is_the_first_plus_the_feedback`
      第 2 次是第 1 次的**逐位元前綴 ＋ `"\\n\\n" ＋ 回饋**。尾端 append 才保得住
      provider 的前綴快取，所以「是前綴」這件事是規格不是巧合。
  · `test_v2_an_agent_that_only_reads_argv_passes_in_prompt_mode_and_fails_in_file_mode`
      **承重的那一條**：假 agent 只看 argv、一個字都不讀 `VACANT_FEEDBACK.md`。
      `prompt` 模式第 2 次就過；`file` 模式燒完額度都沒過（**負向控制**）。
      ⚠ 而且證明它不是因為檔沒寫出來才失敗——檔在、內容也對、agent 也看得到它存在。
  · `test_v2_missing_placeholder_with_prompt_mode_is_a_hard_stop`
      缺 placeholder ＋ `prompt` ⇒ `SystemExit`，**不准安靜退回檔案模式**
      （連 run 目錄都不准開始寫）。反向（有 placeholder 但 mode 是 `file`）、
      沒有下一次 spawn（`--retry none`）、打錯 mode 一律同辦。
  · `test_v2_feedback_in_prompt_never_contains_hidden_testdata` ＋
    `test_v2_vgt_canary_scan_has_teeth_in_argv`
      V/GT 紅線換到 argv 這條管道上再驗一次，**配同一形狀的負向控制**。

兩件小事各一條：`test_suite_under_the_workspace_is_refused`（agent 改得到的驗收
不是驗收）、`test_grandchildren_are_killed_before_the_freeze`（`wait()` 只等直接
子行程 ⇒ 孫行程可以在凍結之後繼續寫）。

⚠ 本檔零模型呼叫、零機時：上游是一個本機假 server，agent 是一支 40 行的
  Python，驗收沙箱走 `none`。
"""
from __future__ import annotations

import json
import pathlib
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain.replay import verify_run_receipts as vrr           # noqa: E402
from ops.vacantrun import launcher                               # noqa: E402
from ops.vacantrun import retry as retrypolicy                   # noqa: E402
from vacant.memory import KS1Violation                           # noqa: E402

#: 唯一標記，兩個形狀各擋一種洩漏：字串（註解／訊息）與數值（測資字面值）。
#: 逐字沿用 `tests/test_gain_vgt_canary.py` 的用意。
GT_CANARY = "CANARY_GT_9f3c7e"
NUM_CANARY = "424242424242"

#: 假 agent。三個 mode：
#:   `always_bad`     ——永遠寫錯（拿來量「用完額度」與「重置」）。
#:   `fix_when_told`  ——**只有在回饋檔真的提到 `check_add` 時**才寫對。
#:   `always_good`    ——第一次就寫對。
#: 它每一次都：(1) 把「我開始時看到什麼」寫進工作區**外**的 trace；
#: (2) 打一通模型通道（per-attempt `requests_seen` 才量得到）；
#: (3) 留下 `leftover.txt` 與 `.git/note.txt` 當重置的靶。
_RETRY_AGENT = r'''
import json, os, pathlib, sys, urllib.request

MODE, TRACE = sys.argv[1], pathlib.Path(sys.argv[2])
ws = pathlib.Path.cwd()
fb = ws / "VACANT_FEEDBACK.md"
fb_text = fb.read_text(encoding="utf-8") if fb.exists() else ""
with TRACE.open("a", encoding="utf-8") as f:
    f.write(json.dumps({
        "feedback_exists": fb.exists(),
        "feedback_mentions_check_add": "check_add" in fb_text,
        "leftover_exists": (ws / "leftover.txt").exists(),
        "git_note_exists": (ws / ".git" / "note.txt").exists(),
        "entries": sorted(p.name for p in ws.iterdir()),
    }, ensure_ascii=False) + "\n")

base = os.environ["OPENAI_BASE_URL"]
req = urllib.request.Request(base.rstrip("/") + "/chat/completions",
                             data=b'{"model":"m","messages":[]}', method="POST")
req.add_header("Content-Type", "application/json")
with urllib.request.urlopen(req, timeout=30) as r:
    r.read()

(ws / "leftover.txt").write_text("left by a previous attempt\n", encoding="utf-8")
(ws / ".git").mkdir(exist_ok=True)
(ws / ".git" / "note.txt").write_text("a previous attempt committed\n",
                                      encoding="utf-8")

GOOD = "def add(a, b):\n    return a + b\n"
BAD = "def add(a, b):\n    return a - b\n"
if MODE == "always_bad":
    code = BAD
elif MODE == "fix_when_told":
    code = GOOD if "check_add" in fb_text else BAD
else:
    code = GOOD
(ws / "solution.py").write_text(code, encoding="utf-8")
'''

_VISIBLE_TEST = '''
def check_add():
    from solution import add
    assert add(2, 3) == 5
'''

#: hidden 側。canary 種在這裡——**一個註解、一條真的隱藏測資、一句訊息**，
#: 三個位置都要掃得到（訊息與 `where` 都會進 `render_failures` 的輸出）。
_HIDDEN_TEST = f'''
def check_hidden():
    from solution import add
    # {GT_CANARY}
    assert add(1, 1) == {NUM_CANARY}, "hint {GT_CANARY}"
'''

#: KS-1 的負向控制素材：**責任修辭從客戶的測試訊息帶進來**，不是從模板。
_KS1_DIRTY_TEST = '''
def check_add():
    from solution import add
    assert add(2, 3) == 5, "you will be punished for this"
'''


class _Upstream(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        return

    def do_POST(self):                                   # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        payload = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture()
def upstream(monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1},
                     daemon=True).start()
    monkeypatch.setenv("OPENAI_BASE_URL",
                       f"http://127.0.0.1:{srv.server_address[1]}/v1")
    yield
    srv.shutdown()
    srv.server_close()


# ── 場地 ─────────────────────────────────────────────────────────────────
def _ws(tmp: pathlib.Path, name: str = "ws") -> pathlib.Path:
    ws = tmp / name
    ws.mkdir(parents=True)
    (ws / "README.md").write_text("write add(a, b)\n", encoding="utf-8")
    return ws


def _suite(tmp: pathlib.Path, name: str = "visible",
           src: str = _VISIBLE_TEST) -> pathlib.Path:
    d = tmp / name
    d.mkdir(parents=True, exist_ok=True)
    (d / f"test_{name}.py").write_text(src, encoding="utf-8")
    return d


def _agent(tmp: pathlib.Path, mode: str, trace: pathlib.Path) -> list[str]:
    p = tmp / "retry_agent.py"
    p.write_text(_RETRY_AGENT, encoding="utf-8")
    return [sys.executable, str(p), mode, str(trace)]


def _go(tmp: pathlib.Path, *, mode: str, retry_arm: str = "none",
        max_attempts: int | None = None, suite: pathlib.Path | None = None,
        ws_name: str = "ws", run_name: str = "run",
        allow_no_suite: bool = False, vacant_on: bool = True) -> dict:
    """跑一次，回 `(summary, 場地)`。trace 落在**工作區外**（重置殺不掉）。"""
    ws = _ws(tmp, ws_name)
    trace = tmp / f"trace_{ws_name}.jsonl"
    run_dir = tmp / run_name
    summary = launcher.run(
        _agent(tmp, mode, trace), workspace=ws, run_dir=run_dir,
        suite_dir=(_suite(tmp) if suite is None else suite),
        vacant_on=vacant_on, task_id=f"t_{ws_name}", sandbox_name="none",
        allow_no_suite=allow_no_suite, retry_arm=retry_arm,
        max_attempts=max_attempts)
    return {"summary": summary, "ws": ws, "run_dir": run_dir,
            "trace": [json.loads(x) for x in
                      trace.read_text(encoding="utf-8").splitlines() if x]}


def _chain_types(run_dir: pathlib.Path, arm: str = launcher.ARM_ON) -> dict:
    counts: dict[str, int] = {}
    for line in (run_dir / f"receipts_{arm}.ndjson").read_text(
            encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            counts[e["type"]] = counts.get(e["type"], 0) + 1
    return counts


def _assert_ruler_is_happy(run_dir: pathlib.Path) -> list[dict]:
    """用**既有的那把尺**驗，並逐格斷言 `attempt 數 ≥ verdict 數`。"""
    out = vrr.verify_run(run_dir)
    assert out, f"{run_dir} 沒有任何鏈可驗——UNVERIFIABLE ≠ CLEAN"
    for rec in out:
        assert rec["verdict"] == "OK", json.dumps(rec, ensure_ascii=False)[:800]
        assert rec["attempt_n"] >= rec["verdict_n"] >= 1, rec
    return out


# ══ 1) revise 真的會重試而且真的會成功 ═══════════════════════════════════
def test_revise_retries_and_succeeds_after_reading_the_feedback_file(
        tmp_path, upstream):
    r = _go(tmp_path, mode="fix_when_told", retry_arm="revise", max_attempts=3)
    s = r["summary"]

    assert s["attempts_used"] == 2, s["attempts"]
    assert s["accepted"] is True and s["stop_reason"] == "visible_pass"
    assert launcher.exit_code(s) == 0

    # 第一次沒有回饋檔；第二次有，**而且它提到了失敗的那條 case**。
    assert r["trace"][0]["feedback_exists"] is False
    assert r["trace"][1]["feedback_exists"] is True
    assert r["trace"][1]["feedback_mentions_check_add"] is True

    # 回饋是**第一次之後**寫的，最後一次不再寫（沒有下一次了）。
    assert s["attempts"][0]["feedback"]["sha256"]
    assert s["attempts"][1]["feedback"] is None
    assert s["attempts"][0]["visible_passed"] == 0
    assert s["attempts"][1]["visible_passed"] == s["attempts"][1]["visible_total"]

    # revise 保留工作區 ⇒ 上一次留下的東西還在（這正是與 resample 的差）。
    assert r["trace"][1]["leftover_exists"] is True

    # 收據：2 筆 attempt ＋ 1 筆 verdict。
    assert _chain_types(r["run_dir"]) == {"ws_attempt": 2, "ws_verdict": 1}
    _assert_ruler_is_happy(r["run_dir"])


# ══ 2) resample 真的重置工作區 ════════════════════════════════════════════
def test_resample_really_resets_the_workspace(tmp_path, upstream):
    r = _go(tmp_path, mode="always_bad", retry_arm="resample", max_attempts=3)
    s = r["summary"]
    assert s["attempts_used"] == 3

    # 每一次開始時，上一次留下的東西都必須不存在——**含 `.git/`**
    # （它不進樹雜湊，所以只有這份 trace 說得出它有沒有被清掉）。
    assert len(r["trace"]) == 3
    for i, seen in enumerate(r["trace"]):
        assert seen["leftover_exists"] is False, (i, seen)
        assert seen["git_note_exists"] is False, (i, seen)
        assert seen["feedback_exists"] is False, (i, seen)   # 不給失敗原文
        assert seen["entries"] == ["README.md"], (i, seen)

    # 工作區雜湊每一次都回到起點，而且重置那一步自己有落盤。
    start = s["ws_start_sha256"]
    assert [a["ws_start_sha256"] for a in s["attempts"]] == [start] * 3
    assert s["attempts"][0]["reset"] is None
    for a in s["attempts"][1:]:
        assert a["reset"] == {"kind": "resample", "ws_sha256": start,
                              "back_to_start": True}

    # resample 這一臂**從來不寫**回饋檔。
    assert not (r["ws"] / retrypolicy.FEEDBACK_FILENAME).exists()
    assert all(a["feedback"] is None for a in s["attempts"])
    _assert_ruler_is_happy(r["run_dir"])


def test_resample_agent_never_sees_the_previous_failure(tmp_path, upstream):
    """負向控制：同一支 agent 在 `revise` 底下看得到，在 `resample` 底下看不到。

    兩條臂的差別如果只寫在文件裡，它就不是差別。
    """
    rev = _go(tmp_path, mode="fix_when_told", retry_arm="revise",
              max_attempts=2, ws_name="rev", run_name="run_rev")
    res = _go(tmp_path, mode="fix_when_told", retry_arm="resample",
              max_attempts=2, ws_name="res", run_name="run_res")
    assert rev["trace"][1]["feedback_mentions_check_add"] is True
    assert res["trace"][1]["feedback_mentions_check_add"] is False
    # 同一支 agent、同樣的額度：revise 過、resample 沒過。
    assert rev["summary"]["accepted"] is True
    assert res["summary"]["accepted"] is False


# ══ 3) 用完額度仍沒過 ⇒ 拒交 ═════════════════════════════════════════════
@pytest.mark.parametrize("arm", ["resample", "revise"])
def test_attempts_exhausted_is_a_refusal_with_its_own_name(tmp_path, upstream,
                                                           arm):
    r = _go(tmp_path, mode="always_bad", retry_arm=arm, max_attempts=3,
            ws_name=f"ws_{arm}", run_name=f"run_{arm}")
    s = r["summary"]
    assert s["attempts_used"] == 3 == s["max_attempts"]
    assert s["stop_reason"] == "attempts_exhausted"
    assert s["accepted"] is False and s["refused"] is True
    assert launcher.exit_code(s) == launcher.EXIT_REFUSED != 0

    row = json.loads((r["run_dir"] / "rows.jsonl").read_text(
        encoding="utf-8").splitlines()[-1])
    assert row["stop_reason"] == "attempts_exhausted"
    assert row["attempts_used"] == 3 and row["retry"] == arm

    chain = json.loads((r["run_dir"] / f"receipts_{launcher.ARM_ON}.ndjson")
                       .read_text(encoding="utf-8").splitlines()[-1])
    assert chain["type"] == "ws_verdict"
    assert chain["payload"]["stop_reason"] == "attempts_exhausted"
    assert chain["payload"]["attempts_used"] == 3
    assert _chain_types(r["run_dir"]) == {"ws_attempt": 3, "ws_verdict": 1}
    _assert_ruler_is_happy(r["run_dir"])


def test_single_shot_failure_is_not_called_attempts_exhausted(tmp_path,
                                                              upstream):
    """`visible_fail` 與 `attempts_exhausted` **不可以同形**：後者多燒了 N−1 次。"""
    r = _go(tmp_path, mode="always_bad")
    assert r["summary"]["stop_reason"] == "visible_fail"
    assert r["summary"]["attempts_used"] == 1


# ══ 4) 收據對帳：每一種收尾都要過既有的那把尺 ════════════════════════════
def test_receipts_reconcile_for_every_ending(tmp_path, upstream):
    cases = [
        ("pass_first", dict(mode="always_good", retry_arm="revise",
                            max_attempts=3), {"ws_attempt": 1,
                                              "ws_verdict": 1}),
        ("pass_second", dict(mode="fix_when_told", retry_arm="revise",
                             max_attempts=3), {"ws_attempt": 2,
                                               "ws_verdict": 1}),
        ("exhausted", dict(mode="always_bad", retry_arm="revise",
                           max_attempts=2), {"ws_attempt": 2,
                                             "ws_verdict": 1}),
        ("resampled", dict(mode="always_bad", retry_arm="resample",
                           max_attempts=2), {"ws_attempt": 2,
                                             "ws_verdict": 1}),
        ("v0_default", dict(mode="always_bad"), {"ws_attempt": 1,
                                                 "ws_verdict": 1}),
    ]
    for name, kw, want in cases:
        r = _go(tmp_path, ws_name=f"ws_{name}", run_name=f"run_{name}", **kw)
        assert _chain_types(r["run_dir"]) == want, name
        _assert_ruler_is_happy(r["run_dir"])

    # 沒有套件的兩種收尾：**照樣有一筆 attempt**（`verdict_sha256=None`
    # ＝這一輪沒有跑驗收）。0 筆 attempt、1 筆 verdict 正是 R530 那個坑。
    for name, allow in (("nosuite", False), ("ungated", True)):
        r = _go(tmp_path, mode="always_bad", suite=tmp_path / "no_such_dir",
                allow_no_suite=allow, ws_name=f"ws_{name}",
                run_name=f"run_{name}")
        assert _chain_types(r["run_dir"]) == {"ws_attempt": 1, "ws_verdict": 1}
        _assert_ruler_is_happy(r["run_dir"])
        first = json.loads((r["run_dir"] / f"receipts_{launcher.ARM_ON}.ndjson")
                           .read_text(encoding="utf-8").splitlines()[0])
        assert first["type"] == "ws_attempt"
        assert first["payload"]["verdict_sha256"] is None


def test_actual_spend_is_recorded_per_attempt(tmp_path, upstream):
    """等預算的定義是「**上限相同、實際用量落盤**」，不是強制用滿（R530 裁決）。"""
    r = _go(tmp_path, mode="always_bad", retry_arm="revise", max_attempts=3)
    s = r["summary"]
    assert [a["requests_seen"] for a in s["attempts"]] == [1, 1, 1]
    assert [a["requests_seen_cumulative"] for a in s["attempts"]] == [1, 2, 3]
    assert s["requests_seen"] == 3
    for a in s["attempts"]:
        assert a["agent_wall_s"] >= 0 and a["agent_rc"] == 0
        assert len(a["ws_start_sha256"]) == 64 and len(a["ws_end_sha256"]) == 64


# ══ 5) V/GT：回饋檔不准帶隱藏測資 ════════════════════════════════════════
def _scan(texts: list[str]) -> list[str]:
    return [c for c in (GT_CANARY, NUM_CANARY)
            if any(c in (t or "") for t in texts)]


def test_feedback_file_never_contains_hidden_testdata(tmp_path, upstream):
    hidden = _suite(tmp_path, "hidden", _HIDDEN_TEST)
    assert GT_CANARY in (hidden / "test_hidden.py").read_text(encoding="utf-8")
    r = _go(tmp_path, mode="always_bad", retry_arm="revise", max_attempts=3,
            suite=_suite(tmp_path))          # ← 餵進去的是 visible，不是 hidden

    fb = r["ws"] / retrypolicy.FEEDBACK_FILENAME
    texts = [fb.read_text(encoding="utf-8")]
    texts += [a["feedback"]["text"] for a in r["summary"]["attempts"]
              if a.get("feedback")]

    # ⚠ **量具要先證明它接上了**：一個字都沒寫出來的情況下「掃描零命中」
    #   是真的，但它證明的是量具沒接上，不是沒有洩漏
    #   （`test_gain_vgt_canary.py` 的 `assert sent` 那一條）。
    assert len(texts) == 3 and all(texts)
    assert "check_add" in texts[0]

    assert _scan(texts) == []


def test_vgt_canary_scan_has_teeth(tmp_path, upstream):
    """負向控制：把 hidden **當成可見套件**餵進去，同一支掃描必須翻紅。

    沒有這一條，上面那個「零命中」跟把掃描關掉在輸出上同形。
    """
    r = _go(tmp_path, mode="always_bad", retry_arm="revise", max_attempts=2,
            suite=_suite(tmp_path, "hidden", _HIDDEN_TEST))
    fb = (r["ws"] / retrypolicy.FEEDBACK_FILENAME).read_text(encoding="utf-8")
    assert _scan([fb]) == [GT_CANARY, NUM_CANARY], fb


# ══ 6) KS-1（鐵律 1）══════════════════════════════════════════════════════
def test_feedback_template_is_ks1_clean():
    for t in (retrypolicy.FEEDBACK_HEADER, retrypolicy.FEEDBACK_BODY,
              retrypolicy.FEEDBACK_TEMPLATE):
        assert "responsible" not in t.lower()
    # 真正的判準是可執行的那一支，不是上面那行字串比對。
    retrypolicy.render_feedback("x::y — assert: ", attempt=1, max_attempts=3)


def test_ks1_negative_control_a_dirty_template_raises(monkeypatch):
    """負向控制：模板被改髒 ⇒ `render_feedback` 必須 raise，不是靜靜送出去。"""
    monkeypatch.setattr(retrypolicy, "FEEDBACK_TEMPLATE",
                        "You are responsible for this.\n\n{block}\n")
    with pytest.raises(KS1Violation):
        retrypolicy.render_feedback("boom", attempt=1, max_attempts=2)


def test_ks1_violation_from_the_client_suite_voids_the_run(tmp_path, upstream):
    """責任修辭也可能**從客戶的測試訊息**帶進來 ⇒ 一樣不准送出去。

    判 `infra_void`（鐵律 1「違反＝run 作廢」），**不判拒交也不判通過**——
    那一格根本沒有量到任何東西。
    """
    r = _go(tmp_path, mode="always_bad", retry_arm="revise", max_attempts=3,
            suite=_suite(tmp_path, "dirty", _KS1_DIRTY_TEST))
    s = r["summary"]
    assert s["stop_reason"] == "ks1_violation"
    assert s["infra_void"] and "KS1Violation" in s["infra_void"]
    assert launcher.exit_code(s) == launcher.EXIT_VOID
    # 作廢的 run 不留回饋檔，也不落收據鏈（基建事件不是裁決）。
    assert not (r["ws"] / retrypolicy.FEEDBACK_FILENAME).exists()
    assert not (r["run_dir"] / f"receipts_{launcher.ARM_ON}.ndjson").exists()


# ══ 7) 預設不改既有使用者的行為，壞組合一律 fail-visible ══════════════════
def test_retry_none_is_still_exactly_v0(tmp_path, upstream):
    r = _go(tmp_path, mode="always_bad")
    s = r["summary"]
    assert s["retry"] == "none" and s["max_attempts"] == 1
    assert s["attempts_used"] == 1 and s["stop_reason"] == "visible_fail"
    assert _chain_types(r["run_dir"]) == {"ws_attempt": 1, "ws_verdict": 1}
    assert len(r["trace"]) == 1


def test_resolve_max_attempts_refuses_the_silent_no_op_combos():
    assert launcher.resolve_max_attempts("none", None) == 1
    assert launcher.resolve_max_attempts("revise", None) == \
        retrypolicy.DEFAULT_MAX_ATTEMPTS
    assert launcher.resolve_max_attempts("resample", 5) == 5
    for arm, n in (("none", 3), ("revise", 0), ("nope", None)):
        with pytest.raises(SystemExit):
            launcher.resolve_max_attempts(arm, n)


def test_retry_on_the_off_arm_is_refused(tmp_path, upstream):
    """OFF 臂沒有裁決可以拿來決定要不要再跑一次 ⇒ 在那裡開迴圈是壞組合。"""
    with pytest.raises(SystemExit):
        _go(tmp_path, mode="always_bad", retry_arm="revise", vacant_on=False)


def test_the_documented_template_is_the_one_that_ships(tmp_path):
    """`docs/VACANT_RUN.md` §7.3 印的回饋模板必須**逐字**等於送出去的那一份。

    文件上印一份、程式送另一份，是「紀錄忠實」這個主張最便宜的破法。
    """
    doc = (ROOT / "docs" / "VACANT_RUN.md").read_text(encoding="utf-8")
    assert retrypolicy.FEEDBACK_TEMPLATE.strip() in doc
    assert retrypolicy.FEEDBACK_FILENAME in doc


def test_cli_exposes_both_arms_and_the_ceiling():
    args = launcher.build_parser().parse_args(
        ["--retry", "revise", "--max-attempts", "4", "--", "echo", "hi"])
    assert args.retry == "revise" and args.max_attempts == 4
    assert launcher.build_parser().parse_args(["--", "x"]).retry == "none"


# ══════════════════════════════════════════════════════════════════════════
#  V2：回饋走 argv（`--feedback-into prompt|both`）
# ══════════════════════════════════════════════════════════════════════════

PH = retrypolicy.FEEDBACK_PLACEHOLDER

#: 使用者那條 agent 命令的最後一個參數。**placeholder 一定在結尾**（V2 的硬規則：
#: 尾端 append 才保得住 provider 的前綴快取）。
_PROMPT_PLAIN = "write add(a, b) into solution.py"
_PROMPT_WITH_PH = _PROMPT_PLAIN + PH

#: V2 的假 agent：**只看 argv，一個字都不讀 `VACANT_FEEDBACK.md`**。
#: 它就是負向控制的本體——V1 的檔案管道在它身上一定失敗，而那不是因為我們把
#: 檔案關掉了（trace 與工作區都證明檔在、內容也對），是因為**沒有人保證
#: agent 會去讀它**。那個洞正是 V2 要補的那一個。
_ARGV_AGENT = r'''
import json, os, pathlib, sys, urllib.request

MODE, TRACE, PROMPT = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3]
ws = pathlib.Path.cwd()
fb = ws / "VACANT_FEEDBACK.md"
with TRACE.open("a", encoding="utf-8") as f:
    f.write(json.dumps({
        "argv": list(sys.argv[1:]),
        "prompt": PROMPT,
        # ⚠ 只記「那個檔在不在」，**刻意不讀它的內容**：這支 agent 的決定
        #   完全來自 argv，讀了就不是負向控制了。
        "feedback_file_exists": fb.exists(),
    }, ensure_ascii=False) + "\n")

base = os.environ["OPENAI_BASE_URL"]
req = urllib.request.Request(base.rstrip("/") + "/chat/completions",
                             data=b'{"model":"m","messages":[]}', method="POST")
req.add_header("Content-Type", "application/json")
with urllib.request.urlopen(req, timeout=30) as r:
    r.read()

GOOD = "def add(a, b):\n    return a + b\n"
BAD = "def add(a, b):\n    return a - b\n"
code = BAD if MODE == "always_bad" else (GOOD if "check_add" in PROMPT else BAD)
(ws / "solution.py").write_text(code, encoding="utf-8")
'''


def _argv_agent(tmp: pathlib.Path, mode: str, trace: pathlib.Path,
                prompt: str) -> list[str]:
    p = tmp / "argv_agent.py"
    p.write_text(_ARGV_AGENT, encoding="utf-8")
    return [sys.executable, str(p), mode, str(trace), prompt]


def _go2(tmp: pathlib.Path, *, mode: str = "fix_when_told_in_argv",
         feedback_into: str = "prompt", retry_arm: str = "revise",
         max_attempts: int | None = 3, placeholder: bool = True,
         suite: pathlib.Path | None = None, ws_name: str = "ws2",
         run_name: str = "run2") -> dict:
    """V2 的場地。回 summary ＋ agent **真的收到**的那幾條 argv。

    `plain_argv` ＝「沒有 Vacant」時使用者會打的那一條（沒有 placeholder）——
    第 1 次的逐位元比對就是對著它比，不是對著我們自己算的東西比。
    """
    ws = _ws(tmp, ws_name)
    trace = tmp / f"trace_{ws_name}.jsonl"
    run_dir = tmp / run_name
    argv = _argv_agent(tmp, mode, trace,
                       _PROMPT_WITH_PH if placeholder else _PROMPT_PLAIN)
    plain_argv = _argv_agent(tmp, mode, trace, _PROMPT_PLAIN)
    summary = launcher.run(
        argv, workspace=ws, run_dir=run_dir,
        suite_dir=(_suite(tmp) if suite is None else suite),
        vacant_on=True, task_id=f"t_{ws_name}", sandbox_name="none",
        retry_arm=retry_arm, max_attempts=max_attempts,
        feedback_into=feedback_into)
    return {"summary": summary, "ws": ws, "run_dir": run_dir, "argv": argv,
            "plain_argv": plain_argv,
            "trace": [json.loads(x) for x in
                      trace.read_text(encoding="utf-8").splitlines() if x]}


# ── V2-1) 第 1 次的 argv 與「沒有 Vacant」時逐位元相同 ────────────────────
def test_v2_first_attempt_argv_is_byte_identical_to_no_vacant(tmp_path,
                                                              upstream):
    """兩臂可比性的基礎：第一次就不一樣的話，後面量到的差別有一半是

    「第一次的 prompt 本來就不同」。形狀與 wire 那條「兩臂 body 逐位元相同」
    同一個用意。
    """
    r = _go2(tmp_path, max_attempts=2)
    s = r["summary"]

    assert r["argv"][-1].endswith(PH)          # 使用者寫的那條**有** placeholder
    a1 = s["attempts"][0]
    assert a1["argv"] == r["plain_argv"]       # spawn 出去的那條**沒有**
    assert a1["argv_sha256"] == retrypolicy.argv_sha256(r["plain_argv"])
    assert a1["feedback_in_prompt_bytes"] == 0
    assert a1["feedback_delivery"] == "prompt"

    # agent 那一端收到的也是同一條（收據說的 ≠ 行程收到的，那收據就不算數）。
    assert r["trace"][0]["prompt"] == _PROMPT_PLAIN
    assert (r["trace"][0]["prompt"].encode("utf-8")
            == _PROMPT_PLAIN.encode("utf-8"))
    assert PH not in r["trace"][0]["prompt"]

    # 簽進鏈裡的也是同一個指紋。
    first = json.loads((r["run_dir"] / f"receipts_{launcher.ARM_ON}.ndjson")
                       .read_text(encoding="utf-8").splitlines()[0])
    assert first["type"] == "ws_attempt"
    assert first["payload"]["argv_sha256"] == a1["argv_sha256"]
    assert first["payload"]["feedback_delivery"] == "prompt"
    _assert_ruler_is_happy(r["run_dir"])


# ── V2-2) 第 2 次＝第 1 次的逐位元前綴 ＋ 回饋 ────────────────────────────
def test_v2_second_attempt_argv_is_the_first_plus_the_feedback(tmp_path,
                                                               upstream):
    r = _go2(tmp_path, mode="always_bad", max_attempts=2,
             ws_name="ws2_pref", run_name="run2_pref")
    s = r["summary"]
    a1, a2 = s["attempts"][0], s["attempts"][1]

    assert a2["argv"][:-1] == a1["argv"][:-1]     # 其餘參數一個位元都沒動
    p1, p2 = a1["argv"][-1], a2["argv"][-1]
    assert p2.startswith(p1)                      # **逐位元前綴**
    tail = p2[len(p1):]
    assert tail == "\n\n" + a1["feedback"]["text"]
    assert "check_add" in tail
    assert a2["feedback_in_prompt_bytes"] == len(tail.encode("utf-8")) > 0

    # agent 行程收到的也一樣（第 2 次是第 1 次的延長，不是另一條命令）。
    assert r["trace"][1]["prompt"] == p2
    assert r["trace"][1]["prompt"].startswith(r["trace"][0]["prompt"])


# ── V2-3) 只看 argv 的 agent：prompt 過、file 不過（負向控制）─────────────
def test_v2_an_agent_that_only_reads_argv_passes_in_prompt_mode_and_fails_in_file_mode(  # noqa: E501
        tmp_path, upstream):
    """**這一條是 V2 的全部理由。**

    同一支 agent、同一份回饋、同樣的額度：回饋進 argv 就會被用到，
    回饋只進檔案就不會。⚠ 能說的到此為止——「回饋一定出現在模型的輸入裡」，
    **不是**「不可忽略」。這支假 agent 照做，是因為我們寫死它照做；
    真模型看得到也可以不理（`docs/VACANT_RUN.md` §8 的誠實邊界 1）。
    """
    prompt_run = _go2(tmp_path, feedback_into="prompt", placeholder=True,
                      ws_name="ws_p", run_name="run_p")
    file_run = _go2(tmp_path, feedback_into="file", placeholder=False,
                    ws_name="ws_f", run_name="run_f")

    ps, fs = prompt_run["summary"], file_run["summary"]
    assert ps["accepted"] is True and ps["stop_reason"] == "visible_pass"
    assert ps["attempts_used"] == 2
    assert fs["accepted"] is False and fs["stop_reason"] == "attempts_exhausted"
    assert fs["attempts_used"] == 3 == fs["max_attempts"]

    # ⚠ **檔案模式不是因為檔沒寫出來才失敗**：檔在、內容也對、agent 也看得到
    #   它存在。差別只有一個——沒有人保證它會去讀。
    fb = file_run["ws"] / retrypolicy.FEEDBACK_FILENAME
    assert "check_add" in fb.read_text(encoding="utf-8")
    assert file_run["trace"][1]["feedback_file_exists"] is True
    assert file_run["trace"][2]["feedback_file_exists"] is True

    # 反過來：prompt 模式**一個檔都沒往工作區寫**（交付物裡不多一個東西）。
    assert not (prompt_run["ws"] / retrypolicy.FEEDBACK_FILENAME).exists()
    assert all(t["feedback_file_exists"] is False for t in prompt_run["trace"])
    assert "check_add" in prompt_run["trace"][1]["prompt"]
    _assert_ruler_is_happy(prompt_run["run_dir"])
    _assert_ruler_is_happy(file_run["run_dir"])


def test_v2_both_delivers_to_the_file_and_the_prompt(tmp_path, upstream):
    """`both` ＝兩邊都給。**不可以被寫成 if/else 漏掉一邊**（`retry.py` 的
    `_PROMPT_MODES`／`_FILE_MODES` 就是為了不讓別處用字串比對）。"""
    r = _go2(tmp_path, feedback_into="both", ws_name="ws_b", run_name="run_b")
    s = r["summary"]
    assert s["accepted"] is True and s["attempts_used"] == 2
    assert "check_add" in r["trace"][1]["prompt"]               # 進了 argv
    assert r["trace"][1]["feedback_file_exists"] is True        # 也進了檔
    assert s["attempts"][0]["feedback"]["sha256"]               # 檔的 sha256 有落盤
    assert s["attempts"][1]["feedback_in_prompt_bytes"] > 0


# ── V2-4) 缺 placeholder ＋ prompt ⇒ SystemExit（不准安靜退回檔案模式）────
def test_v2_missing_placeholder_with_prompt_mode_is_a_hard_stop(tmp_path,
                                                                upstream):
    with pytest.raises(SystemExit) as exc:
        _go2(tmp_path, feedback_into="prompt", placeholder=False,
             ws_name="ws_miss", run_name="run_miss")
    assert PH in str(exc.value)
    # ⚠ **安靜退回檔案模式的反面**：那一跑連 run 目錄都不准開始寫。
    #   收據寫 `prompt` 而模型的輸入裡一個字都沒有，是這條擋門唯一要殺的東西。
    assert not (tmp_path / "run_miss").exists()

    # 反向：argv 有 placeholder 但 mode 是 file ⇒ 那串字會原樣送給 agent 看。
    with pytest.raises(SystemExit):
        _go2(tmp_path, feedback_into="file", placeholder=True,
             ws_name="ws_lit", run_name="run_lit")
    # 沒有下一次 spawn ⇒ 回饋永遠不會被產生。
    with pytest.raises(SystemExit):
        _go2(tmp_path, feedback_into="prompt", retry_arm="none",
             max_attempts=None, ws_name="ws_none", run_name="run_none")


def test_v2_ks1_applies_to_the_users_own_command(tmp_path, upstream):
    """鐵律 1 不因為換了管道就放鬆：**責任修辭在 argv 裡一樣不准送出去。**

    這一格的來源是使用者自己寫的那條命令（V1 那條是客戶測試的訊息帶進來的）。
    判 `infra_void`——鐵律 1 說的是「違反＝run 作廢」，不是「拒交」。
    ⚠ 這也是 `render_argv` 那個 `except KS1Violation` 分支唯一的可執行證明：
      沒有它，那段錯誤處理是死碼。
    """
    ws = _ws(tmp_path, "ws_ks1")
    trace = tmp_path / "trace_ks1.jsonl"
    argv = _argv_agent(tmp_path, "always_bad", trace,
                       "you are responsible for solution.py" + PH)
    run_dir = tmp_path / "run_ks1"
    s = launcher.run(argv, workspace=ws, run_dir=run_dir,
                     suite_dir=_suite(tmp_path), vacant_on=True,
                     task_id="ks1_argv", sandbox_name="none",
                     retry_arm="revise", max_attempts=2,
                     feedback_into="prompt")
    assert s["stop_reason"] == "ks1_violation"
    assert s["infra_void"] and "KS1Violation" in s["infra_void"]
    assert launcher.exit_code(s) == launcher.EXIT_VOID
    # 作廢的 run 不落收據鏈（基建事件不是裁決），agent 也一次都沒被 spawn。
    assert not (run_dir / f"receipts_{launcher.ARM_ON}.ndjson").exists()
    assert not trace.exists()


def test_v2_placeholder_must_be_at_the_end_of_that_argument():
    """插在中間會讓 provider 的前綴快取整段失效，**而那個成本不會出現在

    任何一個我們落盤的欄位裡**——所以它要在畫面上死掉。
    """
    for bad in (f"a{PH}b", f"a{PH}{PH}", PH + "tail"):
        with pytest.raises(SystemExit):
            retrypolicy.render_argv(["pi", "-p", bad], "fb", mode="prompt")
    # 打錯 mode 也要死在畫面上（`delivers_to_prompt()` 為 False 那條路
    # 會安靜退回檔案模式——前一棒的 bug，擋門放在 early-return 後面）。
    with pytest.raises(SystemExit):
        retrypolicy.render_argv(["pi", "-p", f"x{PH}"], "fb", mode="prmopt")
    with pytest.raises(SystemExit):
        retrypolicy.render_argv(["pi", "-p", f"x{PH}"], "fb", mode="both\n")


# ── V2-5) V/GT：hidden 不得出現在任何一次的 argv ──────────────────────────
def _argv_texts(r: dict) -> list[str]:
    """agent **真的收到**的每一個 argv 元素 ＋ 收據落盤的每一個。

    兩份都掃：只掃落盤的那份，等於相信落盤的與 spawn 的是同一條。
    """
    seen = [x for t in r["trace"] for x in t["argv"]]
    logged = [x for a in r["summary"]["attempts"] for x in a.get("argv", [])]
    return seen + logged


def test_v2_feedback_in_prompt_never_contains_hidden_testdata(tmp_path,
                                                              upstream):
    hidden = _suite(tmp_path, "hidden", _HIDDEN_TEST)
    assert GT_CANARY in (hidden / "test_hidden.py").read_text(encoding="utf-8")
    r = _go2(tmp_path, mode="always_bad", feedback_into="prompt",
             max_attempts=3, suite=_suite(tmp_path),   # ← 餵的是 visible
             ws_name="ws_vgt", run_name="run_vgt")

    # ⚠ **量具要先證明它接上了**：一個字都沒寫進 argv 的情況下「掃描零命中」
    #   是真的，但它證明的是量具沒接上，不是沒有洩漏。
    texts = _argv_texts(r)
    assert len(r["trace"]) == 3 and texts
    assert "check_add" in r["trace"][1]["prompt"]
    assert "check_add" in r["trace"][2]["prompt"]

    assert _scan(texts) == []


def test_v2_vgt_canary_scan_has_teeth_in_argv(tmp_path, upstream):
    """負向控制：把 hidden **當成可見套件**餵進去，同一支掃描必須翻紅。

    沒有這一條，上面那個「零命中」跟把掃描關掉在輸出上同形。
    """
    r = _go2(tmp_path, mode="always_bad", feedback_into="prompt",
             max_attempts=2, suite=_suite(tmp_path, "hidden", _HIDDEN_TEST),
             ws_name="ws_teeth", run_name="run_teeth")
    assert _scan(_argv_texts(r)) == [GT_CANARY, NUM_CANARY]


# ── V2 的門面：CLI ＋ 文件 ────────────────────────────────────────────────
def test_v2_cli_exposes_feedback_into_and_defaults_to_file():
    ap = launcher.build_parser()
    assert ap.parse_args(["--", "x"]).feedback_into == "file"   # 預設＝V1
    args = ap.parse_args(["--feedback-into", "prompt", "--retry", "revise",
                          "--", "pi", "-p", f"go{PH}"])
    assert args.feedback_into == "prompt"
    with pytest.raises(SystemExit):        # 封閉集合，多一個就是規格變更
        launcher.build_parser().parse_args(["--feedback-into", "wire", "--", "x"])


def test_v2_docs_print_the_placeholder_that_ships(tmp_path):
    """文件印一個 placeholder、程式認另一個，使用者那條命令就會安靜地不生效。"""
    doc = (ROOT / "docs" / "VACANT_RUN.md").read_text(encoding="utf-8")
    assert retrypolicy.FEEDBACK_PLACEHOLDER in doc
    assert "--feedback-into" in doc
    for mode in retrypolicy.DELIVERY_MODES:
        assert f"`{mode}`" in doc


# ══ 兩件小事 ══════════════════════════════════════════════════════════════
def test_suite_under_the_workspace_is_refused(tmp_path):
    """**agent 改得到的驗收不是驗收。**

    不是「可能被繞過」，是量具與被量的東西放在同一個人手上 ⇒ `accepted=True`
    退化成「它讓自己過了」。正解是 `demo.py::scaffold`：權威的那一份放工作區外，
    要給 agent 看就另外**複製**一份進去。
    """
    ws = _ws(tmp_path, "ws_inside")
    inside = _suite(ws, "tests_visible")          # ← 驗收放在工作區**裡面**
    with pytest.raises(SystemExit) as exc:
        launcher.run([sys.executable, "-c", "pass"], workspace=ws,
                     run_dir=tmp_path / "run_inside", suite_dir=inside,
                     vacant_on=True, task_id="inside", sandbox_name="none")
    assert "--suite" in str(exc.value)
    assert not (tmp_path / "run_inside").exists()

    # 工作區外的同一份就過得去（擋的是位置，不是這個目錄）。
    outside = _suite(tmp_path, "visible_outside")
    launcher.run([sys.executable, "-c", "pass"], workspace=ws,
                 run_dir=tmp_path / "run_outside", suite_dir=outside,
                 vacant_on=True, task_id="outside", sandbox_name="none")


_ORPHAN_CHILD = r'''
import pathlib, sys, time
time.sleep(float(sys.argv[1]))
pathlib.Path(sys.argv[2]).write_text("written after the freeze\n",
                                     encoding="utf-8")
'''

#: agent 把真正的工作 fork 出去就走（背景 lint／watcher／自己的 worker
#: 都是這個形狀），**自己不等它**。
_ORPHAN_AGENT = r'''
import pathlib, subprocess, sys
ws = pathlib.Path.cwd()
subprocess.Popen([sys.executable, sys.argv[1], sys.argv[2],
                  str(ws / "sneaky.txt")])
(ws / "solution.py").write_text("def add(a, b):\n    return a + b\n",
                                encoding="utf-8")
'''


def test_grandchildren_are_killed_before_the_freeze(tmp_path):
    """`proc.wait()` **只等直接子行程**，孫行程不會被等到。

    那代表它可以在我們凍結之後繼續寫工作區——`ws_end_sha256` 就不再是
    「交付當下」的雜湊，而 TOCTOU 那條擋門只在凍結的那一瞬間看得到。
    所以 spawn 用 `start_new_session=True`，`wait()` 回來就 `killpg` 整組。
    """
    ws = _ws(tmp_path, "ws_orphan")
    child = tmp_path / "orphan_child.py"
    child.write_text(_ORPHAN_CHILD, encoding="utf-8")
    agent = tmp_path / "orphan_agent.py"
    agent.write_text(_ORPHAN_AGENT, encoding="utf-8")

    s = launcher.run([sys.executable, str(agent), str(child), "1.5"],
                     workspace=ws, run_dir=tmp_path / "run_orphan",
                     suite_dir=_suite(tmp_path), vacant_on=True,
                     task_id="orphan", sandbox_name="none")
    # ⚠ **這一行是這條測試的牙齒**：`True` ＝ 直接子行程都結束了、群組裡還有
    #   東西活著。沒有 `start_new_session` 的話這裡永遠是 False。
    assert s["attempts"][0]["orphans_killed"] is True
    assert s["accepted"] is True                     # 交付本身照樣成立

    time.sleep(2.5)                                  # 給孫行程它要的那 1.5 秒
    assert not (ws / "sneaky.txt").exists()          # 它沒能寫成
    assert s["ws_end_sha256"] == launcher.wshash.tree_hash(ws)
