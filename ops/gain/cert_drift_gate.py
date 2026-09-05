#!/usr/bin/env python3
"""R477：認證漂移擋門——附錄說「這條收官指令已原樣跑過」，那之後工具被改了嗎？

判準先行：`DECISION_20260905_R477_CERT_DRIFT_EXECUTABLE_GATE.md`（`f3b31ff`，本檔之前 commit）。
定義、四種判決、rc 語意、五條突變體、誠實邊界都在那裡，本檔只是編碼它。

⚠ 誠實邊界（判準 §三，任何引用者不准漏）：
    `CERT_STALE` ＝「引用那個數字之前必須重跑」，**不是**「那個數字變了」。
    R476 實測 `paired_ci.py` 被改過（STALE）但 C.4 的數字逐字重現 ⇒ 本擋門刻意過度警報。
    `CERT_FRESH` 才是強的：blob 逐 byte 相同 ⇒ 同輸入必得同輸出。

rc（判準 §六，寫死）：0 ＝ 掃到東西且全 FRESH；1 ＝ 有 STALE；2 ＝ 有 BROKEN_* 或 UNSCANNED。
                     「沒掃到東西」不准回 0。

用法：
  python3 ops/gain/cert_drift_gate.py --selftest
  python3 ops/gain/cert_drift_gate.py --json ops/gain/data/r477_cert_drift.json
"""
from __future__ import annotations
import argparse, json, os, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
LIVE = "g_r461_lcb3_three_arm"          # 主 run：本檔一個 byte 都不准讀
_LIVE_READS = 0                          # G-LIVE 計數（永遠應為 0）

DOC_GLOB = "DECISION_*.md"
CERT_MARK = "原樣跑過"
HEADING_RE = re.compile(r"^#{1,6}\s")
APPENDIX_RE = re.compile(r"^#\s*附錄\s*([A-Z])")
CMD_RE = re.compile(r"python3\s+(ops/[\w./-]+\.py)")


def _mut() -> str:
    """突變旗標一律在被測函式**內部**讀（memory：寫在模組層的旗標永遠不生效）。"""
    return os.environ.get("R477_MUTANT", "")


def _guard(path: str) -> str:
    global _LIVE_READS
    if LIVE in str(path):
        _LIVE_READS += 1
        raise RuntimeError(f"G-LIVE: 本輪不准碰主 run: {path}")
    return path


def git(*args: str) -> tuple[int, str]:
    for a in args:
        if LIVE in a:
            _guard(a)
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return p.returncode, p.stdout


# ── 解析：認證標記／認證範圍／被認證的工具（判準 §二.1–3）────────────────────
def cert_headings(lines: list[str]) -> list[tuple[int, str]]:
    out = []
    for i, ln in enumerate(lines):
        if CERT_MARK not in ln:
            continue
        is_heading = bool(HEADING_RE.match(ln))
        if _mut() == "M1_PROSE":          # 放寬成「整行含標記」⇒ 散文會混進來
            is_heading = True
        if is_heading:
            out.append((i, ln.rstrip("\n")))
    return out


def appendix_spans(lines: list[str]) -> list[tuple[str, int, int]]:
    starts = [(i, m.group(1)) for i, ln in enumerate(lines) if (m := APPENDIX_RE.match(ln))]
    spans = []
    for k, (i, letter) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        spans.append((letter, i, end))
    return spans


def tools_in(lines: list[str], lo: int, hi: int) -> list[str]:
    rx = CMD_RE
    if _mut() == "M3_REGEX":              # 安靜量不到（第一型）：regex 過期
        rx = re.compile(r"python3\s+(zzz/[\w./-]+\.py)")
    seen, out = set(), []
    for ln in lines[lo:hi]:
        for m in rx.finditer(ln):
            t = m.group(1)
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def scan_doc(doc: pathlib.Path) -> list[dict]:
    lines = doc.read_text(encoding="utf-8").splitlines(keepends=True)
    heads = cert_headings(lines)
    if not heads:
        return []
    spans = appendix_spans(lines)
    groups: dict[str, dict] = {}
    for idx, text in heads:
        key, lo, hi = "doc", 0, len(lines)
        for letter, s, e in spans:
            if s <= idx < e:
                key, lo, hi = letter, s, e
                break
        g = groups.setdefault(key, dict(scope=key, lo=lo, hi=hi, heads=[]))
        g["heads"].append(dict(line=idx + 1, text=text))
    out = []
    for key, g in groups.items():
        g["doc"] = doc.name
        g["tools"] = tools_in(lines, g["lo"], g["hi"])
        out.append(g)
    return out


