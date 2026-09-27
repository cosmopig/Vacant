#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BigCodeBench-Hard 題庫量具：每題參考解要全過、退化樁要被可見測試擋下（零模型呼叫）。

這支在架構裡承重什麼
--------------------
「判成 0 之前先證明量得動」：題庫裡每一題在拿去量 agent 之前，先用兩個已知答案的
輸入試過尺——

  * 參考解（BigCodeBench 官方組法 complete_prompt＋"\\n"＋canonical_solution）
    ⇒ 可見全過、隱藏全過（隱藏跑兩次，抓不穩的題）；
  * 退化樁 `def task_func(*a, **k): return None` ⇒ 可見至少一個失敗。

參考解過不了（缺函式庫、要網路、逾時、記憶體、本身不穩）⇒ 排除並具名記錄；
樁沒被擋 ⇒ 排除（可見測試太弱）。

**判準只有一份**：這支直接 import `vacant_network/vrun/acceptance.py` 與
`sandbox.py`（逐位元組同一份原始碼，sha256 寫進 manifest），呼叫
`acceptance.run_suite(...)` ——也就是閘門用的那一條
`python3 driver.py <ws> <testfile> <nonce>`。沒有另寫第二套判準。

與閘門預設設定不同之處（都是**量得動**的前提，manifest 逐字記錄）
------------------------------------------------------------------
1. `sandbox._clean_env` 的 PATH 前面加上 `<venv>/bin`——預設 PATH 寫死成
   `/usr/local/sbin:…:/bin`，在 vacant-dev 上 `python3`＝`/usr/bin/python3`，
   沒有 pandas，參考解一題都跑不起來。
2. `memory_bytes`（RLIMIT_AS）用 `--memory-mib`（預設 2048）——預設 512MiB 實測
   連 `import matplotlib` 都會 "failed to map segment from shared object"。
3. 後端用 `none`（實驗閘門 gateshim 固定 `sandbox_name="none"`）⇒ **有網路**。
   所以另做一次離線檢查：參考解在 `bwrap --unshare-all`（網路隔離；最小 rootfs 看不到
   `/var/tmp/.../venv`，所以把 venv 唯讀加進 `ro_binds`）再跑一次隱藏檔，失敗且是
   網路類訊息 ⇒ 排除（`network`）。
   ⇒ **實驗的閘門必須用同樣的 PATH 與記憶體設定**，否則這份量具結果不適用。

誠實邊界
--------
「參考解全過＋樁被擋」是**單邊**保證（`vacant_network/suitegauge.py` 那句逐字適用）：
擋得住 return None 不等於可見測試涵蓋真需求。

用法（在 vacant-dev）
--------------------
    venv/bin/python gauge_bank.py --root /var/tmp/vacant_piext_20260924/bcb
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import importlib.util
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import time
import types

STUB = "def task_func(*a, **k): return None\n"

#: 跨輪證據的人工排除（單一輪的自動規則看不到）。**每一條都要附證據出處**，
#: 而且只准往「排除」那一側用——不准拿來把自動規則排除的題救回來。
MANUAL_EXCLUDE = {
    "BigCodeBench/1040": ("flaky",
                          "跨輪不穩：參考解在網路隔離（bwrap）後端的隱藏檔，三輪量具 2 過 1 不過"
                          "（第二輪 ConnectionRefused／ConnectionReset，見 vacant-dev "
                          "logs/bank_manifest_run2.json）；none 後端全過。實驗的閘門與計分都包在 bwrap 裡"
                          " ⇒ 參考解有實測的失敗率 ⇒ 排除。另：單檔 60 秒"),
}

