"""INLINE_COPY_MIN 敏感性（backlog P1 候選 (c)，方向 A 通用任務）。

`INLINE_COPY_MIN = 120`（vacant_network/trace/evidence.py）是「拍的值」：改到 80／200
對樣本集的影響從未量測（docs/UNIVERSAL_TASKS.md §3 門檻 5 要求保守門檻，且改動前
要在樣本集上量誤報）。這個測試把門檻掃一遍，在既有樣本集
（tests/test_noncode_samples.py：21 乾淨 + L-fake）上量出：

- **FP 欄**：每個 `test_clean_*` 樣本在該門檻下是否冒出 copy_of_inline
  （同一份乾淨樣本、同一個 spy 機制，與常駐誤報門
  `test_all_clean_samples_have_no_false_positives` 一致）；
- **FN 欄**：L-fake inline echo（n13）在該門檻下是否仍被抓；
- **邊際表**：每個「交件是 prompt 逐字子串」的候選，其正規化長度＋線索豁免狀態
  ——這些是唯一可能隨門檻下降變成誤報的乾淨交件；n13 的長度是 FN 邊界的實測值。

**本測試不改任何行為**：只量測＋斷言量測本身有意義（邊界必須落在掃測窗內，
否則量不出東西）。結論（2026-10-27 實測）：現行樣本集容許 T ∈ [3, 148]；
120 在窗內且離 FP 邊界最遠，**維持 120**（DECISION 見 ops STATE.md）。

跑法：`pytest tests/test_inline_copy_min_sensitivity.py -v -s`（表單印到 stdout）
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from typing import Any

from vacant_network.adapters import install as INS
from vacant_network.trace import evidence as EV

# test_noncode_samples.py 沒有 __init__.py（repo 慣例），用路徑載入同一份樣本集。
_TESTS_DIR = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "vacant_noncode_samples", _TESTS_DIR / "test_noncode_samples.py")
NS = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = NS
_spec.loader.exec_module(NS)

# 掃測窗：含現行 120、n13 實測長度 148 的兩側（148 仍抓／150 漏抓，把邊界釘死）、
# 以及 backlog 點名的 80／200。
THRESHOLDS = (2, 3, 5, 8, 10, 20, 50, 80, 100, 120, 148, 150, 200, 300)
_LFAKE = "test_lfake_inline_echo_is_caught"


def _fresh_env(sub: pathlib.Path, monkeypatch: Any) -> None:
    """與 tests/test_noncode_samples.py 的 `env` fixture 相同的乾淨環境。"""
    (sub / "home").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(sub / "home"))
    monkeypatch.setenv("VACANT_HOME", str(sub / "vh"))
    for k in ("VACANT_TRACE", "VACANT_MODE"):
        monkeypatch.delenv(k, raising=False)
    p = INS.state_root() / "install.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))


def _run_one(name: str, sub: pathlib.Path, monkeypatch: Any) -> tuple[set, bool]:
    """跑一個樣本測試（`sub` 當 env 傳入），回 (發現 kind 集合, 該測試自身斷言是否過)。"""
    _fresh_env(sub, monkeypatch)
    seen: set[str] = set()
    orig = NS.Agent.evidence

    def spy(self, *a: Any, **k: Any) -> dict:
        ev = orig(self, *a, **k)
        seen.update(f.get("kind") for f in ev["findings"])
        return ev

    NS.Agent.evidence = spy
    ok = True
    try:
        getattr(NS, name)(sub)
    except AssertionError:
        ok = False
    finally:
        NS.Agent.evidence = orig
    return seen, ok


class _Margins:
    """把每個「交件是 prompt 逐字子串」候選的（正規化長度、線索）記下來。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.current = "<none>"
        self._orig = EV.Evidence._copy_of_inline

    def install(self) -> None:
        orig = self._orig
        margins = self

        def wrapper(self: Any, delivs: dict, outs: list, task_texts: list,
                    latest_idx: Any) -> list:
            texts = [t for t in task_texts if t]
            exempt = any(EV.COPY_CUE.search(t) or EV.VERBATIM_CUE.search(t) or
                         EV.EXTRACT_CUE.search(t) for t in texts)
            prompts = [EV._collapse(t).lower() for t in texts]
            for path, (_old, new) in sorted(delivs.items()):
                if not new or not new.strip():
                    continue
                n_d = EV._collapse(new).lower()
                margins.rows.append({
                    "sample": margins.current,
                    "path": path,
                    "norm_len": len(n_d),
                    "substring_of_prompt": bool(prompts)
                        and any(n_d != n_t and n_d in n_t for n_t in prompts),
                    "exempt_cue": exempt,
                })
            return orig(self, delivs, outs, task_texts, latest_idx)

        EV.Evidence._copy_of_inline = wrapper  # type: ignore[assignment]

    def uninstall(self) -> None:
        EV.Evidence._copy_of_inline = self._orig  # type: ignore[assignment]