# ── 認證時刻：把該標題寫進檔案的那個 commit（判準 §二.4）──────────────────
def introducing_commit(doc_name: str, heading_text: str) -> tuple[str | None, int | None]:
    rc, out = git("log", "--reverse", "--format=%H %ct", f"-S{heading_text}", "--", doc_name)
    if rc != 0 or not out.strip():
        return None, None
    h, ct = out.strip().splitlines()[0].split()
    return h, int(ct)


def blob(commit: str, path: str) -> str | None:
    rc, out = git("rev-parse", f"{commit}:{path}")
    return out.strip() if rc == 0 and out.strip() else None


def judge_group(g: dict) -> dict:
    certs = []
    for h in g["heads"]:
        c, ct = introducing_commit(g["doc"], h["text"])
        certs.append(dict(line=h["line"], commit=c, ct=ct))
    live = [c for c in certs if c["commit"]]
    g["cert_commits"] = certs
    if not live:
        g["cert_commit"] = None
        g["items"] = [dict(tool=t, verdict="BROKEN_NO_CERT_COMMIT") for t in g["tools"]] or \
                     [dict(tool=None, verdict="BROKEN_NO_CERT_COMMIT")]
        return g
    oldest = min(live, key=lambda c: c["ct"])          # 保守：取最早的認證時刻
    g["cert_commit"], g["cert_ct"] = oldest["commit"], oldest["ct"]
    if not g["tools"]:
        g["items"] = [dict(tool=None, verdict="BROKEN_NO_TOOLS")]
        return g
    items = []
    for t in g["tools"]:
        verdict, b_then, b_now = "CERT_FRESH", None, None
        # >>> R477-M5-LOADBEARING-BEGIN  §二.5 的 blob 比對；M5 把整段實體刪掉
        b_then, b_now = blob(g["cert_commit"], t), blob("HEAD", t)
        if b_then is None:
            verdict = "BROKEN_TOOL_ABSENT_AT_CERT"
        elif b_now is None:
            verdict = "BROKEN_TOOL_GONE"
        elif b_then != b_now:
            verdict = "CERT_STALE"
        if _mut() == "M2_ALWAYS_FRESH":
            verdict = "CERT_FRESH"
        # <<< R477-M5-LOADBEARING-END
        rc, log = git("log", "--format=%h %ct %s", f"{g['cert_commit']}..HEAD", "--", t)
        items.append(dict(tool=t, verdict=verdict, blob_at_cert=b_then, blob_at_head=b_now,
                          commits_since=[l for l in log.strip().splitlines() if l]))
    g["items"] = items
    return g


EXEMPT_PATH = ROOT / "ops/gain/data/r477_cert_exemptions.json"


def load_exemptions() -> list[dict]:
    """人工分診過的『不是認證』條目。⚠ 只對 BROKEN_NO_TOOLS 生效，永遠不准消音 CERT_STALE。

    R477 事後新增（判準 §七.3 「先查是不是夾具問題」的查明結果）：條目**不刪、仍列出**，
    只是換成 TRIAGED_NOT_A_CERT 並保留 counts_raw。豁免＝採購清單，不是放寬門檻。
    """
    if not EXEMPT_PATH.exists():
        return []
    return json.loads(EXEMPT_PATH.read_text(encoding="utf-8"))["exemptions"]


def apply_exemptions(groups: list[dict], ex: list[dict]) -> int:
    refused = 0
    for g in groups:
        head_lines = {h["line"] for h in g["heads"]}
        for e in ex:
            if e["doc"] != g["doc"] or e["line"] not in head_lines:
                continue
            for it in g["items"]:
                if it["verdict"] == "BROKEN_NO_TOOLS":
                    it["verdict"] = "TRIAGED_NOT_A_CERT"
                    it["triage_reason"] = e["reason"]
                else:
                    refused += 1          # 豁免碰不到 CERT_STALE／CERT_FRESH
                    it["exemption_refused"] = True
    return refused


