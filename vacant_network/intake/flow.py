"""flow — 收件口的**一條**流程，所有入口共用（CLI、agent 掛鉤、`vacant do`、HTTP 收件）。

這支在架構裡承重什麼（`decisions/DECISION_20260924_UNIVERSAL_INTAKE.md` §三）：

不論成果是 pi 寫的、Claude Code 寫的、閉源 SaaS 匯出的、還是人上傳的，進來之後都走
同一條路——所以「支援哪個 agent」不再是判準的一部分，只是「成果從哪個入口進來」：

    lock(契約)        ─→ 釘住輸入 → owner 簽契約鎖（需求權威）→ 帳本
    submit(來源目錄)  ─→ 凍結進隔離區 → 逐項取證 → 裁決（簽）→ 帳本
    check(來源目錄)   ─→ 同上，但不落隔離區、不上帳本（給 agent 自己先驗）
    review / reverify ─→ 人工審查（簽）→ 對**同一個**成果雜湊重新取證
    approve           ─→ 綁定內容的批准（簽）
    release           ─→ 收件端自己重驗一切 → 發布 → 讀回 → 帳本
    withdraw          ─→ 收件端撤回 → 帳本

任何一段的基礎設施失敗都寫成 `infra_void` 事件（不是成功、也不是成果的錯），
**不會讓那一次從帳本消失**。
"""
from __future__ import annotations

import dataclasses
import pathlib
import shutil
import tempfile
from typing import Any

from . import approval as _approval
from . import home as _home
from . import keys as _keys
from .artifact import ArtifactError, Store
from .contract import Contract, load as load_contract, lock as _pin_inputs
from .ledger import Ledger, state_of
from .policy import HIDDEN_DETAIL, decide, results_digest
from .recipients import gate_release, parse_destination, withdraw as _withdraw
from .verifiers import VerifyContext, run_all


@dataclasses.dataclass
class Task:
    contract: Contract
    root: pathlib.Path
    store: Store
    ledger: Ledger
    trust: _keys.Trust

    @property
    def task_id(self) -> str:
        return self.contract.task_id


def open_task(contract: Contract | str | pathlib.Path,
              root: pathlib.Path | None = None) -> Task:
    """載入契約、確保本機金鑰存在、契約雜湊變了就在帳本上記一筆 `task_opened`。"""
    c = contract if isinstance(contract, Contract) else load_contract(contract)
    r = root or _home()
    _keys.ensure_local(r)
    trust = _keys.Trust.load(r / "trust.json")
    led = Ledger(c.task_id, r)
    evs = led.events()
    latest = None
    for ev in evs:
        if ev["type"] == "task_opened":
            latest = ev.get("contract_sha256")
    if latest != c.sha256:
        led.append("task_opened", {"contract_sha256": c.sha256, "version": c.version,
                                   "objective": str(c.raw.get("objective", ""))[:500],
                                   "contract_path": str(c.path) if c.path else None})
    return Task(contract=c, root=r, store=Store(r / "store"), ledger=led, trust=trust)


def lock(path: str | pathlib.Path, root: pathlib.Path | None = None) -> dict[str, Any]:
    """`vacant contract lock`：釘住輸入，然後 **owner 簽**「這個任務就是這個契約雜湊」。

    收件端只依被鎖過的契約放行——同一個 task_id 的另一份契約檔（放行政策較鬆）
    沒有 owner 的簽名，就送不進目的端。契約改了（雜湊變了）要重新鎖。
    """
    pins = _pin_inputs(path)
    task = open_task(path, root)
    ident = _keys.load_or_create("owner", task.root)
    doc = _approval.sign_lock(ident, task_id=task.task_id,
                              contract_sha256=task.contract.sha256,
                              release=task.contract.release)
    task.ledger.append("contract_locked", {"contract_sha256": task.contract.sha256,
                                           "lock": doc})
    return {"pins": pins, "contract_sha256": task.contract.sha256, "lock": doc}


def _lock_for(task: Task) -> Any:
    doc = None
    for ev in task.ledger.events():
        if ev["type"] == "contract_locked" and ev.get("contract_sha256") == task.contract.sha256:
            doc = ev.get("lock")
    return doc


