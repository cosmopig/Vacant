#!/usr/bin/env python3
"""確認批次：回饋四臂發射前的固定步驟（附錄 B 補充 B25／B27／B33(1)＋主文「沿用初稿」）。不看答案鍵。2026-11-28。

步驟（任何硬門檻不過 ⇒ 結束碼 1，不建回饋 root）：
  1. B25：兩台初稿 root 全部 c0 的補回驗收（sha256 對凍結站、補回後頁面集合＝伺服器 200 集合），寫補回簽章鏈（restore_chain.ndjson）。
     正控制用 --positive-root（NO_GC 跑出的格）。
  2. 重算 c0 標記（b24）→ c0/flags_v2.json（`expT_reflag.py --write`，不用答案鍵）。
  3. B33(1)：一致性檢查必須 0（`expT_flagcheck.py`）。
  4. B27：量具缺口名單（無法補回頁 ≥1；補回後頁面集合 ≠ 伺服器集合；網址缺口 >0），只用 c0 的紀錄；寫 sha256。
  5. 建回饋 root：每台把 cells/<組>/r1、r2/c0 與 .live_secret 複製過去；回饋 root 裡 flags.json 換成 flags_v2.json
     （原檔改名 flags_v1_literal.json 保留）；寫 reused_c0_sha256.json（每個檔的 sha256）。
用法：expTc_prelaunch.py --drafts D1003 D1004 --fb F1003 F1004 --positive-root P --out OUT.json
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, shutil, subprocess, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))


def run(cmd):
    r = subprocess.run([sys.executable, *cmd], capture_output=True, text=True, cwd=REPO)
    if r.returncode != 0:
        raise SystemExit(f"step failed: {cmd}\n{r.stdout[-800:]}\n{r.stderr[-800:]}")
    return r.stdout


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--drafts", nargs=2, required=True); ap.add_argument("--fb", nargs=2, required=True)
    ap.add_argument("--positive-root", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); out = pathlib.Path(a.out); tmp = out.parent
    droots = [pathlib.Path(x) for x in a.drafts]; froots = [pathlib.Path(x) for x in a.fb]
    rep = {}
    # 0. B37(1)(2)：30 組 × r1、r2 共 60 份 c0 都有 done.json、沒有 infra_void；這 60 份的 B16 (a)–(e) 越界與網路掃描為 0
    plan_d = json.loads((REPO / "ops/d2/plans/expTc_drafts_qwen9b.json").read_text())
    sets = [f"{m['prefix']}-{x}" for m in plan_d["materials"] for x in m["sets"]]
    missing, void = [], []
    for sid in sets:
        for rp in (1, 2):
            c0 = next((d / "cells" / sid / f"r{rp}" / "c0" for d in droots if (d / "cells" / sid / f"r{rp}" / "c0" / "done.json").is_file()), None)
            if c0 is None:
                missing.append(f"{sid}/r{rp}"); continue
            if json.loads((c0 / "done.json").read_text()).get("infra_void"):
                void.append(f"{sid}/r{rp}")
    sys.path.insert(0, str(HERE))
    from ops.d2 import expTc_confirm_analysis as A
    d2 = str(droots[0].parent); esc, infra, scanned = [], [], 0
    for d in droots:
        for k, v in A.scan_runs(d, d2).items():
            if k[2] == "c0" and k[1] in (1, 2):
                scanned += 1
                if v["escape"]:
                    esc.append({"key": list(k), "kinds": v["escape_kinds"], "unlogged": v["unlogged_server_200"]})
                if v["infra"]:
                    infra.append(list(k))
    rep["b37"] = {"expected_c0": 2 * len(sets), "missing": missing, "infra_void_done_json": void, "scanned_c0_runs": scanned,
                  "escape_runs": esc, "infra_runs_by_scan": infra}
    if missing or void or esc or infra:
        out.write_text(json.dumps(rep, ensure_ascii=False, indent=1)); print(json.dumps(rep, ensure_ascii=False)[:2000]); return 1
    # 1. B25
    run([str(HERE / "expT_b25.py"), *map(str, droots), "--positive-root", a.positive_root, "--write-chain", "--json", str(tmp / "b25_final.json")])
    b25 = json.loads((tmp / "b25_final.json").read_text())
    s = b25["summary"]; rep["b25"] = s
    hard_b25 = s["sha_map_failures"] == 0 and s["positive_control_pass"]
    # 2. reflag
    for d in droots:
        run([str(HERE / "expT_reflag.py"), str(d), "--write", "--mode", "b24", "--json", str(tmp / f"reflag_{d.name}.json")])
    # 3. B33(1)
    run([str(HERE / "expT_flagcheck.py"), *map(str, droots), "--json", str(tmp / "flagcheck_confirm_final.json")])
    fc = json.loads((tmp / "flagcheck_confirm_final.json").read_text())
    rep["b33_inconsistent"] = fc["b33_inconsistent"]; rep["b32_supplement_note"] = "see ops/d2 supplementary invariance in appendix"
    hard_b33 = len(fc["b33_inconsistent"]) == 0
    # 4. B27 suspicious list (c0 records only)
    susp = set()
    for c in b25["cells"]:
        if c["unrestorable_pages"] or not c["recorded_eq_server"]:
            susp.add((c["set"], int(str(c["rep"]).lstrip("r"))))
    d2 = str(droots[0].parent)
    for d in droots:
        runs = A.scan_runs(d, d2)
        for k, v in runs.items():
            if k[2] == "c0" and v.get("requested_own_pages", 0) - v.get("egress_own_pages_200", 0) > 0:
                susp.add((k[0], k[1]))
    sl = sorted(map(list, susp)); blob = json.dumps(sl).encode()
    rep["b27_suspicious_pairs_all_reps"] = sl; rep["b27_sha256"] = hashlib.sha256(blob).hexdigest()
    (tmp / "b27_suspicious.json").write_bytes(blob)
    if not (hard_b25 and hard_b33):
        rep["hard_gates"] = {"b25": hard_b25, "b33": hard_b33}
        out.write_text(json.dumps(rep, ensure_ascii=False, indent=1)); print(json.dumps(rep, ensure_ascii=False)[:2000]); return 1
    # 5. fb roots
    plan = json.loads((REPO / "ops/d2/plans/expTc_fb_qwen9b.json").read_text())
    reuse = plan.get("reuse_c0_from", {}).get("reps", [1, 2])
    for d, f in zip(droots, froots):
        if f.exists():
            raise SystemExit(f"fb root already exists: {f}")
        (f / "cells").mkdir(parents=True)
        shutil.copy2(d / ".live_secret", f / ".live_secret")
        man = {"source_root": d.name, "files": {}}
        for c0 in sorted(d.glob("cells/*/r*/c0")):
            rp = int(c0.parts[-2][1:])
            if rp not in reuse or not (c0 / "done.json").is_file():
                continue
            dst = f / "cells" / c0.parts[-3] / c0.parts[-2] / "c0"
            shutil.copytree(c0, dst, symlinks=True)
            (dst / "flags.json").rename(dst / "flags_v1_literal.json")
            shutil.copy2(dst / "flags_v2.json", dst / "flags.json")
            for p in sorted(dst.rglob("*")):
                if p.is_file():
                    man["files"][str(p.relative_to(f / "cells"))] = sha(p)
            man["files"][f"{c0.parts[-3]}/{c0.parts[-2]}/c0/report.md"] = sha(dst / "report.md")
        (f / "reused_c0_sha256.json").write_text(json.dumps(man, indent=1))
        shutil.copy2(tmp / "b27_suspicious.json", f / "b27_suspicious.json")
        rep.setdefault("fb_roots", {})[f.name] = {"c0_copied": sum(1 for _ in f.glob("cells/*/r*/c0")), "manifest_sha256": sha(f / "reused_c0_sha256.json")}
    rep["hard_gates"] = {"b25": True, "b33": True}
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "b27_suspicious_pairs_all_reps"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
