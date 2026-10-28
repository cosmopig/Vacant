#!/usr/bin/env python3
"""noncode_cell_audit — 主軸 4 量具：從實驗格子的證據檔彙整「Vacant 在這一格實際做了什麼」（round 147）。

背景（為什麼需要這支）：
- ASSIGNMENT 主軸 4：「一般任務（dabstep/dabench/databench 是資料分析題）……有沒有實際的幫助；
  沒幫助就找出原因」。e001-dabstep 子集預註冊分析計畫（round 141，packets/e001_dabstep_analysis.md
  §4「機制診斷」）寫死：結果出來時，對每格 C 臂從證據檔讀 zero_ran / findings（kind+sub）／
  action=continue 的次數與 sent / advisory findings / A 臂對照（寫沒寫要求的檔、空檔、點名檔沒讀）。
- 本腳本是**獨立量具**：只讀 /srv/vlab/runs 下的 cell.json、score.json、delivery.json、
  app_final.tgz、vacant_home.tgz，不碰 cell.py / labd.py / report.py（與 disk_report.py 同一規矩）。
- 機制事實（round 141 盤點，`docs/UNIVERSAL_TASKS.md` + `trace/zerostop.py:pushable_for`）：
  Vacant 對非編碼任務**不判「答案內容對不對」**——隱藏 scorer 才是裁判；Vacant 只看紀錄
  （缺檔、空檔、數值無來源、點名檔沒讀、指令失敗）。可退回（會多跑一回合）的發現：
  missing_output、invalid_output/empty、unsourced、unread（≤1 回合）、failed_step/test_failed（≤1 回合）；
  其餘（copy_of_task、skeleton、stale_output、copy_of_input、copy_of_inline、claimed_run、
  unfetched、claimed_write）**只進交件說明，不退回**。本腳本只報「發生了什麼」，解讀照預註冊計畫 §5。

證據來源（每格）：
  cell.json                    arm/suite/task/rep/wall_s/metrics/vacant_sha/agent_rc/install_rc
  score.json                   pass（root 側 scorer；pass=None → infra）
  delivery.json（C 臂格根目錄） advisory findings、fixed、unverified、not_opened、deliverables
  app_final.tgz                交付工作區檔清單＋大小（空檔偵測；A/C 兩臂都讀）
  vacant_home.tgz（C 臂）      .vacant/trace/projects/*/zero_state.json（每回合 findings、open）
                              .vacant/intake/hooks/events.jsonl（stop 事件的 action/sent/withheld）

誠實規則：
  - 沒有 vacant_home.tgz 的 C 格 → zero_ran=None（**無證據**，不是「沒跑」）。
  - zero_state 的 open 欄位可能是字串也可能是 dict，兩種都接受、正常化為字串。
  - 本腳本**不判內容對錯**、不讀 /srv/eval、不做任何統計檢定（那是 report.py/預註冊計畫的活）。

用法：
  python3 ops/vlab/tools/noncode_cell_audit.py <exp> [--base /srv/vlab/runs] [--suite NAME]
      [--out PATH] [--table]
  python3 ops/vlab/tools/noncode_cell_audit.py --selftest

輸出 JSON：{exp, base, n_cells, cells:[...], pairs:[...], summary:{...}}
  pairs   ：同（suite,task,agent,rep）的 A/C 配對，含 discordant 方向與 C 臂介入摘要。
  summary ：n_pairs / a_only / c_only / C 臂 kickback 格數 / finding kind 計數（pushed+advisory）。
退出碼：0 正常；1 找不到任何 cell.json；2 selftest 失敗或輸入不可讀。
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path


def _tar_list(tgz: Path, pattern_prefix: str = "") -> list[tuple[str, int]]:
    """回 (arcname, size) 清單；tgz 不可讀 → []（誠實：無證據）。"""
    out = []
    try:
        with tarfile.open(tgz, "r:gz") as t:
            for m in t.getmembers():
                if m.isfile() and m.name.startswith(pattern_prefix):
                    out.append((m.name, m.size))
    except (OSError, tarfile.TarError):
        pass
    return out


def _read_tar_bytes(tgz: Path, arcname: str) -> bytes | None:
    try:
        with tarfile.open(tgz, "r:gz") as t:
            f = t.extractfile(arcname)
            if f is None:
                return None
            return f.read()
    except (OSError, tarfile.TarError):
        return None


def _read_tar_json(tgz: Path, arcname: str):
    raw = _read_tar_bytes(tgz, arcname)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return None


def _read_tar_jsonl(tgz: Path, arcname: str) -> list | None:
    """JSONL 成員 → list；不可讀/空 → None（誠實：無證據）。每行獨立解析，壞行跳過。"""
    raw = _read_tar_bytes(tgz, arcname)
    if raw is None:
        return None
    out = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _norm_open(items) -> list[str]:
    """zero_state 的 open 欄位：str 或 dict，統一成字串清單。"""
    out = []
    for it in items or []:
        if isinstance(it, str):
            out.append(it)
        elif isinstance(it, dict):
            out.append(it.get("kind") or it.get("finding_id") or json.dumps(it, ensure_ascii=False))
        else:
            out.append(repr(it))
    return out


def app_files(cell: Path) -> list[dict]:
    rows = _tar_list(cell / "app_final.tgz")
    # 去掉最上層目錄前綴（tgz 內是 app/... 或直接路徑）
    files = []
    for name, size in rows:
        parts = name.split("/", 1)
        files.append({"path": parts[1] if len(parts) > 1 else name, "size": size, "empty": size == 0})
    return files


def zero_profile(cell: Path) -> dict:
    """從 vacant_home.tgz 讀 C 臂的 zerostop 介入證據。沒有 tgz → 全 None（無證據）。"""
    tgz = cell / "vacant_home.tgz"
    prof: dict = {"home_present": tgz.is_file(), "zero_ran": None, "n_rounds": None,
                  "findings": [], "open": [], "kickbacks": None, "sent_total": None,
                  "withheld_total": None, "final_action": None, "n_stop_events": None}
    if not tgz.is_file():
        return prof
    # zero_state.json：.vacant/trace/projects/<hash>/zero_state.json（hash 不固定，掃全數）
    n_rounds, findings, open_ = 0, [], []
    try:
        with tarfile.open(tgz, "r:gz") as t:
            members = [m.name for m in t.getmembers()
                       if m.name.startswith(".vacant/trace/projects/") and m.name.endswith("/zero_state.json")]
            for name in members:
                zs = _read_tar_json(tgz, name)
                if not isinstance(zs, dict):
                    continue
                for sname, sv in (zs.get("sessions") or {}).items():
                    if not isinstance(sv, dict):
                        continue
                    for r in sv.get("rounds") or []:
                        n_rounds += 1
                        for f in r.get("findings") or []:
                            if isinstance(f, dict):
                                findings.append({"round": r.get("round"), "kind": f.get("kind"),
                                                 "sub": f.get("sub"), "step": f.get("step"),
                                                 "cmd": f.get("cmd"), "file": f.get("file")})
                    open_ += _norm_open(sv.get("open"))
    except (OSError, tarfile.TarError):
        pass
    # hooks events.jsonl：stop 事件的 action / zero.sent / zero.withheld
    events = _read_tar_jsonl(tgz, ".vacant/intake/hooks/events.jsonl")
    n_stop, kick, sent, withheld, last_action = 0, 0, 0, 0, None
    if isinstance(events, list):
        for e in events:
            if not isinstance(e, dict) or e.get("event") != "stop":
                continue
            n_stop += 1
            last_action = e.get("action")
            if e.get("action") == "continue":
                kick += 1
            z = e.get("zero") or {}
            sent += int(z.get("sent") or 0)
            withheld += int(z.get("withheld") or 0)
    prof.update({"n_rounds": n_rounds if n_rounds else (0 if zero_state_present(tgz) else None),
                 "findings": findings, "open": open_,
                 "kickbacks": kick if n_stop else None,
                 "sent_total": sent if n_stop else None,
                 "withheld_total": withheld if n_stop else None,
                 "final_action": last_action, "n_stop_events": n_stop})
    # zero_ran：有任何 stop 事件帶 zero_ran=true、或 zero_state 有 rounds → true；
    # 有 stop 事件但全無 zero 欄 → false；連 stop 事件都沒有 → None（無證據）
    ran = None
    if isinstance(events, list):
        ran = any(isinstance(e, dict) and e.get("event") == "stop" and e.get("zero_ran") for e in events)
    if ran is None and n_rounds:
        ran = True
    prof["zero_ran"] = ran
    return prof


def zero_state_present(tgz: Path) -> bool:
    """zero_state 檔存在過（決定 0 rounds 要不要記成 0 而不是 None）。"""
    names = _tar_list(tgz, ".vacant/trace/projects/")
    return any(n.endswith("/zero_state.json") for n, _ in names)


def delivery_profile(cell: Path) -> dict | None:
    p = cell / "delivery.json"
    if not p.is_file():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {
        "present": True,
        "in_progress": d.get("in_progress"),
        "deliverables": d.get("deliverables") or [],
        "not_opened": d.get("not_opened") or [],
        "fixed": d.get("fixed") or [],
        "unverified": d.get("unverified") or [],
        "advisory_findings": [
            (f.get("kind") if isinstance(f, dict) else f)
            for f in (d.get("findings") or [])
        ],
    }


def cell_record(cell: Path) -> dict | None:
    cj = cell / "cell.json"
    if not cj.is_file():
        return None
    try:
        info = json.loads(cj.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SystemExit(f"cell.json 不可讀：{cj}: {e}")
    rec: dict = {
        "cell": info.get("cell") or cell.name,
        "arm": info.get("arm"), "suite": info.get("suite"), "task": info.get("task"),
        "rep": info.get("rep"), "agent": info.get("agent"),
        "pass": None, "wall_s": info.get("wall_s"), "timed_out": info.get("timed_out"),
        "agent_rc": info.get("agent_rc"), "install_rc": info.get("install_rc"),
        "vacant_sha": info.get("vacant_sha"),
        "model_calls": (info.get("metrics") or {}).get("model_calls"),
        "tokens": (lambda m: (m.get("input_tokens") or 0) + (m.get("output_tokens") or 0))
                   (info.get("metrics") or {}),
        "app_files": None, "empty_app_files": [],
        "zero": None, "delivery": None,
    }
    sc = cell / "score.json"
    if sc.is_file():
        try:
            rec["pass"] = json.loads(sc.read_text(encoding="utf-8")).get("pass")
        except (OSError, ValueError):
            pass
    af = app_files(cell)
    rec["app_files"] = af
    rec["empty_app_files"] = [f["path"] for f in af if f["empty"]]
    if (info.get("arm") or "") == "C":
        rec["zero"] = zero_profile(cell)
        rec["delivery"] = delivery_profile(cell)
    return rec


def collect(exp: str, base: Path, suite: str | None) -> list[dict]:
    root = base / exp
    if not root.is_dir():
        raise SystemExit(f"實驗目錄不存在：{root}")
    recs = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if ".infra-" in d.name:
            continue  # 已重跑的保留失敗格：不進對照（與 report.py 同規矩）
        r = cell_record(d)
        if r is None:
            continue
        if suite and r["suite"] != suite:
            continue
        recs.append(r)
    return recs


def pair(records: list[dict]) -> list[dict]:
    by_key: dict[tuple, dict] = {}
    for r in records:
        key = (r["suite"], r["task"], r["agent"], r["rep"])
        by_key.setdefault(key, {})[r["arm"]] = r
    pairs = []
    for key in sorted(by_key, key=lambda k: (str(k[0]), str(k[1]))):
        arms = by_key[key]
        if "A" not in arms or "C" not in arms:
            continue
        a, c = arms["A"], arms["C"]
        if a["pass"] is None or c["pass"] is None:
            continue
        direction = None if a["pass"] == c["pass"] else ("A_only" if a["pass"] else "C_only")
        z = c["zero"] or {}
        pairs.append({
            "suite": key[0], "task": key[1], "A": bool(a["pass"]), "C": bool(c["pass"]),
            "direction": direction,
            "C_zero_ran": z.get("zero_ran"), "C_kickbacks": z.get("kickbacks"),
            "C_findings": [f"{f['kind']}/{f['sub']}" for f in z.get("findings", [])],
            "C_advisory": (c["delivery"] or {}).get("advisory_findings"),
            "A_empty_files": a["empty_app_files"], "C_empty_files": c["empty_app_files"],
            "wall_A": a["wall_s"], "wall_C": c["wall_s"],
        })
    return pairs


def summary(records: list[dict], pairs: list[dict]) -> dict:
    c_cells = [r for r in records if r["arm"] == "C"]
    pushed: dict[str, int] = {}
    advisory: dict[str, int] = {}
    n_kick = 0
    for r in c_cells:
        z = r["zero"] or {}
        if z.get("kickbacks"):
            n_kick += 1
        for f in z.get("findings", []):
            k = f"{f['kind']}/{f['sub']}"
            pushed[k] = pushed.get(k, 0) + 1
        for k in (r["delivery"] or {}).get("advisory_findings", []):
            advisory[k] = advisory.get(k, 0) + 1
    return {
        "n_cells": len(records),
        "n_C_cells": len(c_cells),
        "C_cells_no_home_evidence": sum(1 for r in c_cells if not (r["zero"] or {}).get("home_present")),
        "C_cells_zero_ran_true": sum(1 for r in c_cells if (r["zero"] or {}).get("zero_ran") is True),
        "C_cells_zero_ran_unknown": sum(1 for r in c_cells if (r["zero"] or {}).get("zero_ran") is None),
        "C_cells_with_kickback": n_kick,
        "pushed_finding_kinds": pushed,
        "advisory_finding_kinds": advisory,
        "n_pairs": len(pairs),
        "a_only": sum(1 for p in pairs if p["direction"] == "A_only"),
        "c_only": sum(1 for p in pairs if p["direction"] == "C_only"),
        "note": "本表只報機制發生的事實；『有/沒幫助』的解讀走預註冊計畫（packets/e001_dabstep_analysis.md §5），"
                "本腳本不判內容對錯、不做檢定",
    }


def render_table(exp: str, records: list[dict], pairs: list[dict], s: dict) -> str:
    L = [f"== {exp}（主軸 4：Vacant 在每格實際做了什麼；解讀照預註冊計畫）==",
         f"{'cell':<44}{'arm':<4}{'pass':<6}{'zero_ran':<9}{'kick':<5}{'findings（pushed）':<40}{'advisory':<20}",
         "-" * 118]
    for r in records:
        z = r["zero"] or {}
        pushed = ",".join(f"{f['kind']}/{f['sub']}" for f in z.get("findings", [])) or "-"
        adv = ",".join((r["delivery"] or {}).get("advisory_findings", [])) or "-"
        zr = {True: "yes", False: "no", None: "?"}[z.get("zero_ran")] if r["arm"] == "C" else "-"
        L.append(f"{r['cell']:<44}{r['arm'] or '?':<4}{str(r['pass']):<6}{zr:<9}"
                 f"{str(z.get('kickbacks') or '-'):<5}{pushed:<40}{adv:<20}")
    L.append("")
    L.append(f"配對（A/C 同題）：{s['n_pairs']} 對，A_only={s['a_only']}，C_only={s['c_only']}；"
             f"C 臂有 kickback 的格：{s['C_cells_with_kickback']}/{s['n_C_cells']}")
    for p in pairs:
        if p["direction"]:
            L.append(f"  [{p['direction']}] {p['task']}: C findings={p['C_findings'] or '-'} "
                     f"kick={p['C_kickbacks']} advisory={p['C_advisory'] or '-'} "
                     f"wall A/C={p['wall_A']}/{p['wall_C']}")
    return "\n".join(L) + "\n"


def _mk_tgz(path: Path, files: dict[str, str]) -> None:
    with tarfile.open(path, "w:gz") as t:
        for name, content in files.items():
            data = content.encode()
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            t.addfile(ti, io.BytesIO(data))


def selftest() -> int:
    """離線自測：假實驗（1 A 格＋2 C 格）→ 證據抽取斷言。失敗退出 2。"""
    ok = True
    def check(name: str, cond: bool) -> None:
        nonlocal ok
        if not cond:
            ok = False
            print(f"SELFTEST FAIL: {name}", file=sys.stderr)

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        expd = base / "exp_x"

        def cell(name: str, arm: str, task: str, passed: bool) -> Path:
            d = expd / name
            d.mkdir(parents=True)
            info = {"cell": name, "arm": arm, "exp": "exp_x", "suite": "dabstep",
                    "task": task, "agent": "pi", "rep": 1, "wall_s": 10.0,
                    "timed_out": False, "agent_rc": 0, "install_rc": 0,
                    "metrics": {"model_calls": 5, "input_tokens": 100, "output_tokens": 10}}
            if arm == "C":
                info["vacant_sha"] = "f" * 40
            (d / "cell.json").write_text(json.dumps(info))
            (d / "score.json").write_text(json.dumps({"pass": passed}))
            _mk_tgz(d / "app_final.tgz", {"app/out.csv": "a,b\n1,2\n", "app/empty.md": ""})
            return d

        a1 = cell("t1-pi-A-r1", "A", "t1", True)
        c1 = cell("t1-pi-C-r1", "C", "t1", False)
        c2 = cell("t2-pi-C-r1", "C", "t2", True)

        # C 格 c1：有 zero_state（1 回合 2 個 findings、open 含字串）、hooks 有 1 次 continue 1 次 allow、delivery.json
        zs = {"verified": {"seq": 1, "hash": "h"},
              "sessions": {"pi:s1": {
                  "rounds": [{"round": 1, "findings": [
                      {"finding_id": "z1", "kind": "failed_step", "sub": "test_failed", "step": 3,
                       "cmd": "python3 -m unittest"},
                      {"finding_id": "z2", "kind": "unsourced", "sub": "value", "file": "out.csv"}]}],
                  "open": ["unsourced/value"]}}}
        hooks = [
            {"ts": 1.0, "agent": "pi", "event": "stop", "kind": "stop", "action": "continue",
             "zero": {"ran": True, "round": 1, "sent": 2, "withheld": 0}, "zero_ran": True},
            {"ts": 2.0, "agent": "pi", "event": "stop", "kind": "stop", "action": "allow",
             "zero": {"ran": True, "rounds_used": 1, "left_open": 0}, "zero_ran": True},
            {"ts": 3.0, "agent": "pi", "event": "session_end", "kind": "session_end", "action": "allow"},
        ]
        _mk_tgz(c1 / "vacant_home.tgz", {
            ".vacant/trace/projects/h1/zero_state.json": json.dumps(zs),
            ".vacant/intake/hooks/events.jsonl": "\n".join(json.dumps(h) for h in hooks),
        })
        (c1 / "delivery.json").write_text(json.dumps({
            "in_progress": False, "deliverables": ["out.csv"], "not_opened": ["data.csv"],
            "fixed": ["round 1: step 3 had failed; the record now matches"], "unverified": [],
            "findings": [{"kind": "copy_of_inline", "sub": None}],
        }))

        # C 格 c2：zero 跑了但零 findings、無 delivery.json
        zs2 = {"sessions": {"pi:s2": {"rounds": [], "open": []}}}
        hooks2 = [{"ts": 1.0, "agent": "pi", "event": "stop", "action": "allow",
                   "zero": {"ran": True, "rounds_used": 0}, "zero_ran": True}]
        _mk_tgz(c2 / "vacant_home.tgz", {
            ".vacant/trace/projects/h2/zero_state.json": json.dumps(zs2),
            ".vacant/intake/hooks/events.jsonl": "\n".join(json.dumps(h) for h in hooks2),
        })

        recs = collect("exp_x", base, None)
        check("three cells", len(recs) == 3)
        by_name = {r["cell"]: r for r in recs}
        a = by_name["t1-pi-A-r1"]
        check("A: no zero profile", a["zero"] is None)
        check("A: empty file detected", a["empty_app_files"] == ["empty.md"])
        c1r = by_name["t1-pi-C-r1"]
        check("C1: zero_ran true", c1r["zero"]["zero_ran"] is True)
        check("C1: n_rounds 1", c1r["zero"]["n_rounds"] == 1)
        check("C1: 2 pushed findings", len(c1r["zero"]["findings"]) == 2)
        check("C1: kickbacks 1", c1r["zero"]["kickbacks"] == 1)
        check("C1: sent 2", c1r["zero"]["sent_total"] == 2)
        check("C1: final allow", c1r["zero"]["final_action"] == "allow")
        check("C1: open normalized", c1r["zero"]["open"] == ["unsourced/value"])
        check("C1: advisory kind", c1r["delivery"]["advisory_findings"] == ["copy_of_inline"])
        check("C1: not_opened", c1r["delivery"]["not_opened"] == ["data.csv"])
        c2r = by_name["t2-pi-C-r1"]
        check("C2: zero_ran true, 0 rounds", c2r["zero"]["zero_ran"] is True and c2r["zero"]["n_rounds"] == 0)
        check("C2: no delivery", c2r["delivery"] is None)

        pairs = pair(recs)
        check("one pair (t1 only)", len(pairs) == 1)
        check("pair direction A_only", pairs[0]["direction"] == "A_only")
        check("pair C findings", pairs[0]["C_findings"] == ["failed_step/test_failed", "unsourced/value"])
        s = summary(recs, pairs)
        check("summary kick cells", s["C_cells_with_kickback"] == 1)
        check("summary pushed kinds", s["pushed_finding_kinds"].get("failed_step/test_failed") == 1)
        check("summary advisory kinds", s["advisory_finding_kinds"].get("copy_of_inline") == 1)
        check("summary a_only", s["a_only"] == 1 and s["c_only"] == 0)
        t = render_table("exp_x", recs, pairs, s)
        check("table renders", "t1-pi-C-r1" in t and "A_only" in t)

        # 無證據的 C 格（沒有 vacant_home.tgz）→ zero_ran=None
        c3 = cell("t3-pi-C-r1", "C", "t3", False)
        recs3 = collect("exp_x", base, None)
        by3 = {r["cell"]: r for r in recs3}
        check("C3: no evidence -> None", by3["t3-pi-C-r1"]["zero"]["zero_ran"] is None)
        check("C3: home_present false", by3["t3-pi-C-r1"]["zero"]["home_present"] is False)

    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("exp", nargs="?", help="實驗名（/srv/vlab/runs 下的目錄）")
    ap.add_argument("--base", default="/srv/vlab/runs", help="runs 根目錄（預設 /srv/vlab/runs）")
    ap.add_argument("--suite", help="只取指定 suite（如 dabstep）")
    ap.add_argument("--out", help="JSON 另存路徑")
    ap.add_argument("--table", action="store_true", help="印人讀表格（另有 JSON 到 stdout/--out）")
    ap.add_argument("--selftest", action="store_true", help="離線自測後退出")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.exp:
        ap.error("需要 <exp>（或 --selftest）")
    recs = collect(a.exp, Path(a.base), a.suite)
    if not recs:
        print(f"找不到任何 cell.json：{Path(a.base) / a.exp}（--suite={a.suite}）", file=sys.stderr)
        return 1
    pairs = pair(recs)
    s = summary(recs, pairs)
    out = {"exp": a.exp, "base": str(a.base), "suite": a.suite, **s, "cells": recs, "pairs": pairs}
    txt = json.dumps(out, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).write_text(txt + "\n", encoding="utf-8")
    if a.table:
        sys.stdout.write(render_table(a.exp, recs, pairs, s))
        print(txt, file=sys.stderr)
    else:
        print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