def _reviews_for(task: Task, artifact_sha256: str) -> list[dict[str, Any]]:
    out = []
    for ev in task.ledger.events():
        if ev["type"] != "review_recorded":
            continue
        doc = ev.get("review")
        who, why = _keys.verify_doc(doc, trust=task.trust, role="reviewer")
        if who is None or not isinstance(doc, dict):
            continue
        p = doc["payload"]
        # 審查綁 (task, 契約, 成果)：契約改版可能把同一個 claim id 改成另一件事
        if p.get("task_id") == task.task_id and p.get("artifact_sha256") == artifact_sha256 \
                and p.get("contract_sha256") == task.contract.sha256:
            out.append({**p, "reviewer": who, "ts_ms": ev.get("ts_ms", 0)})
    return out


def _verify_manifest(task: Task, manifest: dict[str, Any], *, sandbox: str,
                     store: Store) -> dict[str, Any]:
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="vacant-verify-"))
    try:
        adir = store.materialize(manifest, scratch / "artifact")
        ctx = VerifyContext(contract=task.contract, artifact_dir=adir, manifest=manifest,
                            scratch=scratch, sandbox_name=sandbox,
                            reviews=_reviews_for(task, manifest["artifact_sha256"]))
        results = run_all(ctx)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    d = decide(task.contract, results, artifact_sha256=manifest["artifact_sha256"])
    return {"decision": d, "manifest": manifest}


def _record_decision(task: Task, d, manifest: dict[str, Any]) -> dict[str, Any]:
    ident = _keys.load_or_create("verifier", task.root)
    doc = _approval.sign_decision(
        ident, task_id=task.task_id, contract_sha256=task.contract.sha256,
        artifact_sha256=manifest["artifact_sha256"], outcome=d.outcome,
        results_sha256=results_digest(d.results), coverage=d.coverage)
    hidden = {c.id for c in task.contract.claims if c.hidden}
    compact = [{"id": r.claim_id, "status": r.status, "verifier": r.verifier,
                "version": r.verifier_version, "required": r.required,
                "authority": r.authority,
                "detail": HIDDEN_DETAIL if r.claim_id in hidden else r.detail[:300]}
               for r in d.results]
    task.ledger.append("decision", {
        "artifact_sha256": manifest["artifact_sha256"],
        "contract_sha256": task.contract.sha256, "outcome": d.outcome,
        "reasons": [x[:300] for x in d.reasons[:20]], "coverage": d.coverage,
        "results": compact, "results_sha256": results_digest(d.results),
        "decision_doc": doc, "skipped": manifest.get("skipped", [])[:20]})
    return doc


def submit(task: Task, source_dir: str | pathlib.Path, *, source: str,
           sandbox: str = "auto", attempt: int | None = None) -> dict[str, Any]:
    """凍結 → 取證 → 裁決 → 上帳本。回傳可直接印成 JSON 的結果。"""
    if not pathlib.Path(source_dir).is_dir():
        task.ledger.append("infra_void", {"stage": "freeze", "attempt": attempt,
                                          "error": f"source directory {source_dir} is missing"})
        return {"outcome": None, "void": True,
                "reasons": [f"source directory {source_dir} is missing"]}
    return _submit(task, lambda: task.store.freeze(
        source_dir, include=task.contract.include,
        exclude=task.contract.exclude + _receiver_excludes(task.contract, source_dir),
        task_id=task.task_id, source=source), source=source, sandbox=sandbox,
        attempt=attempt)


def _receiver_excludes(contract: Contract, source_dir: str | pathlib.Path) -> list[str]:
    """收件端自己的東西不是成果：`dir:` 目的端在專案裡的話（`dir:published`），下一次交件
    會把上一次放行的版本、收件端的紀錄（用過的 nonce、裁決文件）一起凍進候選版本，
    `replace=true` 時還會一層套一層（2026-09-24 對抗審查重現）。Vacant 的狀態目錄同理。"""
    from .statepaths import state_dirs
    src = pathlib.Path(source_dir).resolve()
    out: list[str] = []
    cands = list(state_dirs())
    spec = str(contract.release.get("destination") or "")
    if spec.startswith("dir:"):
        p = pathlib.Path(spec[4:]).expanduser()
        cands.append((p if p.is_absolute() else contract.base_dir / p).resolve())
    for c in cands:
        try:
            rel = c.relative_to(src).as_posix()
        except ValueError:
            continue
        if rel and rel != ".":
            out.append(f"{rel}/**")
    return out


