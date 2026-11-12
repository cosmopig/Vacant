#!/usr/bin/env python3
"""e015 現盤 VERDICT.json 損傷哨兵（r1528、票 P20261112_1930-1 重拆件）。

事實：/srv/vlab/runs/e015_h_multi_review/VERDICT.json 於 2026-11-12 被發現尾部損傷
（前 89598B 與 repo 正典快照逐位元組相同；其後缺 `],` 閉合、殘留 "hypotheses" 鍵與
截斷 "usage" 片段，JSONDecodeError line 1780 column 7）。正典＝repo 內快照
ops/audits/e015_h_multi_review_verdict.json（sha256 d0e29884…，已由
e015_closure_check.py＋e015 裁決管線獨立重算機械複核、r1512 驗收）。

哨兵判準（現盤在位時）：必須可解析為 JSON，且與釘住快照逐位元組相同。
現盤缺位＝UNKNOWN（rc=2）——看不到≠PASS、也≠「沒有」。
唯讀；0 model calls；純 stdlib；CI-home 兼容（selftest 不依賴 /srv/vlab 與 Path.home()）。

rc：0＝現盤與正典相符；1＝VIOLATION（損傷/漂移）；2＝UNKNOWN（現盤缺位）。
"""
import argparse
import hashlib
import json
import pathlib
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
SNAP_DEFAULT = REPO / "ops/audits/e015_h_multi_review_verdict.json"
SNAP_SHA256 = "d0e2988411ad3aeaf55c044e4e7272ce1bcdf055ed5b2d7c358769cb4d7c2fb9"
LIVE_DEFAULT = pathlib.Path("/srv/vlab/runs/e015_h_multi_review/VERDICT.json")


def check(live_p: pathlib.Path, snap_p: pathlib.Path) -> tuple[int, list[str]]:
    """回傳 (rc, 違規清單)。rc=0 相符；1 違規；2 UNKNOWN（現盤缺位）。"""
    if not live_p.is_file():
        return 2, [f"UNKNOWN: 現盤缺位 {live_p}（看不到≠PASS、也≠沒有）"]
    if not snap_p.is_file():
        return 1, [f"正典快照缺位 {snap_p}"]
    snap = snap_p.read_bytes()
    if hashlib.sha256(snap).hexdigest() != SNAP_SHA256:
        return 1, ["正典快照 sha256 drift（非釘住 d0e29884…）"]
    live = live_p.read_bytes()
    out = []
    try:
        json.loads(live.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        out.append(f"現盤無法解析為 JSON: {e}")
    if live != snap:
        n = min(len(live), len(snap))
        i = next((k for k in range(n) if live[k] != snap[k]), n)
        out.append(f"現盤與正典快照非逐位元組相同（首差 byte {i}；"
                   f"live {len(live)}B vs snap {len(snap)}B）")
    return (1 if out else 0), out


def selftest(snap_p: pathlib.Path) -> int:
    if not snap_p.is_file():
        print(f"SELFTEST missing canonical snapshot: {snap_p}")
        return 1
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        snap = snap_p.read_bytes()
        # 正控制：正典副本必過
        good = td / "VERDICT_good.json"
        good.write_bytes(snap)
        rc, v = check(good, snap_p)
        if rc != 0 or v:
            print("SELFTEST positive control FAIL", rc, v)
            return 1
        # 負控制 n1：本輪實損傷同型（缺 ], 閉合＋殘尾、解析必炸）必紅
        cut = snap.rfind(b"  ],")
        bad1 = td / "VERDICT_bad_tail.json"
        bad1.write_bytes(snap[:cut] + b'\n    "hypotheses": "t",\n'
                          b'    "usage": [\n      {\n        "cell": "c1",\n}')
        rc, v = check(bad1, snap_p)
        if rc != 1 or not any("無法解析" in s for s in v):
            print("SELFTEST negative control FAIL [n1 損傷殘尾]:", rc, v)
            return 1
        # 負控制 n2：合法 JSON 但數值篡改（X 15→14）必紅（位元組不同）
        bad2 = td / "VERDICT_tamper.json"
        bad2.write_bytes(snap.replace(b'"X": 15', b'"X": 14', 1))
        rc, v = check(bad2, snap_p)
        if rc != 1 or not any("非逐位元組相同" in s for s in v):
            print("SELFTEST negative control FAIL [n2 數值篡改]:", rc, v)
            return 1
        # 負控制 n3：現盤缺位必 UNKNOWN（rc=2、不判 PASS）
        rc, v = check(td / "absent.json", snap_p)
        if rc != 2 or not any("UNKNOWN" in s for s in v):
            print("SELFTEST negative control FAIL [n3 缺位 UNKNOWN]:", rc, v)
            return 1
    print("VERDICT: E015_LIVE_VERDICT_OK")
    print("  positive＋n1 損傷殘尾＋n2 數值篡改＋n3 缺位 UNKNOWN 全生效")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋3 負控制（暫態檔、不碰現盤）")
    ap.add_argument("--live", type=pathlib.Path, default=LIVE_DEFAULT)
    ap.add_argument("--snap", type=pathlib.Path, default=SNAP_DEFAULT)
    a = ap.parse_args()
    if a.selftest:
        return selftest(a.snap)
    rc, v = check(a.live, a.snap)
    if rc == 2:
        print(*v, sep="\n")
        return 2
    if rc == 1:
        print(*("VIOLATION: " + s for s in v), sep="\n")
        return 1
    print("E015_LIVE_VERDICT: 0 違規（現盤可解析為 JSON 且與正典快照 d0e29884… 逐位元組相同）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
