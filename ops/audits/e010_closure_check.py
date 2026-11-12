#!/usr/bin/env python3
"""e010 大工作區格子（e010_bigwork_pi_AC）結案機械複核（r1482、票 P20261112_0320-1）。
2026-11-11 人類常設定案第 2.b 條與資深審查第四節第 3 條要求 BACKLOG line 96 以機械
證據結案。完賽產物已在案：C-r1 cell.json（agent_rc=0、timed_out=false、
vacant_home_bytes=1,077,331 ≤256MiB 且 <149.5M、vacant_objects_bytes=1,062,407）、
packet §5 五格全 [x]（envelope PASS）；BACKLOG 仍 [ ]＝記錄層缺口（H-0 同型）。
對齊 ops/audits/l007_closure_check.py 架構；只讀受測檔；0 model calls。
判準：cell pass 狀態（pass==True 或 agent_rc==0 且 timed_out==False）＋
vacant_home_bytes==1077331（≤268,435,456 且 <149,500,000）＋vacant_objects_bytes==1062407；
packet §5 完賽段落（「完賽日期」）＋核取方塊 ≥1 全 [x]；
BACKLOG e010_bigwork_pi_AC 項 [x]＋結案註記（日期＋票號）。
"""

import argparse
import json
import pathlib
import re

CELL_DEFAULT = pathlib.Path("/srv/vlab/runs/e010_bigwork_pi_AC/bigwork-bw_repo_readme-pi-C-r1/cell.json")
PACKET_DEFAULT = pathlib.Path.home() / "dev/ops/packets/e010_bigwork.md"
BACKLOG_DEFAULT = pathlib.Path.home() / "dev/ops/BACKLOG.md"
CLOSURE_NOTE = ("**結案（round 1482、2026-11-12、票 P20261112_0320-1）**：C-r1 完賽產物機械複核"
                "（cell：vacant_home_bytes=1,077,331 B ≤256MiB 且 <149.5M；vacant_objects_bytes=1,062,407 B；"
                "envelope_compliance PASS；packet §5 五格全 [x]），本項結案。")

def check(cell_text: str, packet_text: str, backlog_text: str) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out: list[str] = []
    try:
        d = json.loads(cell_text)
    except Exception as e:
        return [f"cell.json 不可解析: {e}"]
    if not (d.get("pass") is True or (d.get("agent_rc") == 0 and d.get("timed_out") is False)):
        out.append("cell pass 狀態：pass!=True 且非 (agent_rc==0 且 timed_out==False)")
    hb = d.get("vacant_home_bytes")
    if hb != 1077331 or not (hb <= 268_435_456 and hb < 149_500_000):
        out.append(f"cell vacant_home_bytes={hb!r} 須為 1077331（≤256MiB 且 <149.5M）")
    if d.get("vacant_objects_bytes") != 1062407:
        out.append("cell vacant_objects_bytes=" + repr(d.get("vacant_objects_bytes")) + " != 1062407")
    m = re.search(r"^## 5\..*?$(.*?)(?=^## \d|\Z)", packet_text, re.M | re.S)
    sec = m.group(1) if m else ""
    if not sec.strip():
        out.append("packet §5 完賽段落缺失")
    else:
        boxes = re.findall(r"-\s*\[([ xX])\]", sec)
        if not boxes or any(c == " " for c in boxes):
            out.append(f"packet §5 核取方塊 {boxes}：缺或未按全 [x]")
        if "完賽日期" not in sec:
            out.append("packet §5 缺「完賽日期」")
    line = next((l for l in backlog_text.splitlines() if "e010_bigwork_pi_AC" in l), None)
    if line is None:
        out.append("BACKLOG 找不到 e010_bigwork_pi_AC 項")
    elif not line.lstrip().startswith("- [x]"):
        out.append("BACKLOG e010 項未勾選 [x]: " + line.lstrip()[:60])
    elif "2026-11-12" not in line or "P20261112_0320-1" not in line:
        out.append("BACKLOG e010 項缺結案註記（日期＋票號）: " + line.lstrip()[:60])
    return out


def selftest(cell_p: pathlib.Path, packet_p: pathlib.Path, backlog_p: pathlib.Path) -> int:
    for name, p in (("cell.json", cell_p), ("packet", packet_p), ("BACKLOG", backlog_p)):
        if not p.is_file():
            print(f"SELFTEST 缺檔 {name}: {p}")
            return 1
    cell_text, packet_text, backlog_text = (p.read_text(encoding="utf-8") for p in (cell_p, packet_p, backlog_p))
    v = check(cell_text, packet_text, backlog_text)  # 正控制：真檔全部判準成立
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:")
        for s in v:
            print("  " + s)
        return 1

    def run(tag: str, cell: str, packet: str, backlog: str, must_hit: str) -> bool:
        vv = check(cell, packet, backlog)
        if not vv or not any(must_hit in s for s in vv):
            print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
            return False
        return True

    ok = True  # 負控制（票面要求）：篡改 byte 數、取消勾選、竄改 pass 狀態時必報違規
    ok &= run("n1 byte 篡改",  # 1,077,331→300,000,000 超封頂
              cell_text.replace('"vacant_home_bytes": 1077331', '"vacant_home_bytes": 300000000', 1),
              packet_text, backlog_text, "vacant_home_bytes")
    ok &= run("n2 pass 狀態篡改",  # agent_rc 0→1
              cell_text.replace('"agent_rc": 0', '"agent_rc": 1', 1),
              packet_text, backlog_text, "pass 狀態")
    ok &= run("n3 §5 未勾選", cell_text,  # §5 勾選退回 [ ]
              packet_text.replace("- [x] 完賽日期", "- [ ] 完賽日期", 1),
              backlog_text, "packet §5")
    ok &= run("n4 BACKLOG 未勾選", cell_text, packet_text,  # BACKLOG 勾選退回 [ ]
              backlog_text.replace("- [x] **e010_bigwork_pi_AC", "- [ ] **e010_bigwork_pi_AC", 1),
              "未勾選 [x]")
    ok &= run("n5 BACKLOG 註記刪除", cell_text, packet_text,  # 結案註記被刪
              backlog_text.replace(CLOSURE_NOTE, "", 1), "缺結案註記")
    if not ok:
        return 1
    print("VERDICT: E010_CLOSURE_OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋5 負控制")
    ap.add_argument("--cell", type=pathlib.Path, default=CELL_DEFAULT)
    ap.add_argument("--packet", type=pathlib.Path, default=PACKET_DEFAULT)
    ap.add_argument("--backlog", type=pathlib.Path, default=BACKLOG_DEFAULT)
    args = ap.parse_args()
    if args.selftest:
        return selftest(args.cell, args.packet, args.backlog)
    v = check(args.cell.read_text(encoding="utf-8"),
              args.packet.read_text(encoding="utf-8"),
              args.backlog.read_text(encoding="utf-8"))
    for s in v:
        print(s)
    print("VERDICT: " + ("E010_CLOSURE_OK" if not v else "E010_CLOSURE_FAIL"))
    return 0 if not v else 1


if __name__ == "__main__":
    raise SystemExit(main())