def audit(doc_glob: str = DOC_GLOB) -> dict:
    glob = doc_glob
    if _mut() == "M4_NO_DOCS":            # 安靜量不到（第三型）：掃到 0 份文件
        glob = "ZZZ_NO_SUCH_*.md"
    docs = sorted(ROOT.glob(glob))
    groups = []
    for d in docs:
        for g in scan_doc(d):
            groups.append(judge_group(g))
    n_heads = sum(len(g["heads"]) for g in groups)
    items = [it for g in groups for it in g["items"]]
    counts_raw: dict[str, int] = {}
    for it in items:
        counts_raw[it["verdict"]] = counts_raw.get(it["verdict"], 0) + 1
    ex = [] if _mut() == "M7_NO_EXEMPT" else load_exemptions()
    if _mut() == "M6_EXEMPT_STALE":       # 豁免不准消音 CERT_STALE
        ex = ex + [dict(doc=g["doc"], line=g["heads"][0]["line"], reason="M6") for g in groups]
    refused = apply_exemptions(groups, ex)
    counts: dict[str, int] = {}
    for it in items:
        counts[it["verdict"]] = counts.get(it["verdict"], 0) + 1
    tools = sorted({it["tool"] for it in items if it["tool"]})
    broken = sum(v for k, v in counts.items() if k.startswith("BROKEN"))
    if not docs:
        verdict, rc = "UNSCANNED", 2
    elif broken:
        verdict, rc = "BROKEN", 2
    elif counts.get("CERT_STALE"):
        verdict, rc = "STALE_CERTS_PRESENT", 1
    elif counts.get("CERT_FRESH"):
        verdict, rc = "OK", 0
    else:
        verdict, rc = "UNSCANNED", 2      # 掃到文件但一格都沒有 ⇒ 不准回 0
    return dict(verdict=verdict, rc=rc, counts_raw=counts_raw, exemptions=len(ex),
                exemptions_refused=refused, docs_scanned=len(docs), cert_headings=n_heads,
                groups_with_certs=len(groups), distinct_tools=tools, counts=counts,
                groups=groups, live_run_reads=_LIVE_READS,
                honesty="CERT_STALE 只表示『引用前必須重跑』，不表示那個數字變了（判準 §三）")


# ── 自檢：雙向真資料校準 ＋ 五條突變體（判準 §五）────────────────────────
def _with_mutant(name: str):
    os.environ["R477_MUTANT"] = name
    try:
        return audit()
    finally:
        os.environ.pop("R477_MUTANT", None)


def _loadbearing_delete() -> dict:
    """M5：把 §二.5 的 blob 比對整段從原始碼刪掉，放進**同一個 import 環境**再跑。

    判準 §五：判準要指名「該看到哪個量變」——這裡是 CERT_STALE 格數必須掉到 0。
    crash 收場算 BROKEN 不算偵測到（memory）。
    """
    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    # ⚠ 標記字面要拼出來，否則這兩行自己就含有標記 ⇒ 每個標記數到 2 ⇒ BASELINE_BROKEN
    stem = "R477-M5-LOAD" + "BEARING-"
    b = [i for i, l in enumerate(lines) if stem + "BEG" + "IN" in l]
    e = [i for i, l in enumerate(lines) if stem + "E" + "ND" in l]
    if len(b) != 1 or len(e) != 1:
        return dict(ok=False, detail=f"BASELINE_BROKEN: 標記數 begin={len(b)} end={len(e)}")
    cut = "".join(lines[:b[0]] + lines[e[0] + 1:])
    if cut == src:
        return dict(ok=False, detail="BASELINE_BROKEN: 刪不掉任何一行")
    tmp = pathlib.Path(__file__).with_name("_r477_m5_mutant.py")   # 同目錄＝同 import 環境
    try:
        tmp.write_text(cut, encoding="utf-8")
        p = subprocess.run([sys.executable, str(tmp)], cwd=ROOT, capture_output=True, text=True,
                           timeout=600)
        if p.returncode not in (0, 1, 2):
            return dict(ok=False, detail=f"BROKEN: 突變體 crash rc={p.returncode} {p.stderr[-200:]}")
        stale = "CERT_STALE" in p.stdout
        return dict(ok=(not stale) and p.returncode == 0,
                    detail=f"刪掉後 rc={p.returncode} CERT_STALE_present={stale} "
                           f"(乾淨版 rc=1 且有 CERT_STALE)")
    finally:
        tmp.unlink(missing_ok=True)


