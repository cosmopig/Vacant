#!/usr/bin/env python3
"""這支在架構裡承重什麼：**把 R535 的結論從「相信我們」變成「你自己算」**。

`runs/r535_retry_channel_20260918/` 是 R535 的歸檔。本檔是它的**離線重算器**：
零模型呼叫、零網路、只用標準函式庫，從歸檔裡的資料把預註冊
（`decisions/DECISION_20260919_R535_RETRY_CHANNEL_PREREG.md` §〇「主要交付
＝三個數字」）那三個數字**重新算一次**，再與 `ops/gain/r535/state_r535.py`
的判定逐項比對。**對不上就是歸檔漏了東西**，不是四捨五入。

## 為什麼不直接呼叫 `state_r535.py` 就算了

`state_r535.py` 只讀 `scores_*.json` 與 `reconcile.json`。那兩份是**衍生物**：
`scores_*.json` 由 `score_r535.py` 從逐格 `run/visible_*.json`＋隱藏套件結果算出，
`m7_file`／`m7_name` 由 `run_r535.py` 從 **wire 原始位元組** grep 出來。
只跑 `state_r535.py` 等於「相信中間那兩層」。本檔刻意走**另一條路**：

| 數字 | 本檔的來源 | `state_r535.py` 的來源 |
|---|---|---|
| M7_file／M7_name | `wire.tar.gz` 解出的 `*.req.bin` 位元組，needle 自己重寫一遍 | `cell.json` 的 `m7_file`（run_r535 當時算的） |
| 第 1 次可見失敗率 | 逐格 `run/run_RUN-ON.json` 的 `attempts[0].accepted` | `scores_*.json` 的 `by_attempt[0].visible_accepted` |
| H1 點估計＋區間 | `accepted` 取自 `run_RUN-ON.json`；`hidden` 取自 `scores_*.json`；b/c、McNemar、bootstrap 全部自己算 | `state_r535.py` 的 `bc_counts`／`ci_of` |

兩條路撞在一起才算數。**`hidden` 只有一個來源**（隱藏套件的執行結果只寫在
`scores_*.json` 裡），這一條本檔驗不動，報表最後兩行會把它印出來（「驗得到／驗不到」）。

## 它怎麼證明 wire 沒有被換掉（M7 的可究責性在這裡）

M7 是唯一一個**必須看原始位元組**的數字。歸檔把那些位元組整包帶進了 repo
（`wire.tar.gz`，10,664 個 body、130 MB 原始 → 8.1 MB），而且它們被一條
**跑的時候就簽好的 ed25519 鏈**綁住：

    receipts_RUN-ON.ndjson（逐格簽章鏈，`vacant_network/logbook.py` 的 hash-chain）
      └─ payload.conversation_sha256
           == sha256(json.dumps([[req_sha, resp_sha], …], separators=(",",":")))
              （`vacant_network/vrun/wireproxy.py::wire_digest`，逐字）
           └─ 那串 sha256 逐筆寫在 wire_RUN-ON/index.jsonl
                └─ 每一個 .req.bin／.resp.bin 的實際位元組

所以「我們事後挑了對自己有利的 body」這件事是**簽章擋得住的**：換一個位元組
⇒ index 的 sha256 對不上；改 index ⇒ wire_digest 對不上；改 wire_digest
⇒ 簽章紅。A5～A7 三條檢查就是在走這條鏈。

## 誠實邊界（改碼請保留）

1. **`M7_file` 是單邊的**：命中 0 只說明那幾條特徵字串沒出現在請求 body 裡，
   **不說明 agent 沒有以任何方式受到那個檔的影響**（`run_r535.py` 的
   `measure_m7_file` docstring 逐字）。本檔重算的是同一個單邊量。
2. **`null` 不是 `false`**（鐵律 3 的 `infra_void` 同一條）：沒有第 2 次嘗試／
   這一臂不產生回饋／wire 切不開，三種 `null` 一律不進分母。
3. **隱藏套件的通過與否本檔重跑不了**：歸檔帶了交付物
   （`run/_frozen_*/solution.py`）與題庫（`ops/gain/r535/bank/`），要重跑得
   執行別人寫的碼，那是稽核者的決定不是本檔的預設。本檔只做內部一致性檢查。
4. **本檔不判「結論對不對」**，只判「歸檔夠不夠外人自己算」。狀態表的裁決權
   在 `state_r535.py`，本檔複算並比對，不另立判準。

用法：

    python3 ops/gain/verify_r535_archive.py                 # 預設歸檔目錄
    python3 ops/gain/verify_r535_archive.py --archive DIR
    python3 ops/gain/verify_r535_archive.py --no-wire       # 不解 wire（M7 轉 na）
    python3 ops/gain/verify_r535_archive.py --json out.json

回傳碼：全綠 0，任何一條紅 1。`na`（拿不到的量具）**不算綠也不判紅**，
在總判定那一行逐項列出——「拿不到」與「通過了」不可以在輸出上同形。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import random
import sys
import tarfile
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_ARCHIVE = REPO / "runs" / "r535_retry_channel_20260918"

# ── 發射時的釘值（`ops/gain/r535/LAUNCH.md` 與預註冊 §二-1）────────────────
PIN_PLAN_SHA = ("7a3accf9b1c925fa07fcc79d67ee0a152e776199229f4ef64228f778"
                "795c658e")
PIN_BANK_MANIFEST_SHA = ("5e727b2ee884d80b197ec42f63af2bf73ce939bdd53c48fc8"
                         "fc29e46e49c0794")
PIN_LAUNCH_COMMIT = "af0f0ff"

N_CELLS = 360
STRATA = ("S1", "S2")
TRIGGER_ARMS = ("RS", "RF", "RP")
TRIGGER_N_EXPECTED = {"S1": 150, "S2": 120}
BOOT_N = 2000
BOOT_SEED = 0

# ── M7 的 needle（`run_r535.py` 的凍結常數，本檔重抄一份）─────────────────
# ⚠ 重抄不是複製貼上圖方便：本檔的立論是「不靠 run_r535 當時算的結果」。
#   但**抄歪了會靜靜地回 False**，所以 drift guard（預設開，`--no-drift-guard`
#   才關）會在
#   `ops/gain/r535/run_r535.py` 匯得進來的時候，逐字比對這三個常數。
BLOCK_PREFIX = "working directory. They did not all pass.\n\n"
BLOCK_SUFFIX = "\n\nFix the working directory."
TEMPLATE_NEEDLES = (
    ("header", "Acceptance feedback (attempt"),
    ("body", "The checks that ship with this task were run against your"),
)
FEEDBACK_FILENAME_NEEDLE = "VACANT_FEEDBACK.md"

#: 口徑禁語（預註冊 §五-3 逐字）。本檔的輸出也受它管。
BANNED = ("等價", "等效", "equivalent", "equivalence",
          "無差異", "沒有差異", "效果為 0", "效果是 0", "兩臂相同", "信任")


# ── 小工具（全部標準函式庫）───────────────────────────────────────────────
def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(p: pathlib.Path) -> list[dict]:
    return [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines()
            if s.strip()]


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def mcnemar_exact(b: int, c: int) -> float:
    """配對二元的 McNemar 精確（雙尾）：不一致對 b vs c 的 p=0.5 二項檢定。

    與 `vacant_network/research.py::mcnemar_exact` 同一條式子，重寫是為了讓歸檔在
    **沒有這個 repo 的機器上**也算得出來。C1 會拿兩邊對算。
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n)
    return min(1.0, 2.0 * tail)


