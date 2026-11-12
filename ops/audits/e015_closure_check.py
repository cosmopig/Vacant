#!/usr/bin/env python3
"""e015 H-multi-review 裁決者校準實驗結案機械複核（round 900、票 P20261112_1136-1）。
2026-11-11 人類常設定案第 2.b 條：一小片一張票、驗收綁可機械複核的量。
完賽產物：VERDICT.json（state=NOT_BETTER_THAN_RANDOM、X=15、n_bad=16、Y=7、n_good=15、missing=1、32 行）
＋ e015 裁決管線（預註冊狀態表獨立重算）＋packet 非空＋BACKLOG 活檔 e015 項結案註記。
唯讀；0 model calls。
CI-home 兼容：缺省路徑皆絕對系統路徑或 repo 相對（REPO 自 __file__）、不依賴 Path.home()。
repo 內 ops/BACKLOG.md 是 e015 釘住（sha256）之凍結快照、本票不碰、結案只記活檔。

r1508 修正（planner 代修；裁決與驗收記錄見票內 r1508 註記）：
  1) 量具接線：舊版把 VERDICT.json 內容傳給 e004 量具（e004 量具期待含 paired 區塊之
     REPORT.json，VERDICT.json 無 paired、必拋「REPORT.json 缺 paired 區塊」）——e015 本無
     e004 式假說量具（H-acc/H-review/H-stakes 系列是 e004/e006 的量具；e015 的預註冊假說
     是 H0/H1、狀態表即其量具）。改用 e015 專用管線（e015_verdict_pipeline.py、
     sha256 釘住 fe94c689…、selftest 12 項綠）：自 32 格 receipts 重算
     state/X/Y/n_bad/n_good/missing、與現盤 VERDICT.json 逐項對齊（現盤裁決可由
     receipts 導出、非憑空記入）。
  2) 舊註記裁決：活檔 line 25–26 舊註記與現盤 VERDICT.json 逐項相符（X=15/16、Y=7/15、
     缺 1/32＝dab_057 UNPARSED 43 calls/114k tok、Holm first 達/second 不達、state、
     Phase 2 不發射）；票內「不符」主張不成立（r1508 機械比對）；結案註記以本裁決為準。
"""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

VERDICT_DEFAULT = pathlib.Path("/srv/vlab/runs/e015_h_multi_review/VERDICT.json")
REPO = pathlib.Path(__file__).resolve().parents[2]
PACKET_DEFAULT = REPO / "ops/vlab/packets/e015_h_multi_review.md"
BACKLOG_DEFAULT = pathlib.Path("/home/user1/dev/ops/BACKLOG.md")
PIPELINE_DEFAULT = pathlib.Path("/home/user1/dev/ops/audits/e015_verdict_pipeline.py")
PIPELINE_SHA256 = "fe94c68923eda6435c0f4a675627a3ccb0f0cd5425405d569a28cd756e1cee32"
QUEUE_DEFAULT = pathlib.Path("/home/user1/dev/ops/staging/15_e015_h_multi_review.json")
RUNS_ROOT = pathlib.Path("/srv/vlab/runs")
EXP = "e015_h_multi_review"

CLOSURE_NOTE = ("**結案（round 900、2026-11-12、票 P20261112_1136-1）**：e015 現盤完賽產物機械複核全過"
                "（VERDICT.json：state=NOT_BETTER_THAN_RANDOM、X=15、n_bad=16、Y=7、n_good=15、missing=1、32 格；"
                "e015 裁決管線（sha256 fe94c689…）獨立重算與現盤 VERDICT.json 逐項相符、selftest 12 項綠；packet 非空）；"
                "判定結果：H1 未成立（NOT_BETTER_THAN_RANDOM、H-multi-review 被否於機制層）、Phase 2 不發射；"
                "裁決（r1508）：本行舊註記與現盤 VERDICT.json 相符（機械逐項比對）、票內「不符」主張不成立。")


