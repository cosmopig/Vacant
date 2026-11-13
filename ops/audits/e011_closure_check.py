#!/usr/bin/env python3
"""e011 DABench 冒煙（A/C 12 格配對、L001 預註冊）完賽結案機械複核（2026-11-13、票 R20261113_0041-1）。對齊 e007/e005 架構；唯讀；0 model calls。
複核對象：REPORT.json（cells_scored=12、infra=0、A 5/6 rate=0.8333、C 6/6 rate=1.0、vacant_sha f2b79012…、pairs=6/A_only=0/C_only=1/mcnemar_p=1.0）
＋envelope_compliance 封頂合規（C 臂 6 PASS/0 FAIL、home_bytes [27940,60363,93160]）＋loop/L001.md（### 6.3 e011 判定量具預驗證＋§3 C1–C4 判準）
＋BACKLOG 第 71 行跟進記錄（含 e009/e011 infra 格註記、行＋換行 sha256 釘住 e8a98f34…）。CI-home 兼容：路徑皆絕對系統路徑或 REPO 相對（REPO 自 __file__）、不依賴 Path.home()。"""
import argparse, hashlib, importlib.util, json, pathlib, shutil, tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
RUNS_BASE = pathlib.Path("/srv/vlab/runs")
EXP = "e011_l001_dabench_smoke"
REPORT_DEFAULT = RUNS_BASE / EXP / "REPORT.json"
LOOP_DOC_DEFAULT = next((p for p in (REPO / "loop/L001.md", REPO.parent / "ops/loop/L001.md",
                                     pathlib.Path("/home/user1/dev/ops/loop/L001.md")) if p.is_file()),
                        REPO / "loop/L001.md")
BACKLOG_DEFAULT = REPO / "ops/BACKLOG.md"
ENV_TOOL = REPO / "ops/vlab/tools/envelope_compliance.py"

PER_ARM = {"A": (6, 5, 0.8333, 46.2, 1035112, 1), "C": (6, 6, 1.0, 11.67, 100772, 0)}  # n/pass/rate/calls_per_success/tokens_per_success/timeouts
VACANT_SHA_C = ["f2b79012cfa98ff00453ffd69384e258188256d3"]
ENVELOPE_C_PASS_FAIL = (6, 0)
ENVELOPE_BYTES = [27940, 60363, 93160]  # C 臂 home_bytes_min_med_max
LOOP_TITLE = "### 6.3 e011 判定量具預驗證"
LOOP_CRITERIA = "C4 成本 sanity"  # §3 C1–C4 判準
BACKLOG_KEY = "e009/e011 完賽時數 infra 格＋原因"
BACKLOG_LINE_NO = 71
BACKLOG_LINE_SHA256 = "e8a98f343f1dbe8d3a39c0386e7e406a2cca29ff9becd3c14ac1374f70e03c19"  # 行＋行尾換行（票面口徑、r1537 先例）

