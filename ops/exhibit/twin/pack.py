"""twin/pack — 把一批 run 目錄收成展件的資料包（`twin_pack.json`）。

## 這支在架構裡承重什麼

展件那一頁必須離線、`file://` 直開、零外部資源（CLAUDE.md §硬約束 2／3），
所以資料只能**內嵌**。本支就是內嵌前的那一步：讀 `run_twin.py` 落下來的
run 目錄，收成一份 JSON。

它**只搬運與推導**，不算任何頁面上要顯示的判決——判決由頁面自己從內嵌的
簽章鏈重算（形狀照 `ops/gain/replay/build_multiparty_viewer.py` 的同一條紀律）。

## 證據等級是**推**出來的，不是宣告的

```
requests_seen == 0                      → L-none    （這一格沒有模型參與）
requests_seen  > 0 且有宣告 L-real/L-fake → 宣告值
requests_seen  > 0 但沒有宣告             → L-unknown（頁面會照實說「沒有紀錄」）
```

第一條是 **fail-closed 且宣告蓋不過去**：`run_twin.py --evidence L-real` 配上
一個 `requests_seen == 0` 的 run，出來還是 `L-none`。這一條是可執行的，
因為「畫面上必須逐格標對哪一格是真跑」正是展場版的鐵律 5。

旁邊一律附上**推導所依據的原始欄位**（`requests_seen`、wire 裡的 `model`、
`wire_by_protocol`），讓看的人可以自己判斷標籤對不對，而不是只能相信它。

## 誠實邊界

1. `model_id` 是從 **proxy 逐字落盤的 request body** 讀出來的，不是設定檔寫的。
   但它只證明「agent 要求了這個模型 id」，不證明上游真的是那個模型
   ——一個假上游可以對任何 model id 回一句話。所以 L-real／L-fake 的界線
   仍然由**上游是什麼**決定，而那件事 run 目錄裡沒有、只能靠宣告。這是殘餘風險。
2. 本支不讀 `hidden/`，一個 byte 都不讀。展件上不會出現隱藏測資（V/GT 紅線）。
3. `visible` 逐條搬過來，包含失敗訊息——那是 agent 自己也看得到的可見測資，
   不是隱藏測資。
4. **`visible` 是最後一次嘗試的閘門結果**，與 `accepted` 同一次；每一次各自的
   結果在 `attempts[*].visible`。舊版讀的是第 1 次那一份（`launcher.py:481`
   的檔名規則），與最後一次的 `accepted` 擺在一起 ⇒ 一格「第 1 次沒過、
   第 3 次過」的 run 在資料上會長成「驗收沒過 ＋ 收下了」。
   1 次嘗試的格剛好相等所以看不出來，3 次嘗試的格就說謊。見 `attempts_of`。

用法：
    python3 ops/exhibit/twin/pack.py --runs runs/twin_fixture_20260919 \\
        --out ops/exhibit/twin/twin_pack.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import roster as rosterlib  # noqa: E402

BANK = REPO / "ops" / "gain" / "r535" / "bank"
ARM = "RUN-ON"

#: 證據等級的說明。頁面直接印這幾句，不自己另外寫一套措辭。
EVIDENCE_TEXT = {
    "L-real": "真模型真跑：模型通道經過 Vacant（requests_seen > 0），上游宣告為真模型端點。",
    "L-fake": "假上游：通道與閘門是真的跑過的，但站在模型位置上的是一個測試用的假上游。"
              "這一格不能讀成模型能力。",
    "L-none": "這一格沒有模型參與（requests_seen = 0）。驗收與收據是真的跑過的，"
              "交出來的東西由一支腳本化的程式寫出來。",
    "L-unknown": "這一格有模型通訊（requests_seen > 0），但上游是什麼沒有留下紀錄。"
                 "不要當成真模型證據。",
}


def _read_json(p: pathlib.Path):
    return json.loads(p.read_text(encoding="utf-8"))


def model_from_wire(run_dir: pathlib.Path) -> str:
    """從 proxy 逐字落盤的第一通 request body 讀 `model`。讀不到回空字串。

    刻意讀 `.req.bin` 而不是任何摘要：那是 agent 真的送出去的位元組。
    """
    idx = run_dir / f"wire_{ARM}" / "index.jsonl"
    if not idx.exists():
        return ""
    for line in idx.read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        for key in ("req_file", "request_file", "req", "call"):
            name = rec.get(key)
            if not isinstance(name, str):
                continue
            cand = run_dir / f"wire_{ARM}" / name
            if not cand.exists():
                cand = run_dir / f"wire_{ARM}" / f"{name}.req.bin"
            if cand.exists():
                try:
                    body = json.loads(cand.read_bytes().decode("utf-8", "replace"))
                except ValueError:
                    continue
                m = body.get("model")
                if isinstance(m, str) and m:
                    return m
    # index 的欄位名不認得就直接掃檔案（欄位名漂掉不該讓證據消失）
    for cand in sorted((run_dir / f"wire_{ARM}").glob("*.req.bin")):
        try:
            body = json.loads(cand.read_bytes().decode("utf-8", "replace"))
        except ValueError:
            continue
        m = body.get("model")
        if isinstance(m, str) and m:
            return m
    return ""


def evidence_level(*, requests_seen: int, declared: str) -> str:
    """fail-closed：沒有 request 就只能是 L-none，宣告蓋不過資料。"""
    if requests_seen <= 0:
        return "L-none"
    if declared in ("L-real", "L-fake"):
        return declared
    return "L-unknown"


#: 單一檔案搬進展件的上限。超過就只留 hash——頁面不是檔案瀏覽器。
MAX_FILE_BYTES = 16 * 1024


def strip_scheme(url: str) -> str:
    """把 `scheme://` 拿掉，只留 host:port。

    理由不是美觀：展件那一頁的離線紅線會掃整份檔案找 URL 形狀的字串
    （`tests/test_twin_viewer.py`，與收據牆共用同一份清單）。一個沒有 scheme
    的 `host:port` 字串沒有辦法被當成資源去載入，而觀眾要看的資訊一個字沒少。
    """
    for sep in ("://",):
        if sep in url:
            return url.split(sep, 1)[1]
    return url


def redact_paths(text: str, run_dir: pathlib.Path) -> str:
    """把建置這台機器的絕對路徑換成佔位符。

    驗收的失敗訊息裡會帶著凍結快照的絕對路徑（`ImportError: … from 'solution'
    (/Users/…/_frozen_RUN-ON/solution.py)`）。那串路徑對觀眾零資訊，卻把建置
    機器的目錄結構印在展場螢幕上。**只換前綴，不動訊息其他任何一個字**——
    `check_02_mul` 為什麼沒過，一個字都沒少。

    ⚠ 2026-09-19：只比對「**現在的** `run_dir`」是不夠的。run 目錄是落盤資料，
    它會被搬、會被另一個 worktree 重新 pack，而訊息裡那串路徑是**當初跑的時候**
    那一台／那一個目錄的。兩者不相等 ⇒ 前綴比對整個失效 ⇒ 建置機器的路徑
    直接印上展場螢幕。實際發生過：換一個 worktree 重跑 `pack.py`，
    `/Users/…/.claude/worktrees/agent-a333…/` 就漏進 `twin_pack.json`。
    ⇒ 前綴比對之後再補一道**與位置無關**的清洗：任何以 `_frozen_<ARM>` 收尾的
      絕對路徑一律換掉，不管它現在在哪。守門的是
      `tests/test_twin_fidelity.py::test_pack_has_no_absolute_build_paths`。
    """
    if not text:
        return text
    out = text.replace(str(run_dir / f"_frozen_{ARM}"), "<凍結快照>")
    out = out.replace(str(run_dir), "<run 目錄>")
    # 與位置無關的第二道：`/任何/地方/_frozen_RUN-ON[_aN]` → `<凍結快照>`
    out = re.sub(r"/[^\s'\"()\[\]]*/_frozen_" + re.escape(ARM) + r"(_a\d+)?",
                 "<凍結快照>", out)
    out = out.replace(str(REPO), "<repo>")
    return out


def delivery_of(run_dir: pathlib.Path, ws_end_sha256: str,
                attempts_used: int | None = None) -> dict:
    """它**交出來的那份東西**——凍結快照裡的檔案，逐檔帶內容與 sha256。

    為什麼要帶內容：展件的靈魂是「觀眾看得到它想交、但被擋下來」。
    只給一個 hash 看不到那件事。

    為什麼可以帶：`ws_end_sha256` 已經在簽章 payload 裡，而樹雜湊的演算法
    （`vacant/vrun/wshash.py`）是「排序過的 {path, sha256, exec} 清單的
    canonical JSON 的 sha256」——頁面可以自己從這些內容重算一次，
    算出來不等於鏈上那個值就代表這一頁在說謊。`recomputable` 就是這件事
    做不做得到的誠實旗標：任何一個檔案的位元組不是 UTF-8 往返不變，
    就整格標成不可重算，而不是算一個看起來很像的值。
    """
    # ⚠ **要讀的是最後一次嘗試的快照，不是第一次。**
    #   `root_claimed` 用的是 `summary["ws_end_sha256"]`，而那是**最後一次**
    #   凍結的樹雜湊。舊版永遠讀 `_frozen_{ARM}`（＝第 1 次）：
    #   單次嘗試的格剛好相等所以看不出來，**三次嘗試的格就對不上**
    #   ⇒ 2026-09-19 的 18 格真跑上，N4「交付物樹雜湊＝鏈上的 ws_end_sha256」
    #   只過 9/18，**而失敗的正好是 9 格拒交**——展件的靈魂那一半。
    #
    #   ⚠ 順帶一個對展件有利的後果：最後一次的工作區裡**有 `VACANT_FEEDBACK.md`**
    #   （`revise` 在每次判定之後寫的）。讀對快照之後，觀眾會看到那個檔
    #   **就躺在那裡**，而 `solution.py` 三次一模一樣——
    #   R535 那個「看見了檔名、沒有讀」的發現，變成畫面上看得到的東西。
    n = attempts_used if isinstance(attempts_used, int) and attempts_used > 1 else None
    frozen = run_dir / (f"_frozen_{ARM}_a{n}" if n else f"_frozen_{ARM}")
    if not frozen.is_dir():
        # 退回第 1 次那份，但**不准假裝算得出來**——
        # 算不回 `root_claimed` 的話 `recomputable` 會是 False，頁面照實說。
        frozen = run_dir / f"_frozen_{ARM}"
    files: list[dict] = []
    recomputable = frozen.is_dir()
    if frozen.is_dir():
        from vacant.vrun import wshash
        for leaf in wshash.tree_leaves(frozen):
            item = {"path": leaf["path"], "sha256": leaf["sha256"],
                    "exec": bool(leaf.get("exec")), "text": None, "truncated": False}
            if leaf.get("symlink") or leaf.get("special"):
                recomputable = False
                item["note"] = "symlink／特殊檔，本頁不重算"
                files.append(item)
                continue
            raw = (frozen / leaf["path"]).read_bytes()
            item["bytes_n"] = len(raw)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                recomputable = False
                item["note"] = "不是 UTF-8，內容不進頁面"
                files.append(item)
                continue
            if text.encode("utf-8") != raw:
                recomputable = False
                item["note"] = "UTF-8 往返不相等，內容不進頁面"
                files.append(item)
                continue
            if len(raw) > MAX_FILE_BYTES:
                item["truncated"] = True
                recomputable = False
                item["text"] = text[:2000]
                item["note"] = f"檔案 {len(raw)} bytes 超過 {MAX_FILE_BYTES}，只留開頭"
            else:
                item["text"] = text
            files.append(item)
    return {
        "root_claimed": ws_end_sha256,
        "algo": "sha256(canonical_json(sorted[{path,sha256,exec}])) — vacant/vrun/wshash.py",
        "recomputable": recomputable,
        "files": files,
    }


def task_meta(task_id: str) -> dict:
    p = BANK / task_id / "meta.json"
    if not p.exists():
        return {}
    m = _read_json(p)
    # 只搬展件用得到的欄位。`hidden_n` 是數字不是內容；`required_names` 是
    # **揭曉**用的（觀眾看完那一格才知道客戶要的介面叫什麼），不是隱藏測資。
    #
    # ⚠ `meta.json` 的 `honesty` **刻意不搬**。它的內容是對的（「擋得住已知壞解
    # ≠ 涵蓋真需求」），但字面上有展場口徑紅線擋掉的詞；而頁面本來就沒有渲染它，
    # 留在資料裡只會讓整頁被紅線擋下來卻沒有任何觀眾讀得到。
    # 同一條界線由頁面自己的「這一頁證明不了什麼」那一列用展場措辭講出來——
    # **界線沒有消失，只是換成觀眾讀得懂的話**。
    return {k: m[k] for k in ("title", "stratum", "trap", "required_names",
                              "visible_n", "hidden_n") if k in m}


def visible_cases(visible: dict, run_dir: pathlib.Path) -> list[dict]:
    """可見驗收的逐條結果（含失敗訊息）。隱藏測資一個 byte 都不讀。"""
    cases = []
    for f in visible.get("files", []):
        for c in f.get("cases", []):
            cases.append({"case": c.get("case"), "ok": bool(c.get("ok")),
                          "kind": c.get("kind"),
                          "message": redact_paths(c.get("message", ""), run_dir),
                          "where": redact_paths(c.get("where") or "", run_dir) or None})
    return cases


def attempts_of(run_dir: pathlib.Path, summary: dict) -> list[dict]:
    """每一次嘗試一筆，**含那一次自己的閘門結果**。

    ⚠ 2026-09-19 查出來的錯：`visible_{ARM}.json` 是**第 1 次嘗試**的結果
    （`launcher.py:481` 的 `suffix = "" if attempt == 1 else f"_a{attempt}"`），
    而 `summary["accepted"]` 是**最後一次**的。舊版 `pack_cell` 把前者當成
    「這一格的閘門結果」、把後者當成「這一格的裁決」擺在一起
    ⇒ 一格「第 1 次沒過、第 3 次過」的 run，資料上會長成
    **「驗收沒過 ＋ 收下了」**——那正是「收下了，其實漏出」那句話的形狀。
    單次嘗試的格剛好相等所以看不出來（fixture 全是 1 次），**三次嘗試的格就說謊**。
    形狀與 `delivery_of` 的同一個坑（讀錯快照）一模一樣。

    ⇒ 這裡逐次讀回各自的 `visible_{ARM}{suffix}.json`，
      `pack_cell` 的 `visible` 改成**最後一次**那一份（與 `accepted` 同一次）。
    """
    out: list[dict] = []
    for rec in summary.get("attempts", []):
        n = int(rec.get("attempt") or 0)
        vp = run_dir / f"visible_{ARM}{'' if n <= 1 else f'_a{n}'}.json"
        vis = _read_json(vp) if vp.exists() else {}
        out.append({
            "attempt": n,
            "requests_seen": int(rec.get("requests_seen") or 0),
            "agent_rc": rec.get("agent_rc"),
            "accepted": rec.get("accepted"),
            "stop_reason": rec.get("stop_reason"),
            # 回饋真的進了幾個位元組（第 1 次恆為 0＝與「沒有 Vacant」逐位元相同）
            "feedback_delivery": rec.get("feedback_delivery"),
            "feedback_in_prompt_bytes": rec.get("feedback_in_prompt_bytes"),
            "reset": rec.get("reset"),
            "ws_end_sha256": rec.get("ws_end_sha256"),
            "visible": ({"passed": vis.get("passed"), "total": vis.get("total"),
                         "all_pass": bool(vis.get("all_pass")),
                         "cases": visible_cases(vis, run_dir)} if vis else None),
        })
    return out


def pack_cell(run_dir: pathlib.Path) -> dict:
    meta = _read_json(run_dir / "twin_cell.json")
    summary = _read_json(run_dir / f"run_{ARM}.json")
    chain_text = (run_dir / f"receipts_{ARM}.ndjson").read_text(encoding="utf-8")
    pub = _read_json(run_dir / f"receipts_{ARM}.pub.json")

    attempts = attempts_of(run_dir, summary)
    # `visible` ＝ **最後一次**嘗試那一份（與 `accepted` 是同一次）。
    n_last = int(summary.get("attempts_used") or 1)
    vlast = run_dir / f"visible_{ARM}{'' if n_last <= 1 else f'_a{n_last}'}.json"
    visible = _read_json(vlast) if vlast.exists() else _read_json(
        run_dir / f"visible_{ARM}.json")

    requests_seen = int(summary.get("requests_seen") or 0)
    model_id = model_from_wire(run_dir)
    level = evidence_level(requests_seen=requests_seen,
                           declared=meta.get("declared_evidence", ""))

    cases = visible_cases(visible, run_dir)

    return {
        "cell_id": meta["cell_id"],
        "resident": meta["resident"],
        "task_id": meta["task_id"],
        "explicit": bool(meta["explicit"]),
        "task": task_meta(meta["task_id"]),
        "exit_code": int(meta["exit_code"]),
        "accepted": summary.get("accepted"),
        "refused": bool(summary.get("refused")),
        "stop_reason": summary.get("stop_reason"),
        "attempts_used": summary.get("attempts_used"),
        "attempts": attempts,
        "retry": summary.get("retry"),
        "requests_seen": requests_seen,
        "wire_by_protocol": summary.get("wire_by_protocol") or {},
        "model_id": model_id,
        "declared_upstream": strip_scheme(meta.get("declared_upstream", "")),
        "declared_evidence": meta.get("declared_evidence", ""),
        "evidence": level,
        "ws_start_sha256": summary.get("ws_start_sha256"),
        "ws_end_sha256": summary.get("ws_end_sha256"),
        "verdict_sha256": summary.get("verdict_sha256"),
        "sandbox": (summary.get("sandbox") or {}).get("backend"),
        # ⚠ 這是**最後一次**嘗試的閘門結果（與 `accepted` 同一次）。
        #   每一次各自的結果在 `attempts[*].visible`。
        "visible": {"passed": visible.get("passed"), "total": visible.get("total"),
                    "all_pass": bool(visible.get("all_pass")), "cases": cases,
                    "attempt": n_last},
        "delivery": delivery_of(run_dir, summary.get("ws_end_sha256") or "",
                                summary.get("attempts_used")),
        "chain": [ln for ln in chain_text.split("\n") if ln.strip()],
        "pub": {"vacant_id": pub["vacant_id"], "pub_hex": pub["pub_hex"]},
    }


def build(runs_root: pathlib.Path) -> dict:
    idx = _read_json(runs_root / "twin_index.json")
    cells = []
    for m in idx["cells"]:
        run_dir = runs_root / "runs" / m["cell_id"]
        if not run_dir.is_dir():
            raise SystemExit(f"run 目錄不見了：{run_dir}")
        cells.append(pack_cell(run_dir))
    cells.sort(key=lambda c: c["cell_id"])

    by_resident: dict[str, list[str]] = {}
    for c in cells:
        by_resident.setdefault(c["resident"], []).append(c["cell_id"])

    residents = []
    for r in rosterlib.default_roster():
        if r.codename not in by_resident:
            continue
        j = r.to_json()
        j["cells"] = by_resident[r.codename]
        j["specialty"] = rosterlib.specialty(r)
        residents.append(j)

    consent_dir = HERE.parent / "consent_demo"
    consent = None
    if (consent_dir / "chain.ndjson").exists():
        consent = {
            "chain": [ln for ln in (consent_dir / "chain.ndjson")
                      .read_text(encoding="utf-8").split("\n") if ln.strip()],
            "pub": _read_json(consent_dir / "chain.pub.json"),
            "manifest": _read_json(consent_dir / "manifest.json"),
        }

    levels: dict[str, int] = {}
    for c in cells:
        levels[c["evidence"]] = levels.get(c["evidence"], 0) + 1

    return {
        "v": 1,
        "source": {
            "runs": str(runs_root.relative_to(REPO)) if runs_root.is_relative_to(REPO)
                    else str(runs_root),
            "arm": ARM,
            "ruler": "vacant/vrun/verify_receipts.py（沒有第二把尺）",
            "note": "每一格都是 `vacant run` 當時落盤的原值，未經加工。",
        },
        "evidence_text": EVIDENCE_TEXT,
        "evidence_counts": dict(sorted(levels.items())),
        "delivered": sum(1 for c in cells if c["exit_code"] == 0),
        "refused": sum(1 for c in cells if c["exit_code"] == 20),
        "void": sum(1 for c in cells if c["exit_code"] not in (0, 20)),
        "residents": residents,
        "cells": cells,
        "consent": consent,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="把 twin run 目錄收成展件資料包")
    ap.add_argument("--runs", required=True, help="run_twin.py 的 --out 根目錄")
    ap.add_argument("--out", default=str(HERE.parent / "twin_pack.json"))
    a = ap.parse_args(argv)
    pack = build(pathlib.Path(a.runs).resolve())
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pack, ensure_ascii=False, sort_keys=True) + "\n",
                   encoding="utf-8")
    print("寫出 %s：%d 格（交付 %d／拒交 %d／作廢 %d）、%d 位居民"
          % (out, len(pack["cells"]), pack["delivered"], pack["refused"],
             pack["void"], len(pack["residents"])))
    print("  證據等級：%s" % pack["evidence_counts"])
    if pack["consent"]:
        print("  同意鏈：%d 筆" % len(pack["consent"]["chain"]))
    if not pack["delivered"] or not pack["refused"]:
        print("⚠ 展件需要交付格與拒交格都有。缺一種就只證明了閘門的一半。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
