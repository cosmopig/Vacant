#!/usr/bin/env python3
"""這支在架構裡承重什麼：`vacant run` 的**零模型呼叫證明**，標準庫直跑。

vacant-dev 上沒有 venv、沒有 pip、沒有 pytest（R530 §三-2 實測），
所以「兩臂 body 逐位元相同」這條證據不能只活在 `tests/test_vacant_run.py` 裡。
本檔把同一批斷言做成一支 `/usr/bin/python3` 就跑得起來的腳本，
並且**把數字印出來**——證據是那兩個 sha256，不是一句 PASS。

四段，依序對應四條要被證明的性質：

  A. OFF（tee）與 ON（act）送出去的 request body **逐位元相同**
  B. 拒交路徑：驗收沒過 ⇒ 退出碼非 0 ⇒ 收據記 `accepted=false`
  C. 交付路徑：驗收過 ⇒ 退出碼 0
  D. 收據被**既有的** `ops/gain/replay/verify_run_receipts.py` 驗過

用法：
    python3 ops/vacantrun/selftest.py            # 印證據，全過回 0
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.gain.replay import verify_run_receipts as vrr           # noqa: E402
from ops.vacantrun import launcher                               # noqa: E402

#: key 順序刻意不是字典序、空白刻意不規則——任何一次 loads→dumps 都會抹平它們。
BODY = (b'{"model":"m","stream":false,  "messages":[{"role":"user",'
        b'"content":"hi"}],"zz_last":1,"aa_first":2}')

AGENT = '''
import os, sys, urllib.request
req = urllib.request.Request(
    os.environ["OPENAI_BASE_URL"].rstrip("/") + "/chat/completions",
    data=%r, method="POST")
req.add_header("Content-Type", "application/json")
with urllib.request.urlopen(req, timeout=30) as r:
    r.read()
if sys.argv[1] == "good":
    open("solution.py", "w").write("def add(a, b):\\n    return a + b\\n")
elif sys.argv[1] == "bad":
    open("solution.py", "w").write("def add(a, b):\\n    return a - b\\n")
''' % BODY

SUITE = "def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n"


class _Up(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen: list[bytes] = []

    def log_message(self, *a):
        return

    def do_POST(self):                                   # noqa: N802
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        type(self).seen.append(raw)
        out = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


def main() -> int:
    fails: list[str] = []

    def ck(label: str, cond: bool, extra: str = "") -> None:
        print(f"  {'OK  ' if cond else 'FAIL'} {label}" + (f"  {extra}" if extra else ""))
        if not cond:
            fails.append(label)

    _Up.seen = []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Up)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1},
                     daemon=True).start()
    import os
    os.environ["OPENAI_BASE_URL"] = f"http://127.0.0.1:{srv.server_address[1]}/v1"

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="vacantrun_selftest_"))
    try:
        agent_py = tmp / "agent.py"
        agent_py.write_text(AGENT, encoding="utf-8")
        suite = tmp / "visible"
        suite.mkdir()
        (suite / "test_visible.py").write_text(SUITE, encoding="utf-8")
        run_dir = tmp / "run"

        # ── A. 兩臂 body 逐位元相同 ──────────────────────────────────
        print("\n[A] VACANT=0（tee）vs VACANT=1（act）：request body 必須逐位元相同")
        shas: dict[str, tuple[str, bytes]] = {}
        for on in (False, True):
            arm = launcher.ARM_ON if on else launcher.ARM_OFF
            ws = tmp / f"ws_{arm}"
            ws.mkdir()
            (ws / "README.md").write_text("task\n", encoding="utf-8")
            s = launcher.run([sys.executable, str(agent_py), "good"],
                             workspace=ws, run_dir=run_dir, suite_dir=suite,
                             vacant_on=on, task_id=f"byte_{arm}",
                             sandbox_name="none")
            idx = [json.loads(x) for x in
                   (run_dir / f"wire_{arm}" / "index.jsonl")
                   .read_text(encoding="utf-8").splitlines() if x]
            raw = (run_dir / f"wire_{arm}" /
                   f"{idx[0]['call_id']}.req.bin").read_bytes()
            shas[arm] = (idx[0]["request_sha256"], raw)
            print(f"      {arm:8} mode={idx[0]['mode']:4} "
                  f"body_sha256={idx[0]['request_sha256']}  "
                  f"bytes={idx[0]['request_bytes']}  stop={s['stop_reason']}")
        off, on_ = shas[launcher.ARM_OFF], shas[launcher.ARM_ON]
        print(f"      期望            body_sha256={hashlib.sha256(BODY).hexdigest()}")
        ck("A1_sha256_identical", off[0] == on_[0], f"{off[0][:16]}… == {on_[0][:16]}…")
        ck("A2_raw_bytes_identical", off[1] == on_[1] == BODY)
        ck("A3_upstream_received_the_same_bytes",
           _Up.seen[:2] == [BODY, BODY])

        # ── B. 拒交路徑 ──────────────────────────────────────────────
        print("\n[B] 驗收沒過 ⇒ 退出碼非 0 ⇒ 收據記 refused")
        ws = tmp / "ws_bad"
        ws.mkdir()
        (ws / "README.md").write_text("task\n", encoding="utf-8")
        bad = launcher.run([sys.executable, str(agent_py), "bad"],
                           workspace=ws, run_dir=tmp / "run_bad",
                           suite_dir=suite, vacant_on=True, task_id="refuse",
                           sandbox_name="none")
        rc = launcher.exit_code(bad)
        chain = json.loads((tmp / "run_bad" / "receipts_RUN-ON.ndjson")
                           .read_text(encoding="utf-8").splitlines()[-1])
        print(f"      stop_reason={bad['stop_reason']}  accepted={bad['accepted']}"
              f"  refused={bad['refused']}  exit_code={rc}")
        print(f"      visible={bad['visible_passed']}/{bad['visible_total']}"
              f"  verdict_sha256={(bad['verdict_sha256'] or '')[:16]}…")
        print(f"      收據 seq={chain['seq']} type={chain['type']} "
              f"accepted={chain['payload']['accepted']} "
              f"stop_reason={chain['payload']['stop_reason']}")
        ck("B1_exit_code_nonzero", rc == launcher.EXIT_REFUSED != 0, f"rc={rc}")
        ck("B2_receipt_says_refused",
           chain["type"] == "ws_verdict"
           and chain["payload"]["accepted"] is False
           and chain["payload"]["stop_reason"] == "visible_fail")

        # ── C. 交付路徑 ──────────────────────────────────────────────
        print("\n[C] 驗收過 ⇒ 退出碼 0")
        good = json.loads((run_dir / "run_RUN-ON.json").read_text(encoding="utf-8"))
        print(f"      stop_reason={good['stop_reason']}  accepted={good['accepted']}"
              f"  exit_code={launcher.exit_code(good)}  "
              f"ws {good['ws_start_sha256'][:12]}→{good['ws_end_sha256'][:12]}")
        ck("C1_accepted_exit_zero",
           good["accepted"] is True and launcher.exit_code(good) == 0)

        # ── D. 既有的那把尺 ─────────────────────────────────────────
        print("\n[D] 收據交給既有的 ops/gain/replay/verify_run_receipts.py")
        for d in (run_dir, tmp / "run_bad"):
            for rec in vrr.verify_run(d):
                print(f"      {d.name:9} arm={rec['arm']:8} entries={rec['entries_n']}"
                      f" verified={rec['verified_n']} verdict={rec['verdict']}"
                      f" head={(rec['head'] or '')[:16]}…")
                ck(f"D_{d.name}_{rec['arm']}_verdict_OK", rec["verdict"] == "OK",
                   json.dumps(rec["failures"], ensure_ascii=False)[:200])
    finally:
        srv.shutdown()
        srv.server_close()
        shutil.rmtree(tmp, ignore_errors=True)

    print("\nselftest: " + ("PASS" if not fails else f"{len(fails)} FAILED {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
