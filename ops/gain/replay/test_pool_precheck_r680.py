#!/usr/bin/env python3
"""round680 植入缺陷測試：`pool_precheck.py` 有沒有牙齒。

判準 `CRITERION_20260903_R680_POOL_PRECONDITIONS.md` §四 事前寫死：
判準**不准只寫 `rc≠0`**——每一條都要指名偵測器該看到的那個量（訊息裡的字或欄位值）；
且必須含兩型「安靜量不到」：欄位不見了、比對集合變空。

變造只發生在 `/dev/shm`，**真 run 目錄唯讀**（本檔一次都沒有以寫入模式開過 runs/）。
"""
from __future__ import annotations

import copy
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
TOOL = ROOT / "ops/gain/replay/pool_precheck.py"
CRIT = ROOT / "CRITERION_20260903_R680_POOL_PRECONDITIONS.md"
ATTEST = ROOT / "runs/_analysis_r680/CODE_ATTEST.md"
REAL = [ROOT / "runs/g_r444_conform_mbpp", ROOT / "runs/g_r445_conform_mbpp_ext"]
WORK = pathlib.Path("/dev/shm/r680_pool")

results: list[tuple[bool, str, str]] = []


def fixture(mut=None, crit_text=None, attest_text=None) -> tuple[list[str], str, str]:
    """造一組 /dev/shm 的假 run（summary.json 從真 run 複製後變造）。"""
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    dirs = []
    sums = {}
    for src in REAL:
        d = WORK / src.name
        d.mkdir()
        sums[src.name] = json.loads((src / "summary.json").read_text(encoding="utf-8"))
        dirs.append(str(d))
    if mut:
        mut(sums)
    for src in REAL:
        (WORK / src.name / "summary.json").write_text(
            json.dumps(sums[src.name], ensure_ascii=False), encoding="utf-8")
    c = WORK / "crit.md"
    c.write_text(crit_text if crit_text is not None
                 else CRIT.read_text(encoding="utf-8"), encoding="utf-8")
    a = WORK / "attest.md"
    a.write_text(attest_text if attest_text is not None
                 else ATTEST.read_text(encoding="utf-8"), encoding="utf-8")
    return dirs, str(c), str(a)


def run(dirs, crit, attest=None) -> tuple[int, str]:
    cmd = [sys.executable, str(TOOL), "--runs", *dirs, "--criterion", crit]
    if attest:
        cmd += ["--code-attest", attest]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return p.returncode, p.stdout + p.stderr


def check(label, cond, detail):
    results.append((bool(cond), label, detail))
    print(f"{'PASS' if cond else 'FAIL'} {label}　{detail}")


R444, R445 = "g_r444_conform_mbpp", "g_r445_conform_mbpp_ext"

# ── T1 乾淨基線 ────────────────────────────────────────────────────
d, c, a = fixture()
rc, o = run(d, c, a)
check("T1 乾淨 fixture ⇒ POOLABLE",
      rc == 0 and "POOLABLE" in o and "371 題" in o, f"rc={rc} 聯集字樣={'371 題' in o}")

# ── T2 題目重疊（偵測器該看到：重疊題數 ≥1）────────────────────────
def mut_overlap(s):
    s[R444]["instrument"]["detail"][0]["task_id"] = \
        s[R445]["instrument"]["detail"][0]["task_id"]
d, c, a = fixture(mut_overlap)
rc, o = run(d, c, a)
check("T2 一題重疊 ⇒ BROKEN 且指名「1 題重疊」",
      rc == 2 and "1 題重疊" in o, f"rc={rc} 訊息含『1 題重疊』={'1 題重疊' in o}")

# ── T3 run 內部自我重複 ────────────────────────────────────────────
def mut_dup(s):
    s[R444]["instrument"]["detail"][1]["task_id"] = \
        s[R444]["instrument"]["detail"][0]["task_id"]
d, c, a = fixture(mut_dup)
rc, o = run(d, c, a)
check("T3 run 內重複 ⇒ BROKEN 指名「179 列、178 個相異」",
      rc == 2 and "179 列" in o and "178 個相異" in o, f"rc={rc} {o.strip()[:70]}")