def selftest() -> int:
    base = audit()
    ck: list[tuple[str, bool, str]] = []

    def add(n, ok, detail=""):
        ck.append((n, bool(ok), detail))

    def tool_verdicts(rep, name):
        # 比 basename 不用 endswith：endswith("paired_ci.py") 會連 pooled_paired_ci.py 一起吃掉
        return sorted({it["verdict"] for g in rep["groups"] for it in g["items"]
                       if it["tool"] and it["tool"].rsplit("/", 1)[-1] == name})

    # 真資料雙向校準
    neg = tool_verdicts(base, "r447_eq5_offline.py")
    pos = tool_verdicts(base, "paired_ci.py")
    pooled = tool_verdicts(base, "pooled_paired_ci.py")
    add("A_realdata_negative_control_fresh", neg == ["CERT_FRESH"], f"eq5_offline={neg}")
    add("B_realdata_positive_control_stale", pos == ["CERT_STALE"], f"paired_ci={pos} pooled={pooled}")
    add("C_not_all_one_box", len(set(base["counts"])) >= 2, f"counts={base['counts']}")

    # M1 散文誤收：認證標題數必須變多
    m1 = _with_mutant("M1_PROSE")
    add("M1_prose_inflates_headings", m1["cert_headings"] > base["cert_headings"],
        f"{base['cert_headings']} -> {m1['cert_headings']}")
    # M2 恆綠：STALE 必須掉到 0
    m2 = _with_mutant("M2_ALWAYS_FRESH")
    add("M2_always_fresh_kills_stale",
        base["counts"].get("CERT_STALE", 0) > 0 and m2["counts"].get("CERT_STALE", 0) == 0,
        f"stale {base['counts'].get('CERT_STALE',0)} -> {m2['counts'].get('CERT_STALE',0)}")
    # M3 regex 過期：要 BROKEN_NO_TOOLS ＋ rc=2，不准 rc=0
    m3 = _with_mutant("M3_REGEX")
    add("M3_stale_regex_is_broken_not_clean",
        m3["rc"] == 2 and m3["counts"].get("BROKEN_NO_TOOLS", 0) > 0,
        f"rc={m3['rc']} counts={m3['counts']}")
    # M4 掃到 0 份文件：要 UNSCANNED ＋ rc=2
    m4 = _with_mutant("M4_NO_DOCS")
    add("M4_no_docs_is_unscanned_not_ok",
        m4["rc"] == 2 and m4["verdict"] == "UNSCANNED" and m4["docs_scanned"] == 0,
        f"rc={m4['rc']} verdict={m4['verdict']}")
    # rc 語意
    def spec_rc(rep):                     # 判準 §六 的 rc 語意，逐條轉錄
        if rep["docs_scanned"] == 0:
            return 2
        if any(k.startswith("BROKEN") for k in rep["counts"]):
            return 2
        if rep["counts"].get("CERT_STALE"):
            return 1
        return 0 if rep["counts"].get("CERT_FRESH") else 2
    add("D_rc_semantics", all(r["rc"] == spec_rc(r) for r in (base, m1, m2, m3, m4)),
        f"base rc={base['rc']} spec={spec_rc(base)} verdict={base['verdict']}")
    add("E_no_live_reads", base["live_run_reads"] == 0, f"live_run_reads={base['live_run_reads']}")

    # M6 豁免不准消音 CERT_STALE（豁免機制自己的牙齒）
    m6 = _with_mutant("M6_EXEMPT_STALE")
    add("M6_exemption_cannot_silence_stale",
        m6["counts"].get("CERT_STALE", 0) == base["counts"].get("CERT_STALE", 0)
        and m6["exemptions_refused"] > 0,
        f"stale {base['counts'].get('CERT_STALE',0)} -> {m6['counts'].get('CERT_STALE',0)}, "
        f"refused={m6['exemptions_refused']}")
    # M7 關掉豁免名單 ⇒ 原始 BROKEN 必須回來（證明豁免確實有作用、而且是它讓 rc 從 2 變 1）
    m7 = _with_mutant("M7_NO_EXEMPT")
    add("M7_without_exemptions_broken_returns",
        m7["rc"] == 2 and m7["counts"].get("BROKEN_NO_TOOLS", 0) > 0
        and base["counts_raw"].get("BROKEN_NO_TOOLS", 0) == m7["counts"].get("BROKEN_NO_TOOLS", 0),
        f"m7 rc={m7['rc']} counts={m7['counts']} base_raw={base['counts_raw']}")

    # M5 承重牆：把 blob 比對整段**實體刪掉**（不是改旗標），必須紅
    m5 = _loadbearing_delete()
    add("M5_deleting_blob_compare_goes_red", m5["ok"], m5["detail"])

    for n, ok, d in ck:
        print(f"  {n:38s} {'PASS' if ok else 'FAIL':4s}  {d}")
    bad = [n for n, ok, _ in ck if not ok]
    print(f"selftest {'SELFTEST_PASS' if not bad else 'SELFTEST_FAIL'} {len(ck)-len(bad)}/{len(ck)}")
    return 0 if not bad else 3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    rep = audit()
    if a.json:
        p = pathlib.Path(_guard(a.json))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"verdict {rep['verdict']}  rc={rep['rc']}  docs={rep['docs_scanned']}  "
          f"cert_headings={rep['cert_headings']}  counts={rep['counts']}")
    for g in rep["groups"]:
        print(f"  {g['doc']} 附錄{g['scope']}  cert={str(g.get('cert_commit'))[:8]}  "
              f"heads={[h['line'] for h in g['heads']]}")
        for it in g["items"]:
            print(f"      {str(it['tool']):44s} {it['verdict']}  "
                  f"(+{len(it.get('commits_since') or [])} commits since)")
    return rep["rc"]


if __name__ == "__main__":
    sys.exit(main())
