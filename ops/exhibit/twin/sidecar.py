"""twin/sidecar — 分身**自己**記的旁註串流（`twin.sidecar/1`）。不是 Vacant 的事件。

## 這支在架構裡承重什麼

2026-09-24 人類裁決兩次：

1. 「刪事後推導，留錄影重播」——電視事件只剩 `vacant.lifecycle/1` 一條路。
   副作用：OFF 臂的事後稽核（`postaudit`）與整批累計（`counters`）從電視上消失。
2. 「**分身側自己記一份補回**」——這兩樣**不是 Vacant 當場做的事**，所以
   **不准進 Vacant 的 lifecycle 契約**（`vacant_network/vrun/*` 一個字都不動）。

這一支就是第 2 條的那「一份」：分身（`run_twin.py`）在**它自己做的事**發生的當下
寫一筆旁註。現在只有一種——`postaudit`：OFF 那一跑結束之後，分身用同一把尺
（`tests_visible`）在 OFF 的凍結快照上補量一次（`run_twin.postaudit_off`）。

```
 vacant run ──lifecycle.jsonl──────────┐   Vacant 當場觀察到的（契約：lifecycle.py）
 run_twin.postaudit_off ──X.sidecar.jsonl ┴─▶ live_events.Folder ──▶ 電視 postaudit
                          分身自己事後做的（契約：這一支）
```

`counters` **不在旁註裡**：它不是任何人「做」的一件事，是 `serve_twin` 依
**已經播過的格子**當場數出來的（`live_events.Tally`）。旁註只記發生過的事。

## 放哪裡：旁邊一個同名 `X.sidecar.jsonl`（**不**混進 lifecycle 同一個檔）

選了分檔，理由依重要性排：

1. **lifecycle 檔要維持「純 Vacant」。** `lifecycle.validate_stream` 見到不認得的
   schema 會判整份不合格，而 `serve_twin.load_recordings` 的規則是「一行壞就整份不收」。
   混在同一個檔 ⇒ 要嘛改 Vacant 的 validate（不准動 `vrun/*`），要嘛每一個讀
   lifecycle 的人都得先學會「跳過分身的行」——第一個沒學會的讀者會把整份錄影判死，
   或者更糟：學會「跳過不認得的行」，之後 Vacant 真的換版時也安靜地跳過。
2. **兩個作者、兩份來歷，在檔案層就分得開。** 「這一行是 Vacant 當場觀察到的」
   與「這一行是分身事後補量的」是展場最不能混的兩句話（鐵律 5 的展場版本）。
   分檔之後，連 `grep` 都不會把它們混成一句。
3. **寫的人本來就不同。** lifecycle 是 `launcher` 裡的 `Emitter` 開檔追加；
   旁註是 `run_twin` 在 `launcher.run` 回來之後追加。同一個檔兩個寫者，
   要靠行寫入的原子性撐著；分檔就沒有這個問題。

分檔的代價與補法：

- **錄影的 sha256 綁定原本只涵蓋 lifecycle 那一個檔。** ⇒ `pair_receipts` 另外綁
  旁註的 sha256（`pack["recording"]["sidecar"]`），規則對稱：資料包綁了旁註而旁註
  不在、旁註在而資料包沒綁、sha256 對不上，三種都不收（`pair_receipts.check_sidecar`）。
- **`recordings/*.jsonl` 的 glob 會掃到 `X.sidecar.jsonl`。** ⇒
  `serve_twin.default_recordings` 用 `is_sidecar` 排掉；就算有人硬塞
  `--recording X.sidecar.jsonl`，它過不了 `lifecycle.validate_stream`，照樣整份不收。
- **現場真跑要 tail 兩個檔。** ⇒ `serve_twin --live L.jsonl` 自動 tail
  `sidecar_path(L)`，兩者都用 `live_events.Tail`。

## 契約（`twin.sidecar/1`）

每一行一個 JSON 物件。共同欄位 `COMMON`，各型別專屬欄位 `FIELDS`（**key 一定要在**，
值可以是 `None`——「沒量到」要看得見）。`validate()` 是可執行版本。

`postaudit`：

| 欄位 | 意思 |
|---|---|
| `cell_id` | 哪一格（＝ lifecycle `run_started.caller.cell_id`） |
| `run_id` | **被量的那一跑**（OFF 臂）的 lifecycle `run_id` |
| `ws_end_sha256` | 那一跑 `run_ended.ws_end_sha256`：量的就是這棵凍結的樹 |
| `arm` | 恆 `"OFF"` |
| `when` | 恆 `"after_the_run"` |
| `is_verdict` | 恆 `false` |
| `signed` | 恆 `false` |
| `all_pass`／`passed`／`total` | 同一份 `tests_visible` 的結果 |
| `failed_case` | 第一個沒過的案例**名字**（不帶訊息全文），全過＝`null` |
| `ruler`／`note` | 用哪一把尺、以及「這不是裁決」那一句 |

## 綁定（`validate(rows, lifecycle_events=…)`）

每一筆 `postaudit` 都要綁得上**同一份錄影裡**的一跑：`run_id` 存在、是 `RUN-OFF`、
有 `run_ended`、不是 `infra_void`、`ws_end_sha256` 相等、`cell_id` 相等、
`ts_ms` 不早於那一跑的 `run_ended`（「事後」要在資料上成立）、一跑最多一筆。
綁不上 ⇒ 整份旁註不收（**不是**整份錄影不收：lifecycle 是 Vacant 的紀錄，
它本身沒壞；壞的是分身的註，那就不演分身的註）。

## 誠實邊界（改碼時保留）

1. **旁註不是證據，也不是裁決。** 沒有簽章、沒有進收據鏈；三個旗標
   （`when`／`is_verdict`／`signed`）缺一不可，`validate` 與電視契約各擋一次。
2. **旁註不准改變一跑的任何東西。** 它在 `launcher.run` 回來**之後**才寫，
   寫不進去只印一行警告（`append` 回錯誤字串，不丟例外）。
3. **不帶內容。** 不寫案例訊息全文、不寫程式碼、不寫 prompt（`CONTENT_KEYS`）。
4. **不准拿舊 run 目錄補寫旁註。** 旁註只在 `postaudit_off` 完成的當下寫；
   事後替沒有旁註的舊錄影補一份＝事後推導從後門回來（與 `pair_receipts`
   誠實邊界 3 同一條）。舊錄影沒有旁註，電視上就沒有 postaudit。
"""
from __future__ import annotations

