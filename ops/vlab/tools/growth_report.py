#!/usr/bin/env python3
"""growth_report — 主軸 2 量具：「~/.vacant 從零開始一天長多少」的真機增長趨勢（round 187，2026-10-29）。

背景（為什麼需要這支）：
- ASSIGNMENT 最優先驗收 4(a) 與 disk_top_priority.md §5-4：「量它從零開始一天長多少，
  就是使用者真實的成長速度」。既有量具各管一半：
  - `vacant usage`（retention.usage_main）＝**此刻**多大、對 64 MiB trace 上限與
    256 MiB 穩態封頂的百分比；
  - `vacant_growth_log.py`＝人手觸發的單點快照（~/dev/ops/data/vacant_growth.jsonl）；
  - `~/.vacant/growth.jsonl`＝round 186 起 auto gc 每次真跑自動記的同 schema 點。
  但「一天長多少」是**序列問題**：單點回答不了。本工具把兩份 JSONL 併排、
  算 24h 視窗內最大增長、峰値、對封頂的餘量，並判「證據夠不夠」（不夠＝UNKNOWN，
  絕不假 PASS）。
- **唯讀**：只讀兩份 JSONL（＋可選 gc_report.json），不碰 `~/.vacant` 任何檔案。
- 上限常數直接 import `vacant_network.retention`（DEFAULT_TRACE_BUDGET_BYTES、
  STABLE_ENVELOPE_BYTES）——量具與產品同一來源，不另抄一份數字（H-5 同規矩）。
  import 不到時（非 wheel/無 venv）上限欄＝None、判定降級 UNKNOWN，不猜數字。

判定語意（誠實口徑）：
- **UNKNOWN**：兩份 JSONL 都缺、或點數 <2、或跨時 <20h（「一天」證據不足）、
  或上限常數取不到。UNKNOWN 既不是 PASS 也不是 FAIL（同 H-3 的 UNVERIFIABLE 口徑）。
- **PASS**：證據足（≥20h 序列）＋最新點總計 ≤ 穩態封頂＋最新點 trace ≤ trace 上限
  ＋最新一個 gc 點 status=ok 且 target_reached=true（回收在真實使用裡生效）。
- **FAIL**：證據足但任一上限被最新點超過、或 gc 點 status 非 ok／target_reached 非 true。
  歷史峰値超過上限**不**單獨判 FAIL（封頂是軟上限、store 可暫超待 gc 收回——
  disk_top_priority §1 誠實邊界），但會記在 `peak_overrun` 欄讓使用者看見。

用法：
  python3 ops/vlab/tools/growth_report.py [--home ~/.vacant] [--ops-data ~/dev/ops/data]
      [--json] [--out PATH]
  python3 ops/vlab/tools/growth_report.py --selftest

退出碼：0 verdict=PASS；1 verdict=FAIL 或 UNKNOWN（證據不足）；2 selftest 失敗或輸入不可讀。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:  # 量具與產品同一來源（fail-open：import 不到 → 上限=None → UNKNOWN，不猜）
    from vacant_network import retention as _ret
    TRACE_BUDGET_BYTES: int | None = getattr(_ret, "DEFAULT_TRACE_BUDGET_BYTES", None)
    ENVELOPE_BYTES: int | None = getattr(_ret, "STABLE_ENVELOPE_BYTES", None)
except Exception:  # noqa: BLE001 - 量具必須在任何環境跑得起
    TRACE_BUDGET_BYTES = None
    ENVELOPE_BYTES = None

MIN_EVIDENCE_HOURS = 20.0  # 「一天」證據門檻：跨時 <20h 判 UNKNOWN（不是 24h：真機序列 20:53 已滿 24h，但量具不該卡邊）


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")
    except (TypeError, ValueError):
        return None


def load_points(*paths: Path) -> list[dict]:
    """讀多份 growth JSONL，併排去重（同 ts+同 total_bytes 只留一筆）。缺檔/壞行跳過（誠實：只報讀得到的）。"""
    seen: set[tuple[str, int]] = set()
    out: list[dict] = []
    for p in paths:
        if not p.is_file():
            continue
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                o = json.loads(ln)
                ts, total = o.get("ts"), o.get("total_bytes")
                if not isinstance(ts, str) or not isinstance(total, int):
                    continue
                key = (ts, total)
                if key in seen:
                    continue
                seen.add(key)
                o["_src"] = str(p)
                out.append(o)
            except ValueError:
                continue
    return out


def _sort_key(o: dict) -> tuple:
    dt = _parse_ts(o["ts"])
    return (dt is None, dt or datetime.min.replace(tzinfo=None), o["ts"])


def trend(points: list[dict]) -> dict:
    """從點列算增長趨勢。points 需 ≥1；跨時/24h 增長在 <2 點時為 None（UNKNOWN 素材）。"""
    pts = sorted(points, key=_sort_key)
    totals = [p["total_bytes"] for p in pts]
    first, last = pts[0], pts[-1]
    t0, t1 = _parse_ts(first["ts"]), _parse_ts(last["ts"])
    span_h = (t1 - t0).total_seconds() / 3600.0 if (t0 and t1) else None

    max_24h = None  # 24h 視窗內最大增長（位元組）：「一天長多少」的保守量（取最大正向視窗）
    if t0 and t1 and len(pts) >= 2:
        best = 0
        for i, a in enumerate(pts):
            ta = _parse_ts(a["ts"])
            for b in pts[i + 1:]:
                tb = _parse_ts(b["ts"])
                if ta and tb and 0 < (tb - ta).total_seconds() <= 24 * 3600:
                    best = max(best, b["total_bytes"] - a["total_bytes"])
        max_24h = best

    per_dir_peak: dict[str, int] = {}
    for p in pts:
        for k, v in (p.get("per_dir_bytes") or {}).items():
            if isinstance(v, int):
                per_dir_peak[k] = max(per_dir_peak.get(k, 0), v)
    per_dir_latest = {k: v for k, v in (last.get("per_dir_bytes") or {}).items() if isinstance(v, int)}

    last_gc = (last.get("gc_last") or {})
    return {
        "n_points": len(pts),
        "first": {"ts": first["ts"], "total_bytes": first["total_bytes"]},
        "last": {"ts": last["ts"], "total_bytes": last["total_bytes"]},
        "span_hours": round(span_h, 2) if span_h is not None else None,
        "min_total_bytes": min(totals),
        "peak_total_bytes": max(totals),
        "latest_total_bytes": totals[-1],
        "max_24h_growth_bytes": max_24h,
        "net_growth_bytes": totals[-1] - totals[0],
        "per_dir_peak_bytes": per_dir_peak,
        "per_dir_latest_bytes": per_dir_latest,
        "gc_last": last_gc or None,
    }


def report(home: Path | None = None, ops_data: Path | None = None,
           growth_home: Path | None = None) -> dict:
    """彙整兩份 JSONL → 趨勢＋封頂判定。純讀取；不寫任何檔案。"""
    home = Path(home) if home else Path(os.path.expanduser("~/.vacant"))
    ops_data = Path(ops_data) if ops_data else Path(os.path.expanduser("~/dev/ops/data"))
    candidates = [
        growth_home / "growth.jsonl" if growth_home else home / "growth.jsonl",
        ops_data / "vacant_growth.jsonl",
    ]
    sources = [str(c) for c in candidates if c.is_file()]
    points = load_points(*candidates)
    base = {
        "sources": sources,
        "sources_missing": [str(c) for c in candidates if not c.is_file()],
        "caps": {
            "trace_budget_bytes": TRACE_BUDGET_BYTES,
            "stable_envelope_bytes": ENVELOPE_BYTES,
            "caps_source": "vacant_network.retention" if TRACE_BUDGET_BYTES and ENVELOPE_BYTES else None,
        },
    }
    if not points:
        base.update({"verdict": "UNKNOWN",
                     "reason": "no growth points readable — 既沒有 auto gc 點也沒有手動快照；"
                               "「一天長多少」目前無法回答（UNKNOWN，不是 0 也不是 PASS）"})
        return base
    t = trend(points)
    base.update(t)

    span_ok = (t["span_hours"] is not None and t["span_hours"] >= MIN_EVIDENCE_HOURS
               and t["n_points"] >= 2)
    if not span_ok:
        base.update({"verdict": "UNKNOWN",
                     "reason": f"證據不足：n_points={t['n_points']}, span_hours={t['span_hours']} "
                               f"(門檻 ≥2 點且 ≥{MIN_EVIDENCE_HOURS:g}h)——「一天長多少」還量不出來"})
        return base
    if not (TRACE_BUDGET_BYTES and ENVELOPE_BYTES):
        base.update({"verdict": "UNKNOWN",
                     "reason": "上限常數取不到（vacant_network.retention import 失敗）——"
                               "序列有，但對不上產品上限，不判 PASS"})
        return base

    # 判定用**最新點**（穩態口徑）：封頂是軟上限，store 可暫超待 gc 收回
    #（disk_top_priority §1 誠實邊界）；歷史峰値只記在 peak_overrun，不單獨判 FAIL。
    trace_latest = (t.get("per_dir_latest_bytes") or {}).get("trace")
    latest = t["latest_total_bytes"]
    peak = t["peak_total_bytes"]
    gc = t.get("gc_last") or {}
    problems = []
    if latest > ENVELOPE_BYTES:
        problems.append(f"latest total {latest} B > 穩態封頂 {ENVELOPE_BYTES} B")
    if trace_latest is not None and trace_latest > TRACE_BUDGET_BYTES:
        problems.append(f"latest trace {trace_latest} B > trace 上限 {TRACE_BUDGET_BYTES} B")
    if gc.get("status") != "ok":
        problems.append(f"最新 gc 點 status={gc.get('status')!r}（非 ok）")
    elif gc.get("target_reached") is not True:
        problems.append("最新 gc 點 target_reached 非 true（回收未證實在真實使用裡生效）")

    base["peak_overrun"] = {
        "peak_total_bytes": peak,
        "over_stable_envelope": peak > ENVELOPE_BYTES,
        "note": "歷史峰値超封頂＝暫超（軟上限、待 gc 收回）；最新點超封頂才判 FAIL（disk_top_priority §1 誠實邊界）",
    }
    if problems:
        base.update({"verdict": "FAIL", "reason": "; ".join(problems)})
    else:
        base.update({
            "verdict": "PASS",
            "reason": (f"{t['n_points']} 點跨 {t['span_hours']}h：峰值 {peak} B、"
                       f"最新 {latest} B ≤ 封頂 {ENVELOPE_BYTES} B；24h 視窗最大增長 "
                       f"{t['max_24h_growth_bytes']} B；gc status=ok 且 target_reached=true"),
        })
    return base


def _fmt_mb(n: int | None) -> str:
    return "—" if n is None else f"{n / 1048576:.1f} MiB"


def human(base: dict) -> str:
    if base["verdict"] == "UNKNOWN":
        return (f"UNKNOWN：{base.get('reason')}\n"
                f"  sources: {base['sources'] or '（無）'}；missing: {base['sources_missing']}")
    t = base
    lines = [
        f"verdict: {t['verdict']}",
        f"sources: {', '.join(t['sources']) or '—'}",
        f"序列: {t['first']['ts']} → {t['last']['ts']}（{t['span_hours']}h，{t['n_points']} 點）",
        f"總計: min {_fmt_mb(t['min_total_bytes'])} / peak {_fmt_mb(t['peak_total_bytes'])} "
        f"/ latest {_fmt_mb(t['latest_total_bytes'])}",
        f"「一天長多少」（24h 視窗最大增長）: {_fmt_mb(t['max_24h_growth_bytes'])}",
        f"淨增長（序列內）: {_fmt_mb(t['net_growth_bytes'])}",
        f"分組峰值: " + ", ".join(f"{k} {_fmt_mb(v)}" for k, v in sorted(t["per_dir_peak_bytes"].items())),
        f"分組最新: " + ", ".join(f"{k} {_fmt_mb(v)}" for k, v in sorted(t["per_dir_latest_bytes"].items())),
        f"封頂: trace 上限 {_fmt_mb(t['caps']['trace_budget_bytes'])} / "
        f"穩態 {_fmt_mb(t['caps']['stable_envelope_bytes'])}"
        f"（{t['caps']['caps_source'] or 'UNKNOWN'}）",
        f"gc_last: {t['gc_last']}",
    ]
    if t["verdict"] != "PASS":
        lines.append(f"原因: {t['reason']}")
    return "\n".join(lines)


def selftest() -> int:
    """紅綠對照（tmp 合成 JSONL，不碰真實 ~/.vacant）：
    1 綠：26h 3 點、在封頂內、gc ok → PASS＋max_24h 正確
    2 紅：最新點超封頂 → FAIL（不能假 PASS）
    3 未知：無檔 → UNKNOWN
    4 未知：2 點但只跨 2h → UNKNOWN（證據不足）
    任一不成立 → return 2。"""
    import tempfile

    ENV = ENVELOPE_BYTES or 256 * 1024 * 1024
    TR = TRACE_BUDGET_BYTES or 64 * 1024 * 1024

    def _point(ts: str, total: int, trace: int, gc_ok: bool = True) -> str:
        return json.dumps({"ts": ts, "home": "/tmp/fx", "total_bytes": total,
                           "per_dir_bytes": {"trace": trace, "possess": 1000},
                           "objects_files": 10,
                           "gc_last": {"status": "ok" if gc_ok else "error",
                                       "target_reached": True}})

    def _write(d: Path, lines: list[str], name: str = "vacant_growth.jsonl") -> Path:
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # 1 綠
        g = _write(td / "green", [_point("2026-10-28T00:00:00+0000", 20 * 1024 * 1024, 10 * 1024 * 1024),
                                  _point("2026-10-28T12:00:00+0000", 30 * 1024 * 1024, 15 * 1024 * 1024),
                                  _point("2026-10-29T02:00:00+0000", 40 * 1024 * 1024, 20 * 1024 * 1024)],
                   name="growth.jsonl")
        r = report(home=td / "green", ops_data=td / "none")
        assert r["verdict"] == "PASS", r
        # 24h 視窗：00:00→12:00(+12h, +10MiB)、12:00→02:00(+14h, +10MiB)；00:00→02:00(+26h) 出窗
        assert r["max_24h_growth_bytes"] == 10 * 1024 * 1024, r
        # 2 紅：最新點超封頂
        red = _write(td / "red", [_point("2026-10-28T00:00:00+0000", 10 * 1024 * 1024, 5 * 1024 * 1024),
                                  _point("2026-10-29T00:00:00+0000", (ENV // 1024 // 1024 + 1) * 1024 * 1024, TR + 1)],
                     name="growth.jsonl")
        r = report(home=td / "red", ops_data=td / "none")
        assert r["verdict"] == "FAIL", r
        # 3 未知：無檔
        r = report(home=td / "missing", ops_data=td / "missing2")
        assert r["verdict"] == "UNKNOWN" and not r["sources"], r
        # 4 未知：跨時不足
        short = _write(td / "short", [_point("2026-10-29T00:00:00+0000", 20 * 1024 * 1024, 10 * 1024 * 1024),
                                      _point("2026-10-29T02:00:00+0000", 22 * 1024 * 1024, 11 * 1024 * 1024)])
        r = report(home=short, ops_data=td / "none")
        assert r["verdict"] == "UNKNOWN", r
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--home", default=None, help="~/.vacant 路徑（預設 $HOME/.vacant）")
    ap.add_argument("--ops-data", default=None, help="ops 數據目錄（預設 ~/dev/ops/data）")
    ap.add_argument("--json", action="store_true", help="只出 JSON")
    ap.add_argument("--out", default=None, help="JSON 另存到 PATH")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        rc = selftest()
        if not a.json:
            print("selftest:", "OK" if rc == 0 else "FAIL")
        return rc
    base = report(Path(a.home) if a.home else None, Path(a.ops_data) if a.ops_data else None)
    if a.out:
        Path(a.out).write_text(json.dumps(base, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if a.json:
        print(json.dumps(base, ensure_ascii=False, indent=1))
    else:
        print(human(base))
    return 0 if base["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
