#!/usr/bin/env python3
"""e005 OpenCode 五臂冒煙（A/C/H/M/S 各 1 格、預註冊）完賽結案機械複核（2026-11-12、票 P20261112_2131-2）。對齊 e013/e003 架構；唯讀；0 model calls。
複核對象：REPORT.json（cells_scored=5、infra=0、A/C/H/S 各 1/1 rate=1.0、M 0/1 rate=0.0 timeouts=1、
C 臂 vacant_sha bf1a9f1a…、A_vs_C pairs=1 p=1.0、A_vs_M pairs=1 A_only=1 p=1.0）＋envelope_compliance 封頂合規（C 臂 1 PASS/0 FAIL、home_bytes [79333,79333,79333]）
＋packet 標題＋BACKLOG 第 84 行結案記錄（-[x]＋e006 全盤發射前置＋e005 M 格 900s 逾時註記＋行 sha256 釘住）。
CI-home 兼容：路徑皆絕對系統路徑或 REPO 相對（REPO 自 __file__）、不依賴 Path.home()。"""
import argparse, hashlib, importlib.util, json, pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
RUNS_BASE = pathlib.Path("/srv/vlab/runs")
EXP = "e005_opencode_five_arm_smoke"
REPORT_DEFAULT = RUNS_BASE / EXP / "REPORT.json"

PACKET_DEFAULT = next((p for p in (REPO / "ops/vlab/packets/e005_opencode_five_arm_smoke.md", REPO.parent / "ops/vlab/packets/e005_opencode_five_arm_smoke.md",
                                   pathlib.Path("/home/user1/dev/ops/vlab/packets/e005_opencode_five_arm_smoke.md")) if p.is_file()),
                     REPO / "ops/vlab/packets/e005_opencode_five_arm_smoke.md")
BACKLOG_DEFAULT = REPO / "ops/BACKLOG.md"
ENV_TOOL = REPO / "ops/vlab/tools/envelope_compliance.py"

PER_ARM = {"A": (1, 1, 1.0), "C": (1, 1, 1.0), "H": (1, 1, 1.0), "M": (1, 0, 0.0), "S": (1, 1, 1.0)}  # n/pass/rate
TIMEOUTS_M = 1
VACANT_SHA_C = ["bf1a9f1afb211460b48611f8f28b1d9433985c4a"]
ENVELOPE_C_PASS_FAIL = (1, 0)
ENVELOPE_BYTES = [79333, 79333, 79333]  # C 臂 home_bytes_min_med_max
PAIRED = {"A_vs_C": (("pairs", 1), ("A_only", 0), ("C_only", 0), ("mcnemar_p_two_sided", 1.0)),
          "A_vs_M": (("pairs", 1), ("A_only", 1), ("M_only", 0), ("mcnemar_p_two_sided", 1.0))}
PACKET_TITLE = "# e005 研究包：OpenCode 五臂冒煙（A/C/H/M/S 各 1 格，預註冊）"
BACKLOG_KEY = "e006 全盤發射前置"
BACKLOG_NOTE = "e005 M 格 900s 逾時 agent_rc=124"
BACKLOG_LINE_NO = 84  # 票面釘住的人類記錄行號（1-based）
BACKLOG_LINE_SHA256 = "0db7714370bd26347a3b496cdd42b52ba510d06a64cfd019e128e21fe5902806"

