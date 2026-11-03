#!/usr/bin/env python3
"""C2 真鏈向後相容驗收（pre-registered: DECISION_20261103_STEPCHAIN_SEALING §5 C2；
缺口登記: DECISION_20261103_ROUND891_ARGON_PHASEA_REVIEW §3 G2）。

對 `~/.vacant/trace/projects/` 下的每一條真鏈（本機 dogfood 鏈），在**副本**上實測：

1. 升級前 `verify`（舊格式＝單一 chain.ndjson；已分卷格式＝chain-NNNNNN.ndjson＋chain.ndjson）；
2. 追加一步（舊格式副本以 `volume_max_bytes=1` 強制封印——與 round 891 審查 §5 同法；
   封印卷＝整條舊鏈＋1 seal 行，新活動卷承接後續）；
3. 升級後 `verify`；
4. 裁決：升級前後 `verify` 結果一致（皆 True）且仍可追加。

安全邊界（與 round 891 審查同法）：
- 全部操作在 `/tmp` 副本；**原鏈與 `~/.vacant` 原址不動**。
- 副本含 `intake/`（簽名身分）——因 recorder 的單簽章者規則
  （recorder.py `MixedSignerRefused`：append 身分的公鍵必須等於創世筆 signer）。
- 輸出＝JSON 收據（每鏈一段），可入庫作為驗收證據；不輸出任何金鑰材料。

預設目標＝預註冊的兩條真鏈（DECISION_20261103_ROUND891_ARGON_PHASEA_REVIEW §3 G2 點名）；
`--all` 掃全部專案（含測試殘鏈——會多出 UNKNOWN 段，只作普查用）。

用法：
    python3 ops/stepchain/c2_realchain_acceptance.py [--out receipt.json] [--all]
    python3 ops/stepchain/c2_realchain_acceptance.py --selfcheck   # 不碰真鏈：合成 legacy 鏈走同一程序

退出碼：0 全綠；1 有鏈未過。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# 預註冊點名的兩條真鏈（round 891 審查 §3 G2 / §5 實測對象）
PREREGISTERED_CHAINS = ("b0a568dfe7dbe3b0", "535f1510326fb03a")


def _project_dirs(vacant_home: Path) -> list[Path]:
    base = vacant_home / "trace" / "projects"
    if not base.is_dir():
        return []
    return sorted(
        d for d in base.iterdir()
        if d.is_dir() and any(p.name.endswith(".ndjson") for p in d.iterdir())
    )


def _read_genesis(project_dir: Path) -> tuple[str | None, str | None]:
    """找創世筆（type=trace_genesis），回傳 (workspace, signer)。

    舊格式：chain.ndjson 首行。已分卷：chain-000001.ndjson[.gz] 首行（卷 1 必含創世）。
    """
    import json as _json
    candidates = []
    for name in ("chain-000001.ndjson", "chain-000001.ndjson.gz", "chain.ndjson"):
        p = project_dir / name
        if p.is_file():
            candidates.append(p)
    for path in candidates:
        try:
            if path.name.endswith(".gz"):
                import gzip
                with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
                    first_line = f.readline()
            else:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    first_line = f.readline()
            first = _json.loads(first_line)
            if first.get("type") == "trace_genesis":
                p = first.get("payload") or {}
                return p.get("workspace"), p.get("signer")
        except (json.JSONDecodeError, UnicodeDecodeError, OSError, EOFError):
            continue
    return None, None


def _accept_one(project_dir: Path, stamp: str) -> dict:
    """對單條鏈（副本上）跑 C2 程序，回傳一段收據。不 raise：失敗寫進收據。"""
    receipt: dict = {
        "project": project_dir.name,
        "files_before": {p.name: p.stat().st_size for p in project_dir.iterdir()
                         if p.name.endswith(".ndjson") or p.name.endswith(".ndjson.gz")},
    }
    ws, signer = _read_genesis(project_dir)
    receipt["genesis_workspace"] = ws
    receipt["genesis_signer"] = str(signer)[:16] + "…" if signer else None
    if not ws:
        receipt["status"] = "UNKNOWN"
        receipt["why"] = "cannot read trace_genesis from copy; not a decidable C2 run"
        return receipt

    home = Path(tempfile.mkdtemp(prefix=f"c2accept_{stamp}_{project_dir.name}_"))
    try:
        # 身分（簽名金）＋專案目錄 → 副本 home
        src_home = Path(os.environ.get("VACANT_HOME", str(Path.home() / ".vacant")))
        shutil.copytree(src_home / "intake", home / "intake", dirs_exist_ok=True)
        (home / "trace" / "projects").mkdir(parents=True)
        shutil.copytree(project_dir, home / "trace" / "projects" / project_dir.name)

        _old_home = os.environ.get("VACANT_HOME")
        os.environ["VACANT_HOME"] = str(home)
        try:
            from vacant_network.trace import recorder as R
            rec = R.Recorder(Path(ws))
            assert rec.dir.name == project_dir.name, (rec.dir, project_dir.name)

            ok0, why0 = rec.verify()
            receipt["verify_before"] = {"ok": ok0, "why": why0}

            # 舊格式（無封印卷）→ volume_max_bytes=1 強制封印；已分卷 → 直接追加。
            legacy = not any((home / "trace" / "projects" / project_dir.name / n).exists()
                             for n in ("chain-000001.ndjson", "chain-000001.ndjson.gz"))
            receipt["format_before"] = "legacy_single_chain" if legacy else "volumes"
            if legacy:
                rec.volume_max_bytes = 1
            t0 = time.perf_counter()
            main = R.Actor("c2-acceptance", "r895")
            rec.pre("c2.accept", main, "Note", {"note": "C2 real-chain acceptance (copy)"})
            rec.post("c2.accept", main, "Note", {"note": "C2 real-chain acceptance (copy)"}, "ok")
            receipt["append_ms"] = round((time.perf_counter() - t0) * 1000, 1)

            ok1, why1 = rec.verify()
            receipt["verify_after"] = {"ok": ok1, "why": why1}
            files_after = {p.name: p.stat().st_size for p in
                           (home / "trace" / "projects" / project_dir.name).iterdir()
                           if p.name.endswith(".ndjson") or p.name.endswith(".ndjson.gz")}
            receipt["files_after"] = files_after
            receipt["status"] = "PASS" if (ok0 and ok1) else "FAIL"
            receipt["why_status"] = (
                "verify identical (True) before/after upgrade and appendable"
                if ok0 and ok1 else
                f"before={ok0} after={ok1}; {why0[:80]} / {why1[:80]}"
            )
        finally:
            # 還原環境（若同進程續跑；ident 無進程級快取，還原 env 即還原一切）
            if _old_home is not None:
                os.environ["VACANT_HOME"] = _old_home
            else:
                os.environ.pop("VACANT_HOME", None)
    finally:
        shutil.rmtree(home, ignore_errors=True)
    return receipt


def run(vacant_home: Path | None = None, *, all_chains: bool = False) -> dict:
    home = Path(vacant_home or os.environ.get("VACANT_HOME") or (Path.home() / ".vacant"))
    stamp = time.strftime("%Y%m%dT%H%M%S")
    if all_chains:
        projects = _project_dirs(home)
    else:
        projects = [home / "trace" / "projects" / n for n in PREREGISTERED_CHAINS]
        projects = [d for d in projects if d.is_dir()]
    missing = [n for n in PREREGISTERED_CHAINS
               if not all_chains and not (home / "trace" / "projects" / n).is_dir()]
    result = {
        "schema": "vacant.c2-realchain/1",
        "ran_at": stamp,
        "vacant_home": str(home),
        "scope": "all_projects" if all_chains else "preregistered",
        "chains": [_accept_one(d, stamp) for d in projects],
        "missing_preregistered": missing,
    }
    result["all_pass"] = not missing and bool(result["chains"]) \
        and all(c["status"] == "PASS" for c in result["chains"])
    return result


def _selfcheck() -> dict:
    """不碰真鏈：合成一條 legacy 鏈，走同一程序（副本 home），驗證程序本身。"""
    src = Path(os.environ.get("VACANT_HOME", str(Path.home() / ".vacant")))
    work = Path(tempfile.mkdtemp(prefix="c2self_"))
    home = work / "home"
    shutil.copytree(src / "intake", home / "intake", dirs_exist_ok=True)
    ws = work / "ws"
    ws.mkdir()
    _old_home = os.environ.get("VACANT_HOME")
    os.environ["VACANT_HOME"] = str(home)
    try:
        from vacant_network.trace import recorder as R
        rec = R.Recorder(ws)
        main = R.Actor("selfcheck", "s1")
        for i in range(5):
            rec.pre(f"s{i}", main, "Write", {"file_path": f"f{i}.txt"})
            rec.post(f"s{i}", main, "Write", {"file_path": f"f{i}.txt"}, "ok")
        assert rec.verify()[0]
        proj = rec.dir
        # 把這條合成鏈當「真鏈」走 _accept_one（它會再複製一份——程序即被驗證）
        receipt = _accept_one(proj, "selfcheck")
    finally:
        if _old_home is not None:
            os.environ["VACANT_HOME"] = _old_home
        else:
            os.environ.pop("VACANT_HOME", None)
        shutil.rmtree(work, ignore_errors=True)
    return receipt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=None, help="receipt JSON output path")
    ap.add_argument("--selfcheck", action="store_true",
                    help="run the same procedure against a synthetic legacy chain (no real chains)")
    ap.add_argument("--all", action="store_true",
                    help="scan ALL project chains (default: only the pre-registered two)")
    args = ap.parse_args(argv)
    if args.selfcheck:
        result = {"schema": "vacant.c2-realchain/1", "mode": "selfcheck",
                  "chains": [_selfcheck()], }
        result["all_pass"] = all(c["status"] == "PASS" for c in result["chains"])
    else:
        result = run(all_chains=args.all)
    text = json.dumps(result, indent=1, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"receipt -> {args.out}")
    print(text)
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
