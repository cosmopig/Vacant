"""原始資料歸檔（2026-09-27；人類要求「每個檔案 raw data log 都要記錄保存清楚」）。

這支在架構裡承重什麼：2026-09-27 容器回到舊的快照，留出批次約 270 跑的原始資料只活在暫存區、全部遺失
（`ops/eval/evidence_20260926_local/RUNLOG.md` §15）。之後每一個批次跑的時候，原始資料**定期**進 repo：

- 每一跑有 `result.json` 的 Harbor 目錄（pi 事件流、軌跡、Vacant 的病歷與交件說明、評分器輸出）整包；
- 代理的全文紀錄（`io.jsonl`）與逐通帳（`ledger.jsonl`）裡屬於這些跑的行（依標籤）；
- 驅動的 `progress.jsonl`、`driver*.log`（每次覆蓋成最新）。

每次呼叫只收**還沒歸檔**的跑，打成 `raw/chunk_NNN.tar.xz`（每個 < `--max-mb`，預設 85 MB），`raw/MANIFEST.jsonl` 一行一包：
包的 sha256、大小、裡面的跑（`<組>-s<次>/<job>/<trial>`）、io／ledger 的行數與 sha256。已經歸檔的跑之後又被改（例如補跑移開）
不會重包——那是 `_void_first/` 的事，它會被當成新的目錄歸檔。不讀任何評分的值。

    python3 ops/eval/local/archive_raw.py --jobs <jobs 根目錄> --ledger <代理 ledger 目錄> --prefix <標籤前綴> --out <repo 裡的證據目錄>
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import lzma
import pathlib
import re
import tarfile
import time
from typing import Any

EXCLUDE = re.compile(r"/vacant_home/trace/projects/[^/]+/content[^/]*(/|$)|/agent/sessions/")


def sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def trial_dirs(jobs: pathlib.Path) -> list[pathlib.Path]:
    out = [t.parent for t in jobs.glob("*/*/*__*/result.json")]
    out += [t.parent for t in jobs.glob("_void_first/*/*__*/result.json")]
    return sorted(set(out))


def rel(jobs: pathlib.Path, t: pathlib.Path) -> str:
    return str(t.relative_to(jobs))


def tag_of(t: pathlib.Path) -> str | None:
    """Harbor 的 job 名＝代理的標籤（run_local.sh：`--job-name "$TAG"`）；補跑移開的目錄名是 `<組>-s<次>__<job>`。"""
    job = t.parent.name
    return job.split("__", 1)[1] if "__" in job else job


def lines_for(path: pathlib.Path, tags: set[str]) -> list[str]:
    if not path.is_file():
        return []
    out = []
    with path.open(encoding="utf-8", errors="replace") as f:
        for ln in f:
            m = re.search(r'"tag": "([^"]+)"', ln[:500])
            if m and m.group(1) in tags:
                out.append(ln if ln.endswith("\n") else ln + "\n")
    return out


def add_bytes(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    ti = tarfile.TarInfo(name)
    ti.size = len(data)
    ti.mtime = int(time.time())
    tar.addfile(ti, io.BytesIO(data))


def pack(jobs: pathlib.Path, ledger: pathlib.Path, runs: list[pathlib.Path], dest: pathlib.Path) -> dict[str, Any]:
    tags = {tag_of(t) for t in runs} - {None}
    io_lines = lines_for(ledger / "io.jsonl", tags)            # type: ignore[arg-type]
    led_lines = lines_for(ledger / "ledger.jsonl", tags)      # type: ignore[arg-type]
    with lzma.open(dest, "wb", preset=6) as xz, tarfile.open(fileobj=xz, mode="w") as tar:
        for t in runs:
            for f in sorted(t.rglob("*")):
                s = str(f)
                if f.is_file() and not EXCLUDE.search(s):
                    tar.add(f, arcname="runs/" + str(f.relative_to(jobs)), recursive=False)
        add_bytes(tar, "proxy/io.jsonl", "".join(io_lines).encode())
        add_bytes(tar, "proxy/ledger.jsonl", "".join(led_lines).encode())
    return {"runs": [rel(jobs, t) for t in runs], "tags": sorted(tags),
            "io_lines": len(io_lines), "ledger_lines": len(led_lines),
            "io_sha256": hashlib.sha256("".join(io_lines).encode()).hexdigest()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--ledger", required=True, type=pathlib.Path)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--max-mb", type=float, default=85.0)
    ap.add_argument("--runs-per-chunk", type=int, default=40)
    a = ap.parse_args(argv)
    raw = a.out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    man = raw / "MANIFEST.jsonl"
    done: set[str] = set()
    n = 0
    if man.is_file():
        for ln in man.read_text().splitlines():
            if ln.strip():
                d = json.loads(ln)
                done.update(d["runs"])
                n = max(n, int(d["chunk"]))
    todo = [t for t in trial_dirs(a.jobs) if rel(a.jobs, t) not in done]
    new = []
    i = 0
    size = a.runs_per_chunk
    while i < len(todo):
        group = todo[i:i + size]
        n += 1
        dest = raw / f"chunk_{n:03d}.tar.xz"
        rec = pack(a.jobs, a.ledger, group, dest)
        mb = dest.stat().st_size / 1e6
        if mb > a.max_mb and len(group) > 1:                  # 太大：這一包重來、每包少一半
            dest.unlink()
            n -= 1
            size = max(1, len(group) // 2)
            continue
        rec.update(chunk=n, file=dest.name, bytes=dest.stat().st_size, sha256=sha256(dest),
                   created=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), prefix=a.prefix)
        with man.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        new.append({k: rec[k] for k in ("chunk", "file", "bytes", "io_lines", "ledger_lines")} | {"runs": len(group)})
        i += len(group)
        size = a.runs_per_chunk
    for f in ("progress.jsonl",):
        if (a.jobs / f).is_file():
            (a.out / f).write_bytes((a.jobs / f).read_bytes())
    for f in sorted(a.jobs.glob("driver*.log")) + sorted(a.jobs.glob("rerun_void*.json")):
        (a.out / f.name).write_bytes(f.read_bytes())
    print(json.dumps({"new_chunks": new, "archived_runs_total": len(done) + sum(x["runs"] for x in new)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
