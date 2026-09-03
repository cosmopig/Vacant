#!/usr/bin/env python3
"""R445 §五：`--offset` 接線的植入缺陷測試（M1–M4）。

接一個新旋鈕不算接好，除非它壞掉的時候會被抓到。含「安靜量不到」兩型：
M3 一題都沒載到、M4 載到的數量掉下來。

零模型呼叫：全部走 `--arms probe`（gain_run 在 load_keys() 之前 return）。
"""
import json, os, pathlib, shutil, subprocess, sys, tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
SEED = "g-r212-route-20260828"
DEC = "DECISION_20260903_R445_CONFORM_BANK_EXTENSION.md"
RUN = "g_r445_conform_mbpp_ext"          # 名字要與 DECISION 內文相符（R440G 閘門）
ENV = {**os.environ,
       "VACANT_EVALPLUS_PATH": ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz",
       "CLINE_KEYS": "/nonexistent"}


def probe(script, *, offset=None, n=192, sample=8):
    """跑一次 --arms probe，回傳 (rc, stdout+stderr, 量具實際碰到的 task_id)。"""
    tmp = pathlib.Path(tempfile.mkdtemp(dir="/dev/shm", prefix="r445t_"))
    out = tmp / RUN
    cmd = [sys.executable, str(script), "--out", str(out), "--n", str(n),
           "--decision", DEC, "--seed", SEED, "--arms", "probe",
           "--bank", "evalplus", "--probe-sample", str(sample)]
    if offset is not None:
        cmd += ["--offset", str(offset)]
    p = subprocess.run(cmd, cwd=REPO, env=ENV, capture_output=True, text=True)
    ids = []
    notes = out / "notes.jsonl"
    if notes.exists():
        for line in notes.read_text().splitlines():
            try:
                d = json.loads(line)
            except Exception:
                continue
            for e in d.get("detail", []):
                ids.append(e["task_id"])
    shutil.rmtree(tmp, ignore_errors=True)
    return p.returncode, p.stdout + p.stderr, ids


def head_ids():
    """r444 實際跑的 179 題（直接讀落盤，不靠『同 seed』這個宣稱）。"""
    ids = set()
    for line in (REPO / "runs/g_r444_conform_mbpp/rows.jsonl").read_text().splitlines():
        ids.add(json.loads(line)["task_id"])
    return ids


def make_mutant(_unused, find, repl):
    """突變體**必須放在 ops/gain/ 底下**。

    gain_run.py 靠 `parents[2]` of `__file__` 把 repo root 塞進 sys.path，
    放到 /dev/shm 會 `ModuleNotFoundError: No module named 'ops'` 而 rc=1——
    那是基礎設施壞掉，不是偵測器叫了。第一次寫這支測試就踩到，
    幸好 M1 的判準要求 `overlap > 0` 而不是只看 rc≠0，才沒把它誤判成通過。
    """
    src = (REPO / "ops/gain/gain_run.py").read_text(encoding="utf-8")
    assert src.count(find) == 1, f"突變錨點不唯一：{find!r}"
    m = REPO / "ops/gain" / "_mutant_r445_tmp.py"
    m.write_text(src.replace(find, repl, 1), encoding="utf-8")
    return m


def main():
    clean = REPO / "ops/gain/gain_run.py"
    head = head_ids()
    results = []

    def record(tag, ok, detail):
        results.append((tag, ok, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {tag}: {detail}")

    # ── M0 乾淨版：offset 生效，取到的題目與 r444 零重疊 ──────────────
    rc, log, ids = probe(clean, offset=179)
    record("M0 clean offset=179",
           rc == 0 and ids and not (set(ids) & head),
           f"rc={rc} probed={len(ids)} overlap_with_r444={len(set(ids) & head)}")

    # ── M1 安靜忽略 offset（最危險：跑出來的數字看起來完全正常）────────
    with tempfile.TemporaryDirectory() as td:
        mut = make_mutant(td,
                          "tasks = load_tasks(args.bank, args.seed, args.n, offset=args.offset)",
                          "tasks = load_tasks(args.bank, args.seed, args.n)")
        try:
            rc, log, ids = probe(mut, offset=179)
        finally:
            mut.unlink(missing_ok=True)
        overlap = len(set(ids) & head)
        # 偵測器要抓到的就是這個重疊；抓到＝這條測試有牙齒
        record("M1 offset 被忽略 ⇒ 必須被偵測到",
               rc == 0 and overlap == len(ids) and overlap > 0,
               f"rc={rc} overlap_with_r444={overlap}/{len(ids)}（重疊=偵測器該叫）")

    # ── M2 負 offset（python 會從尾巴切＝安靜取到別的題目）─────────────
    rc, log, ids = probe(clean, offset=-5)
    record("M2 負 offset 被擋", rc != 0 and "offset 不得為負" in log,
           f"rc={rc} msg={'有' if 'offset 不得為負' in log else '無'}")

    # ── M3 安靜量不到型一：offset 超過庫尾 ⇒ 0 題，不准當通過 ───────────
    rc, log, ids = probe(clean, offset=400)
    record("M3 offset 超過庫尾 ⇒ 拒絕啟動",
           rc != 0 and "一題都沒載到" in log,
           f"rc={rc} msg={'有' if '一題都沒載到' in log else '無'}")

    # ── M4 安靜量不到型二：數量掉下來 ⇒ 必須顯式報出 ────────────────
    rc, log, ids = probe(clean, offset=179, n=300)
    record("M4 offset+n 超過庫尾 ⇒ 顯式報缺口",
           rc == 0 and "只載到 192 題" in log and "少 108 題" in log,
           f"rc={rc} warn={'有' if '只載到 192 題' in log else '無'}")

    bad = [t for t, ok, _ in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} 通過")
    if bad:
        print("未通過：" + ", ".join(bad))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
