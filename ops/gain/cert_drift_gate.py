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
# R478 §二.1：認證段落自記 blob sha。行首錨定、40 位全長，縮寫 sha 不接受。
CERTBLOB_RE = re.compile(r"^\s*[-*]\s*CERT-BLOB\s+`(ops/[\w./-]+\.py)`\s*=\s*`([0-9a-f]{40})`\s*$")
# 「長得像自記標記但格式不合」——要吵不要安靜跳過
CERTBLOB_LOOSE_RE = re.compile(r"^\s*[-*]\s*CERT-BLOB\b")


def _mut() -> str:
    """突變旗標一律在被測函式**內部**讀（memory：寫在模組層的旗標永遠不生效）。"""
    return os.environ.get("R477_MUTANT", "")


def _has(name: str) -> bool:
    """R478：旗標改成逗號可組合（M9+M10 必須併用才重現得出 R477 的低報）。

    ⚠ 語意與 R477 的 `_mut() == name` 逐條相同（單一旗標時集合只有一個元素）。
    """
    return name in [x for x in _mut().split(",") if x]


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
        if _has("M1_PROSE"):          # 放寬成「整行含標記」⇒ 散文會混進來
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
    if _has("M3_REGEX"):              # 安靜量不到（第一型）：regex 過期
        rx = re.compile(r"python3\s+(zzz/[\w./-]+\.py)")
    seen, out = set(), []
    for ln in lines[lo:hi]:
        for m in rx.finditer(ln):
            t = m.group(1)
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def recorded_in(lines: list[str], lo: int, hi: int) -> tuple[dict[str, str], list[str]]:
    """R478 §二.1–2：只讀**有認證標題的附錄區塊**內的自記標記。

    範圍限定就是自我匹配擋門：判準檔自己雖含 `CERT-BLOB` 字面，卻沒有認證標題 ⇒ 讀不到（S1）。
    回傳 (工具->sha, 格式不合的原始行)。
    """
    rx = CERTBLOB_RE
    if _has("M12_RE_STALE"):              # 安靜量不到（第一型）：標記正規式過期
        rx = re.compile(r"^ZZZ-NO-SUCH-MARKER$")
    rec: dict[str, str] = {}
    bad: list[str] = []
    for ln in lines[lo:hi]:
        m = rx.match(ln)
        if m:
            sha = m.group(2)
            if _has("M8_BAD_RECORDED"):   # 合法格式、歷史上不存在
                sha = "0" * 39 + "1"
            rec.setdefault(m.group(1), sha)
        elif CERTBLOB_LOOSE_RE.match(ln) and not _has("M12_RE_STALE"):
            bad.append(ln.rstrip("\n"))
    return rec, bad


def blob_history(path: str) -> set[str]:
    """R478 §二.5：該路徑歷史上出現過的所有 blob sha（--raw 的後像欄位，一次 git 呼叫）。"""
    rc, out = git("log", "--format=%H", "--raw", "--no-abbrev", "--", path)
    shas: set[str] = set()
    if rc != 0:
        return shas
    for ln in out.splitlines():
        if not ln.startswith(":"):
            continue
        f = ln.split()
        if len(f) >= 4 and re.fullmatch(r"[0-9a-f]{40}", f[3]) and set(f[3]) != {"0"}:
            shas.add(f[3])
    return shas


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
        g["recorded"], g["recorded_malformed"] = recorded_in(lines, g["lo"], g["hi"])
        out.append(g)
    return out


