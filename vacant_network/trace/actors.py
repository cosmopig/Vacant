"""actors — **後果**：責任按行動者累積（信譽，沿用 `reputation.py`）→ 路由（給人的建議＋`--agent auto`）。

這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §4.5–4.7；K9、K12、K14、K15）：

**後果是事件，信譽是重播出來的**。每一筆後果（`consequence`）追加進帳本
（`$VACANT_HOME/trace/actors.ndjson`，同時簽進那個專案的病歷）；信譽由重播「沒有被撤銷的
後果」得到——所以人撤銷一個結論（`vacant flag --dismiss`）會**逐位元**反轉它的效果，
帳本兩筆都留。

| 追緝結論 | 後果 |
|---|---|
| `provable`（事實層） | 那一步的行動者：`record_review` 對應維度 0 分、weight 1.0（值錯 ⇒ factual；程式／檢查 ⇒ logical）。**不 slash** |
| `lineage_exact`（輸入錯） | 行動者不動；**來源**記一筆計數（檔案／網址／使用者訊息） |
| `lineage_internal`／`heuristic` | 不動任何信譽；只進報告 |
| `gap` | 不動任何人；**整合覆蓋率**記一筆（那個平台的掛鉤沒看到） |
| 工作階段結束時契約過／不過 | 主 agent 的 adoption 維 1／0（這一跑的結果，不是對 agent 的定論） |

信譽鍵（§4.6）：
    stream    ＝ 行動者**定義**的雜湊（子 agent 的定義檔）；主 agent ＝ `main`；內建子 agent ＝ `builtin:<類型>`
    branch    ＝ 平台（有版本就加主版本）
    substrate ＝ 模型 id，前綴 `claimed:`（逐字稿／掛鉤自稱）或 `unknown`
    family    ＝ 契約裡驗證器種類的排序集合

路由（K15）：只做**給人的建議**（報告尾端）與 `vacant do --agent auto`（非文字的機會通道）；
對 agent 說「委派給誰」是文字通道 ⇒ 不做。

## 誠實邊界（改碼請保留）

1. 每格 n 長期是個位數：**永遠顯示次數，不顯示裸分數；n < `MIN_N` 不採取任何行動**
   （`--agent auto` 在那之前只做輪流探索）。
2. 自稱的模型 id 當鍵時標 `claimed:`，報告照實寫出。
3. 「這一跑過了」是這一跑、這個契約、這個觀測等級下的事實，不是對 agent 的定論（K18）。
4. 單一使用者、同一台機器：帳本和病歷一樣是本機金鑰、同一帳號 ⇒ 竄改可察覺，不是不可能。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
from typing import Any

from ..atomic import file_lock
from ..reputation import Reputation
from .recorder import trace_home

MIN_N = 5
_LOGICAL_VERIFIERS = {"python_checks", "command", "json_schema"}


def family_of(contract: Any) -> str:
    if contract is None:
        return ""
    return "+".join(sorted({c.verifier for c in contract.claims}))


def _def_sha(p: pathlib.Path) -> str | None:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


_DEF_DIRS = {
    "claude": [".claude/agents"],
    "opencode": [".opencode/agent", ".opencode/agents", ".config/opencode/agent",
                 ".config/opencode/agents"],
    "codex": [".codex/agents", ".codex/roles"],
    "pi": [".pi/agents", ".pi/agent/agents"],
}
_NAME_RE = __import__("re").compile(r"(?m)^\s*name\s*[:=]\s*[\"']?([^\"'\n]+?)[\"']?\s*$")


def _find_definition(platform: str, name: str, workspace: pathlib.Path | None) -> str | None:
    """子 agent 的定義檔：檔名相同，或 frontmatter／TOML 的 `name` 相同（Claude、pi 以
    frontmatter 的 name 認 agent；Codex 的角色是 `.toml`——2026-09-24 批判 §0-9）。"""
    bases = ([workspace] if workspace else []) + [pathlib.Path.home()]
    for base in bases:
        for d in _DEF_DIRS.get(platform, []):
            root = base / d
            if not root.is_dir():
                continue
            for f in sorted(root.rglob("*")):
                if f.suffix not in (".md", ".toml") or not f.is_file():
                    continue
                if f.stem == name:
                    return _def_sha(f)
                try:
                    head = f.read_text(encoding="utf-8", errors="replace")[:4000]
                except OSError:
                    continue
                m = _NAME_RE.search(head)
                if m and m.group(1).strip() == name:
                    return _def_sha(f)
    return None


def definition_of(actor: dict[str, Any], workspace: pathlib.Path | None = None) -> str:
    """行動者的「記憶」：子 agent 的定義檔改了 ⇒ 新的一格（既有「換了記憶就重來」的語意）。
    **一律帶平台前綴**：`reputation.py` 的衰減時鐘以 stream 為單位，四個平台的主 agent 若都叫
    `main`，Codex 跑 400 次會讓 Claude 那一格的證據老化（2026-09-24 批判 §1.1，實測 0.55→0.52）。"""
    platform = str(actor.get("platform") or "?")
    at = actor.get("agent_type")
    if not actor.get("agent") and not at:
        return f"{platform}:main"
    if not at:
        return f"{platform}:subagent"
    name = str(at)
    sha = _find_definition(platform, name, workspace)
    return f"{platform}:def:{name}:{sha}" if sha else f"{platform}:builtin:{name}"


def key_of(actor: dict[str, Any], contract: Any = None,
           workspace: pathlib.Path | None = None) -> tuple[str, str, str, str]:
    model = actor.get("model")
    substrate = f"claimed:{model}" if model else "unknown"
    branch = str(actor.get("platform") or "?")
    if actor.get("version"):
        # 主版本＋次版本（Codex 0.x 的每一版行為都可能不同；批判 §1.1）
        branch += "/" + ".".join(str(actor["version"]).split(".")[:2])
    return (definition_of(actor, workspace), branch, substrate, family_of(contract))


def label(key: tuple[str, str, str, str] | list[str]) -> str:
    st, br, su, _fam = key
    plat = br.split("/")[0]
    shown = st[len(plat) + 1:] if st.startswith(plat + ":") else st
    return f"{br} {shown} [{su}]"


class ActorBook:
    """全機一本（同一個 agent 設定在不同專案累積的是同一格）。"""

    def __init__(self, path: pathlib.Path | None = None):
        self.path = path or (trace_home() / "actors.ndjson")

    def _lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return file_lock(self.path.with_suffix(".lock"), timeout=30.0)

    def events(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    def _append(self, ev: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def record(self, ev: dict[str, Any]) -> bool:
        """冪等（同一個 `id` 只記一次）。回傳這一次有沒有真的記。"""
        with self._lock():
            if any(e.get("id") == ev["id"] for e in self.events()):
                return False
            self._append({"ts": time.time(), **ev})
            return True

    # ── 重播 ─────────────────────────────────────────────────────────
    def state(self) -> dict[str, Any]:
        evs = self.events()
        dismissed = {str(e.get("finding_id")) for e in evs if e.get("kind") == "dismiss"}
        rep = Reputation()
        runs: dict[tuple[str, ...], list[int]] = {}
        faults: dict[tuple[str, ...], int] = {}
        sources: dict[str, dict[str, Any]] = {}
        coverage: dict[str, int] = {}
        for e in evs:
            k = e.get("kind")
            if e.get("finding_id") and str(e["finding_id"]) in dismissed and k != "dismiss":
                continue
            key = tuple(e.get("key") or ())
            if k == "outcome" and len(key) == 4:
                ok = 1.0 if e.get("accepted") else 0.0
                rep.record_review(key[0], key[1], key[2], {"adoption": ok}, weight=1.0,
                                  family=key[3])
                runs.setdefault(key, []).append(int(ok))
            elif k == "provable_fault" and len(key) == 4:
                rep.record_review(key[0], key[1], key[2], {str(e.get("dim") or "factual"): 0.0},
                                  weight=1.0, family=key[3])
                faults[key] = faults.get(key, 0) + 1
            elif k == "input_fault":
                s = sources.setdefault(str(e.get("source")), {"count": 0, "findings": []})
                s["count"] += 1
                s["findings"].append(e.get("finding_id"))
            elif k == "gap":
                coverage[str(e.get("platform"))] = coverage.get(str(e.get("platform")), 0) + 1
        cells = []
        for key in sorted(set(runs) | set(faults)):
            r = runs.get(key, [])
            st, br, su, fam = key[0], key[1], key[2], key[3]
            cells.append({"key": list(key), "label": label([st, br, su, fam]), "runs": len(r),
                          "accepted": sum(r), "provable_faults": faults.get(key, 0),
                          "mean": rep.score(st, br, su, fam),
                          "observations": rep.observations(st, br, su, fam)})
        return {"cells": cells, "sources": sources, "coverage_gaps": coverage,
                "dismissed": sorted(dismissed), "reputation": rep}


def consequences(book: ActorBook, blames: list[dict[str, Any]], *, contract: Any,
                 workspace: pathlib.Path, finding_id,
                 platform: str | None = None) -> list[dict[str, Any]]:
    """把追緝結論變成後果事件（只有 §4.5 表上那幾種）。回傳這一次新記下的。"""
    out = []
    for b in blames:
        fid = finding_id(b)
        conf = b.get("confidence")
        step_id = str((b.get("step") or {}).get("step") or "")
        if conf == "provable" and b.get("step"):
            actor = dict(b["step"].get("actor") or {})
            verifier = ""
            try:
                from .rerun import claim_by_id
                verifier = claim_by_id(contract, str(b.get("claim"))).verifier
            except (KeyError, AttributeError):
                pass
            ev = {"id": f"pf:{fid}:{step_id}", "kind": "provable_fault", "finding_id": fid,
                  "key": list(key_of(actor, contract, workspace)),
                  "dim": "logical" if verifier in _LOGICAL_VERIFIERS else "factual",
                  "claim": b.get("claim"), "step": b["step"].get("n"),
                  "workspace": str(workspace)}
        elif conf == "lineage_exact" and b.get("fault_class") == "input" and \
                (b.get("source") or {}).get("kind") in ("input", "url", "instructions", "prompt",
                                                         "tool_output"):
            # 繳付物本來就寫錯（pre_existing 的 file）不是「來源」：不記在來源帳上
            src = b.get("source") or {}
            ref = src.get("path") or src.get("ref") or src.get("kind")
            ev = {"id": f"if:{fid}", "kind": "input_fault", "finding_id": fid,
                  "source": f"{src.get('kind')}:{ref}", "claim": b.get("claim"),
                  "workspace": str(workspace)}
        elif conf == "gap":
            ev = {"id": f"gap:{fid}", "kind": "gap", "finding_id": fid,
                  "platform": _platform_hint(b) if _platform_hint(b) != "unknown"
                  else (platform or "unknown"), "workspace": str(workspace)}
        else:
            continue
        if book.record(ev):
            out.append(ev)
    return out


def _platform_hint(b: dict[str, Any]) -> str:
    for c in b.get("chain") or []:
        a = (c or {}).get("actor") or {}
        if a.get("platform"):
            return str(a["platform"])
    return "unknown"


def record_outcome(book: ActorBook, *, session_key: str, actor: dict[str, Any],
                   accepted: bool, contract: Any, workspace: pathlib.Path) -> bool:
    return book.record({"id": f"out:{session_key}", "kind": "outcome", "accepted": bool(accepted),
                        "key": list(key_of(actor, contract, workspace)),
                        "workspace": str(workspace)})


def dismiss(book: ActorBook, finding_id: str, reason: str) -> bool:
    return book.record({"id": f"dismiss:{finding_id}", "kind": "dismiss",
                        "finding_id": finding_id, "reason": reason})


# ── 路由 ─────────────────────────────────────────────────────────────

def recommend(book: ActorBook, family: str) -> list[dict[str, Any]]:
    """這一類任務的紀錄，好的在前；`actionable`＝次數夠（≥ `MIN_N`）才可以拿來做決定。"""
    # `main` 沒有平台前綴的是 2026-09-24 早先版本寫的格子：照樣算主 agent
    rows = [c for c in book.state()["cells"]
            if c["key"][3] == family and (str(c["key"][0]) == "main"
                                          or str(c["key"][0]).endswith(":main"))]
    for r in rows:
        r["actionable"] = r["runs"] >= MIN_N
    rows.sort(key=lambda r: (-r["actionable"], -(r["accepted"] / r["runs"] if r["runs"] else 0),
                             r["provable_faults"], r["label"]))
    return rows


def recommendation_line(book: ActorBook, family: str) -> str | None:
    rows = recommend(book, family)
    if not rows:
        return None
    parts = [f"{r['label']} {r['accepted']}/{r['runs']} accepted"
             + (f", {r['provable_faults']} provable fault(s)" if r["provable_faults"] else "")
             for r in rows[:4]]
    small = "" if any(r["actionable"] for r in rows) else f" (n < {MIN_N}: too few to act on)"
    return f"For `{family}` tasks so far: " + "; ".join(parts) + small


def pick_agent(book: ActorBook, family: str, candidates: list[str], *,
               model_of: dict[str, str | None] | None = None, c: float = 0.3) -> dict[str, Any]:
    """`vacant do --agent auto`：UCB 於主 agent 的格子上。任何候選還不到 `MIN_N` 次 ⇒
    先輪流（挑次數最少的），不拿小樣本做決定。"""
    import math
    # 一個平台可能有好幾格（不同模型、不同版本）：路由挑的是平台，所以把它的格子加總
    # （2026-09-24 審查 consequences#3：原本留最後一格，隨便丟掉其他格的紀錄）
    rows: dict[str, dict[str, Any]] = {}
    for r in recommend(book, family):
        plat = r["key"][1].split("/")[0]
        if plat not in candidates:
            continue
        if model_of and model_of.get(plat) and r["key"][2] not in (
                f"claimed:{model_of[plat]}", "unknown"):
            continue
        agg = rows.setdefault(plat, {"runs": 0, "accepted": 0, "provable_faults": 0})
        for k in ("runs", "accepted", "provable_faults"):
            agg[k] += int(r[k])
    runs = {a: (rows[a]["runs"] if a in rows else 0) for a in candidates}
    if min(runs.values(), default=0) < MIN_N:
        a = sorted(candidates, key=lambda x: (runs[x], candidates.index(x)))[0]
        return {"agent": a, "why": f"exploring: {a} has {runs[a]} run(s) on this task family "
                                   f"(< {MIN_N})", "runs": runs}
    total = sum(runs.values())
    scored = {}
    for a in candidates:
        r = rows[a]
        rate = r["accepted"] / r["runs"]
        scored[a] = rate + c * math.sqrt(math.log(total + 1.0) / r["runs"])
    a = max(candidates, key=lambda x: (scored[x], -candidates.index(x)))
    return {"agent": a, "why": "UCB over accepted runs: " + ", ".join(
        f"{x} {rows[x]['accepted']}/{rows[x]['runs']}" for x in candidates), "runs": runs}
