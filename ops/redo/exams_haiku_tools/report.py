#!/usr/bin/env python3
"""report — 由 qualify.json／measure.json 產生 REPORT.md 的數字部分（缺陷與推論另寫在 REPORT_NOTES.md，接在後面）。"""
import ast
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import haiku_call as H  # noqa: E402

RES = H.OUT.parents[0] / "results" / "ctl_exams_haiku_20261127"
KINDS = ["xm", "xmv", "pb", "ex"]


def pct(a, b):
    return f"{100 * a / b:.1f}% ({a}/{b})" if b else "n/a (0/0)"


def seg(task, kind, line):
    f = H.OUT / task / f"{kind}_test.py"
    src = f.read_text(encoding="utf-8")
    try:
        for n in ast.walk(ast.parse(src)):
            if getattr(n, "lineno", None) == int(line) and isinstance(n, (ast.Assert, ast.With)):
                return " ".join((ast.get_source_segment(src, n) or "").split())[:240]
    except SyntaxError:
        pass
    return src.split("\n")[int(line) - 1].strip()[:240]


def main() -> int:
    qual = json.loads((RES / "qualify.json").read_text())
    meas = json.loads((RES / "measure.json").read_text())
    ver = meas["versions"]
    tasks = {t["task"]: t for t in meas["tasks"]}
    qd = {q["task"]: q for q in qual}
    L = ["# Haiku 驗收考卷品質報告（37 題 Exercism；探索性前導）", "",
         "決定檔：`decisions/DECISION_20261127_HAIKU_EXAMS.md`。考卷凍結於 `ops/redo/exams_haiku_20261127/`（見 MANIFEST.json），量測期間未改。",
         f"環境：{ver['python']}、{ver['pytest']}、{ver['bwrap']}（bwrap：無網路、唯讀系統、一次性可寫工作目錄、30 秒時限）。", ""]
    # ---- 錯解池
    nc = sum(len(q["cands"]) for q in qual)
    nq = sum(c["qualified"] for q in qual for c in q["cands"])
    from collections import Counter
    why = Counter(c["why"] for q in qual for c in q["cands"] if not c["qualified"])
    bysrc = Counter(c["source"] for q in qual for c in q["cands"] if c["qualified"])
    per_task_q = Counter({q["task"]: sum(c["qualified"] for c in q["cands"]) for q in qual})
    L += ["## 1. 錯解池", "",
          f"候選 {nc} 個（Haiku 寫的 {sum(1 for q in qual for c in q['cands'] if c['source']=='haiku_wrong')}、Devin 失敗交付 "
          f"{sum(1 for q in qual for c in q['cands'] if c['source']=='devin_failed')}；沒有 Haiku 的失敗交付——Haiku 校準 37/37 全過）；"
          f"入選 {nq}（Haiku {bysrc['haiku_wrong']}、Devin {bysrc['devin_failed']}）。丟棄原因：{dict(why)}。",
          f"每題入選數：{dict(sorted(Counter(per_task_q.values()).items()))}（鍵＝入選數，值＝題數）。", ""]
    # ---- 原始測試檔參照
    onum = [q["orig_ref"]["n"] for q in qual]
    opass = [q["orig_ref"]["pass"] for q in qual]
    L += ["## 2. 參照點：原始完整 Exercism 測試檔", "",
          f"對參考解：逐測試通過 {pct(sum(opass), sum(onum))}；平均每題 {sum(onum)/len(onum):.1f} 個測試。",
          "對入選錯解：**依入選條件＝100% 攔下（循環論證，不是量到的能力）**；另報：入選錯解平均失敗的測試占比 "
          + (lambda a: f"{100*a:.1f}%")(
              sum(c["orig_fail"] / c["orig_n"] for q in qual for c in q["cands"] if c["qualified"]) / max(nq, 1)) + "。", ""]
    # ---- 各類總表
    summ = {}
    for k in KINDS:
        s = dict(n_ok=0, n_mal=0, n_none=0, n_missing=0, units=[], rt_p=0, rt_n=0, ex_pass=0, ex_n=0, ex_collect=0,
                 a_p=0, a_n=0, a_unr=0, w_rej=0, w_n=0, wv_rej=0, wv_n=0, ntests=[])
        for t, T in tasks.items():
            e = T["exams"][k]
            if e["status"] == "none":
                s["n_none"] += 1
                continue
            if e["status"] == "missing":
                s["n_missing"] += 1
                continue
            s["ex_n"] += 1
            if e["status"] == "malformed":
                s["n_mal"] += 1
                continue
            s["n_ok"] += 1
            s["units"].append(e["units"])
            ref = e["ref"]
            tests = ref["tests"]
            if ref["collect_error"] or ref["timeout"]:
                s["ex_collect"] += 1
            else:
                s["rt_n"] += len(tests)
                s["rt_p"] += sum(v == "pass" for v in tests.values())
                s["ntests"].append(len(tests))
                if all(v == "pass" for v in tests.values()):
                    s["ex_pass"] += 1
            ra = e["ref_assertions"]
            s["a_n"] += len(ra)
            s["a_p"] += sum(v == "pass" for v in ra.values())
            s["a_unr"] += sum(v == "unreached" for v in ra.values())
            valid = (not ref["collect_error"]) and (not ref["timeout"]) and all(v == "pass" for v in tests.values())
            for w in e["wrong"]:
                s["w_n"] += 1
                s["w_rej"] += w["rejected"]
                if valid:
                    s["wv_n"] += 1
                    s["wv_rej"] += w["rejected"]
        summ[k] = s
    L += ["## 3. 每種考卷總表", "",
          "| 種類 | 有考卷/37 | 無法解析 | none | 平均斷言數 | 平均測試函式數 | 參考解逐測試通過 | 參考解逐斷言通過（unreached 算失敗） | 參考解整份全過 | 錯解拒絕（全部） | 錯解拒絕（只算參考解全過的考卷） |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in KINDS:
        s = summ[k]
        mu = f"{sum(s['units'])/len(s['units']):.1f}" if s["units"] else "n/a"
        mt = f"{sum(s['ntests'])/len(s['ntests']):.1f}" if s["ntests"] else "n/a"
        L.append(f"| {k.upper()} | {s['ex_n']} | {s['n_mal']} | {s['n_none']} | {mu} | {mt} | {pct(s['rt_p'], s['rt_n'])} | "
                 f"{pct(s['a_p'], s['a_n'])}（unreached {s['a_unr']}） | {pct(s['ex_pass'], s['ex_n'])} | "
                 f"{pct(s['w_rej'], s['w_n'])} | {pct(s['wv_rej'], s['wv_n'])} |")
    L += ["", "「整份全過」分母含無法解析者（算不過）；匯入失敗或逾時的考卷（參考解 collect_error/timeout）："
          + ", ".join(f"{k.upper()} {summ[k]['ex_collect']}" for k in KINDS) + "。", ""]
    # ---- 逐題
    L += ["## 4. 逐題", "", "格式：斷言數／參考解逐測試通過/總數／錯解拒絕數/入選錯解數。", "",
          "| 題 | 入選錯解 | " + " | ".join(k.upper() for k in KINDS) + " |", "|---|---|" + "---|" * len(KINDS)]
    for t, T in tasks.items():
        cells = []
        for k in KINDS:
            e = T["exams"][k]
            if e["status"] != "ok":
                cells.append(e["status"])
                continue
            tests = e["ref"]["tests"]
            tp = sum(v == "pass" for v in tests.values())
            flag = "!" if (e["ref"]["collect_error"] or e["ref"]["timeout"]) else ""
            rj = sum(w["rejected"] for w in e["wrong"])
            cells.append(f"{e['units']}／{tp}/{len(tests)}{flag}／{rj}/{len(e['wrong'])}")
        L.append(f"| {t} | {per_task_q[t]} | " + " | ".join(cells) + " |")
    L += ["", "「!」＝參考解下該考卷匯入失敗或逾時（0 個測試）。", ""]
    # ---- 錯誤斷言
    L += ["## 5. 考卷錯誤（參考解沒過的斷言／測試）", ""]
    nerr = 0
    for k in KINDS:
        for t, T in tasks.items():
            e = T["exams"][k]
            if e["status"] != "ok":
                continue
            bad = {a: s for a, s in e["ref_assertions"].items() if s != "pass"}
            failed_tests = [i for i, v in e["ref"]["tests"].items() if v != "pass"]
            if not bad and not failed_tests and not e["ref"]["collect_error"] and not e["ref"]["timeout"]:
                continue
            L.append(f"### {k.upper()} / {t}")
            if e["ref"]["collect_error"] or e["ref"]["timeout"]:
                L.append(f"- 整份考卷在參考解下無法執行（collect_error={e['ref']['collect_error']}, timeout={e['ref']['timeout']}）：`{e['ref']['tail'].strip()[-200:]}`")
            for a, s in sorted(bad.items(), key=lambda x: int(x[0])):
                nerr += 1
                L.append(f"- 行 {a}（{s}）：`{seg(t, k, a)}`" + (f" → {e['ref_assertion_msgs'].get(a, '')[:160]}" if s == "fail" else ""))
            if failed_tests:
                L.append("- 失敗的測試：" + ", ".join(f"`{i.split('::')[-1]}`" for i in failed_tests))
            L.append("")
    L.insert(L.index("## 5. 考卷錯誤（參考解沒過的斷言／測試）") + 1, f"共 {nerr} 個斷言錯誤（逐斷言口徑，不含整份無法執行者）；逐項如下。")
    notes = RES / "REPORT_NOTES.md"
    (RES / "REPORT.md").write_text("\n".join(L) + "\n" + (notes.read_text(encoding="utf-8") if notes.exists() else ""), encoding="utf-8")
    print("written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