import json
import os
import pathlib
import time
from typing import Any, Iterable

SCHEMA = "twin.sidecar/1"

#: 檔名後綴：`X.jsonl` 的旁註是 `X.sidecar.jsonl`。
SUFFIX = ".sidecar.jsonl"

TYPES = ("postaudit",)

COMMON = ("schema", "type", "ts_ms", "cell_id", "run_id")

FIELDS: dict[str, tuple[str, ...]] = {
    "postaudit": ("arm", "ws_end_sha256", "when", "is_verdict", "signed",
                  "all_pass", "passed", "total", "failed_case", "ruler", "note"),
}

WHEN_AFTER = "after_the_run"

#: 旁註裡不准出現的內容欄位（誠實邊界 3）。
CONTENT_KEYS = ("cases", "message", "body", "request", "response", "messages",
                "prompt", "code", "source")

#: lifecycle 那一側 OFF 臂的名字（launcher 的 `arm`）。
LC_ARM_OFF = "RUN-OFF"


def sidecar_path(lifecycle_path: str | os.PathLike) -> pathlib.Path:
    """`X.jsonl` → `X.sidecar.jsonl`（同目錄）。"""
    p = pathlib.Path(lifecycle_path)
    return p.with_name(p.stem + SUFFIX)


def is_sidecar(path: str | os.PathLike) -> bool:
    return pathlib.Path(path).name.endswith(SUFFIX)


