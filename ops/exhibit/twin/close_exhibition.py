"""twin/close_exhibition — **展期結束即刪**：把每一位分身的 run 產物刪掉，只留收據。

## 這支在架構裡承重什麼

人類裁決（2026-09-24）：「wire log 等 run 產物：**展期內保留、展期結束即刪**，
收據鏈上的雜湊照留。」在這之前，撤回的人會被刪（`twinlink.withdraw` →
`twinagent.erase_run_artifacts`），**沒撤回的人永遠留著**——`wire_RUN-ON/*.req.bin`
逐字落盤（鐵律 3），裡面是觀眾貼回來的特質原文。

這一支是那句裁決的可執行版本。它**不在 loop 裡**、不會被任何排程觸發：
閉展是人按的，而且要打兩次展期名（`--exhibition X --yes-close X`）。

## 刪什麼、留什麼（與撤回同一份清單：`twinagent.erase_run_artifacts`）

| 落點 | 內容 | 閉展時 |
|---|---|---|
| `ws/<slug>/` | 活工作區（TRAITS.md、PLAN.md、成品） | **刪** |
| `doors/<slug>/` | 圍牆的門的 journal（VM 圍牆模式；逐字落盤） | **刪** |
| `runs/<slug>/wire_RUN-ON/` | request／response 原始位元組（**特質原文**） | **刪** |
| `runs/<slug>/_frozen_RUN-ON/` | 凍結快照 | **刪** |
| `runs/<slug>/agent_*.log`、`enclosure_stderr.log` | pi／圍牆印出來的字 | **刪** |
| `runs/<slug>/pi_cfg/`、`home/`、`run_RUN-ON.json`、`lifecycle_part.jsonl`、其餘 | 設定、摘要 | **刪** |
| `runs/<slug>/receipts_RUN-ON.ndjson`＋`.pub.json`＋`rows.jsonl` | 只有雜湊與計數 | **留**（驗章器要它們，見 C 線裁決 §六） |

⇒ 閉展之後 `work_root` 底下**只准剩**每位分身的那三個收據檔。最後一步是整棵樹再掃一次
（`residue`）：多出任何一個檔（例如有人把 wire log 複製到別處），抹除證明就寫
**不乾淨**，不是「刪了我們知道的那幾個就回綠」。

## 抹除證明（`<庫名>.close_<展期名>.jsonl`，append-only；每一位也上 twinstore 鏈）

每一位分身一列：`twin_id`（公開別名，**不寫 `sub_id`**——那是撤回的能力憑證）、
刪了哪幾類（類別名、檔數、位元組數）、留了哪幾個收據檔、拿不掉的是什麼（`problems`）、
收據在刪完之後**重新驗章**的結果。最後一列是總結（`kind="summary"`）。

twinstore 鏈上每位分身多一列 `note`（`twinlink_event="exhibition_closed"`，只有類別
與計數）。撤回過而且早就刪乾淨的人**不重複寫**（`action="already_erased"`）；
同一個展期名重跑一次也不重複寫（`action="already_closed"`）。

## 不在這一支範圍內的（**照實寫進抹除證明**，不是安靜略過）

* **檔案庫（twinvault）裡的卡片原文與分身文字**：人類裁決只講 run 產物。沒撤回的人的
  原文閉展後仍在檔案庫裡——`summary.vault_plaintext_subjects` 寫出還有幾位，那一步要
  人類另外決定（`twinlink withdraw` 逐位刪，或另一份裁決）。
* **lifecycle 事件檔與錄影**：設計上不帶內容（`lifecycle` 誠實邊界 3、
  `DECISION_20260924_TWIN_AGENT_RUN.md` §二）。這一支**量**它：拿每一位還在檔案庫裡的人
  的原文去掃事件檔與錄影（`content_scan`），命中就寫不乾淨。撤回過的人原文已刪、掃不到——
  那一部分是「沒量到」，照寫。
* **雲端那一份**、**systemd journal**：刪不到（`twinvault` 誠實邊界 2）。

用法：
    python3 ops/exhibit/twin/close_exhibition.py --db <庫> --exhibition 2026-10-A --dry-run
    python3 ops/exhibit/twin/close_exhibition.py --db <庫> --exhibition 2026-10-A \\
        --yes-close 2026-10-A
退出碼：0 乾淨；1 不乾淨（有拿不掉的、有殘留、收據驗不過、事件檔掃到原文）；2 用法／確認錯。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
from typing import Any

HERE = pathlib.Path(__file__).resolve()
TWIN = HERE.parent
REPO = TWIN.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ops.exhibit.twin import twinagent  # noqa: E402
from ops.exhibit.twin.twinstore import (  # noqa: E402
    KIND_NOTE, TwinStore)

SCHEMA = "vacant.twin.close/1"
CLOSE_EVENT = "exhibition_closed"
_NAME = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _tree(p: pathlib.Path) -> tuple[int, int]:
    return twinagent._tree_size(p)                       # noqa: SLF001


def _closed_before(store: TwinStore, sub_id: str, exhibition: str) -> bool:
    for e in store.events(sub_id=sub_id, kind=KIND_NOTE):
        pl = e.get("payload") or {}
        if pl.get("twinlink_event") == CLOSE_EVENT and pl.get("exhibition") == exhibition:
            return True
    return False


def plan_one(work_root: pathlib.Path, sub_id: str) -> list[dict[str, Any]]:
    """這一位**會被刪**的東西（類別、檔數、位元組）——dry-run 用，不動任何檔。"""
    ws, rd = twinagent.paths_for(work_root, sub_id)
    door = work_root / "doors" / twinagent.slug_for(sub_id)
    out: list[dict[str, Any]] = []
    if ws.exists():
        n, b = _tree(ws)
        out.append({"what": "workspace", "files": n, "bytes": b})
    if door.exists():
        n, b = _tree(door)
        out.append({"what": "door_journal", "files": n, "bytes": b})
    if rd.exists():
        for c in sorted(rd.iterdir()):
            if c.name in twinagent.KEEP_ON_ERASE and c.is_file():
                continue
            n, b = _tree(c)
            out.append({"what": c.name, "files": n, "bytes": b})
    return out


def residue(work_root: pathlib.Path) -> list[dict[str, Any]]:
    """整棵 `work_root` 掃一次：**只准剩** `runs/<slug>/{收據三檔}`。其餘每一個檔都是殘留。"""
    left: list[dict[str, Any]] = []
    if not work_root.exists():
        return left
    for p in sorted(work_root.rglob("*")):
        if not p.is_file() and not p.is_symlink():
            continue
        rel = p.relative_to(work_root)
        parts = rel.parts
        if (len(parts) == 3 and parts[0] == "runs"
                and parts[2] in twinagent.KEEP_ON_ERASE):
            continue
        cat = ("wire_log" if any(x.startswith("wire_") for x in parts) or
               p.suffix == ".bin" else parts[0])
        try:
            size = p.lstat().st_size
        except OSError:
            size = None
        left.append({"path": str(rel), "category": cat, "bytes": size})
    return left


def content_scan(store: TwinStore, files: list[pathlib.Path]) -> dict[str, Any]:
    """拿檔案庫裡還在的原文去掃事件檔／錄影。**回的只有命中數與檔名，不回命中的字。**"""
    from ops.exhibit.twin import twinlink
    blobs: dict[str, bytes] = {}
    for f in files:
        try:
            blobs[str(f)] = f.read_bytes()
        except OSError:
            pass
    hits: dict[str, int] = {}
    scanned = 0
    unscannable = 0
    for sid in store.sub_ids():
        secrets = twinlink._subject_secrets(store, sid)        # noqa: SLF001
        if not secrets:
            unscannable += 1          # 撤回過（原文已刪）或本來就沒有 ⇒ 沒量到
            continue
        scanned += 1
        enc = [s.encode("utf-8") for s in secrets]
        for name, b in blobs.items():
            if any(s in b for s in enc):
                hits[name] = hits.get(name, 0) + 1
    return {"files": sorted(blobs), "subjects_scanned": scanned,
            "subjects_unscannable": unscannable,
            "hits_by_file": hits, "clean": not hits,
            "note": ("命中＝那個檔裡出現了某位觀眾的原文字串（只記檔名與人數）。"
                     "`subjects_unscannable` 是檔案庫裡已經沒有原文的人——對他們是**沒量到**")}


def _orphan(work_root: pathlib.Path, slug: str, exhibition: str, *,
            dry_run: bool) -> dict[str, Any]:
    """庫裡對不到人的 slug：同一份刪除規則（run-dir 留收據三檔，其餘全刪）。"""
    import shutil
    items: list[dict[str, Any]] = []
    problems: list[str] = []
    for sub in ("ws", "runs", "doors"):
        p = work_root / sub / slug
        if not p.exists():
            continue
        targets = ([c for c in sorted(p.iterdir())
                    if not (c.name in twinagent.KEEP_ON_ERASE and c.is_file())]
                   if sub == "runs" else [p])
        for t in targets:
            n, b = _tree(t)
            items.append({"what": f"{sub}/{t.name}" if sub == "runs" else sub,
                          "files": n, "bytes": b})
            if dry_run:
                continue
            try:
                if t.is_dir() and not t.is_symlink():
                    shutil.rmtree(t)
                else:
                    t.unlink()
            except OSError as exc:
                problems.append(f"{sub}: {type(exc).__name__}")
    return {"schema": SCHEMA, "kind": "orphan", "exhibition": exhibition, "slug": slug,
            "action": "would_erase" if dry_run else "erased",
            ("would_erase" if dry_run else "erased"): items,
            "files_erased": 0 if dry_run else sum(i["files"] for i in items),
            "bytes_erased": 0 if dry_run else sum(i["bytes"] for i in items),
            "problems": problems, "clean": not problems}


def close(db: pathlib.Path, exhibition: str, *, dry_run: bool,
          work_root: pathlib.Path | None = None,
          events: list[pathlib.Path] | None = None) -> dict[str, Any]:
    from vacant_network.vrun import verify_receipts as vrr
    store = TwinStore(db)
    work_root = pathlib.Path(work_root or twinagent.default_work_root(db))
    events = list(events or [])
    proof_path = db.parent / f"{db.stem}.close_{exhibition}.jsonl"
    rows: list[dict[str, Any]] = []
    known_slugs: set[str] = set()
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        scan = content_scan(store, [p for p in events if p.is_file()])
        vault_left = 0
        for sid in store.sub_ids():
            slug = twinagent.slug_for(sid)
            known_slugs.add(slug)
            cur = store.current(sid) or {}
            status = cur.get("status")
            if store.vault.open_card(sid) or store.vault.open_twin(sid):
                vault_left += 1
            row: dict[str, Any] = {
                "schema": SCHEMA, "kind": "twin", "exhibition": exhibition,
                "twin_id": twinagent.public_twin_id(sid), "status": status}
            planned = plan_one(work_root, sid)
            if not planned:
                row["action"] = ("already_closed" if _closed_before(store, sid, exhibition)
                                 else "already_erased" if status in ("withdrawn", "erased")
                                 else "nothing_to_erase")
                row.update(erased=[], kept_hash_only=[], problems=[])
            elif dry_run:
                row.update(action="would_erase", would_erase=planned,
                           problems=[], kept_hash_only=[])
            else:
                rec = twinagent.erase_run_artifacts(work_root, sid)
                row.update(action="erased", erased=rec["erased"],
                           kept_hash_only=rec["kept_hash_only"],
                           problems=rec["problems"])
            _, rd = twinagent.paths_for(work_root, sid)
            if rd.exists() and any(rd.glob("receipts_*.ndjson")):
                row["receipts_after"] = [r.get("verdict") for r in vrr.verify_run(rd)]
            else:
                row["receipts_after"] = None     # 這一位沒有收據（沒跑過／infra_void）
            row["files_erased"] = sum(x["files"] for x in row.get("erased") or [])
            row["bytes_erased"] = sum(x["bytes"] for x in row.get("erased") or [])
            row["clean"] = (not row["problems"]
                            and row["receipts_after"] in (None, ["OK"])
                            and not (not dry_run and plan_one(work_root, sid)))
            if not dry_run and row["action"] == "erased":
                # 上鏈：只有類別與計數（這一列會跟著鏈一直留著）
                store.append(KIND_NOTE, sid, {
                    "twinlink_event": CLOSE_EVENT, "exhibition": exhibition,
                    "run_artifacts_erased": row["erased"],
                    "run_artifacts_kept_hash_only": row["kept_hash_only"],
                    "run_artifacts_problems": row["problems"],
                    "receipts_after": row["receipts_after"], "at": now,
                }, source="local:close_exhibition")
            rows.append(row)
        # 庫裡沒有、但 work_root 裡有的 slug（探針、上一個庫留下來的）⇒ 一樣刪、一樣記
        for sub in ("ws", "runs", "doors"):
            base = work_root / sub
            if not base.is_dir():
                continue
            for d in sorted(base.iterdir()):
                if d.name in known_slugs:
                    continue
                known_slugs.add(d.name)
                rows.append(_orphan(work_root, d.name, exhibition, dry_run=dry_run))
        left = residue(work_root) if not dry_run else []
        receipts = [r for r in rows if r.get("receipts_after")]
        chain = store.verify()
        summary = {
            "schema": SCHEMA, "kind": "summary", "exhibition": exhibition,
            "at": now, "dry_run": dry_run, "work_root": str(work_root),
            "twins": sum(1 for r in rows if r["kind"] == "twin"),
            "orphans": sum(1 for r in rows if r["kind"] == "orphan"),
            "actions": {a: sum(1 for r in rows if r.get("action") == a)
                        for a in sorted({r.get("action") for r in rows})},
            "files_erased": sum(r.get("files_erased") or 0 for r in rows),
            "bytes_erased": sum(r.get("bytes_erased") or 0 for r in rows),
            "would_erase_files": sum(x["files"] for r in rows
                                     for x in (r.get("would_erase") or [])),
            "would_erase_bytes": sum(x["bytes"] for r in rows
                                     for x in (r.get("would_erase") or [])),
            "problems": [p for r in rows for p in (r.get("problems") or [])],
            "residue": left,
            "receipts_verified": sum(1 for r in receipts if r["receipts_after"] == ["OK"]),
            "receipts_failed": sum(1 for r in receipts if r["receipts_after"] != ["OK"]),
            "twinstore_chain": {"ok": chain.get("ok"), "checked": chain.get("checked")},
            "content_scan": scan,
            # 不在範圍內的，照寫（見檔頭）
            "vault_plaintext_subjects": vault_left,
            "not_erased_by_design": ["receipts_RUN-ON.ndjson", "receipts_RUN-ON.pub.json",
                                     "rows.jsonl", "twinstore 鏈（append-only）",
                                     "lifecycle 事件檔（不帶內容）"],
            "cannot_reach": ["雲端那一份（沒有 delete 路由）", "systemd journal"],
        }
        summary["clean"] = (not summary["problems"] and not left
                            and summary["receipts_failed"] == 0
                            and chain.get("ok") is True and scan["clean"]
                            and all(r.get("clean", True) for r in rows))
    finally:
        store.close()
    if not dry_run:
        with proof_path.open("a", encoding="utf-8") as f:
            for r in rows + [summary]:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        summary["proof_path"] = str(proof_path)
    return {"rows": rows, "summary": summary}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="展期結束即刪：刪 run 產物、只留收據、寫抹除證明")
    ap.add_argument("--db", required=True, help="twinstore.sqlite3（loop 用的那一份）")
    ap.add_argument("--exhibition", required=True, help="展期名（寫進抹除證明與鏈上）")
    ap.add_argument("--work-root", default=None,
                    help="預設 VACANT_TWIN_AGENTRUNS，否則 <庫名>.agentruns/")
    ap.add_argument("--events", action="append", default=[],
                    help="要掃原文的 lifecycle 事件檔／錄影（可給多次；預設庫旁邊的 "
                         "twin_lifecycle.jsonl 與 VACANT_EVENTS）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="只列出會刪什麼，不刪")
    g.add_argument("--yes-close", default=None, metavar="展期名",
                   help="真的刪。**要跟 --exhibition 一字不差**")
    a = ap.parse_args(argv)
    if not _NAME.match(a.exhibition):
        print("展期名只准英數與 ._-（它會變成檔名）", file=sys.stderr)
        return 2
    if a.yes_close is not None and a.yes_close != a.exhibition:
        print(f"--yes-close {a.yes_close!r} 跟 --exhibition {a.exhibition!r} 不一樣 ⇒ 不刪。",
              file=sys.stderr)
        return 2
    db = pathlib.Path(a.db)
    if not db.is_file():
        print(f"庫不在：{db}（不會替你建一個空庫再回報「刪乾淨了」）", file=sys.stderr)
        return 2
    events = [pathlib.Path(e) for e in a.events]
    if not events:
        cand = {twinagent.default_events_path(db)}
        if os.environ.get("VACANT_EVENTS"):
            cand.add(pathlib.Path(os.environ["VACANT_EVENTS"]))
        events = sorted(cand)
    out = close(db, a.exhibition, dry_run=a.dry_run,
                work_root=pathlib.Path(a.work_root) if a.work_root else None,
                events=events)
    print(json.dumps(out["summary"], ensure_ascii=False, indent=2))
    if a.dry_run:
        for r in out["rows"]:
            if r.get("action") == "would_erase":
                print(json.dumps({k: r.get(k) for k in ("twin_id", "slug", "status",
                                                        "would_erase", "items")},
                                 ensure_ascii=False))
        return 0
    return 0 if out["summary"]["clean"] else 1


if __name__ == "__main__":
    sys.exit(main())
