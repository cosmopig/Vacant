"""門檻二：`verify_receipts` 要分得出**零請求的假拒交格**。

這支在架構裡承重什麼
────────────────────
2026-09-19 的隨傳隨到負控制（`runs/v1_five_agent_matrix_20260919/controls.sh`）
把 `/bin/true` 和一行 `cp` 放在 agent 的位置，**一通模型都不打**：

    ctl_norequest_refuse    exit 20   accepted=false  visible_fail   rs=0  rc=0
    ctl_norequest_deliver   exit 0    accepted=true   visible_pass   rs=0  rc=0

**退出碼、`accepted`、`stop_reason`、`agent_rc`、`chain_ok` 五個欄位在零通模型
呼叫下全部成立**，而當時驗章器對這兩格的總判是乾淨的 `OK`
（`controls_receipts_verify.txt` 逐字留著那一行「總判：OK」）。

本檔是那件事的可執行版本。四條紅線，一條一個測試：

  1. `requests_seen == 0` ⇒ **VOID**，而且總判反映得出來。
  2. **不准把 `chain_ok` 改成 false**——鏈確實是完整的，說它壞掉是另一種說謊。
  3. `--allow-no-suite` 那種**刻意沒有驗收**的跑不是假拒交格，不准誤殺。
  4. **舊鏈沒有 `requests_seen` 這個欄位** ⇒ `mediated=null`＝沒量到，
     **不是**「量到 0」，所以不准判 VOID（鐵律 3；已歸檔 6,468 筆的可比性）。

⚠ 誠實邊界：這一整批擋得住的是「**完全沒打**」，擋不住「打了但打到別的地方」
  ——那要看 `wire_by_protocol` 與 `upstreams`，而那兩個欄位不在簽章鏈上。
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

from vacant_network.crypto import pub_to_hex                             # noqa: E402
from vacant_network.identity import Identity                             # noqa: E402
from vacant_network.logbook import Logbook                               # noqa: E402
from vacant_network.vrun import launcher, receipts                       # noqa: E402
from vacant_network.vrun import verify_receipts as vrr                   # noqa: E402

#: 一通模型都不打的假 agent。**`ctl_norequest_refuse` 的 Python 版**。
_NO_REQUEST_AGENT = "import sys; sys.exit(0)\n"
#: 一通模型都不打，但**把參考解放進去** ⇒ 驗收會過。`ctl_norequest_deliver`。
_NO_REQUEST_DELIVER = ('open("solution.py", "w").write('
                       '"def add(a, b):\\n    return a + b\\n")\n')
#: 打一通的 agent（對照組）。
_ONE_REQUEST_AGENT = r'''
import os, urllib.request
base = os.environ["OPENAI_BASE_URL"].rstrip("/")
req = urllib.request.Request(base + "/chat/completions", data=b'{"m":1}',
                             method="POST")
urllib.request.urlopen(req, timeout=30).read()
open("solution.py", "w").write("def add(a, b):\n    return a + b\n")
'''

_VISIBLE = ("def check_add():\n"
            "    from solution import add\n"
            "    assert add(2, 3) == 5\n")


class _Upstream(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        return

    def do_POST(self):                                           # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")


@pytest.fixture()
def upstream():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1},
                     daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()
    srv.server_close()


def _scaffold(tmp: pathlib.Path, name: str, src: str) -> tuple:
    ws = tmp / f"ws_{name}"
    ws.mkdir(parents=True)
    agent = tmp / f"{name}.py"
    agent.write_text(src, encoding="utf-8")
    suite = tmp / "suite"
    if not suite.exists():
        suite.mkdir()
        (suite / "test_visible.py").write_text(_VISIBLE, encoding="utf-8")
    return ws, agent, suite


def test_zero_request_refusal_cell_is_VOID(tmp_path, upstream, monkeypatch):
    """`ctl_norequest_refuse` 的逐欄複製：五個欄位全成立，只有這一維抓得到。"""
    monkeypatch.setenv("VACANT_RUN_UPSTREAM_OPENAI", upstream)
    ws, agent, suite = _scaffold(tmp_path, "refuse", _NO_REQUEST_AGENT)
    run_dir = tmp_path / "rd_refuse"
    s = launcher.run([sys.executable, str(agent)], workspace=ws,
                     run_dir=run_dir, suite_dir=suite, vacant_on=True,
                     task_id="ctl_norequest_refuse", sandbox_name="none")

    # ── 那五個「全部成立」的欄位，逐個確認它們真的成立 ─────────────────
    assert launcher.exit_code(s) == launcher.EXIT_REFUSED == 20
    assert s["accepted"] is False and s["stop_reason"] == "visible_fail"
    assert s["agent_rc"] == 0
    assert s["requests_seen"] == 0 and s["wire_by_protocol"] == {}

    rec = vrr.verify_run(run_dir)[0]
    assert rec["chain_ok"] is True, "鏈是完整的"
    assert rec["logbook_verify_chain"] is True
    assert rec["failures"] == [] and rec["failed_n"] == 0
    # ── 唯一分得出來的那一維 ──────────────────────────────────────────
    assert rec["verdict"] == "VOID"
    assert rec["mediated"] is False
    assert rec["void_reason"] == "no_requests_seen"
    assert rec["unmediated_task_ids"] == ["ctl_norequest_refuse"]
    assert rec["requests_seen_total"] == 0

    out = vrr.run_glob(str(run_dir))
    assert out["verdict"] == "VOID", "一批裡有零請求的跑，總判不准是乾淨的 OK"
    assert out["broken_chains_n"] == 0, "VOID 不准被講成鏈壞了"
    assert out["unmediated_chains_n"] == 1
    assert vrr.exit_code(out) == vrr.EXIT_VOID != vrr.EXIT_BROKEN


def test_zero_request_delivery_cell_is_also_VOID(tmp_path, upstream, monkeypatch):
    """`ctl_norequest_deliver`：**交付格**（exit 0／accepted=true）一樣要抓到。

    只抓拒交格等於預設「作假只會往拒交的方向」，而那一天量到的是兩格都成立。
    """
    monkeypatch.setenv("VACANT_RUN_UPSTREAM_OPENAI", upstream)
    ws, agent, suite = _scaffold(tmp_path, "deliver", _NO_REQUEST_DELIVER)
    run_dir = tmp_path / "rd_deliver"
    s = launcher.run([sys.executable, str(agent)], workspace=ws,
                     run_dir=run_dir, suite_dir=suite, vacant_on=True,
                     task_id="ctl_norequest_deliver", sandbox_name="none")
    assert launcher.exit_code(s) == 0
    assert s["accepted"] is True and s["stop_reason"] == "visible_pass"
    assert s["requests_seen"] == 0

    rec = vrr.verify_run(run_dir)[0]
    assert rec["chain_ok"] is True and rec["failures"] == []
    assert rec["verdict"] == "VOID" and rec["mediated"] is False


def test_a_really_mediated_cell_is_OK(tmp_path, upstream, monkeypatch):
    """對照組：真的打了一通 ⇒ OK、`mediated=True`。**沒有這條就沒有對照。**"""
    monkeypatch.setenv("VACANT_RUN_UPSTREAM_OPENAI", upstream)
    ws, agent, suite = _scaffold(tmp_path, "real", _ONE_REQUEST_AGENT)
    run_dir = tmp_path / "rd_real"
    s = launcher.run([sys.executable, str(agent)], workspace=ws,
                     run_dir=run_dir, suite_dir=suite, vacant_on=True,
                     task_id="really_mediated", sandbox_name="none")
    assert s["requests_seen"] == 1 and s["accepted"] is True
    rec = vrr.verify_run(run_dir)[0]
    assert rec["verdict"] == "OK"
    assert rec["mediated"] is True and rec["void_reason"] is None
    assert rec["requests_seen_total"] == 1
    assert vrr.run_glob(str(run_dir))["verdict"] == "OK"


def test_allow_no_suite_with_traffic_is_not_killed(tmp_path, upstream,
                                                   monkeypatch):
    """⚠ `--allow-no-suite` **不是**假拒交格：它明講「這一次不量驗收」。

    兩個維度**正交**：沒量驗收（`accepted=null`）與沒中介（`requests_seen=0`）
    是兩件事，混在一起就會把一種刻意的用法誤殺掉。
    """
    monkeypatch.setenv("VACANT_RUN_UPSTREAM_OPENAI", upstream)
    ws, agent, _ = _scaffold(tmp_path, "ungated", _ONE_REQUEST_AGENT)
    run_dir = tmp_path / "rd_ungated"
    s = launcher.run([sys.executable, str(agent)], workspace=ws,
                     run_dir=run_dir, suite_dir=None, vacant_on=True,
                     task_id="ungated_but_mediated", sandbox_name="none",
                     allow_no_suite=True)
    assert s["accepted"] is None, "沒量驗收的那一格 accepted 應該是 null"
    assert s["stop_reason"] == "ungated" and s["requests_seen"] == 1

    rec = vrr.verify_run(run_dir)[0]
    assert rec["verdict"] == "OK", "刻意沒有驗收的跑不准被當成假拒交格"
    assert rec["mediated"] is True
    assert rec["ungated_task_ids"] == ["ungated_but_mediated"]
    assert vrr.run_glob(str(run_dir))["verdict"] == "OK"


def test_legacy_chain_without_the_field_is_not_VOID(tmp_path):
    """**已歸檔資料的可比性保險絲。**

    R460R／R529／R530 那 6,468 筆 verdict 一筆都沒有 `requests_seen`。
    沒有欄位 ⇒ `mediated=None` ＝**沒量到**，不是「量到 0」（鐵律 3）。
    判它們 VOID 等於把一句沒說過的話塞進已歸檔的資料裡。
    """
    d = tmp_path / "legacy"
    d.mkdir()
    ident = Identity.generate()
    book = Logbook()
    receipts.append_attempt(book, ident, task_id="t0", arm="HMIX", attempt=1,
                            gate_round=1, ws_sha256="a" * 64,
                            verdict_sha256="b" * 64,
                            conversation_sha256="c" * 64)
    receipts.append_verdict(book, ident, task_id="t0", arm="HMIX",
                            accepted=True, ws_start_sha256="d" * 64,
                            ws_end_sha256="e" * 64, verdict_sha256="b" * 64,
                            conversation_sha256="c" * 64,
                            stop_reason="visible_pass")
    book.save(d / "receipts_HMIX.ndjson")
    (d / "receipts_HMIX.pub.json").write_text(json.dumps(
        {"vacant_id": ident.vacant_id, "pub_hex": pub_to_hex(ident.pub)}),
        encoding="utf-8")
    (d / "rows.jsonl").write_text(
        json.dumps({"arm": "HMIX", "task_id": "t0"}) + "\n", encoding="utf-8")

    rec = vrr.verify_run(d)[0]
    assert "requests_seen" not in (
        json.loads((d / "receipts_HMIX.ndjson")
                   .read_text(encoding="utf-8").splitlines()[1])["payload"])
    assert rec["verdict"] == "OK"
    assert rec["mediated"] is None and rec["void_reason"] is None
    assert rec["requests_seen_total"] is None, "沒量到不准落成 0"
    assert rec["verdicts_without_requests_seen"] == 1
    out = vrr.run_glob(str(d))
    assert out["verdict"] == "OK" and out["chains_without_requests_seen_n"] == 1
    assert vrr.exit_code(out) == vrr.EXIT_OK


def test_one_void_cell_poisons_the_batch_verdict(tmp_path, upstream, monkeypatch):
    """**總判要反映它**：一批裡有一格零請求 ⇒ 總判不准是乾淨的 OK。"""
    monkeypatch.setenv("VACANT_RUN_UPSTREAM_OPENAI", upstream)
    batch = tmp_path / "batch"
    batch.mkdir()
    for name, src, tid in (("real", _ONE_REQUEST_AGENT, "ok_cell"),
                           ("fake", _NO_REQUEST_DELIVER, "void_cell")):
        ws, agent, suite = _scaffold(tmp_path, name, src)
        launcher.run([sys.executable, str(agent)], workspace=ws,
                     run_dir=batch / name, suite_dir=suite, vacant_on=True,
                     task_id=tid, sandbox_name="none")
    out = vrr.run_glob(str(batch / "*"))
    assert out["chains_n"] == 2
    assert out["mediated_chains_n"] == 1 and out["unmediated_chains_n"] == 1
    assert out["verdict"] == "VOID"
    assert out["unmediated_task_ids"] == ["void_cell"]
    # 畫面上要指得出是哪一格，不是只給一個總字
    assert "void_cell" in vrr.render(out)


def test_selftest_carries_the_negative_control(monkeypatch):
    """`--selftest` 的負控制**自己要能失敗**，否則它只是一段註解。

    作法：把中介維度整個打成「永遠是 True」，selftest 必須當場紅。
    這是對負控制的負控制——沒有它，H／I／J 三條可能只是恆真式。
    """
    r = subprocess.run([sys.executable, "-m", "vacant_network.vrun.verify_receipts",
                        "--selftest"], cwd=str(ROOT), capture_output=True,
                       text=True, timeout=300)
    assert r.returncode == 0 and "PASS" in r.stdout, r.stdout[-800:]

    monkeypatch.setattr(vrr, "mediation_of", lambda verdicts: {
        "mediated": True, "void_reason": None,
        "verdicts_with_requests_seen": len(verdicts),
        "verdicts_without_requests_seen": 0, "requests_seen_total": 1,
        "unmediated_task_ids": [], "ungated_task_ids": []})
    assert vrr.selftest() == 1, "尺瞎掉了而 selftest 還是 PASS——那它沒在量東西"
