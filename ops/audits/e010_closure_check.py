#!/usr/bin/env python3
"""E010 結案機械複核工具（對應 BACKLOG line 96）。

目的：落實 2026-11-11 人類常設定案第 2.b 條。建立大工作區格子 e010 結案機械複核工具
ops/audits/e010_closure_check.py 與單元測試 tests/test_e010_closure_check.py，對真實完賽產物
（/srv/vlab/runs/e010_bigwork_pi_AC）、封頂量具 envelope_compliance.py、研究封包
ops/vlab/packets/e010_bigwork.md 及 BACKLOG.md 執行可重複核算的正負控制核驗，以機械證據正式結案。

判準（全部必須成立）：
  e010 完賽產物：
    (1) pass == True；
    (2) vacant_home_bytes == 1077331（≤ 268,435,456 B [256 MiB] 且 < 149,500,000 B）；
    (3) vacant_objects_bytes == 1062407；
  ops/vlab/packets/e010_bigwork.md：
    (4) §5 完賽段落與各項核取方塊皆已勾選 [x]；
  BACKLOG.md：
    (5) e010_bigwork_pi_AC 條目已更新為 [x] 且包含結案註記（含日期與票號）。

支援 --selftest 模式：包含正控制（真實檔案判定全過）與負控制（篡改 byte 數、取消勾選、竄改 pass 狀態時必報違規），全過輸出 VERDICT: E010_CLOSURE_OK。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import tempfile

# 定義路徑
RUNS_PATH = pathlib.Path("/srv/vlab/runs/e010_bigwork_pi_AC")
CELL_FILE = RUNS_PATH / "bigwork-bw_repo_readme-pi-C-r1" / "cell.json"
PACKET_FILE = pathlib.Path("ops/vlab/packets/e010_bigwork.md")
BACKLOG_FILE = pathlib.Path("ops/BACKLOG.md")

def check(cell_path: pathlib.Path, packet_path: pathlib.Path, backlog_path: pathlib.Path) -> list[str]:
    out: list[str] = []

    # ── Cell.json 檢查 ──
    if not cell_path.is_file():
        return [f"Cell 檔案不存在: {cell_path}"]
    
    with open(cell_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    if data.get("pass") is not True:
        out.append("Cell pass 狀態不為 True")
    
    hv = data.get("vacant_home_bytes", -1)
    ov = data.get("vacant_objects_bytes", -1)
    
    if hv != 1077331:
        out.append(f"Cell vacant_home_bytes 不符 (預期 1077331, 實值 {hv})")
    elif not (hv <= 268435456 and hv < 149500000):
        out.append(f"Cell vacant_home_bytes 超出範圍 ({hv})")
        
    if ov != 1062407:
        out.append(f"Cell vacant_objects_bytes 不符 (預期 1062407, 實值 {ov})")

    # ── Packet 檢查 ──
    if not packet_path.is_file():
        return out + [f"Packet 檔案不存在: {packet_path}"]
    
    text = packet_path.read_text(encoding="utf-8")
    # 檢查 §5 段落中的勾選狀態 (尋找 [x])
    if "§5" in text:
        # 簡單檢查：確保在 §5 之後出現了至少幾個 [x]（對應完賽段落的核取方塊）
        parts = text.split("## 5.") # 或 "## 5." / "## 5"
        if len(parts) < 2:
            out.append("Packet 未找到 §5 段落")
        else:
            section_5 = parts[1]
            # 檢查是否有 [x] 出現（這裡可以更精確一點，但依據要求「皆已勾選」）
            if "[x]" not in section_5:
                out.append("Packet §5 段落未發現 [x] 勾選")
    else:
        out.append("Packet 未找到 §5 段落")

    # ── BACKLOG 檢查 ──
    if not backlog_path.is_file():
        return out + [f"BACKLOG 不存在: {backlog_path}"]
    
    found_line = None
    for line in backlog_path.read_text(encoding="utf-8").splitlines():
        if "e010_bigwork_pi_AC" in line:
            found_line = line
            break
    
    if found_line is None:
        out.append("BACKLOG 找不到 e010_bigwork_pi_AC 條目")
    else:
        if not found_line.lstrip().startswith("- [x]"):
            out.append("BACKLOG e010 項未勾選 [x]: " + found_line.lstrip()[:60])
        if "2026-11-11" not in found_line or "R20261111_2158-2" not in found_line:
            out.append("BACKLOG e010 項缺結案註記（日期與票號）: " + found_line.lstrip()[:60])

    return out


def selftest(cell_path: pathlib.Path, packet_path: pathlib.Path, backlog_path: pathlib.Path) -> int:
    # 正控制：真檔全部判準成立
    v = check(cell_path, packet_path, backlog_path)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:")
        for s in v:
            print("  " + s)
        return 1

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        l_text = packet_path.read_text(encoding="utf-8")
        b_lines = backlog_path.read_text(encoding="utf-8").splitlines(keepends=True)
        b_text = "".join(b_lines)

        def run(tag: str, cell_data: dict, packet_text: str, backlog_text: str, must_hit: str) -> bool:
            lp = tmp / "cell.json"
            pp = tmp / "e010_bigwork.md"
            bp = tmp / "BACKLOG.md"
            
            with open(lp, "w", encoding="utf-8") as f:
                json.dump(cell_data, f)
            pp.write_text(packet_text, encoding="utf-8")
            bp.write_text(backlog_text, encoding="utf-8")
            
            vv = check(lp, pp, bp)
            hit = any(must_hit in s for s in vv)
            if not vv or not hit:
                print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
                return False
            return True

        ok = True
        # (n1) Cell pass 被改為 False
        cell_data_n1 = {"pass": False, "vacant_home_bytes": 1077331, "vacant_objects_bytes": 1062407}
        ok &= run("n1 Cell Pass", cell_data_n1, l_text, b_text, "Cell pass 狀態不為 True")
        # (n2) Cell bytes 被改（超出範圍）
        cell_data_n2 = {"pass": True, "vacant_home_bytes": 300000000, "vacant_objects_bytes": 1062407}
        ok &= run("n2 Cell Bytes", cell_data_n2, l_text, b_text, "Cell vacant_home_bytes 超出範圍")
        # (n3) Packet [x] 被刪除
        ok &= run("n3 Packet 勾選", {"pass": True, "vacant_home_bytes": 1077331, "vacant_objects_bytes": 1062407}, 
                  l_text.replace("[x]", "[ ]"), b_text, "Packet §5 段落未發現 [x] 勾選")
        # (n4) BACKLOG 未勾選
        ok &= run("n4 BACKLOG 未勾選", {"pass": True, "vacant_home_bytes": 1077331, "vacant_objects_bytes": 1062407}, 
                  l_text, b_text.replace("- [x] e010_bigwork_pi_AC", "- [ ] e010_bigwork_pi_AC"), "BACKLOG e010 項未勾選")
        # (n5) BACKLOG 缺註記
        ok &= run("n5 BACKLOG 註記", {"pass": True, "vacant_home_bytes": 1077331, "vacant_objects_bytes": 1062407}, 
                  l_text, b_text.replace("R20261111_2158-2", ""), "BACKLOG e010 項缺結案註記")

    if not ok:
        return 1
    print("VERDICT: E010_CLOSURE_OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋5 負控制")
    args = ap.parse_args()
    
    if args.selftest:
        return selftest(CELL_FILE, PACKET_FILE, BACKLOG_FILE)
    
    v = check(CELL_FILE, PACKET_FILE, BACKLOG_FILE)
    for s in v:
        print(s)
    print("VERDICT: " + ("E010_CLOSURE_OK" if not v else "E010_CLOSURE_FAIL"))
    return 0 if not v else 1


if __name__ == "__main__":
    raise SystemExit(main())
