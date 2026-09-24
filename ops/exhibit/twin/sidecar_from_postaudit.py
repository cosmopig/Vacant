"""twin/sidecar_from_postaudit — 把一批 run 目錄裡的 `postaudit_RUN-OFF.json` 轉寫成旁註。

## 這支在架構裡承重什麼（以及它**不是**什麼）

`twin.sidecar/1`（`sidecar.py`）是分身這一側自己的紀錄：OFF 臂跑完之後，
`run_twin.postaudit_off` 用同一把尺事後量一次。正常路徑是 `run_twin --events`
在**量完的當下**就寫旁註（`run_twin.write_postaudit_sidecar`）。

2026-09-24 的 L-real 重錄（`decisions/DECISION_20260924_TWIN_LREAL_RERECORD.md`）
在旁註程式合併之前就發射了，照「同一批不換程式」的紀律跑完 ⇒ 錄影沒有旁註，
但每一格的 `postaudit_RUN-OFF.json` 都在（54/54）。這一支把**那份已經存在的事後
稽核結果**換成旁註的格式，不重量、不重算任何東西。

⚠ **它不是「從 run 目錄推事件」的那條舊路**（人類 2026-09-24 裁決刪掉的是那條）：
  - 它**不碰 Vacant 的 lifecycle**：錄影一個位元組都不改，Vacant 當場觀察到的事
    仍然只來自 launcher 當場寫的那一份。
  - 它搬的資料本來就是**分身這一側自己量、自己寫**的（`run_twin.postaudit_off`），
    不是 Vacant 的裁決；旁註的三個旗標（`when`／`is_verdict`／`signed`）由
    `sidecar.postaudit_row` 寫死。

## 綁定怎麼守（每一條都 fail-closed）

1. 錄影裡這一格 OFF 那一跑必須有 `run_ended`、不是 `infra_void`。
2. run 目錄的 `run_RUN-OFF.json` 的 `ws_end_sha256` 必須**等於**錄影裡
   `run_ended.ws_end_sha256`——對不上代表這份事後稽核量的不是錄影裡那一跑，不轉。
3. 轉出來的整份旁註再過一次 `sidecar.validate(rows, lifecycle_events=錄影)`。

## 誠實邊界

1. **`ts_ms` 是那一跑的 `run_ended.ts_ms`，不是事後稽核真正完成的時間。**
   舊的 `postaudit_RUN-OFF.json` 沒有記時間；檔案的 mtime 會被 git checkout 改寫，
   拿它當時間是說謊。取 `run_ended.ts_ms` 是「不早於那一跑結束」這條綁定規則的下界。
2. 每一筆多帶 `derived_from`，講明它是事後從哪個檔轉寫的——看資料的人分得出
   「當下寫的旁註」與「轉寫的旁註」。

用法：
    python3 ops/exhibit/twin/sidecar_from_postaudit.py \\
        --recording ops/exhibit/twin/recordings/lreal_20260924.jsonl \\
        --runs runs/twin_lreal_20260924
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import sidecar as sidecarlib  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402

DERIVED_NOTE = ("postaudit_RUN-OFF.json 事後轉寫（2026-09-24）：這一批在旁註程式合併前發射，"
                "量的當下沒有寫旁註；ts_ms 取那一跑的 run_ended，不是量完的時間")


def build(recording: pathlib.Path, runs_root: pathlib.Path) -> tuple[list[dict], list[str]]:
    """回 `(旁註列, 問題)`。有任何一格綁不上就回問題、不回部分結果。"""
    evs = lifecycle.read(recording)
    bad = lifecycle.validate_stream(evs)
    if bad:
        return [], ["錄影本身不合 lifecycle 契約：" + b for b in bad[:3]]
    cell_of: dict[str, str] = {}
    rows: list[dict] = []
    problems: list[str] = []
    for e in evs:
        if e["type"] == "run_started":
            cell_of[e["run_id"]] = (e.get("caller") or {}).get("cell_id") or e["task_id"]
        if e["type"] != "run_ended" or e["arm"] != sidecarlib.LC_ARM_OFF:
            continue
        cid = cell_of.get(e["run_id"])
        if e.get("infra_void"):
            continue                    # 基建壞了的那一跑沒有東西可量（不是 0）
        run_dir = runs_root / "runs" / str(cid)
        pa_path = run_dir / "postaudit_RUN-OFF.json"
        sm_path = run_dir / "run_RUN-OFF.json"
        if not pa_path.exists() or not sm_path.exists():
            problems.append(f"{cid}：run 目錄缺 postaudit_RUN-OFF.json 或 run_RUN-OFF.json")
            continue
        pa = json.loads(pa_path.read_text(encoding="utf-8"))
        sm = json.loads(sm_path.read_text(encoding="utf-8"))
        if sm.get("ws_end_sha256") != e.get("ws_end_sha256"):
            problems.append(f"{cid}：run 目錄的 ws_end_sha256 與錄影裡那一跑不同，"
                            "這份事後稽核量的不是錄影裡那一跑")
            continue
        row = sidecarlib.postaudit_row(pa, cell_id=cid, run_id=e["run_id"],
                                       ws_end_sha256=e.get("ws_end_sha256"),
                                       ts_ms=e["ts_ms"])
        row["derived_from"] = DERIVED_NOTE
        rows.append(row)
    if not problems:
        problems += ["轉出來的旁註過不了契約：" + b
                     for b in sidecarlib.validate(rows, lifecycle_events=evs)]
    return ([] if problems else rows), problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="postaudit_RUN-OFF.json → 旁註（twin.sidecar/1）")
    ap.add_argument("--recording", required=True)
    ap.add_argument("--runs", required=True, help="run_twin 的 --out（底下有 runs/<cell>/）")
    ap.add_argument("--force", action="store_true", help="旁註檔已存在時覆寫")
    a = ap.parse_args(argv)
    rec = pathlib.Path(a.recording)
    out = sidecarlib.sidecar_path(rec)
    if out.exists() and not a.force:
        print(f"✗ {out} 已經存在（當下寫的旁註不准被轉寫的蓋掉）；確定要覆寫就給 --force",
              file=sys.stderr)
        return 1
    rows, problems = build(rec, pathlib.Path(a.runs))
    if problems:
        for p in problems:
            print("✗ " + p, file=sys.stderr)
        return 1
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                   encoding="utf-8")
    n_fail = sum(1 for r in rows if not r["all_pass"])
    print(f"✓ {out}（{len(rows)} 筆事後稽核，其中 {n_fail} 筆沒有全過；"
          "分身補量的，不是 Vacant 的裁決）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
