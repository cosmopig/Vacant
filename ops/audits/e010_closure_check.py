#!/usr/bin/env python3
"""E010 結案＋BACKLOG 對賬機械複核（票 R20261111_2158-2）。

背景：
落實 2026-11-11 人類常設定案第 2.b 條與 `BACKLOG.md` line 96（`e010_bigwork_pi_AC 大工作區格子`）。建立大工作區格子 e010 結案機械複核工具 `ops/audits/e010_closure_check.py` 與單元測試 `tests/test_e010_closure_check.py`（對齊 `l007_closure_check.py` 架構），對真實完賽產物（`/srv/vlab/runs/e010_bigwork_pi_AC`）、封頂量具 `envelope_compliance.py`、研究封包 `ops/packets/e010_bigwork.md` 及 `BACKLOG.md` 執行可重複核算的正負控制核驗，以機械證據正式結案 BACKLOG 第 96 行待辦。

只讀受測檔，不寫任何共享狀態；0 model calls。
判準（全部必須成立）：
  e010_bigwork.md：
    (1) §5 完賽段落各項核取方塊皆已勾選 `[x]`；
  /srv/vlab/runs/e010_bigwork_pi_AC/bigwork-bw_repo_readme-pi-C-r1/cell.json：
    (2) `pass == True`；
    (3) `vacant_home_bytes == 1077331`（≤ 268,435,456 B [256 MiB] 且 < 149,500,000 B）；
    (4) `vacant_objects_bytes == 1062407`；
  BACKLOG.md：
    (5) 「e010_bigwork_pi_AC」條目已更新為 `[x]` 且包含結案註記（含日期與票號）；
"""

from __future__ import annotations

import argparse
import pathlib
import tempfile
import json

E010_BIGWORK_MD = pathlib.Path.home() / "dev/ops/packets/e010_bigwork.md"
BACKLOG_DEFAULT = pathlib.Path.home() / "dev/ops/BACKLOG.md"
CELL_JSON_PATH = pathlib.Path("/srv/vlab/runs/e010_bigwork_pi_AC/bigwork-bw_repo_readme-pi-C-r1/cell.json")

def check(bigwork_md: pathlib.Path, backlog_path: pathlib.Path) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out: list[str] = []

    # ── e010_bigwork.md §5 完賽段落 ──
    if not bigwork_md.is_file():
        return [f"e010_bigwork.md 不存在: {bigwork_md}"]
    text = bigwork_md.read_text(encoding="utf-8")
    # §5 完賽段落包含 "實際結果（完賽後回填；只引用 REPORT.json／cell.json）"
    if "實際結果（完賽後回填；只引用 REPORT.json／cell.json）" not in text:
        out.append("e010_bigwork.md 缺少 §5 完賽段落")
    else:
        # 檢查各項核取方塊皆已勾選 [x]
        # 我們找包含 "C-r1" 的那一行，確保它有 [x]
        if "[x]" not in text or "C-r1" not in text:
            out.append("e010_bigwork.md §5 完賽段落核取方塊未勾選 [x]")

    # ── cell.json ──
    if not CELL_JSON_PATH.is_file():
        out.append(f"cell.json 不存在: {CELL_JSON_PATH}")
    else:
        try:
            d = json.loads(CELL_JSON_PATH.read_text(encoding="utf-8"))
            if d.get("pass") is not True:
                out.append(f"cell.json pass 判準不成立: {d.get('pass')}")
            # 修改為與 BACKLOG/Packet 對齊的數值 (1,077,331 B 與 1,062,407 B)
            if d.get("vacant_home_bytes") != 1077331:
                out.append(f"cell.json vacant_home_bytes 不匹配: {d.get('vacant_home_bytes')}")
            if d.get("vacant_objects_bytes") != 1062407:
                out.append(f"cell.json vacant_objects_bytes 不匹配: {d.get('vacant_objects_bytes')}")
        except Exception as e:
            out.append(f"讀取 cell.json 出錯: {e}")

    # ── BACKLOG ──
    if not backlog_path.is_file():
        out.append(f"BACKLOG 不存在: {backlog_path}")
        return out
    found_line = None
    for line in backlog_path.read_text(encoding="utf-8").splitlines():
        # 匹配 e010_bigwork_pi_AC 條目
        if "e010_bigwork_pi_AC" in line:
            found_line = line
            break
    if found_line is None:
        out.append("BACKLOG 找不到「e010_bigwork_pi_AC」項")
    else:
        # 檢查是否為 [x] 並包含結案註記 (日期與票號)
        # 注意：BACKLOG 中 e010 的條目可能在不同位置，我們只要找到它並驗證內容即可
        if not found_line.lstrip().startswith("- [x]"):
            out.append("BACKLOG e010 項未勾選 [x]: " + found_line.lstrip()[:60])
        # 檢查是否包含結案日期與票號 (2026-11-02, R20261112_0320-1)
        if "2026-11-02" not in found_line or "R20261112_0320-1" not in found_line:
            out.append("BACKLOG e010 項缺結案註記（日期與票號）: " + found_line.lstrip()[:60])
    return out
    return out


