#!/usr/bin/env python3
"""S10：展件說「它保證做過什麼會留下來」——量它自己的模擬留下了多少。

**為什麼要有這一支**（第 115 輪）：

第 114 輪示範過一次同樣的形狀：`world/js/slash.js:31` 寫「不是永久除名」，
而它自己的模擬量出來 28/30 場再也沒拿到工作。這一支量另一句話。

要判的句子（`vacant_hm/index.html:153` ＋ `world/js/main.js:194`，一字不差兩處）：

    「它不保證每次都對——**它保證做過什麼會留下來**，而且會有後果。」

前半是誠實邊界句（〈否定脈絡〉，紅線 C 允許），**不動**。
後半是正向宣稱，而展件裡「做過什麼」的唯一逐件紀錄是 `r.recent`：

    sim-bridge.js:233-234 / 304-305 / 344-345
        worker.recent.unshift({key, bad, requester});
        if (worker.recent.length > 10) worker.recent.length = 10;

三處都封頂 10 筆，而且 `unshift` **只在「收下」那條路上**發生。
`phone.js:145-147` 又只列前 6 筆給觀眾指認。

⇒ 這一支不下文案判決，只給四個數字（分母一律連報）：

    R1 保留率    = 期末 recent.length ÷ 這輩子曾經有過逐件紀錄的件數
    R2 有紀錄率  = ever_recorded ÷ done（被派到的件數）
    R3 指得到率  = min(6, recent.length) ÷ done（手機頁實際列得出來的）
    R4 壞的留住  = 曾被收下的壞交付裡，期末還在前 6 筆的比例

—— 誠實邊界 ——
* 量的是**展件自己的 JS 模擬**，不是 Vacant 的 Python 機制，也不是真模型。
* 量的是**手機頁那一組真實參數**（`buildWorld(DAY)` ＋ `warmUp(…, 12000)`），
  不是大螢幕的活體路徑。大螢幕沒量。
* 「留得少」不等於展件在說謊——展件可以有意識地只留一個窗口，
  只要畫面上不寫「保證留下來」。**這一支只給數字。**

—— 三件刻意的設計 ——
① **計數器與採集分開。** JS 只吐原始觀測（每一件被收下的交付是誰的、期末誰手上
   還有哪幾筆），四個比值由本檔的 `measure()` 算 ⇒ 計數器可以餵合成資料自驗。
② **觀測要 fail-closed。** `recent` 是長度 10 的 FIFO：取樣太疏，東西會進了又被
   擠掉而沒被看見，**而漏算的方向剛好會讓 R1 變好看**。所以採集端每 1 件觀測
   一次，並且在 JS 裡自己驗「兩次觀測之間最多只可能新增 1 筆」；
   `--self-test` 的 `P0d` 用合成輸入確認計數器**喊得出**漏算。
③ **不在 `vacant_hm` 裡放任何檔案**（S9 同款）：`http.server` 指到 repo 根，
   導到 404 同源 URL，模組靠動態 `import()` 拉進來。

用法：
    python3 runs/s10_record_retention.py --self-test
    python3 runs/s10_record_retention.py --run OUTDIR [--warm 12000] [--seeds 3]
    python3 runs/s10_record_retention.py --report OUTDIR
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
DBG_PORT = 9351
HTTP_PORT = 8751

PHONE_LIST = 6      # phone.js:145-147 只列前 6 筆
CAP = 10            # sim-bridge.js 三處的 recent 上限


# ══════════════════════════════════════════════════════════════════════
# 一、計數器（被自驗的那個東西）
# ══════════════════════════════════════════════════════════════════════

def measure(obs: dict) -> dict:
    """從一場的原始觀測算出四個比值。

    `obs` 需要的鍵：
      `residents` —— 每位一個 dict：
          i, done, rejected, caught, audited,
          ever            = 這輩子被 unshift 進 recent 的件數（採集端逐件觀測）
          ever_bad        = 其中 bad 的件數
          still           = 期末 recent.length
          still_bad_top   = 期末前 6 筆裡 bad 的件數
      `missed`    —— 採集端自己回報的「可能漏看」件數。**> 0 就作廢。**

    回傳 pooled 四個比值 ＋ 恆等式檢查。比值一律連分母報。
    """
    rs = obs["residents"]
    tot_done = sum(r["done"] for r in rs)
    tot_ever = sum(r["ever"] for r in rs)
    tot_still = sum(r["still"] for r in rs)
    tot_point = sum(min(PHONE_LIST, r["still"]) for r in rs)
    tot_ever_bad = sum(r["ever_bad"] for r in rs)
    tot_bad_top = sum(r["still_bad_top"] for r in rs)

    # G1154 的恆等式：done − ever == rejected + caught（暖機路徑沒有在途件）
    ident_ok, ident_bad = 0, []
    for r in rs:
        if r["done"] - r["ever"] == r["rejected"] + r["caught"]:
            ident_ok += 1
        else:
            ident_bad.append(r["i"])

    def ratio(a, b):
        return None if b == 0 else a / b

    per_r1 = [r["still"] / r["ever"] for r in rs if r["ever"] > 0]
    busy = [r for r in rs if r["ever"] > CAP]      # 只有這些人的上限才咬得到

    return {
        "n_residents": len(rs),
        "missed": obs.get("missed", 0),
        "tot_done": tot_done, "tot_ever": tot_ever, "tot_still": tot_still,
        "tot_pointable": tot_point,
        "tot_ever_bad": tot_ever_bad, "tot_bad_top": tot_bad_top,
        "R1": ratio(tot_still, tot_ever),
        "R2": ratio(tot_ever, tot_done),
        "R3": ratio(tot_point, tot_done),
        "R4": ratio(tot_bad_top, tot_ever_bad),
        "R1_median": statistics.median(per_r1) if per_r1 else None,
        "n_busy": len(busy),
        "R1_busy": ratio(sum(r["still"] for r in busy), sum(r["ever"] for r in busy)),
        "identity_ok": ident_ok, "identity_bad": ident_bad[:10],
        "ever_max": max((r["ever"] for r in rs), default=0),
        "still_max": max((r["still"] for r in rs), default=0),
    }


def self_test() -> int:
    """P0b／P0c／P0d：已知答案的兩個方向 ＋ 失聯偵測。

    P0a（分塊等價）不在這裡——它需要瀏覽器，走 `--run` 的第一步。
    """
    fails = []

    # P0b 正向：只收下 3 件 ⇒ 全部留著
    pos = {"residents": [{"i": 0, "done": 3, "rejected": 0, "caught": 0, "audited": 0,
                          "ever": 3, "ever_bad": 1, "still": 3, "still_bad_top": 1}],
           "missed": 0}
    m1 = measure(pos)
    if m1["R1"] != 1.0:
        fails.append(f"P0b 正向 R1：期望 1.0，得到 {m1['R1']}")
    if m1["identity_ok"] != 1:
        fails.append(f"P0b 恆等式：期望 1，得到 {m1['identity_ok']}")

    # P0c 負向：收下 25 件、封頂 10 ⇒ R1 = 0.4；另外 5 件被擋下 ⇒ R2 = 25/30
    neg = {"residents": [{"i": 0, "done": 30, "rejected": 4, "caught": 1, "audited": 2,
                          "ever": 25, "ever_bad": 4, "still": 10, "still_bad_top": 0}],
           "missed": 0}
    m2 = measure(neg)
    if abs(m2["R1"] - 0.4) > 1e-9:
        fails.append(f"P0c 負向 R1：期望 0.400，得到 {m2['R1']}")
    if abs(m2["R2"] - 25 / 30) > 1e-9:
        fails.append(f"P0c 負向 R2：期望 {25/30:.4f}，得到 {m2['R2']}")
    if abs(m2["R3"] - 6 / 30) > 1e-9:
        fails.append(f"P0c 負向 R3：期望 {6/30:.4f}，得到 {m2['R3']}")
    if m2["R4"] != 0.0:
        fails.append(f"P0c 負向 R4：期望 0.0，得到 {m2['R4']}")
    if m2["identity_ok"] != 1:
        fails.append(f"P0c 恆等式：期望 1（30−25==4+1），得到 {m2['identity_ok']}")

    # P0d 失聯：ever 少算 ⇒ 恆等式必須自己壞掉，而且 R1 會**變好看**
    lost = {"residents": [{"i": 0, "done": 30, "rejected": 4, "caught": 1, "audited": 2,
                           "ever": 14, "ever_bad": 2, "still": 10, "still_bad_top": 0}],
            "missed": 0}
    m3 = measure(lost)
    if m3["identity_ok"] != 0:
        fails.append("P0d 失聯：漏算 11 筆時恆等式應該壞掉，卻通過了")
    if not (m3["R1"] > m2["R1"]):
        fails.append("P0d 方向：漏算應該讓 R1 變好看，卻沒有")

    print("P0 計數器 fixture（不需要瀏覽器的那三格）：")
    print(f"  P0b 正向（收下 3 件全留著）  R1 = {m1['R1']:.3f}          期望 1.000")
    print(f"  P0c 負向（收下 25 件封頂 10）R1 = {m2['R1']:.3f} · R2 = {m2['R2']:.3f} · "
          f"R3 = {m2['R3']:.3f}   期望 0.400 · 0.833 · 0.200")
    print(f"  P0d 失聯（故意漏算 11 筆）  恆等式 ok = {m3['identity_ok']}（期望 0）；"
          f"漏算把 R1 從 {m2['R1']:.3f} 拉到 {m3['R1']:.3f}（變好看 ⇒ 這正是要防的方向）")
    if fails:
        for f in fails:
            print("FAIL " + f)
        return 1
    print("  ⇒ 三格都答對，計數器可以拿去量未知的（P0a 分塊等價在 --run 第一步）")
    return 0


# ══════════════════════════════════════════════════════════════════════
# 二、採集（在瀏覽器裡跑展件自己的模擬，一行都不改它）
# ══════════════════════════════════════════════════════════════════════

# 走**手機頁那一組參數**：buildWorld(DAY) ＋ warmUp(world, sim, 12000)。
# 觀測方式：把 warmUp 拆成每次 1 件（P0a 先證明拆了等價），每件之後看
# 「剛剛那個 key 有沒有出現在某個人的 recent[0]」。unshift 保證它在 index 0。
COLLECT_JS = r"""
(async () => {
  const W  = await import('/world/js/world.js');
  const SB = await import('/world/js/sim-bridge.js');
  const ok = await SB.initSim();
  if (!ok) return {error: 'initSim 回 false —— sim.js 沒載到'};

  const WARM = %WARM%;

  /* ── P0a：分塊等價。一次跑完 vs 每次 1 件，期末狀態必須逐值相同。 ──
     不等價的話，本輪的觀測手段本身就是竄改，後面所有數字作廢。 */
  function fingerprint(world, sim) {
    return JSON.stringify({
      tally: sim.tally, seq: sim.seq,
      rs: world.residents.map(r => [r.done|0, r.rejected|0, r.caught|0, r.audited|0,
                                    r.stage, +r.rep.toFixed(6),
                                    (r.recent||[]).map(d => d.key).join(',')]),
    });
  }
  const equivSeeds = %EQUIV_SEEDS%;
  const equiv = [];
  for (const seed of equivSeeds) {
    const wA = W.buildWorld(30, seed, 'organic'); const sA = SB.makeSim(wA);
    wA.works = wA.works || []; wA.edges = wA.edges || [];
    SB.warmUp(wA, sA, WARM);
    const wB = W.buildWorld(30, seed, 'organic'); const sB = SB.makeSim(wB);
    wB.works = wB.works || []; wB.edges = wB.edges || [];
    for (let k = 0; k < WARM; k++) SB.warmUp(wB, sB, 1);
    equiv.push({seed, same: fingerprint(wA, sA) === fingerprint(wB, sB)});
  }

  /* ── 主採集 ── */
  const out = [];
  for (const seed of %SEEDS%) {
    const world = W.buildWorld(30, seed, 'organic');
    const sim = SB.makeSim(world);
    if (!sim) return {error: 'makeSim 回 null'};
    world.works = world.works || []; world.edges = world.edges || [];
    for (let i = 0; i < world.residents.length; i++)
      if (world.residents[i].i !== i) return {error: 'resident.i 不是陣列索引，探針的假設破了'};

    const n = world.residents.length;
    const ever = new Array(n).fill(0), everBad = new Array(n).fill(0);
    const lastLen = new Array(n).fill(0);
    let missed = 0, seenKeys = 0;

    for (let k = 0; k < WARM; k++) {
      const before = sim.seq;
      SB.warmUp(world, sim, 1);
      const consumed = sim.seq - before;          // 正常是 1
      const key = 'T' + before;
      let hit = -1;
      for (let i = 0; i < n; i++) {
        const rec = world.residents[i].recent;
        if (rec.length && rec[0].key === key) { hit = i; break; }
      }
      if (hit >= 0) {
        ever[hit]++; seenKeys++;
        if (world.residents[hit].recent[0].bad) everBad[hit]++;
      }
      /* fail-closed：兩次觀測之間，任何人的 recent 長度增加超過 1，
         就代表有東西進了又被擠掉而沒被看見。**寧可喊出來也不要安靜少算。** */
      for (let i = 0; i < n; i++) {
        const L = world.residents[i].recent.length;
        if (L - lastLen[i] > 1) missed += (L - lastLen[i] - 1);
        lastLen[i] = L;
      }
      if (consumed !== 1) missed += 1000000;      // 假設破了，直接讓它壞得很大聲
    }

    out.push({
      seed, warm: WARM, missed, seen_keys: seenKeys,
      tally: JSON.parse(JSON.stringify(sim.tally)), seq: sim.seq,
      residents: world.residents.map(r => ({
        i: r.i, code: r.code, stage: r.stage,
        done: r.done|0, rejected: r.rejected|0, caught: r.caught|0, audited: r.audited|0,
        ever: ever[r.i], ever_bad: everBad[r.i],
        still: r.recent.length,
        still_bad: r.recent.filter(d => d.bad).length,
        still_bad_top: r.recent.slice(0, 6).filter(d => d.bad).length,
      })),
    });
  }
  return {equiv, runs: out};
})()
"""


def collect(seeds, warm, timeout=1800.0):
    """起 http.server ＋ chrome，把觀測吐回來。**不在 vacant_hm 裡寫任何檔案。**"""
    srv = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(HTTP_PORT),
         "--bind", "127.0.0.1", "--directory", str(HM_ROOT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ch = None
    try:
        time.sleep(1.2)
        ch = cdp.Chrome(str(CHROME), DBG_PORT, size=(900, 600), extra_flags=CFLAGS)
        ch.call("Page.enable")
        ch.call("Page.navigate", {"url": f"http://127.0.0.1:{HTTP_PORT}/__s10_probe__"})
        time.sleep(1.0)
        js = (COLLECT_JS
              .replace("%WARM%", str(warm))
              .replace("%EQUIV_SEEDS%", json.dumps(seeds[:1]))
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
        return val
    finally:
        if ch:
            ch.close()
        srv.terminate()
        try:
            srv.wait(timeout=10)
        except Exception:
            srv.kill()


def run(outdir: Path, seeds_n: int, warm: int) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    seeds = [f"W{i+1}" for i in range(seeds_n)]
    print(f"── 採集（warm={warm} · {len(seeds)} 場 · 逐件觀測）…", flush=True)
    t0 = time.time()
    val = collect(seeds, warm)
    dt = time.time() - t0
    with (outdir / "runs.jsonl").open("w", encoding="utf-8") as f:
        for r in val["runs"]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (outdir / "meta.json").write_text(json.dumps(
        {"seeds": seeds, "warm": warm, "equiv": val["equiv"],
         "phone_list": PHONE_LIST, "cap": CAP},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   {len(val['runs'])} 場 · {dt:.1f}s · {outdir/'runs.jsonl'}")
    print(f"   P0a 分塊等價：{val['equiv']}")
    return 0


# ══════════════════════════════════════════════════════════════════════
# 三、報告
# ══════════════════════════════════════════════════════════════════════

def report(outdir: Path) -> int:
    meta = json.loads((outdir / "meta.json").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in (outdir / "runs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rc = 0

    print("S10 · 展件說「它保證做過什麼會留下來」——它自己的模擬留下了多少")
    print("資料性質：**機制模擬**（展件的 JS 模擬），不是真模型、不是 Vacant 的 Python 機制。")
    print(f"參數＝手機頁那一組：buildWorld(DAY) ＋ warmUp(…, {meta['warm']})；"
          f"recent 上限 {meta['cap']}、手機頁只列前 {meta['phone_list']} 筆。\n")

    # P0a：分塊等價（觀測手段本身有沒有動到被量的東西）
    eq = meta.get("equiv", [])
    eq_ok = bool(eq) and all(e["same"] for e in eq)
    print(f"P0a 分塊等價（warmUp(n) vs warmUp(1)×n 期末逐值相同）："
          f"{'PASS' if eq_ok else 'FAIL'}  {eq}")
    if not eq_ok:
        print("FAIL P0a —— 觀測手段會改變被量的對象，本輪數字全部作廢")
        return 1

    ms = []
    for r in rows:
        m = measure({"residents": r["residents"], "missed": r["missed"]})
        m["seed"] = r["seed"]
        m["tally"] = r["tally"]
        ms.append(m)

    # P1：驗後果不驗前提。逐件觀測到的筆數必須等於模擬自己的 accepted。
    print("\nP1 觀測完整性（驗後果：觀測到的筆數 vs 模擬自己的計數器）")
    for m, r in zip(ms, rows):
        acc = r["tally"]["accepted"]
        ok = (m["tot_ever"] == acc) and (m["missed"] == 0)
        if not ok:
            rc = 1
        print(f"  {m['seed']}: ever_recorded = {m['tot_ever']} · tally.accepted = {acc} · "
              f"missed = {m['missed']}  {'PASS' if ok else 'FAIL'}")

    print("\nP2 恆等式（done − ever_recorded == rejected + caught）"
          "—— 成立＝被擋下／被抓到的交付**零逐件紀錄**")
    for m in ms:
        ok = m["identity_ok"] == m["n_residents"]
        if not ok:
            rc = 1
        print(f"  {m['seed']}: {m['identity_ok']}/{m['n_residents']}  "
              f"{'PASS' if ok else 'FAIL ' + str(m['identity_bad'])}")

    print("\nP3 主量測（四個比值，分母一起報）")
    hdr = f"  {'場':<5}{'R1 保留':>16}{'R2 有紀錄':>18}{'R3 指得到':>18}{'R4 壞的留住':>18}"
    print(hdr)
    for m in ms:
        print(f"  {m['seed']:<5}"
              f"{m['R1']:.3f} ({m['tot_still']}/{m['tot_ever']})".rjust(16) +
              f"{m['R2']:.3f} ({m['tot_ever']}/{m['tot_done']})".rjust(18) +
              f"{m['R3']:.3f} ({m['tot_pointable']}/{m['tot_done']})".rjust(18) +
              (f"{m['R4']:.3f} ({m['tot_bad_top']}/{m['tot_ever_bad']})".rjust(18)
               if m["R4"] is not None else "n/a".rjust(18)))

    def pooled(k_num, k_den):
        a = sum(m[k_num] for m in ms)
        b = sum(m[k_den] for m in ms)
        return (a / b if b else None), a, b

    r1, a1, b1 = pooled("tot_still", "tot_ever")
    r2, a2, b2 = pooled("tot_ever", "tot_done")
    r3, a3, b3 = pooled("tot_pointable", "tot_done")
    r4, a4, b4 = pooled("tot_bad_top", "tot_ever_bad")
    print(f"\n  pooled  R1 = {r1:.3f} ({a1}/{b1}) · R2 = {r2:.3f} ({a2}/{b2}) · "
          f"R3 = {r3:.3f} ({a3}/{b3}) · R4 = {r4:.3f} ({a4}/{b4})")

    print("\nP4 上限咬到誰（R1 的 pooled 值會被「只做過幾件」的居民拉高，所以分開報）")
    for m in ms:
        med = "n/a" if m["R1_median"] is None else f"{m['R1_median']:.3f}"
        bus = "n/a（沒有人超過上限）" if m["R1_busy"] is None else f"{m['R1_busy']:.3f}"
        print(f"  {m['seed']}: 逐位 R1 中位 = {med} · "
              f"曾有 >{CAP} 筆紀錄的居民 {m['n_busy']}/{m['n_residents']} 位，"
              f"他們的 R1 = {bus} · "
              f"單人最多曾有 {m['ever_max']} 筆、期末最多握 {m['still_max']} 筆")

    print("\n判定：本支不下文案判決，只給數字。"
          "「保證做過什麼會留下來」對不對，看的是 R2／R3 這兩個分母。")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--run", metavar="OUTDIR")
    ap.add_argument("--report", metavar="OUTDIR")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--warm", type=int, default=12000)
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.run:
        return run(Path(a.run), a.seeds, a.warm)
    if a.report:
        return report(Path(a.report))
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
