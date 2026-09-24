"""recipients — **真正的接受點**：放行只經過這裡，而且這裡自己重驗一切。

這支在架構裡承重什麼（報告 §04「判了拒交，不等於阻止了交付」、§06、§16「必須能推翻
自己的測試」）：

`vrun/launcher.py` 的 exit 20 是一個**判決**；檔案仍在 agent 的工作區，任何不看退出碼的
呼叫者都能 `cp` 走（`vrun/release.py` 開頭記的 abpi 那批就是活體例子）。
收件端要反過來：**目的端只從這裡取得內容**，而這裡在寫入之前自己檢查：

0. 契約本身由**收件端簽章者清單上**的 owner 鎖過（`vacant contract lock` 簽的契約鎖）——
   放行政策（要不要批准、誰能批准、能不能取代）以那一份為準，不是以呼叫者手上碰巧
   拿著的那份契約為準。
1. 裁決文件由**收件端簽章者清單上**的 verifier 簽、結論是 accept、綁定的契約雜湊與
   成果雜湊都對得上（契約改過 ⇒ 舊裁決不算）。
2. 隔離區裡的每個物件重算雜湊都對得上（批准 A 之後換成 B ⇒ 雜湊不是 A）。
3. 契約要求批准時：批准文件由簽章者清單上、且名列契約 `release.approvers` 的人簽，
   綁定同一個任務、契約、成果、**解析後的**目的端（不是設定字串——相對路徑在不同
   目錄會解析到不同地方）、動作，沒過期，nonce 沒用過（目的端的紀錄**與**簽過的帳本
   兩邊都查）。
4. 這個目的端沒有把這個任務撤回過（撤回後重送一律拒絕，要開一個新的 task_id）。
5. 目的端已經有**別的**版本 ⇒ 除非契約 `release.replace=true`，否則拒絕。
   已經有**同一個**版本 ⇒ 不重做，但 0、1 兩條照樣檢查（目的端的紀錄可以被偽造，
   契約也可能已經收緊），過了才讀回確認（冪等：逾時後重試不會發兩次）。
6. 帳本沒有被截短或換掉：收件端記下它看過的最後一筆（筆數＋雜湊），下次要看到同一筆。

寫入之後**讀回**：目的端的每個檔案重算雜湊，與隔離區清單逐一比對，
結果寫進 `released` 事件的 `readback_ok`。讀回不成立 ⇒ `release_unconfirmed`，
不是 `released`。

## 目的端種類

- `dir:<path>`：發布到 `<path>/<task_id>/`。先寫到同一個檔案系統上的暫存目錄、
  逐檔驗雜湊，再以 `rename` 原子地換上。收件端自己的紀錄在 `<path>/.vacant-recipient/`。
- `git:<repo>#<branch>[:<subdir>]`：用 git plumbing（暫存 index → write-tree →
  commit-tree → `update-ref` 帶舊值比對）把成果提交到那個分支；
  `<subdir>` 底下（或整棵樹，沒給 subdir 時）＝恰好那份成果。
  讀回＝`ls-tree` 的 blob id 與成果內容逐一比對。紀錄在 `<repo>/.git/vacant-recipient/`。

## 誠實邊界

1. **本檔只控制它自己寫的那個目的端。** 讓 agent 沒有別的路寫進正式系統
   （不同帳號、不同憑證、分支保護）是部署的事；做不到時，能宣稱的是
   「這個目的端沒有接受不合格的版本」，不能擴張成「agent 沒做任何壞事」。
2. `git:` 目的端假設下游只讀那個分支（或那個 subdir）。有人直接 push 到那個分支，
   本檔攔不住——那要靠 git 伺服器的分支保護。
3. 撤回刪得掉目的端上的檔案，**刪不掉已經被讀走的副本**（報告 §07 對撤回的同一句）。
4. 第 6 條只抓得到「收件端看過之後」的截短。同一個帳號在收件端第一次看到之前就把帳本
   截短（例如撤掉一筆後來的 reject），這裡看不出來——要靠另一個帳號上的收件端或
   外部見證（`keys.py` 誠實邊界 1 的同一件事）。
5. 「拒絕」與「結果不明」分開：在任何寫入之前就被擋下（`RecipientError`）是拒絕；
   寫到一半出錯（`OSError`）是 `effect=unknown`，帳本記 `release_unconfirmed`，先查不要重做。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
from typing import Any

from ..atomic import atomic_write_text, file_lock
from . import approval as _approval
from .artifact import ArtifactError, Store
from .contract import Contract
from .keys import Trust

RECORD_NAME = ".vacant-release.json"


class RecipientError(RuntimeError):
    pass


def parse_destination(spec: str, base_dir: pathlib.Path) -> "Recipient":
    if spec.startswith("dir:"):
        p = pathlib.Path(spec[4:]).expanduser()
        return DirRecipient(spec, p if p.is_absolute() else (base_dir / p))
    if spec.startswith("git:"):
        rest = spec[4:]
        if "#" not in rest:
            raise RecipientError("git destination must be git:<repo>#<branch>[:<subdir>]")
        repo, ref = rest.split("#", 1)
        branch, _, subdir = ref.partition(":")
        rp = pathlib.Path(repo).expanduser()
        return GitRecipient(spec, rp if rp.is_absolute() else (base_dir / rp), branch,
                            subdir.strip("/"))
    raise RecipientError(f"unknown destination {spec!r} (use dir:<path> or git:<repo>#<branch>)")


class Recipient:
    spec: str
    records: pathlib.Path

    @property
    def canonical(self) -> str:
        """解析後的目的端（批准綁的是這個，不是設定字串）。"""
        raise NotImplementedError

    # ── 收件端自己的紀錄（不依賴簽章端的帳本）─────────────────────────
    def _state(self) -> dict[str, Any]:
        p = self.records / "state.json"
        if p.is_file():
            try:
                st = json.loads(p.read_text(encoding="utf-8"))
            except ValueError as e:
                raise RecipientError(f"recipient state {p} is unreadable: {e}") from e
            if not isinstance(st, dict):
                raise RecipientError(f"recipient state {p} is not an object")
            return st
        return {"used_nonces": [], "withdrawn": [], "log": [], "witness": {}}

    def _save(self, st: dict[str, Any]) -> None:
        self.records.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.records / "state.json", json.dumps(st, indent=2) + "\n")

    def lock(self):
        self.records.mkdir(parents=True, exist_ok=True)
        return file_lock(self.records / "lock")

    # ── 子類別 ──────────────────────────────────────────────────────
    def current(self, task_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def _publish(self, task_id: str, manifest: dict[str, Any], store: Store,
                 record: dict[str, Any], replace: bool) -> str:
        raise NotImplementedError

    def readback(self, task_id: str, manifest: dict[str, Any]) -> tuple[bool, list[str]]:
        raise NotImplementedError

    def _withdraw(self, task_id: str, record: dict[str, Any]) -> None:
        raise NotImplementedError

    def occupied_unmanaged(self, task_id: str) -> bool:
        return False

    def location(self, task_id: str) -> str:
        raise NotImplementedError


class DirRecipient(Recipient):
    def __init__(self, spec: str, root: pathlib.Path):
        self.spec = spec
        self.root = root.resolve()
        self.records = self.root / ".vacant-recipient"

    @property
    def canonical(self) -> str:
        return f"dir:{self.root}"

    def location(self, task_id: str) -> str:
        return str(self.root / task_id)

    def current(self, task_id: str) -> dict[str, Any] | None:
        rec = self.root / task_id / RECORD_NAME
        if rec.is_file():
            try:
                return json.loads(rec.read_text(encoding="utf-8"))
            except ValueError as e:
                raise RecipientError(f"the destination's release record is unreadable: {e}") \
                    from e
        return None

    def occupied_unmanaged(self, task_id: str) -> bool:
        """目的端有這個任務的目錄（或連結），卻沒有收件端寫的紀錄。"""
        t = self.root / task_id
        return (t.exists() or t.is_symlink()) and not (t / RECORD_NAME).is_file()

    def _publish(self, task_id, manifest, store, record, replace):
        target = self.root / task_id
        if (target.exists() or target.is_symlink()) and not replace:
            raise RecipientError("destination already holds another version")
        stage = self.root / ".vacant-staging" / f"{task_id}-{os.getpid()}-{time.time_ns()}"
        stage.parent.mkdir(parents=True, exist_ok=True)
        try:
            store.materialize(manifest, stage)
            atomic_write_text(stage / RECORD_NAME, json.dumps(record, indent=2) + "\n")
            if target.exists():
                if not replace:
                    raise RecipientError("destination already holds another version")
                old = self.root / ".vacant-superseded" / f"{task_id}-{_stamp()}"
                old.parent.mkdir(parents=True, exist_ok=True)
                os.rename(target, old)
            os.rename(stage, target)
        finally:
            if stage.exists():
                shutil.rmtree(stage, ignore_errors=True)
        return "published"

    def readback(self, task_id, manifest):
        target = self.root / task_id
        probs = []
        want = {f["path"]: f["sha256"] for f in manifest.get("files", [])}
        seen = set()
        for p in sorted(target.rglob("*")) if target.is_dir() else []:
            if not p.is_file():
                continue
            rel = p.relative_to(target).as_posix()
            if rel == RECORD_NAME:
                continue
            seen.add(rel)
            if rel not in want:
                probs.append(f"unexpected file at destination: {rel}")
            elif _sha256(p.read_bytes()) != want[rel]:
                probs.append(f"{rel}: content at destination differs")
        for rel in sorted(set(want) - seen):
            probs.append(f"{rel}: missing at destination")
        return (not probs), probs

    def _withdraw(self, task_id, record):
        target = self.root / task_id
        if target.exists():
            dst = self.root / ".vacant-withdrawn" / f"{task_id}-{_stamp()}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.rename(target, dst)
            atomic_write_text(dst / ".vacant-withdrawn.json", json.dumps(record, indent=2))


class GitRecipient(Recipient):
    def __init__(self, spec: str, repo: pathlib.Path, branch: str, subdir: str):
        self.spec = spec
        self.repo = repo.resolve()
        self.branch = branch
        self.subdir = subdir
        gd = self._git("rev-parse", "--git-dir").strip()
        gdp = pathlib.Path(gd)
        self.records = (gdp if gdp.is_absolute() else self.repo / gdp) / "vacant-recipient"

    @property
    def canonical(self) -> str:
        return f"git:{self.repo}#{self.branch}:{self.subdir}"

    def location(self, task_id: str) -> str:
        return f"{self.repo}#{self.branch}:{self.subdir}"

    def occupied_unmanaged(self, task_id: str) -> bool:
        return False

    def _git(self, *args: str, input_bytes: bytes | None = None,
             env: dict[str, str] | None = None) -> str:
        e = dict(os.environ)
        e.update({"GIT_TERMINAL_PROMPT": "0", "GIT_AUTHOR_NAME": "vacant",
                  "GIT_AUTHOR_EMAIL": "vacant@localhost", "GIT_COMMITTER_NAME": "vacant",
                  "GIT_COMMITTER_EMAIL": "vacant@localhost"})
        if env:
            e.update(env)
        cp = subprocess.run(["git", "-C", str(self.repo), *args], input=input_bytes,
                            capture_output=True, env=e)
        if cp.returncode != 0:
            raise RecipientError(f"git {' '.join(args[:2])} failed: "
                                 f"{cp.stderr.decode('utf-8', 'replace').strip()[:400]}")
        return cp.stdout.decode("utf-8", "replace")

    def _tip(self) -> str | None:
        try:
            return self._git("rev-parse", "--verify", "-q",
                             f"refs/heads/{self.branch}^{{commit}}").strip() or None
        except RecipientError:
            return None

    def current(self, task_id: str) -> dict[str, Any] | None:
        """這個任務在分支上**最近一次**由收件端寫的提交（不只看分支頂端——
        別的任務在同一條分支上發布之後，頂端就不是這個任務的了）。"""
        tip = self._tip()
        if not tip:
            return None
        log = self._git("log", "-F", f"--grep=Vacant-Task: {task_id}", "-n", "500",
                        "--format=%H%x1f%B%x1e", tip)
        for chunk in log.split("\x1e"):
            if "\x1f" not in chunk:
                continue
            commit, msg = chunk.strip("\n").split("\x1f", 1)
            tr = {}
            for line in msg.splitlines():
                if line.startswith("Vacant-") and ":" in line:
                    k, v = line.split(":", 1)
                    tr[k.strip()] = v.strip()
            if tr.get("Vacant-Task") == task_id:          # -F 是子字串比對，這裡要完全相等
                return {"artifact_sha256": tr.get("Vacant-Artifact"), "commit": commit.strip(),
                        "withdrawn": tr.get("Vacant-Withdrawn") == "true"}
        return None

    def _publish(self, task_id, manifest, store, record, replace):
        cur = self.current(task_id)
        if cur and not cur.get("withdrawn") and not replace:
            raise RecipientError("destination branch already holds another version")
        tip = self._tip()
        with tempfile.TemporaryDirectory() as td:
            idx = {"GIT_INDEX_FILE": str(pathlib.Path(td) / "index")}
            if tip:
                self._git("read-tree", tip, env=idx)
                if self.subdir:
                    self._git("rm", "-r", "-q", "--cached", "--ignore-unmatch", "--",
                              self.subdir, env=idx)
                else:
                    self._git("read-tree", "--empty", env=idx)
            for f in manifest["files"]:
                data = store.object_path(f["sha256"]).read_bytes()
                if _sha256(data) != f["sha256"]:
                    raise ArtifactError(f"{f['path']}: quarantine object changed")
                blob = self._git("hash-object", "-w", "--stdin", input_bytes=data).strip()
                path = f"{self.subdir}/{f['path']}" if self.subdir else f["path"]
                mode = "100755" if f.get("exec") else "100644"
                self._git("update-index", "--add", "--cacheinfo", f"{mode},{blob},{path}",
                          env=idx)
            tree = self._git("write-tree", env=idx).strip()
        msg = (f"vacant: release {task_id}\n\n"
               f"Vacant-Task: {task_id}\nVacant-Artifact: {manifest['artifact_sha256']}\n"
               f"Vacant-Contract: {record['contract_sha256']}\n"
               f"Vacant-Ledger-Head: {record.get('ledger_head')}\n")
        args = ["commit-tree", tree, "-m", msg]
        if tip:
            args[2:2] = ["-p", tip]
        commit = self._git(*args).strip()
        # 帶舊值的 update-ref ＝ compare-and-swap：別人在這之間動過分支就失敗，不覆蓋
        self._git("update-ref", f"refs/heads/{self.branch}", commit, tip or "0" * 40)
        return "published"

    def readback(self, task_id, manifest):
        tip = self._tip()
        if not tip:
            return False, ["branch does not exist"]
        # `-z`：沒有它，非 ASCII／含 tab 或引號的路徑會被加上引號跳脫 ⇒ 被報成缺檔，
        # 而且多出來的那種檔案躲得過「不該在這裡的檔案」檢查。
        listing = self._git("ls-tree", "-r", "-z", "--full-tree", tip)
        have = {}
        modes = {}
        for rec in listing.split("\0"):
            if not rec:
                continue
            meta, path = rec.split("\t", 1)
            mode, typ, sha = meta.split()
            if typ == "blob":
                have[path] = sha
                modes[path] = mode
        probs = []
        prefix = f"{self.subdir}/" if self.subdir else ""
        want = {prefix + f["path"]: f for f in manifest["files"]}
        for path, f in want.items():
            if path not in have:
                probs.append(f"{path}: missing on branch")
                continue
            raw = subprocess.run(["git", "-C", str(self.repo), "cat-file", "blob", have[path]],
                                 capture_output=True).stdout
            if _sha256(raw) != f["sha256"]:
                probs.append(f"{path}: content on branch differs")
            elif modes.get(path) != ("100755" if f.get("exec") else "100644"):
                probs.append(f"{path}: mode on branch differs")
        extra = [p for p in have if p.startswith(prefix) and p not in want]
        probs += [f"unexpected file on branch: {p}" for p in extra[:20]]
        return (not probs), probs

    def _withdraw(self, task_id, record):
        tip = self._tip()
        if not tip:
            return
        with tempfile.TemporaryDirectory() as td:
            idx = {"GIT_INDEX_FILE": str(pathlib.Path(td) / "index")}
            self._git("read-tree", tip, env=idx)
            if self.subdir:
                self._git("rm", "-r", "-q", "--cached", "--ignore-unmatch", "--",
                          self.subdir, env=idx)
            else:
                self._git("read-tree", "--empty", env=idx)
            tree = self._git("write-tree", env=idx).strip()
        msg = (f"vacant: withdraw {task_id}\n\nVacant-Task: {task_id}\n"
               f"Vacant-Withdrawn: true\nVacant-Reason: {record.get('reason', '')[:200]}\n")
        commit = self._git("commit-tree", tree, "-p", tip, "-m", msg).strip()
        self._git("update-ref", f"refs/heads/{self.branch}", commit, tip)


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def gate_release(*, contract: Contract, recipient: Recipient, store: Store,
                 artifact_sha256: str, decision_doc: Any, approval_doc: Any | None,
                 trust: Trust, ledger_head: str | None, lock_doc: Any = None,
                 ledger_hashes: list[str] | None = None,
                 ledger_used_nonces: set[str] | frozenset[str] = frozenset(),
                 ledger_withdrawn: bool = False,
                 now: float | None = None) -> dict[str, Any]:
    """收件端的全部檢查＋發布＋讀回。回傳 `{"released": bool, "reasons": [...], ...}`。

    ⚠ 這個函式簽名裡沒有任何退出碼、沒有「agent 說它完成了」——那些都不是收件的依據。
    `ledger_*` 是呼叫端從**簽過的帳本**讀出來的：撤回與用過的 nonce 兩邊都記，
    刪掉目的端的 `state.json` 不會讓用過的批准或撤回過的任務復活。
    """
    task_id = contract.task_id
    rel = contract.release
    out: dict[str, Any] = {"released": False, "task_id": task_id,
                           "artifact_sha256": artifact_sha256, "destination": recipient.spec,
                           "canonical_destination": recipient.canonical, "reasons": []}
    with recipient.lock():
        st = recipient._state()
        reasons: list[str] = []
        if task_id in st.get("withdrawn", []) or ledger_withdrawn:
            reasons.append("this task was withdrawn from this destination; "
                           "open a new task (a new task_id) to deliver again")
        # 6. 帳本沒有被截短或換掉（收件端看過的最後一筆還在原位）
        wit = (st.get("witness") or {}).get(task_id)
        rolled_back = False
        if wit and ledger_hashes is not None:
            n, h = int(wit.get("n", 0)), wit.get("hash")
            if len(ledger_hashes) < n or ledger_hashes[n - 1] != h:
                rolled_back = True
                reasons.append("the task ledger no longer contains an entry this recipient "
                               "already saw (it was truncated or replaced)")
        # 0／1：契約鎖與裁決——冪等路徑也要過（目的端紀錄可偽造、契約可能已收緊）
        reasons += _approval.check_lock(lock_doc, trust=trust, task_id=task_id,
                                        contract_sha256=contract.sha256)
        reasons += _approval.check_decision(decision_doc, trust=trust, task_id=task_id,
                                            contract_sha256=contract.sha256,
                                            artifact_sha256=artifact_sha256)
        cur = recipient.current(task_id)
        if cur and cur.get("artifact_sha256") == artifact_sha256 and not cur.get("withdrawn"):
            # 冪等：同一個版本已經在目的端 ⇒ 只讀回、不再產生任何效果、不消耗批准。
            # （逾時後重試的正確行為是「先查是否已執行」，不是再做一次——報告 §12。）
            if reasons:
                if not rolled_back:
                    _witness(st, task_id, ledger_hashes)
                    recipient._save(st)
                out["reasons"] = ["the destination already holds this version, but it is not "
                                  "authorized under the current contract:"] + reasons
                return out
            try:
                m0 = store.load_manifest(artifact_sha256)
                ok, probs = recipient.readback(task_id, m0)
            except ArtifactError as e:
                ok, probs = False, [str(e)]
            _witness(st, task_id, ledger_hashes)
            recipient._save(st)
            out.update(effect="already_published", readback_ok=ok, readback_problems=probs,
                       location=recipient.location(task_id), released=ok,
                       reasons=[] if ok else probs)
            return out
        try:
            manifest = store.load_manifest(artifact_sha256)
            reasons += [f"quarantine: {p}" for p in store.integrity_problems(manifest)]
        except ArtifactError as e:
            manifest = None
            reasons.append(f"quarantine: {e}")
        nonce = None
        if rel.get("requires_approval"):
            if approval_doc is None:
                reasons.append("the contract requires an approval and none was given")
            else:
                reasons += _approval.check(
                    approval_doc, trust=trust, task_id=task_id,
                    contract_sha256=contract.sha256, artifact_sha256=artifact_sha256,
                    destination=recipient.canonical, allowed=list(rel.get("approvers") or []),
                    used_nonces=set(st.get("used_nonces", [])) | set(ledger_used_nonces),
                    now=now)
                nonce = (approval_doc.get("payload") or {}).get("nonce")
        if cur and not cur.get("withdrawn") and not rel.get("replace"):
            reasons.append("destination already holds a different version of this task "
                           "(set release.replace=true to supersede it)")
        elif not cur and recipient.occupied_unmanaged(task_id) and not rel.get("replace"):
            reasons.append("the destination path for this task exists but was not written by "
                           "this recipient (refusing to overwrite it)")
        if reasons:
            if not rolled_back:      # 拒絕也算「看過」：之後的截短一樣抓得到
                _witness(st, task_id, ledger_hashes)
                recipient._save(st)
            out["reasons"] = reasons
            return out
        assert manifest is not None
        record = {"schema": "vacant-release/3", "task_id": task_id,
                  "artifact_sha256": artifact_sha256, "contract_sha256": contract.sha256,
                  "files": manifest["files"], "decision": decision_doc, "lock": lock_doc,
                  "approval": approval_doc, "ledger_head": ledger_head,
                  "released_at": time.time()}
        try:
            effect = recipient._publish(task_id, manifest, store, record,
                                        bool(rel.get("replace")))
        except (RecipientError, ArtifactError) as e:
            # 在任何寫入之前就被擋下（佔用、分支在這之間被動過、隔離區物件變了）⇒ 拒絕
            out["reasons"] = [f"publish refused before writing: {e}"]
            return out
        except OSError as e:
            out["reasons"] = [f"publish failed part-way: {e}"]
            out["effect"] = "unknown"
            return out
        if nonce:
            st.setdefault("used_nonces", []).append(nonce)
        ok, probs = recipient.readback(task_id, manifest)
        st.setdefault("log", []).append({"t": time.time(), "event": "released",
                                         "task_id": task_id,
                                         "artifact_sha256": artifact_sha256,
                                         "ledger_head": ledger_head, "readback_ok": ok})
        _witness(st, task_id, ledger_hashes)
        recipient._save(st)
        out.update(released=ok, effect=effect, readback_ok=ok, readback_problems=probs,
                   location=recipient.location(task_id), approval_nonce=nonce)
        return out


def _witness(st: dict[str, Any], task_id: str, ledger_hashes: list[str] | None) -> None:
    if ledger_hashes:
        st.setdefault("witness", {})[task_id] = {"n": len(ledger_hashes),
                                                 "hash": ledger_hashes[-1]}


def withdraw(*, contract: Contract, recipient: Recipient, reason: str,
             ledger_head: str | None) -> dict[str, Any]:
    task_id = contract.task_id
    with recipient.lock():
        st = recipient._state()
        cur0 = recipient.current(task_id)
        if cur0 is None or cur0.get("withdrawn"):
            # 目的端上沒有這個任務的版本：不是撤回，是空操作。記成撤回的話，這個任務
            # 之後每一個被接受的版本都會永遠被拒（2026-09-24 對抗審查重現）。
            return {"withdrawn": False, "noop": True, "readback_ok": True,
                    "destination": recipient.spec,
                    "note": "nothing from this task is at the destination; nothing changed"}
        record = {"task_id": task_id, "reason": reason, "ledger_head": ledger_head,
                  "withdrawn_at": time.time()}
        recipient._withdraw(task_id, record)
        if task_id not in st.setdefault("withdrawn", []):
            st["withdrawn"].append(task_id)
        cur = recipient.current(task_id)
        gone = cur is None or bool(cur.get("withdrawn"))
        st.setdefault("log", []).append({"t": time.time(), "event": "withdrawn",
                                         "task_id": task_id, "readback_ok": gone})
        recipient._save(st)
    return {"withdrawn": True, "readback_ok": gone, "destination": recipient.spec,
            "note": "copies already fetched by others are outside this guarantee"}