def submit_blobs(task: Task, blobs: dict[str, bytes], *, source: str,
                 sandbox: str = "auto") -> dict[str, Any]:
    """HTTP 收件入口：路徑→位元組。提交者**只能提交**，給不了裁決。"""
    return _submit(task, lambda: task.store.freeze_blobs(
        blobs, task_id=task.task_id, source=source, include=task.contract.include,
        exclude=task.contract.exclude), source=source, sandbox=sandbox, attempt=None)


def _submit(task: Task, freeze, *, source: str, sandbox: str,
            attempt: int | None) -> dict[str, Any]:
    try:
        manifest = freeze()
    except ArtifactError as e:
        # 成果本身不合格（太大、路徑不安全）⇒ 這是成果的問題，記成 reject
        task.ledger.append("decision", {"artifact_sha256": None,
                                        "contract_sha256": task.contract.sha256,
                                        "outcome": "reject", "reasons": [f"artifact: {e}"],
                                        "coverage": {}, "results": [],
                                        "results_sha256": None, "decision_doc": None})
        return {"outcome": "reject", "reasons": [f"artifact: {e}"], "artifact_sha256": None,
                "void": False}
    except OSError as e:
        task.ledger.append("infra_void", {"stage": "freeze", "error": str(e)[:500],
                                          "attempt": attempt})
        return {"outcome": None, "void": True, "reasons": [f"freeze failed: {e}"]}
    task.ledger.append("candidate_frozen", {
        "artifact_sha256": manifest["artifact_sha256"], "n_files": len(manifest["files"]),
        "n_skipped": len(manifest.get("skipped", [])), "source": source, "attempt": attempt})
    try:
        v = _verify_manifest(task, manifest, sandbox=sandbox, store=task.store)
    except (ArtifactError, OSError) as e:
        task.ledger.append("infra_void", {"stage": "verify", "error": str(e)[:500],
                                          "artifact_sha256": manifest["artifact_sha256"],
                                          "attempt": attempt})
        return {"outcome": None, "void": True, "reasons": [f"verification failed: {e}"],
                "artifact_sha256": manifest["artifact_sha256"]}
    d = v["decision"]
    _record_decision(task, d, manifest)
    return {**d.to_json(task.contract), "n_files": len(manifest["files"]),
            "skipped": manifest.get("skipped", []), "void": False}


def check(contract: Contract, source_dir: str | pathlib.Path, *,
          sandbox: str = "auto", reveal_hidden: bool = False) -> dict[str, Any]:
    """只驗不收：暫存隔離區、不寫帳本、不需要金鑰。給 agent 在宣告完成之前自己先跑。
    隱藏主張的細節預設遮掉；`reveal_hidden` 給委託者自己看（agent 也叫得到——
    所以真正的秘密不能放在契約裡，見 `policy.HIDDEN_DETAIL`）。"""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="vacant-check-"))
    try:
        store = Store(tmp / "store")
        manifest = store.freeze(source_dir, include=contract.include,
                                exclude=contract.exclude, task_id=contract.task_id,
                                source="check")
        fake = Task(contract=contract, root=tmp, store=store,
                    ledger=Ledger(contract.task_id, tmp), trust=_keys.Trust(tmp / "t", {}))
        v = _verify_manifest(fake, manifest, sandbox=sandbox, store=store)
        return {**v["decision"].to_json(None if reveal_hidden else contract),
                "n_files": len(manifest["files"]),
                "skipped": manifest.get("skipped", []), "dry_run": True}
    except ArtifactError as e:
        return {"outcome": "reject", "reasons": [f"artifact: {e}"], "dry_run": True}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def latest_artifact(task: Task, *, outcome: str | None = None) -> str | None:
    art = None
    for ev in task.ledger.events():
        if ev["type"] == "decision" and ev.get("contract_sha256") == task.contract.sha256 \
                and ev.get("artifact_sha256") and (outcome is None or ev.get("outcome") == outcome):
            art = ev["artifact_sha256"]
    return art


