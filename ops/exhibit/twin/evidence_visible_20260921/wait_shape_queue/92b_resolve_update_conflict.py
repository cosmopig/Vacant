#!/usr/bin/env python3
"""第三輪合併衝突的解法（只有一處，`director.update(dt)` 的開頭）。

兩邊**都是插入**、插在同一個點上，所以 `git merge-file` 判不出先後：

  現行（別的代理今天稍早加的）：`if (this.mode === "wait"){ … return; }`
      待機那一格自己的迴圈——`toDrop()` 切到郵筒、`waitAction()`、
      每 9–18 秒有人轉頭看投遞口。**它會 `return`。**
  等待態（本條）：`this.waitTick();` ＋ `if (this.mode === "visitor_wait"){ … }`

**順序是語意不是排版**：`waitTick()` 是等待態的相位機
（forming → centre → corner → retiring → retired），而觀眾投完卡、土堆縮到角落
之後 `mode` 會走回 `"wait"`（演完一段重播就 `toWait()`）。把 `waitTick()` 排在
那個會 `return` 的區塊後面 ⇒ 相位機在待機時停擺 ⇒ **那一團土會永遠留在角落，
退役儀式永遠不會演**。所以：`waitTick()` 先，然後兩個 mode 區塊（互斥，誰先都行）。

用法：python3 r3_resolve.py <merged.html>
"""
import sys, re, pathlib

p = pathlib.Path(sys.argv[1])
lines = p.read_text(encoding="utf-8").split("\n")

out, i, n = [], 0, 0
while i < len(lines):
    if lines[i].startswith("<<<<<<< "):
        j = i + 1
        ours = []
        while not lines[j].startswith("||||||| "):
            ours.append(lines[j]); j += 1
        j += 1
        base = []
        while lines[j] != "=======":
            base.append(lines[j]); j += 1
        j += 1
        theirs = []
        while not lines[j].startswith(">>>>>>> "):
            theirs.append(lines[j]); j += 1
        if [l for l in base if l.strip()]:
            sys.exit("🔴 基底不是空的（不是單純的兩邊各自插入）——停下來自己看。")
        out.extend(theirs)
        out.extend(ours)
        n += 1
        i = j + 1
        continue
    out.append(lines[i]); i += 1

p.write_text("\n".join(out), encoding="utf-8")
print(f"解了 {n} 處（等待態在前、現行 wait 區塊在後）")
