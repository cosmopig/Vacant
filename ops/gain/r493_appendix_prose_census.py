#!/usr/bin/env python3
"""R493：R461 附錄「內文宣稱」的可證偽性／過期普查。

判準：DECISION_20260905_R493_R461_APPENDIX_PROSE_CENSUS.md（量測前單獨 commit 56859a7）。
只掃「原始碼／repo 事實」型的宣稱（判準 §一），17 條 + 2 條校準控制。

G-LIVE 硬擋門：任何開檔路徑含 g_r461_lcb3_three_arm 一律 RuntimeError（主 run 還在跑，
P-R461-1/2/3 的盲測不得被破壞）。報告印 live_reads，必須是 0。
"""
from __future__ import annotations
import ast, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIVE = "g_r461_lcb3_three_arm"
N_CLAIMS_EXPECTED = 17          # 判準 §四.1 釘死，不是可調門檻
TWIN = "runs/g_r447_conform_lcb2"

_live_reads = 0


def _p(rel: str) -> Path:
    """唯一的路徑入口。G-LIVE 擋門在這裡。"""
    global _live_reads
    if LIVE in str(rel):
        _live_reads += 1
        raise RuntimeError(f"G-LIVE: 拒絕碰主 run 的路徑：{rel}")
    return ROOT / rel


def _src(rel: str) -> str:
    return _p(rel).read_text(encoding="utf-8")


def _lines(rel: str) -> list[str]:
    return _src(rel).splitlines()


# ---------------------------------------------------------------- ast helpers
def _return_str_literals(rel: str, fn_name: str) -> list[str]:
    """逐字取某個函式所有 `return "..."` 的字串字面（memory：要用 ast，不要自己改寫一份）。"""
    tree = ast.parse(_src(rel))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fn_name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Constant) \
                        and isinstance(sub.value.value, str):
                    out.append(sub.value.value)
    return out


def _argparse_defaults(rel: str) -> dict[str, object]:
    """取 add_argument("--x", default=...) 的 default（沒寫 default 的記 sentinel）。"""
    tree = ast.parse(_src(rel))
    out: dict[str, object] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"):
            continue
        flags = [a.value for a in node.args
                 if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if not flags:
            continue
        dflt: object = "<no-default>"
        for kw in node.keywords:
            if kw.arg == "default":
                dflt = kw.value.value if isinstance(kw.value, ast.Constant) else "<expr>"
        for f in flags:
            out[f] = dflt
    return out


def _module_consts(rel: str) -> dict[str, object]:
    tree = ast.parse(_src(rel))
    out: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = node.value.value
    return out


_VERDICT_KEYS = {"verdict", "verdict_pooled"}


def _scan_py(fn) -> list[str]:
    hits = []
    for f in sorted((ROOT / "ops" / "gain").rglob("*.py")):
        rel = str(f.relative_to(ROOT))
        if LIVE in rel:
            continue
        try:
            tree = ast.parse(_src(rel))
        except SyntaxError:
            continue
        if fn(tree):
            hits.append(rel)
    return hits


def _mentions(literal: str) -> list[str]:
    """**舊量，保留在紀錄裡**：檔案裡出現這個字串字面（不論位置）。

    ⚠ 這個量**結構上自我推翻**：任何一支「稽核這條宣稱」的工具都必須把該字串寫進自己的
    原始碼（當搜尋參數），於是它自己就讓宣稱變成假的。R493 第一版用的就是這個量，
    實測把 `r462_r461_census.py`（R462 的稽核工具本身）與本檔記成 emitters。
    同 memory 的「不得 import X 用字串比對會匹配到自己」與「搜尋標記的那幾行自己含有標記」。
    保留它不刪，後輪才收得回仲裁權。"""
    def has(tree):
        return any(isinstance(n, ast.Constant) and n.value == literal for n in ast.walk(tree))
    return _scan_py(has)


def _emitters(literal: str) -> list[str]:
    """附錄 B.1 原文的量：有沒有任何 .py **吐得出**這個判決字串。

    「吐得出」逐字化成三種語法位置（ast，不是 grep）：
      1. `return "<L>"`（判決函式的出口，R462 取詞彙表用的就是這個）
      2. dict 裡 `{"verdict": "<L>"}` / `{"verdict_pooled": "<L>"}`
      3. 指派給名為 verdict / verdict_pooled 的變數或 `x["verdict"] = "<L>"`
    只是把字串當**搜尋參數**或寫在註解／散文裡，不算吐得出。"""
    def has(tree):
        for n in ast.walk(tree):
            if isinstance(n, ast.Return) and isinstance(n.value, ast.Constant) \
                    and n.value.value == literal:
                return True
            if isinstance(n, ast.Dict):
                for k, v in zip(n.keys, n.values):
                    if isinstance(k, ast.Constant) and k.value in _VERDICT_KEYS \
                            and isinstance(v, ast.Constant) and v.value == literal:
                        return True
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) \
                    and n.value.value == literal:
                for t in n.targets:
                    if isinstance(t, ast.Name) and t.id in _VERDICT_KEYS:
                        return True
                    if isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant) \
                            and t.slice.value in _VERDICT_KEYS:
                        return True
        return False
    return _scan_py(has)


