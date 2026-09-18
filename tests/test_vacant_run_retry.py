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
      **配一條負向控制** `test_reset_that_does_not_return_to_start_is_infra_void`
      （把 `restore_origin` 換成 no-op ⇒ 重置後的複查必須判 `ws_reset_failed`）。
  · `test_attempts_exhausted_is_a_refusal_with_its_own_name`
      用完額度仍沒過 ⇒ 拒交、退出碼非 0、收據記 `attempts_exhausted`。
  · `test_receipts_reconcile_for_every_ending`
      **R530 踩過的坑**：只在 happy path 簽 attempt ⇒ 0 筆 attempt、1 筆
      verdict ⇒ 鏈沒壞，壞的是「鏈說得出這一格發生過什麼」。
      這一條對**每一種收尾**都跑既有的那把尺
      （`ops/gain/replay/verify_run_receipts.py`，不准另寫第二把），
      並逐格斷言 `attempt 數 ≥ verdict 數`。
      **配一條負向控制** `test_the_ruler_catches_the_r530_hole_in_this_code`
      （把 `_sign_attempt` 換成 no-op ＝當年那個 bug 本身 ⇒ 鏈仍完整、
      總判必須 BROKEN）。沒有它，上面那些「尺說 OK」跟把尺拔掉在輸出上同形。
  · `test_feedback_file_never_contains_hidden_testdata`
      V/GT 紅線的可執行版本，形狀照抄 `tests/test_gain_vgt_canary.py`：
      canary 種在 hidden 側，掃 feedback 檔要零命中。**配一條負向控制**
      （把 hidden 當成可見套件餵進去，同一支掃描必須翻紅）——
      沒有負控的「掃描零命中」跟把掃描關掉在輸出上同形。
  · `test_ks1_*`
      鐵律 1 的可執行防呆接上了，而且**有負向控制**。
  · `test_retry_none_is_still_exactly_v0`
      預設不改既有使用者的行為。

⚠ 本檔零模型呼叫、零機時：上游是一個本機假 server，agent 是一支 40 行的
  Python，驗收沙箱走 `none`。
"""
from __future__ import annotations

import json
import pathlib
import sys
import threading
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


def test_reset_that_does_not_return_to_start_is_infra_void(tmp_path, upstream,
                                                          monkeypatch):
    """負向控制：重置沒回到起點 ⇒ `ws_reset_failed`＝`infra_void`，**不判拒交也不判通過**。

    `retry.py` 的 docstring 寫「還原完會再量一次樹雜湊，對不回起點 ⇒ 判
    `infra_void`」。把 `restore_origin` 換成 no-op，那句話才變成可執行的——
    否則上面那條「每次都回到起點」證明的是這支假 agent 的行為，
    不是**那道複查真的在看**。
    """
    monkeypatch.setattr(retrypolicy, "restore_origin", lambda *a, **k: None)
    r = _go(tmp_path, mode="always_bad", retry_arm="resample", max_attempts=3)
    s = r["summary"]
    assert s["stop_reason"] == "ws_reset_failed"
    assert s["infra_void"] and s["infra_void"].startswith("reset=")
    assert launcher.exit_code(s) == launcher.EXIT_VOID
    # 第二次嘗試在 spawn **之前**就停了 ⇒ agent 只跑過一次。
    assert len(r["trace"]) == 1
    assert s["attempts"][-1]["reset"]["back_to_start"] is False
    # `infra_void` 整條鏈都不落盤（基建事件不是裁決）。
    assert not (r["run_dir"] / f"receipts_{launcher.ARM_ON}.ndjson").exists()


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


def test_the_ruler_catches_the_r530_hole_in_this_code(tmp_path, upstream,
                                                     monkeypatch):
    """負向控制：把 `_sign_attempt` 變回 no-op（＝R530 當年那個 bug），那把尺必須翻紅。

    上面每一條都在斷言「尺說 OK」。**沒有這一條，那些 OK 跟把尺拔掉在輸出上同形**
    ——只證明鏈是完整的，不證明「0 筆 attempt／1 筆 verdict」會被抓到。

    這一條同時把那句話變成可執行的：斷言 `chain_ok` 與 `logbook_verify_chain`
    **都是 True**（鏈真的沒壞），而總判仍是 BROKEN、理由是
    `attempt_fewer_than_verdict`。壞的不是鏈，是**鏈說得出這一格發生過什麼**。
    """
    monkeypatch.setattr(launcher, "_sign_attempt", lambda *a, **k: None)
    r = _go(tmp_path, mode="always_bad", retry_arm="revise", max_attempts=3)
    assert r["summary"]["stop_reason"] == "attempts_exhausted"
    assert r["summary"]["attempts_used"] == 3        # 真的燒了三次
    assert _chain_types(r["run_dir"]) == {"ws_verdict": 1}

    out = vrr.verify_run(r["run_dir"])
    assert len(out) == 1
    rec = out[0]
    assert rec["chain_ok"] is True and rec["logbook_verify_chain"] is True
    assert rec["attempt_n"] == 0 and rec["verdict_n"] == 1
    assert rec["verdict"] == "BROKEN"
    assert [f["reason"] for f in rec["failures"]] == ["attempt_fewer_than_verdict"]


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
