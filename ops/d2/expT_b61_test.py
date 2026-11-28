#!/usr/bin/env python3
"""B61 合成測試：伺服器沒在跑 ⇒ 基礎設施；伺服器在跑、請求被白名單擋 ⇒ 模型行為；用錯埠／協定（被擋）⇒ 模型行為；
伺服器在跑、沒有被擋紀錄、對本格 0 筆（窗內有別格成功）⇒ 模型行為（伺服器有回應）。用法：expT_b61_test.py OUT.json"""
import json, pathlib, sys, tempfile
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.d2 import expTc_confirm_analysis as A  # noqa: E402
HOST = "xx-s01-r1.d2-sources.example"
def blk(tmp, rows):
    p = pathlib.Path(tmp) / "net_blocked.jsonl"; p.write_text("".join(json.dumps(r) + "\n" for r in rows)); return p
CASES = [
    ("server_down_no_records", [], [], True),
    ("server_up_request_blocked_https443", [{"ts": 1050.0, "host": "yy-s02-r1.d2-sources.example", "status": 200}],
     [{"ts": 1040.0, "blocked": True, "reason": "host_not_allowed", "host": HOST, "port": 443, "method": "CONNECT"}], False),
    ("wrong_port_blocked_server_down_otherwise", [], [{"ts": 1040.0, "blocked": True, "reason": "host_not_allowed", "host": f"{HOST}:8080", "port": 8080}], False),
    ("server_up_other_cells_only_no_block", [{"ts": 1090.0, "host": "yy-s02-r1.d2-sources.example", "status": 200}], [], False),
    ("other_cell_success_outside_60s", [{"ts": 1300.0, "host": "yy-s02-r1.d2-sources.example", "status": 200}], [], True),
]
rows = []; ok_all = True
for cid, acc, blocked, exp in CASES:
    with tempfile.TemporaryDirectory() as t:
        got = A.b61_server_unresponsive(acc, 1000.0, 1100.0, blk(t, blocked), HOST)
    ok = got == exp; ok_all &= ok
    rows.append({"case": cid, "expected_server_unresponsive": exp, "got": got, "pass": ok})
    print(("PASS " if ok else "FAIL ") + f"{cid:42s} exp_infra_possible={exp} got={got}")
pathlib.Path(sys.argv[1]).write_text(json.dumps({"all_pass": ok_all, "cases": rows}, indent=1))
print("ALL PASS" if ok_all else "NOT ALL PASS"); sys.exit(0 if ok_all else 1)
