#!/usr/bin/env python3
"""audit_v5_hint_delivery.py — v5 fresh_hint 治療組「投遞稽核」（離線、零模型調用）。

背景：v5 的 UNRESOLVED 判定（`ops/realrun/analyze_v5.json`）建立在預註冊
`prereg_v5.json` 的治療描述上——「C_fresh_hint3 與 B_resample3 的唯一差異＝
失敗後重抽前，工作區放一份 ≤380B 的真實失敗提示檔（VACANT_FEEDBACK.md），
由 agent 自讀進 prompt；control 的 launcher 永不寫該檔」。判定本身沒有錯，
但「治療真的被投遞了」是那個判定生效的邊界條件，此前沒有從落盤證據稽核過。
本腳本補上這一環。它不改 v5 的主分析（102 pairs 的 pooled McNemar 仍是唯一
判定），只回答：治療通道有沒有按預註冊的樣子走。

只讀落盤證據（run 摘要 JSON + 工作區檔 + wire log），零模型調用、離線可跑：

  D1 投遞介斷   wire 請求數 == attempts_used == 摘要 requests_seen（每個
                attempt 都有真實的模型通道證據，不是設定值）。
  D2 乾淨重置   每個 attempt k>=2 都從乾淨 origin 開始（reset.back_to_start
                且 reset.ws_sha256 == 第 1 attempt 的 ws_start_sha256）。
  D3 提示檔     treatment：attempts_used>=2 時 VACANT_FEEDBACK.md 存在、
                非空、<=380B、文字 == 最後一次寫入的提示（attempts[au-2].
                feedback.text）；attempts_used==1 時該檔不存在（沒失敗就不
                該有檔）。control：任何 cell 都不該有該檔（負對照）。
  D4 wire 內文  第 1 attempt 的請求體不含提示標記；treatment 每個 attempt
                k>=2 的請求體（JSON 解析後的 user content）逐字包含該次該
                看到的提示文字（attempts[k-2].feedback.text）；control 所有
                請求體都不含標記。這是「模型輸入真的含提示」的最強證據，
                比「工作區有檔」更硬。
  D5 prompt 同  同一 (rep, task) 下兩臂第 1 attempt 的 argv_sha256 相同——
                launcher 給的 prompt 逐位元組一致，兩臂的模型輸入差異只
                可能來自 agent 端追加的提示檔（正是預註冊聲稱的唯一差異）。

輸出：JSON 稽核檔（repo 鏡像 ops/realrun/audit_v5_hint_delivery.json）＋
stdout 摘要。退出碼：0 = 全部通過；1 = 有 anomaly；2 = 用法/讀檔錯誤。

另外附一個**描述性**子集統計（明確標註 out_of_prereg、decision_state=null）：
「treatment 真正用到提示」的那些 pair 上，control vs treatment 的接受數與
b/c。這不是新判定、不是新預註冊、不可引用為效應——它只是說 UNRESOLVED
的判定實際覆蓋了多少次「提示可能發揮作用」的機會。

Usage:
  python3 ops/realrun/audit_v5_hint_delivery.py \
      --prereg ops/realrun/prereg_v5.json \
      --roots <root_r1> <root_r2> <root_r3> [--json OUT]
  python3 ops/realrun/audit_v5_hint_delivery.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HINT_MARKER = "Previous attempt failed acceptance check:"
FEEDBACK_FILENAME = "VACANT_FEEDBACK.md"
MAX_HINT_BYTES = 380  # prereg_v5.json: hint <= 380 bytes


def _run_summary(root: Path, arm: str, task: str) -> Path:
    run_dir = root / arm / task / "run"
    files = [f for f in sorted(run_dir.glob("run_*.json")) if "receipts" not in f.name]
    if not files:
        raise FileNotFoundError(f"no run summary under {run_dir}")
    return files[0]


def _wire_bodies(root: Path, arm: str, task: str) -> list[bytes]:
    """Wire 請求體，按時間序（ts 升冪）。"""
    wire = root / arm / task / "run" / "wire_RUN-ON"
    idx = [json.loads(l) for l in (wire / "index.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    idx.sort(key=lambda e: e["ts"])
    out = []
    for e in idx:
        out.append((wire / (e["call_id"] + ".req.bin")).read_bytes())
    return out


def _user_contents(body: bytes) -> list[str]:
    """請求體是標準 chat-completion JSON；回所有 user message 的 content 字串。"""
    doc = json.loads(body)
    out = []
    for m in doc.get("messages", []):
        c = m.get("content")
        if m.get("role") == "user" and isinstance(c, str):
            out.append(c)
    return out


def audit_cell(root: Path, arm: str, task: str, *, is_treatment: bool) -> dict:
    """單一 cell 的投遞稽核。回 {"pass": bool, "checks": {...}, "anomalies": [...]}。"""
    anomalies: list[str] = []
    s = json.loads(_run_summary(root, arm, task).read_text(encoding="utf-8"))
    attempts = s.get("attempts") or []
    au = s.get("attempts_used")
    n_req = s.get("requests_seen")

    bodies = _wire_bodies(root, arm, task)
    checks: dict = {}

    # D1 投遞介斷
    d1 = len(bodies) == au == n_req and au is not None
    checks["D1_mediation"] = {"pass": bool(d1),
                              "wire_requests": len(bodies), "attempts_used": au,
                              "requests_seen": n_req}
    if not d1:
        anomalies.append(f"D1: wire={len(bodies)} != attempts_used={au} != requests_seen={n_req}")
    if s.get("wire_errors"):
        anomalies.append(f"D1: wire_errors={s['wire_errors']}")
        d1 = False
        checks["D1_mediation"]["pass"] = False

    # D2 乾淨重置（兩臂都該有：resample 與 fresh_hint 都是乾淨重抽）
    origin_ws = attempts[0].get("ws_start_sha256") if attempts else None
    d2 = True
    for k, a in enumerate(attempts):
        if a.get("attempt", k + 1) < 2:
            continue
        r = a.get("reset") or {}
        if not (r.get("back_to_start") is True and r.get("ws_sha256") == origin_ws):
            d2 = False
            anomalies.append(f"D2: attempt {k+1} reset={r!r} origin={origin_ws!r}")
    checks["D2_clean_reset"] = {"pass": bool(d2)}

    # D3 提示檔
    ws = root / arm / task / "ws" / FEEDBACK_FILENAME
    file_present = ws.exists()
    file_text = ws.read_text(encoding="utf-8") if file_present else None
    d3 = True
    if is_treatment:
        if au is not None and au >= 2:
            expected = (attempts[au - 2].get("feedback") or {}).get("text")
            ok = (file_present and file_text is not None and file_text.strip() != ""
                  and len(file_text.encode("utf-8")) <= MAX_HINT_BYTES
                  and expected is not None and file_text == expected)
            if not ok:
                d3 = False
                anomalies.append(
                    "D3: hint file wrong "
                    f"(present={file_present}, bytes={len(file_text.encode('utf-8')) if file_text else None}, "
                    f"expected_sha_match={expected is not None and file_text == expected})")
        else:
            if file_present and (file_text or "").strip() != "":
                d3 = False
                anomalies.append("D3: attempts_used==1 but a non-empty hint file exists")
    else:
        if file_present and (file_text or "").strip() != "":
            d3 = False
            anomalies.append("D3: control cell has a non-empty hint file (negative control broken)")
    checks["D3_hint_file"] = {
        "pass": bool(d3), "file_present": file_present,
        "file_bytes": len(file_text.encode("utf-8")) if file_text else None}

    # D4 wire 內文（最硬的一環：模型輸入裡有沒有那個提示）
    d4 = True
    d4_detail = []
    if au is not None and d1:
        if HINT_MARKER in "\n".join(_user_contents(bodies[0])):
            d4 = False
            anomalies.append("D4: hint marker present in attempt-1 request")
        for k in range(1, len(bodies)):
            contents = "\n".join(_user_contents(bodies[k]))
            has_marker = HINT_MARKER in contents
            if is_treatment:
                expected = (attempts[k - 1].get("feedback") or {}).get("text")
                has_text = expected is not None and expected in contents
                if not (has_marker and has_text):
                    d4 = False
                    anomalies.append(f"D4: attempt {k+1} request missing its hint "
                                     f"(marker={has_marker}, exact_text={has_text})")
            else:
                if has_marker:
                    d4 = False
                    anomalies.append(f"D4: control attempt {k+1} request contains hint marker")
            d4_detail.append({"attempt": k + 1, "marker": has_marker,
                              "exact_hint": (expected is not None and expected in contents)
                              if is_treatment else None})
    checks["D4_wire_content"] = {"pass": bool(d4), "per_attempt": d4_detail}

    checks["argv_sha256_attempt1"] = attempts[0].get("argv_sha256") if attempts else None
    return {"pass": not anomalies, "checks": checks, "anomalies": anomalies,
            "accepted": s.get("accepted") is True, "attempts_used": au,
            "stop_reason": s.get("stop_reason")}


def audit(roots: list[Path], tasks: list[str], arm_control: str, arm_treatment: str) -> dict:
    per_root: dict = {}
    all_cells: dict[tuple[str, str], dict] = {}
    for root in roots:
        arms = {arm_control: {"is_treatment": False}, arm_treatment: {"is_treatment": True}}
        root_out = {}
        for arm, meta in arms.items():
            arm_out = {"cells": {}, "n_cells": 0, "n_accepted": 0,
                       "anomalies": []}
            for t in tasks:
                try:
                    r = audit_cell(root, arm, t, is_treatment=meta["is_treatment"])
                except (FileNotFoundError, OSError, json.JSONDecodeError) as e:
                    r = {"pass": False, "checks": {}, "anomalies": [f"unreadable: {e}"],
                         "accepted": None, "attempts_used": None, "stop_reason": None}
                arm_out["cells"][t] = r
                arm_out["n_cells"] += 1
                arm_out["n_accepted"] += bool(r["accepted"])
                if not r["pass"]:
                    arm_out["anomalies"].append({"task": t, "anomalies": r["anomalies"]})
                all_cells[(str(root), arm, t)] = r
            root_out[arm] = arm_out
        per_root[str(root)] = root_out

    # D5 prompt 同（跨臂配對檢查）
    d5_bad = []
    for (root_s, arm, t), r in all_cells.items():
        if arm == arm_control:
            rt = all_cells.get((root_s, arm_treatment, t))
            if rt is None:
                continue
            a = (r["checks"].get("argv_sha256_attempt1"))
            b = (rt["checks"].get("argv_sha256_attempt1"))
            if a != b:
                d5_bad.append({"root": root_s, "task": t, "control": a, "treatment": b})

    # 描述性子集（out_of_prereg；不是判定）
    subset_pairs = []
    for (root_s, arm, t), r in all_cells.items():
        if arm == arm_treatment and (r["attempts_used"] or 0) >= 2:
            rc = all_cells.get((root_s, arm_control, t))
            if rc is None:
                continue
            subset_pairs.append({"root": root_s, "task": t,
                                 "control_accepted": rc["accepted"],
                                 "treatment_accepted": r["accepted"]})
    sub_b = sum(1 for p in subset_pairs if p["control_accepted"] and not p["treatment_accepted"])
    sub_c = sum(1 for p in subset_pairs if p["treatment_accepted"] and not p["control_accepted"])
    descriptive = {
        "out_of_prereg": True, "decision_state": None,
        "definition": "pairs where the treatment cell actually used the hint (attempts_used>=2)",
        "n_pairs": len(subset_pairs),
        "control_accepted": sum(1 for p in subset_pairs if p["control_accepted"]),
        "treatment_accepted": sum(1 for p in subset_pairs if p["treatment_accepted"]),
        "b_control_only": sub_b, "c_treatment_only": sub_c,
        "note": ("descriptive only: exposure of the UNRESOLVED verdict, NOT a decision "
                 "and NOT a new effect claim; no p-value is assigned to it"),
    }

    n_control_files = sum(
        1 for (root_s, arm, t), r in all_cells.items()
        if arm == arm_control and r["checks"]["D3_hint_file"]["file_present"]
        and (r["checks"]["D3_hint_file"]["file_bytes"] or 0) > 0)
    n_cells = len(all_cells)
    all_pass = (not d5_bad and not any(
        a["anomalies"] for root_out in per_root.values() for a in root_out.values()))
    return {
        "schema": "vacant.audit/v5_hint_delivery/1",
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": ("verify the v5 treatment (fresh_hint) was delivered as the prereg "
                    "describes; boundary condition of the UNRESOLVED verdict, not a new analysis"),
        "roots": [str(r) for r in roots],
        "arms": {"control": arm_control, "treatment": arm_treatment},
        "n_cells": n_cells,
        "per_root": per_root,
        "D5_prompt_identical_across_arms": {"pass": not d5_bad, "mismatches": d5_bad},
        "control_nonempty_hint_files": n_control_files,
        "descriptive_hint_used_subset": descriptive,
        "all_checks_passed": bool(all_pass),
    }


def _mk_cell(base: Path, arm: str, task: str, *, n_attempts: int,
             hint_texts: list[str], write_file: bool, file_text: str | None,
             argv_sha: str, wire_bodies: list[str],
             requests_seen: int | None = None) -> None:
    """selftest 用：造一個最小但結構合法的 cell。"""
    run_dir = base / arm / task / "run"
    (run_dir / ".." / "ws").mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    ws_dir = base / arm / task / "ws"
    if write_file and file_text is not None:
        (ws_dir / FEEDBACK_FILENAME).write_text(file_text, encoding="utf-8")
    attempts = []
    for k in range(n_attempts):
        a = {
            "attempt": k + 1,
            "retry": "fresh_hint",
            "reset": (None if k == 0 else
                      {"kind": "fresh_hint", "ws_sha256": "ORIGIN", "back_to_start": True}),
            "feedback": ({"path": "ws/VACANT_FEEDBACK.md", "bytes": len(hint_texts[k]),
                          "sha256": "x", "text": hint_texts[k], "delivery": "file"}
                         if k < len(hint_texts) else None),
            "ws_start_sha256": "ORIGIN" if k == 0 else "SOMETHING",
            "argv_sha256": argv_sha,
            "requests_seen": 1, "requests_seen_cumulative": k + 1,
            "visible_passed": 1 if k == n_attempts - 1 else 0,
            "visible_total": 1, "accepted": k == n_attempts - 1,
            "stop_reason": "visible_pass" if k == n_attempts - 1 else "visible_fail",
        }
        attempts.append(a)
    s = {"task_id": f"selftest_{task}", "arm": "RUN-ON", "accepted": n_attempts == 1,
         "requests_seen": requests_seen if requests_seen is not None else n_attempts,
         "attempts_used": n_attempts, "stop_reason": attempts[-1]["stop_reason"],
         "wire_errors": [], "attempts": attempts}
    (run_dir / "run_RUN-ON.json").write_text(json.dumps(s), encoding="utf-8")
    wire = run_dir / "wire_RUN-ON"
    wire.mkdir(parents=True, exist_ok=True)
    idx = []
    for i, content in enumerate(wire_bodies):
        body = {"model": "m", "messages": [{"role": "user", "content": content}]}
        blob = json.dumps(body).encode("utf-8")
        (wire / (f"call{i}.req.bin")).write_bytes(blob)
        idx.append({"call_id": f"call{i}", "ts": 1000.0 + i,
                    "request_bytes": len(blob)})
    (wire / "index.jsonl").write_text(
        "\n".join(json.dumps(e) for e in idx) + "\n", encoding="utf-8")


def _selftest() -> int:
    H1 = (f"<!-- Attempt 1 failed -->\n{HINT_MARKER}\nassert: 3/9 visible tests failed.\n"
          "Avoid this failure in your clean implementation.")
    H2 = (f"<!-- Attempt 2 failed -->\n{HINT_MARKER}\nimport: SyntaxError (x.py, line 1)\n"
          "Avoid this failure in your clean implementation.")
    plain = "Read goal.md and do what it says.\n"
    ok = 0
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        # 好的 treatment cell：2 attempts，檔＝最後提示，wire req2 含 H1 逐字
        _mk_cell(base, "C", "good", n_attempts=2, hint_texts=[H1],
                 write_file=True, file_text=H1, argv_sha="SAME",
                 wire_bodies=[plain, plain + "\n\n---\n" + H1])
        # 好的 control cell：2 attempts，無檔，wire 全無標記
        _mk_cell(base, "B", "good", n_attempts=2, hint_texts=[],
                 write_file=False, file_text=None, argv_sha="SAME",
                 wire_bodies=[plain, plain])
        # 壞例：treatment 無檔
        _mk_cell(base, "C", "nofile", n_attempts=2, hint_texts=[H1],
                 write_file=False, file_text=None, argv_sha="S",
                 wire_bodies=[plain, plain + "\n\n---\n" + H1])
        # 壞例：control 有檔
        _mk_cell(base, "B", "ctrlfile", n_attempts=1, hint_texts=[],
                 write_file=True, file_text=H1, argv_sha="S",
                 wire_bodies=[plain])
        # 壞例：req1 含標記
        _mk_cell(base, "C", "req1hint", n_attempts=2, hint_texts=[H1],
                 write_file=True, file_text=H1, argv_sha="S",
                 wire_bodies=[plain + "\n\n---\n" + H1, plain + "\n\n---\n" + H1])
        # 壞例：wire 數與 attempts 不符
        _mk_cell(base, "C", "unmapped", n_attempts=2, hint_texts=[H1],
                 write_file=True, file_text=H1, argv_sha="S",
                 wire_bodies=[plain], requests_seen=3)
        # 壞例：提示文字在 wire 裡被改掉（檔對、wire 錯）
        _mk_cell(base, "C", "wiremut", n_attempts=2, hint_texts=[H1],
                 write_file=True, file_text=H1, argv_sha="S",
                 wire_bodies=[plain, plain + "\n\n---\n" + H1.replace("3/9", "9/3")])

        def run(arm: str, task: str, treatment: bool) -> dict:
            return audit_cell(base, arm, task, is_treatment=treatment)

        cases = [
            ("C", "good", True, True, "good treatment passes"),
            ("B", "good", False, True, "good control passes"),
            ("C", "nofile", True, False, "missing hint file detected"),
            ("B", "ctrlfile", False, False, "control hint file detected"),
            ("C", "req1hint", True, False, "attempt-1 hint detected"),
            ("C", "unmapped", True, False, "wire/attempts mismatch detected"),
            ("C", "wiremut", True, False, "wire hint mutation detected"),
        ]
        failures = []
        for arm, task, treat, expect_pass, label in cases:
            got = run(arm, task, treat)["pass"]
            if got is not expect_pass:
                failures.append(f"{label}: expected pass={expect_pass}, got {got} "
                                f"({run(arm, task, treat)['anomalies']})")
            else:
                ok += 1
        # D5 配對：good 兩臂 argv 同 → 過；不同 → 不過
        base2 = base / "d5"
        _mk_cell(base2, "B", "d5", n_attempts=1, hint_texts=[], write_file=False,
                 file_text=None, argv_sha="AAA", wire_bodies=[plain])
        _mk_cell(base2, "C", "d5", n_attempts=1, hint_texts=[], write_file=False,
                 file_text=None, argv_sha="BBB", wire_bodies=[plain])
        res = audit([base2], ["d5"], "B", "C")
        if res["D5_prompt_identical_across_arms"]["pass"] is False:
            ok += 1
        else:
            failures.append("D5 argv mismatch not detected")
    if failures:
        print("SELFTEST FAIL:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"selftest OK: {ok} cases (good cells pass; all 6 anomaly shapes caught; D5 pairing works)")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prereg", type=Path, default=None,
                    help="prereg json（取 task_ids 與臂名）")
    ap.add_argument("--roots", nargs="*", type=Path, default=None,
                    help="v5 rep 根目錄（runs_v5_r1 runs_v5_r2 runs_v5_r3）")
    ap.add_argument("--json", type=Path, default=None, help="稽核 JSON 輸出")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.prereg or not args.roots:
        ap.error("--prereg and --roots are required (or --selftest)")

    preg = json.loads(args.prereg.read_text(encoding="utf-8"))
    tasks = list(preg["fixed"]["tasks"])
    arm_c = preg["fixed"]["arm_roles"]["control"]
    arm_t = preg["fixed"]["arm_roles"]["treatment"]
    result = audit(args.roots, tasks, arm_c, arm_t)
    result["prereg_id"] = preg.get("id")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
    d = result["descriptive_hint_used_subset"]
    print(f"cells={result['n_cells']}  all_checks_passed={result['all_checks_passed']}")
    for root_s, arms in result["per_root"].items():
        for arm, a in arms.items():
            print(f"  {root_s} {arm}: cells={a['n_cells']} accepted={a['n_accepted']} "
                  f"anomalies={len(a['anomalies'])}")
    print(f"  D5 prompt identical across arms: {result['D5_prompt_identical_across_arms']['pass']}")
    print(f"  control non-empty hint files: {result['control_nonempty_hint_files']} (expected 0)")
    print(f"  [descriptive, out_of_prereg] hint-used pairs={d['n_pairs']} "
          f"ctrl_acc={d['control_accepted']} treat_acc={d['treatment_accepted']} "
          f"b={d['b_control_only']} c={d['c_treatment_only']} (no p, not a decision)")
    return 0 if result["all_checks_passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
