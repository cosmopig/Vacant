#!/usr/bin/env python3
"""ops.e1.build_doc_chains — 從真實修訂教材目錄（realrev materials）建構 E1′ 文件多回合鏈。

這支在架構裡承重什麼
====================
讀取 realrev 教材目錄（`manifest.json` 含 sets／claims／truth／cycles，與 `sets/<set>/cycle_k/site/*.html`），
建構 E1′ 的文件更新任務鏈（**本實驗延伸，our extension**）：
- 初始 `report.md`：以 `template.md`（或 `claims[*].template_line`）填入 `truth[0]`，因此第 0 回合起始狀態
  **100% 全對**（量測的是「更新變動項目時能否保護原本已對的項目」）。
- 回合 ＝ cycles `1..K`（一般為 1..4）：每回合由本機來源伺服器（`ops/d2/source_server.py`）提供
  `cycle_k/site/` 的網頁；任務文字固定為：
  `"The website at <index URL> has been updated. Update report.md so every value matches the website now; change nothing else."`
- Oracle 受影響單元 ＝ 在週期 `k` 真值與週期 `k-1` 不同的範本行標籤前綴（`": "` 之前）。
- 真值表獨立存於 `hidden_truth.json`（不與公開鏈描述混放），供宿主端獨立評分使用。

誠實邊界（改碼請保留）
----------------------
- 起始 `report.md` 預填 `truth[0]` 是為了精確分離「保護已正確工作」的效應；現實工作中起始報告可能原本就有錯。
- 網頁快照取自公開維基百科真實修訂，但多回合 E1′ 任務鏈包裝屬於本實驗延伸（our extension）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.e1 import (
    DOC_CHAIN_SCHEMA,
    assert_ks1_clean,
    atomic_write_json,
    sha256_file,
    utc_now_iso,
)
from ops.e1.evaluate import evaluate_doc_report
from ops.e1.units import doc_line_prefix

DOC_TASK_TEMPLATE = (
    "The website at {index_url} has been updated. "
    "Update report.md so every value matches the website now; change nothing else."
)


def _render_initial_report(set_dir: pathlib.Path, set_obj: dict) -> str:
    """以 truth[0] 填滿範本行，產生全對的起始 report.md。"""
    truth0 = set_obj["truth"][0]
    claims = set_obj["claims"]
    by_pref: dict[str, str] = {}
    for c in claims:
        pref = doc_line_prefix(c["template_line"]) or c["template_line"].rstrip(": ").strip()
        by_pref[pref] = truth0[c["id"]]

    tpl_path = set_dir / "template.md"
    if tpl_path.is_file():
        out_lines: list[str] = []
        for ln in tpl_path.read_text(encoding="utf-8").splitlines():
            pref = doc_line_prefix(ln)
            if pref is not None and pref in by_pref:
                out_lines.append(f"{pref}: {by_pref[pref]}")
            else:
                out_lines.append(ln)
        return "\n".join(out_lines) + "\n"

    # 若教材沒有獨立 template.md，依 claims 的 template_line 建構
    lines = [f"# {set_obj.get('domain', set_obj['set'])} — verification report", ""]
    for c in claims:
        pref = doc_line_prefix(c["template_line"]) or c["template_line"].rstrip(": ").strip()
        lines.append(f"{pref}: {truth0[c['id']]}")
    return "\n".join(lines) + "\n"


def build_doc_chains(
    *,
    materials_dir: pathlib.Path,
    out_dir: pathlib.Path,
    sets: list[str] | None = None,
) -> dict:
    """從 realrev 教材目錄建構文件多回合鏈。"""
    mat = materials_dir.expanduser().resolve()
    manifest_path = mat / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"找不到 manifest.json：{manifest_path}")
    manifest_sha = sha256_file(manifest_path)

    sha_file = mat / "manifest.sha256"
    if sha_file.is_file():
        expected = sha_file.read_text(encoding="utf-8").strip().split()[0]
        if expected != manifest_sha:
            raise ValueError(f"manifest.sha256 不符：實際 {manifest_sha} != 預期 {expected}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    all_sets = manifest.get("sets") or []
    wanted = set(sets) if sets else None

    selected_sets = [s for s in all_sets if wanted is None or s["set"] in wanted]
    if wanted is not None:
        found = {s["set"] for s in selected_sets}
        missing = sorted(wanted - found)
        if missing:
            raise ValueError(f"manifest 裡找不到指定的 sets：{missing}")
    if not selected_sets:
        raise ValueError("沒有選到任何 doc set")

    out_dir.mkdir(parents=True, exist_ok=True)
    chains_summary: list[dict] = []

    for s in selected_sets:
        sid = str(s["set"])
        chain_id = f"doc_{sid}"
        set_dir = mat / "sets" / sid
        truth_list: list[dict] = s["truth"]
        claims: list[dict] = s["claims"]
        n_cycles = len(truth_list) - 1
        if n_cycles < 1:
            raise ValueError(f"set {sid} 週期數不足（需至少 2 個時間點）")

        # 確認 cycle_0..cycle_K 網站目錄皆存在
        pages = list(s.get("pages") or [])
        index_file = str(s.get("index") or "index.html")
        for k in range(len(truth_list)):
            site_dir = set_dir / f"cycle_{k}" / "site"
            if not site_dir.is_dir():
                raise FileNotFoundError(f"找不到網站目錄：{site_dir}")
            for pg in pages:
                if not (site_dir / pg).is_file():
                    raise FileNotFoundError(f"找不到頁面：{site_dir / pg}")

        initial_report = _render_initial_report(set_dir, s)
        # 確認第 0 回合起始報告 100% 通過獨立評分
        ev0 = evaluate_doc_report(initial_report, claims, truth_list[0])
        if not ev0["all_pass"]:
            raise RuntimeError(f"set {sid} 起始 report.md 未通過 truth[0] 驗證：{ev0}")

        claim_prefix = {
            c["id"]: (doc_line_prefix(c["template_line"]) or c["template_line"].rstrip(": ").strip())
            for c in claims
        }
        required_prefixes = [claim_prefix[c["id"]] for c in claims]

        rounds_public: list[dict] = []
        for k in range(1, len(truth_list)):
            changed_cids = [c["id"] for c in claims if truth_list[k][c["id"]] != truth_list[k - 1][c["id"]]]
            oracle_prefixes = [claim_prefix[cid] for cid in changed_cids]
            assert_ks1_clean(DOC_TASK_TEMPLATE.format(index_url="http://example.invalid/index.html"))
            rounds_public.append({
                "round": k,
                "cycle": k,
                "kind": "update",
                "task_text_template": DOC_TASK_TEMPLATE,
                "prev_site_dir": str((set_dir / f"cycle_{k - 1}" / "site").resolve()),
                "site_dir": str((set_dir / f"cycle_{k}" / "site").resolve()),
                "index_file": index_file,
                "pages": pages,
                "required_units": list(required_prefixes),
                "new_requirements": list(oracle_prefixes),
                "oracle_affected_units": list(oracle_prefixes),
                "oracle_changed_claim_ids": list(changed_cids),
            })

        cdir = out_dir / chain_id
        cdir.mkdir(parents=True, exist_ok=True)
        chain_obj = {
            "schema": DOC_CHAIN_SCHEMA,
            "chain_id": chain_id,
            "kind": "doc",
            "set_id": sid,
            "domain": s.get("domain"),
            "created_utc": utc_now_iso(),
            "extension_note": (
                "Derived from public real-revision materials; multi-round E1' chain packaging is our extension."
            ),
            "materials_dir": str(mat),
            "manifest_sha256": manifest_sha,
            "index_file": index_file,
            "pages": pages,
            "required_units": required_prefixes,
            "initial_report": initial_report,
            "rounds": rounds_public,
        }
        hidden_obj = {
            "schema": "vacant.e1.doc_hidden_truth/1",
            "chain_id": chain_id,
            "set_id": sid,
            "claims": claims,
            "truth": truth_list,
        }
        atomic_write_json(cdir / "chain.json", chain_obj)
        atomic_write_json(cdir / "hidden_truth.json", hidden_obj)
        chains_summary.append({
            "chain_id": chain_id,
            "set_id": sid,
            "path": str(cdir.resolve()),
            "n_claims": len(claims),
            "n_rounds": len(rounds_public),
            "changed_per_round": [len(r["oracle_affected_units"]) for r in rounds_public],
        })

    index_obj = {
        "schema": "vacant.e1.doc_chain_index/1",
        "kind": "doc",
        "created_utc": utc_now_iso(),
        "materials_dir": str(mat),
        "manifest_sha256": manifest_sha,
        "n_chains": len(chains_summary),
        "extension_note": (
            "Derived from public real-revision materials; multi-round E1' chain packaging is our extension."
        ),
        "chains": chains_summary,
    }
    atomic_write_json(out_dir / "index.json", index_obj)
    return index_obj


def main() -> int:
    ap = argparse.ArgumentParser(description="從 realrev 教材目錄建構 E1′ 文件多回合鏈（屬本實驗延伸）")
    ap.add_argument("--materials", type=pathlib.Path, required=True, help="realrev 教材目錄（含 manifest.json）")
    ap.add_argument("--sets", nargs="*", help="指定要建構的 set 名稱（支援空白或逗號分隔；省略＝全部）")
    ap.add_argument("--out", type=pathlib.Path, required=True, help="輸出目錄")
    args = ap.parse_args()

    set_list: list[str] | None = None
    if args.sets:
        set_list = []
        for item in args.sets:
            set_list.extend(x.strip() for x in item.split(",") if x.strip())

    idx = build_doc_chains(
        materials_dir=args.materials,
        out_dir=args.out,
        sets=set_list,
    )
    print(f"built {idx['n_chains']} doc chains in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
