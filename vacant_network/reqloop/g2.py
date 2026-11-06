"""
G2 真草稿冒煙測試（工單 P000-20261104-02-real-draft-smoke，2026-11-04）。

範圍（工單紅線）：
- 6 格（3 真草稿 × generic/localized）只驗管線，不宣稱任何提升。
- 兩臂同模型、同總預算；成本缺值＝UNKNOWN（None），絕不填 0。
- hidden 分只引用既有受權量表的已記錄結果（score.json），不餵給模型、不在本地重跑。
- 不向修復模型提供隱藏答案：checks.check_kv_recomputed 的重算值不進證據；
  repair.build_repair_prompt 只帶可見反例。
- 原型 opt-in：不呼叫本模組時，系統行為不變。

入口（單一）：
  python -m vacant_network.reqloop.g2 --manifest <path> --dry-run   # 列 3 草稿/6 格/hash/budget
  python -m vacant_network.reqloop.g2 --manifest <path>             # 真跑（同一入口）
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import pathlib
import tempfile
import time
from typing import Any, Callable, Sequence

from vacant_network.reqloop import repair
from vacant_network.reqloop.requirements import RequirementSet

RESULT_SCHEMA = "vacant.reqloop.g2.result/1"
MANIFEST_SCHEMA = "vacant.reqloop.g2.manifest/1"
AFTER_HIDDEN_UNKNOWN = "UNKNOWN"   # 本地無權重跑 hidden scorer；缺失即 UNKNOWN，絕不填 0

DEFAULT_MANIFEST = (pathlib.Path(__file__).resolve().parents[2]
                    / "ops" / "reqloop" / "g2" / "smoke" / "manifest.json")


def _sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ── manifest（先凍結，再跑）──────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class G2Manifest:
    """凍結清單：3 份真草稿（來源、已記錄 hidden 分、交付檔 hash）、兩臂、模型、預算。"""
    schema: str
    frozen_at: str
    ticket: str
    purpose: str
    arms: tuple[str, ...]
    model: dict[str, Any]
    budget: dict[str, Any]
    scoring: dict[str, Any]
    leak_guard: str
    drafts: tuple[dict[str, Any], ...]
    raw: dict[str, Any]
    manifest_path: str | None = None   # load() 設；結果檔用它記實際生效的 manifest

    @classmethod
    def load(cls, path: str | pathlib.Path) -> G2Manifest:
        p = pathlib.Path(path)
        raw = json.loads(p.read_text(encoding="utf-8"))
        if raw.get("schema") != MANIFEST_SCHEMA:
            raise ValueError(f"manifest schema 不符：{raw.get('schema')!r} ≠ {MANIFEST_SCHEMA!r}")
        drafts = list(raw.get("drafts", []))
        if not drafts:
            raise ValueError("manifest 沒有 drafts")
        for d in drafts:
            for field in ("name", "role", "task_id", "source", "draft", "task"):
                if field not in d:
                    raise ValueError(f"draft 缺欄位 {field!r}: {d.get('name')!r}")
            if d["source"].get("score") is None:
                raise ValueError(f"draft {d['name']!r} 沒有已記錄 hidden 分（score 不得為 null）")
            if not d["draft"].get("files"):
                raise ValueError(f"draft {d['name']!r} 沒有凍結交付檔 hash")
            if not d["task"]["requirements"].get("sha256"):
                raise ValueError(f"draft {d['name']!r} 沒有 requirements sha256")
        return cls(
            schema=raw["schema"],
            frozen_at=str(raw.get("frozen_at", "")),
            ticket=str(raw.get("ticket", "")),
            purpose=str(raw.get("purpose", "")),
            arms=tuple(raw.get("arms", ["generic", "localized"])),
            model=dict(raw.get("model", {})),
            budget=dict(raw.get("budget", {})),
            scoring=dict(raw.get("scoring", {})),
            leak_guard=str(raw.get("leak_guard", "")),
            drafts=tuple(drafts),
            raw=raw,
            manifest_path=str(p),
        )

    def verify_frozen(self, base: str | pathlib.Path) -> None:
        """凍結副本必須真的在 base 下、hash對得上（工單：先凍結清單再跑）。"""
        base = pathlib.Path(base)
        for d in self.drafts:
            for rel, h in d["draft"]["files"].items():
                f = base / d["draft"]["dir"] / rel
                if not f.is_file():
                    raise FileNotFoundError(f"凍結交付檔缺失：{f}")
                if _sha256(f) != h:
                    raise ValueError(f"凍結交付檔 hash 不符：{f}")
            req_f = base / d["task"]["dir"] / "requirements.json"
            if not req_f.is_file():
                raise FileNotFoundError(f"凍結 requirements 缺失：{req_f}")
            if _sha256(req_f) != d["task"]["requirements"]["sha256"]:
                raise ValueError(f"requirements hash 不符：{req_f}")
            # r1011（審計票 R20261104_2123-1）：凍結清單裡的每條 pin 都必須可解析、
            # hash 相符——effect_manifest 曾有 5 份 e013 data_files key 缺 data/ 前綴，
            # 檔案在、hash 對，舊門卻從不驗（靠漏驗拿到的綠燈就是放過洞的條件）。
            for rel, h in d["task"].get("data_files", {}).items():
                df = base / d["task"]["dir"] / rel
                if not df.is_file():
                    raise FileNotFoundError(f"凍結資料檔缺失：{df}")
                if _sha256(df) != h:
                    raise ValueError(f"凍結資料檔 hash 不符：{df}")


def plan_cells(man: G2Manifest) -> list[tuple[str, str]]:
    """6 格＝3 草稿 × 2 臂（順序固定：先草稿、後臂，兩臂同草稿同預算）。"""
    return [(d["name"], arm) for d in man.drafts for arm in man.arms]


# ── dry-run（不呼叫模型）─────────────────────────────────────────────

def dry_run_json(man: G2Manifest) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "mode": "dry_run",
        "drafts": list(man.drafts),
        "cells": [{"draft": n, "arm": a} for n, a in plan_cells(man)],
        "arms": list(man.arms),
        "model": man.model,
        "budget": man.budget,
        "scoring": man.scoring,
        "hidden_after": AFTER_HIDDEN_UNKNOWN,
    }


def dry_run_text(man: G2Manifest) -> str:
    cells = plan_cells(man)
    b = man.budget
    m = man.model
    lines: list[str] = []
    lines.append("G2 真草稿冒煙 — DRY RUN（不呼叫模型、不改任何凍結檔）")
    lines.append(f"ticket : {man.ticket}")
    lines.append(f"purpose: {man.purpose}")
    lines.append("")
    lines.append(f"{len(man.drafts)} drafts · {len(cells)} cells（arms: {', '.join(man.arms)}）")
    lines.append(f"model  : {m.get('model', 'UNKNOWN')} (provider: {m.get('provider', 'UNKNOWN')})"
                 + (f"  ← {m['note']}" if m.get("note") else ""))
    lines.append(
        "budget : max_rounds_per_cell=" + str(b.get("max_rounds_per_cell", "UNKNOWN"))
        + "  timeout_s_per_round=" + str(b.get("timeout_s_per_round", "UNKNOWN"))
        + "  hard_token_cap=" + str(bool(b.get("hard_token_cap", False))).lower()
        + "  min_rounds=" + json.dumps(b.get("min_rounds", {}), ensure_ascii=False)
    )
    if b.get("token_cap_note"):
        lines.append(f"         {b['token_cap_note']}")
    lines.append("")
    for d in man.drafts:
        score = d["source"].get("score", {})
        lines.append(f"  - {d['name']}  role={d['role']}  task={d['task_id']}")
        lines.append(f"      source : {d['source'].get('run', '?')}/{d['source'].get('cell', '?')}"
                     f"  recorded_score={score.get('n_correct', 'UNKNOWN')}"
                     f" (pass={score.get('pass', 'UNKNOWN')})")
        for rel, h in d["draft"]["files"].items():
            lines.append(f"      file   : {d['draft']['dir']}/{rel}  sha256={h}")
        lines.append(f"      req    : {d['task']['dir']}/requirements.json  sha256="
                     f"{d['task']['requirements']['sha256']}")
    lines.append("")
    lines.append("cells  :")
    for i, (n, a) in enumerate(cells, 1):
        lines.append(f"  {i}. {n} × {a}")
    lines.append("")
    lines.append(f"hidden-after = {AFTER_HIDDEN_UNKNOWN}（本地無權重跑 hidden scorer；缺值不填 0）")
    return "\n".join(lines)


# ── 真跑（6 格，同模型同總預算）──────────────────────────────────────

@dataclasses.dataclass
class G2Result:
    manifest_sha256: str
    generated_at: str
    model: dict[str, Any]
    budget: dict[str, Any]
    scoring: dict[str, Any]
    cells: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        # R20261105_0346-1：no_gap（0 呼叫）格本無 usage/wall（cost 為 None）——未執行
        # 的格不該把整份總計拖成 UNKNOWN；只有「實際跑了 session（calls>0）」的格
        # 才要求齊全。舊碼對所有格 all()，任何一格 localized no_gap 即令 totals 恆 None。
        active = [c for c in self.cells if int(c["cost"].get("calls") or 0) > 0]

        def _total(key: str) -> int | None:
            # P001-20261105-03 紅線保留：任一格實際跑了（calls>0）卻缺值 ⇒ UNKNOWN（None）
            # ——不得把已知部分當完整總和。無任何 active 格 ⇒ 無可加總 ⇒ UNKNOWN（不填 0）。
            vals = [c["cost"].get(key) for c in active]
            if not vals:
                return None
            if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
                return int(sum(vals))
            return None

        return {
            "schema": RESULT_SCHEMA,
            "mode": "run",
            "generated_at": self.generated_at,
            "manifest": {"sha256": self.manifest_sha256},
            "model": self.model,
            "budget": self.budget,
            "scoring": self.scoring,
            "hidden_after": AFTER_HIDDEN_UNKNOWN,   # 全格同一口徑
            "cells": self.cells,
            "totals": {
                "cells": len(self.cells),
                # R20261105_0346-1：修復 session（agent 啟動）數；與 model_calls（API 請求數）嚴格區分
                "repair_sessions": sum(int(c["cost"].get("calls") or 0) for c in self.cells),
                "model_calls": _total("model_calls"),  # 實際模型 API 呼叫數；任一 active 格缺 ⇒ UNKNOWN（不填 0）
                "tokens": _total("tokens"),
                "wall_ms_total": _total("wall_ms_total"),
            },
        }


def run_g2_smoke(
    man: G2Manifest,
    base: str | pathlib.Path,
    out_root: str | pathlib.Path,
    build: Callable[[str, pathlib.Path], Any],
    run: Callable[..., dict[str, Any]],
    *,
    include_dirs: tuple[str, ...] = ("data",),
    max_tool_calls: int | None = None,
    max_tokens: int | None = None,
) -> G2Result:
    """跑 6 格。每格＝repair_slice（有上限的修復入口）：
    generic 臂 min_rounds=1（對的草稿也重驗一次）；localized 臂 min_rounds=0（缺口驅動）。
    兩臂同 max_rounds、同 timeout、同模型、同資料、同草稿。

    硬預算上限（opt-in，2026-11-06）：優先序＝顯式引數 > manifest budget
    （`max_tool_calls`／`max_tokens`）> None。皆 None＝不量不殺，呼叫形狀與以前相同；
    設了＝執行器超過即殺，該輪 `budget_exceeded` 記錄進每格 cell。
    """
    from vacant_network.reqloop.checks import run_requirement_checks

    base = pathlib.Path(base)
    man.verify_frozen(base)
    out_root = pathlib.Path(out_root)
    max_rounds = int(man.budget.get("max_rounds_per_cell", 2))
    timeout_s = float(man.budget.get("timeout_s_per_round", 300.0))
    min_by_arm = man.budget.get("min_rounds", {}) or {}
    if max_tool_calls is None:
        max_tool_calls = man.budget.get("max_tool_calls")
    if max_tokens is None:
        max_tokens = man.budget.get("max_tokens")

    cells: list[dict[str, Any]] = []
    for d in man.drafts:
        task_dir = base / d["task"]["dir"]
        draft_dir = base / d["draft"]["dir"]
        req_set = RequirementSet.load(task_dir / "requirements.json")
        # 修復前的 readable 判定（與 repair_slice 同一口径）
        before = run_requirement_checks(task_dir, req_set, draft_dir)
        before_map = {c.claim_id: c.status for c in before}
        for arm in man.arms:
            min_rounds = int(min_by_arm.get(arm, 1 if arm == "generic" else 0))
            outcome = repair.repair_slice(
                task_dir, req_set, draft_dir,
                out_root=out_root / d["name"] / arm,
                build=build, run=run,
                feedback_mode=arm,
                max_rounds=max_rounds, timeout_s=timeout_s,
                max_tool_calls=max_tool_calls, max_tokens=max_tokens,
                synthetic=False,
                min_rounds=min_rounds,
                include_dirs=include_dirs,
            )
            last_after = outcome.rounds[-1].after if outcome.rounds else before
            cells.append({
                "draft": d["name"],
                "task_id": d["task_id"],
                "role": d["role"],
                "arm": arm,
                "stopped": outcome.stopped,
                "before_readable_status": before_map,
                "after_readable_status": {c.claim_id: c.status for c in last_after},
                "final_readable_status": dict(outcome.final_status),
                "fixed": list(outcome.fixed),
                "regressed": list(outcome.regressed),
                "unresolved": list(outcome.unresolved),
                # P000-20261105-02：來源改動＝不可接受（必須可見於實驗記錄）
                "source_tampered": outcome.source_tampered,
                "source_tampered_files": list(outcome.source_tampered_files),
                # r1088：逐輪硬預算殺因（None＝該輪未被殺；未啟用上限時全 None）
                "budget_exceeded": [r.agent.get("budget_exceeded") for r in outcome.rounds],
                "before_hidden": d["source"].get("score"),       # 已記錄（引用，不重跑）
                "after_hidden": AFTER_HIDDEN_UNKNOWN,            # 本地無權重跑；絕不填 0，
                "cost": dict(outcome.cost),
                "draft_sha256": outcome.draft_sha256,
                "prompt_sha256": [r.prompt_sha256 for r in outcome.rounds],
            })
    manifest_used = (pathlib.Path(man.manifest_path)
                     if man.manifest_path else base / "manifest.json")
    return G2Result(
        manifest_sha256=_sha256(manifest_used),
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        model=dict(man.model),
        budget=dict(man.budget),
        scoring=dict(man.scoring),
        cells=cells,
    )


def write_result(res: G2Result, out_root: str | pathlib.Path) -> pathlib.Path:
    out_root = pathlib.Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    p = out_root / "g2_result.json"
    p.write_text(json.dumps(res.to_dict(), ensure_ascii=False, indent=1, default=str) + "\n",
                 encoding="utf-8")
    return p


# ── CLI（單一入口：--dry-run 列清單；否則真跑）────────────────────────

def _default_build(provider: str | None, model: str | None, hooks: bool = True):
    """與 repair._default_build 同一份（含直譯器 pin）——此處不許再有第二份副本（drift 來源）。"""
    return repair._default_build(provider, model, hooks=hooks)


def main(argv: Sequence[str] | None = None, *,
         build: Callable | None = None,
         run: Callable | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m vacant_network.reqloop.g2",
        description="G2 真草稿冒煙：3 真草稿 × generic/localized＝6 格；只驗管線，不宣稱提升。"
                    "原型 opt-in；不呼叫時系統行為不變。")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST),
                    help=f"凍結清單（預設 {DEFAULT_MANIFEST}）")
    ap.add_argument("--dry-run", action="store_true",
                    help="只列 3 草稿/6 格/hash/budget；不呼叫模型")
    ap.add_argument("--json", action="store_true", help="輸出 JSON（machine-readable）")
    ap.add_argument("--out", default=None, help="真跑輸出根目錄（預設 /tmp 下新建）")
    ap.add_argument("--provider", default=None, help="pi provider（預設讀 manifest）")
    ap.add_argument("--model", default=None, help="pi model（預設讀 manifest）")
    ap.add_argument("--no-hooks", action="store_true", help="pi 不載 Vacant 掛鉤")
    ap.add_argument("--max-tool-calls", type=int, default=None,
                    help="單輪 agent 工具呼叫數硬上限（覆蓋 manifest；不給＝讀 manifest，無＝不量不殺）")
    ap.add_argument("--max-tokens", type=int, default=None,
                    help="單輪 agent token 用量硬上限（覆蓋 manifest；不給＝讀 manifest，無＝不量不殺）")
    args = ap.parse_args(argv)

    man_path = pathlib.Path(args.manifest)
    man = G2Manifest.load(man_path)
    base = man_path.parent

    if args.dry_run:
        if args.json:
            print(json.dumps(dry_run_json(man), ensure_ascii=False, indent=1, default=str))
        else:
            print(dry_run_text(man))
        return 0

    # 真跑
    provider = args.provider or man.model.get("provider")
    model = args.model or man.model.get("model")
    if build is None:
        build = _default_build(provider, model, hooks=not args.no_hooks)
    if run is None:
        from vacant_network.adapters.run import run_agent
        run = run_agent
    out_root = pathlib.Path(args.out) if args.out else pathlib.Path(
        tempfile.mkdtemp(prefix="vacant-g2-"))

    res = run_g2_smoke(man, base, out_root, build, run, include_dirs=("data",),
                       max_tool_calls=args.max_tool_calls, max_tokens=args.max_tokens)
    p = write_result(res, out_root)

    if args.json:
        print(json.dumps(res.to_dict(), ensure_ascii=False, indent=1, default=str))
    else:
        print(dry_run_text(man).splitlines()[0])
        for c in res.cells:
            print(f"  {c['draft']} × {c['arm']:<11} stopped={c['stopped']:<11} "
                  f"sessions={c['cost'].get('calls')} model_calls={c['cost'].get('model_calls')} "
                  f"final={c['final_readable_status']} "
                  f"before_hidden={c['before_hidden'].get('n_correct')} "
                  f"after_hidden={c['after_hidden']}")
            if c["regressed"]:
                print(f"      REGRESSED: {', '.join(c['regressed'])}")
        t = res.to_dict()["totals"]
        tokens_s = str(t["tokens"]) if t["tokens"] is not None else "UNKNOWN（缺值不填 0）"
        mc_s = str(t["model_calls"]) if t["model_calls"] is not None else "UNKNOWN（缺值不填 0）"
        wall_s = str(t["wall_ms_total"]) if t["wall_ms_total"] is not None else "UNKNOWN"
        print(f"totals: cells={t['cells']}  model_calls={mc_s}  tokens={tokens_s}  wall_ms={wall_s}")
    print(f"result: {p}")
    # 冒煙口徑：只要管線跑通（每格都有 readable 判定）即 0；缺口修沒修好是**結果**，不是失敗
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
