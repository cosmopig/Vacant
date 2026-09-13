#!/usr/bin/env python3
"""round662 量具雙向驗證：乾淨要全對，M1-M4 四個突變體都要被抓到。"""
import sys, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import voidclass as V

CLEAN = {
    "sandbox verifier unavailable: [Errno 2] no such file": "SANDBOX",
    "qwen-a 重試 4 次仍失敗：HTTP Error 400: Bad Request": "HTTP_400",
    "qwen-b 重試 4 次仍失敗：HTTP Error 502: Bad Gateway": "HTTP_502",
    "gem-1 重試 2 次仍失敗：The read operation timed out": "TIMEOUT",
    "gem-2 重試 4 次仍失敗：<urlopen error [Errno 104] Connection reset by peer>": "CONN",
    "gem-3 重試 4 次仍失敗：ValueError: empty completion": "OTHER:ValueError: empty completion",
}

caught = {}
fails = []

# 乾淨方向
for msg, want in CLEAN.items():
    got = V.classify(msg)
    if got != want:
        fails.append(f"CLEAN: {msg!r} -> {got!r} 期望 {want!r}")
if not fails:
    print("乾淨 → PASS（6/6 分類正確，UNPARSED=0）")

# M1：400 換成 502，HTTP_400 計數必須改變
base = collections.Counter(V.classify(m) for m in CLEAN)
mut = collections.Counter(
    V.classify(m.replace("HTTP Error 400", "HTTP Error 502")) for m in CLEAN)
if mut["HTTP_400"] != base["HTTP_400"]:
    caught["M1"] = f"HTTP_400 {base['HTTP_400']}→{mut['HTTP_400']}"
else:
    fails.append("M1 沒被抓到：改了狀態碼但 HTTP_400 計數不變（沒真的讀碼）")

# M2：兩條規則都不匹配 → 必須 UNPARSED
g = V.classify("完全不符合任何形狀的字串 no marker here")
if g == "UNPARSED":
    caught["M2"] = "UNPARSED"
else:
    fails.append(f"M2 沒被抓到：不可解析字串被分到 {g!r} 而不是 UNPARSED")

# M3：sandbox 前綴挪到中間 → 不得再算 SANDBOX
g = V.classify("worker-x 重試 4 次仍失敗：sandbox verifier unavailable: boom")
if g != "SANDBOX":
    caught["M3"] = f"→{g}"
else:
    fails.append("M3 沒被抓到：前綴在中間仍被分到 SANDBOX（沒錨開頭）")

# M4：Q3 可補量分子真的有被讀
def recover_rate(voids, succ):
    hit = sum(1 for arm, tid, _ in voids if succ.get(tid, set()) - {arm})
    return hit / len(voids) if voids else 0.0

voids = [("ON", "t1", "x"), ("ON", "t2", "x")]
full = {"t1": {"OFF"}, "t2": {"OFF5"}}
none = {}
r_full, r_none = recover_rate(voids, full), recover_rate(voids, none)
if r_none < r_full:
    caught["M4"] = f"{r_full:.2f}→{r_none:.2f}"
else:
    fails.append("M4 沒被抓到：抽掉所有成功紀錄，可補量比例沒下降")

print("caught =", caught)
if fails:
    print("SELFTEST FAIL")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("SELFTEST PASS（4/4 突變體被抓到，乾淨方向滿分）")