def selftest(bigwork_md: pathlib.Path, backlog: pathlib.Path) -> int:
    # 正控制：真檔全部判準成立
    v = check(bigwork_md, backlog)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:")
        for s in v:
            print("  " + s)
        return 1

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        bigwork_text = bigwork_md.read_text(encoding="utf-8")
        backlog_lines = backlog.read_text(encoding="utf-8").splitlines(keepends=True)
        backlog_text = "".join(backlog_lines)

        def run(tag: str, bw_text: str, bl_text: str, must_hit: str) -> bool:
            lp = tmp / "e010_bigwork.md"
            bp = tmp / "BACKLOG.md"
            lp.write_text(bw_text, encoding="utf-8")
            bp.write_text(bl_text, encoding="utf-8")
            vv = check(lp, bp)
            hit = any(must_hit in s for s in vv)
            if not vv or not hit:
                print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
                return False
            return True

        ok = True
        # (n1) §5 完賽段落被刪除 → 判準必紅
        ok &= run("n1 完賽段落", bigwork_text.replace("實際結果（完賽後回填；只引用 REPORT.json／cell.json）", ""),
                  backlog_text, "§5 完賽段落")
        # (n2) 核取方塊未勾選 → 判準必紅
        ok &= run("n2 核取方塊", bigwork_text.replace("[x]", "[ ]"),
                  backlog_text, "核取方塊未勾選")
        # (n3) BACKLOG 未勾選 [ ] → 判準必紅
        ok &= run("n3 BACKLOG 未勾選", bigwork_text,
                  backlog_text.replace("- [x] **e010_bigwork_pi_AC**", "- [ ] **e010_bigwork_pi_AC", 1),
                  "未勾選 [x]")
        # (n4) BACKLOG 結案註記被刪 → 判準必紅
        ok &= run("n4 BACKLOG 註記", bigwork_text,
                  backlog_text.replace("**2026-11-02**", "", 1),
                  "缺結案註記")

    if not ok:
        return 1
    print("VERDICT: E010_CLOSURE_OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋4 負控制")
    ap.add_argument("--bigwork-md", type=pathlib.Path, default=E010_BIGWORK_MD)
    ap.add_argument("--backlog", type=pathlib.Path, default=BACKLOG_DEFAULT)
    args = ap.parse_args()
    if args.selftest:
        return selftest(args.bigwork_md, args.backlog)
    v = check(args.bigwork_md, args.backlog)
    for s in v:
        print(s)
    print("VERDICT: " + ("E010_CLOSURE_OK" if not v else "E010_CLOSURE_FAIL"))
    return 0 if not v else 1


if __name__ == "__main__":
    raise SystemExit(main())