def _first_failed(result: dict) -> str | None:
    """第一個沒過的可見測試名。**走訪順序與 ON 臂 `gate_ran.failed_case` 相同**
    （`launcher._first_failed_case`：`files[*].cases[*]`），兩臂同一把尺、同一種讀法。"""
    for f in result.get("files") or []:
        for c in f.get("cases") or []:
            if not c.get("ok"):
                return c.get("case")
    return None


def postaudit_row(pa: dict, *, cell_id: str, run_id: str,
                  ws_end_sha256: str | None, ts_ms: int | None = None) -> dict:
    """`run_twin.postaudit_off` 的回傳 → 一筆旁註。三個旗標**寫死**，不從 `pa` 抄。

    ⚠ 寫死的理由：`pa` 是 `run_twin` 自己組的 dict，改碼的人手滑把 `is_verdict`
      改成 `True` 也不會有任何東西攔他；旁註這一層再寫死一次，資料上就不可能出現
      「事後稽核自稱裁決」。
    """
    return {
        "schema": SCHEMA, "type": "postaudit",
        "ts_ms": int(ts_ms if ts_ms is not None else time.time() * 1000),
        "cell_id": cell_id, "run_id": run_id, "arm": "OFF",
        "ws_end_sha256": ws_end_sha256,
        "when": WHEN_AFTER, "is_verdict": False, "signed": False,
        "all_pass": bool(pa.get("all_pass")),
        "passed": pa.get("passed"), "total": pa.get("total"),
        "failed_case": _first_failed(pa),
        "ruler": pa.get("ruler"), "note": pa.get("note"),
    }


def append(path: str | os.PathLike, row: dict) -> str | None:
    """追加一行。回 `None`＝寫進去了；否則回錯誤字串（**不丟例外**，誠實邊界 2）。"""
    try:
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
        return None
    except (OSError, TypeError, ValueError) as exc:
        return f"{type(exc).__name__}: {exc}"


def read(path: str | os.PathLike) -> list[dict]:
    """讀整個檔；不存在＝空清單。最後一行寫到一半不算（`lifecycle.read` 同一條規則）。"""
    p = pathlib.Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            break
    return out


