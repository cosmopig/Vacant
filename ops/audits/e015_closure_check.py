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

r1530（票 vq-el4.105）：閉環檢查預設含 live 現盤（r1528 盲區：快照綠但 live 損傷須另跑
  e015_live_verdict_check.py 才看得到）——plain 模式預設併入 live 哨兵：live 相符→OK 行；
  live 損傷/漂移→VIOLATION rc=1；live 缺位→UNKNOWN rc=2（看不到≠PASS、也≠「沒有」）。
  --live 可覆寫；selftest 增 live 整合正/負控制（暫態檔、不碰現盤）。
"""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
VERDICT_DEFAULT = REPO / "ops/audits/e015_h_multi_review_verdict.json"
VERDICT_SHA256 = "d0e2988411ad3aeaf55c044e4e7272ce1bcdf055ed5b2d7c358769cb4d7c2fb9"
PACKET_DEFAULT = REPO / "ops/vlab/packets/e015_h_multi_review.md"
BACKLOG_DEFAULT = REPO / "ops/BACKLOG.md"
BACKLOG_LINE_SHA256 = "a2829e9ca73c5a3e52de96154c0b6a19903a6bfc2c46257e056ef378633fc80f"
PIPELINE_DEFAULT = pathlib.Path("/home/user1/dev/ops/audits/e015_verdict_pipeline.py")
PIPELINE_SHA256 = "fe94c68923eda6435c0f4a675627a3ccb0f0cd5425405d569a28cd756e1cee32"
QUEUE_DEFAULT = pathlib.Path("/home/user1/dev/ops/staging/15_e015_h_multi_review.json")
RUNS_ROOT = pathlib.Path("/srv/vlab/runs")
EXP = "e015_h_multi_review"
LIVE_MOD_DEFAULT = REPO / "ops/audits/e015_live_verdict_check.py"
LIVE_DEFAULT = pathlib.Path("/srv/vlab/runs/e015_h_multi_review/VERDICT.json")

CLOSURE_NOTE = ("**結案（round 900、2026-11-12、票 P20261112_1136-1）**：e015 現盤完賽產物機械複核全過"
                "（VERDICT.json：state=NOT_BETTER_THAN_RANDOM、X=15、n_bad=16、Y=7、n_good=15、missing=1、32 格；"
                "e015 裁決管線（sha256 fe94c689…）獨立重算與現盤 VERDICT.json 逐項相符、selftest 12 項綠；packet 非空）；"
                "判定結果：H1 未成立（NOT_BETTER_THAN_RANDOM、H-multi-review 被否於機制層）、Phase 2 不發射；"
                "裁決（r1508）：本行舊註記與現盤 VERDICT.json 相符（機械逐項比對）、票內「不符」主張不成立。")


def _live_mod():
    """載入同目錄 live 哨兵（同 e013 載 envelope_compliance 之 importlib 接法；不 pin sha——
    量具在 repo 內、有自己的 selftest 與測試、三分支同步紀律同本檔）。"""
    spec = importlib.util.spec_from_file_location("e015_live_verdict_check", LIVE_MOD_DEFAULT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def live_section(live_p: pathlib.Path, snap_p: pathlib.Path) -> tuple[int, list[str]]:
    """預設含 live 現盤（r1530）：回 (rc, 行)。0＝live 與正典相符；1＝live 違規（損傷/漂移）；
    2＝UNKNOWN（live 缺位、看不到≠PASS、也≠「沒有」）。"""
    rc, v = _live_mod().check(live_p, snap_p)
    if rc == 0:
        return 0, ["live: 現盤與正典快照逐位元組相同"]
    if rc == 2:
        return 2, [f"UNKNOWN: live 現盤缺位 {live_p}（看不到≠PASS、也≠『沒有』）"]
    return 1, ["VIOLATION(live): " + s for s in v]


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
    """回傳違規清單；空列表＝全部判準成立。"""
    out = []
    try:
        d = json.loads(verdict_text)
    except json.JSONDecodeError:
        return ["VERDICT.json 無法解析為 JSON"]
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
    elif hashlib.sha256(m.group(0).encode("utf-8")).hexdigest() != BACKLOG_LINE_SHA256:
        out.append("BACKLOG e015 目標行 sha256 漂移")
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
    if verdict_p == VERDICT_DEFAULT and hashlib.sha256(verdict_p.read_bytes()).hexdigest() != VERDICT_SHA256:
        v.append("VERDICT 快照 sha256 drift")
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
    # live 整合控制（r1530：閉環檢查預設含 live；暫態檔、不碰現盤）
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        snap_b = verdict_p.read_bytes()
        cut = snap_b.rfind(b"  ],")
        good = td / "live_good.json"
        good.write_bytes(snap_b)
        rc, lines = live_section(good, verdict_p)
        if rc != 0 or not any("live" in s for s in lines):
            print("SELFTEST live 整合 FAIL [正控制]:", rc, lines)
            return 1
        bad = td / "live_bad.json"
        bad.write_bytes(snap_b[:cut] + b'\n  "tail": {\n')
        rc, lines = live_section(bad, verdict_p)
        if rc != 1 or not any("VIOLATION" in s for s in lines):
            print("SELFTEST live 整合 FAIL [n6 live 損傷]:", rc, lines)
            return 1
        rc, lines = live_section(td / "live_absent.json", verdict_p)
        if rc != 2 or not any("UNKNOWN" in s for s in lines):
            print("SELFTEST live 整合 FAIL [n7 live 缺位 UNKNOWN]:", rc, lines)
            return 1
    print("VERDICT: E015_CLOSURE_OK")
    print("  files:", verdict_p, packet_p, backlog_p, PIPELINE_DEFAULT, sep="\n  ")
    print("  live 整合：正控制＋n6 live 損傷＋n7 live 缺位 UNKNOWN 全生效")
    return 0


def plain(verdict_p: pathlib.Path, packet_p: pathlib.Path, backlog_p: pathlib.Path,
          live_p: pathlib.Path) -> tuple[int, list[str]]:
    """plain 閉環檢查（r1530：預設含 live）：回 (rc, 行)。
    rc=0 全過（含 live 相符）；1＝違規（快照違規或 live 損傷/漂移）；2＝UNKNOWN（live 缺位）。"""
    missing = [f"missing file {n}: {p}" for n, p in
               (("VERDICT.json", verdict_p), ("packet", packet_p), ("BACKLOG", backlog_p)) if not p.is_file()]
    if missing:
        return 1, missing
    v = check(verdict_p.read_text(encoding="utf-8"),
              packet_p.read_text(encoding="utf-8"),
              backlog_p.read_text(encoding="utf-8"),
              verdict_p)
    if verdict_p == VERDICT_DEFAULT and hashlib.sha256(verdict_p.read_bytes()).hexdigest() != VERDICT_SHA256:
        v.append("VERDICT 快照 sha256 drift")
    if v:
        return 1, ["VIOLATION: " + s for s in v]
    rc_live, lv = live_section(live_p, verdict_p)
    if rc_live == 1:
        return 1, lv
    if rc_live == 2:
        return 2, lv
    return 0, ["E015_CLOSURE: 0 違規（VERDICT.json 數字＋管線獨立重算＋管線 selftest＋packet＋BACKLOG 結案註記"
               "＋live 現盤與正典逐位元組相同 全過）"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋負控制自測（含 live 整合控制）")
    ap.add_argument("--verdict", type=pathlib.Path, default=VERDICT_DEFAULT)
    ap.add_argument("--packet", type=pathlib.Path, default=PACKET_DEFAULT)
    ap.add_argument("--backlog", type=pathlib.Path, default=BACKLOG_DEFAULT)
    ap.add_argument("--live", type=pathlib.Path, default=LIVE_DEFAULT,
                    help="live 現盤 VERDICT.json（r1530 閉環檢查預設含 live；缺位＝UNKNOWN rc=2）")
    args = ap.parse_args()
    if args.selftest:
        return selftest(args.verdict, args.packet, args.backlog)
    rc, lines = plain(args.verdict, args.packet, args.backlog, args.live)
    print(*lines, sep="\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
