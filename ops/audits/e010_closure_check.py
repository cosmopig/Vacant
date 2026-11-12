#!/usr/bin/env python3
"""e010 大工作區格子（e010_bigwork_pi_AC）結案機械複核（r1482、票 P20261112_0320-1）。
2026-11-11 人類常設定案第 2.b 條與資深審查第 4 節第 3 點，要求 BACKLOG line 96
以機械證據結案。完賽產物在卷：C-r1 cell.json（agent_rc=0、timed_out=false、
vacant_home_bytes=1,077,331 ≤256MiB 且 <149.5M、vacant_objects_bytes=1,062,407）、
packet §5 五格 [x]；BACKLOG 仍 [ ]＝記錄層缺口（H-0 同構）；對齊 l007_closure_check 架構；唯讀；0 model calls。
判準：cell pass 狀態（pass==True 或 agent_rc==0 且 timed_out==False）＋
vacant_home_bytes==1077331（≤268,435,456 且 <149,500,000）＋vacant_objects_bytes==1062407；
packet §5 完賽段落（「完賽日期」）＋核取方塊 ≥1 全 [x]；
BACKLOG e010_bigwork_pi_AC 項 [x]＋結案註記（日期＋票號）；
envelope_compliance 量具（packet §7／BACKLOG 點名之 ops/vlab/tools/envelope_compliance.py）
verdict==PASS 且 C-r1 compliance==PASS。
"""

import argparse
import importlib.util
import json
import pathlib
import re

RUNS_BASE = pathlib.Path("/srv/vlab/runs")
EXP = "e010_bigwork_pi_AC"
CELL_DEFAULT = RUNS_BASE / EXP / "bigwork-bw_repo_readme-pi-C-r1" / "cell.json"
PACKET_DEFAULT = pathlib.Path.home() / "dev/ops/packets/e010_bigwork.md"
BACKLOG_DEFAULT = pathlib.Path.home() / "dev/ops/BACKLOG.md"
ENVELOPE_TOOL = pathlib.Path(__file__).resolve().parents[2] / "ops/vlab/tools/envelope_compliance.py"
CLOSURE_NOTE = ("**結案（round 1482、2026-11-12、票 P20261112_0320-1）**：C-r1 完賽產物機械複核"
                "（cell：vacant_home_bytes=1,077,331 B ≤256MiB 且 <149.5M；vacant_objects_bytes=1,062,407 B；"
                "envelope_compliance verdict=PASS（C-r1 封頂佔比 0.004）；packet §5 五格全 [x]），本項結案。")


def check(cell_text: str, packet_text: str, backlog_text: str) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out = []
    d = json.loads(cell_text)
    if not (d.get("pass") is True or (d.get("agent_rc") == 0 and d.get("timed_out") is False)):
        out.append(f"cell pass 狀態不成立：pass={d.get('pass')!r} agent_rc={d.get('agent_rc')!r} timed_out={d.get('timed_out')!r}")
    hb = d.get("vacant_home_bytes")
    if hb != 1077331:
        out.append(f"cell vacant_home_bytes={hb!r} != 1077331")
    elif not (hb <= 268435456 and hb < 149500000):
        out.append(f"cell vacant_home_bytes={hb} 超 256MiB 封頂或未 <149.5M")
    if d.get("vacant_objects_bytes") != 1062407:
        out.append("cell vacant_objects_bytes=" + repr(d.get("vacant_objects_bytes")) + " != 1062407")
    m = re.search(r"^##\s*5[、.．][^\n]*\n(.*?)(?=^##\s|\Z)", packet_text, re.M | re.S)
    sec = m.group(1) if m else ""
    if "完賽日期" not in sec:
        out.append("packet §5 缺完賽段落（無「完賽日期」）")
    boxes = re.findall(r"^\s*-\s*\[([ xX])\]", sec, re.M)
    if not boxes or any(b != "x" for b in boxes):
        out.append(f"packet §5 核取方塊未全部勾選 [x]：{boxes!r}")
    mm = re.search(r"^\s*-\s*\[([ xX])\]\s*\*\*e010_bigwork_pi_AC[^*]*\*\*(.*)$", backlog_text, re.M)
    if not mm:
        out.append("BACKLOG 未找到 e010_bigwork_pi_AC 項")
    elif mm.group(1) != "x":
        out.append("BACKLOG e010_bigwork_pi_AC 項未勾選 [x]")
    elif not (CLOSURE_NOTE in mm.group(2)):
        out.append("BACKLOG e010 項缺結案註記（結案日期＋票號）")
    return out


