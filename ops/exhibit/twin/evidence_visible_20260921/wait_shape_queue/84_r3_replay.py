"""把一批改動從 A→B **原封不動**搬到第三個檔上。

為什麼不用 `patch -p1`：`patch` 對漂掉的基底會用 fuzz／offset 套到錯的位置，
**而且退出碼還是 0**（第二輪實測，`wait_shape/README.md` §八）。
這一支的做法是**錨定式取代**：每一段改動連同前後各 CTX 行 context 當成一個
字串，在目標檔裡**必須剛好出現一次**，否則整支停下來不寫檔。

🔴 **這一支自己也說過一次謊**（2026-09-21 14:40，本輪實際踩到）：
   第一版把每個 difflib opcode 各自當一段。兩段改動只隔 4 行時，它們的
   context 會**重疊**；第一段替換完，第二段的 `old` 就不在字串裡了，
   而 `str.replace(old, new, 1)` 對找不到的字串是**安靜地什麼都不做**——
   於是角落卡那兩行改動整段掉了，而這支腳本回報「12 段全部寫入」。
   是下游的 `waitcheck.mjs` W13z（一條掃描判準）把它抓出來的。
   兩個修法都上：
     (1) 相鄰太近的 opcode **先合併成一段**（gap ≤ 2·CTX ⇒ 不可能重疊）；
     (2) 每一次 `replace` 之後**檢查字串真的變了**，沒變就中止。
   ⇒ 「安靜地少做一件事」這條路被關掉了。

用法：python3 r3_replay.py <改動前> <改動後> <目標檔> [輸出檔]
"""
import difflib, pathlib, sys

a_p, b_p, t_p = map(pathlib.Path, sys.argv[1:4])
out_p = pathlib.Path(sys.argv[4]) if len(sys.argv) > 4 else t_p

A = a_p.read_text(encoding="utf-8").split("\n")
B = b_p.read_text(encoding="utf-8").split("\n")
T = t_p.read_text(encoding="utf-8")

CTX = 6
sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
ops = [list(o) for o in sm.get_opcodes() if o[0] != "equal"]

# (1) 合併：兩段在 A 上的距離 ≤ 2·CTX ⇒ context 會重疊 ⇒ 併成一段
merged = []
for op in ops:
    if merged and op[1] - merged[-1][2] <= 2 * CTX:
        p = merged[-1]
        p[2], p[4] = op[2], op[4]          # i2, j2 往後吃
        p[0] = "replace"
    else:
        merged.append(op)
print(f"改動段落：{len(ops)} → 合併後 {len(merged)}")

blocks = []
for tag, i1, i2, j1, j2 in merged:
    lo, hi = max(0, i1 - CTX), min(len(A), i2 + CTX)
    old = "\n".join(A[lo:i1] + A[i1:i2] + A[i2:hi])
    new = "\n".join(A[lo:i1] + B[j1:j2] + A[i2:hi])
    blocks.append((i1, old, new))

bad = 0
for i1, old, new in blocks:
    n = T.count(old)
    if n != 1:
        print(f"🔴 第 {i1+1} 行附近那一段在目標檔裡出現 {n} 次（要剛好 1 次）")
        print("   " + old.strip().split("\n")[0][:90])
        bad += 1
if bad:
    sys.exit(f"🔴 {bad} 段對不上，什麼都沒寫。")

for i1, old, new in blocks:
    before = T
    T = T.replace(old, new, 1)
    # (2) 沒變就是沒套到——不准安靜跳過
    if T == before and old != new:
        sys.exit(f"🔴 第 {i1+1} 行那一段 replace 之後字串沒變（套失敗），中止。")
out_p.write_text(T, encoding="utf-8")
print(f"寫進 {out_p}（{len(T.splitlines())} 行）")
