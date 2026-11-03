"""G2：C2 真鏈驗收——**入庫**（round 891 審查 §3 G2 / §7 門檻2；Phase A 缺口#2）。

兩條預註冊真鏈（審查 §5 點名，`PREREGISTERED_CHAINS`）：
- `b0a568dfe7dbe3b0`（21.6 MB、已分卷，ws=~/dev/Vacant 的活鏈）
- `535f1510326fb03a`（15.0 MB、legacy 單 chain.ndjson，ws=~/dev/wt/worker）

證據兩層（都在庫內、任何機器可跑）：
1. **已提交的驗收收據** `ops/stepchain/c2_receipt_round895.json`（round 895 在本機真鏈
   上執行、兩鏈 upgrade 前後 verify 皆 True、upgrade 後仍可 append）——本測試只斷言
   收據存在、可解析、兩鏈皆 PASS（不重跑）。
2. **本機活跑**：若兩條真鏈在本機 `~/.vacant/trace/projects/` 存在，重跑同一程序
   （`ops/stepchain/c2_realchain_acceptance.py`，在 /tmp 複製體上，絕不碰活鏈）；
   鏈不存在的機器（CI 等）跳過第 2 層——已提交收據即證據（誠實邊界：跳過≠未驗收）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / "ops" / "stepchain" / "c2_receipt_round895.json"
SCRIPT = REPO / "ops" / "stepchain" / "c2_realchain_acceptance.py"


def test_g2_script_and_receipt_committed():
    """G2 的「在 repo 中」要件：驗收腳本與收據皆已提交。"""
    assert SCRIPT.is_file(), "C2 acceptance script must be committed (ops/stepchain/)"
    assert RECEIPT.is_file(), "C2 receipt must be committed (ops/stepchain/)"
    r = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert r.get("schema") == "vacant.c2-realchain/1"
    assert r.get("scope") == "preregistered"
    by = {c["project"]: c for c in r.get("chains", [])}
    for name in ("b0a568dfe7dbe3b0", "535f1510326fb03a"):
        assert name in by, f"receipt must record pre-registered chain {name}"
        c = by[name]
        assert c["status"] == "PASS", f"{name}: {c['status']} ({c.get('why_status')})"
        assert c["verify_before"]["ok"] is True and c["verify_after"]["ok"] is True, name
        # upgrade 前後 verify 一致（皆 True）且 upgrade 後仍可 append
        assert c["append_ms"] is not None, f"{name}: must be appendable after upgrade"
    assert r["all_pass"] is True
    assert r.get("missing_preregistered") == []


def _real_chains_present() -> bool:
    home = Path(os.environ.get("VACANT_HOME") or (Path.home() / ".vacant"))
    return all((home / "trace" / "projects" / n).is_dir()
               for n in ("b0a568dfe7dbe3b0", "535f1510326fb03a"))


@pytest.mark.skipif(not _real_chains_present(),
                    reason="real pre-registered chains not on this machine; "
                           "committed receipt (ops/stepchain/c2_receipt_round895.json) is the evidence")
def test_g2_live_reaccept_on_local_copy():
    """本機有真鏈時：同一程序在 /tmp 複製體上重跑，兩鏈仍 PASS（絕不碰活鏈）。"""
    import ops.stepchain.c2_realchain_acceptance as c2
    result = c2.run()
    by = {c["project"]: c for c in result["chains"]}
    assert result["all_pass"], json.dumps(result, ensure_ascii=False)[:600]
    for name in ("b0a568dfe7dbe3b0", "535f1510326fb03a"):
        assert by[name]["status"] == "PASS", f"{name}: {by[name].get('why_status')}"
        assert by[name]["verify_before"]["ok"] and by[name]["verify_after"]["ok"]


def test_c2_acceptance_handles_compressed_gz_chains(tmp_path):
    """C2 驗收程式必須支援 Phase B 壓縮之 .gz 鏈（chain-000001.ndjson.gz）。"""
    from vacant_network.trace import recorder as R
    from vacant_network.intake import keys
    import ops.stepchain.c2_realchain_acceptance as c2

    vh = tmp_path / "home"
    ws = tmp_path / "ws"
    ws.mkdir(parents=True)
    old = os.environ.get("VACANT_HOME")
    os.environ["VACANT_HOME"] = str(vh)
    try:
        keys.init_local()
        rec = R.Recorder(ws)
        rec.compact_on_seal = True  # Phase B 預設壓縮！
        rec.volume_max_entries = 4
        m = R.Actor("c2_test", "s1")
        for i in range(10):
            rec.pre(f"t{i}", m, "Write", {"file_path": f"f{i}.txt"})
            (ws / f"f{i}.txt").write_text("ok")
            rec.post(f"t{i}", m, "Write", {"file_path": f"f{i}.txt"}, "ok")
        assert (rec.dir / "chain-000001.ndjson.gz").is_file()
        assert not (rec.dir / "chain-000001.ndjson").is_file()

        receipt = c2._accept_one(rec.dir, "test_gz")
        assert receipt["status"] == "PASS", f"C2 must pass on compressed chain: {receipt}"
        assert receipt["verify_before"]["ok"] is True
        assert receipt["verify_after"]["ok"] is True
        assert receipt["format_before"] == "volumes"
    finally:
        if old is not None:
            os.environ["VACANT_HOME"] = old
        else:
            os.environ.pop("VACANT_HOME", None)