def _n_py_scanned() -> int:
    return len(list((ROOT / "ops" / "gain").rglob("*.py")))


# ---------------------------------------------------------------- claim checks
# 每個 check 回 (ok, detail, n_scan_targets, can_refute, substantive_change)

def c_B1_1(mut):
    want = {"NON_INFERIOR_BUT_UNRESOLVED", "ON_WINS", "RULED_OUT", "UNINFORMATIVE"}
    if mut == "M1_drop_on_wins":
        want = want - {"ON_WINS"}
    got = set(_return_str_literals("ops/gain/replay/paired_ci.py", "verdict"))
    return (got == want, f"verdict() 字面詞彙表={sorted(got)}｜期望={sorted(want)}",
            len(got), len(got) > 0, False)


def _neg_emitter(name, control="ON_WINS"):
    em = _emitters(name)
    ment = _mentions(name)          # 舊量，照實併報（見 _mentions 的 docstring）
    ctrl = _emitters(control)
    return (em == [],
            f'emitters("{name}")={em}｜校準 emitters("{control}")={len(ctrl)} 支'
            f'｜[舊量，非判定] mentions={ment}',
            _n_py_scanned(), len(ctrl) > 0, False)


def c_B1_2(mut):
    return _neg_emitter("OFF5_WINS")


def c_B1_3(mut):
    return _neg_emitter("CONFORM_WINS")


def c_B2_1(mut):
    d = _argparse_defaults("ops/gain/replay/paired_ci.py")
    ok = "--key" in d and d["--key"] == "meets_demand"
    return (ok, f'--key default={d.get("--key", "<缺這個旗標>")!r}', len(d), len(d) > 0, False)


def c_B2_2(mut):
    d = _argparse_defaults("ops/gain/replay/paired_ci.py")
    flags = {"--run", "--a-arm", "--b-arm"} <= set(d)
    keys = set(_json_out_keys("ops/gain/replay/paired_ci.py"))
    ok = flags and "verdict" in keys
    return (ok, f'旗標齊={flags}｜產物頂層鍵含 verdict={"verdict" in keys}（共 {len(keys)} 鍵）',
            len(d) + len(keys), len(d) > 0, False)


def _json_out_keys(rel: str) -> list[str]:
    """抓 out = {...} / out["k"]= / out.update(ev) 的頂層鍵（R479 M11 的坑：不要漏 update）。"""
    tree = ast.parse(_src(rel))
    keys: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k in node.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.append(k.value)
    return sorted(set(keys))


def c_C1_1(mut):
    ls = _lines("ops/gain/replay/pooled_paired_ci.py")
    line = ls[241] if len(ls) >= 242 else ""
    shape = ("len(args.stratum) < 2" in line) or ("len(strata) < 2" in line)
    r = subprocess.run([sys.executable, "ops/gain/replay/pooled_paired_ci.py",
                        "--stratum", "lcb3=runs/_nonexistent_r493", "--a-arm", "OFF5",
                        "--b-arm", "OFF", "--key", "deliv"],
                       cwd=ROOT, capture_output=True, text=True, timeout=120)
    return (shape and r.returncode == 2,
            f":242={line.strip()!r}｜單一 --stratum 實跑 rc={r.returncode}",
            len(ls), len(ls) >= 242, False)