#: 自動分類之外，人讀過失敗訊息後補的具體說明（寫進 manifest 的 exclude_detail）。
#: **只補說明，不改自動分類的結果**——分類規則仍是 classify() 那一份。
KNOWN_DETAIL = {
    "BigCodeBench/101": ("參考解在 matplotlib 3.8 下 heatmap 的 QuadMesh.get_array() 回 2-D (13,13)，"
                         "測試期望 1-D (169,)（官方釘 matplotlib 3.7.0）；另一條測試從 lib.stat.cmu.edu "
                         "下載 Boston 資料集，整檔超過 120 秒"),
    "BigCodeBench/227": ("測試 test_spl_calculation 用了 `assertAlmostEquals`（Python 3.12 已移除的別名）"
                         "⇒ 在 3.12 上參考解必定 AttributeError；與解答無關，是測試檔本身與 3.12 不相容"),
    "BigCodeBench/461": "測試監看一個子行程直到它自己的逾時，整檔超過 120 秒",
    "BigCodeBench/590": "測試真的連到 en.wikibooks.org，對方回 HTTP 403（有網路也過不了）",
    "BigCodeBench/1012": "測試真的從 drive.google.com 下載；有網路時過、離線後端 NameResolutionError",
    "BigCodeBench/1085": ("參考解用了 `punctuation` 卻沒有 import；官方評測能過，只因為測試檔的 "
                          "`from string import punctuation` 與解答共用同一個命名空間。我們的解答是獨立模組 "
                          "⇒ NameError。自足的解不受影響，但參考解過不了 ⇒ 沒有正控制 ⇒ 排除"),
}

NETWORK_MARKERS = (
    "Temporary failure in name resolution", "Name or service not known",
    "Network is unreachable", "nodename nor servname", "Max retries exceeded",
    "ConnectionError", "URLError", "gaierror", "NewConnectionError",
    "Failed to establish a new connection",
    "getaddrinfo failed", "No address associated with hostname", "NameResolutionError",
)
MISSING_LIB_MARKERS = ("ModuleNotFoundError", "No module named", "cannot import name")
MEMORY_MARKERS = ("MemoryError", "Cannot allocate memory", "failed to map segment",
                  "OpenBLAS", "std::bad_alloc")


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_vrun(vrun_dir: pathlib.Path):
    """把 acceptance.py／sandbox.py 當成一個獨立套件載入（避開 vacant_network/__init__ 的依賴）。"""
    pkg = types.ModuleType("_vacant_vrun")
    pkg.__path__ = [str(vrun_dir)]
    sys.modules["_vacant_vrun"] = pkg
    mods = {}
    for name in ("sandbox", "acceptance"):
        spec = importlib.util.spec_from_file_location(f"_vacant_vrun.{name}", vrun_dir / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"_vacant_vrun.{name}"] = mod
        spec.loader.exec_module(mod)
        mods[name] = mod
    return mods["sandbox"], mods["acceptance"]


