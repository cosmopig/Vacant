#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把抵達層那一段**逐字**抄進證據目錄。

為什麼要這一份：這次的改動活在**另一個 repo 的未提交工作樹**（vacant_hm，
同時有十幾個 agent 在動同一個檔），沒有 commit 可以指。只留一個 sha 的話，
那棵樹被 reset 之後這批證據就指向一段誰也找不回來的碼。

⚠ 這是**抄本不是 patch**：它不能 `git apply`。要還原現場行為用網址參數
   `?arrive=0`（一行，不改碼）；要對帳就拿這一份跟當下的 index.html 比。
"""
import hashlib, os, re

HM = os.path.expanduser("~/Documents/GitHub/vacant_hm/world3/index.html")
DST = ("/Users/cosmopig/Documents/GitHub/Vacant/.claude/worktrees/wf_32a45899-6ee-1"
       "/ops/exhibit/twin/evidence_visible_20260921/arrival_beat/ARRIVAL_LAYER_extract.js")

raw = open(HM, "rb").read()
sha = hashlib.sha256(raw).hexdigest()
lines = raw.decode("utf-8").split("\n")

# 區塊頭尾用內容找，不寫死行號（別的 agent 一直在這個檔的別處加東西）
start = end = None
for i, ln in enumerate(lines):
    if start is None and ln.startswith("/* ══ 抵達層"):
        start = i
    elif start is not None and ln.startswith("/* ══ 等待態"):
        end = i
        break
assert start is not None and end is not None, "找不到區塊邊界——**不要當成 0 行，當成沒找到**"

call_sites = []
for i, ln in enumerate(lines):
    if i >= start and i < end:
        continue
    if re.search(r"arrivals\.(arrive|holding)\(", ln) or "ARRIVE_ON" in ln:
        call_sites.append((i + 1, ln.strip()))

hdr = [
    "/* 抵達層（arrivals）逐字抄本 —— 給證據目錄用，**不是可 apply 的 patch**",
    " *",
    " * 來源：vacant_hm/world3/index.html",
    " * sha256：" + sha,
    " * 區塊：第 %d–%d 行（共 %d 行），邊界用內容找（'══ 抵達層' → '══ 等待態'）" % (
        start + 1, end, end - start),
    " *",
    " * 一行還原：網址加 ?arrive=0 ⇒ ARRIVE_ON=false ⇒ arrive()／update()／draw()",
    " *           全部提早 return，畫面回到改動前。**不用改碼。**",
    " *",
    " * 區塊外面的呼叫點（同一份 index.html，行號對應上面那個 sha）：",
]
for n, s in call_sites:
    hdr.append(" *   L%-5d %s" % (n, s[:110]))
hdr += [
    " *",
    " * ⚠ 這個檔**不會被任何東西載入**。它是抄本，改它不會改到展件。",
    " */",
    "",
]
with open(DST, "w", encoding="utf-8") as f:
    f.write("\n".join(hdr))
    f.write("\n".join(lines[start:end]))
    f.write("\n")
print(DST, os.path.getsize(DST), "bytes ·", end - start, "行 · 呼叫點", len(call_sites))
for n, s in call_sites:
    print("  L%-5d %s" % (n, s[:100]))