def c_C2_1(mut):
    c = _module_consts("ops/gain/replay/paired_ci.py")
    want_min = 999 if mut == "C_NEG" else 60
    ok = c.get("PRACTICAL_PP") == 5.0 and c.get("MIN_PAIRED") == want_min
    return (ok, f'PRACTICAL_PP={c.get("PRACTICAL_PP")}｜MIN_PAIRED={c.get("MIN_PAIRED")}'
                f'（期望 {want_min}）', len(c), "MIN_PAIRED" in c, False)


def c_C3_1(mut):
    src = _src("ops/gain/replay/paired_ci.py")
    tree = ast.parse(src)
    seg = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "deliv":
                    seg = ast.get_source_segment(src, v)
    ok = seg is not None and "accepted" in seg and "meets_demand" in seg
    return (ok, f'KEYS["deliv"] 逐字={seg!r}', 1 if seg else 0, seg is not None, False)


def _line_shape(rel, lineno, needles, mut):
    ls = _lines(rel)
    if mut == "M4_lineno_always_true":
        return (True, f"{rel}:{lineno} <M4 恆真>", len(ls), True, False)
    line = ls[lineno - 1] if len(ls) >= lineno else ""
    ok = all(nd in line for nd in needles)
    return (ok, f"{rel}:{lineno}={line.strip()!r}｜期望含 {needles}", len(ls), len(ls) >= lineno, False)


def c_C3_2(mut):
    return _line_shape("ops/gain/gain_run.py", 588, ["chosen if accepted else"], mut)


def c_C3_3(mut):
    return _line_shape("ops/gain/gain_run.py", 1586, ["meets_demand("], mut)


def c_D2_1(mut):
    d = _argparse_defaults("ops/gain/r447_eq5_offline.py")
    ok = d.get("--bank") == "lcb2"
    return (ok, f'--bank default={d.get("--bank", "<缺>")!r}', len(d), len(d) > 0, False)


def c_D2_2(mut):
    src = _src("ops/gain/r447_eq5_offline.py")
    tree = ast.parse(src)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get" and isinstance(node.func.value, ast.Name) \
                and node.func.value.id == "summary":
            a = node.args[0]
            if isinstance(a, ast.Constant):
                hits.append(a.value)
    ok = "summary.json" in src and "seed" in hits and "n" in hits
    return (ok, f'summary.get(...) 逐字取到 {sorted(set(hits))}', len(hits), len(hits) > 0, False)


def _summaries():
    out = []
    for f in sorted((ROOT / "runs").rglob("summary.json")):
        rel = str(f.relative_to(ROOT))
        if LIVE in rel:
            continue                      # 具名排除還在跑的主 run（同 R480）
        out.append(rel)
    return out


def c_D2_3a(mut):
    s = _summaries()
    return (len(s) == 41, f"全庫 summary.json 份數={len(s)}（原文寫 41）",
            len(s), True, False)


def c_D2_3b(mut):
    s = _summaries()
    with_bank, parsed = [], 0
    for rel in s:
        try:
            d = json.loads(_p(rel).read_text(encoding="utf-8"))
        except Exception:
            continue
        parsed += 1
        if isinstance(d, dict) and "bank" in d:
            with_bank.append(rel)
    return (with_bank == [], f"記 bank 的 summary.json={with_bank}｜成功解析 {parsed}/{len(s)} 份",
            parsed, parsed > 0, False)


def c_E2_1(mut):
    ls = _lines("ops/gain/r447_gauge_capability.py")
    if mut == "M4_lineno_always_true":
        return (True, "r447_gauge_capability.py:89-92 <M4 恆真>", len(ls), True, False)
    blk = "\n".join(ls[88:92])
    ok = "def passed" in blk and 'any(bool(r.get("meets_demand")) for r in rs)' in blk
    return (ok, f":89-92 逐字={blk.strip()!r}", len(ls), len(ls) >= 92, False)


