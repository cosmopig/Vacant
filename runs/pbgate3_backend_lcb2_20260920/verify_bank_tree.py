#!/usr/bin/env python3
"""把 ops/gain/r534/{templates,hidden} 的每個檔案逐份比對 bank_manifest.json 的釘值。

為什麼不直接用 `ops/gain/r534/build_bank.py --check`：那一支會先重跑**選題**，
而選題要讀 `runs/g_r460_harness_lcb2_*/rows.jsonl`／`runs/g_r532_lcb2_*/rows.jsonl`
（1.7 G 的歸檔資料）。執行端只剩 3.1 G 磁碟，不搬 runs/。
這一支**只驗渲染結果**，判準與 build_bank 的 `--check` 是同一組 sha256
（manifest 的 `tasks.<id>.sha256`），fail-closed：對不上就非零退出。

⚠ 單邊：這證明「這棵樹與 Mac 上 `--check` 過的那一棵逐位元相同」，
   不證明選題規則本身；規則的驗證留在有 runs/ 的那一側。
"""
import hashlib, json, os, sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if len(sys.argv) > 1:
    REPO = os.path.abspath(sys.argv[1])
R534 = os.path.join(REPO, "ops", "gain", "r534")
man = json.load(open(os.path.join(R534, "bank_manifest.json"), encoding="utf-8"))

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()

bad, n = [], 0
for tid, t in man["tasks"].items():
    for rel, want in t["sha256"].items():
        if rel.startswith("hidden/"):
            p = os.path.join(R534, rel)
        else:
            p = os.path.join(R534, "templates", tid, rel)
        n += 1
        if not os.path.exists(p):
            bad.append((p, "MISSING", want)); continue
        got = sha(p)
        if got != want:
            bad.append((p, got, want))
mh = sha(os.path.join(R534, "bank_manifest.json"))
pinned = open(os.path.join(R534, "bank_manifest.sha256"), encoding="utf-8").read().split()[0]
print("manifest sha256 =", mh, "pinned =", pinned, "OK" if mh == pinned else "MISMATCH")
print("files checked   =", n, " tasks =", len(man["tasks"]))
for p, got, want in bad:
    print("MISMATCH", p, got, want)
ok = (not bad) and mh == pinned
print("verdict =", "OK" if ok else "FAIL")
sys.exit(0 if ok else 1)
