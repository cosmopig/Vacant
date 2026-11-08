"""vq-el4.7：repo 的 beads 工作區必須指向共享 vq 庫（審查指示4 固化）。

事故：110ae3ff 在 repo 跑了 `bd init`，建了獨立庫
（metadata.json dolt_database="Vacant"、project_id=01de207e-…），
使 prompt 要求的 `bd list --parent vq-el4 --all` 報 `issue not found`。
b5251fbb（r1211）修復：dolt_database 回 "vq"、project_id 回全局共享專案
7ee45eb8-…，且 `.beads/.gitignore` 補 `embeddeddolt`（機器本機 DB 不入库）。

本測試把修復後的狀態鎖進 CI：任何一次 `bd init` 同型回退（改回獨立庫、
或讓本機 embeddeddolt 庫被 commit）都會紅燈。
注意：只斷言 git-tracked 檔案（metadata.json / .gitignore）——CI worktree
沒有共享 DB 實體，不跑 bd 子程序（功能性驗收＝人工跑
`env -u BEADS_DIR bd list --parent vq-el4 --all`，預期 7 issues）。
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 共享 vq 庫（~/dev/ops/.beads，vq-* issues 所在）的 canonical 指紋。
SHARED_DB_NAME = "vq"
SHARED_PROJECT_ID = "7ee45eb8-eec3-4d1b-b15b-a7bfb2d46be6"


def _repo_beads_metadata() -> dict:
    p = REPO / ".beads" / "metadata.json"
    assert p.is_file(), "repo 缺 .beads/metadata.json（beads 工作區配置被拆掉？）"
    return json.loads(p.read_text(encoding="utf-8"))


def test_metadata_points_at_shared_vq_database() -> None:
    meta = _repo_beads_metadata()
    db = meta.get("dolt_database")
    assert db == SHARED_DB_NAME, (
        f".beads/metadata.json dolt_database={db!r}（應為 {SHARED_DB_NAME!r}）："
        "repo 工作區被指到獨立庫（110ae3ff `bd init` 同型回退），"
        "會使 `bd list --parent vq-el4 --all` 報 issue not found。"
        "修復＝把 dolt_database 改回 vq（b5251fbb 的做法），別建獨立庫。"
    )
    pid = meta.get("project_id")
    assert pid == SHARED_PROJECT_ID, (
        f".beads/metadata.json project_id={pid!r}（應為共享專案 {SHARED_PROJECT_ID}）："
        "庫名相同但專案不同，vq-* issues 仍查不到。"
    )


def test_embeddeddolt_local_db_is_git_ignored() -> None:
    gi = REPO / ".beads" / ".gitignore"
    assert gi.is_file(), "repo 缺 .beads/.gitignore"
    lines = {ln.strip() for ln in gi.read_text(encoding="utf-8").splitlines()}
    assert "embeddeddolt" in lines, (
        ".beads/.gitignore 少了 embeddeddolt：機器本機的 embeddeddolt 庫"
        "（或指向共享庫的 symlink）會被 commit 進去，污染其他 worktree。"
    )