def c_E2_2(mut):
    ls = _lines("ops/gain/r447_gauge_capability.py")
    if mut == "M4_lineno_always_true":
        return (True, "r447_gauge_capability.py:228-241 <M4 恆真>", len(ls), True, False)
    blk = "\n".join(ls[227:241])
    ok = ("def main" in blk or "sys.argv[1]" in blk)
    d = _argparse_defaults("ops/gain/r447_gauge_capability.py")
    no_flags = not ({"--bank", "--seed", "--n"} & set(d))
    return (ok and no_flags,
            f":228-241 首行={ls[227].strip()!r}｜含 main()/argv[1]={ok}"
            f"｜無 --bank/--seed/--n={no_flags}（旗標={sorted(d)}）",
            len(ls), len(ls) >= 241, False)


def c_H2_1(mut):
    """H-2／H-3 兩段釘死的 inline 指令，原樣在孿生 run 上跑。"""
    if LIVE in TWIN:
        raise RuntimeError("G-LIVE")
    h2 = subprocess.run([sys.executable, "-c", f"""
import json
n=t=0
for l in open('{TWIN}/rows.jsonl'):
    r=json.loads(l)
    if r.get('arm')!='CONFORM': continue
    t+=1
    if (not r.get('accepted')) and r.get('meets_demand'): n+=1
print('CONFORM rows=',t,' accepted=False and meets_demand=True 格數=',n)"""],
                        cwd=ROOT, capture_output=True, text=True, timeout=120)
    h3 = subprocess.run([sys.executable, "-c", f"""
import json
s=set()
for l in open('{TWIN}/notes.jsonl'):
    d=json.loads(l)
    if 'void' in json.dumps(d,ensure_ascii=False): s.add(d.get('task_id'))
print('voided_tasks=',len(s))"""],
                        cwd=ROOT, capture_output=True, text=True, timeout=120)
    o2, o3 = h2.stdout.strip(), h3.stdout.strip()
    ok = (h2.returncode == 0 and h3.returncode == 0
          and "CONFORM rows= 120" in o2 and "格數= 0" in o2 and "voided_tasks= 0" in o3)
    return (ok, f"H-2 rc={h2.returncode} {o2!r}｜H-3 rc={h3.returncode} {o3!r}",
            2, True, False)


def c_CPOS(mut):
    ok = _p("ops/gain/replay/paired_ci.py").is_file()
    return (ok, "paired_ci.py 是存在的檔（構造為真的正對照）", 1, True, False)


CLAIMS = [
    ("B1-1",  "附錄 B.1", "evidence", c_B1_1),
    ("B1-2",  "附錄 B.1", "evidence", c_B1_2),
    ("B1-3",  "附錄 B.1", "evidence", c_B1_3),
    ("B2-1",  "附錄 B.2/C.2", "evidence", c_B2_1),
    ("B2-2",  "附錄 B.2/C.2", "evidence", c_B2_2),
    ("C1-1",  "附錄 C.1", "evidence", c_C1_1),
    ("C2-1",  "附錄 C.2", "evidence", c_C2_1),
    ("C3-1",  "附錄 C.3", "evidence", c_C3_1),
    ("C3-2",  "附錄 C.3", "evidence", c_C3_2),
    ("C3-3",  "附錄 C.3", "evidence", c_C3_3),
    ("D2-1",  "附錄 D.2", "evidence", c_D2_1),
    ("D2-2",  "附錄 D.2", "evidence", c_D2_2),
    ("D2-3a", "附錄 D.2", "evidence", c_D2_3a),
    ("D2-3b", "附錄 D.2", "evidence", c_D2_3b),
    ("E2-1",  "附錄 E.2", "evidence", c_E2_1),
    ("E2-2",  "附錄 E.2", "evidence", c_E2_2),
    ("H2-1",  "附錄 H.2", "evidence", c_H2_1),
]
# 校準控制（判準 §二；不算在 17 條裡）
CONTROLS = [
    ("C_POS", c_CPOS, "VERIFIED"),
    ("C_NEG", c_C2_1, "REFUTED"),      # C2-1 的刻意錯版，mut="C_NEG" 觸發
]