def tree_state(root: pathlib.Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            try:
                out[str(p.relative_to(root))] = sha256_file(p)
            except OSError:
                out[str(p.relative_to(root))] = "<unreadable>"
    return out


def failing_msgs(res: dict, limit: int = 6) -> list[str]:
    out = []
    for f in res.get("files", []):
        for c in f.get("cases", []):
            if not c.get("ok"):
                out.append(f"{c.get('case')} [{c.get('kind')}]: {(c.get('message') or '')[:400]}"
                           + (f" | output: {(c.get('output') or '')[-300:]}" if c.get("output") else ""))
    return out[:limit]


def all_text(res: dict) -> str:
    parts = []
    for f in res.get("files", []):
        parts.append(f.get("stderr_tail") or "")
        for c in f.get("cases", []):
            if not c.get("ok"):
                parts += [c.get("kind") or "", c.get("message") or "", c.get("output") or ""]
    return "\n".join(parts)


def summarize(res: dict) -> dict:
    files = res.get("files", [])
    return {
        "passed": res.get("passed"), "total": res.get("total"), "all_pass": res.get("all_pass"),
        "timed_out": any(f.get("timed_out") for f in files),
        "wall_ms": max([f.get("wall_ms") or 0 for f in files] or [0]),
        "result_sha256": res.get("result_sha256"),
        "failing": failing_msgs(res),
        "empty_reason": res.get("empty_reason"),
    }


def classify(ref_runs: list[dict], hidden_runs: list[dict]) -> str:
    """參考解沒全過的時候，理由歸哪一類（順序即優先序）。

    `flaky` 只看**同一個套件的重複執行**（隱藏跑兩次）結果不一致；
    可見過、隱藏不過不是不穩，是隱藏有一條本來就過不了。
    （`Connection refused` 刻意不算網路標記：localhost 的 socket 測試也會丟它。）
    """
    passes = [r["all_pass"] for r in hidden_runs]
    text = "\n".join(all_text(r) for r in ref_runs)
    if any(r.get("timed_out") for r in (summarize(x) for x in ref_runs)):
        return "timeout"
    if any(m in text for m in MISSING_LIB_MARKERS):
        return "missing_lib"
    if any(m in text for m in MEMORY_MARKERS):
        return "memory"
    if any(m in text for m in NETWORK_MARKERS):
        return "network"
    if any(passes) and not all(passes):
        return "flaky"
    return "reference_fails_other"


def gauge_one(t: dict, *, root: pathlib.Path, sb, acc, timeout_s: float, hidden_reps: int,
              sb_net=None) -> dict:
    d = t["dir"]
    bank = root / "bank"
    tpl = bank / "templates" / d
    hid = bank / "hidden" / d
    work = root / "gauge_work" / d
    shutil.rmtree(work, ignore_errors=True)
    rec: dict = {"dir": d, "task_id": t["task_id"]}
    t0 = time.time()
    for which, sol in (("reference", (root / "reference" / d / "solution.py").read_text(encoding="utf-8")),
                       ("stub", STUB)):
        ws = work / which / "ws"
        shutil.copytree(tpl, ws)
        (ws / "solution.py").write_text(sol, encoding="utf-8")
        before = tree_state(ws)
        runs = {"visible": [], "hidden": []}
        reps = {"visible": 1, "hidden": hidden_reps if which == "reference" else 1}
        for suite, sdir in (("visible", tpl / "tests_visible"), ("hidden", hid)):
            for _ in range(reps[suite]):
                res = acc.run_suite(sb, ws, sdir, suite=suite, task_id=d,
                                    verify_root=work / which / "_verify", timeout_s=timeout_s)
                runs[suite].append(res)
        after = tree_state(ws)
        rec[which] = {
            "visible": [summarize(r) for r in runs["visible"]],
            "hidden": [summarize(r) for r in runs["hidden"]],
            "ws_files_added": sorted(set(after) - set(before)),
            "ws_files_changed": sorted(k for k in before if k in after and before[k] != after[k]),
            "ws_files_removed": sorted(set(before) - set(after)),
        }
        rec[f"_{which}_raw"] = runs
    ref = rec["reference"]
    ref_ok = all(r["all_pass"] for r in ref["visible"] + ref["hidden"])
    # 離線檢查：主量具用 none 後端（＝閘門的後端，有網路）。參考解另外在一個
    # 網路隔離的後端（bwrap --unshare-all）再跑一次隱藏檔；那裡過不了而且訊息是
    # 網路類 ⇒ 這題的通過依賴外部伺服器 ⇒ 排除（結果會隨網路漂）。
    net_rec = None
    if sb_net is not None and ref_ok:
        ws = work / "netcheck" / "ws"
        shutil.copytree(tpl, ws)
        (ws / "solution.py").write_text((root / "reference" / d / "solution.py").read_text(encoding="utf-8"),
                                        encoding="utf-8")
        nres = acc.run_suite(sb_net, ws, hid, suite="hidden", task_id=d,
                             verify_root=work / "netcheck" / "_verify", timeout_s=timeout_s)
        net_rec = summarize(nres)
        net_rec["network_markers"] = any(m in all_text(nres) for m in NETWORK_MARKERS)
    rec["netcheck_offline_hidden"] = net_rec
    stub_blocked = not rec["stub"]["visible"][0]["all_pass"]
    stub_vis = rec["stub"]["visible"][0]
    stub_fail_n = (stub_vis["total"] or 0) - (stub_vis["passed"] or 0)
    reason = None
    if not ref_ok:
        reason = classify(rec["_reference_raw"]["visible"] + rec["_reference_raw"]["hidden"],
                          rec["_reference_raw"]["hidden"])
    elif net_rec is not None and not net_rec["all_pass"]:
        # 參考解在 none 後端全過、在離線後端又跑一次隱藏卻沒過：
        # 訊息是網路類 ⇒ 通過要靠外部伺服器（network）；
        # 不是網路類 ⇒ 同一份參考解同一個隱藏檔，換一次執行就不過 ⇒ 不穩（flaky）。
        reason = "network" if net_rec["network_markers"] else "flaky"
    elif not stub_blocked:
        reason = "stub_not_blocked"
    rec["offline_fail_non_network"] = bool(net_rec is not None and not net_rec["all_pass"]
                                           and not net_rec["network_markers"])
    rec.update({
        "reference_ok": ref_ok,
        "stub_blocked_visible": stub_blocked,
        "stub_visible_failed_cases": stub_fail_n,
        "stub_blocked_hidden": not rec["stub"]["hidden"][0]["all_pass"],
        "usable": reason is None,
        "exclude_reason": reason,
        "reference_max_file_wall_ms": max(r["wall_ms"] for r in ref["visible"] + ref["hidden"]),
        "gauge_seconds": round(time.time() - t0, 1),
    })
    rec.pop("_reference_raw")
    rec.pop("_stub_raw")
    shutil.rmtree(work, ignore_errors=True)
    return rec


def dir_size_bytes(p: pathlib.Path) -> int:
    out = subprocess.run(["du", "-sb", str(p)], capture_output=True, text=True)
    try:
        return int(out.stdout.split()[0])
    except Exception:
        return -1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="BCB-Hard 題庫量具（零模型呼叫）")
    ap.add_argument("--root", required=True, help="bcb 工作根（含 bank/ reference/ venv/ src/vrun/）")
    ap.add_argument("--backend", default="none",
                    help="主量具的沙箱後端；預設 none＝實驗閘門用的那一個（gateshim 固定 none）")
    ap.add_argument("--netcheck-backend", default="bwrap",
                    help="離線檢查用的網路隔離後端（空字串＝不做）")
    ap.add_argument("--memory-mib", type=int, default=2048)
    ap.add_argument("--timeout-s", type=float, default=120.0)
    ap.add_argument("--hidden-reps", type=int, default=2)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", nargs="*", default=None, help="只量這幾個 dir（偵錯用；不寫 manifest）")
    ap.add_argument("--prune", action="store_true",
                    help="把排除題的兩棵樹搬到 <root>/excluded/（題庫只留可用題）")
    a = ap.parse_args(argv)

    root = pathlib.Path(a.root).resolve()
    venv = root / "venv"
    vrun_dir = root / "src" / "vrun"
    sbx, acc = load_vrun(vrun_dir)

    orig_clean_env = sbx._clean_env

    def patched_clean_env(workspace):
        env = orig_clean_env(workspace)
        env["PATH"] = f"{venv / 'bin'}:{env['PATH']}"
        return env

    sbx._clean_env = patched_clean_env
    probe_dir = root / "gauge_work" / "_probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    sb, meta = sbx.make_sandbox(a.backend, workdir=str(probe_dir),
                                memory_bytes=a.memory_mib * 1024 * 1024)
    # bwrap 的最小 rootfs 只 ro-bind /usr /bin /lib /etc ⇒ venv 在沙箱裡不存在。
    # 每一次執行都把 venv 以唯讀加進 ro_binds（unshare／none 後端看得到整台機器，
    # ro_binds 對它們沒有作用——sandbox.py 自己的 docstring 就這樣寫）。
    orig_wrap = sb._wrap

    def wrap_with_venv(command, workspace, ro_binds=()):
        return orig_wrap(command, workspace, tuple(ro_binds) + (venv,))

    sb._wrap = wrap_with_venv
    sb_net, meta_net = None, None
    if a.netcheck_backend:
        sb_net, meta_net = sbx.make_sandbox(a.netcheck_backend, workdir=str(root / "gauge_work" / "_probe_net"),
                                            memory_bytes=a.memory_mib * 1024 * 1024)
        if not meta_net.get("network_isolated"):
            raise SystemExit(f"離線檢查後端 {a.netcheck_backend} 沒有網路隔離（{meta_net}）——量不動，停。")
        orig_wrap_net = sb_net._wrap

        def wrap_net_with_venv(command, workspace, ro_binds=()):
            return orig_wrap_net(command, workspace, tuple(ro_binds) + (venv,))

        sb_net._wrap = wrap_net_with_venv
        chk2 = sb_net.run("python3 -c 'import pandas; print(\"IMPORT_OK\")'",
                          workspace=root / "gauge_work" / "_probe_net", timeout_s=60)
        if "IMPORT_OK" not in chk2.stdout:
            raise SystemExit(f"離線檢查沙箱 import 不到函式庫，停。{chk2.stderr[-600:]!r}")
    # 驗「量得動」：沙箱裡的 python3 真的是 venv 那一支、import 得到 pandas。
    chk = sb.run("command -v python3; python3 -c 'import pandas, matplotlib, sklearn; print(\"IMPORT_OK\")'",
                 workspace=probe_dir, timeout_s=60)
    if "IMPORT_OK" not in chk.stdout:
        raise SystemExit(f"沙箱裡 import 不到函式庫——量不動，停。stdout={chk.stdout!r} stderr={chk.stderr[-600:]!r}")

    rm = json.loads((root / "bank" / "render_manifest.json").read_text(encoding="utf-8"))
    tasks = rm["tasks"]
    if a.only:
        tasks = [t for t in tasks if t["dir"] in set(a.only)]
    results: dict[str, dict] = {}
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(gauge_one, t, root=root, sb=sb, acc=acc, timeout_s=a.timeout_s,
                          hidden_reps=a.hidden_reps, sb_net=sb_net): t for t in tasks}
        for i, fu in enumerate(cf.as_completed(futs), 1):
            t = futs[fu]
            try:
                results[t["dir"]] = fu.result()
            except Exception as e:  # infra：量具自己壞 ≠ 題目壞，照實記
                results[t["dir"]] = {"dir": t["dir"], "task_id": t["task_id"], "usable": False,
                                     "exclude_reason": "gauge_infra_error",
                                     "error": f"{type(e).__name__}: {e}"}
            r = results[t["dir"]]
            print(f"[{i}/{len(tasks)}] {t['dir']:10s} usable={r.get('usable')} "
                  f"reason={r.get('exclude_reason')} wall={r.get('reference_max_file_wall_ms')}ms "
                  f"({time.time() - t0:.0f}s)", flush=True)

    if a.only:
        print(json.dumps(results, ensure_ascii=False, indent=1)[:20000])
        return 0

    per_task = []
    for t in rm["tasks"]:
        g = results[t["dir"]]
        if t["task_id"] in MANUAL_EXCLUDE and g.get("usable"):
            g["usable"] = False
            g["exclude_reason"], g["exclude_rule"] = MANUAL_EXCLUDE[t["task_id"]][0], "manual_cross_round"
        per_task.append({**{k: t[k] for k in ("task_id", "dir", "libs", "third_party_libs",
                                                 "n_methods_total", "n_visible", "n_hidden_only",
                                                 "visible_methods", "hidden_file_methods",
                                                 "duplicate_method_names", "reference_solution_sha256",
                                                 "test_upstream_sha256", "files_sha256")},
                         "gauge": {k: v for k, v in g.items() if k not in ("dir", "task_id")},
                         "usable": g.get("usable"), "exclude_reason": g.get("exclude_reason"),
                         "exclude_detail": ((MANUAL_EXCLUDE.get(t["task_id"], (None, None))[1]
                                             or KNOWN_DETAIL.get(t["task_id"])) if not g.get("usable") else None)})
    usable = [p["dir"] for p in per_task if p["usable"]]
    reasons: dict[str, list[str]] = {}
    for p in per_task:
        if not p["usable"]:
            reasons.setdefault(p["exclude_reason"], []).append(p["task_id"])
    for e in rm["policy_excluded"]:
        reasons.setdefault("policy_tensorflow_keras", []).append(e["task_id"])

    freeze = subprocess.run([str(venv / "bin" / "python"), "-m", "pip", "freeze"],
                            capture_output=True, text=True).stdout
    manifest = {
        **{k: rm[k] for k in ("bank", "dataset", "split", "source_url", "source_repo_sha",
                              "parquet_sha256", "n_upstream", "n_rendered", "split_rule",
                              "split_rule_sha256", "reference_solution_rule", "stub_solution",
                              "policy_excluded")},
        "gauge": {
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "host": platform.node(), "platform": platform.platform(),
            "judge": "acceptance.run_suite（python3 driver.py <ws> <testfile> <nonce>），與閘門同一份原始碼",
            "vrun_sources_sha256": {n: sha256_file(vrun_dir / f"{n}.py") for n in ("acceptance", "sandbox")},
            "backend_meta": {k: meta.get(k) for k in ("backend", "network_isolated", "write_confined",
                                                       "memory_bytes", "honest_bound", "tried")},
            "deviations_from_gate_defaults": {
                "PATH": f"{venv / 'bin'} 放在 _clean_env 的 PATH 最前面（預設 PATH 找到的是 /usr/bin/python3，沒有 pandas）",
                "memory_bytes": f"{a.memory_mib} MiB（預設 512 MiB 實測 import matplotlib 就 failed to map segment）",
                "timeout_s": f"{a.timeout_s}（每個測試檔；閘門 launcher 預設 10）",
                "backend": f"主量具 {a.backend}（＝實驗閘門）；離線檢查 {a.netcheck_backend or '不做'}，venv 以 ro_binds 唯讀掛入",
            },
            "netcheck_backend_meta": ({k: meta_net.get(k) for k in ("backend", "network_isolated", "write_confined",
                                                                     "memory_bytes")} if meta_net else None),
            "netcheck_rule": ("參考解在 none 後端全過之後，另在網路隔離的後端再跑一次隱藏檔；"
                              "失敗且訊息含網路類標記 ⇒ exclude_reason=network；失敗但沒有網路標記 ⇒ "
                              "exclude_reason=flaky（同一份參考解同一個隱藏檔換一次執行就不過）。"),
            "in_sandbox_python": chk.stdout.strip().splitlines()[0] if chk.stdout.strip() else None,
            "hidden_reps_reference": a.hidden_reps,
            "venv": str(venv), "venv_python": str(venv / "bin" / "python3"),
            "venv_bytes": dir_size_bytes(venv),
            "pip_freeze": freeze.splitlines(),
            "pip_freeze_sha256": hashlib.sha256(freeze.encode()).hexdigest(),
            "wall_seconds": round(time.time() - t0, 1),
        },
        "summary": {
            "n_rendered": len(per_task), "n_usable": len(usable),
            "n_excluded_total": len(per_task) - len(usable) + len(rm["policy_excluded"]),
            "exclude_reasons": {k: sorted(v, key=lambda s: int(s.split("/")[1])) for k, v in sorted(reasons.items())},
        },
        "usable_dirs": usable,
        "tasks": per_task,
    }
    text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    mp = root / "bank" / "bank_manifest.json"
    mp.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (root / "bank" / "bank_manifest.sha256").write_text(f"{digest}  bank_manifest.json\n", encoding="utf-8")
    print(f"usable {len(usable)}/{len(per_task)}（另政策排除 {len(rm['policy_excluded'])}）；"
          f"排除理由：{ {k: len(v) for k, v in reasons.items()} }")
    print(f"bank_manifest.json sha256 {digest}")

    if a.prune:
        ex_root = root / "excluded"
        for p in per_task:
            if p["usable"]:
                continue
            for sub in ("templates", "hidden"):
                src = root / "bank" / sub / p["dir"]
                if src.exists():
                    dst = ex_root / sub / p["dir"]
                    shutil.rmtree(dst, ignore_errors=True)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dst))
        print(f"已把排除題搬到 {ex_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
