"""twin/pair_receipts — 每一份 lifecycle 錄影配一份**它自己那一批**的收據資料包。

## 這支在架構裡承重什麼

電視播的是錄影（`recordings/<名字>.jsonl`）；觀眾掃了 `/r/<cell>` 要能在自己的
瀏覽器裡**重驗那一跑的簽章鏈**。在此之前收據頁只內嵌 `twin_pack.json`（54 格
L-real 那一批），而 fixture 錄影與它共用 `cell_id`、鏈卻不同 ⇒ `serve_twin`
只能照實回 404。這一支補的是那一格：

```
 run_twin.py --events L.jsonl --out RUNS      （同一次執行產生兩樣東西）
      │                      │
      ▼                      ▼
 recordings/X.jsonl     pair_receipts.py --recording X.jsonl --runs RUNS
 （電視事件的來源）      → recordings/X.pack.json（收據頁的資料，綁 X.jsonl 的 sha256）
```

`serve_twin` 載入 `X.jsonl` 時一併載入 `X.pack.json`，用同一頁收據頁
（`examples/twin_viewer.html`）換掉內嵌資料現做一頁 `/v/X.html`。

## 綁定：兩道，缺一不收（`check_pair`）

1. **sha256**：`pack["recording"]["sha256"]` ＝ 錄影檔逐位元組的 sha256。
   錄影換了、收據沒換（或反過來）⇒ 不收。
2. **逐格鏈頭**：錄影裡每一格 ON 那一跑的 `run_ended.verdict_hash`，
   都要等於資料包裡那一格簽章鏈的鏈頭（`LogEntry.hash()`）；**兩邊的格子集合要相等**
   （錄影有收據的格、資料包的格）。這一道不靠 sha256：就算有人連 sha256 一起改，
   鏈頭對不上照樣不收。`serve_twin` 的 `/r/<cell>` 另外還有第三道（電視上演的
   那一跑的鏈頭＝收據頁那一條的鏈頭才轉），三道各自獨立。

外加一條：建置機的絕對路徑不准進資料包（它會印上展場的收據頁）。

### 旁註（`X.sidecar.jsonl`，2026-09-24 加）也在綁定裡（`check_sidecar`）

分身自己的旁註（`sidecar.py`：OFF 臂的事後稽核）放在錄影旁邊另一個檔，
所以第 1 道的 sha256 **原本涵蓋不到它**。補法是資料包另外綁一個
`pack["recording"]["sidecar"] = {file, sha256, lines}`，三種情形都不收：

- 旁註在、資料包沒綁它（沒被綁的註不准跟著錄影上展場）；
- 資料包綁了旁註、旁註不在（有人刪掉了事後稽核，畫面會少一句話卻不自知）；
- sha256 對不上（改了旁註任何一個位元組）。

兩邊都沒有（舊錄影）＝合格：那份錄影就是沒有 postaudit，電視上也不會有。

## 誠實邊界

1. 綁定證明的是「這份收據與這份錄影是**同一次執行**的產物」，**不證明**那次執行
   本身對不對——那要看收據鏈自己驗不驗得過（收據頁在觀眾瀏覽器裡從創世重算）。
2. **不准拿舊 run 目錄配新錄影。** 鏈頭對不上就是不收；這支不提供「放寬」的旗標。
3. 錄影與 run 目錄必須是**同一次** `run_twin.py` 產的。事後替沒有錄影的舊批次
   補錄影（把 run 目錄轉成 lifecycle）是被禁止的事後推導，這支也不做。

用法：
    python3 ops/exhibit/twin/pair_receipts.py --recording recordings/X.jsonl --runs <RUNS>
    python3 ops/exhibit/twin/pair_receipts.py --check --recording recordings/X.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import pack as packlib  # noqa: E402
from ops.exhibit.twin import sidecar as sidecarlib  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402

#: 會印上展場螢幕的東西裡不准出現的建置機路徑（與 `serve_twin.PATH_LEAKS` 同一份）。
PATH_LEAKS = ("/Users/", "/home/", "/private/var/", "worktrees/agent-")


def pair_path(recording: pathlib.Path) -> pathlib.Path:
    """`X.jsonl` → `X.pack.json`（同目錄、同名）。"""
    recording = pathlib.Path(recording)
    return recording.with_name(recording.stem + ".pack.json")


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def chain_head(cell: dict) -> str | None:
    if not cell.get("chain"):
        return None
    from vacant_network.logbook import LogEntry
    return LogEntry.from_json(json.loads(cell["chain"][-1])).hash()


def recording_heads(evs: list[dict]) -> dict[str, str | None]:
    """錄影裡每一格 ON 那一跑的 `verdict_hash`（沒簽收據的格是 None）。"""
    cell_of: dict[str, str] = {}
    out: dict[str, str | None] = {}
    for e in evs:
        if e["type"] == "run_started":
            cell_of[e["run_id"]] = (e.get("caller") or {}).get("cell_id") or e["task_id"]
        elif e["type"] == "run_ended" and e["arm"] == packlib.ARM:
            cid = cell_of.get(e["run_id"])
            if cid is not None and cid not in out:
                out[cid] = e.get("verdict_hash")
    return out


def check_sidecar(recording: pathlib.Path, pack: dict) -> list[str]:
    """旁註的 sha256 綁定（模組 docstring「旁註也在綁定裡」）。回問題清單。"""
    sc = sidecarlib.sidecar_path(recording)
    bind = (pack.get("recording") or {}).get("sidecar")
    if bind is None:
        if sc.exists():
            return [f"旁註 {sc.name} 在，資料包卻沒有綁它（沒被綁的註不准跟著錄影上展場）"]
        return []
    if not sc.exists():
        return [f"資料包綁了旁註 {bind.get('file')!r}，旁註卻不在（事後稽核被拿掉了）"]
    got = sha256_file(sc)
    if bind.get("sha256") != got:
        return [f"旁註 sha256 綁定對不上：收據綁的是 {str(bind.get('sha256'))[:12]}…，"
                f"旁註是 {got[:12]}…（旁註或收據其中一個換過）"]
    return []


def check_pair(recording: pathlib.Path, pack: dict, *, pack_text: str | None = None
               ) -> list[str]:
    """兩道綁定＋路徑不外漏。回問題清單（空＝這份收據就是這份錄影的）。"""
    recording = pathlib.Path(recording)
    bad: list[str] = []
    bind = pack.get("recording") or {}
    got = sha256_file(recording)
    if bind.get("sha256") != got:
        bad.append(f"sha256 綁定對不上：收據綁的是 {str(bind.get('sha256'))[:12]}…，"
                   f"錄影是 {got[:12]}…（錄影或收據其中一個換過）")
    bad += check_sidecar(recording, pack)
    text = pack_text if pack_text is not None else json.dumps(pack, ensure_ascii=False)
    bad += [f"建置機的路徑漏進收據資料包：{leak}" for leak in PATH_LEAKS if leak in text]
    heads = {cid: h for cid, h in recording_heads(lifecycle.read(recording)).items()
             if h is not None}
    packed = {c["cell_id"]: chain_head(c) for c in pack.get("cells") or []}
    for cid in sorted(set(heads) - set(packed)):
        bad.append(f"{cid}：錄影裡有收據，資料包裡沒有這一格")
    for cid in sorted(set(packed) - set(heads)):
        bad.append(f"{cid}：資料包裡有，錄影裡沒有這一格的收據（不是同一批）")
    for cid in sorted(set(heads) & set(packed)):
        if heads[cid] != packed[cid]:
            bad.append(f"{cid}：鏈頭對不上（錄影 {heads[cid][:12]}… ≠ "
                       f"收據 {str(packed[cid])[:12]}…）")
    return bad


def build_pair(recording: pathlib.Path, runs_root: pathlib.Path) -> dict:
    """同一次執行的 run 目錄 → 綁在這份錄影上的收據資料包。對不上就 `SystemExit`。"""
    recording, runs_root = pathlib.Path(recording), pathlib.Path(runs_root).resolve()
    pack = packlib.build(runs_root)
    # `source.runs` 會印上收據頁。run 目錄在 repo 裡就寫相對路徑；
    # 不在（例如 record_fixture.sh 的暫存目錄，錄完就刪）就只寫它是哪一批。
    pack["source"]["runs"] = (
        str(runs_root.relative_to(REPO)) if runs_root.is_relative_to(REPO)
        else f"（錄影 {recording.name} 的同一次執行；run 目錄不在 repo 裡）")
    pack["recording"] = {
        "file": recording.name,
        "sha256": sha256_file(recording),
        "lines": len(lifecycle.read(recording)),
        "note": "這份收據與同名錄影是同一次 run_twin.py 的產物。serve_twin 載入前會驗 "
                "sha256 與逐格鏈頭，對不上就不收。",
    }
    sc = sidecarlib.sidecar_path(recording)
    if sc.exists():
        rows = sidecarlib.read(sc)
        sbad = sidecarlib.validate(rows, lifecycle_events=lifecycle.read(recording))
        if sbad:
            raise SystemExit("旁註綁不上這份錄影，不寫：\n  " + "\n  ".join(sbad[:8]))
        pack["recording"]["sidecar"] = {
            "file": sc.name, "sha256": sha256_file(sc), "lines": len(rows),
            "note": "分身自己的旁註（OFF 臂事後稽核，不是 Vacant 的事件）。"
                    "與錄影同一次執行；改一個位元組 serve_twin 就不收。",
        }
    bad = check_pair(recording, pack)
    if bad:
        raise SystemExit("配對不成立，不寫：\n  " + "\n  ".join(bad[:8]))
    return pack


def dumps(pack: dict) -> str:
    """與 `pack.py` 寫檔同一個格式（收據頁內嵌的就是這一串）。"""
    return json.dumps(pack, ensure_ascii=False, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="lifecycle 錄影 ↔ 同一批收據資料包（配對＋綁定）")
    ap.add_argument("--recording", required=True)
    ap.add_argument("--runs", default=None, help="同一次 run_twin.py 的 --out 根目錄")
    ap.add_argument("--out", default=None, help="預設 <錄影同名>.pack.json")
    ap.add_argument("--check", action="store_true", help="只驗既有的配對")
    a = ap.parse_args(argv)
    rec = pathlib.Path(a.recording)
    out = pathlib.Path(a.out) if a.out else pair_path(rec)
    if a.check:
        if not out.exists():
            print(f"✗ 沒有配對收據：{out.name}", file=sys.stderr)
            return 1
        text = out.read_text(encoding="utf-8")
        bad = check_pair(rec, json.loads(text), pack_text=text)
        for b in bad:
            print("✗ " + b, file=sys.stderr)
        if not bad:
            sc = (json.loads(text).get("recording") or {}).get("sidecar")
            print(f"✓ {out.name} 綁在 {rec.name} 上（sha256＋逐格鏈頭"
                  + (f"＋旁註 {sc['file']}" if sc else "；沒有旁註") + "）")
        return 1 if bad else 0
    if not a.runs:
        ap.error("要產配對就要給 --runs（同一次執行的 run 目錄）")
    pack = build_pair(rec, pathlib.Path(a.runs))
    out.write_text(dumps(pack), encoding="utf-8")
    print(f"✓ 配對收據 → {out}（{len(pack['cells'])} 格，綁 {rec.name} "
          f"sha256 {pack['recording']['sha256'][:12]}…）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