def classify(ok, n_targets, can_refute):
    """判準 §二釘死的 class 規則。"""
    if n_targets == 0:
        return "UNSCANNED"
    if not can_refute:
        return "FORCED_GREEN"
    return "EVALUABLE"


def run(mut: str = "") -> dict:
    global _live_reads
    _live_reads = 0
    claims = [c for c in CLAIMS if not (mut == "M5_drop_claim" and c[0] == "H2-1")]
    controls = [c for c in CONTROLS if not (mut == "M2_drop_cneg" and c[0] == "C_NEG")]

    rows, blockers = [], []
    for cid, src_ref, intent, fn in claims:
        try:
            ok, detail, n_t, can_ref, subst = fn(mut)
        except RuntimeError:
            raise
        except Exception as e:                      # noqa: BLE001
            rows.append({"id": cid, "source": src_ref, "intent": intent,
                         "status": "BROKEN_CHECK", "class": "UNSCANNED",
                         "premise_stale": None, "substantive_change": None,
                         "detail": f"{type(e).__name__}: {e}"})
            blockers.append(f"BROKEN_CHECK:{cid}")
            continue
        rows.append({"id": cid, "source": src_ref, "intent": intent,
                     "status": "VERIFIED" if ok else "REFUTED",
                     "class": classify(ok, n_t, can_ref),
                     "premise_stale": (not ok), "substantive_change": bool(subst),
                     "n_scan_targets": n_t, "can_refute": bool(can_ref),
                     "detail": detail})

    ctrl_out = {}
    for name, fn, want in controls:
        ok, detail, *_ = fn("C_NEG" if name == "C_NEG" else mut)
        got = "VERIFIED" if ok else "REFUTED"
        ctrl_out[name] = {"got": got, "want": want, "detail": detail}
        if got != want:
            blockers.append(f"CALIBRATION:{name} got={got} want={want}")

    n = len(rows)
    if n != N_CLAIMS_EXPECTED:
        blockers.append(f"SCAN_COUNT:{n}!={N_CLAIMS_EXPECTED}")
    if len(controls) != 2:
        blockers.append(f"CALIBRATION:missing_control({len(controls)}/2)")

    verdict = "CENSUS_OK"
    if any(b.startswith("SCAN_COUNT") for b in blockers):
        verdict = "BROKEN_SCAN_COUNT"
    elif any(b.startswith("CALIBRATION") for b in blockers):
        verdict = "BROKEN_CALIBRATION"
    elif blockers:
        verdict = "BROKEN"

    stale = [r["id"] for r in rows if r.get("premise_stale")]
    return {"verdict": verdict, "n_claims_scanned": n,
            "n_premise_stale": len(stale), "premise_stale_ids": stale,
            "n_substantive_change": sum(1 for r in rows if r.get("substantive_change")),
            "class_counts": {c: sum(1 for r in rows if r["class"] == c)
                             for c in ("EVALUABLE", "FORCED_GREEN", "UNRESOLVED", "UNSCANNED")},
            "controls": ctrl_out, "live_reads": _live_reads,
            "blockers": blockers, "claims": rows}


