#!/usr/bin/env python3
"""B54 對帳的合成測試（決策方 2026-11-28 要求）：同頁帶 query ⇒ 相等；多出伺服器沒有的 path ⇒ 紀錄不可信。
在暫存目錄造一個最小 run root（access.jsonl、一格一輪的 run.json、final/vh 的 egress.jsonl），不讀任何真實紀錄。
用法：expT_b54_test.py OUT.json"""
import json, pathlib, sys, tempfile
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.d2 import expTc_b54 as B54  # noqa: E402

HOST = "xx-s01-r1.d2-sources.example"


def make(tmp: pathlib.Path, egress_urls: list, server_paths: list) -> pathlib.Path:
    root = tmp / "root"; arm = root / "cells" / "xx-s01" / "r1" / "T"
    run = arm / "round_1" / "run"; run.mkdir(parents=True)
    (run / "run.json").write_text(json.dumps({"t_start": 1000.0, "t_end": 1100.0}))
    pj = arm / "final" / "vh" / "trace" / "projects" / "p"; pj.mkdir(parents=True)
    (pj / "egress.jsonl").write_text("".join(json.dumps({"ts_ms": 1050000, "url": u, "method": "GET", "status": 200}) + "\n" for u in egress_urls))
    (root / "access.jsonl").write_text("".join(json.dumps({"ts": 1050.0, "host": HOST, "path": p, "status": 200}) + "\n" for p in server_paths))
    return root


CASES = [
    ("same_page_with_query_equal", [f"http://{HOST}/a.html?format=json", f"http://{HOST}/a.html"], ["/a.html"], "equal"),
    ("same_page_with_port80_equal", [f"http://{HOST}:80/a.html"], ["/a.html"], "equal"),
    ("extra_path_not_on_server_untrusted", [f"http://{HOST}/a.html", f"http://{HOST}/b.html"], ["/a.html"], "record_untrusted"),
    ("server_has_more_gauge_gap", [f"http://{HOST}/a.html"], ["/a.html", "/b.html"], "gauge_gap"),
]


def main() -> int:
    rows = []; ok_all = True
    for cid, eg, srv, exp in CASES:
        with tempfile.TemporaryDirectory() as t:
            r = B54.check_root(make(pathlib.Path(t), eg, srv))
        row = r["rows"][0]
        got = "record_untrusted" if row["record_untrusted"] else "gauge_gap" if row["gauge_gap"] else "equal" if row["equal"] else "?"
        ok = got == exp; ok_all &= ok
        rows.append({"case": cid, "expected": exp, "got": got, "pass": ok})
        print(("PASS " if ok else "FAIL ") + f"{cid:38s} exp={exp} got={got}")
    pathlib.Path(sys.argv[1]).write_text(json.dumps({"all_pass": ok_all, "cases": rows}, indent=1))
    print("ALL PASS" if ok_all else "NOT ALL PASS"); return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
