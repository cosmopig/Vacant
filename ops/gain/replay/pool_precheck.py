#!/usr/bin/env python3
"""併庫前提檢查：兩個（以上）run 併成一個分析樣本，在**科學上**合不合法。

判準：`CRITERION_20260903_R680_POOL_PRECONDITIONS.md`（round680，寫在量測之前）。

為什麼要有這支（round680）：
`pooled_paired_ci.py`（round675）驗過**算術**——加法恆等式、`--key` 有牙齒、
兩型安靜量不到；`power_paired.py`（round678）用它做投影；`r445_predcheck.py`
（round677）的 P-E2／P-E3 直接轉述它的輸出。**三輪都沒有驗過前提**：
被併的兩個 run 是不是同一個實驗。`grep -c "併庫前提|poolab|pool_precheck"
~/vacant/GAIN_STATE.md` 在 round680 之前是 **0**。

若處置定義不同（模型、seed、臂的碼、評審 prompt），併出來的 CI 是
「兩種不同處置的混合」，而**數字會照印、擋門會全綠**——收官文字會把它當成
單一處置的區間引用。這就是安靜量錯東西。

**工具裡沒有任何門檻數字。** C1／C3 是恆等式（集合不相交、載到的題數＝宣告的
題數、聯集＝各 n 之和），C4 唯一的數字從 `--criterion` 那份判準的 Q4 那一列
parse 出來——改門檻的唯一形狀是改判準檔（會留 commit），parse 不到就 BROKEN，
不會安靜沿用預設值。

退出碼：0＝POOLABLE，2＝BROKEN（前提不成立／量不到）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

RC_OK, RC_BROKEN = 0, 2


class Broken(Exception):
    pass


def load_summary(d: pathlib.Path) -> dict:
    p = d / "summary.json"
    if not p.exists():
        raise Broken(f"{d.name}：讀不到 summary.json ⇒ 前提無法驗證（不是通過）")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:                                   # noqa: BLE001
        raise Broken(f"{d.name}：summary.json 壞掉：{e}")


def task_ids(d: pathlib.Path, s: dict) -> list[str]:
    """題目清單一律取自 `instrument.detail`——它在**開跑前**就寫滿全部 n 題，
    中途快照也是完整的；`rows.jsonl` 會隨進度長，拿它當清單會把「還沒跑到」
    誤判成「題目不重疊」。"""
    inst = s.get("instrument")
    if not isinstance(inst, dict) or "detail" not in inst:
        raise Broken(
            f"{d.name}：summary.instrument.detail 不存在 ⇒ 題目清單量不到。"
            "沒有清單就無從判斷重不重疊，這不是通過。")
    detail = inst["detail"]
    if not isinstance(detail, list) or not detail:
        raise Broken(
            f"{d.name}：summary.instrument.detail 是空的（{type(detail).__name__}）"
            "⇒ 比對集合為空。空集合與任何集合都不相交，會偽裝成「不重疊」。")
    ids = []
    for row in detail:
        if not isinstance(row, dict) or "task_id" not in row:
            raise Broken(f"{d.name}：instrument.detail 有一列沒有 task_id 欄位")
        ids.append(row["task_id"])
    return ids


def bank_witness(ids: list[str]) -> str:
    """`--bank` 沒有被記進 summary.json（round680 順帶發現）。用 task_id 的前綴
    當見證：`mbppplus_Mbpp/554` → `mbppplus`。兩個 run 前綴不同＝題庫不同。"""
    return ",".join(sorted({i.split("_", 1)[0] for i in ids}))


def parse_void_pp(criterion: pathlib.Path) -> float:
    if not criterion.exists():
        raise Broken(f"判準檔不存在：{criterion} ⇒ 門檻無來源（工具裡沒有預設值）")
    q4 = [ln for ln in criterion.read_text(encoding="utf-8").splitlines()
          if "**Q4**" in ln]
    if len(q4) != 1:
        raise Broken(
            f"{criterion.name}：找不到唯一的 Q4 那一列（找到 {len(q4)} 列）"
            "⇒ 門檻 parse 不到。不沿用預設值。")
    hits = re.findall(r"(\d+(?:\.\d+)?)\s*pp", q4[0])
    if not hits:
        raise Broken(f"{criterion.name}：Q4 那一列裡沒有 `<n>pp` 形狀的門檻")
    return float(hits[0])


def void_rate(s: dict, arm: str) -> tuple[float, int, int]:
    a = s.get("arms", {}).get(arm)
    if not isinstance(a, dict):
        raise Broken(f"summary.arms.{arm} 不存在 ⇒ void 率量不到")
    if "infra_void" not in a:
        raise Broken(f"summary.arms.{arm} 沒有 infra_void 欄位 ⇒ void 率量不到")
    n = a.get("n") or a.get("accepted") or 0
    tot = max(int(n), int(a["infra_void"]))
    return (100.0 * a["infra_void"] / tot if tot else 0.0), int(a["infra_void"]), tot


def write_json(path: str | None, obj: dict) -> None:
    """`--json` 的目標目錄不存在就建起來。

    round680 實測到的坑：收官指令寫成 `--json runs/_analysis_r445/...`，
    而那個目錄要到收官那一輪才會存在 ⇒ 工具**印完 POOLABLE 之後才崩**，
    rc=1。判決是對的、退出碼是錯的，收官會看成「前提尺壞了」。
    """
    if not path:
        return
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--criterion", required=True,
                    help="判準檔；C4 的門檻從它的 Q4 那一列 parse 出來")
    ap.add_argument("--code-attest", default=None,
                    help="當 run 自己沒記錄跑在哪個 commit 時，指向一份逐函式比對的"
                         "書面證據；該檔必須存在且內文含每個 run 目錄名")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    out: dict = {"runs": args.runs, "checks": {}}
    try:
        dirs = [pathlib.Path(r) for r in args.runs]
        if len(dirs) < 2:
            raise Broken("併庫至少要兩個 run")
        summaries = {d.name: load_summary(d) for d in dirs}
        ids = {d.name: task_ids(d, summaries[d.name]) for d in dirs}

        # ── C1 題目不重疊（三個恆等式，零門檻）──────────────────────
        c1: dict = {"per_run": {}}
        for name, lst in ids.items():
            declared = summaries[name].get("n")
            if declared is None:
                raise Broken(f"{name}：summary 沒有 n 欄位 ⇒ 無法驗「載到的＝宣告的」")
            if len(set(lst)) != len(lst):
                raise Broken(f"{name}：自己的題目清單裡就有重複（{len(lst)} 列、"
                             f"{len(set(lst))} 個相異）")
            if len(lst) != int(declared):
                raise Broken(f"{name}：instrument.detail 有 {len(lst)} 題，"
                             f"但 summary.n 宣告 {declared} 題 ⇒ 安靜縮水")
            c1["per_run"][name] = len(lst)
        names = list(ids)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                inter = set(ids[names[i]]) & set(ids[names[j]])
                if inter:
                    raise Broken(
                        f"{names[i]} 與 {names[j]} 有 {len(inter)} 題重疊"
                        f"（例：{sorted(inter)[:3]}）⇒ 同一題會被配對兩次")
        union = set().union(*[set(v) for v in ids.values()])
        total = sum(len(v) for v in ids.values())
        if len(union) != total:
            raise Broken(f"聯集 {len(union)} ≠ 各 run 題數之和 {total}")
        c1.update(union=len(union), sum_n=total, verdict="HIT")
        out["checks"]["C1_disjoint"] = c1

        # ── C3 執行參數相同 ───────────────────────────────────────
        def sig(name: str) -> dict:
            s = summaries[name]
            return {
                "seed": s.get("seed"),
                "arms": sorted(s.get("arms", {}).keys()),
                "pool": sorted(f"{p.get('agent_id')}={p.get('model')}"
                               for p in (s.get("pool") or [])),
                "bank_witness": bank_witness(ids[name]),
            }
        sigs = {n: sig(n) for n in names}
        base = sigs[names[0]]
        diffs = {n: {k: (base[k], sigs[n][k]) for k in base if base[k] != sigs[n][k]}
                 for n in names[1:]}
        bad = {n: d for n, d in diffs.items() if d}
        if bad:
            raise Broken(f"執行參數不同 ⇒ 不是同一個實驗：{json.dumps(bad, ensure_ascii=False)}")
        if not base["pool"]:
            raise Broken("pool 是空的 ⇒ 模型清單量不到（空清單與空清單「相同」是假綠燈）")
        out["checks"]["C3_config"] = {"verdict": "HIT", "signature": base}

        # ── C4 request_policy 差異的唯一可觀測後果＝void 率 ──────────
        thr = parse_void_pp(pathlib.Path(args.criterion))
        pols = {n: summaries[n].get("request_policy") for n in names}
        pol_same = all(pols[n] == pols[names[0]] for n in names)
        rates: dict = {}
        for n in names:
            for arm in base["arms"]:
                rates[f"{n}/{arm}"] = void_rate(summaries[n], arm)
        spread = max(r[0] for r in rates.values()) - min(r[0] for r in rates.values())
        c4 = {"policy_identical": pol_same, "threshold_pp": thr,
              "void_spread_pp": round(spread, 4),
              "rates": {k: {"pct": round(v[0], 4), "void": v[1], "n": v[2]}
                        for k, v in rates.items()}}
        if not pol_same and spread >= thr:
            raise Broken(f"request_policy 不同、且 void 率差 {spread:.2f}pp ≥ {thr}pp "
                         "⇒ 差異有可觀測後果，併庫要揭露")
        c4["verdict"] = "HIT" if pol_same else "DIFFERS_NO_CONSEQUENCE"
        out["checks"]["C4_void"] = c4

        # ── C2 處置定義（碼版本）───────────────────────────────────
        # 欄位在、但 sha 是 None（例如 run 在非 git 目錄下跑）⇒ 仍算「沒記錄」。
        # 否則 {None} 這個單元素集合會讓 C2 判成 HIT＝假綠燈。
        missing = [n for n in names
                   if not (summaries[n].get("runner_git") or {}).get("sha")]
        c2: dict = {"runner_git": {n: summaries[n].get("runner_git") for n in names}}
        if not missing:
            shas = {summaries[n]["runner_git"].get("sha") for n in names}
            c2["verdict"] = "HIT" if len(shas) == 1 else "DIFFERS"
            c2["shas"] = sorted(x for x in shas if x)
            if len(shas) != 1:
                c2["note"] = ("碼版本不同 ⇒ 必須逐函式比對臂的碼，"
                              "本工具不代替那件事；請附 --code-attest")
                if not args.code_attest:
                    raise Broken("碼版本不同且沒有附 --code-attest 的逐函式比對證據")
        else:
            c2["verdict"] = "UNVERIFIABLE_NO_CODE_VERSION"
            c2["missing"] = missing
            if not args.code_attest:
                raise Broken(
                    f"這些 run 沒有記錄自己跑在哪個 commit：{missing}"
                    " ⇒ 處置定義相同與否**在 run 的產物裡無法驗證**。"
                    "要併庫就得附 --code-attest 指向逐函式比對的書面證據。"
                    "（沒有欄位不等於相同——那是安靜量不到。）")
        if args.code_attest:
            att = pathlib.Path(args.code_attest)
            if not att.exists():
                raise Broken(f"--code-attest 檔不存在：{att}")
            txt = att.read_text(encoding="utf-8")
            absent = [n for n in names if n not in txt]
            if absent:
                raise Broken(
                    f"{att.name} 內文沒有提到這些 run：{absent} ⇒ 這份證據不是在講它們"
                    "（與 R440G 的 --decision 閘門同一個機制）")
            c2["attested_by"] = str(att)
        out["checks"]["C2_code"] = c2

    except Broken as e:
        out["verdict"] = "BROKEN"
        out["reason"] = str(e)
        print(f"BROKEN：{e}")
        write_json(args.json, out)
        return RC_BROKEN

    out["verdict"] = "POOLABLE"
    print("POOLABLE　" + "　".join(
        f"{k}={v['verdict']}" for k, v in out["checks"].items()))
    print(f"  題目：{'+'.join(str(v) for v in out['checks']['C1_disjoint']['per_run'].values())}"
          f" = {out['checks']['C1_disjoint']['union']} 題，兩兩不相交")
    print(f"  處置：{out['checks']['C3_config']['signature']['bank_witness']}　"
          f"seed={out['checks']['C3_config']['signature']['seed']}　"
          f"{len(out['checks']['C3_config']['signature']['pool'])} agent／"
          f"{len({p.split('=')[1] for p in out['checks']['C3_config']['signature']['pool']})} 模型")
    print(f"  void：spread {out['checks']['C4_void']['void_spread_pp']}pp"
          f"（門檻 {out['checks']['C4_void']['threshold_pp']}pp，取自判準檔）")
    if out["checks"]["C2_code"]["verdict"] != "HIT":
        print(f"  ⚠ 碼版本：{out['checks']['C2_code']['verdict']}"
              f"，由 {out['checks']['C2_code'].get('attested_by')} 背書")
    write_json(args.json, out)
    return RC_OK


if __name__ == "__main__":
    sys.exit(main())