def selftest() -> int:
    fails = []
    # A：乾淨基線的結構性質
    r = run("")
    if r["n_claims_scanned"] != N_CLAIMS_EXPECTED:
        fails.append(f"A: n={r['n_claims_scanned']}")
    if r["live_reads"] != 0:
        fails.append(f"A: live_reads={r['live_reads']}")
    # B：G-LIVE 擋門真的會叫（正對照）
    try:
        _p(f"runs/{LIVE}/rows.jsonl")
        fails.append("B: G-LIVE 沒有擋下主 run 路徑")
    except RuntimeError:
        pass
    # C：G-LIVE 不會誤擋別的路徑（負對照）
    try:
        _p(TWIN + "/rows.jsonl")
    except RuntimeError:
        fails.append("C: G-LIVE 誤擋孿生 run")
    # D：classify 的三個分支各釘一格
    for args, want in (((True, 0, True), "UNSCANNED"), ((True, 5, False), "FORCED_GREEN"),
                       ((True, 5, True), "EVALUABLE"), ((False, 5, True), "EVALUABLE")):
        if classify(*args) != want:
            fails.append(f"D: classify{args}={classify(*args)} 期望 {want}")
    # E：C_NEG 這條錯版宣稱真的被判 REFUTED（判準的雙向校準）
    if r["controls"].get("C_NEG", {}).get("got") != "REFUTED":
        fails.append(f"E: C_NEG={r['controls'].get('C_NEG')}")
    if r["controls"].get("C_POS", {}).get("got") != "VERIFIED":
        fails.append(f"E: C_POS={r['controls'].get('C_POS')}")
    # F：ast 取字面的 helper 對已知輸入正確（不共用被測檔 helper，r699）
    got = set(_return_str_literals("ops/gain/replay/paired_ci.py", "verdict"))
    if "ON_WINS" not in got:
        fails.append(f"F: _return_str_literals 取不到 ON_WINS：{got}")
    # G：argparse 取 default 的 helper 對已知輸入正確
    if _argparse_defaults("ops/gain/r447_eq5_offline.py").get("--bank") != "lcb2":
        fails.append("G: _argparse_defaults 取不到 --bank=lcb2")
    # H：emitters 的正／負對照（負：一個絕不存在的字串）
    if not _emitters("ON_WINS"):
        fails.append("H: emitters 正對照抓不到 ON_WINS")
    # ⚠ 負對照的字串必須拼出來：寫成字面會出現在本檔裡，被自己的掃描器抓到
    #   （memory：「搜尋標記的那幾行自己含有標記」；本條第一版就是這樣紅的）。
    if _emitters("ZZZ_NOT_A" + "_VERDICT_R493"):
        fails.append("H: emitters 負對照誤報")
    # H2 合成復現（**這是把 _mentions 換成 _emitters 的唯一理由**，不是結果數字）：
    #   造兩個檔，一個只「提到」判決名（當搜尋參數／註解），一個真的 `return` 它。
    #   舊量兩個都算 emitter ⇒ 稽核工具自己讓宣稱變假；新量只算後者。
    import tempfile
    L = "OFF5" + "_WINS"
    men_src = f'def audit():\n    return census_vocab("X1", {L!r})\n'
    emi_src = f'def verdict():\n    return {L!r}\n'
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        (t / "only_mentions.py").write_text(men_src, encoding="utf-8")
        (t / "really_emits.py").write_text(emi_src, encoding="utf-8")

        def _in(path, fn):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            return fn(tree)

        def _has_mention(tree):
            return any(isinstance(n, ast.Constant) and n.value == L for n in ast.walk(tree))

        def _has_emit(tree):
            return any(isinstance(n, ast.Return) and isinstance(n.value, ast.Constant)
                       and n.value.value == L for n in ast.walk(tree))
        if not _in(t / "only_mentions.py", _has_mention):
            fails.append("H2: 合成夾具的『只提到』檔連舊量都抓不到（夾具壞了）")
        if _in(t / "only_mentions.py", _has_emit):
            fails.append("H2: 新量把『只提到』誤判成 emitter")
        if not _in(t / "really_emits.py", _has_emit):
            fails.append("H2: 新量抓不到真的 return 判決名的檔")
    # I：每條宣稱都要有 detail，且 id 不重複
    ids = [c[0] for c in CLAIMS]
    if len(set(ids)) != len(ids):
        fails.append("I: claim id 重複")
    print("selftest:", "all passed" if not fails else "FAILED")
    for f in fails:
        print("  -", f)
    return 0 if not fails else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    mut = os.environ.get("R493_MUTANT", "")
    r = run(mut)
    print(f'verdict={r["verdict"]}  n_claims={r["n_claims_scanned"]}  '
          f'stale={r["n_premise_stale"]} {r["premise_stale_ids"]}  '
          f'substantive_change={r["n_substantive_change"]}  live_reads={r["live_reads"]}')
    print(f'  class={r["class_counts"]}  controls='
          + " ".join(f'{k}:{v["got"]}' for k, v in r["controls"].items())
          + f'  blockers={r["blockers"]}')
    for c in r["claims"]:
        print(f'  {c["id"]:<6} {c["status"]:<9} {c["class"]:<12} '
              f'stale={str(c.get("premise_stale")):<5} {c["detail"]}')
    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if r["verdict"] == "CENSUS_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