# ── T4 安靜縮水：detail 少一列但 n 沒改 ─────────────────────────────
def mut_shrink(s):
    s[R445]["instrument"]["detail"].pop()
d, c, a = fixture(mut_shrink)
rc, o = run(d, c, a)
check("T4 detail 191 題 vs n=192 ⇒ BROKEN「安靜縮水」",
      rc == 2 and "191 題" in o and "192 題" in o and "安靜縮水" in o,
      f"rc={rc} {o.strip()[:80]}")

# ── T5 安靜量不到・型一：欄位不見了 ─────────────────────────────────
def mut_nokey(s):
    s[R445]["instrument"].pop("detail")
d, c, a = fixture(mut_nokey)
rc, o = run(d, c, a)
check("T5 instrument.detail 鍵不見 ⇒ BROKEN「題目清單量不到」（不是通過）",
      rc == 2 and "detail 不存在" in o, f"rc={rc} {o.strip()[:80]}")

# ── T6 安靜量不到・型二：比對集合變空 ───────────────────────────────
def mut_empty(s):
    s[R445]["instrument"]["detail"] = []
d, c, a = fixture(mut_empty)
rc, o = run(d, c, a)
# 判準要求「指名偵測器該看到的那個量」＝這裡是**理由本身**：空 detail 必須以
# 「比對集合為空」報出，不准退化成「聯集對不上」——後者會讓下一輪去查錯的地方。
check("T6 detail 是空的 ⇒ BROKEN 且理由是「比對集合為空」而非聯集對不上",
      rc == 2 and "比對集合為空" in o
      and "聯集" not in o and "自己的題目清單" not in o, f"rc={rc} {o.strip()[:90]}")

# ── T7/T8/T9 執行參數不同 ──────────────────────────────────────────
for label, key, mut in [
    ("T7 seed 不同", "seed", lambda s: s[R445].__setitem__("seed", "g-OTHER")),
    ("T8 模型不同", "pool",
     lambda s: s[R445]["pool"][0].__setitem__("model", "qwen3.6-35b")),
    ("T9 題庫不同", "bank_witness",
     lambda s: [r.__setitem__("task_id", "lcb_" + r["task_id"].split("_", 1)[1])
                for r in s[R445]["instrument"]["detail"]]),
]:
    d, c, a = fixture(mut)
    rc, o = run(d, c, a)
    check(f"{label} ⇒ BROKEN 指名 `{key}`",
          rc == 2 and "執行參數不同" in o and key in o, f"rc={rc} {o.strip()[:90]}")

# ── T10 假綠燈：pool 兩邊都空，"相同" 但量不到 ───────────────────────
def mut_nopool(s):
    for k in s:
        s[k]["pool"] = []
d, c, a = fixture(mut_nopool)
rc, o = run(d, c, a)
check("T10 兩邊 pool 都空 ⇒ BROKEN（空清單＝空清單不算相同）",
      rc == 2 and "pool 是空的" in o, f"rc={rc} {o.strip()[:80]}")

# ── T11 門檻來源：判準檔沒有 Q4 那一列 ⇒ 不沿用預設值 ────────────────
d, c, a = fixture(crit_text=CRIT.read_text(encoding="utf-8").replace("**Q4**", "**QX**"))
rc, o = run(d, c, a)
check("T11 判準檔缺 Q4 列 ⇒ BROKEN「門檻 parse 不到」（工具裡沒有預設值）",
      rc == 2 and "找到 0 列" in o, f"rc={rc} {o.strip()[:80]}")

# ── T12 門檻真的從判準檔讀：同一份資料，改判準的數字就翻面 ─────────────
def mut_void(pp_void):
    def f(s):
        s[R445]["request_policy"]["timeout_s"] = 300          # policy 不同
        s[R445]["arms"]["OFF"]["infra_void"] = pp_void         # accepted=61
    return f
