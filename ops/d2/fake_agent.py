#!/usr/bin/env python3
"""selftest 用的假 agent（不碰模型）：照提示裡的網址用 http_proxy 抓頁面，把 report.md 的值填成頁面規格表上的值。
只驗執行器、評分、稽核的接線；不代表任何模型的行為。"""
import pathlib
import re
import sys
import urllib.request

prompt = sys.argv[1]
urls = sorted(set(re.findall(r"http://[a-z0-9.-]+/p\d\.html", prompt)))
rows = {}
for u in urls:
    html = urllib.request.urlopen(u, timeout=10).read().decode()
    name = re.search(r"<h1>(.*?)</h1>", html).group(1)
    for lab, val in re.findall(r"<tr><td>(.*?)</td><td>(.*?)</td></tr>", html):
        rows[(name, lab)] = val
rep = pathlib.Path("report.md")
out = []
for line in rep.read_text().splitlines():
    m = re.match(r"^- (.+?) — (.+?): (.*)$", line)
    if m and (m.group(1), m.group(2)) in rows:
        line = f"- {m.group(1)} — {m.group(2)}: {rows[(m.group(1), m.group(2))]}"
    out.append(line)
rep.write_text("\n".join(out) + "\n")