def check_envelope(base: pathlib.Path) -> list[str]:
    """跑 packet §7／BACKLOG 點名之量具：verdict 須 PASS、C-r1 compliance 須 PASS。"""
    try:
        spec = importlib.util.spec_from_file_location("envelope_compliance", ENVELOPE_TOOL)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        env, src = mod._load_envelope(); out = mod.evaluate(base, EXP, env, src)
    except Exception as e:
        return [f"envelope_compliance 量具不可執行: {e}"]
    v = [] if out["verdict"] == "PASS" else [f"envelope_compliance verdict={out['verdict']!r} != PASS"]
    c = next((x for x in out["cells"] if x.get("cell") == "bigwork-bw_repo_readme-pi-C-r1"), None)
    return v + ([] if c and c.get("compliance") == "PASS" else ["envelope_compliance C-r1 compliance 非 PASS"])


def selftest(cell_p: pathlib.Path, packet_p: pathlib.Path, backlog_p: pathlib.Path) -> int:
    missing = [f"SELFTEST missing file {n}: {p}" for n, p in (("cell.json", cell_p), ("packet", packet_p), ("BACKLOG", backlog_p)) if not p.is_file()]
    if missing:
        print(*missing, sep="\n"); return 1
    cell_text, packet_text, backlog_text = (p.read_text(encoding="utf-8") for p in (cell_p, packet_p, backlog_p))
    v = check(cell_text, packet_text, backlog_text) + check_envelope(RUNS_BASE)  # 正控制：真檔＋量具全過
    if v:
        print("SELFTEST positive control FAIL:", *v, sep="\n  ")
        return 1
    print("SELFTEST positive control OK（cell.json／packet §5／BACKLOG／envelope 量具 全過）")

    def run(tag: str, cell: str, packet: str, backlog: str, must_hit: str) -> bool:
        vv = check(cell, packet, backlog)
        if not vv or not any(must_hit in s for s in vv):
            print(f"SELFTEST negative control FAIL [{tag}]: violations={vv} (應含 {must_hit!r})"); return False
        return True

    ok = True  # 負控制（票面要求）：篡改 byte 數、取消勾選、竄改 pass 狀態時必報違規
    ok &= run("n1 byte 篡改", cell_text.replace('"vacant_home_bytes": 1077331', '"vacant_home_bytes": 300000000', 1), packet_text, backlog_text, "vacant_home_bytes")
    ok &= run("n2 pass 狀態篡改", cell_text.replace('"agent_rc": 0', '"agent_rc": 1', 1), packet_text, backlog_text, "pass 狀態")
    ok &= run("n3 §5 未勾選", cell_text, packet_text.replace("- [x] 完賽日期", "- [ ] 完賽日期", 1), backlog_text, "packet §5")
    ok &= run("n4 BACKLOG 未勾選", cell_text, packet_text, backlog_text.replace("- [x] **e010_bigwork_pi_AC", "- [ ] **e010_bigwork_pi_AC", 1), "未勾選 [x]")
    ok &= run("n5 BACKLOG 註記刪除", cell_text, packet_text, backlog_text.replace(CLOSURE_NOTE, "", 1), "缺結案註記")
    if not ok: return 1
    print("VERDICT: E010_CLOSURE_OK")
    print("  files:", cell_p, packet_p, backlog_p, sep="\n  ")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋負控制自測")
    ap.add_argument("--cell", type=pathlib.Path, default=CELL_DEFAULT)
    ap.add_argument("--packet", type=pathlib.Path, default=PACKET_DEFAULT)
    ap.add_argument("--backlog", type=pathlib.Path, default=BACKLOG_DEFAULT)
    args = ap.parse_args()
    if args.selftest:
        return selftest(args.cell, args.packet, args.backlog)
    v = check(args.cell.read_text(encoding="utf-8"), args.packet.read_text(encoding="utf-8"), args.backlog.read_text(encoding="utf-8")) + check_envelope(RUNS_BASE)
    for s in v:
        print("VIOLATION:", s)
    return 1 if v else 0


if __name__ == "__main__":
    raise SystemExit(main())