def boot_ci(items: list[float], *, n_boot: int = BOOT_N,
            seed: int = BOOT_SEED) -> tuple[float, float]:
    """95% bootstrap 百分位區間。**重抽順序必須與 `research.boot_ci` 逐次相同**
    （`random.Random(seed)` ＋ `rng.randrange(n)`），否則區間會差在小數第三位
    而看起來像「歸檔壞了」。"""
    rng = random.Random(seed)
    n = len(items)
    if n == 0:
        return float("nan"), float("nan")
    vals = []
    for _ in range(n_boot):
        sample = [items[rng.randrange(n)] for _ in range(n)]
        vals.append(mean(sample))
    vals.sort()
    return (vals[int(round(2.5 / 100 * (n_boot - 1)))],
            vals[int(round(97.5 / 100 * (n_boot - 1)))])


def holm(pvals: list[float]) -> list[float]:
    m = len(pvals)
    order = sorted(range(m), key=lambda i: (pvals[i], i))
    out = [0.0] * m
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, pvals[i] * (m - rank)))
        out[i] = run
    return out


def needle_variants(text: str) -> list[bytes]:
    """同一條字串在 wire 上的三種長相：原文、`ensure_ascii` 轉義、不轉義。

    少了第二種就會漏掉最常見的一類 client，而漏掉的方式是**安靜地回 False**。
    """
    out = [text.encode("utf-8"),
           json.dumps(text)[1:-1].encode("utf-8"),
           json.dumps(text, ensure_ascii=False)[1:-1].encode("utf-8")]
    uniq, seen = [], set()
    for b in out:
        if b not in seen:
            seen.add(b)
            uniq.append(b)
    return uniq


def hit(blobs: list[bytes], text: str) -> bool:
    return any(v in b for v in needle_variants(text) for b in blobs)


def build_needles(feedback_text: str) -> list[tuple[str, str]]:
    needles = list(TEMPLATE_NEEDLES)
    if BLOCK_PREFIX in feedback_text and BLOCK_SUFFIX in feedback_text:
        block = feedback_text.split(BLOCK_PREFIX, 1)[1].split(
            BLOCK_SUFFIX, 1)[0]
        if block.strip():
            needles.append(("block", block.strip()))
            for line in block.splitlines():
                s = line.strip()
                if len(s) >= 16:
                    needles.append(("block_line", s))
    return needles


# ── 歸檔讀取 ─────────────────────────────────────────────────────────────
class Archive:
    def __init__(self, root: pathlib.Path):
        self.root = root
        self.cells_dir = root / "cells"
        self.scores_path = sorted(root.glob("scores_*.json"))[-1]
        self.scores = json.loads(self.scores_path.read_text(encoding="utf-8"))
        self.reconcile = json.loads(
            (root / "reconcile.json").read_text(encoding="utf-8"))
        self.plan = read_jsonl(root / "plan.jsonl")
        self.cells_jsonl = read_jsonl(root / "cells.jsonl")
        self.names = sorted(p.name for p in self.cells_dir.iterdir()
                            if p.is_dir())
        self._cell_json: dict[str, dict] = {}
        self._summary: dict[str, dict] = {}

    def cell_json(self, name: str) -> dict:
        if name not in self._cell_json:
            self._cell_json[name] = json.loads(
                (self.cells_dir / name / "cell.json").read_text("utf-8"))
        return self._cell_json[name]

    def summary(self, name: str) -> dict:
        """逐格 `run/run_RUN-ON.json`——launcher 落盤的**原始跑況**。"""
        if name not in self._summary:
            self._summary[name] = json.loads(
                (self.cells_dir / name / "run" / "run_RUN-ON.json")
                .read_text("utf-8"))
        return self._summary[name]

    def index(self, name: str) -> list[dict]:
        return read_jsonl(self.cells_dir / name / "run" / "wire_RUN-ON"
                          / "index.jsonl")

    def receipts(self, name: str) -> list[dict]:
        return read_jsonl(self.cells_dir / name / "run"
                          / "receipts_RUN-ON.ndjson")