def reverify(task: Task, artifact_sha256: str | None = None, *,
             sandbox: str = "auto") -> dict[str, Any]:
    """對隔離區裡**同一個**成果重新取證（例如人工審查之後）。不重新凍結。"""
    art = artifact_sha256 or latest_artifact(task)
    if not art:
        return {"outcome": None, "reasons": ["no candidate to re-verify"]}
    try:
        manifest = task.store.load_manifest(art)
        v = _verify_manifest(task, manifest, sandbox=sandbox, store=task.store)
    except (ArtifactError, OSError) as e:
        task.ledger.append("infra_void", {"stage": "reverify", "error": str(e)[:500],
                                          "artifact_sha256": art})
        return {"outcome": None, "void": True, "reasons": [str(e)]}
    _record_decision(task, v["decision"], manifest)
    return {**v["decision"].to_json(task.contract), "void": False}


def review(task: Task, *, claim_id: str, verdict: str, reason: str,
           artifact_sha256: str | None = None) -> dict[str, Any]:
    if verdict not in ("pass", "fail"):
        raise ValueError("verdict must be pass or fail")
    if claim_id not in {c.id for c in task.contract.claims}:
        raise ValueError(f"no claim {claim_id!r} in the contract")
    art = artifact_sha256 or latest_artifact(task)
    if not art:
        raise ValueError("no candidate to review")
    ident = _keys.load_or_create("reviewer", task.root)
    doc = _keys.sign_doc(ident, {"schema": "vacant-review/2", "task_id": task.task_id,
                                 "contract_sha256": task.contract.sha256,
                                 "claim_id": claim_id, "artifact_sha256": art,
                                 "verdict": verdict, "reason": reason[:2000]})
    task.ledger.append("review_recorded", {"artifact_sha256": art, "claim_id": claim_id,
                                           "verdict": verdict, "review": doc})
    return doc


def approve(task: Task, *, artifact_sha256: str | None = None,
            destination: str | None = None, ttl_s: float = _approval.DEFAULT_APPROVAL_TTL_S
            ) -> dict[str, Any]:
    art = artifact_sha256 or latest_artifact(task, outcome="accept")
    if not art:
        raise ValueError("no accepted candidate to approve")
    dest = destination or task.contract.release.get("destination")
    if not dest:
        raise ValueError("no destination (contract.release.destination or --to)")
    # 綁**解析後**的目的端：`dir:published` 在另一個目錄裡解析成另一個地方，
    # 綁字串的話同一張單次批准可以在每一份契約拷貝旁邊各用一次。
    canon = parse_destination(dest, task.contract.base_dir).canonical
    ident = _keys.load_or_create("approver", task.root)
    name = task.trust.name_of("approver", _keys.pub_hex(ident)) or "unknown"
    doc = _approval.issue(ident, approver=name, task_id=task.task_id,
                          contract_sha256=task.contract.sha256, artifact_sha256=art,
                          destination=canon, ttl_s=ttl_s)
    task.ledger.append("approval_recorded", {"artifact_sha256": art,
                                             "contract_sha256": task.contract.sha256,
                                             "destination": canon, "approver": name,
                                             "approval": doc})
    return doc


def _decision_doc_for(task: Task, art: str) -> Any:
    doc = None
    for ev in task.ledger.events():
        if ev["type"] == "decision" and ev.get("artifact_sha256") == art \
                and ev.get("contract_sha256") == task.contract.sha256:
            doc = ev.get("decision_doc")
    return doc


def _approval_for(task: Task, art: str, dest: str) -> Any:
    doc = None
    for ev in task.ledger.events():
        if ev["type"] == "approval_recorded" and ev.get("artifact_sha256") == art \
                and ev.get("destination") == dest \
                and ev.get("contract_sha256") == task.contract.sha256:
            doc = ev.get("approval")
    return doc


def _ledger_memory(task: Task, canon: str) -> tuple[set[str], bool]:
    """簽過的帳本裡：這個任務用過的批准 nonce、有沒有從這個目的端撤回過。"""
    nonces: set[str] = set()
    withdrawn = False
    for ev in task.ledger.events():
        if ev["type"] == "released" and ev.get("approval_nonce"):
            nonces.add(str(ev["approval_nonce"]))
        if ev["type"] == "withdrawn" and ev.get("canonical_destination") == canon \
                and not ev.get("noop"):
            withdrawn = True
    return nonces, withdrawn


