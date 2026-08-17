#!/usr/bin/env python3
"""S9：展件的世界模擬裡，被抓之後的居民會不會再拿到工作。

**為什麼要有這一支**（第 114 輪）：

人類 2026-08-17 裁定（`DECISION_SLASH.md`）：`slash_n_factor` 維持 1.0，
**代價寫進展場，不藏**。代價是 S1 量到的 **0/368**——600 輪內一個都沒回來過。

但展件寫的是相反的話：`vacant_hm/world/js/slash.js:31` 寫「被 slash 之後
**不是永久除名**」，`sim-bridge.js` 三處寫死 `recovers = true`，理由是
「『被抓過就再也回不來』其實只是觀眾沒待夠久，正解是壓縮世界時間」。

S1 量到的成因是**時鐘停走**（不被路由 ⇒ 沒有事件 ⇒ 不 decay）。
時鐘停走的話，把時間壓縮幾倍都是乘以零 ⇒ 那個理由與量到的成因對不上。

⇒ 兩邊至少有一邊在對觀眾說錯話。**這一支只量，不改展件任何一行。**

量的定義**逐字沿用 Python S1**（`vacant/entrycost.py:321-327`）：

    rounds_to_next_route = first_route_after_slash − first_slash_round
    None ＝ 本場輪數內沒有再被路由過（**右設限**，報的時候必須連
            rounds_after_slash ＝ horizon − first_slash_round 一起報）

只認**第一次**被 slash 的身份（S1 同款理由：換身份重生是另一條路）。

—— 誠實邊界 ——
* 量的是**展件自己的 JS 模擬**，不是 Vacant 的 Python 機制，也不是真模型。
  兩份是不同的程式，量到不一致**不等於**哪一邊是 bug。
* 「回來率高」不等於展件說謊——展件可以有意識地演一個比機制寬容的世界，
  只要畫面上講明白。**這一支不下判定，只給數字。**

—— 兩件刻意的設計 ——
① **計數器與採集分開。** JS 只吐原始軌跡（每一件派工交給誰、第一次 slash 在
   第幾件），`rounds_to_next_route` 由本檔的 `measure()` 算。於是計數器可以
   餵合成軌跡做已知答案自驗（`--self-test`），而那正是「量到 0」與
   「線根本沒接上」分不開的地方（S1 §一 同款理由）。
② **不在 `vacant_hm` 裡放任何檔案。** 起 `http.server` 指到 repo 根，
   導到一個 404 URL（同源），再用動態 `import()` 把模組拉進來。
   所以 `vacant_hm` 的 `git status` 可以逐字不變——那是本輪的 S1 判準。

用法：
    python3 runs/s9_slash_return.py --self-test
    python3 runs/s9_slash_return.py --run OUTDIR [--seeds 30] [--horizon 600]
    python3 runs/s9_slash_return.py --report OUTDIR
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
sys.path.insert(0, str(HOME / "vacant" / "vacant-docs-web" / "probe"))
import cdp  # noqa: E402  ← 全 repo 唯一那份 CDP 客戶端（HANDOFF §8：不寫第二份）

CHROME = HOME / ".local" / "bin" / "chrome-headless-shell"
HM_ROOT = HOME / "vacant" / "vacant_hm"
CFLAGS = ["--disable-gpu", "--no-sandbox", "--hide-scrollbars",
          "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
DBG_PORT = 9347
HTTP_PORT = 8747


# ══════════════════════════════════════════════════════════════════════
# 一、計數器（被自驗的那個東西）
# ══════════════════════════════════════════════════════════════════════

def measure(trace: dict, horizon: int) -> dict:
    """從一條原始軌跡算出 S1 的兩個欄位。

    `trace` 需要兩個鍵：
      `dispatches` —— 陣列，第 k 項＝第 k 件派工交給的居民索引（k 從 0 起算）
      `slash`      —— {"i": 居民索引, "round": 第幾件派工當下被 slash} 或 None

    回傳 S1 的欄位名，逐字相同，方便兩邊並排。
    """
    sl = trace.get("slash")
    if sl is None:
        return {"slashed": False, "first_slash_round": None,
                "rounds_to_next_route": None, "rounds_after_slash": None,
                "routes_after_slash": 0}
    who, r0 = sl["i"], sl["round"]
    d = trace["dispatches"]
    first_after = None
    routes_after = 0
    # 從 r0+1 起算。第 r0 件是「被 slash 那一刻已經在檯面上的那一件」，
    # 它是**在 slash 之前**派出去的 ⇒ 不算回來。少了這個 +1，計數器會把
    # 每一場都讀成「等 0 輪就回來了」——`--self-test` 的 P0a 就是這樣抓到的。
    for k in range(r0 + 1, min(len(d), horizon)):
        if d[k] == who:
            routes_after += 1
            if first_after is None:
                first_after = k
    return {
        "slashed": True,
        "first_slash_round": r0,
        "rounds_to_next_route": (first_after - r0) if first_after is not None else None,
        "rounds_after_slash": horizon - r0,
        "routes_after_slash": routes_after,
    }


# ── P0：已知答案，兩個方向 ────────────────────────────────────────────
# 正向＝一定量得到（第 137 件又交給他 ⇒ 37）
# 負向＝一定量不到（100 之後再也沒有他 ⇒ None，而且分母必須是 500）
# 兩格都對才准去量未知的。少了負向，一個「永遠回 None」的壞計數器會剛好
# 印出我事先擔心的那個答案；少了正向，一個「永遠回 0」的也會。
def self_test() -> int:
    HOR = 600
    fails = []

    pos = {"dispatches": [(0 if k != 137 else 7) for k in range(HOR)],
           "slash": {"i": 7, "round": 100}}
    pos["dispatches"][100] = 7          # 被 slash 的那一件本身就是交給他的
    got = measure(pos, HOR)
    if got["rounds_to_next_route"] != 37:
        fails.append(f"P0a 正向：期望 37，得到 {got['rounds_to_next_route']}")

    neg = {"dispatches": [0] * HOR, "slash": {"i": 7, "round": 100}}
    neg["dispatches"][100] = 7
    got2 = measure(neg, HOR)
    if got2["rounds_to_next_route"] is not None:
        fails.append(f"P0b 負向：期望 None，得到 {got2['rounds_to_next_route']}")
    if got2["rounds_after_slash"] != 500:
        fails.append(f"P0b 分母：期望 500，得到 {got2['rounds_after_slash']}")

    print("P0 計數器 fixture：")
    print(f"  P0a 正向（第 137 件回來） rounds_to_next_route = {got['rounds_to_next_route']}  期望 37")
    print(f"  P0b 負向（再也沒有）      rounds_to_next_route = {got2['rounds_to_next_route']}  期望 None")
    print(f"  P0b 右設限分母            rounds_after_slash   = {got2['rounds_after_slash']}  期望 500")
    if fails:
        for f in fails:
            print("FAIL " + f)
        return 1
    print("  ⇒ 2/2 方向都答對，計數器可以拿去量未知的")
    return 0


# ══════════════════════════════════════════════════════════════════════
# 二、採集（在瀏覽器裡跑展件自己的模擬，一行都不改它）
# ══════════════════════════════════════════════════════════════════════

# 走**活體路徑**（`stepSim` 不帶 force ＋ `tickDeliveries` ＋ `applySlash`），
# 因為那才是觀眾看到的那條；暖機路徑根本不叫 `triggerSlash`，量它等於量
# 一個畫面上不存在的東西。時間是自己推的（dt 固定），不等 wall-clock。
COLLECT_JS = r"""
(async () => {
  const W  = await import('/world/js/world.js');
  const SB = await import('/world/js/sim-bridge.js');
  const SL = await import('/world/js/slash.js');
  const ok = await SB.initSim();
  if (!ok) return {error: 'initSim 回 false —— sim.js 沒載到'};

  const HOR = %HORIZON%;
  const RECOVER = %RECOVER%;
  if (RECOVER > 0) SL.setRecover(RECOVER);

  const out = [];
  for (const seed of %SEEDS%) {
    const world = W.buildWorld(30, seed, 'organic');
    const sim = SB.makeSim(world);
    if (!sim) return {error: 'makeSim 回 null'};
    world.works = world.works || [];
    world.edges = world.edges || [];
    // `buildWorld` 已經把 `i` 設成陣列索引（world.js:39）。這裡**不覆寫**，
    // 只斷言——覆寫等於探針動到了被量的對象，而斷言會在假設破掉時大聲壞掉。
    for (let i = 0; i < world.residents.length; i++)
      if (world.residents[i].i !== i) return {error: 'resident.i 不是陣列索引，探針的假設破了'};

    const dispatches = [];          // 第 k 件派工交給誰（居民索引）
    const dims = [];                // 派工那一刻，收工作的人有多亮（route() 的 damp）
    const seen = new Set();
    let slash = null;
    const DT = 1 / 60;
    let t = 0, frames = 0;
    while (dispatches.length < HOR && frames < 400000) {
      frames++;
      t += DT;
      SB.stepSim(world, sim, DT, t);
      SB.tickDeliveries(world, sim, t);
      SL.applySlash(world, t);
      for (const d of sim.live) {
        if (seen.has(d.key)) continue;
        seen.add(d.key);
        dispatches.push(d.worker.i);
        dims.push(+(d.worker.dim ?? 1).toFixed(3));
      }
      if (slash === null) {
        for (const r of world.residents) {
          if (r.slashAt !== undefined) {
            slash = {i: r.i, round: dispatches.length - 1, code: r.code, t: r.slashAt};
            break;
          }
        }
      }
    }
    /* 對照組自己也要有已知答案（第 114 輪事後補，理由寫在報告裡）：
       兩臂印出一模一樣的數字時，「setRecover 沒有效果」與「setRecover 根本
       沒跑到」長得完全一樣。終局狀態分得開——預設 26 秒那一臂，`applySlash`
       會把 `slashAt` 刪掉並讓 dim 回到 1；1e9 那一臂不會。 */
    const first = slash ? world.residents[slash.i] : null;
    out.push({
      seed, frames, world_t: t,
      dispatches, dims, slash,
      final: first ? {still_slashed: first.slashAt !== undefined,
                      dim: +(first.dim ?? 1).toFixed(3),
                      rep: +first.rep.toFixed(3), done: first.done} : null,
      tally: JSON.parse(JSON.stringify(sim.tally)),
      seq: sim.seq,
      residents: world.residents.length,
    });
  }
  return {runs: out};
})()
"""


def collect(seeds, horizon, recover, timeout=900.0):
    """起 http.server ＋ chrome，把軌跡吐回來。**不在 vacant_hm 裡寫任何檔案。**"""
    srv = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(HTTP_PORT),
         "--bind", "127.0.0.1", "--directory", str(HM_ROOT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ch = None
    try:
        time.sleep(1.2)
        ch = cdp.Chrome(str(CHROME), DBG_PORT, size=(900, 600), extra_flags=CFLAGS)
        ch.call("Page.enable")
        # 404 頁：同源、不啟動任何展件程式碼。模組靠動態 import() 拉進來。
        ch.call("Page.navigate", {"url": f"http://127.0.0.1:{HTTP_PORT}/__s9_probe__"})
        time.sleep(1.0)
        js = (COLLECT_JS
              .replace("%HORIZON%", str(horizon))
              .replace("%RECOVER%", str(recover))
              .replace("%SEEDS%", json.dumps(seeds)))
        res = ch.call("Runtime.evaluate",
                      {"expression": js, "awaitPromise": True, "returnByValue": True},
                      timeout=timeout)
        if "exceptionDetails" in res:
            raise RuntimeError(json.dumps(res["exceptionDetails"], ensure_ascii=False)[:800])
        val = res["result"].get("value")
        if val is None:
            raise RuntimeError("Runtime.evaluate 回了 None —— 沒有值就是沒跑到")
        if "error" in val:
            raise RuntimeError(val["error"])
        return val["runs"]
    finally:
        if ch:
            ch.close()
        srv.terminate()
        try:
            srv.wait(timeout=10)
        except Exception:
            srv.kill()


def run(outdir: Path, seeds_n: int, horizon: int) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    seeds = [f"W{i+1}" for i in range(seeds_n)]

    arms = [("live", 0), ("norecover", 10**9)]   # 第二臂＝動畫永不復原（P4 成因分辨）
    for name, rec in arms:
        print(f"── 採集 {name}（recover={rec or '預設 26'}）…", flush=True)
        t0 = time.time()
        runs = collect(seeds, horizon, rec)
        dt = time.time() - t0
        path = outdir / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for r in runs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"   {len(runs)} 場 · {dt:.1f}s · {path}")
    (outdir / "meta.json").write_text(json.dumps(
        {"seeds": seeds, "horizon": horizon, "arms": [a[0] for a in arms]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


# ══════════════════════════════════════════════════════════════════════
# 三、報告
# ══════════════════════════════════════════════════════════════════════

def report(outdir: Path) -> int:
    meta = json.loads((outdir / "meta.json").read_text(encoding="utf-8"))
    horizon = meta["horizon"]
    rc = 0
    print("S9 · 展件世界模擬的「被抓之後還回不回得來」")
    print("資料性質：**機制模擬**（展件的 JS 模擬），不是真模型、不是 Vacant 的 Python 機制。")
    print(f"定義逐字沿用 S1：rounds_to_next_route ＝ 再次被路由的派工序號 − 被 slash 的派工序號；"
          f"None ＝ {horizon} 件內沒再被路由（右設限）。\n")

    for arm in meta["arms"]:
        rows = [json.loads(l) for l in (outdir / f"{arm}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        print(f"── 臂：{arm} ──")

        # P1：驗後果不驗前提。JS 記到的筆數必須逐值等於模擬自己的計數器。
        bad = [r for r in rows if len(r["dispatches"]) != r["tally"]["dispatched"]]
        thin = [r for r in rows if r["tally"]["dispatched"] < 500]
        print(f"   P1  記到的派工筆數 == sim.tally.dispatched：{len(rows) - len(bad)}/{len(rows)} 逐值相等"
              + (f"  ← FAIL {[r['seed'] for r in bad][:5]}" if bad else ""))
        print(f"   P1  dispatched >= 500：{len(rows) - len(thin)}/{len(rows)}"
              + (f"  ← FAIL {[(r['seed'], r['tally']['dispatched']) for r in thin][:5]}" if thin else ""))
        if bad or thin:
            rc = 1

        ms = [measure(r, horizon) for r in rows]
        slashed = [m for m in ms if m["slashed"]]
        print(f"   P1b 有人被 triggerSlash 的場次（＝分母）：{len(slashed)}/{len(rows)}")
        if not slashed:
            print("   ⇒ 沒有分母 ⇒ 這一臂 VOID，不報回來率")
            rc = 1
            continue

        back = [m for m in slashed if m["rounds_to_next_route"] is not None]
        waits = sorted(m["rounds_to_next_route"] for m in back)
        cens = sorted(m["rounds_after_slash"] for m in slashed)
        print(f"   P2  回來率 **{len(back)}/{len(slashed)} ＝ {len(back)/len(slashed):.3f}**"
              f"   （S1 同定義、λ=1 f=0.5：0/368 ＝ 0.000）")
        if waits:
            print(f"       等待輪數：中位 {statistics.median(waits):.0f} · 最短 {waits[0]} · 最長 {waits[-1]}")
        print(f"   P3  右設限分母 rounds_after_slash：中位 {statistics.median(cens):.0f}"
              f" · 最小 {cens[0]} · 最大 {cens[-1]}")
        ra = sorted(m["routes_after_slash"] for m in slashed)
        print(f"       被 slash 之後總共又拿到幾件：中位 {statistics.median(ra):.0f}"
              f" · 最小 {ra[0]} · 最大 {ra[-1]}")
        cau = sorted(r["tally"]["caught"] for r in rows)
        print(f"       每場 caught：中位 {statistics.median(cau):.0f} · 最小 {cau[0]} · 最大 {cau[-1]}")

        # ── P4b（事後補）：對照組真的有生效嗎 ────────────────────────
        # 兩臂數字一模一樣的時候，「沒有效果」與「沒跑到」長得一樣。
        # 終局狀態分得開：預設 26 秒那一臂會把 slashAt 刪掉、dim 回 1。
        fin = [r["final"] for r in rows if r.get("final")]
        still = sum(1 for f in fin if f["still_slashed"])
        dimv = sorted(f["dim"] for f in fin)
        print(f"   P4b 終局仍掛著 slashAt：{still}/{len(fin)}"
              f" · 終局 dim 中位 {statistics.median(dimv):.3f}（最小 {dimv[0]} 最大 {dimv[-1]}）")

        # ── P4c（事後補）：回來的那幾件，是在哪個亮度下被路由的 ─────
        # `route()` 的 damp 直接吃 `dim`，而 `slashDim` 的「被照亮」段
        # 會把 dim 推到 1.78 ⇒ 剛被抓的那 0.38 秒反而比平常更容易拿到工作。
        # 閃光窗（slash 後前 3 件）與其餘的再路由率並排。兩個數字放在一起，
        # 「回來」是不是閃光造成的才分得開——只報 2/30 的話兩種解釋都成立。
        WIN = 3
        hit_win = hit_rest = opp_win = opp_rest = 0
        for m, r in zip(ms, rows):
            if not m["slashed"]:
                continue
            r0, who = m["first_slash_round"], r["slash"]["i"]
            for k in range(r0 + 1, min(len(r["dispatches"]), horizon)):
                inwin = (k - r0) <= WIN
                if inwin:
                    opp_win += 1
                else:
                    opp_rest += 1
                if r["dispatches"][k] == who:
                    if inwin:
                        hit_win += 1
                    else:
                        hit_rest += 1
        print(f"   P4d slash 後前 {WIN} 件：再路由 {hit_win} 次／{opp_win} 個機會"
              f"　·　其餘：{hit_rest} 次／{opp_rest} 個機會")

        for m, r in zip(ms, rows):
            if m["slashed"] and m["rounds_to_next_route"] is not None:
                k = m["first_slash_round"] + m["rounds_to_next_route"]
                print(f"   P4c {r['seed']}：等 {m['rounds_to_next_route']} 件回來，"
                      f"那一刻 dim = {r['dims'][k]}"
                      + ("  ← >1 ＝ 還在「被照亮」段" if r["dims"][k] > 1 else ""))
        print()
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--run", type=Path, default=None)
    ap.add_argument("--report", type=Path, default=None)
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--horizon", type=int, default=600)
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.run:
        return run(a.run, a.seeds, a.horizon)
    if a.report:
        return report(a.report)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