# ── A：完整性 ────────────────────────────────────────────────────────────
def a1_sha256sums(ar: Archive) -> dict:
    p = ar.root / "SHA256SUMS"
    if not p.exists():
        return {"ok": False, "detail": "SHA256SUMS 不存在"}
    listed: dict[str, str] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        sha, rel = line.split("  ", 1)
        listed[rel] = sha
    on_disk = {q.relative_to(ar.root).as_posix()
               for q in ar.root.rglob("*") if q.is_file()
               and q.name != "SHA256SUMS"}
    missing = sorted(set(listed) - on_disk)
    extra = sorted(on_disk - set(listed))
    bad = []
    for rel, sha in sorted(listed.items()):
        f = ar.root / rel
        if f.exists() and sha256_file(f) != sha:
            bad.append(rel)
    ok = not missing and not extra and not bad
    return {"ok": ok, "n_listed": len(listed),
            "missing": missing[:8], "extra": extra[:8], "mismatch": bad[:8],
            "detail": (f"{len(listed)} 檔逐檔 sha256 全中" if ok else
                       f"缺 {len(missing)}／多 {len(extra)}／不符 {len(bad)}")}


def a2_plan(ar: Archive) -> dict:
    sha = sha256_file(ar.root / "plan.jsonl")
    ok = (sha == PIN_PLAN_SHA == ar.reconcile.get("plan_sha256"))
    return {"ok": ok, "plan_sha256": sha, "pin": PIN_PLAN_SHA,
            "reconcile_says": ar.reconcile.get("plan_sha256"),
            "n_plan_rows": len(ar.plan),
            "detail": ("plan.jsonl 的 sha256 ＝ 發射釘值 ＝ reconcile 記的值"
                       if ok else "plan sha256 對不上")}


def a3_bank(ar: Archive) -> dict:
    seen = {ar.cell_json(n).get("bank_manifest_sha256") for n in ar.names}
    ok_cells = (seen == {PIN_BANK_MANIFEST_SHA})
    repo_manifest = REPO / "ops" / "gain" / "r535" / "bank_manifest.json"
    repo_sha = sha256_file(repo_manifest) if repo_manifest.exists() else None
    ok_repo = None if repo_sha is None else (repo_sha == PIN_BANK_MANIFEST_SHA)
    return {"ok": bool(ok_cells and (ok_repo is not False)),
            "n_distinct_in_cells": len(seen), "pin": PIN_BANK_MANIFEST_SHA,
            "repo_bank_manifest_sha256": repo_sha,
            "repo_manifest_matches": ok_repo,
            "detail": (f"360 格逐格記的題庫 manifest 都是釘值；"
                       f"repo 內 bank_manifest.json "
                       f"{'也是同一份' if ok_repo else '對不上／不存在'}")}


def a4_cells(ar: Archive) -> dict:
    from_plan = {r["cell"] for r in ar.plan}
    from_dirs = set(ar.names)
    from_jsonl = {r["cell"] for r in ar.cells_jsonl}
    from_scores = {c["cell"] for c in ar.scores["cells"]}
    ok = (len(from_dirs) == N_CELLS
          and from_plan == from_dirs == from_jsonl == from_scores)
    return {"ok": ok, "n": len(from_dirs),
            "reconcile_verdict": ar.reconcile.get("verdict"),
            "detail": (f"{len(from_dirs)} 格：plan／目錄／cells.jsonl／scores "
                       f"四邊同一個集合；reconcile verdict="
                       f"{ar.reconcile.get('verdict')}")}


def a5_receipts(ar: Archive) -> dict:
    """ed25519 簽章鏈。需要 `cryptography`（repo 唯一的 runtime 依賴）。

    拿不到就記 `na`——**不可以當成綠**（鐵律 3 的同一條）。
    """
    try:
        sys.path.insert(0, str(REPO))
        from vacant_network.vrun.verify_receipts import verify_run
    except Exception as exc:                                # noqa: BLE001
        return {"ok": None, "detail": f"na：匯不進驗證器（{type(exc).__name__}）"}
    broken, n_entries = [], 0
    for n in ar.names:
        for rec in verify_run(ar.cells_dir / n / "run"):
            n_entries += rec.get("entries_n") or 0
            if rec.get("verdict") != "OK":
                broken.append({"cell": n, "failures": rec.get("failures")[:2]})
    return {"ok": not broken, "n_chains": len(ar.names),
            "n_entries": n_entries, "broken": broken[:5],
            "detail": (f"{len(ar.names)} 條鏈、{n_entries} 筆簽章逐筆驗過"
                       if not broken else f"{len(broken)} 條鏈紅")}


