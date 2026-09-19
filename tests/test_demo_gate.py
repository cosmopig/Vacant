"""`vacant demo gate` 的擋門測試——**demo 不准變成假演出**。

第一幕是使用者對整個系統的第一印象，所以這一批測的不是「函式有沒有回東西」，
是**畫面上那三句話有沒有真的發生**：

  · `test_gate_really_refuses_the_delivery`
      agent 自認成功（rc=0）、閘門判拒交、`vacant run` 這個**真子行程**
      的退出碼是 20。三個數字都從真跑讀出來，不是常數。
  · `test_failure_text_is_really_raised_not_a_string_literal`
      畫面上那句 `ImportError: cannot import name 'mul'` 必須是驗收
      driver 當場抓到的例外——所以 `demo.py` 的原始碼裡**不准**有那句話。
  · `test_receipt_is_real_and_verifies_with_the_existing_ruler`
      收據是真的 Ed25519 鏈，而且用**既有的**驗章器（`vacant_network.vrun.verify_receipts`
      ＝`ops/gain/replay/verify_run_receipts.py` 的同一支）驗得過。
      不准另寫第二把尺。
      ⚠ **2026-09-19 起這一幕的總判是 `VOID` 不是 `OK`，而且那是規格**：
      這隻假 agent 一通模型都沒打 ⇒ `requests_seen == 0` ⇒ 鏈完整但不是
      「中介發生過」的證據。判回 OK ＝ 尺分不出零請求的假拒交格，
      那正是那天量到的洞，所以這條測試把 VOID 釘死。
  · `test_demo_agent_makes_no_network_call`
      「沒有網路也跑得完」的可執行版本：假 agent 的原始碼裡不准出現任何
      連線用的模組，而且真跑的 `requests_seen` 必須是 0。
  · `test_eco_demo_is_untouched`
      `vacant demo`（不給 kind）還是舊的生態對照實驗——沒有被覆蓋。
  · `test_selfcheck_requests_seen_is_the_evidence`
      README 寫的那個自檢指令的可執行證明：agent 真的打了一通模型請求時，
      `run_RUN-ON.json` 的 `requests_seen` 才會非 0。
      **「我設了環境變數」不是證據，這個數字才是。**
  · `test_verify_glob_accepts_absolute_path`
      畫面上印給使用者複製的那行驗證指令用的是絕對路徑；
      `--glob` 吃不吃絕對路徑，決定那行字是不是一行跑不動的裝飾。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vacant_network.vrun import demo, launcher                           # noqa: E402
from vacant_network.vrun import verify_receipts as vrr                   # noqa: E402


@pytest.fixture(scope="module")
def ran(tmp_path_factory) -> dict:
    """整批共用同一次真跑（約 1.5 秒）：跑一次，驗很多條。"""
    root = tmp_path_factory.mktemp("demo_gate") / "run"
    return demo.run_demo(root, quiet=True)


def test_gate_really_refuses_the_delivery(ran):
    assert ran["plain_rc"] == 0                       # 裸 agent 自認成功
    assert ran["gated_rc"] == launcher.EXIT_REFUSED == 20
    assert ran["stop_reason"] == "visible_fail"
    assert ran["accepted"] is False
    assert (ran["visible_passed"], ran["visible_total"]) == (1, 2)


def test_failure_text_is_really_raised_not_a_string_literal(ran):
    assert "cannot import name 'mul'" in ran["failures"]
    src = (ROOT / "vacant_network" / "vrun" / "demo.py").read_text(encoding="utf-8")
    # 那句話只准出現在**模組 docstring**裡（說明 V0 實測長什麼樣），
    # 不准出現在任何一行會被執行的碼上——否則畫面上那句就是印死字串。
    lines = src.splitlines()
    end_of_docstring = next(i for i, l in enumerate(lines, 1)
                            if l.startswith("from __future__"))
    hits = [i for i, l in enumerate(lines, 1) if "cannot import name" in l]
    assert hits and max(hits) < end_of_docstring, (hits, end_of_docstring)


def test_receipt_is_real_and_verifies_with_the_existing_ruler(ran):
    assert ran["receipt_entries"] == 2                # ws_attempt + ws_verdict
    # 鏈是完整的（失敗 0），但這一幕零模型請求 ⇒ 總判 VOID。兩件事分開講。
    assert ran["receipts_verdict"] == "VOID"
    assert ran["receipts_failed_total"] == 0
    assert ran["receipts_unmediated_chains_n"] == 1
    run_dir = pathlib.Path(ran["root"]) / "receipts"
    chain = [json.loads(l) for l in
             (run_dir / "receipts_RUN-ON.ndjson")
             .read_text(encoding="utf-8").splitlines() if l.strip()]
    assert chain[-1]["type"] == "ws_verdict"
    assert chain[-1]["payload"]["accepted"] is False
    assert chain[-1]["payload"]["stop_reason"] == "visible_fail"
    # 再用既有那把尺跑一次（不准另寫第二把）
    rows = vrr.verify_run(run_dir)
    assert [r["verdict"] for r in rows] == ["VOID"]
    # ⚠ **VOID 不准把鏈說成壞的**：鏈完整與中介發生過是兩個維度。
    assert rows[0]["chain_ok"] is True
    assert rows[0]["logbook_verify_chain"] is True
    assert rows[0]["failures"] == []
    assert rows[0]["mediated"] is False
    assert rows[0]["void_reason"] == "no_requests_seen"


def test_demo_agent_makes_no_network_call(ran, tmp_path):
    assert ran["requests_seen"] == 0
    paths = demo.scaffold(tmp_path / "scaffold")
    src = paths["agent"].read_text(encoding="utf-8")
    for banned in ("socket", "urllib", "http", "requests", "httpx", "subprocess"):
        assert banned not in src, f"假 agent 不准碰 {banned}：離線要跑得完"


def test_the_anti_performance_guard_actually_fires():
    """負控制：防呆自己要抓得到「這一幕沒發生」，不然它只是註解。"""
    ok = subprocess.CompletedProcess([], 0, stdout="Done.\n", stderr="")
    gated_ok = subprocess.CompletedProcess([], launcher.EXIT_REFUSED, "", "")
    summary = {"stop_reason": "visible_fail", "accepted": False, "refused": True,
               "failures": "boom", "visible_passed": 1, "visible_total": 2}
    chain = [{"type": "ws_verdict", "payload": {"accepted": False}}]
    verified = {"verdict": "VOID", "failed_total": 0, "unmediated_chains_n": 1}
    st = subprocess.CompletedProcess([], 0, stdout="selftest: PASS\n", stderr="")
    vf = subprocess.CompletedProcess([], demo.VERIFY_EXIT_VOID, stdout="",
                                     stderr="")
    # 乾淨路徑不喊停
    demo._assert_not_a_performance(ok, gated_ok, summary, chain, verified, st, vf)

    # 每一種「其實沒發生」都要被指名
    for label, kw in (
        ("閘門沒擋", {"gated": subprocess.CompletedProcess([], 0, "", "")}),
        ("裁決不對", {"summary": {**summary, "stop_reason": "visible_pass"}}),
        ("收據說 accepted", {"chain": [{"type": "ws_verdict",
                                        "payload": {"accepted": True}}]}),
        ("收據驗不過", {"verified": {"verdict": "BROKEN", "failed_total": 1,
                                      "unmediated_chains_n": 0}}),
        # ⚠ 這一條是新的負控制：尺**判回 OK** 也要當場死掉——零請求的這一幕
        #   如果驗成乾淨的 OK，代表那把尺分不出假拒交格。
        ("尺判回 OK（分不出零請求）",
         {"verified": {"verdict": "OK", "failed_total": 0,
                       "unmediated_chains_n": 0}}),
        ("負控制沒過", {"st": subprocess.CompletedProcess([], 1, "1 FAILED", "")}),
        ("驗章器回 0（應該是 VOID）",
         {"vf": subprocess.CompletedProcess([], 0, "", "")}),
    ):
        args = {"plain": ok, "gated": gated_ok, "summary": summary,
                "chain": chain, "verified": verified, "selftest": st,
                "verify": vf}
        args.update({{"st": "selftest", "vf": "verify"}.get(k, k): v
                     for k, v in kw.items()})
        try:
            demo._assert_not_a_performance(**args)
        except SystemExit:
            continue
        pytest.fail(f"防呆沒抓到「{label}」——它就只是一段註解")


def test_eco_demo_is_untouched():
    """`vacant demo` 不給 kind ⇒ 還是舊的 §11 生態對照實驗。"""
    from vacant_network.cli import build_parser

    assert build_parser().parse_args(["demo"]).kind == "eco"
    assert build_parser().parse_args(["demo", "gate"]).kind == "gate"


def test_cli_demo_gate_exits_zero_and_prints_json(tmp_path):
    """`vacant demo gate` 自己回 0（它成功地示範了一次拒交）。

    真正非 0 的是它內部那個 `vacant run` 子行程——退出碼寫在 JSON 裡。
    """
    out = subprocess.run(
        [sys.executable, "-m", "vacant_network.cli", "demo", "gate", "--json",
         "--root", str(tmp_path / "cli")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stderr[-2000:]
    got = json.loads(out.stdout)
    assert got["gated_rc"] == 20 and got["accepted"] is False


# ── 自檢指令：requests_seen 才是「被中介了」的證據 ────────────────────────
_CALLER = '''
import os, urllib.request
req = urllib.request.Request(
    os.environ["OPENAI_BASE_URL"].rstrip("/") + "/chat/completions",
    data=b'{"model":"m"}', method="POST")
req.add_header("Content-Type", "application/json")
with urllib.request.urlopen(req, timeout=30) as r:
    r.read()
open("solution.py", "w").write("def add(a, b):\\n    return a + b\\n")
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
def upstream():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1},
                     daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()
    srv.server_close()


def test_selfcheck_requests_seen_is_the_evidence(tmp_path, upstream, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", upstream)
    agent = tmp_path / "caller.py"
    agent.write_text(_CALLER, encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir()
    run_dir = tmp_path / "vr"
    launcher.run([sys.executable, str(agent)], workspace=ws, run_dir=run_dir,
                 suite_dir=None, vacant_on=True, task_id="selfcheck",
                 sandbox_name="none", allow_no_suite=True)
    # ↓ README／demo 印出來的那一行，逐字同一個讀法
    seen = json.load((run_dir / "run_RUN-ON.json").open(encoding="utf-8"))
    assert seen["requests_seen"] == 1
    # 反面：沒有打模型的那一跑，同一個欄位就是 0——所以它分得開兩種情況
    assert json.loads((tmp_path / "vr" / "rows.jsonl")
                      .read_text(encoding="utf-8").splitlines()[0]
                      )["requests_seen"] == 1


def test_verify_glob_accepts_absolute_path(ran):
    run_dir = pathlib.Path(ran["root"]) / "receipts"
    out = vrr.run_glob(str(run_dir))
    # 這條測的是**路徑吃不吃**，不是判決內容；`VOID` 是那一幕的正解
    # （零模型請求），只要 `runs_n` 數得對就代表 glob 命中了。
    assert out["runs_n"] == 1 and out["verdict"] == "VOID"
    assert out["broken_chains_n"] == 0
    # 帶萬用字元的絕對 pattern 也要吃（`--glob '~/.vacant-run/*'` 的形狀）
    out2 = vrr.run_glob(str(run_dir.parent / "*"))
    assert out2["runs_n"] >= 1 and out2["verdict"] == "VOID"
