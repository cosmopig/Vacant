#!/usr/bin/env python3
"""L007 結案＋BACKLOG 對賬機械複核（r1459、票 R20261111_1516-1）。

背景：
~/dev/ops/loop/L007.md（round 906 資料損失後依官方 REPORT＋原始格重建）的下一步
（e016 收口後重新開啟）在 round 1441 已隨 e016 裁決 NO_MECHANISM 完成實質收口，
但 L007 檔內無結案段、BACKLOG.md 第 11 行 L007 項仍 `[ ]`——「未結」是記錄層缺口
（H-0 同型：狀態與證據不同步）。本輪補結案段（L007 §8，終態
`CLOSED: NO_MECHANISM`＋e016 資料＋三臂義＋結論句逐字引用）、勾選 BACKLOG、
並以本檔機械複核（正控制：真檔全過；負控制：每類篡改必被抓）。

只讀受測檔，不寫任何共享狀態；0 model calls。
判準（全部必須成立）：
  L007 檔：
    (1) 結案終態字樣 `CLOSED: NO_MECHANISM` 在案；
    (2) e016 資料在案：通過率 A 18/34、C 17/34、C-nf 16/34、McNemar p=1.0；
    (3) 三臂義在案（A＝無 Vacant；C-nf 開關 VACANT_FAILED_STEP_REVIEW=0）；
    (4) 結論句逐字引用在案（e016_failed_step_ablation_verdict.json .why）；
    (5) 結案票號 R20261111_1516-1 在案。
  BACKLOG.md：
    (6) 「L007 資料損失」項已勾選 `[x]`；
    (7) 該項含結案註記（round 1459 結案＋票號）。
"""

from __future__ import annotations

import argparse
import pathlib
import tempfile

L007_DEFAULT = pathlib.Path.home() / "dev/ops/loop/L007.md"
BACKLOG_DEFAULT = pathlib.Path.home() / "dev/ops/BACKLOG.md"

L007_REQUIRED: tuple[tuple[str, str], ...] = (
    ("結案終態", "CLOSED: NO_MECHANISM"),
    ("通過率 A", "A 18/34"),
    ("通過率 C", "C 17/34"),
    ("通過率 C-nf", "C-nf 16/34"),
    ("McNemar p", "p=1.0"),
    ("臂 A 義", "無 Vacant"),
    ("C-nf 開關", "VACANT_FAILED_STEP_REVIEW=0"),
    ("結論句逐字", "C vs C-nf 未顯著（開關無可測效應"),
    ("結案票號", "R20261111_1516-1"),
)


def check(l007_path: pathlib.Path, backlog_path: pathlib.Path) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out: list[str] = []

    # ── L007 檔 ──
    if not l007_path.is_file():
        return [f"L007 檔不存在: {l007_path}"]
    text = l007_path.read_text(encoding="utf-8")
    for name, needle in L007_REQUIRED:
        if needle not in text:
            out.append(f"L007 缺{name}: {needle!r}")

    # ── BACKLOG ──
    if not backlog_path.is_file():
        out.append(f"BACKLOG 不存在: {backlog_path}")
        return out
    found_line = None
    for line in backlog_path.read_text(encoding="utf-8").splitlines():
        if "L007 資料損失" in line:
            found_line = line
            break
    if found_line is None:
        out.append("BACKLOG 找不到「L007 資料損失」項")
    else:
        if not found_line.lstrip().startswith("- [x]"):
            out.append("BACKLOG L007 項未勾選 [x]: " + found_line.lstrip()[:60])
        if "round 1459 結案" not in found_line or "R20261111_1516-1" not in found_line:
            out.append("BACKLOG L007 項缺結案註記（round 1459＋票號）: " + found_line.lstrip()[:60])
    return out


def selftest(l007: pathlib.Path, backlog: pathlib.Path) -> int:
    # 正控制：真檔全部判準成立
    v = check(l007, backlog)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:")
        for s in v:
            print("  " + s)
        return 1

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        l_text = l007.read_text(encoding="utf-8")
        b_lines = backlog.read_text(encoding="utf-8").splitlines(keepends=True)
        b_text = "".join(b_lines)

        def run(tag: str, l007_text: str, backlog_text: str, must_hit: str) -> bool:
            lp = tmp / "L007.md"
            bp = tmp / "BACKLOG.md"
            lp.write_text(l007_text, encoding="utf-8")
            bp.write_text(backlog_text, encoding="utf-8")
            vv = check(lp, bp)
            hit = any(must_hit in s for s in vv)
            if not vv or not hit:
                print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
                return False
            return True

        ok = True
        # 註：needle 在 L007 內可能多處出現（§8 本體＋裁決原句引用），一律全量替換，
        # 確保篡改後 needle 完全消失（count=1 會留殘、負控制失效）。
        # (n1) 終態被換成 MECHANISM_CONFIRMED → 終態判準必紅
        ok &= run("n1 終態", l_text.replace("CLOSED: NO_MECHANISM", "CLOSED: MECHANISM_CONFIRMED"),
                  b_text, "結案終態")
        # (n2) e016 通過率被改（A 18/34→A 19/34）→ 資料判準必紅
        ok &= run("n2 通過率", l_text.replace("A 18/34", "A 19/34"), b_text, "通過率 A")
        # (n3) 結論句逐字引用被刪 → 引用判準必紅
        ok &= run("n3 結論句", l_text.replace("C vs C-nf 未顯著（開關無可測效應", "C vs C-nf 有顯著效應"),
                  b_text, "結論句逐字")
        # (n4) BACKLOG 勾選被退回 [ ] → 勾選判準必紅
        ok &= run("n4 BACKLOG 未勾選", l_text,
                  b_text.replace("- [x] **L007 資料損失", "- [ ] **L007 資料損失", 1),
                  "未勾選 [x]")
        # (n5) BACKLOG 結案註記被刪 → 註記判準必紅
        ok &= run("n5 BACKLOG 註記", l_text,
                  b_text.replace("**round 1459 結案（票 R20261111_1516-1）**：", "", 1),
                  "缺結案註記")

    if not ok:
        return 1
    print("VERDICT: L007_CLOSURE_OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋5 負控制")
    ap.add_argument("--l007", type=pathlib.Path, default=L007_DEFAULT)
    ap.add_argument("--backlog", type=pathlib.Path, default=BACKLOG_DEFAULT)
    args = ap.parse_args()
    if args.selftest:
        return selftest(args.l007, args.backlog)
    v = check(args.l007, args.backlog)
    for s in v:
        print(s)
    print("VERDICT: " + ("L007_CLOSURE_OK" if not v else "L007_CLOSURE_FAIL"))
    return 0 if not v else 1


if __name__ == "__main__":
    raise SystemExit(main())
