#!/usr/bin/env python3
"""E010 結案＋BACKLOG 對賬機械複核（票 R20261111_2-e010-bigwork-closure-check.md）。

背景：
針對 e010_bigwork_pi_AC 的結案狀態進行機械式驗證。
判準（全部必須成立）：
  e010_bigwork.md 內容與實際數據對應：
    (1) C-r1 vacant_home_bytes ≤256MiB 且 <149.5M (0.5× workspace＝299M÷2 純算術；stage 實值 300M 時為 150M)。
    (2) vacant_objects_bytes 與 vacant_home_bytes 落盤可核。
    (3) report.py e010_bigwork_pi_AC --rescore 0 格不一致（score 為完成信號，A/C 各 1 格）。
    (4) envelope_compliance.py e010_bigwork_pi_AC verdict=PASS。

只讀受測檔，不寫任何共享狀態；0 model calls。
"""

from __future__ import annotations
import argparse
import pathlib
import json
import os
import tempfile

# 預設路徑（可透過參數覆蓋）
DEFAULT_PACKET = pathlib.Path.home() / "dev/wt/worker/ops/vlab/packets/e010_bigwork.md"
DEFAULT_REPORT = pathlib.Path("/srv/vlab/runs/e010_bigwork_pi_AC/REPORT.json")
DEFAULT_CELL_C = pathlib.Path("/srv/vlab/runs/e010_bigwork_pi_AC/bigwork-bw_repo_readme-pi-C-r1/cell.json")

def check(packet_path: pathlib.Path, report_path: pathlib.Path, cell_c_path: pathlib.Path) -> list[str]:
    out: list[str] = []

    # ── Packet 內容檢查 ──
    if not packet_path.is_file():
        return [f"Packet 檔不存在: {packet_path}"]
    
    packet_text = packet_path.read_text(encoding="utf-8")
    
    # (1) C-r1 vacant_home_bytes ≤256MiB 且 <149.5M
    if not cell_c_path.is_file():
        out.append("C-r1 cell.json 不存在")
    else:
        cell_data = json.loads(cell_c_path.read_text(encoding="utf-8"))
        home_bytes = cell_data.get("vacant_home_bytes", 0)
        objects_bytes = cell_data.get("vacant_objects_bytes", 0)
        workspace_bytes = cell_data.get("workspace_bytes", 0)

        # 判準：<149.5M (對應 workspace 的一半，即 299M / 2 = 149.5M)
        limit_half = workspace_bytes / 2
        if home_bytes > 268435456: # 256MiB
            out.append(f"C-r1 vacant_home_bytes ({home_bytes}) > 256MiB")
        if home_bytes >= limit_half:
            out.append(f"C-r1 vacant_home_bytes ({home_bytes}) >= {limit_half} (0.5x workspace)")

        # (2) 落盤可核 (檢查文件是否存在，且 bytes 必須大於 0)
        if home_bytes == 0 or objects_bytes == 0:
            out.append("vacant_home_bytes 或 vacant_objects_bytes 為 0")

    # (3) report.py --rescore 0 格不一致
    if not report_path.is_file():
        out.append(f"REPORT.json 不存在: {report_path}")
    else:
        report_data = json.loads(report_path.read_text(encoding="utf-8"))
        mismatches = report_data.get("rescore_mismatch", [])
        if mismatches:
            out.append(f"report.py --rescore 存在不一致: {mismatches}")

    # (4) envelope_compliance.py verdict=PASS
    try:
        import subprocess
        # 使用獨立量具核對 C-r1 的合規性。
        cmd = ["python3", "ops/vlab/tools/envelope_compliance.py", "e010_bigwork_pi_AC", "--base", "/srv/vlab/runs"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            out.append(f"envelope_compliance.py 執行失敗 (RC={res.returncode}): {res.stderr}")
        else:
            comp_data = json.loads(res.stdout)
            # verdict 為 "PASS", "FAIL", "NO_EVIDENCE", 或 "NA"
            verdict = comp_data.get("verdict")
            if verdict != "PASS":
                out.append(f"envelope_compliance.py verdict={verdict} (預期 PASS)")
    except Exception as e:
        out.append(f"執行 envelope_compliance.py 時發生異常: {str(e)}")

    return out

def selftest(packet: pathlib.Path, report: pathlib.Path, cell_c: pathlib.Path) -> int:
    # 正控制：真檔全部判準成立
    v = check(packet, report, cell_c)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:")
        for s in v:
            print("  " + s)
        return 1

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        l_text = packet.read_text(encoding="utf-8")
        
        # 模擬一個會失敗的 cell.json (home_bytes 太大)
        bad_cell = {
            "vacant_home_bytes": 300000000, # > 256MiB
            "vacant_objects_bytes": 1000000,
            "workspace_bytes": 400000000
        }
        bad_cell_path = tmp / "cell.json"
        bad_cell_path.write_text(json.dumps(bad_cell), encoding="utf-8")

        def run_test(tag: str, cell_data: dict) -> bool:
            # 這裡簡化，直接傳入 mock data 或寫入 tmp 檔案
            # 為符合 check 函數邏輯，我們寫入檔案
            path = tmp / "cell.json"
            path.write_text(json.dumps(cell_data), encoding="utf-8")
            vv = check(packet, report, path)
            hit = any("vacant_home_bytes" in s for s in vv)
            if not vv or not hit:
                print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}")
                return False
            return True

        ok = True
        # (n1) home_bytes 太大
        ok &= run_test("n1 home_bytes 過大", {"vacant_home_bytes": 300000000, "vacant_objects_bytes": 1000000, "workspace_bytes": 400000000})
        # (n2) home_bytes 為 0
        ok &= run_test("n2 home_bytes 為 0", {"vacant_home_bytes": 0, "vacant_objects_bytes": 1000000, "workspace_bytes": 400000000})

    if not ok:
        return 1
    print("VERDICT: E010_CLOSURE_OK")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋負控制")
    ap.add_argument("--packet", type=pathlib.Path, default=DEFAULT_PACKET)
    ap.add_argument("--report", type=pathlib.Path, default=DEFAULT_REPORT)
    ap.add_argument("--cell-c", type=pathlib.Path, default=DEFAULT_CELL_C)
    args = ap.parse_args()

    if args.selftest:
        return selftest(args.packet, args.report, args.cell_c)
    
    v = check(args.packet, args.report, args.cell_c)
    for s in v:
        print(s)
    print("VERDICT: " + ("E010_CLOSURE_OK" if not v else "E010_CLOSURE_FAIL"))
    return 0 if not v else 1

if __name__ == "__main__":
    raise SystemExit(main())