def a6_wire_digest(ar: Archive) -> dict:
    """index.jsonl → wire_digest → 收據 payload 的 conversation_sha256。

    這一條是 M7 可究責性的骨幹：它把「我們給你看的 wire 清單」綁死在
    **跑的時候就簽好**的那條鏈上。
    """
    bad = []
    for n in ar.names:
        idx = ar.index(n)
        pairs = [[r.get("request_sha256"), r.get("response_sha256")]
                 for r in idx]
        wd = hashlib.sha256(
            json.dumps(pairs, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        s = ar.summary(n)
        if wd != s.get("wire_digest"):
            bad.append({"cell": n, "why": "index 重算 ≠ summary.wire_digest"})
            continue
        convs = [r["payload"].get("conversation_sha256")
                 for r in ar.receipts(n)
                 if isinstance(r.get("payload"), dict)]
        if wd not in convs:
            bad.append({"cell": n, "why": "wire_digest 不在任何收據 payload 裡"})
    return {"ok": not bad, "n_cells": len(ar.names), "bad": bad[:5],
            "detail": ("360 格的 index.jsonl 重算出的 wire_digest 都等於 "
                       "run_RUN-ON.json 記的值，而且都出現在簽章收據的 "
                       "conversation_sha256 裡"
                       if not bad else f"{len(bad)} 格對不上")}


def a7_wire_bytes(ar: Archive, wire_root: pathlib.Path | None) -> dict:
    if wire_root is None:
        return {"ok": None, "detail": "na：沒有解 wire（--no-wire）"}
    n_ok = n_bad = n_missing = n_null_resp = 0
    bad = []
    for n in ar.names:
        base = wire_root / "cells" / n / "run" / "wire_RUN-ON"
        for r in ar.index(n):
            for kind in ("req", "resp"):
                want = r.get(f"{'request' if kind == 'req' else 'response'}"
                             f"_sha256")
                p = base / f"{r['call_id']}.{kind}.bin"
                if want is None:
                    # `response_sha256` 為 null ＝ 上游沒回話那一通
                    # （`wireproxy.py` §98 逐字）。**null 不是 0**，記下來。
                    n_null_resp += 1
                    continue
                if not p.exists():
                    n_missing += 1
                    continue
                if sha256_file(p) == want:
                    n_ok += 1
                else:
                    n_bad += 1
                    if len(bad) < 5:
                        bad.append(p.as_posix())
    return {"ok": (n_bad == 0 and n_missing == 0 and n_ok > 0),
            "n_ok": n_ok, "n_bad": n_bad, "n_missing": n_missing,
            "n_null_response_sha256": n_null_resp, "bad": bad,
            "detail": (f"wire.tar.gz 解出的 {n_ok} 個 body，sha256 逐個命中 "
                       f"index.jsonl（另有 {n_null_resp} 通上游沒回話，"
                       f"index 記 null ⇒ 不進分母）"
                       if n_bad == 0 and n_missing == 0
                       else f"{n_bad} 個不符、{n_missing} 個缺")}


def a9_unindexed_bodies(ar: Archive, wire_root: pathlib.Path | None) -> dict:
    """**落盤了卻沒有進帳的 body**——本歸檔自己揭露的缺口。

    `wireproxy._handle` 的順序是：先寫 `.req.bin` → 打上游 → 寫 `.resp.bin`
    → `_index(rec)` → `requests_seen += 1`。所以一通在半路被砍掉的呼叫會
    **留下 body 但沒有 index 列**，因而也不進 `wire_digest`、不進簽章。
    這是設計使然（沒收到回應的那一通不算一通），但它對 `M7_file` 是一個
    **真的單邊缺口**：那份 body 可能已經送出去了，而 M7 的切片只走 index。

    所以這一條不是形式檢查，它問的是一個會改數字的問題：
    **那些沒進帳的 RF 請求裡，有沒有回饋原文？** 有 ⇒ `M7_file` 被低估了。
    """
    if wire_root is None:
        return {"ok": None, "detail": "na：沒有解 wire（--no-wire）"}
    rows = []
    rf_with_feedback = []
    for n in ar.names:
        base = wire_root / "cells" / n / "run" / "wire_RUN-ON"
        if not base.is_dir():
            continue
        on_disk = {p.name.split(".")[0] for p in base.glob("*.bin")}
        indexed = {r["call_id"] for r in ar.index(n)}
        extra = sorted(on_disk - indexed)
        if not extra:
            continue
        arm_name = ar.cell_json(n).get("arm")
        s = ar.summary(n)
        texts = [(a.get("feedback") or {}).get("text")
                 for a in (s.get("attempts") or [])]
        needles = [t for fb in texts if fb for _k, t in build_needles(fb)]
        for cid in extra:
            q = base / f"{cid}.req.bin"
            r = base / f"{cid}.resp.bin"
            qb = q.read_bytes() if q.exists() else b""
            has_fb = any(hit([qb], t) for t in needles) if needles else False
            rows.append({"cell": n, "arm": arm_name, "call_id": cid,
                         "req_bytes": len(qb),
                         "resp_bytes": r.stat().st_size if r.exists() else 0,
                         "carries_feedback_text": has_fb})
            if arm_name == "RF" and has_fb:
                rf_with_feedback.append(n)
    return {"ok": not rf_with_feedback, "n_unindexed": len(rows),
            "rf_cells_undercounted": sorted(set(rf_with_feedback)),
            "rows": rows,
            "detail": (f"{len(rows)} 個 body 落盤了卻沒進 index（半路被砍的"
                       f"呼叫；因而不進 wire_digest、不進簽章）。**RF 臂那些"
                       f"沒進帳的請求裡沒有一個帶回饋原文** ⇒ M7_file 沒有被"
                       f"這個缺口低估"
                       if not rf_with_feedback else
                       f"{len(rf_with_feedback)} 格的 RF 未入帳請求帶著回饋"
                       f"原文 ⇒ M7_file 被低估，不可照現值引用")}


def a8_raw_vs_scores(ar: Archive) -> dict:
    """原始 `run_RUN-ON.json` 與衍生 `scores_*.json` 的逐格對帳。

    scores 是本檔唯一沒有第二來源的東西（隱藏套件結果），所以能對的欄位
    **一個都不放過**：`accepted`／`attempts_used`／`requests_seen`／逐次可見。
    """
    by_cell = {c["cell"]: c for c in ar.scores["cells"]}
    bad = []
    for n in ar.names:
        s, sc = ar.summary(n), by_cell[n]
        if bool(s.get("accepted")) != bool(sc.get("visible_accepted")):
            bad.append({"cell": n, "field": "accepted"})
        if s.get("attempts_used") != sc.get("attempts_used"):
            bad.append({"cell": n, "field": "attempts_used"})
        if s.get("requests_seen") != sc.get("requests_seen"):
            bad.append({"cell": n, "field": "requests_seen"})
        for a, ba in zip(s.get("attempts") or [], sc.get("by_attempt") or []):
            if bool(a.get("accepted")) != bool(ba.get("visible_accepted")):
                bad.append({"cell": n, "field": f"attempt{a['attempt']}"})
        # 隱藏結果的內部一致性：逐 case 的 ok 數要等於 passed。
        for ba in sc.get("by_attempt") or []:
            h = ba.get("hidden") or {}
            cases = [c for f in (h.get("files") or []) for c in
                     (f.get("cases") or [])]
            if cases and sum(1 for c in cases if c.get("ok")) != h.get("passed"):
                bad.append({"cell": n, "field": "hidden_case_count"})
    return {"ok": not bad, "n_cells": len(ar.names), "bad": bad[:8],
            "detail": ("逐格原始跑況與 scores 的 accepted／attempts_used／"
                       "requests_seen／逐次可見／隱藏逐 case 計數全部對得上"
                       if not bad else f"{len(bad)} 處對不上")}


# ── B1：M7_file／M7_name（從 wire 位元組重算）──────────────────────────────
def b1_m7(ar: Archive, wire_root: pathlib.Path | None) -> dict:
    if wire_root is None:
        return {"ok": None, "detail": "na：沒有解 wire（--no-wire）⇒ M7 只能讀"
                                      "`cell.json` 記的值，等於相信我們"}
    per_cell: dict[str, dict] = {}
    mismatch = []
    for n in ar.names:
        arm_name = ar.cell_json(n).get("arm")
        s = ar.summary(n)
        arm = s.get("arm", "RUN-ON")
        attempts = s.get("attempts") or []
        base = wire_root / "cells" / n / "run" / f"wire_{arm}"
        idx = ar.index(n)

        def blobs_of(slice_ids: list[str]) -> list[bytes]:
            out = []
            for cid in slice_ids:
                p = base / f"{cid}.req.bin"
                if p.exists():
                    out.append(p.read_bytes())
            return out

        # 切片：照 requests_seen_cumulative 切 index.jsonl。對不起來就 null。
        cum_last = 0
        for rec in attempts:
            if rec.get("requests_seen_cumulative") is not None:
                cum_last = rec["requests_seen_cumulative"]
        slices: dict[int, list[str]] = {}
        slice_ok = (cum_last == len(idx))
        if slice_ok:
            prev = 0
            for rec in attempts:
                c = rec.get("requests_seen_cumulative")
                if c is None:
                    slices[rec["attempt"]] = []
                    continue
                slices[rec["attempt"]] = [r["call_id"] for r in idx[prev:c]]
                prev = c

        m7f: bool | None = None
        m7n: bool | None = None
        reason = None
        if len(attempts) < 2:
            reason = "no_second_attempt"
        elif arm_name == "RS":
            reason = "arm_has_no_feedback_by_policy"
        elif not slice_ok:
            reason = "wire_unmappable"
        else:
            first = blobs_of(slices.get(1, []))
            # M7_file
            any_true = any_checked = False
            for rec in attempts:
                k = rec["attempt"]
                if k < 2:
                    continue
                fb = ((attempts[k - 2].get("feedback") or {}).get("text"))
                if not fb:
                    continue
                good = [(kind, t) for kind, t in build_needles(fb)
                        if not hit(first, t)]
                if not good:
                    continue
                bl = blobs_of(slices.get(k, []))
                found = any(hit(bl, t) for _, t in good)
                any_checked = True
                any_true = any_true or found
            m7f = bool(any_true) if any_checked else None
            if m7f is None:
                reason = "no_usable_attempt"
            # M7_name
            if hit(first, FEEDBACK_FILENAME_NEEDLE):
                m7n = None                      # needle 在 attempt 1 就出現
            else:
                nt = nc = False
                for rec in attempts:
                    k = rec["attempt"]
                    if k < 2:
                        continue
                    nc = True
                    nt = nt or hit(blobs_of(slices.get(k, [])),
                                   FEEDBACK_FILENAME_NEEDLE)
                m7n = bool(nt) if nc else None
        per_cell[n] = {"arm": arm_name, "stratum": ar.cell_json(n)["stratum"],
                       "m7_file": m7f, "m7_name": m7n, "reason": reason}
        cj = ar.cell_json(n)
        if cj.get("m7_file") != m7f or cj.get("m7_name") != m7n:
            mismatch.append({"cell": n,
                             "archived": [cj.get("m7_file"), cj.get("m7_name")],
                             "recomputed": [m7f, m7n]})

    out: dict = {"ok": not mismatch, "mismatch": mismatch[:8],
                 "n_mismatch": len(mismatch), "by_stratum": {}}
    for st in STRATA:
        sel = [v for v in per_cell.values()
               if v["stratum"] == st and v["arm"] == "RF"]
        t = sum(1 for v in sel if v["m7_file"] is True)
        f = sum(1 for v in sel if v["m7_file"] is False)
        nn = sum(1 for v in sel if v["m7_file"] is None)
        nt = sum(1 for v in sel if v["m7_name"] is True)
        nf = sum(1 for v in sel if v["m7_name"] is False)
        den = t + f
        nden = nt + nf
        out["by_stratum"][st] = {
            "arm": "RF", "n_cells": len(sel),
            "m7_file_hit": t, "m7_file_denominator": den, "m7_file_null": nn,
            "m7_file_rate": (t / den) if den else None,
            "rule_of_three_upper": (3 / den) if (den and t == 0) else None,
            "m7_name_hit": nt, "m7_name_denominator": nden,
            "m7_name_rate": (nt / nden) if nden else None,
        }
    out["detail"] = ("逐格從 .req.bin 位元組重算，360 格全部與 cell.json 記的"
                     "一致" if not mismatch else f"{len(mismatch)} 格對不上")
    out["one_sided"] = ("單邊：命中 0 只說明那幾條特徵字串沒出現在請求 body 裡，"
                        "不說明 agent 沒有以任何方式受到那個檔的影響。")
    return out


# ── B2：第 1 次嘗試可見失敗率（從原始 run_RUN-ON.json）─────────────────────
def b2_trigger(ar: Archive) -> dict:
    by_cell = {c["cell"]: c for c in ar.scores["cells"]}
    res: dict = {"ok": True, "by_stratum": {}}
    for st in STRATA:
        n = fails = 0
        drift = []
        for name in ar.names:
            cj = ar.cell_json(name)
            if cj["stratum"] != st or cj["arm"] not in TRIGGER_ARMS:
                continue
            atts = ar.summary(name).get("attempts") or []
            if not atts:
                continue
            raw = bool(atts[0].get("accepted"))
            n += 1
            fails += (0 if raw else 1)
            ba = (by_cell[name].get("by_attempt") or [{}])[0]
            if raw != bool(ba.get("visible_accepted")):
                drift.append(name)
        ok = (n == TRIGGER_N_EXPECTED[st]) and not drift
        res["ok"] = res["ok"] and ok
        res["by_stratum"][st] = {
            "arms": list(TRIGGER_ARMS), "pc_excluded": True,
            "n": n, "n_expected": TRIGGER_N_EXPECTED[st],
            "attempt1_fail": fails, "attempt1_fail_rate": fails / n if n else None,
            "scores_disagree": drift[:5]}
    res["detail"] = ("分母＝RS／RF／RP 三臂的第 1 次嘗試（PC 是另一個 TASK，"
                     "不進分母）；逐格取自 run_RUN-ON.json 的 attempts[0]，"
                     "再與 scores 對算")
    return res


# ── B3：H1（M1 ＝ accepted ∧ hidden 全過）──────────────────────────────────
def b3_h1(ar: Archive) -> dict:
    by_cell = {c["cell"]: c for c in ar.scores["cells"]}
    m1: dict[tuple[str, str, str], bool] = {}     # (stratum, task, arm) -> M1
    for name in ar.names:
        cj = ar.cell_json(name)
        sc = by_cell[name]
        acc = bool(ar.summary(name).get("accepted"))   # 原始：launcher 落盤
        hid = sc.get("hidden_pass")                    # 唯一來源：scores
        if hid is None:
            continue
        m1[(cj["stratum"], cj["task_id"], cj["arm"])] = bool(acc) and bool(hid)

    res: dict = {"ok": True, "by_stratum": {}, "m1_definition":
                 "M1 ≡ accepted ∧ hidden 全過（拒交強制 0）"}
    raw_p = []
    for st in STRATA:
        tasks = sorted({t for (s, t, _a) in m1 if s == st})
        b = c = 0
        diffs: list[float] = []
        for t in tasks:
            rf, rp = m1.get((st, t, "RF")), m1.get((st, t, "RP"))
            if rf is None or rp is None:
                continue
            diffs.append(float(rp) - float(rf))
            if not rf and rp:
                b += 1
            elif rf and not rp:
                c += 1
        p = mcnemar_exact(b, c)
        lo, hi = boot_ci(diffs)
        raw_p.append(p)
        res["by_stratum"][st] = {
            "b_rp_wins": b, "c_rf_wins": c, "n_pairs": len(diffs),
            "p_exact": p, "mean_diff": mean(diffs) if diffs else None,
            "ci_lo": lo, "ci_hi": hi,
            "ci_method": f"bootstrap 百分位 2.5/97.5，seed={BOOT_SEED}，"
                         f"n_boot={BOOT_N}",
            "sign": "+ ＝ RP 贏（與 b 同號）"}
    for st, hp in zip(STRATA, holm(raw_p)):
        res["by_stratum"][st]["p_holm"] = hp
    res["family"] = {"members": ["H1-S1", "H1-S2"], "raw_p": raw_p,
                     "holm_p": holm(raw_p)}
    res["detail"] = ("accepted 取自 run_RUN-ON.json（原始），hidden 取自 "
                     "scores（唯一來源）；b/c、McNemar exact、Holm、"
                     "bootstrap 區間全部本檔自己算")
    return res


# ── C：與 state_r535.py 對帳 ─────────────────────────────────────────────
def c1_cross_check(ar: Archive, mine: dict) -> dict:
    try:
        sys.path.insert(0, str(REPO))
        sys.path.insert(0, str(REPO / "ops" / "gain" / "r535"))
        import state_r535                                      # noqa: PLC0415
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": None,
                "detail": f"na：匯不進 state_r535（{type(exc).__name__}）"}
    cells = state_r535.load_scores(ar.scores_path)
    doc = state_r535.analyse(cells,
                            reconcile_invalid=(ar.reconcile.get("verdict")
                                               != "OK"),
                            m7ws_selftest="unavailable")
    rows = []

    def cmp(label: str, got, want, tol: float | None = None) -> None:
        if tol is not None and isinstance(got, float) \
                and isinstance(want, float):
            same = abs(got - want) <= tol
        else:
            same = got == want
        rows.append({"item": label, "verify": got, "state_r535": want,
                     "same": bool(same)})

    for st in STRATA:
        ps = doc["per_stratum"][st]
        cmp(f"{st}/attempt1_fail",
            mine["B2"]["by_stratum"][st]["attempt1_fail"],
            ps["trigger"]["attempt1_fail"])
        cmp(f"{st}/attempt1_n", mine["B2"]["by_stratum"][st]["n"],
            ps["trigger"]["n"])
        cmp(f"{st}/H1_b", mine["B3"]["by_stratum"][st]["b_rp_wins"],
            ps["h1"]["b"])
        cmp(f"{st}/H1_c", mine["B3"]["by_stratum"][st]["c_rf_wins"],
            ps["h1"]["c"])
        cmp(f"{st}/H1_p", mine["B3"]["by_stratum"][st]["p_exact"],
            ps["h1"]["p_exact"], tol=1e-12)
        cmp(f"{st}/H1_holm", mine["B3"]["by_stratum"][st]["p_holm"],
            ps["p_holm"], tol=1e-12)
        cmp(f"{st}/mean_diff", mine["B3"]["by_stratum"][st]["mean_diff"],
            ps["ci"]["mean_diff"], tol=1e-12)
        cmp(f"{st}/ci_lo", mine["B3"]["by_stratum"][st]["ci_lo"],
            ps["ci"]["ci_lo"], tol=1e-12)
        cmp(f"{st}/ci_hi", mine["B3"]["by_stratum"][st]["ci_hi"],
            ps["ci"]["ci_hi"], tol=1e-12)
        if mine["B1"].get("by_stratum"):
            mf = mine["B1"]["by_stratum"][st]
            cmp(f"{st}/M7_file_hit", mf["m7_file_hit"], ps["m7_file"]["hit"])
            cmp(f"{st}/M7_file_den", mf["m7_file_denominator"],
                ps["m7_file"]["denominator"])
    states = {st: doc["state"][st] for st in STRATA}
    return {"ok": all(r["same"] for r in rows), "rows": rows,
            "state_r535_state": states,
            "detail": (f"{sum(1 for r in rows if r['same'])}/{len(rows)} 項"
                       f"與 state_r535.py 一致；狀態表＝{states}")}


def check_diction(doc: dict) -> dict:
    blob = json.dumps(doc, ensure_ascii=False)
    hits = [w for w in BANNED if w in blob]
    return {"ok": not hits, "hits": hits}


# ── 報表 ─────────────────────────────────────────────────────────────────
def mark(ok) -> str:
    return "綠" if ok is True else ("紅" if ok is False else "na")


def render(doc: dict) -> str:
    L = [f"R535 歸檔離線重算　{doc['archive']}",
         f"  發射 commit {PIN_LAUNCH_COMMIT}　plan {PIN_PLAN_SHA[:12]}…　"
         f"bank {PIN_BANK_MANIFEST_SHA[:12]}…",
         f"  scores 用的是 {doc['scores_file']}",
         ""]
    L.append("── A 完整性 ─────────────────────────────────────")
    for k in ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"):
        r = doc[k]
        L.append(f"  [{mark(r['ok'])}] {k} {doc['labels'][k]:<26} "
                 f"{r['detail']}")
    L.append("")
    L.append("── B 三個數字（歸檔重算）────────────────────────")
    b1 = doc["B1"]
    L.append(f"  [{mark(b1['ok'])}] 數字 1　M7_file／M7_name（RF 臂）")
    for st in STRATA:
        if b1.get("by_stratum"):
            m = b1["by_stratum"][st]
            r3 = ("　rule-of-three 上界 "
                  f"{m['rule_of_three_upper']:.3f}"
                  if m["rule_of_three_upper"] is not None else "")
            L.append(f"        {st}: M7_file {m['m7_file_hit']}/"
                     f"{m['m7_file_denominator']}"
                     f"＝{_f(m['m7_file_rate'])}　null={m['m7_file_null']}"
                     f"{r3}")
            L.append(f"            M7_name {m['m7_name_hit']}/"
                     f"{m['m7_name_denominator']}＝{_f(m['m7_name_rate'])}")
    L.append(f"        {b1.get('detail')}")
    L.append(f"        ⚠ {b1.get('one_sided', '')}")
    b2 = doc["B2"]
    L.append(f"  [{mark(b2['ok'])}] 數字 2　第 1 次嘗試可見失敗率")
    for st in STRATA:
        m = b2["by_stratum"][st]
        L.append(f"        {st}: {m['attempt1_fail']}/{m['n']}"
                 f"＝{_f(m['attempt1_fail_rate'])}"
                 f"（預期 n={m['n_expected']}）")
    b3 = doc["B3"]
    L.append(f"  [{mark(b3['ok'])}] 數字 3　H1 點估計＋95% 區間"
             f"（{b3['m1_definition']}）")
    for st in STRATA:
        m = b3["by_stratum"][st]
        L.append(f"        {st}: 均差 {m['mean_diff']:+.4f}"
                 f"　95% [{m['ci_lo']:.4f}, {m['ci_hi']:.4f}]"
                 f"　b={m['b_rp_wins']}（RP 贏）c={m['c_rf_wins']}（RF 贏）"
                 f"　p={m['p_exact']:.5g}　Holm p={m['p_holm']:.5g}")
    L.append("")
    c1 = doc["C1"]
    L.append("── C 與 ops/gain/r535/state_r535.py 對帳 ────────")
    L.append(f"  [{mark(c1['ok'])}] {c1['detail']}")
    for r in c1.get("rows", []):
        if not r["same"]:
            L.append(f"        ✗ {r['item']}: 本檔={r['verify']} "
                     f"state_r535={r['state_r535']}")
    L.append("")
    L.append(f"口徑檢查：{mark(doc['diction']['ok'])}"
             + (f"　命中 {doc['diction']['hits']}"
                if doc["diction"]["hits"] else ""))
    L.append(f"總判定：{doc['verdict']}")
    L.append("")
    got = ["計畫與題庫的釘值", "360 格齊不齊"]
    if doc["A5"]["ok"] is True:
        got.append("簽章鏈")
    if doc["A6"]["ok"] is True:
        got.append("wire 清單與簽章的綁定")
    if doc["A7"]["ok"] is True:
        got.append("wire 位元組")
    if doc["B1"]["ok"] is True:
        got.append("M7 從位元組重算")
    got += ["第 1 次可見失敗率", "H1 的 b/c／點估計／區間"]
    L.append("驗得到：" + "、".join(got) + "。"
             + ("　⚠ 這一次**沒有**解 wire ⇒ M7 只是照抄我們記的值，"
                "不是重算。" if doc["B1"]["ok"] is None else ""))
    L.append("驗不到：隱藏套件的執行結果只有一個來源（`scores_*.json`），"
             "本檔只做內部一致性檢查，沒有重跑那些測試；"
             "M7 是單邊量；模型那一端的行為本身不可重現（溫度、後端版本）。")
    return "\n".join(L)


def _f(x) -> str:
    return "—" if x is None else f"{x:.4f}"


LABELS = {
    "A1": "逐檔 sha256",
    "A2": "plan 釘值",
    "A3": "題庫 manifest 釘值",
    "A4": "360 格齊不齊",
    "A5": "ed25519 收據鏈",
    "A6": "wire↔簽章 綁定",
    "A7": "wire 位元組 sha256",
    "A8": "原始↔scores 對帳",
    "A9": "未入帳的 wire body",
}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="R535 歸檔的離線重算（零模型呼叫、零網路）")
    ap.add_argument("--archive", default=str(DEFAULT_ARCHIVE))
    ap.add_argument("--no-wire", action="store_true",
                    help="不解 wire.tar.gz：M7 轉 na（等於相信我們記的值）")
    ap.add_argument("--json", help="把完整報表寫成 JSON")
    ap.add_argument("--no-drift-guard", action="store_true",
                    help="不比對 run_r535.py 的 needle 常數")
    return ap