def test_inline_copy_min_sensitivity_table(tmp_path, monkeypatch):
    DEFAULT = EV.INLINE_COPY_MIN
    assert DEFAULT == 120, "現行門檻已變，本測試的斷言要隨之更新"
    clean_names = sorted(n for n in dir(NS)
                         if n.startswith("test_clean_") and callable(getattr(NS, n)))
    assert len(clean_names) >= 20, f"乾淨樣本不足 20：{len(clean_names)}"

    margins = _Margins()
    margins.install()
    results: list[dict] = []
    try:
        for T in THRESHOLDS:
            monkeypatch.setattr(EV, "INLINE_COPY_MIN", T)
            fp = []
            for i, name in enumerate(clean_names):
                sub = tmp_path / f"fp_{T}_{i}"
                sub.mkdir(parents=True, exist_ok=True)
                margins.current = name
                seen, _ok = _run_one(name, sub, monkeypatch)
                if "copy_of_inline" in seen:
                    fp.append(name)
            sub = tmp_path / f"fn_{T}"
            sub.mkdir(parents=True, exist_ok=True)
            margins.current = _LFAKE
            seen, ok = _run_one(_LFAKE, sub, monkeypatch)
            assert "copy_of_inline" in seen or not ok, (T, seen)
            results.append({"T": T, "fp": fp, "lfake_caught": ok and "copy_of_inline" in seen})
    finally:
        margins.uninstall()

    # ── 表單 ────────────────────────────────────────────────────────────────
    table = [f"INLINE_COPY_MIN 敏感性（{len(clean_names)} 乾淨樣本 + L-fake n13；"
             f"現行 = {DEFAULT}）"]
    for r in results:
        mark = "  <-- 現行" if r["T"] == DEFAULT else ""
        table.append(f"T={r['T']:<4} false_positives={len(r['fp']):<3} "
                     f"lfake_n13_caught={r['lfake_caught']}{mark}"
                     + (f"   fp={r['fp']}" if r["fp"] else ""))
    subs = sorted({(m["sample"], m["norm_len"], m["exempt_cue"])
                   for m in margins.rows if m["substring_of_prompt"]},
                  key=lambda x: (x[1], x[0]))
    table.append("邊際（交件是 prompt 逐字子串的樣本；norm_len 為正規化後長度）：")
    for sample, ln, exempt in subs:
        table.append(f"  {sample}: norm_len={ln} exempt_cue={exempt}")
    print("\n".join(table))

    # ── 斷言 ────────────────────────────────────────────────────────────────
    by_T = {r["T"]: r for r in results}

    # 1) 現行預設值在安全窗內：零誤報 + L-fake 仍被抓。
    d = by_T[DEFAULT]
    assert d["fp"] == [], d
    assert d["lfake_caught"], d

    # 2) 兩欄都隨 T 單調不增（門檻升高，誤報與抓得到都只會變少）——量測機制自身沒壞。
    fp_counts = [len(r["fp"]) for r in results]
    assert all(a >= b for a, b in zip(fp_counts, fp_counts[1:])), results
    caught = [r["lfake_caught"] for r in results]
    assert all(a >= b for a, b in zip(caught, caught[1:])), results

    # 3) 掃測窗真的橫跨了 L-fake 的漏抓邊界（量出的是邊界，不是常數）：
    #    最低門檻仍抓到、最高門檻漏抓。
    assert results[0]["lfake_caught"] and not results[-1]["lfake_caught"], results

    # 4) FP 側有真實的 FP-eligible 樣本（n16，正規化長度 2）：最低門檻下必現，
    #    證明「零誤報」是門檻撐住的、不是樣本碰巧沒有這種交件。
    assert fp_counts[0] >= 1, results
    assert all(r["fp"] == [] for r in results if r["T"] >= 3), results