def recompute_from_receipts() -> dict:
    """e015 專用管線（sha256 釘住）：自 32 格 receipts 逐格重算預註冊狀態表。
    唯讀（check_cell＋decide、不寫 VERDICT.json）。量具缺/漂移、receipts 未齊皆拋例外。"""
    pipe = PIPELINE_DEFAULT
    if hashlib.sha256(pipe.read_bytes()).hexdigest() != PIPELINE_SHA256:
        raise RuntimeError("裁決管線 sha256 drift（非釘住 fe94c689… 之量具）")
    spec = importlib.util.spec_from_file_location("e015_verdict_pipeline", pipe)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    job = json.loads(QUEUE_DEFAULT.read_text(encoding="utf-8"))
    rows = []
    for c in job["cells"]:
        outdir = RUNS_ROOT / EXP / "reviewer" / pathlib.Path(c["cell_src"]).name
        chk = mod.check_cell(outdir)
        chk["cell"] = c["cell_src"]
        chk["truth"] = c["truth"]
        rows.append(chk)
    if any(r["why"] == "no_receipt" for r in rows):
        raise RuntimeError("receipts 未齊（有格 no_receipt）、不能結案")
    return mod.decide([r for r in rows if r["truth"] == "GOOD"],
                      [r for r in rows if r["truth"] == "BAD"])


