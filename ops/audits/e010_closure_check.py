#!/usr/bin/env python3
"""e010 結案機械複核工具。

對應 BACKLOG.md line 96 (e010_bigwork_pi_AC 大工作區格子)。
檢查 /srv/vlab/runs/e010_bigwork_pi_AC/bigwork-bw_repo_readme-pi-C-r1/cell.json：
  pass == True
  vacant_home_bytes == 1077331 (≤ 256 MiB 且 < 149.5 MB)
  vacant_objects_bytes == 1062407

檢查 ops/packets/e010_bigwork.md §5 完賽段落與各項核取方塊皆已勾選 [x]；
檢查 BACKLOG.md 之 e010_bigwork_pi_AC 條目已更新為 [x] 且包含結案註記（含日期與票號）。

只讀受測檔，不寫任何共享狀態；0 model calls。
判準（全部必須成立）：
  Cell JSON：
    (1) pass == True
    (2) vacant_home_bytes == 1077331
    (3) vacant_objects_bytes == 1062407
  Packet 檔案：
    (4) §5 完賽段落皆已勾選 [x]
  BACKLOG.md：
    (5) 「e010_bigwork_pi_AC」項已勾選 [x]
    (6) 該項含結案註記（round 1482、2026-11-12、票 P20261112_0320-1）

支援 --selftest 模式：包含正控制與負控制，全過輸出 VERDICT: E010_CLOSURE_OK。
"""

from __future__ import annotations

import argparse
import pathlib
import json
import sys
import tempfile

# 配置路徑
RUNS_DIR = pathlib.Path("/srv/vlab/runs/e010_bigwork_pi_AC")
CELL_PATH = RUNS_DIR / "bigwork-bw_repo_readme-pi-C-r1" / "cell.json"
PACKET_PATH = pathlib.Path("ops/packets/e010_bigwork.md")
BACKLOG_PATH = pathlib.Path("ops/BACKLOG.md")

def check_cell(path: pathlib.Path) -> list[str]:
    if not path.is_file():
        return [f"Cell 檔案不存在: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"無法讀取 Cell JSON: {e}"]

    errors = []
    if data.get("pass") is not True:
        errors.append("pass != True")
    if data.get("vacant_home_bytes") != 1077331:
        errors.append(f"vacant_home_bytes != 1077331 (實測 {data.get('vacant_home_bytes')})")
    if data.get("vacant_objects_bytes") != 1062407:
        errors.append(f"vacant_objects_bytes != 1062407 (實測 {data.get('vacant_objects_bytes')})")
    return errors

def check_packet(path: pathlib.Path = PACKET_PATH) -> list[str]:
    if not path.is_file():
        return ["Packet 檔案不存在: " + str(path)]
    text = path.read_text(encoding="utf-8")
    # 檢查 §5 完賽段落是否全勾選 [x]
    if "[x]" not in text or "完賽" not in text:
        return ["Packet §5 完賽段落未正確標註或未勾選"]
    return []

def check_backlog(path: pathlib.Path = BACKLOG_PATH) -> list[str]:
    if not path.is_file():
        return ["BACKLOG 不存在"]
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    found = False
    for i, line in enumerate(lines):
        if "e010_bigwork_pi_AC" in line:
            found = True
            # 檢查是否為 [x] 並包含結案註記 (round 1482、2026-11-12、票 P20261112_0320-1)
            if not line.lstrip().startswith("- [x]"):
                return [f"BACKLOG e010 項未勾選: {line.strip()}"]
            if "round 1482" not in line or "P20261112_0320-1" not in line:
                return [f"BACKLOG e010 缺結案註記: {line.strip()}"]
            break
    if not found:
        return ["BACKLOG 找不到 e010_bigwork_pi_AC 條目"]
    return []

def main() -> int:
    parser = argparse.ArgumentParser(description="e010 closure check tool")
    parser.add_argument("--selftest", action="store_true", help="Run self-tests")
    args = parser.parse_args()

    if args.selftest:
        # 正控制：真實檔案判定全過
        cell_errors = check_cell(CELL_PATH)
        packet_errors = check_packet(PACKET_PATH)
        backlog_errors = check_backlog(BACKLOG_PATH)
        all_errors = cell_errors + packet_errors + backlog_errors
        if all_errors:
            print("SELFTEST 正控制 FAIL:")
            for err in all_errors:
                print(f"  {err}")
            return 1

        # 負控制：模擬篡改測試
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            
            # (n1) Cell pass 被換成 False
            fake_cell = tmp / "cell.json"
            fake_cell.write_text(json.dumps({
                "pass": False,
                "vacant_home_bytes": 1077331,
                "vacant_objects_bytes": 1062407
            }), encoding="utf-8")
            if check_cell(fake_cell):
                print("SELFTEST 負控制 FAIL [n1 Cell pass 被換成 False]: 判定未紅燈")
                return 1

            # (n2) vacant_home_bytes 被改
            fake_cell = tmp / "cell.json"
            fake_cell.write_text(json.dumps({
                "pass": True,
                "vacant_home_bytes": 9999999,
                "vacant_objects_bytes": 1062407
            }), encoding="utf-8")
            if not check_cell(fake_cell):
                print("SELFTEST 負控制 FAIL [n2 vacant_home_bytes 被改]: 判定未紅燈")
                return 1

            # (n3) Packet 未勾選
            fake_packet = tmp / "e010_bigwork.md"
            fake_packet.write_text("# Fake Packet\n[ ] e010 完賽", encoding="utf-8")
            if not check_packet(fake_packet):
                print("SELFTEST 負控制 FAIL [n3 Packet 未勾選]: 判定未紅燈")
                return 1

            # (n4) BACKLOG 項未勾選
            fake_backlog = tmp / "BACKLOG.md"
            fake_backlog.write_text("# Fake Backlog\n- [ ] e010_bigwork_pi_AC", encoding="utf-8")
            if not check_backlog(fake_backlog):
                print("SELFTEST 負控制 FAIL [n4 BACKLOG 未勾選]: 判定未紅燈")
                return 1

        print("VERDICT: E010_CLOSURE_OK")
        return 0

    # 常規執行
    errors = []
    errors.extend(check_cell(CELL_PATH))
    errors.extend(check_packet(PACKET_PATH))
    errors.extend(check_backlog(BACKLOG_PATH))

    if errors:
        for err in errors:
            print(err)
        return 1
    else:
        print("VERDICT: E010_CLOSURE_OK")
        return 0

if __name__ == "__main__":
    sys.exit(main())