def drift_guard() -> dict:
    """本檔重抄的 needle 常數 vs `run_r535.py` 的原件。抄歪了會靜靜回 False。"""
    try:
        sys.path.insert(0, str(REPO / "ops" / "gain" / "r535"))
        import run_r535                                        # noqa: PLC0415
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": None, "detail": f"na：匯不進 run_r535（{type(exc).__name__}）"}
    same = (run_r535._BLOCK_PREFIX == BLOCK_PREFIX
            and run_r535._BLOCK_SUFFIX == BLOCK_SUFFIX
            and tuple(run_r535._TEMPLATE_NEEDLES) == TEMPLATE_NEEDLES
            and run_r535._FEEDBACK_FILENAME_NEEDLE
            == FEEDBACK_FILENAME_NEEDLE)
    return {"ok": same,
            "detail": ("本檔重抄的 needle 常數與 run_r535.py 逐字相同"
                       if same else "needle 常數漂了——重算結果不可採信")}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = pathlib.Path(args.archive).resolve()
    ar = Archive(root)

    tmp = None
    wire_root = None
    if not args.no_wire:
        tar = root / "wire.tar.gz"
        if tar.exists():
            tmp = tempfile.TemporaryDirectory(prefix="r535wire_")
            with tarfile.open(tar, "r:gz") as tf:
                tf.extractall(tmp.name, filter="data")
            wire_root = pathlib.Path(tmp.name)

    doc: dict = {"tool": "ops/gain/verify_r535_archive.py",
                 "archive": root.as_posix(),
                 "scores_file": ar.scores_path.name,
                 "wire_extracted": wire_root is not None,
                 "labels": LABELS,
                 "drift_guard": ({"ok": None, "detail": "na：--no-drift-guard"}
                                 if args.no_drift_guard else drift_guard())}
    doc["A1"] = a1_sha256sums(ar)
    doc["A2"] = a2_plan(ar)
    doc["A3"] = a3_bank(ar)
    doc["A4"] = a4_cells(ar)
    doc["A5"] = a5_receipts(ar)
    doc["A6"] = a6_wire_digest(ar)
    doc["A7"] = a7_wire_bytes(ar, wire_root)
    doc["A8"] = a8_raw_vs_scores(ar)
    doc["A9"] = a9_unindexed_bodies(ar, wire_root)
    doc["B1"] = b1_m7(ar, wire_root)
    doc["B2"] = b2_trigger(ar)
    doc["B3"] = b3_h1(ar)
    doc["C1"] = c1_cross_check(ar, doc)
    reds = [k for k in ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9",
                        "B1", "B2", "B3", "C1", "drift_guard")
            if doc[k]["ok"] is False]
    nas = [k for k in ("A5", "A7", "A9", "B1", "C1", "drift_guard")
           if doc[k]["ok"] is None]
    doc["verdict"] = ("紅：" + "／".join(reds)) if reds else (
        f"全綠（{len(nas)} 項 na：{'／'.join(nas)}）" if nas else "全綠")
    doc["diction"] = check_diction({k: v for k, v in doc.items()
                                    if k != "diction"})
    print(render(doc))
    if args.json:
        p = pathlib.Path(args.json)
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        print(f"\n→ {p}", file=sys.stderr)
    if tmp is not None:
        tmp.cleanup()
    return 0 if (not reds and doc["diction"]["ok"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