def run_envelope(base: pathlib.Path) -> dict:
    """跑 envelope_compliance 量具（同 e003/e013 的 importlib 接法）；回 evaluate() 結果 dict。"""
    spec = importlib.util.spec_from_file_location("envelope_compliance", ENV_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    env, src = mod._load_envelope()
    return mod.evaluate(base, EXP, env, src)

def check(report_text: str, packet_text: str, backlog_text: str,
          base: pathlib.Path = RUNS_BASE) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out: list[str] = []
    try:
        d = json.loads(report_text)
    except json.JSONDecodeError:
        return ["REPORT.json 無法解析為 JSON"]
    if d.get("cells_scored") != 5 or len(d.get("infra") or []) != 0:
        out.append(f"REPORT cells_scored={d.get('cells_scored')!r}/infra={len(d.get('infra') or [])} != 5/0")
    for arm, want in PER_ARM.items():
        a = (d.get("per_arm") or {}).get(arm) or {}
        if (a.get("n"), a.get("pass"), a.get("rate")) != want:
            out.append(f"REPORT per_arm[{arm}] n/pass/rate={a.get('n')!r}/{a.get('pass')!r}/{a.get('rate')!r} != {want[0]}/{want[1]}/{want[2]}")
    m = (d.get("per_arm") or {}).get("M") or {}
    if m.get("timeouts") != TIMEOUTS_M:
        out.append(f"REPORT per_arm[M].timeouts={m.get('timeouts')!r} != {TIMEOUTS_M}")
    for pk, wants in PAIRED.items():
        pc = (d.get("paired") or {}).get(pk) or {}
        for key, want in wants:
            if pc.get(key) != want:
                out.append(f"REPORT {pk} {key}={pc.get(key)!r} != {want}")
    if ((d.get("per_arm") or {}).get("C") or {}).get("vacant_sha") != VACANT_SHA_C:
        out.append(f"REPORT per_arm[C].vacant_sha != {VACANT_SHA_C}")
    try:
        r = run_envelope(base)
        ec = (r.get("by_arm") or {}).get("C") or {}
        c = ec.get("counts") or {}
        if (c.get("PASS"), c.get("FAIL")) != ENVELOPE_C_PASS_FAIL:
            out.append(f"envelope C 臂 PASS/FAIL={c.get('PASS')!r}/{c.get('FAIL')!r} != {ENVELOPE_C_PASS_FAIL[0]}/{ENVELOPE_C_PASS_FAIL[1]}")
        if ec.get("home_bytes_min_med_max") != ENVELOPE_BYTES:
            out.append(f"envelope home_bytes_min_med_max={ec.get('home_bytes_min_med_max')!r} != {ENVELOPE_BYTES}")
    except (Exception, SystemExit) as e:
        out.append(f"envelope_compliance 量具不可執行: {e}")
    if not (packet_text or "").strip() or PACKET_TITLE not in packet_text:
        out.append(f"packet 缺或為空、缺標題 {PACKET_TITLE!r}: {PACKET_DEFAULT}")
    lines = backlog_text.splitlines()
    idx = BACKLOG_LINE_NO - 1
    found = lines[idx] if len(lines) > idx and BACKLOG_KEY in lines[idx] else next((l for l in lines if BACKLOG_KEY in l), None)
    if found is None:
        out.append(f"BACKLOG 找不到項: {BACKLOG_KEY!r}")
        return out
    if not found.lstrip().startswith("- [x]"):
        out.append(f"BACKLOG e005 收口項未勾選 [x]: {found.lstrip()[:60]}")
    if BACKLOG_NOTE not in found:
        out.append(f"BACKLOG e005 收口項缺收口註記（{BACKLOG_NOTE}）: {found.lstrip()[:60]}")
    if hashlib.sha256(found.encode("utf-8")).hexdigest() != BACKLOG_LINE_SHA256:
        out.append(f"BACKLOG e005 目標行 sha256 漂移（第 {BACKLOG_LINE_NO} 行釘住 {BACKLOG_LINE_SHA256[:12]}…、改動即紅）")
    return out

def _read_or_die(p: pathlib.Path, name: str):
    """缺檔印一欄乾淨訊息並回 None（不拋未捕獲異常）。"""
    if not p.is_file():
        print(f"missing file {name}: {p}")
        return None
    return p.read_text(encoding="utf-8")

def selftest(report_p: pathlib.Path, packet_p: pathlib.Path, backlog_p: pathlib.Path,
             base: pathlib.Path) -> int:
    report, packet, backlog = (_read_or_die(report_p, "REPORT.json"), _read_or_die(packet_p, "packet"), _read_or_die(backlog_p, "BACKLOG"))
    if None in (report, packet, backlog): return 1
    v = check(report, packet, backlog, base)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:", *v, sep="\n  "); return 1
    print("SELFTEST 正控制 OK（REPORT.json／envelope_compliance／packet／BACKLOG 第 84 行結案記錄 全過）")
    def run(tag, rr, pp, bb, must_hit) -> bool:  # 負控制須命中指定違規字串才算生效
        vv = check(rr, pp, bb, base)
        if not (vv and any(must_hit in s for s in vv)):
            print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
            return False
        return True
    ok = True  # 負控制（票面要求）：篡改 REPORT pass 數、篡改 M 臂 timeouts、取消勾選、刪 e005 註記 必紅
    ok &= run("n1 REPORT pass 數篡改", report.replace('"pass": 1', '"pass": 0', 1), packet, backlog, "per_arm[A]")
    ok &= run("n2 REPORT M 臂 timeouts 篡改", report.replace('"timeouts": 1', '"timeouts": 0', 1), packet, backlog, "per_arm[M]")
    ok &= run("n3 BACKLOG 取消勾選", report, packet, backlog.replace("- [x] e006 全盤發射前置", "- [ ] e006 全盤發射前置", 1), "未勾選 [x]")
    ok &= run("n4 BACKLOG e005 註記刪除", report, packet, backlog.replace(BACKLOG_NOTE, "", 1), "缺收口註記")
    if not ok: return 1
    print("VERDICT: E005_CLOSURE_OK")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋4 負控制自測")
    ap.add_argument("--report", type=pathlib.Path, default=REPORT_DEFAULT)
    ap.add_argument("--packet", type=pathlib.Path, default=PACKET_DEFAULT)
    ap.add_argument("--backlog", type=pathlib.Path, default=BACKLOG_DEFAULT)
    args = ap.parse_args()
    if args.selftest:
        return selftest(args.report, args.packet, args.backlog, RUNS_BASE)
    report, packet, backlog = (_read_or_die(args.report, "REPORT.json"), _read_or_die(args.packet, "packet"), _read_or_die(args.backlog, "BACKLOG"))
    if None in (report, packet, backlog): return 1
    v = check(report, packet, backlog)
    print("\n".join(f"VIOLATION: {s}" for s in v), end="")
    return 1 if v else 0

if __name__ == "__main__":
    raise SystemExit(main())
