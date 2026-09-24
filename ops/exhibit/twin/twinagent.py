"""twin/twinagent — 數位分身**真跑**：分身自己決定任務，在 `vacant run` 底下用 pi 做完。

## 這支在架構裡承重什麼

裁決：`decisions/DECISION_20260924_TWIN_AGENT_RUN.md`（流程、事件、權限、退化、撤回）。

在這之前 `twinlink.generate()` 是**直接打 1003 LM Studio 要三句台詞**：沒有 agent、
沒有 `vacant run`、沒有收據。分身「做了什麼」只是一句模型寫的台詞。這一支把它換成：

```
特質（檔案庫開封，主執行緒）
  → 拋棄式工作區 ws/<slug>/TRAITS.md          run-dir runs/<slug>/（工作區外）
  → launcher.run(twin_agent.sh …, vacant_on=True, allow_no_suite=True,
                 events_path=<展場 live 檔>, events_caller={cell_id,resident,prompt})
  → pi 自己決定 → PLAN.md ＋ 成品（工作區裡的檔案）
  → 行程結束 ⇒ 凍結 ⇒ ws_attempt ＋ ws_verdict（accepted_is_null）簽進收據
  → 主執行緒讀凍結快照 → twinvault（鏈外）＋ twinstore（commitment ＋ run_id ＋ verdict_hash）
```

**這一支不碰 sqlite**：`TwinStore` 的連線不跨執行緒。worker 只跑 launcher 與讀檔；
封印與寫鏈由 `twinlink` 在主執行緒做。

## 「做對」這件事（人類 2026-09-24）

「**這個問題是 vacant 問題，不是數位分身的問題**」⇒ 這一支**不發明評分**、不找模型當裁判。
跑法是 `allow_no_suite=True`：`stop_reason="ungated"`、`accepted=None`＝**沒有客觀標準、
不判**（不是 `False`）。

## 誠實邊界（改碼時保留）

1. **`accepted=None` 不准被壓成 `False`，也不准畫成「通過」。**
2. **收住的是「模型叫得到的工具」，不是 pi 這個行程**（裁決 §三）——**除非**
   `enclose` 開著而且這台起得來圍牆（VM，`twinenclose.py`）：那時整跑（launcher＋pi）
   在 bwrap 的 netns＋mount ns 裡，收據簽的是量出來的 `enclosure.applied`，天花板 B。
   圍牆起不來時 `enclose=auto` 會退回不圍、`enclose=on` 則不起 pi（誠實邊界 5）。
3. **`twin_id` 是雜湊別名，不是匿名化**：拿得到 `sub_id` 的人算得出它。它擋的是反方向——
   從公開的事件流／收據推回撤回用的那把鑰匙（`sub_id` 是能力憑證）。
4. **事件流與收據都不帶觀眾原文**：`caller.prompt` 是固定字串、`task_id` 是別名。
   事件流是 append-only 的檔，撤回刪不到裡面的行——所以從一開始就不寫進去。
5. **退化要看得出來**（twinlink 誠實邊界 2）：`requests_seen == 0`、沒有 `PLAN.md`、
   `infra_void` 都**不准**標成 `vacant_run:*`。
6. **撤回刪 run 產物，但收據留著**：`receipts_*.ndjson`／`.pub.json` 只有雜湊與計數，
   是「這一跑發生過」的可驗證據。其餘（wire log 含特質原文、凍結快照、stdout／stderr、
   摘要）全刪。`erase_run_artifacts()` 回報刪了什麼、留了什麼、哪裡出錯。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import sys
import threading
import time
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

HERE = pathlib.Path(__file__).resolve()
TWIN = HERE.parent
REPO = TWIN.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ops.exhibit.twin import roster as rosterlib  # noqa: E402
from vacant_network.memory import assert_ks1_clean  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402
# ⚠ `launcher` 在 `run_one` 裡才 import：它拉進 wireproxy／attest／sandbox，
#   而 twinlink（展場 loop）一 import 這一支就會拉它——這台跑不起 pi 時
#   （例如 1003 Windows 本機）不該因為一個用不到的模組而連 loop 都起不來。

#: 分身那一跑的 agent 命令（pi，工具收窄）。
WRAPPER = TWIN / "twin_agent.sh"

#: 畫面上 `engine` 的前綴。`vacant_run:pi:<model>` ＝ 真的在 `vacant run` 底下跑過、
#: 真的打到模型、真的寫了 PLAN.md。三個條件缺一就不是這個 engine（誠實邊界 5）。
ENGINE_PREFIX = "vacant_run:pi"

#: 1003 吞吐 4 串封頂，而同一張卡上還有別的線在跑 ⇒ 預設 2。
DEFAULT_PARALLEL = 2

#: 單跑牆鐘上限（launcher 的 `timeout_s`）。真模型一跑實測約 1–2 分鐘。
DEFAULT_AGENT_TIMEOUT = 300.0

#: 讀回的成品上限（每位分身）。
MAX_ARTIFACTS = 4
MAX_ARTIFACT_CHARS = 4000
MAX_PLAN_CHARS = 2000

#: 磁碟水位（MB）。低於它就**停收新分身**（不起新的 run），畫面與 log 都講。
#: 估算與理由：`ops/exhibit/twin/START.md`「VM 磁碟」一節。環境變數是單一真相來源：
#: loop（決定要不要起新的 run）與 serve／export（畫面上的 `intake`）讀同一個值。
ENV_MIN_FREE_MB = "VACANT_TWIN_MIN_FREE_MB"
DEFAULT_MIN_FREE_MB = 2048

#: 收據級別的高低（`require_tier` 用）。A > B > B' > C。
TIER_RANK = {"A": 3, "B": 2, "B'": 1, "C": 0}

#: 工作區裡**不是**成品的檔。
NOT_ARTIFACTS = frozenset({"TRAITS.md", "PLAN.md", "VACANT_FEEDBACK.md"})

#: 撤回時 run-dir 裡**留下**的檔：只有雜湊與計數（誠實邊界 6）。
#: `rows.jsonl` 也要留：既有的驗章器（`verify_receipts.verify_run`）拿它對帳
#: 「每題一筆 verdict」，少了它收據就驗不過——留收據卻驗不了等於沒留。
#: 它的欄位是別名、雜湊、計數與固定枚舉（`launcher._persist` 的 `row`）。
KEEP_ON_ERASE = ("receipts_RUN-ON.ndjson", "receipts_RUN-ON.pub.json", "rows.jsonl")

# ---------------------------------------------------------------------------
# 固定文字（全場逐字相同；argv 裡沒有觀眾原文）
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "你是「Vacant 世界」裡的一位居民，也是一位真人觀眾的數位分身。"
    "TRAITS.md 是那位觀眾交給我們的特質描述；你的個性、在意的事、說話的方式都從那裡來。\n\n"
    "這個世界不會指派工作給你，也沒有人會給你指令。你自己決定要在這裡做什麼。\n\n"
    "你只有三個工具：ws_list（看你房間裡有什麼）、ws_read（讀檔）、ws_write（寫檔）。"
    "它們只碰得到你自己的房間（目前的資料夾）。你沒有終端機，也沒有網路。\n\n"
    "步驟：\n"
    "1. 決定一件你想在這個世界完成的實務小事——寫在檔案裡就能完成的事，"
    "例如一封信、一份計畫、一張清單。不要寫程式。\n"
    "2. 用 ws_write 寫 PLAN.md：第一行用一句話說你決定做什麼；"
    "接著用兩三句說你為什麼選它（從 TRAITS.md 的特質出發）。\n"
    "3. 動手做：用 ws_write 把成品寫成一個檔（檔名你自己取，副檔名用 .md 或 .txt）。\n"
    "4. 做完就停，最後用一句話說你交出了什麼。\n\n"
    "規則：用繁體中文。不要自稱 AI，不要提到模型或提示詞。"
    "不要在檔案裡逐字抄錄 TRAITS.md 的內容。"
)

FIRST_MESSAGE = "上面是 TRAITS.md。照說明的步驟開始：先寫 PLAN.md，再做你決定要做的事。"

#: 事件流 `caller.prompt`。**固定字串**：觀眾特質與分身的決定都不進事件流（誠實邊界 4）。
CALLER_PROMPT = "這位分身自己決定要做什麼（內容只留在會場本機，撤回就刪）"

for _t in (SYSTEM_PROMPT, FIRST_MESSAGE, CALLER_PROMPT):
    assert_ks1_clean(_t)          # 鐵律 1：import 時就驗，不等到跑


# ---------------------------------------------------------------------------
# 名字與路徑
# ---------------------------------------------------------------------------

def public_twin_id(sub_id: str) -> str:
    """公開別名。**不用 `sub_id` 本身**：它是撤回的能力憑證（誠實邊界 3）。"""
    h = hashlib.sha256(("vacant.twin.public/1\n" + sub_id).encode("utf-8"))
    return "tw-" + h.hexdigest()[:12]


def resident_code(sub_id: str) -> str:
    """分身代號（確定性，與 `roster.make_resident` 同一支）。"""
    return rosterlib.make_resident(public_twin_id(sub_id)).codename


def slug_for(sub_id: str) -> str:
    """目錄名 ＝ `sha256(sub_id)[:32]`（與 `twinvault.slug_for` 同一個算法，防路徑穿越）。"""
    return hashlib.sha256(sub_id.encode("utf-8")).hexdigest()[:32]


def default_work_root(db_path: pathlib.Path | str) -> pathlib.Path:
    """run 產物住哪裡：`<庫名>.agentruns/` 就在庫旁邊（與檔案庫同一個理由）。

    ⚠ **單一真相來源**：`loop`（寫）與 `serve --allow-withdraw`（撤回時刪）是兩個行程，
    兩邊都從庫的路徑推出同一個位置。要換地方用 `VACANT_TWIN_AGENTRUNS`，**兩邊都要設**。
    """
    env = os.environ.get("VACANT_TWIN_AGENTRUNS")
    p = pathlib.Path(db_path)
    return pathlib.Path(env) if env else p.parent / (p.stem + ".agentruns")


def default_events_path(db_path: pathlib.Path | str) -> pathlib.Path:
    """展場 live 檔：`VACANT_EVENTS` 優先，否則庫旁邊的 `twin_lifecycle.jsonl`。"""
    env = (os.environ.get(lifecycle.ENV_EVENTS) or "").strip()
    return pathlib.Path(env) if env else pathlib.Path(db_path).parent / "twin_lifecycle.jsonl"


def paths_for(work_root: pathlib.Path, sub_id: str) -> tuple[pathlib.Path, pathlib.Path]:
    """（工作區, run-dir）。兩者在不同子樹 ⇒ run-dir 一定不在工作區底下。"""
    s = slug_for(sub_id)
    return work_root / "ws" / s, work_root / "runs" / s


# ---------------------------------------------------------------------------
# 設定與前置檢查
# ---------------------------------------------------------------------------

@dataclass
class AgentConfig:
    work_root: pathlib.Path
    events_path: pathlib.Path | None
    model: str
    endpoint: str
    parallel: int = DEFAULT_PARALLEL
    timeout_s: float = DEFAULT_AGENT_TIMEOUT
    #: launcher 的 argv 前綴；之後會接 `<run_dir> <system_prompt> <first_message>`。
    argv_prefix: list[str] = field(default_factory=lambda: ["bash", str(WRAPPER)])
    #: 這一台要有哪些可執行檔才算「跑得起來」。測試用的 fixture agent 給 `[]`。
    requires: list[str] = field(default_factory=lambda: [
        "bash", os.environ.get("VACANT_TWIN_PI") or "pi"])
    #: 圍牆（`twinenclose.py`）：`off`＝不圍（Windows／macOS）、`auto`＝起得來就圍、
    #: `on`＝**一定要圍**，起不來就不起 pi（`agent_available` 回 False 並講為什麼）。
    enclose: str = "off"
    #: 收據級別下限（例：`"B"`）。這一跑簽的 `tier` 低於它 ⇒ 不算分身做的
    #: （`degrade_kind=tier_below_required`）。`None` ＝不設下限（舊行為）。
    #: 這是 twin 這一層的 `VACANT_ATTEST=fail`：launcher 只記級別不拒發，擋門在這裡。
    require_tier: str | None = None


def agent_available(cfg: AgentConfig) -> tuple[bool, str]:
    """這一台跑得起分身嗎。**跑不起來要講為什麼**，不要讓 launcher 撞 5 分鐘的牆。"""
    for exe in cfg.requires:
        if not (shutil.which(exe) or pathlib.Path(exe).is_file()):
            return False, f"找不到 {exe}（PATH 上沒有）"
    for a in cfg.argv_prefix[1:2]:
        if a.endswith((".sh", ".py")) and not pathlib.Path(a).is_file():
            return False, f"找不到 agent 包裝 {a}"
    if cfg.enclose == "on":
        from ops.exhibit.twin import twinenclose
        ok, why = twinenclose.available()
        if not ok:
            return False, f"enclose=on 但圍牆起不來：{why}"
    return True, "ok"


def use_enclosure(cfg: AgentConfig) -> tuple[bool, str]:
    """這一跑要不要進圍牆（`on`／`auto` 且這台起得來）。回（要不要, 為什麼）。"""
    if cfg.enclose not in ("on", "auto"):
        return False, "enclose=off"
    from ops.exhibit.twin import twinenclose
    ok, why = twinenclose.available()
    return ok, why


def meets_tier(tier: Any, required: str | None) -> bool:
    """`tier` 有沒有達到 `required`。`required=None` ⇒ 一律 True；量不到（None）⇒ False。"""
    if not required:
        return True
    return TIER_RANK.get(str(tier), -1) >= TIER_RANK.get(required, 99)


def min_free_bytes() -> int:
    """水位門檻（位元組）。`VACANT_TWIN_MIN_FREE_MB` 讀不懂 ⇒ 用預設值，不是 0。"""
    try:
        mb = int(float(os.environ.get(ENV_MIN_FREE_MB) or DEFAULT_MIN_FREE_MB))
    except ValueError:
        mb = DEFAULT_MIN_FREE_MB
    return max(0, mb) * 1024 * 1024


def intake_status(work_root: pathlib.Path | str) -> dict[str, Any]:
    """磁碟水位 ⇒ 收不收新分身。**量不到不是「夠」**：`free_bytes=None` ⇒ `accepting=False`。

    量的是 `work_root` 所在的檔案系統（它不存在就往上找存在的那一層）。
    """
    p = pathlib.Path(work_root)
    while not p.exists() and p != p.parent:
        p = p.parent
    need = min_free_bytes()
    try:
        free = shutil.disk_usage(p).free
    except OSError:
        free = None
    accepting = free is not None and free >= need
    reason = None
    if free is None:
        reason = f"量不到 {p} 的剩餘空間 ⇒ 不收新分身（不是「空間夠」）"
    elif not accepting:
        reason = (f"磁碟只剩 {free // (1024 * 1024)} MB（門檻 {need // (1024 * 1024)} MB）"
                  " ⇒ 暫停收新分身；已經在跑的會跑完，排隊的人留在佇列裡")
    return {"accepting": accepting, "free_bytes": free, "min_free_bytes": need,
            "path": str(p), "reason": reason}


def upstream_reachable(endpoint: str, timeout: float = 3.0) -> bool:
    """模型端點探得到嗎（`GET /models`）。探不到 ⇒ 不起 pi（起了只是撞牆）。"""
    try:
        with urllib.request.urlopen(endpoint.rstrip("/") + "/models",
                                    timeout=timeout) as r:
            return 200 <= r.status < 300
    except Exception:                                    # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# 工作區 ↔ 特質／產出
# ---------------------------------------------------------------------------

_CARD_LABELS = (("需求", "need"), ("形狀", "shape"), ("質感", "texture"),
                ("色系", "color"), ("氣質", "vibe"), ("第一句話", "first_line"))


def render_traits(card: Any, card_text: Any) -> str:
    """觀眾的特質 → TRAITS.md。**這是觀眾原文進到 agent 的唯一入口。**"""
    lines = ["# 這位觀眾的特質", ""]
    c = card if isinstance(card, dict) else {}
    for label, key in _CARD_LABELS:
        v = c.get(key)
        if v not in (None, ""):
            lines.append(f"- {label}：{str(v)[:600]}")
    if card_text:
        lines += ["", "## 他貼回來的原文", "", str(card_text)[:6000]]
    return "\n".join(lines) + "\n"


def _clip(s: str, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def parse_plan(text: str) -> tuple[str | None, str | None]:
    """PLAN.md → (決定, 理由)。第一個非空行是決定，其後是理由。"""
    rows = [r.strip() for r in str(text).splitlines()]
    rows = [r for r in rows if r]
    if not rows:
        return None, None
    first = rows[0].lstrip("#-*> ").strip()
    for pre in ("我決定：", "我決定:", "決定：", "決定:"):
        if first.startswith(pre):
            first = first[len(pre):].strip()
    reason = "\n".join(rows[1:]).strip() or None
    return (first[:200] or None), (reason[:MAX_PLAN_CHARS] if reason else None)


def read_outputs(root: pathlib.Path | None) -> dict[str, Any]:
    """從（凍結快照的）工作區讀回分身的決定與成品。"""
    out: dict[str, Any] = {"decision": None, "reason": None, "artifacts": [],
                           "has_plan": False}
    if root is None or not root.is_dir():
        return out
    plan = root / "PLAN.md"
    if plan.is_file():
        try:
            txt = plan.read_text(encoding="utf-8", errors="replace")
            out["decision"], out["reason"] = parse_plan(txt)
            out["has_plan"] = out["decision"] is not None
        except OSError:
            pass
    arts = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if (not p.is_file() or p.is_symlink() or rel in NOT_ARTIFACTS
                or any(part.startswith(".") for part in p.relative_to(root).parts)):
            continue
        if p.suffix.lower() not in (".md", ".txt"):
            continue
        try:
            raw = p.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        arts.append({"name": rel[:120], "bytes": len(raw),
                     "text": text[:MAX_ARTIFACT_CHARS],
                     "truncated": len(text) > MAX_ARTIFACT_CHARS})
        if len(arts) >= MAX_ARTIFACTS:
            break
    out["artifacts"] = arts
    return out


def derive_lines(decision: str | None, reason: str | None,
                 artifacts: list[dict]) -> dict[str, str]:
    """螢幕的三句台詞**從產出衍生**（不再是另一個模型憑空寫的）。"""
    d = _clip(decision or "我還在想要做什麼", 40)
    first_reason = ""
    if reason:
        for sep in ("。", "！", "？", "\n", ".", "!"):
            if sep in reason:
                first_reason = reason.split(sep)[0]
                break
        first_reason = first_reason or reason
    working = _clip(first_reason, 40) if first_reason else f"開始動手：{_clip(d, 30)}"
    handover = (f"做好了，放在「{_clip(artifacts[0]['name'], 30)}」。" if artifacts
                else "我把決定寫下來了。")
    return {"arrival": d, "working": working, "handover": handover}


# ---------------------------------------------------------------------------
# worker（跑在執行緒裡；**不碰 sqlite**）
# ---------------------------------------------------------------------------

@dataclass
class Job:
    sub_id: str
    traits: str
    cfg: AgentConfig


def run_one(job: Job) -> dict[str, Any]:
    """一位分身跑一次。回一份**只有資料**的結果（封印由主執行緒做）。"""
    t0 = time.time()
    tid = public_twin_id(job.sub_id)
    ws, rd = paths_for(job.cfg.work_root, job.sub_id)
    res: dict[str, Any] = {"sub_id": job.sub_id, "twin_id": tid,
                           "error": None, "summary": None, "outputs": None}
    try:
        from vacant_network.vrun import launcher        # 延後 import，見檔頭
        for d in (ws, rd):
            if d.exists():
                shutil.rmtree(d)
        ws.mkdir(parents=True)
        rd.mkdir(parents=True)
        (ws / "TRAITS.md").write_text(job.traits, encoding="utf-8")
        argv = list(job.cfg.argv_prefix) + [str(rd), SYSTEM_PROMPT, FIRST_MESSAGE]
        caller = {"cell_id": tid, "resident": resident_code(job.sub_id),
                  "stratum": "twin", "prompt": CALLER_PROMPT,
                  "declared_evidence": "",
                  # 電視靠它分出「分身的自主任務」：沒有客觀標準、只有一臂、
                  # 用 task_id(＝twin_id) 去對名冊（tv_contract 規則 11）。
                  "task_kind": "practical"}
        enclosed, enc_why = use_enclosure(job.cfg)
        res["enclosed"] = enclosed
        res["enclosure_why"] = enc_why
        res["require_tier"] = job.cfg.require_tier
        if enclosed:
            from ops.exhibit.twin import twinenclose
            summary = twinenclose.run_enclosed(
                argv=argv, workspace=ws, run_dir=rd,
                door_dir=twinenclose.door_dir_for(job.cfg.work_root, slug_for(job.sub_id)),
                task_id=f"twin:{tid}", timeout_s=job.cfg.timeout_s,
                events_path=job.cfg.events_path, events_caller=caller,
                endpoint=job.cfg.endpoint, model=job.cfg.model,
                pi_bin=os.environ.get("VACANT_TWIN_PI") or "pi")
        else:
            summary = launcher.run(
                argv, workspace=ws, run_dir=rd, suite_dir=None,
                vacant_on=True, allow_no_suite=True,
                task_id=f"twin:{tid}",
                timeout_s=job.cfg.timeout_s,
                capture_agent_stdout=True,
                events_path=(str(job.cfg.events_path) if job.cfg.events_path else None),
                events_caller=caller)
        last = (summary.get("attempts") or [{}])[-1]
        frozen = last.get("frozen_path")
        res["summary"] = {
            k: summary.get(k) for k in (
                "stop_reason", "accepted", "refused", "infra_void", "requests_seen",
                "agent_rc", "agent_timed_out", "verdict_hash", "attempts_used")}
        res["summary"]["run_id"] = (summary.get("lifecycle") or {}).get("run_id")
        res["summary"]["count_semantics"] = (summary.get("model_wire") or {}).get(
            "count_semantics")
        att = summary.get("attestation") or {}
        res["summary"]["tier"] = att.get("tier")
        res["summary"]["enclosure_applied"] = (att.get("enclosure") or {}).get("applied")
        res["summary"]["twin_enclosure"] = summary.get("twin_enclosure")
        if enclosed:
            # 圍牆裡的 pi 寫得到 run-dir（twinenclose 誠實邊界 2）⇒ 主機側**當場驗章**，
            # 不信圍牆裡寫出來的 summary。
            from vacant_network.vrun import verify_receipts as vrr
            try:
                res["summary"]["receipt_verdicts"] = [
                    r.get("verdict") for r in vrr.verify_run(rd)]
            except Exception as e:                       # noqa: BLE001
                res["summary"]["receipt_verdicts"] = [f"error:{type(e).__name__}"]
        res["outputs"] = read_outputs(pathlib.Path(frozen) if frozen else None)
    except (Exception, SystemExit) as exc:               # noqa: BLE001
        res["error"] = type(exc).__name__
        res["error_detail"] = str(exc)[:300]
    res["wall_s"] = round(time.time() - t0, 3)
    return res


def build_twin(res: dict[str, Any], *, model: str,
               fallback: Any) -> dict[str, Any]:
    """worker 結果 → 要封印的 twin。**`engine` 照裁決 §五 的表決定，不看心情。**

    `fallback` 是 `twinlink.fallback_twin`（傳進來避免循環 import）。
    """
    s = res.get("summary") or {}
    o = res.get("outputs") or {}
    run_fields = {
        "twin_id": res.get("twin_id"),
        "run_id": s.get("run_id"), "verdict_hash": s.get("verdict_hash"),
        "stop_reason": s.get("stop_reason"),
        # 🔴 三值：`None` ＝沒有客觀標準、不判。不准壓成 False。
        "accepted": s.get("accepted"),
        "requests_seen": s.get("requests_seen"),
        "count_semantics": s.get("count_semantics"),
        "agent_rc": s.get("agent_rc"), "agent_timed_out": s.get("agent_timed_out"),
        "latency_ms": int(float(res.get("wall_s") or 0) * 1000),
        # 收據上簽的級別（量出來的）＋這一跑有沒有進圍牆。只有枚舉與計數。
        "tier": s.get("tier"),
        "enclosed": res.get("enclosed"),
        "enclosure_applied": s.get("enclosure_applied"),
        "door_calls": (s.get("twin_enclosure") or {}).get("door_calls"),
    }
    te = s.get("twin_enclosure") or {}
    why = None
    if res.get("error"):
        why = (res["error"], res.get("error_detail"))
    elif s.get("infra_void"):
        why = (f"infra_void:{s.get('stop_reason')}", str(s.get("infra_void"))[:300])
    elif not isinstance(s.get("requests_seen"), int) or s["requests_seen"] <= 0:
        why = ("no_model_call", "這一跑沒有任何一通模型呼叫經過中介")
    elif not o.get("has_plan"):
        why = ("agent_no_plan", "有模型呼叫，但工作區裡沒有 PLAN.md")
    elif res.get("enclosed") and s.get("receipt_verdicts") != ["OK"]:
        why = ("receipt_unverified",
               f"圍牆裡那一跑的收據主機側驗不過：{s.get('receipt_verdicts')}")
    elif res.get("enclosed") and te.get("door_excess") != 0:
        why = ("door_unreconciled",
               f"門看到 {te.get('door_calls')} 通、收據記 {s.get('requests_seen')} 通"
               " ⇒ 有呼叫沒經過收據那一層（或對不上帳）")
    elif not meets_tier(s.get("tier"), res.get("require_tier")):
        why = ("tier_below_required",
               f"收據級別 {s.get('tier')!r} 低於要求的 {res.get('require_tier')!r}")

    if why is not None:
        out = fallback(None)
        out.update({k: v for k, v in run_fields.items() if v is not None})
        out["engine"] = "fallback_deterministic"
        out["degraded_from"] = f"{ENGINE_PREFIX}:{model}"
        out["degrade_kind"] = str(why[0])[:120]
        out["degrade_reason"] = str(why[1])     # 只進鏈外（可能夾帶 stderr 片段）
        out["n_artifacts"] = len(o.get("artifacts") or [])
        return out

    lines = derive_lines(o.get("decision"), o.get("reason"), o.get("artifacts") or [])
    return {
        **lines,
        "decision": o.get("decision"), "reason": o.get("reason"),
        "artifacts": o.get("artifacts") or [],
        "n_artifacts": len(o.get("artifacts") or []),
        "lines_from": "agent_workspace",
        "engine": f"{ENGINE_PREFIX}:{model}", "model": model,
        **run_fields,
    }


# ---------------------------------------------------------------------------
# 佇列
# ---------------------------------------------------------------------------

class AgentPool:
    """最多並行 N 位分身。**提交與收成都在主執行緒**；worker 只跑 `run_one`。"""

    def __init__(self, parallel: int = DEFAULT_PARALLEL) -> None:
        self.parallel = max(1, int(parallel))
        self._ex = ThreadPoolExecutor(max_workers=self.parallel,
                                      thread_name_prefix="twin-agent")
        self._futs: dict[str, Future] = {}
        self._lock = threading.Lock()

    def in_flight(self) -> set[str]:
        with self._lock:
            return set(self._futs)

    def submit(self, job: Job) -> bool:
        with self._lock:
            if job.sub_id in self._futs:
                return False
            self._futs[job.sub_id] = self._ex.submit(run_one, job)
            return True

    def harvest(self, *, block: bool = False) -> list[dict[str, Any]]:
        """收成跑完的。`block=True` ⇒ 等到佇列清空。"""
        out: list[dict[str, Any]] = []
        while True:
            with self._lock:
                done = [s for s, f in self._futs.items() if f.done()]
                for s in done:
                    f = self._futs.pop(s)
                    try:
                        out.append(f.result())
                    except BaseException as exc:          # noqa: BLE001
                        out.append({"sub_id": s, "twin_id": public_twin_id(s),
                                    "error": type(exc).__name__,
                                    "error_detail": str(exc)[:300],
                                    "summary": None, "outputs": None})
                left = len(self._futs)
            if not block or left == 0:
                return out
            time.sleep(0.2)

    def wait_idle(self, poll_s: float = 0.2) -> None:
        """等到手上的都跑完——**不收成**（收成要交給主執行緒的 `generate` 去封印）。"""
        while True:
            with self._lock:
                if all(f.done() for f in self._futs.values()):
                    return
            time.sleep(poll_s)

    def shutdown(self, wait: bool = True) -> None:
        self._ex.shutdown(wait=wait)


# ---------------------------------------------------------------------------
# 撤回：真的刪 run 產物
# ---------------------------------------------------------------------------

def _tree_size(p: pathlib.Path) -> tuple[int, int]:
    if p.is_file() or p.is_symlink():
        try:
            return 1, p.lstat().st_size
        except OSError:
            return 1, 0
    n = b = 0
    for q in p.rglob("*"):
        if q.is_file() and not q.is_symlink():
            n += 1
            try:
                b += q.stat().st_size
            except OSError:
                pass
    return n, b


def erase_run_artifacts(work_root: pathlib.Path, sub_id: str) -> dict[str, Any]:
    """刪掉這位分身在 run 那一側留下的一切，**只留收據**（誠實邊界 6）。

    回 `{"erased": [...], "kept_hash_only": [...], "problems": [...]}`。
    `erased` 每一項只有**類別名、檔數、位元組數**——這一份會上鏈，不准有內容。
    """
    ws, rd = paths_for(pathlib.Path(work_root), sub_id)
    erased: list[dict[str, Any]] = []
    kept: list[str] = []
    problems: list[str] = []

    def _rm(p: pathlib.Path, label: str) -> None:
        n, b = _tree_size(p)
        try:
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p)
            else:
                p.unlink()
        except OSError as exc:
            problems.append(f"{label}: {type(exc).__name__}")
            return
        if p.exists() or p.is_symlink():
            problems.append(f"{label}: 刪了但還在")
            return
        erased.append({"what": label, "files": n, "bytes": b})

    if ws.exists():
        _rm(ws, "workspace")
    # 圍牆的門（twinenclose）：門的 journal 也是逐字落盤 ⇒ 有特質原文
    door = pathlib.Path(work_root) / "doors" / slug_for(sub_id)
    if door.exists():
        _rm(door, "door_journal")
    if rd.exists():
        for child in sorted(rd.iterdir()):
            if child.name in KEEP_ON_ERASE and child.is_file():
                kept.append(child.name)
                continue
            _rm(child, child.name)
        # 正控制：run-dir 裡只准剩收據
        left = sorted(c.name for c in rd.iterdir() if c.name not in KEEP_ON_ERASE)
        if left:
            problems.append(f"run-dir 還剩 {len(left)} 項不是收據")
    return {"erased": erased, "kept_hash_only": kept, "problems": problems}


def run_artifacts_present(work_root: pathlib.Path, sub_id: str) -> bool:
    """這位分身在 run 那一側還有**非收據**的東西嗎（撤回後應為 False）。"""
    ws, rd = paths_for(pathlib.Path(work_root), sub_id)
    if ws.exists() or (pathlib.Path(work_root) / "doors" / slug_for(sub_id)).exists():
        return True
    if rd.exists():
        return any(c.name not in KEEP_ON_ERASE for c in rd.iterdir())
    return False


def job_for(sub_id: str, card: Any, card_text: Any, cfg: AgentConfig) -> Job | None:
    """主執行緒組 job。特質讀不到（檔案庫沒有、舊庫壞掉）⇒ `None`，呼叫端走退化。"""
    if card in (None, {}, "") and not card_text:
        return None
    return Job(sub_id=sub_id, traits=render_traits(card, card_text), cfg=cfg)


def describe(cfg: AgentConfig) -> dict[str, Any]:
    """落進 generate 回報的那一塊（路徑、並行數、上限）。"""
    return {"work_root": str(cfg.work_root),
            "events_path": str(cfg.events_path) if cfg.events_path else None,
            "parallel": cfg.parallel, "timeout_s": cfg.timeout_s,
            "enclose": cfg.enclose, "require_tier": cfg.require_tier,
            "argv_prefix": [pathlib.Path(a).name for a in cfg.argv_prefix]}


if __name__ == "__main__":      # 只印固定文字，方便人讀
    print(json.dumps({"system_prompt": SYSTEM_PROMPT, "first_message": FIRST_MESSAGE,
                      "caller_prompt": CALLER_PROMPT}, ensure_ascii=False, indent=2))