def check(verdict_text: str, packet_text: str, backlog_text: str,
          report_p: pathlib.Path = VERDICT_DEFAULT) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。
    （report_p 為對齊舊簽名之兼容參數、現不直接使用。）"""
    out = []
    d = json.loads(verdict_text)
    if d.get("state") != "NOT_BETTER_THAN_RANDOM":
        out.append(f"VERDICT state={d.get('state')} != NOT_BETTER_THAN_RANDOM")
    for key, want in (("X", 15), ("n_bad", 16), ("Y", 7), ("n_good", 15), ("missing", 1)):
        if d.get(key) != want:
            out.append(f"VERDICT {key}={d.get(key)} != {want}")
    if len(d.get("rows") or []) != 32:
        out.append(f"VERDICT rows count={len(d.get('rows') or [])} != 32")
    if len(d.get("missing_cells") or []) != 1:
        out.append(f"VERDICT missing_cells count={len(d.get('missing_cells') or [])} != 1")
    # e015 裁決管線：selftest（12 項）＋獨立重算與現盤 VERDICT.json 逐項對齊
    st = subprocess.run([sys.executable, str(PIPELINE_DEFAULT), "--selftest"],
                        capture_output=True, text=True, timeout=120)
    if st.returncode != 0:
        out.append(f"e015 裁決管線 selftest 不綠（rc={st.returncode}）")
    else:
        try:
            r = recompute_from_receipts()
            for key in ("state", "X", "Y", "n_bad", "n_good", "missing"):
                if d.get(key) != r.get(key):
                    out.append(f"重算 {key}={d.get(key)} != 管線重算 {r.get(key)}")
        except Exception as e:
            out.append(f"e015 裁決管線不可執行: {e}")
    if not packet_text.strip():
        out.append("packet 缺或為空")
    m = re.search(r"^\s*-\s*\[([ xX])\]\s*\*\*發射 Phase 1（round 900[^*]*\*\*(.*)$", backlog_text, re.M)
    if not m:
        out.append("BACKLOG 未找到 e015 項")
    elif m.group(1) != "x":
        out.append("BACKLOG e015 項未勾選 [x]")
    elif CLOSURE_NOTE not in m.group(2):
        out.append("BACKLOG e015 項缺結案註記（日期＋輪次＋票號＋判定結果）")
    return out


def selftest(verdict_p: pathlib.Path = VERDICT_DEFAULT,
             packet_p: pathlib.Path = PACKET_DEFAULT,
             backlog_p: pathlib.Path = BACKLOG_DEFAULT) -> int:
    missing = [f"SELFTEST missing file {n}: {p}" for n, p in
               (("VERDICT.json", verdict_p), ("packet", packet_p), ("BACKLOG", backlog_p),
                ("裁決管線", PIPELINE_DEFAULT), ("發射 queue", QUEUE_DEFAULT)) if not p.is_file()]
    if missing:
        print(*missing, sep="\n")
        return 1
    v_text = verdict_p.read_text(encoding="utf-8")
    p_text = packet_p.read_text(encoding="utf-8")
    b_text = backlog_p.read_text(encoding="utf-8")
    v = check(v_text, p_text, b_text, verdict_p)
    if v:
        print("SELFTEST positive control FAIL:", *v, sep="\n  ")
        return 1
    print("SELFTEST positive control OK（VERDICT.json 數字＋管線獨立重算＋管線 selftest＋packet＋BACKLOG 結案註記 全過）")

    def run(tag: str, verdict: str, packet: str, backlog: str, must_hit: str) -> bool:
        vv = check(verdict, packet, backlog, verdict_p)
        if not vv or not any(must_hit in s for s in vv):
            print(f"SELFTEST negative control FAIL [{tag}]: violations={vv} (應含 {must_hit!r})")
            return False
        return True

    ok = True
    ok &= run("n1 state 篡改", v_text.replace('"state": "NOT_BETTER_THAN_RANDOM"', '"state": "EFFECTIVE"', 1),
              p_text, b_text, "state=EFFECTIVE != NOT_BETTER_THAN_RANDOM")
    ok &= run("n2 Y 篡改", v_text.replace('"Y": 7', '"Y": 13', 1), p_text, b_text, "Y=13 != 7")
    ok &= run("n3 BACKLOG 未勾選", v_text, p_text,
              b_text.replace("- [x] **發射 Phase 1", "- [ ] **發射 Phase 1", 1), "未勾選 [x]")
    ok &= run("n4 結案註記刪除", v_text, p_text, b_text.replace(CLOSURE_NOTE, "", 1), "缺結案註記")
    import tempfile
    with tempfile.TemporaryDirectory() as td:  # n5 量具漂移：暫態檔、不碰正典
        bad = pathlib.Path(td) / "pipeline_tampered.py"
        bad.write_text(PIPELINE_DEFAULT.read_text(encoding="utf-8") + "\n# tamper\n", encoding="utf-8")
        saved = PIPELINE_DEFAULT
        globals()["PIPELINE_DEFAULT"] = bad
        try:
            vv = check(v_text, p_text, b_text, verdict_p)
            if not any("sha256 drift" in s for s in vv):
                print(f"SELFTEST negative control FAIL [n5 量具漂移]: violations={vv!r} (應含 'sha256 drift')")
                ok = False
        finally:
            globals()["PIPELINE_DEFAULT"] = saved
    if not ok:
        return 1
    print("VERDICT: E015_CLOSURE_OK")
    print("  files:", verdict_p, packet_p, backlog_p, PIPELINE_DEFAULT, sep="\n  ")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋負控制自測")
    ap.add_argument("--verdict", type=pathlib.Path, default=VERDICT_DEFAULT)
    ap.add_argument("--packet", type=pathlib.Path, default=PACKET_DEFAULT)
    ap.add_argument("--backlog", type=pathlib.Path, default=BACKLOG_DEFAULT)
    args = ap.parse_args()
    if args.selftest:
        return selftest(args.verdict, args.packet, args.backlog)
    v = check(args.verdict.read_text(encoding="utf-8"),
              args.packet.read_text(encoding="utf-8"),
              args.backlog.read_text(encoding="utf-8"),
              args.verdict)
    if v:
        print(*("VIOLATION: " + s for s in v), sep="\n")
        return 1
    print("E015_CLOSURE: 0 違規（VERDICT.json 數字＋管線獨立重算＋管線 selftest＋packet＋BACKLOG 結案註記 全過）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
