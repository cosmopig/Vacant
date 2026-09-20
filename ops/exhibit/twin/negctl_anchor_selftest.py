"""對 `twinanchor.py selftest` 本身的負控制——**證明那 20 個綠燈量得動**。

## 為什麼需要這一支

`twinanchor.py selftest` 第一次跑就 20/20 全綠。**那個數字本身不是證據**：
一支什麼都沒量的自檢也會印 20/20。這個 repo 已經吃過一次虧
（「核心判準四輪實跑都印綠燈而根本沒在量」），所以規矩是：

> **判成綠之前，先證明它紅得起來。**

做法：把偵測能力／攻擊本身逐一拿掉，selftest 必須跟著變紅，而且要紅在
**對的那幾條**上。三個情境：

| 拿掉什麼 | selftest 應該紅在 |
|---|---|
| ① `verify_all` 永遠回綠（偵測能力整個拿掉） | 負控制 A/B/C/D/E 全倒 |
| ② `simulate_full_rewrite` 什麼都不做（攻擊沒發生） | 負控制 A |
| ③ `simulate_truncate` 什麼都不做（攻擊沒發生） | 負控制 B |

②③ 這兩個特別重要：它們排除「錨定其實是在抓別的東西，只是剛好紅了」。

用法：
    python3 ops/exhibit/twin/negctl_anchor_selftest.py   # 退出碼 0 ＝ selftest 量得動
"""
from __future__ import annotations

import contextlib
import io
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve()
ROOT = HERE.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import twinanchor as ta  # noqa: E402


def run(tag: str, patch) -> tuple[int, list[str]]:
    saved = (ta.verify_all, ta.simulate_full_rewrite, ta.simulate_truncate)
    patch()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = ta.selftest()
    ta.verify_all, ta.simulate_full_rewrite, ta.simulate_truncate = saved
    fails = [ln for ln in buf.getvalue().splitlines() if ln.startswith("[FAIL]")]
    print(f"--- {tag}: rc={rc}  FAIL 條數={len(fails)}")
    for f in fails:
        print("   ", f)
    return rc, fails


def _p1() -> None:
    """① 偵測能力整個拿掉：verify_all 永遠說綠。"""
    ta.verify_all = lambda *a, **k: {
        "ok": True, "failures": [], "warnings": [], "pubkey_pinned": True,
        "no_rollback": {"ok": True}, "stream_bound": {"ok": True},
        "slip": {"ok": True}, "per_anchor": [], "anchors": 0,
    }


def _p2() -> None:
    """② 攻擊沒發生：整條重算改成 no-op（回報卻照樣說「少了一列」）。"""
    ta.simulate_full_rewrite = lambda db, drop_seqs=(): {
        "before": 8, "after": 7, "dropped": list(drop_seqs)}


def _p3() -> None:
    """③ 攻擊沒發生：截斷改成 no-op。"""
    ta.simulate_truncate = lambda db, n: {"before": 8, "after": 8, "removed": 0}


def main() -> int:
    rc1, f1 = run("① verify_all 永遠綠（偵測能力拿掉）", _p1)
    rc2, f2 = run("② 整條重算沒真的發生（攻擊拿掉）", _p2)
    rc3, f3 = run("③ 截斷沒真的發生（攻擊拿掉）", _p3)

    ok = (rc1 == 1 and rc2 == 1 and rc3 == 1
          and any("負控制 A" in x for x in f1)
          and any("負控制 B" in x for x in f1)
          and any("負控制 A" in x for x in f2)
          and any("負控制 B" in x for x in f3))
    print()
    print("負控制總結：",
          "PASS（selftest 量得動，紅得起來）" if ok else "FAIL（selftest 是假綠燈）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