# ── 認證時刻：把該標題寫進檔案的那個 commit（判準 §二.4）──────────────────
def introducing_commit(doc_name: str, heading_text: str) -> tuple[str | None, int | None]:
    if _has("M9_HEADING_REWRITTEN"):
        # 標題被改寫後 `-S<新字串>` 只匹配得到改寫那一次 ⇒ 認證時刻塌到最近的 commit。
        # 這裡用 HEAD 當那個「較晚的 commit」的極端情形。
        rc, out = git("log", "-1", "--format=%H %ct", "HEAD")
        if rc == 0 and out.strip():
            h, ct = out.strip().split()[:2]
            return h, int(ct)
        return None, None
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
    recorded = {} if _has("M10_IGNORE_RECORDED") else (g.get("recorded") or {})
    for t in g["tools"]:
        verdict, b_then, b_now = "CERT_FRESH", None, None
        b_derived = blob(g["cert_commit"], t)
        # ↓ R477 的舊行為就是這四行（只用 -S 反推）。M11 把下面那段實體刪掉後
        #   剩下的正好是它 ⇒ 刪除不會 crash，看得到的差別只有判決本身。
        src, b_rec, mismatch, notinhist = "derived", None, None, False
        b_cert_used = b_derived
        # >>> R478-M11-LOADBEARING-BEGIN  §二.3–5：自記優先＋交叉檢查＋真實性檢查
        b_rec = recorded.get(t)
        if b_rec is not None:
            src = "recorded"
            if b_rec not in blob_history(t):
                notinhist = True                       # 抄錯／編造的 sha
            elif b_derived is not None and b_rec != b_derived:
                mismatch = dict(doc=g["doc"], scope=g["scope"], tool=t,
                                recorded=b_rec, derived=b_derived)
            b_cert_used = b_rec
        # <<< R478-M11-LOADBEARING-END
        # >>> R477-M5-LOADBEARING-BEGIN  §二.5 的 blob 比對；M5 把整段實體刪掉
        b_then, b_now = b_cert_used, blob("HEAD", t)
        if b_then is None:
            verdict = "BROKEN_TOOL_ABSENT_AT_CERT"
        elif b_now is None:
            verdict = "BROKEN_TOOL_GONE"
        elif b_then != b_now:
            verdict = "CERT_STALE"
        if _has("M2_ALWAYS_FRESH"):
            verdict = "CERT_FRESH"
        # <<< R477-M5-LOADBEARING-END
        if notinhist:
            # 自記值不可信 ⇒ 大聲壞掉。此時**不另記 mismatch**：那會把同一個事件數兩次。
            verdict, mismatch = "BROKEN_CERT_SHA_NOT_IN_HISTORY", None
        rc, log = git("log", "--format=%h %ct %s", f"{g['cert_commit']}..HEAD", "--", t)
        items.append(dict(tool=t, verdict=verdict, blob_at_cert=b_then, blob_at_head=b_now,
                          sha_source=src, blob_at_cert_recorded=b_rec,
                          blob_at_cert_derived=b_derived, cert_sha_mismatch=mismatch,
                          commits_since=[l for l in log.strip().splitlines() if l]))
    for badline in (g.get("recorded_malformed") or []):
        items.append(dict(tool=None, verdict="BROKEN_CERT_SHA_UNPARSEABLE", line_text=badline))
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
    if _has("M4_NO_DOCS"):            # 安靜量不到（第三型）：掃到 0 份文件
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
    ex = [] if _has("M7_NO_EXEMPT") else load_exemptions()
    if _has("M6_EXEMPT_STALE"):       # 豁免不准消音 CERT_STALE
        ex = ex + [dict(doc=g["doc"], line=g["heads"][0]["line"], reason="M6") for g in groups]
    refused = apply_exemptions(groups, ex)
    counts: dict[str, int] = {}
    for it in items:
        counts[it["verdict"]] = counts.get(it["verdict"], 0) + 1
    tools = sorted({it["tool"] for it in items if it["tool"]})
    mismatches = [it["cert_sha_mismatch"] for it in items if it.get("cert_sha_mismatch")]
    slots_recorded = sum(1 for it in items if it.get("sha_source") == "recorded")
    slots_derived = sum(1 for it in items if it.get("sha_source") == "derived")
    broken = sum(v for k, v in counts.items() if k.startswith("BROKEN"))
    if not docs:
        verdict, rc = "UNSCANNED", 2
    elif mismatches:
        verdict, rc = "BROKEN", 2      # 自記值與 -S 反推打架 ⇒ 大聲叫（判準 §二.4）
    elif broken:
        verdict, rc = "BROKEN", 2
    elif counts.get("CERT_STALE"):
        verdict, rc = "STALE_CERTS_PRESENT", 1
    elif counts.get("CERT_FRESH"):
        verdict, rc = "OK", 0
    else:
        verdict, rc = "UNSCANNED", 2      # 掃到文件但一格都沒有 ⇒ 不准回 0
    return dict(verdict=verdict, rc=rc, counts_raw=counts_raw, exemptions=len(ex),
                cert_sha_mismatches=mismatches, slots_recorded=slots_recorded,
                slots_derived=slots_derived,
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


def _loadbearing_delete(stem: str = "R477-M5-LOAD" + "BEARING-", tag: str = "m5",
                        env: str = "") -> dict:
    """把一段承重牆從原始碼**實體刪掉**，放進**同一個 import 環境**再跑。

    判準 §五／§六：判準要指名「該看到哪個量變」——這兩處都是 CERT_STALE 格數必須掉到 0。
    crash 收場算 BROKEN 不算偵測到（memory）。
    ⚠ 標記字面一律拼出來，否則搜尋標記的那兩行自己就含有標記 ⇒ 標記數×2 ⇒ BASELINE_BROKEN。
    """
    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    b = [i for i, l in enumerate(lines) if stem + "BEG" + "IN" in l]
    e = [i for i, l in enumerate(lines) if stem + "E" + "ND" in l]
    if len(b) != 1 or len(e) != 1:
        return dict(ok=False, detail=f"BASELINE_BROKEN: 標記數 begin={len(b)} end={len(e)}")
    cut = "".join(lines[:b[0]] + lines[e[0] + 1:])
    if cut == src:
        return dict(ok=False, detail="BASELINE_BROKEN: 刪不掉任何一行")
    tmp = pathlib.Path(__file__).with_name(f"_r47x_{tag}_mutant.py")  # 同目錄＝同 import 環境
    try:
        tmp.write_text(cut, encoding="utf-8")
        ev = dict(os.environ)
        if env:
            ev["R477_MUTANT"] = env
        else:
            ev.pop("R477_MUTANT", None)
        p = subprocess.run([sys.executable, str(tmp)], cwd=ROOT, capture_output=True, text=True,
                           timeout=600, env=ev)
        if p.returncode not in (0, 1, 2):
            return dict(ok=False, detail=f"BROKEN: 突變體 crash rc={p.returncode} {p.stderr[-200:]}")
        stale = "CERT_STALE" in p.stdout
        return dict(ok=(not stale) and p.returncode == 0,
                    detail=f"刪掉後 rc={p.returncode} CERT_STALE_present={stale}"
                           + (f" env={env}" if env else "") + " (乾淨版 rc=1 且有 CERT_STALE)")
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
        if rep.get("cert_sha_mismatches"):
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

    # ── R478（判準 §六）────────────────────────────────────────────
    prereg_doc = "DECISION_20260905_R478_CERT_SELF_RECORDED_SHA.md"
    # S1 自我匹配擋門：判準檔含 CERT-BLOB 字面，但沒有認證標題 ⇒ 不准貢獻群組
    has_literal = (ROOT / prereg_doc).exists() and \
        ("CERT-" + "BLOB") in (ROOT / prereg_doc).read_text(encoding="utf-8")
    contributed = [g for g in base["groups"] if g["doc"] == prereg_doc]
    add("S1_prereg_has_literal_but_no_group", has_literal and not contributed,
        f"字面存在={has_literal} 貢獻群組={len(contributed)}")
    # P1：來源計數
    add("F_sha_source_counts", base["slots_recorded"] > 0,
        f"recorded={base['slots_recorded']} derived={base['slots_derived']}")
    # M12 標記正規式過期 ⇒ slots_recorded 掉到 0（安靜量不到第一型要看得見）
    m12 = _with_mutant("M12_RE_STALE")
    add("M12_marker_regex_stale_drops_recorded",
        base["slots_recorded"] > 0 and m12["slots_recorded"] == 0,
        f"recorded {base['slots_recorded']} -> {m12['slots_recorded']}")
    # M8 自記 sha 不在歷史裡 ⇒ BROKEN_CERT_SHA_NOT_IN_HISTORY ＋ rc=2
    m8 = _with_mutant("M8_BAD_RECORDED")
    add("M8_bad_recorded_sha_is_broken",
        m8["rc"] == 2 and m8["counts"].get("BROKEN_CERT_SHA_NOT_IN_HISTORY", 0) > 0,
        f"rc={m8['rc']} counts={m8['counts']}")
    # M9 標題被改寫（-S 塌到 HEAD）⇒ 自記優先讓 STALE 留在原地 ＋ mismatch 大聲叫
    m9 = _with_mutant("M9_HEADING_REWRITTEN")
    add("M9_rewritten_heading_keeps_stale_and_alarms",
        m9["counts"].get("CERT_STALE", 0) == base["counts"].get("CERT_STALE", 0)
        and len(m9["cert_sha_mismatches"]) > 0 and m9["rc"] == 2,
        f"stale {base['counts'].get('CERT_STALE',0)} -> {m9['counts'].get('CERT_STALE',0)}, "
        f"mismatches={len(m9['cert_sha_mismatches'])} rc={m9['rc']}")
    # M9+M10 ＝ R477 舊行為 ⇒ 必須重現低報（STALE 掉到 0、rc=0）
    m910 = _with_mutant("M9_HEADING_REWRITTEN,M10_IGNORE_RECORDED")
    add("M10_old_behaviour_underreports",
        m910["counts"].get("CERT_STALE", 0) == 0 and m910["rc"] == 0,
        f"stale -> {m910['counts'].get('CERT_STALE',0)} rc={m910['rc']} "
        f"(＝R477 的洞被重現)")
    # M11 承重牆：把自記優先那段實體刪掉、再加 M9 ⇒ 應與 M9+M10 同樣低報
    m11 = _loadbearing_delete(stem="R478-M11-LOAD" + "BEARING-", tag="m11",
                              env="M9_HEADING_REWRITTEN")
    add("M11_deleting_recorded_pref_goes_red", m11["ok"], m11["detail"])
    add("G_no_mismatch_on_clean_realdata", len(base["cert_sha_mismatches"]) == 0,
        f"mismatches={len(base['cert_sha_mismatches'])} "
        f"(判準 §五 P3：這是**結構強制綠燈**，intent=guard，不准當證據)")

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
    print(f"  sha_source: recorded={rep['slots_recorded']} derived={rep['slots_derived']}  "
          f"cert_sha_mismatches={len(rep['cert_sha_mismatches'])}")
    for g in rep["groups"]:
        print(f"  {g['doc']} 附錄{g['scope']}  cert={str(g.get('cert_commit'))[:8]}  "
              f"heads={[h['line'] for h in g['heads']]}")
        for it in g["items"]:
            print(f"      {str(it['tool']):44s} {it['verdict']}  [{it.get('sha_source')}]  "
                  f"(+{len(it.get('commits_since') or [])} commits since)")
    return rep["rc"]


if __name__ == "__main__":
    sys.exit(main())