def release(task: Task, *, artifact_sha256: str | None = None,
            destination: str | None = None, approval_doc: Any | None = None,
            trust: _keys.Trust | None = None) -> dict[str, Any]:
    art = artifact_sha256 or latest_artifact(task, outcome="accept") or latest_artifact(task)
    dest = destination or task.contract.release.get("destination")
    if not art or not dest:
        why = ["nothing to release" if not art else "no destination"]
        task.ledger.append("release_refused", {"artifact_sha256": art, "destination": dest,
                                               "reasons": why})
        return {"released": False, "reasons": why}
    tr = trust or task.trust
    res: dict[str, Any]
    try:
        rcp = parse_destination(dest, task.contract.base_dir)
        canon = rcp.canonical
        ok, why_chain = task.ledger.verify(tr)
        if not ok:
            res = {"released": False, "reasons": [f"task ledger: {why_chain}"]}
        else:
            nonces, withdrawn = _ledger_memory(task, canon)
            appr = approval_doc if approval_doc is not None else _approval_for(task, art, canon)
            res = gate_release(contract=task.contract, recipient=rcp, store=task.store,
                               artifact_sha256=art, decision_doc=_decision_doc_for(task, art),
                               approval_doc=appr, trust=tr, ledger_head=task.ledger.head(),
                               lock_doc=_lock_for(task), ledger_hashes=task.ledger.hashes(),
                               ledger_used_nonces=nonces, ledger_withdrawn=withdrawn)
    except Exception as e:  # noqa: BLE001 — 放行這一段的任何基礎設施失敗都要上帳本
        task.ledger.append("infra_void", {"stage": "release", "error": f"{type(e).__name__}: "
                                                                        f"{e}"[:500],
                                          "artifact_sha256": art})
        return {"released": False, "void": True, "reasons": [f"release failed: {e}"]}
    if res.get("released") or res.get("effect"):
        task.ledger.append("released", {
            "artifact_sha256": art, "contract_sha256": task.contract.sha256,
            "destination": dest, "canonical_destination": canon, "effect": res.get("effect"),
            "readback_ok": bool(res.get("readback_ok")),
            "readback_problems": (res.get("readback_problems") or [])[:20],
            "location": res.get("location"), "approval_nonce": res.get("approval_nonce")})
    else:
        reasons = [str(r)[:300] for r in list(res.get("reasons") or [])]
        task.ledger.append("release_refused", {"artifact_sha256": art, "destination": dest,
                                               "reasons": reasons})
    return res


def withdraw(task: Task, *, reason: str, destination: str | None = None) -> dict[str, Any]:
    dest = destination or task.contract.release.get("destination")
    if not dest:
        raise ValueError("no destination")
    try:
        rcp = parse_destination(dest, task.contract.base_dir)
        res = _withdraw(contract=task.contract, recipient=rcp, reason=reason,
                        ledger_head=task.ledger.head())
    except Exception as e:  # noqa: BLE001
        task.ledger.append("infra_void", {"stage": "withdraw",
                                          "error": f"{type(e).__name__}: {e}"[:500]})
        return {"withdrawn": False, "void": True, "readback_ok": False, "destination": dest,
                "reasons": [f"withdraw failed: {e}"], "note": "nothing is known to have changed"}
    task.ledger.append("withdrawn", {"destination": dest, "canonical_destination": rcp.canonical,
                                     "reason": reason[:500], "readback_ok": res["readback_ok"],
                                     "noop": bool(res.get("noop"))})
    return res


def status(task: Task) -> dict[str, Any]:
    evs = task.ledger.events()
    st = state_of(evs)
    last = None
    for ev in evs:
        if ev["type"] == "decision" and ev.get("contract_sha256") == task.contract.sha256:
            last = ev
    if last:
        st["latest_reasons"] = last.get("reasons")
        st["latest_results"] = last.get("results")
        st["coverage"] = last.get("coverage")
    st["ledger_verified"] = task.ledger.verify(task.trust)
    return st