def _is_nat(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _runs(lifecycle_events: Iterable[dict]) -> dict[str, dict[str, Any]]:
    runs: dict[str, dict[str, Any]] = {}
    for e in lifecycle_events:
        rid = e.get("run_id")
        if e.get("type") == "run_started":
            caller = e.get("caller") or {}
            runs[rid] = {"arm": e.get("arm"), "ended": False,
                         "cell_id": caller.get("cell_id") or e.get("task_id")}
        elif e.get("type") == "run_ended" and rid in runs:
            runs[rid].update(ended=True, ended_ms=e.get("ts_ms"),
                             ws_end=e.get("ws_end_sha256"),
                             infra_void=e.get("infra_void"))
    return runs


def validate(rows: Iterable[dict], *,
             lifecycle_events: Iterable[dict] | None = None) -> list[str]:
    """旁註契約自檢（＋給了 lifecycle 就一併驗綁定）。回問題清單（空＝合格）。"""
    bad: list[str] = []
    runs = _runs(lifecycle_events) if lifecycle_events is not None else None
    seen: set[str] = set()
    for i, r in enumerate(rows, 1):
        for k in COMMON:
            if k not in r:
                bad.append(f"旁註第 {i} 筆缺共同欄位 {k}")
        if r.get("schema") != SCHEMA:
            bad.append(f"旁註第 {i} 筆 schema 是 {r.get('schema')!r}，不是 {SCHEMA}")
        t = r.get("type")
        if t not in FIELDS:
            bad.append(f"旁註第 {i} 筆 type 不在契約裡：{t!r}")
            continue
        for k in FIELDS[t]:
            if k not in r:
                bad.append(f"旁註第 {i} 筆（{t}）缺欄位 {k}")
        for k in CONTENT_KEYS:
            if k in r:
                bad.append(f"旁註第 {i} 筆夾帶了內容欄位 {k}")
        if not _is_nat(r.get("ts_ms")):
            bad.append(f"旁註第 {i} 筆 ts_ms 不是非負整數")
        if t == "postaudit":
            # ── 事後稽核不准長得像裁決：三個旗標缺一不可 ──────────────
            if r.get("is_verdict") is not False:
                bad.append(f"旁註第 {i} 筆：postaudit 的 is_verdict 必須是 false")
            if r.get("signed") is not False:
                bad.append(f"旁註第 {i} 筆：postaudit 的 signed 必須是 false")
            if r.get("when") != WHEN_AFTER:
                bad.append(f"旁註第 {i} 筆：postaudit 沒說它是事後量的"
                           f"（when 必須是 {WHEN_AFTER!r}）")
            if r.get("arm") != "OFF":
                bad.append(f"旁註第 {i} 筆：postaudit 只量 OFF 臂（ON 臂有自己的閘門）")
            if not isinstance(r.get("all_pass"), bool):
                bad.append(f"旁註第 {i} 筆：all_pass 只能是 true／false")
            p, n = r.get("passed"), r.get("total")
            if not (_is_nat(p) and _is_nat(n) and p <= n):
                bad.append(f"旁註第 {i} 筆：passed／total 要是 0 ≤ passed ≤ total 的整數")
            elif r.get("all_pass") is True and p != n:
                bad.append(f"旁註第 {i} 筆：all_pass=true 卻只過了 {p}/{n}")
            rid = r.get("run_id")
            if rid in seen:
                bad.append(f"旁註第 {i} 筆：同一跑 {rid} 有兩筆 postaudit")
            seen.add(rid)
            if runs is None:
                continue
            # ── 綁定：這一筆量的是錄影裡的哪一跑 ─────────────────────
            run = runs.get(rid)
            if run is None:
                bad.append(f"旁註第 {i} 筆：run_id {rid} 不在這份錄影裡")
                continue
            if run["arm"] != LC_ARM_OFF:
                bad.append(f"旁註第 {i} 筆：run_id {rid} 是 {run['arm']}，不是 OFF 臂")
            if not run["ended"]:
                bad.append(f"旁註第 {i} 筆：那一跑在錄影裡沒有 run_ended")
                continue
            if run.get("infra_void"):
                bad.append(f"旁註第 {i} 筆：那一跑 infra_void（沒跑成），不該有事後稽核")
            if r.get("ws_end_sha256") != run.get("ws_end"):
                bad.append(f"旁註第 {i} 筆：ws_end_sha256 與那一跑的 run_ended 不同"
                           "（量的不是那一棵樹）")
            if r.get("cell_id") != run["cell_id"]:
                bad.append(f"旁註第 {i} 筆：cell_id {r.get('cell_id')!r} 與那一跑的格子"
                           f" {run['cell_id']!r} 不同")
            if _is_nat(r.get("ts_ms")) and _is_nat(run.get("ended_ms")) \
                    and r["ts_ms"] < run["ended_ms"]:
                bad.append(f"旁註第 {i} 筆：ts_ms 早於那一跑的 run_ended——"
                           "「事後」在資料上不成立")
    return bad


def merge(lifecycle_events: list[dict], rows: list[dict]) -> list[dict]:
    """lifecycle ＋ 旁註 → 一條給 `Folder` 吃的串流。

    每一筆旁註插在**它綁的那一跑的 `run_ended` 之後**（不是照 `ts_ms` 重排：
    重排可能動到 lifecycle 自己的順序）。綁不上的旁註接在最後——`Folder` 會因為
    找不到那一跑而不發事件（不猜）。呼叫端應該先 `validate`。
    """
    by_run: dict[str, list[dict]] = {}
    for r in rows:
        by_run.setdefault(r.get("run_id"), []).append(r)
    out: list[dict] = []
    for e in lifecycle_events:
        out.append(e)
        if e.get("type") == "run_ended":
            out.extend(by_run.pop(e.get("run_id"), []))
    for rest in by_run.values():
        out.extend(rest)
    return out