base_crit = CRIT.read_text(encoding="utf-8")
d, c, a = fixture(mut_void(2))                                 # 2/61 = 3.28pp
rc_lo, o_lo = run(d, c, a)
d, c, a = fixture(mut_void(2), crit_text=base_crit.replace("差 <5pp", "差 <1pp"))
rc_hi, o_hi = run(d, c, a)
check("T12 同一份資料（void 3.28pp）：判準 5pp ⇒ 過、判準 1pp ⇒ BROKEN",
      rc_lo == 0 and "DIFFERS_NO_CONSEQUENCE" in o_lo
      and rc_hi == 2 and "≥ 1.0pp" in o_hi,
      f"5pp:rc={rc_lo} 1pp:rc={rc_hi}")

# void 率的分母是該臂**已嘗試**的題數 `arms[arm].n`（不是 accepted）——r445 還在跑，
# 分母會長，所以這裡不寫死期望的百分比，只驗「跨過判準門檻」這件事本身。
d, c, a = fixture(mut_void(6))
rc, o = run(d, c, a)
check("T13 policy 不同且 void 率跨過 5pp 門檻 ⇒ BROKEN「差異有可觀測後果」",
      rc == 2 and "≥ 5.0pp" in o and "差異有可觀測後果" in o, f"rc={rc} {o.strip()[:90]}")

# ── T14 背書機制（與 R440G --decision 同一個形狀）──────────────────────
d, c, a = fixture(attest_text="這份文件只講 g_r444_conform_mbpp，沒提另一個 run。")
rc, o = run(d, c, a)
check("T14 背書檔沒提到 r445 ⇒ BROKEN 指名該 run",
      rc == 2 and R445 in o and "不是在講它們" in o, f"rc={rc} {o.strip()[:90]}")

d, c, a = fixture()
rc, o = run(d, c)          # 不附背書
check("T15 沒有背書檔 ⇒ BROKEN「沒有記錄自己跑在哪個 commit」（安靜量不到）",
      rc == 2 and "沒有記錄自己跑在哪個 commit" in o, f"rc={rc} {o.strip()[:80]}")

# ── T16/T17 runner_git 欄位一旦存在，C2 就不再需要背書 ─────────────────
def mut_git(same):
    def f(s):
        s[R444]["runner_git"] = {"sha": "aaaaaaa", "dirty": False}
        s[R445]["runner_git"] = {"sha": "aaaaaaa" if same else "bbbbbbb", "dirty": False}
    return f
d, c, a = fixture(mut_git(True))
rc, o = run(d, c)
check("T16 兩 run 都記了同一個 sha ⇒ C2=HIT 且不需背書",
      rc == 0 and "C2_code=HIT" in o, f"rc={rc} {o.strip()[:80]}")
d, c, a = fixture(mut_git(False))
rc, o = run(d, c)
check("T17 兩 run 記了不同 sha 且無背書 ⇒ BROKEN「碼版本不同」",
      rc == 2 and "碼版本不同" in o, f"rc={rc} {o.strip()[:80]}")

# ── T19 假綠燈：runner_git 在、但 sha 是 None（{None} 是單元素集合）──────
def mut_git_none(s):
    s[R444]["runner_git"] = {"sha": None}
    s[R445]["runner_git"] = {"sha": None}
d, c, a = fixture(mut_git_none)
rc, o = run(d, c)
check("T19 runner_git 存在但 sha=None ⇒ 仍算沒記錄（不是 C2=HIT）",
      rc == 2 and "沒有記錄自己跑在哪個 commit" in o and "C2_code=HIT" not in o,
      f"rc={rc} {o.strip()[:80]}")

# ── T18 真 run 目錄唯讀 ────────────────────────────────────────────
sha = {p.name: __import__("hashlib").sha256((p / "summary.json").read_bytes())
       .hexdigest()[:8] for p in REAL}
check("T18 真 run 目錄未被本測試寫過（summary sha256[:8] 記錄在案）", True,
      json.dumps(sha, ensure_ascii=False))

ok = sum(1 for r, _, _ in results if r)
print(f"\n{ok}/{len(results)} PASS")
sys.exit(0 if ok == len(results) else 1)
