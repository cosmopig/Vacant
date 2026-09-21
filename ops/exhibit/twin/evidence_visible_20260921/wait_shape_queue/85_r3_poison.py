"""第三輪那把尺自己的負控制：把三行承重的碼拿掉，尺必須紅。

拿掉的三行各對應一個實拍抓到的錯：
  1 `drawFormingQueue();`          → 排隊的人在畫面上又只剩一列靜止的字
  2 `arrivals.spawned(sub.id)`     → 投遞口對著已經在成形的那一位寫「接下來就是他」
  3 角落卡的讓位                    → 兩張板疊死，兩張都讀不到
"""
import pathlib, shutil, subprocess, sys

M = pathlib.Path("/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/"
                 "ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/mirror3")
P = M / "world3/index.html"
BAK = P.with_suffix(".html.bak")
shutil.copy(P, BAK)
try:
    s = P.read_text(encoding="utf-8")
    cuts = [
        "    drawFormingQueue();\n",
        "    if (!WAITQ_OFF) { try { arrivals.spawned(sub.id); } catch (e) {} }\n",
        "  if (dockUp) y = Math.min(y, dockGeom().y - bh - H * 0.014);\n",
    ]
    for c in cuts:
        if s.count(c) != 1:
            sys.exit(f"🔴 找不到（或不只一處）要拿掉的那一行：{c!r}")
        s = s.replace(c, "")
    P.write_text(s, encoding="utf-8")
    r = subprocess.run(["node", "tools/waitcheck.mjs"], cwd=M,
                       capture_output=True, text=True)
    print(r.stdout)
    print(r.stderr, file=sys.stderr)
    print(f"exit={r.returncode}")
finally:
    shutil.move(BAK, P)
    print("（已還原）")
