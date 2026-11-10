#!/usr/bin/env python3
"""下載 Twin-2K-500 的 wave_split，轉成倉庫外的參與者目錄。

不帶 --fixture 時會連到 Hugging Face，把 parquet 放進快取（預設
~/.cache/vacant/twin2k500）。不把資料寫進 git。persona_summary 讀到也丟掉。

    python3 ops/personal_pilot/datasets/twin2k500.py --participants 20 --seed 20261109 --out ~/vacant-twin2k-20
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vacant_network.personal.twin2k import (  # noqa: E402
    DATASET_CONFIG,
    DATASET_ID,
    DEFAULT_CACHE,
    Twin2kError,
    assert_outside_repo,
    load_rows_json,
    prepare_rows,
)

CHUNK_API = "https://huggingface.co/api/datasets/LLM-Digital-Twin/Twin-2K-500/tree/main/wave_split/chunks"
RESOLVE = "https://huggingface.co/datasets/LLM-Digital-Twin/Twin-2K-500/resolve/main/"


def _download(url: str, dest: Path, timeout: int = 120) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_suffix(dest.suffix + ".partial")
    with urllib.request.urlopen(url, timeout=timeout) as response, temporary.open("wb") as handle:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            handle.write(chunk)
    temporary.replace(dest)


def ensure_parquet(cache: Path) -> list[Path]:
    raw = assert_outside_repo(cache) / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(CHUNK_API, timeout=60) as response:
        listing = json.load(response)
    paths = []
    for item in listing:
        path = item.get("path") or ""
        if not path.endswith(".parquet"):
            continue
        dest = raw / Path(path).name
        if not dest.is_file():
            _download(RESOLVE + path, dest)
        paths.append(dest)
    if not paths:
        raise Twin2kError("wave_split chunk listing contained no parquet files")
    return paths


def rows_from_parquet(paths: list[Path]) -> list[dict]:
    try:
        import pyarrow.parquet as pq
    except ImportError:
        pq = None
    if pq is not None:
        rows = []
        for path in paths:
            table = pq.read_table(path)
            rows.extend(table.to_pylist())
        return rows
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise Twin2kError(
            "reading the parquet cache needs pyarrow or datasets. "
            "Install one of them, or pass --fixture for the synthetic file. "
            f"Original error: {exc}"
        ) from exc
    dataset = load_dataset(DATASET_ID, DATASET_CONFIG, split="data")
    return [dict(row) for row in dataset]


def load_wave_split(cache: Path | None = None) -> list[dict]:
    cache_dir = assert_outside_repo(cache or DEFAULT_CACHE)
    cached_rows = cache_dir / "rows.jsonl"
    if cached_rows.is_file():
        rows = []
        for line in cached_rows.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
    paths = ensure_parquet(cache_dir)
    rows = rows_from_parquet(paths)
    cached_rows.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert Twin-2K-500 wave_split. Does not commit data.")
    parser.add_argument("--participants", type=int, default=None)
    parser.add_argument("--seed", type=int, default=20261109)
    parser.add_argument("--cache", default=str(DEFAULT_CACHE))
    parser.add_argument("--out", required=True)
    parser.add_argument("--fixture", help="local JSON shaped like the dataset; skips the download")
    args = parser.parse_args(argv)
    try:
        if args.fixture:
            rows = load_rows_json(Path(args.fixture))
        else:
            rows = load_wave_split(Path(args.cache))
        manifest = prepare_rows(rows, Path(args.out), n=args.participants, seed=args.seed)
    except (Twin2kError, OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"out": str(Path(args.out).expanduser().resolve()), "pids": manifest["pids"], "persona_summary_used": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
