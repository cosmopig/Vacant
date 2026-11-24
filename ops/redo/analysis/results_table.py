"""結果總表產生器（2026-11-22，vacant-hope 要求）：要給人看的總表直接從來源生出來，不手抄。

來源（只讀檔，不呼叫 redo.py status）：
- ops/redo/results/batches.json：要列哪些批次、各屬哪一段、REPORT／run root／進度來源在哪（**只放路徑，不放數字**）。
- 各批的 REPORT.json（已結案：ops/redo/results/*_REPORT.json，與 redo.py report 產出的同一份）。
- 計畫檔 ops/redo/plans/*.json（依 REPORT 的 plan_id 或 manifest 的 plan_id 找）：題庫、題數×重複、agent、模型、後端、jobs、產品臂 wheel 雜湊。
- 後端速度：ops/redo/analysis/turn_latency.py 的 measure(run_root)；run root 不在這台機器上就讀上一次的快取
  ops/redo/results/speed_cache.json（以 REPORT 的 sha256 為鍵，報告變了快取就失效）。
- 結論檔：decisions/conclusions/*.md 裡提到該 REPORT 檔名或 plan_id 的檔。
- 進行中：只顯示進度（本機 run root 數兩臂都有 cell.json 的對；Colab 讀 keepalive.log 最新的「N/M 對」），不顯示通過數。

用法：python3 ops/redo/analysis/results_table.py [--out docs/RESULTS_TABLE.md] [--no-speed]
每批結案後：把它的 REPORT.json 複製進 ops/redo/results/、在 batches.json 把那一列改成 closed，重跑一次。
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RES = os.path.join(ROOT, "ops", "redo", "results")
PLANS = os.path.join(ROOT, "ops", "redo", "plans")
CONCL = os.path.join(ROOT, "decisions", "conclusions")
CACHE = os.path.join(RES, "speed_cache.json")


def _x(p: str | None) -> str | None:
    return os.path.expanduser(p) if p else None


def _load_turn_latency():
    spec = importlib.util.spec_from_file_location("turn_latency", os.path.join(os.path.dirname(__file__), "turn_latency.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _plans_by_id() -> dict:
    """id → (檔, 計畫)；同一個 id 有多份（例如範本）時留題數多的那份；另外以 sha256 為鍵存一份（REPORT 的 plan_sha256 優先）。"""
    out = {}
    for f in glob.glob(os.path.join(PLANS, "*.json")):
        if f.endswith(".selection.json"):
            continue
        try:
            d = json.load(open(f))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and "id" in d:
            out["sha:" + hashlib.sha256(open(f, "rb").read()).hexdigest()] = (f, d)
            if d["id"] not in out or len(d.get("tasks") or []) > len(out[d["id"]][1].get("tasks") or []):
                out[d["id"]] = (f, d)
    return out


def _file_sha8(path: str) -> str | None:
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()[:8]
    except OSError:
        return None


def _arm_wheel(arm: dict, raw: str) -> str | None:
    """產品臂實際用的 wheel（從臂的結構欄位取，不從全文抓第一個雜湊）：
    - argv[0] 是本機 venv 的 vacant ⇒ 讀那個 venv 裡 vacant_network 的 direct_url.json（pip 記下的 wheel sha256）；editable ⇒ 本機 checkout。
    - argv[0] 在 /opt/redo/（Colab VM，由 launch_batch --extra-wheel 裝）⇒ 計畫裡寫明的 .whl 檔，重算它的 sha256（只認存在的檔，多個不同就全列）。
    - 裸 `vacant` ⇒ 當時 PATH 上的本機 checkout。
    不是產品臂（沒有 vacant do）⇒ None。"""
    argv = (arm.get("agent") or {}).get("argv") or []
    if len(argv) < 2 or os.path.basename(argv[0]) != "vacant" or argv[1] != "do":
        return None
    exe = os.path.expanduser(argv[0])
    if exe == "vacant":
        return "（本機 checkout）"
    if exe.startswith("/opt/redo/"):
        shas = sorted({h for h in (_file_sha8(os.path.expanduser(w)) for w in re.findall(r"(~?/[^\s：，；（）\"']+\.whl)", raw)) if h})
        if not shas:  # 計畫寫的是 dist 目錄（~/dev/ops/rcN_dist）：重算目錄裡那個 wheel
            for d in sorted(set(re.findall(r"(~/dev/ops/rc\d+_dist)", raw))):
                shas += [h for h in (_file_sha8(w) for w in glob.glob(os.path.join(os.path.expanduser(d), "*.whl"))) if h]
            shas = sorted(set(shas))
        if shas:
            return "／".join(shas)
        m = re.search(r"wheel sha256 ([0-9a-f]{8})", raw)  # 最後才用計畫文字裡寫明的 P 臂 wheel 雜湊（標出來）
        return f"{m.group(1)}（計畫文字）" if m else "（VM wheel，計畫未寫）"
    venv = os.path.dirname(os.path.dirname(exe))
    for du in glob.glob(os.path.join(venv, "lib", "python*", "site-packages", "vacant_network-*.dist-info", "direct_url.json")):
        try:
            d = json.load(open(du))
        except (OSError, ValueError):
            continue
        if (d.get("dir_info") or {}).get("editable"):
            return "（本機 checkout）"
        h = ((d.get("archive_info") or {}).get("hashes") or {}).get("sha256") or (d.get("archive_info") or {}).get("hash", "").split("=")[-1]
        if h:
            return h[:8]
    m = re.fullmatch(r"(rc\d+)_venv", os.path.basename(venv))  # venv 已刪（dist 保留）：依同名 dist 目錄的 wheel，標出來
    if m:
        shas = sorted({h for h in (_file_sha8(w) for w in glob.glob(os.path.expanduser(f"~/dev/ops/{m.group(1)}_dist/*.whl"))) if h})
        if shas:
            return "／".join(shas) + f"（venv 已刪，依 {m.group(1)}_dist）"
    return f"（{os.path.basename(venv)}：讀不到 wheel 紀錄）"


def _plan_facts(plan: dict, raw: str) -> dict:
    bank = (plan.get("prereg") or {}).get("bank_name") or plan.get("bank", "")
    if bank.startswith("/srv/"):  # Colab：題庫在 VM 上的固定位置，真名看計畫 id／選題
        bank = "（Colab 題庫：發射時指定）"
    bank = os.path.basename(bank.rstrip("/")) if "/" in bank else bank
    prov = (plan.get("providers") or [{}])[0]
    ctrl, treat = (plan.get("arms") or {}).get(plan["pair"][0], {}), (plan.get("arms") or {}).get(plan["pair"][1], {})
    base_agent = (plan.get("agent") or {}).get("argv", ["?"])[0]

    def arm_desc(a: dict) -> str:
        if "agent" in a:
            argv = a["agent"]["argv"]
            if len(argv) > 2 and os.path.basename(argv[0]) == "vacant" and argv[1] == "do":
                at = argv[argv.index("--attempt-timeout") + 1] if "--attempt-timeout" in argv else None
                return f"vacant do {argv[2]}" + (f"（單次 {at}s）" if at else "")
            return os.path.basename(argv[0])
        if a.get("policy") == "restart":
            return f"harness 重開×{a.get('max_attempts', '?')}"
        return f"原生 {base_agent}"

    wheel = _arm_wheel(treat, raw) or _arm_wheel(ctrl, raw)
    host = prov.get("name", "?")
    backend = {"colab": "Colab vLLM", "lms1003": "1003 llama.cpp", "lms1004": "1004 llama.cpp"}.get(host, host)
    if host == "colab":
        gpu = "A100" if "a100" in plan["id"] else "L4"
        backend = f"Colab {gpu} vLLM"
    return {
        "bank": bank, "n": f"{len(plan.get('tasks', []))}×{plan.get('reps', '?')}",
        "arms": f"{arm_desc(ctrl)} 對 {arm_desc(treat)}",
        "model": prov.get("model", "?"), "backend": f"{backend} j{prov.get('jobs', '?')}",
        "wheel": wheel or "—",
    }


def _colab_state(e: dict) -> dict | None:
    """Colab 批次的 state.json（launch_batch 寫的：bank_local、gpu）；在 run root 的上一層或 keepalive.log 旁邊。"""
    for p in (e.get("run_root"), e.get("keepalive")):
        p = _x(p)
        if not p:
            continue
        f = os.path.join(os.path.dirname(p.rstrip("/")), "state.json")
        if os.path.exists(f):
            try:
                return json.load(open(f))
            except (OSError, ValueError):
                return None
    return None


def _conclusions(keys: list[str]) -> list[str]:
    hits = []
    for f in sorted(glob.glob(os.path.join(CONCL, "*.md"))):
        try:
            s = open(f, encoding="utf-8").read()
        except OSError:
            continue
        if any(k and k in s for k in keys):
            hits.append(os.path.relpath(f, ROOT))
    return hits


def _speed(report_path: str, run_root: str | None, cache: dict, tl, use: bool) -> dict | None:
    sha = hashlib.sha256(open(report_path, "rb").read()).hexdigest()
    if use and run_root and os.path.isdir(run_root):
        m = tl.measure(run_root)
        val = {"turn_mean": m["turn_latency_s"]["all"]["mean"], "turn_median": m["turn_latency_s"]["all"]["median"],
               "turn_p90": m["turn_latency_s"]["all"].get("p90"), "p_cap_rate": m["p_inner_cap"]["rate"],
               "a_median_wall": m["control_single_run"]["median_wall_s"], "a_timeouts": m["control_single_run"]["timeouts"],
               "a_cells": m["control_single_run"]["cells"]}
        cache[sha] = val
        return val
    return cache.get(sha)


def _progress(entry: dict) -> str:
    if entry.get("keepalive") and os.path.exists(_x(entry["keepalive"])):
        last = None
        for line in open(_x(entry["keepalive"]), errors="replace"):
            m = re.search(r"(\d+)/(\d+) 對", line)
            if m:
                last = f"{m.group(1)}/{m.group(2)} 對"
        return last or "已發射、尚無進度"
    root = _x(entry.get("run_root"))
    if root and os.path.exists(os.path.join(root, "runner.log")):
        # 從 runner.log 算（不手寫）：每一格一行「task/rN/arm … pass=…」，兩臂都有的才算一對完成；最後一行「完成 N/M 對」若有就用它
        arms: dict = {}
        last = None
        for line in open(os.path.join(root, "runner.log"), errors="replace"):
            m = re.search(r"\s(\S+)/r(\d+)/(\S+)\s+pass=", line)
            if m:
                arms.setdefault((m.group(1), m.group(2)), set()).add(m.group(3))
            t = re.search(r"完成 (\d+)/(\d+) 對", line)
            if t:
                last = f"{t.group(1)}/{t.group(2)} 對（runner.log）"
        done = sum(1 for v in arms.values() if len(v) >= 2)
        return last or f"{done} 對完成（runner.log）"
    if root and os.path.isdir(root):
        arms: dict = {}
        for cj in glob.glob(os.path.join(root, "cells", "*", "r*", "*", "cell.json")):
            parts = cj.split(os.sep)
            arms.setdefault((parts[-4], parts[-3]), set()).add(parts[-2])
        done = sum(1 for v in arms.values() if len(v) >= 2)
        return f"{done} 對完成"
    return entry.get("status_text", "未發射")


def _fmt(v, suf=""):
    return "—" if v is None else f"{v}{suf}"


def build(use_speed: bool = True) -> str:
    man = json.load(open(os.path.join(RES, "batches.json")))
    plans = _plans_by_id()
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    tl = _load_turn_latency() if use_speed else None
    closed, other = [], []
    for e in man["batches"]:
        rep = json.load(open(os.path.join(RES, e["report"]))) if e.get("report") else None
        pid = (rep or {}).get("plan_id") or e.get("plan_id")
        pf, plan = plans.get("sha:" + (rep or {}).get("plan_sha256", ""), None) or plans.get(pid, (None, None))
        facts = _plan_facts(plan, open(pf).read()) if plan else {k: "—" for k in ("bank", "n", "arms", "model", "backend", "wheel")}
        st = _colab_state(e)
        if st:
            facts["bank"] = os.path.basename(st.get("bank_local", "").rstrip("/")) or facts["bank"]
            if st.get("gpu"):
                facts["backend"] = re.sub(r"Colab \S+ vLLM", f"Colab {st['gpu']} vLLM", facts["backend"])
        if rep and facts["n"].startswith("0×"):
            facts["n"] = f"{len(rep.get('per_task') or [])}×{facts['n'].split('×')[1]}"
        concl = _conclusions([os.path.basename(e["report"]).replace(".json", "") if e.get("report") else None, pid]) \
            if e["category"] == "closed" else []
        links = "、".join(f"[{os.path.basename(c)}]({os.path.relpath(os.path.join(ROOT, c), os.path.join(ROOT, 'docs'))})"
                         for c in concl) or "—"
        if e["category"] == "closed":
            ctrl, treat = rep["control"], rep["treatment"]
            pa, pr = rep["per_arm"][ctrl], rep["per_arm"][treat]
            pdd = rep.get("paired") or {}
            abw = (pa.get("accepted_but_wrong") or 0) + (pr.get("accepted_but_wrong") or 0)
            sp = _speed(os.path.join(RES, e["report"]), _x(e.get("run_root")), cache, tl, use_speed)
            spd = "—" if not sp else (f"每輪 {_fmt(sp['turn_median'])}／{_fmt(sp['turn_mean'])}／{_fmt(sp['turn_p90'])} s；"
                                      f"P 撞上限 {_fmt(None if sp['p_cap_rate'] is None else round(sp['p_cap_rate'] * 100), '%')}；"
                                      f"A 中位 {_fmt(sp['a_median_wall'], 's')}、逾時 {sp['a_timeouts']}/{sp['a_cells']}")
            flag = "（harness 中途變更）" if rep.get("harness_changed_mid_run") else ""
            voids = rep.get("pairs_infra_void") or []
            vnote = f"（{len(voids)} 對 infra_void 不計）" if voids else ""
            closed.append(f"| {e['name']} | {facts['bank']} {facts['n']} | {facts['arms']} | {facts['model']}／{facts['backend']} | "
                          f"{facts['wheel']} | {pa['pass']}/{pa['scored']} → {pr['pass']}/{pr['scored']}{vnote} | "
                          f"{_fmt(pdd.get('control_only_b'))}／{_fmt(pdd.get('treatment_only_c'))}／{_fmt(pdd.get('mcnemar_exact_p_two_sided'))} | "
                          f"**{rep['state']}**{flag} | {abw} | {spd} | {links} |")
        else:
            label = {"running": "進行中", "queued": "排隊中", "void": "作廢", "withdrawn": "撤回"}[e["category"]]
            prog = _progress(e) if e["category"] in ("running", "queued") else "—"
            note = e.get("note", "")
            doc = e.get("doc")
            doc_l = f"[{os.path.basename(doc)}]({os.path.relpath(os.path.join(ROOT, doc), os.path.join(ROOT, 'docs'))})" if doc else "—"
            other.append(f"| {e['name']} | {label} | {facts['bank']} {facts['n']} | {facts['arms']} | "
                         f"{facts['model']}／{facts['backend']} | {facts['wheel']} | {prog} | {note} | {doc_l} |")
    if use_speed:
        with open(CACHE, "w") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    out = [
        "# Vacant 量測結果總表",
        "",
        f"> 由 `ops/redo/analysis/results_table.py` 從各批 REPORT.json、計畫檔與 run root 直接產生（{now}）。**不要手改**；"
        "要改內容就改來源或 `ops/redo/results/batches.json`，再重跑。",
        "> 引用規則照 REPORT 的 quoting_rule：只有 state=EFFECTIVE 且沒有 harness 中途變更的整批數字可以引用，"
        "引用時連同模型、agent、題庫、對數一起講；UNRESOLVED／INCOMPLETE 不是負結果。",
        "",
        "## 已結案",
        "",
        "通過數：對照 → 處理（各臂 通過/計分格數）。b＝只有對照過、c＝只有處理過、p＝精確雙尾 McNemar。"
        "後端速度：每輪模型回應 中位／平均／p90（秒）、處理臂內層撞單次上限的比例、對照臂單次的中位牆鐘與逾時數。"
        "「中位」是 turn_latency.py 的最近秩取法：n 為偶數時取上中位數（例如 confirm2 的 A 單次 300.1 秒，標準中位數 289.9 秒）；p90 同為最近秩。",
        "",
        "| 批次 | 題庫 題數×重複 | 對照 對 處理 | 模型／後端 | 產品 wheel | 通過數 | b／c／p | state | 放行卻錯 | 後端速度 | 結論 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
        *closed,
        "",
        "## 進行中／排隊／作廢／撤回",
        "",
        "進行中的批次只顯示進度，不顯示通過數（預註冊：跑完之前不看數字）。",
        "",
        "| 批次 | 狀態 | 題庫 題數×重複 | 對照 對 處理 | 模型／後端 | 產品 wheel | 進度 | 備註 | 文件 |",
        "|---|---|---|---|---|---|---|---|---|",
        *other,
        "",
    ]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "RESULTS_TABLE.md"))
    ap.add_argument("--no-speed", action="store_true", help="不重算後端速度，只用快取")
    a = ap.parse_args(argv)
    md = build(use_speed=not a.no_speed)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