def run_envelope(base: pathlib.Path) -> dict:
    """跑 envelope_compliance 量具（同 e007/e005 的 importlib 接法）；回 evaluate() 結果 dict。"""
    spec = importlib.util.spec_from_file_location("envelope_compliance", ENV_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    env, src = mod._load_envelope()
    return mod.evaluate(base, EXP, env, src)

def check(report_text: str, loop_text: str, backlog_text: str,
          base: pathlib.Path = RUNS_BASE) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out: list[str] = []
    try:
        d = json.loads(report_text)
    except json.JSONDecodeError:
        return ["REPORT.json 無法解析為 JSON"]
    if d.get("cells_scored") != 12 or len(d.get("infra") or []) != 0: out.append(f"REPORT cells_scored={d.get('cells_scored')!r}/infra={len(d.get('infra') or [])} != 12/0")
    for arm, want in PER_ARM.items():
        a = (d.get("per_arm") or {}).get(arm) or {}
        got = (a.get("n"), a.get("pass"), a.get("rate"), a.get("calls_per_success"), a.get("tokens_per_success"), a.get("timeouts"))
        if got != want: out.append(f"REPORT per_arm[{arm}] n/pass/rate/calls/tokens/timeouts={got} != {want}")
    pc = (d.get("paired") or {}).get("A_vs_C") or {}
    for key, want in (("pairs", 6), ("A_only", 0), ("C_only", 1), ("mcnemar_p_two_sided", 1.0)):
        if pc.get(key) != want: out.append(f"REPORT A_vs_C {key}={pc.get(key)!r} != {want}")
    if ((d.get("per_arm") or {}).get("C") or {}).get("vacant_sha") != VACANT_SHA_C: out.append(f"REPORT per_arm[C].vacant_sha != {VACANT_SHA_C}")
    try:
        r = run_envelope(base)
        ec = (r.get("by_arm") or {}).get("C") or {}
        c = ec.get("counts") or {}
        if (c.get("PASS"), c.get("FAIL")) != ENVELOPE_C_PASS_FAIL: out.append(f"envelope C 臂 PASS/FAIL={c.get('PASS')!r}/{c.get('FAIL')!r} != {ENVELOPE_C_PASS_FAIL[0]}/{ENVELOPE_C_PASS_FAIL[1]}")
        if ec.get("home_bytes_min_med_max") != ENVELOPE_BYTES: out.append(f"envelope home_bytes_min_med_max={ec.get('home_bytes_min_med_max')!r} != {ENVELOPE_BYTES}")
    except (Exception, SystemExit) as e:
        out.append(f"envelope_compliance 量具不可執行: {e}")
    if not (loop_text or "").strip() or LOOP_TITLE not in (loop_text or ""): out.append(f"loop/L001.md 缺或為空、缺標題 {LOOP_TITLE!r}: {LOOP_DOC_DEFAULT}")
    elif LOOP_CRITERIA not in loop_text: out.append(f"loop/L001.md 缺 §3 C1–C4 判準（{LOOP_CRITERIA}）")
    lines = backlog_text.splitlines()
    idx = BACKLOG_LINE_NO - 1
    found = lines[idx] if len(lines) > idx and BACKLOG_KEY in lines[idx] else next((l for l in lines if BACKLOG_KEY in l), None)
    if found is None:
        out.append(f"BACKLOG 缺跟進註記（{BACKLOG_KEY}）: {BACKLOG_DEFAULT}"); return out
    if hashlib.sha256((found + "\n").encode("utf-8")).hexdigest() != BACKLOG_LINE_SHA256:
        out.append(f"BACKLOG 第 {BACKLOG_LINE_NO} 行 sha256 漂移（釘住 {BACKLOG_LINE_SHA256[:12]}…、改動即紅）")
    return out

def tamper_envelope_base(tmp: pathlib.Path) -> pathlib.Path:
    """負控制輔助：複製真實 run 目錄（6.8M）至 tmp、第一格 C 的 vacant_home_bytes 改超封頂 → C 臂 5 PASS/1 FAIL。"""
    dst = tmp / EXP
    shutil.copytree(RUNS_BASE / EXP, dst)
    ccell = next(d for d in sorted(dst.iterdir()) if d.is_dir() and (d / "cell.json").is_file() and json.loads((d / "cell.json").read_text(encoding="utf-8")).get("arm") == "C")
    p = ccell / "cell.json"
    data = json.loads(p.read_text(encoding="utf-8")); data["vacant_home_bytes"] = 10 ** 12
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return tmp

def _read_or_die(p: pathlib.Path, name: str):
    """缺檔印一欄乾淨訊息並回 None（不拋未捕獲異常）。"""
    if not p.is_file():
        print(f"missing file {name}: {p}"); return None
    return p.read_text(encoding="utf-8")

def selftest(report_p: pathlib.Path, loop_p: pathlib.Path, backlog_p: pathlib.Path) -> int:
    report, loop, backlog = (_read_or_die(report_p, "REPORT.json"), _read_or_die(loop_p, "loop 文件"), _read_or_die(backlog_p, "BACKLOG"))
    if None in (report, loop, backlog): return 1
    v = check(report, loop, backlog)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:", *v, sep="\n  "); return 1
    print("SELFTEST 正控制 OK（REPORT.json／envelope_compliance／loop/L001.md／BACKLOG 第 71 行 全過）")
    def run(tag, rr, ll, bb, base, must_hit) -> bool:  # 負控制須命中指定違規字串才算生效
        vv = check(rr, ll, bb, base)
        if not (vv and any(must_hit in s for s in vv)):
            print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）"); return False
        return True
    ok = True  # 負控制（票面要求）：REPORT pass 數篡改／McNemar p 篡改／envelope C 臂 PASS 數篡改／BACKLOG 註記刪除 必紅
    with tempfile.TemporaryDirectory() as t:
        tmp = tamper_envelope_base(pathlib.Path(t))
        ok &= run("n1 REPORT pass 數篡改", report.replace('"pass": 5', '"pass": 4', 1), loop, backlog, RUNS_BASE, "per_arm[A]")
        ok &= run("n2 REPORT McNemar p 篡改", report.replace('"mcnemar_p_two_sided": 1.0', '"mcnemar_p_two_sided": 0.01', 1), loop, backlog, RUNS_BASE, "A_vs_C")
        ok &= run("n3 envelope C 臂 PASS 數篡改", report, loop, backlog, tmp, "envelope C 臂 PASS/FAIL")
        ok &= run("n4 BACKLOG 註記刪除", report, loop, backlog.replace("e009/e011 完賽時數 infra 格＋原因", "e009 完賽時數 infra 格＋原因", 1), RUNS_BASE, "缺跟進註記")
    if not ok: return 1
    print("VERDICT: E011_CLOSURE_OK")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋4 負控制自測")
    ap.add_argument("--report", type=pathlib.Path, default=REPORT_DEFAULT)
    ap.add_argument("--loop", dest="loop_doc", type=pathlib.Path, default=LOOP_DOC_DEFAULT)
    ap.add_argument("--backlog", type=pathlib.Path, default=BACKLOG_DEFAULT)
    args = ap.parse_args()
    if args.selftest: return selftest(args.report, args.loop_doc, args.backlog)
    report, loop, backlog = (_read_or_die(args.report, "REPORT.json"), _read_or_die(args.loop_doc, "loop 文件"), _read_or_die(args.backlog, "BACKLOG"))
    if None in (report, loop, backlog): return 1
    v = check(report, loop, backlog)
    print("\n".join(f"VIOLATION: {s}" for s in v), end="")
    return 1 if v else 0

if __name__ == "__main__":
    raise SystemExit(main())
