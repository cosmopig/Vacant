"""R481 掃描範圍擴張的接線（判準 §五／§六）。

`python3 ops/run_tests_nopytest.py tests/test_cert_scope_r481.py`

⚠ 不寫死任何絕對數字（文件增減會讓寫死的數字安靜衰減成永遠紅——R481 §八實測過一次）。
驗四件結構性的事：範圍真的變大、舊範圍那一半逐格對得回**改動前釘死的 commit**、
第三型「掃到 0 個目標」的安全網在新範圍底下仍然會叫、以及自檢本身仍是綠的。
"""
import json, os, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops" / "gain"))
import cert_drift_gate as G

TOOL = "ops/gain/cert_drift_gate.py"
BASE = "6d59c906cf354c85cb8c359ad0fe447ba65ab355"   # R481 判準 commit ＝ 改動**前**的工具


def _run(args, env_extra=None):
    ev = dict(os.environ)
    ev.update(env_extra or {})
    return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True,
                          text=True, timeout=1800, env=ev)


def test_scope_actually_extended():
    rep = G.audit()
    assert rep["scope_extended"] is True, rep["scope_globs"]
    assert rep["docs_scanned"] > rep["docs_scanned_legacy"] > 0, rep
    assert rep["docs_new_scope"] == rep["docs_scanned"] - rep["docs_scanned_legacy"], rep
    assert rep["live_run_reads"] == 0 and rep["live_paths_skipped"] == 0, rep
    # 具名排除要看得見（judged quantity：清單非空且每筆有理由）
    assert rep["out_of_scope_named"] and all(x["reason"] for x in rep["out_of_scope_named"]), rep


def test_additivity_against_pinned_precommit_tool():
    """加法性對照釘**改動前的 commit**，不是 HEAD（釘 HEAD ＝ 拿自己比自己）。"""
    old_src = subprocess.run(["git", "show", f"{BASE}:{TOOL}"], cwd=ROOT,
                             capture_output=True, text=True, timeout=120)
    assert old_src.returncode == 0 and old_src.stdout, old_src.stderr[-300:]
    tmp = ROOT / "ops" / "gain" / "_r481_test_base_gate.py"   # 同目錄＝同 import 環境
    outp = ROOT / "ops" / "gain" / "_r481_test_base.json"
    try:
        tmp.write_text(old_src.stdout, encoding="utf-8")
        p = _run([str(tmp), "--json", str(outp)])
        assert p.returncode in (0, 1), (p.returncode, p.stderr[-300:])
        old = json.loads(outp.read_text(encoding="utf-8"))
    finally:
        tmp.unlink(missing_ok=True)
        outp.unlink(missing_ok=True)
    new = G.audit()
    assert new["legacy_counts"] == old["counts"], (new["legacy_counts"], old["counts"])
    assert new["legacy_cert_headings"] == old["cert_headings"], new["legacy_cert_headings"]
    assert new["docs_scanned_legacy"] == old["docs_scanned"], new["docs_scanned_legacy"]

    def slots(r):
        return {f"{g['doc']}|{g['scope']}|{it['tool']}": it["verdict"]
                for g in r["groups"] for it in g["items"]}
    # 全範圍可以多，但**舊格不准少也不准改判**
    so, sn = slots(old), slots(new)
    assert all(sn.get(k) == v for k, v in so.items()), \
        {k: (v, sn.get(k)) for k, v in so.items() if sn.get(k) != v}


def test_third_type_safety_net_survives_wider_scope():
    """M4 ＝『掃到 0 個目標』。範圍變大之後它必須仍然吐 UNSCANNED＋rc=2，不准變成綠的。

    這一條就是本輪自己踩過的回歸：新範圍原本沒被 M4 歸零 ⇒ 安全網被拆掉還印 rc=1。
    """
    p = _run([TOOL], {"R477_MUTANT": "M4_NO_DOCS"})
    assert p.returncode == 2, (p.returncode, p.stdout[-400:])
    assert "UNSCANNED" in p.stdout, p.stdout[-400:]
    clean = _run([TOOL])
    assert clean.returncode in (0, 1) and "UNSCANNED" not in clean.stdout, clean.stdout[-400:]


def test_selftest_still_green():
    p = _run([TOOL, "--selftest"])
    assert p.returncode == 0, p.stdout[-800:]
    assert "SELFTEST_PASS" in p.stdout, p.stdout[-800:]
