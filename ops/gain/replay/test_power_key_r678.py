#!/usr/bin/env python3
"""round678 植入缺陷測試：power_paired.py 的 --key 有沒有牙齒。

判準 CRITERION_20260903_R678_POWER_PROJECTION.md §四。
零 API、零模型呼叫。**唯讀真 run 目錄**，所有變造只在 --work（預設 /dev/shm/r678）。

判準不寫「rc≠0 就算過」（記憶：突變體放錯目錄害 import 失敗也是 rc≠0）——
每一條都指名「偵測器該看到的那個量」：訊息裡要出現哪個字、或哪個數字要等於多少。
"""
from __future__ import annotations
import json, pathlib, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE.parent / "power_paired.py"
REAL = HERE.parent.parent.parent / "runs" / "g_r444_conform_mbpp"


def run(run_dir, *extra):
    cmd = [sys.executable, str(TOOL), "--a-run", str(run_dir), "--a-arm", "CONFORM",
           "--b-run", str(run_dir), "--b-arm", "OFF5", "--n-cap", "179", *extra]
    return subprocess.run(cmd, capture_output=True, text=True)


def fixture(work: pathlib.Path, name: str, mutate) -> pathlib.Path:
    d = work / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    rows = [json.loads(l) for l in (REAL / "rows.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = mutate(rows)
    (d / "rows.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return d


def main() -> int:
    work = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/dev/shm/r678")
    work.mkdir(parents=True, exist_ok=True)
    res = []

    def check(tag, cond, detail):
        res.append((tag, bool(cond), detail))
        print(f"{'PASS' if cond else 'FAIL'}  {tag}  {detail}")

    # --- P0 乾淨基線：兩個 key 都跑得起來，且 JSON 記下量的是哪個 -----------------
    jm = work / "m.json"; jd = work / "d.json"
    a = run(REAL, "--key", "meets_demand", "--json", str(jm))
    b = run(REAL, "--key", "deliv", "--json", str(jd))
    check("P0a rc=0 兩個 key", a.returncode == 0 and b.returncode == 0,
          f"rc={a.returncode}/{b.returncode}")
    M, D = json.loads(jm.read_text()), json.loads(jd.read_text())
    check("P0b key 進 JSON", M["key"] == "meets_demand" and D["key"] == "deliv"
          and D["key_fields"] == ["accepted", "meets_demand"],
          f'{M["key"]} / {D["key"]} fields={D["key_fields"]}')

    # --- P1 預設＝舊行為（回歸相容，不是宣稱） ------------------------------------
    jdef = work / "def.json"
    run(REAL, "--json", str(jdef))
    check("P1 預設逐位元＝--key meets_demand",
          jdef.read_bytes().replace(b'"key": "meets_demand"', b'X') ==
          jm.read_bytes().replace(b'"key": "meets_demand"', b'X'), "兩份 JSON 相同")

    # --- P2 Q1 前提：真資料上 deliv ≡ meets_demand（構造，不是巧合） --------------
    same = (M["b_only"], M["c_only"], M["n_paired_now"]) == (D["b_only"], D["c_only"], D["n_paired_now"])
    check("P2 r444 上兩個 key 同值（Q1 前提）", same,
          f'b/c/n = {M["b_only"]}/{M["c_only"]}/{M["n_paired_now"]} vs {D["b_only"]}/{D["c_only"]}/{D["n_paired_now"]}')

    # --- P3 --key 有牙齒：造一格「拒交但 meets_demand=true」⇒ 兩個 key 必須分歧 ----
    # 這正是 round670 §三 擔心的那一格。找一個 CONFORM 上 md=True 的 task，
    # 把 accepted 翻成 False：meets_demand 眼裡沒變，deliv 眼裡它掉了。
    def mutate_refuse(rows):
        for r in rows:
            if r["arm"] == "CONFORM" and r.get("meets_demand") and r.get("accepted"):
                r["accepted"] = False
                break
        return rows
    fx = fixture(work, "refuse", mutate_refuse)
    jm2, jd2 = work / "m2.json", work / "d2.json"
    run(fx, "--key", "meets_demand", "--json", str(jm2))
    run(fx, "--key", "deliv", "--json", str(jd2))
    M2, D2 = json.loads(jm2.read_text()), json.loads(jd2.read_text())
    check("P3 拒交格之下兩個 key 給出相反的帳",
          (M2["b_only"], M2["c_only"]) == (M["b_only"], M["c_only"])
          and (D2["b_only"], D2["c_only"]) != (D["b_only"], D["c_only"]),
          f'meets {M2["b_only"]}/{M2["c_only"]}（不動）  deliv {D2["b_only"]}/{D2["c_only"]}（動了，原 {D["b_only"]}/{D["c_only"]}）')

    # --- P4 安靜量不到・型一：欄位不見了 -----------------------------------------
    fx1 = fixture(work, "noacc", lambda rows: [{k: v for k, v in r.items() if k != "accepted"} for r in rows])
    r1 = run(fx1, "--key", "deliv")
    check("P4 缺 accepted 欄位 ⇒ BROKEN（不是安靜全判失敗）",
          r1.returncode != 0 and "accepted" in r1.stderr and "量不到" in r1.stderr,
          f"rc={r1.returncode} err={r1.stderr.strip().splitlines()[-1][:70] if r1.stderr.strip() else ''}")
    # 對照：同一份 fixture 用 meets_demand 應該照常跑（證明擋門是看欄位不是看檔壞了）
    r1b = run(fx1, "--key", "meets_demand")
    check("P4b 同一份 fixture 用 meets_demand 仍 rc=0（擋門看的是欄位，不是檔壞了）",
          r1b.returncode == 0, f"rc={r1b.returncode}")

    # --- P5 安靜量不到・型二：配對數掉到 0 ---------------------------------------
    fx2 = fixture(work, "nopair", lambda rows: [dict(r, task_id=r["task_id"] + "_X") if r["arm"] == "OFF5" else r for r in rows])
    r2 = run(fx2, "--key", "deliv")
    check("P5 兩臂 task_id 不重疊 ⇒ BROKEN（不是 disc_rate=0.00%）",
          r2.returncode != 0 and "配對數 = 0" in r2.stderr,
          f"rc={r2.returncode} err={r2.stderr.strip().splitlines()[-1][:70] if r2.stderr.strip() else ''}")

    # --- P6 臂名打錯也走型二/型一（不是印出漂亮的零） -----------------------------
    r3 = subprocess.run([sys.executable, str(TOOL), "--a-run", str(REAL), "--a-arm", "CONFROM",
                         "--b-run", str(REAL), "--b-arm", "OFF5", "--n-cap", "179", "--key", "deliv"],
                        capture_output=True, text=True)
    check("P6 臂名打錯 ⇒ BROKEN", r3.returncode != 0 and "量不到" in r3.stderr,
          f"rc={r3.returncode}")

    # --- P7 唯讀：真 run 目錄逐位元不變 -------------------------------------------
    import hashlib
    h = hashlib.sha256((REAL / "rows.jsonl").read_bytes()).hexdigest()[:8]
    check("P7 真 run 目錄唯讀", h == SHA0, f"rows.jsonl sha256[:8]={h}")

    ok = sum(1 for _, c, _ in res if c)
    print(f"\n{ok}/{len(res)} PASS")
    return 0 if ok == len(res) else 1


import hashlib
SHA0 = hashlib.sha256((REAL / "rows.jsonl").read_bytes()).hexdigest()[:8]

if __name__ == "__main__":
    raise SystemExit(main())
