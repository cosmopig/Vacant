#!/usr/bin/env python3
"""逐 run 驗收據鏈：創世→鏈頭連續、每筆 Ed25519 簽章有效、條數與 rows 對得上。

這支在架構裡承重什麼：收據是 Vacant 對外唯一「不用信任我」的東西。R460R／R529
的 run 目錄裡各臂都落了 `receipts_<ARM>.ndjson` ＋ `receipts_<ARM>.pub.json`，
但**落盤 ≠ 驗得起來**（`CRITERION_20260903_R666` 就是為了這個差別寫的）。
本檔是稽核端：不讀模型、不讀 cache，只拿鏈檔與公鑰重算。

與 `vacant_network/logbook.py::Logbook.verify_chain` 的關係：那支回一個 bool，
**壞在哪一筆看不出來**。本檔逐字重跑它的同一套規則（同一個
`_signed_bytes`／`_entry_hash`，不是另寫一份），差別只在**逐筆記錄失敗原因**
——任何一條失敗都要指得出 seq、type、原因，而不是只報一個 False。
兩邊的結論必須一致：`chain_ok` 與 `logbook_verify_chain` 兩個欄位都輸出，
不一致本身就是 `verdict=BROKEN`（那代表本檔漂掉了，不是鏈壞了）。

條數對帳（每題每臂一個 verdict）：
  · `harness_verdict`／`conform_verdict` 的條數 == 該臂在 `rows.jsonl` 的列數；
  · verdict 的 `task_id` 集合 == 該臂 rows 的 `task_id` 集合（不是只比個數）；
  · `*_attempt` 條數 ≥ verdict 條數（多輪臂會多；少於就是漏寫）。
⚠ **沒有收據檔的臂不是失敗**：OFF／OFF5 本來就沒有收據這回事，
  記成 `arms_without_receipts` 而不是 BROKEN——「沒量到」≠「量到 0」。

## 中介維度（2026-09-19 加）：`chain_ok` 單獨不准成立

2026-09-19 的隨傳隨到負控制（`runs/v1_five_agent_matrix_20260919/controls.sh`）
把 `/bin/true` 和一行 `cp` 放在 agent 的位置，**一通模型都不打**：

    ctl_norequest_refuse    exit 20   accepted=false  visible_fail   rs=0  rc=0
    ctl_norequest_deliver   exit 0    accepted=true   visible_pass   rs=0  rc=0

**退出碼、`accepted`、`stop_reason`、`agent_rc`、`chain_ok` 五個欄位在零通模型
呼叫下全部成立**，而當時本檔對這兩格的總判是乾淨的 `OK`。那等於這把尺說得出
「這張收據沒被改過」，說不出「這張收據底下有沒有發生過中介」——而 `vacant run`
的**全部意義**就是中介。

所以本檔多一個**正交**的維度：

  · `chain_ok`      ——鏈本身完整嗎？（**語意一個字都沒改**）
  · `mediated`      ——這一格的模型通道真的有流量嗎？
                       `True`／`False`／`None`（＝這條鏈沒有記這件事）
  · `void_reason`   ——`mediated is False` 時說出是哪一種。

⚠ **不准把 `chain_ok` 改成 `False`**：零請求的那一格，鏈**確實**是完整的，
  說它壞掉是另一種說謊。兩件事分開講，總判才有辦法同時反映兩者：
  `verdict ∈ {OK, VOID, BROKEN, UNVERIFIABLE}`，**VOID ＝鏈是好的、但這一格
  不是「中介發生過」的證據**。

⚠ **誠實邊界（改碼請保留）**：這個維度擋得住的是「**完全沒打**」，
  **擋不住「打了但打到別的地方」**。`requests_seen > 0` 只代表有 bytes 經過
  本機的 proxy，不代表那些 bytes 去了你以為的那台機器——那要看
  `run_<ARM>.json` 的 `wire_by_protocol` 與 `upstreams`（誰指定了上游位址、
  有沒有落到 sink 或公開 API），而**那兩個欄位不在簽章鏈上**。
  本檔對它們一個字都說不出來。

⚠ **`--allow-no-suite` 不是假拒交格，不准誤殺**：那一格明講「這一次不量驗收」
  （`accepted_is_null=true`、`stop_reason ∈ {no_suite, ungated}`），而它的模型
  通道照樣可能有流量。兩個維度**正交**：ungated 的格子照樣要問 `requests_seen`，
  有流量就不是 VOID。

## 它住在哪（2026-09-18 搬家）

本檔的實作住在套件裡（`vacant_network/vrun/verify_receipts.py`），因為 `pip install
vacant-network` 的人也要驗得動自己 `vacant run` 跑出來的收據——驗章器只存在於
repo checkout 裡的話，「不用信任我」這句話對下載的人不成立。
`ops/gain/replay/verify_run_receipts.py` **仍然是那個路徑、仍然可以直接執行**，
它現在是一層 re-export：`sys.modules` 指到本檔，所以**只有一份判準、不會漂**。

用法（兩行等價，跑的是同一支）：
    python3 ops/gain/replay/verify_run_receipts.py \\
        --glob 'runs/g_r460r[123]_*' --json ops/gain/replay/r460r/receipts_verify.json
    python3 -m vacant_network.vrun.verify_receipts --selftest
"""
from __future__ import annotations

import argparse
import json
import pathlib


def _glob_base() -> pathlib.Path:
    """相對 `--glob` 的基準目錄。

    這支在架構裡承重什麼：搬進套件之前，「相對 pattern 以 repo 根為基準」是靠
    `__file__` 往上數四層算出來的。裝成 wheel 之後那個算法會指到 site-packages
    ——一個**不存在 `runs/` 的地方**，於是 `--glob 'runs/…'` 會靜靜地零筆命中，
    而零筆命中在本檔的判準裡是 `UNVERIFIABLE` 不是錯誤。安靜的零是最糟的失敗法。

    所以改成：認得出 repo checkout（同時有 `pyproject.toml` 與 `runs/`）就維持
    舊行為；認不出就以 **cwd** 為基準——那是 `pip install` 之後唯一有意義的解讀，
    也是使用者打那行指令時心裡想的那個目錄。絕對 pattern 兩種情況都照絕對解，
    不受本函式影響（`_glob_dirs`）。
    """
    repo = pathlib.Path(__file__).resolve().parents[2]
    if (repo / "pyproject.toml").is_file() and (repo / "runs").is_dir():
        return repo
    return pathlib.Path.cwd()


ROOT = _glob_base()

from ..crypto import pub_to_hex  # noqa: E402
from ..identity import Identity, PublicIdentity  # noqa: E402
from ..logbook import (EMPTY_PREV_HASH, GENESIS_STREAM_ID,  # noqa: E402
                       Logbook, _signed_bytes)

def _rel(p: pathlib.Path) -> str:
    """相對 repo 根的路徑；不在 repo 底下（selftest 的 tmpdir）就給絕對路徑。"""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


#: 收據的事件別 → 它對帳的那一邊。`*_verdict` 每題一筆，`*_attempt` 每輪一筆。
#:
#: round530（2026-09-13）：加上 R530 的兩個型別。**對帳規則一個字都沒改**——
#: 加的只是「認得這兩個名字」。認不得的型別會讓 `verdict_n` 變成 0，
#: 於是每一條 R530 的鏈都判 BROKEN（`verdict_count_ne_rows`），
#: 而那是量具沒接上，不是鏈壞了。
#: `ws_attempt`：每一個閘門輪／每一次重抽嘗試一筆；`A-SOLO` 宣告完成時也一筆
#:   （`verdict_sha256=None` ＝這一輪沒有跑驗收）⇒ `attempt 數 ≥ verdict 數`
#:   這條對帳在沒有閘門的那條臂上照樣成立。
#: `ws_verdict`：每格一筆（每題每臂）。
#: ⚠ **R530 的兩個型別有兩套名字，兩套都認**：Fable 2026-09-13 給建置代理的
#:   裁決寫的是 `ws_attempt`／`ws_verdict`，而同一天更新的預註冊
#:   （§五-4、§三-6 C6）寫的是 `openwork_attempt`／`openwork_verdict`。
#:   兩邊指的是同一件事。認一套而漏另一套會讓那一批鏈判 `verdict_count_ne_rows`
#:   ——而那是量具沒接上，不是鏈壞了。**命名要由人類／Fable 收斂成一套**；
#:   在那之前這裡兩套都收，並且在收斂之後才准刪。
VERDICT_TYPES = ("harness_verdict", "conform_verdict",
                 "ws_verdict", "openwork_verdict")
ATTEMPT_TYPES = ("harness_attempt", "conform_attempt",
                 "ws_attempt", "openwork_attempt")

#: 收據 payload 裡「這一格有沒有真的中介到模型通道」的那個欄位。
#: `vacant_network/vrun/launcher.py` 每一筆 `ws_attempt`／`ws_verdict` 都簽它進去。
#:
#: ⚠ **舊鏈沒有這個欄位**：2026-09-19 掃過 `runs/`，R460R／R529／R530 那
#:   6,468 筆 verdict（`conform_verdict` 2,581＋`harness_verdict` 3,711＋
#:   `ws_verdict` 176）一筆都沒有。沒有欄位 ⇒ `mediated=None` ＝**沒量到**，
#:   **不是**「量到 0」（鐵律 3）。把舊鏈判成 VOID 會把一句沒說過的話塞進
#:   已歸檔的資料裡。
MEDIATION_FIELD = "requests_seen"

#: `--allow-no-suite` 那一格的指紋。**它不是假拒交格**——見模組 docstring。
UNGATED_STOP_REASONS = ("no_suite", "ungated")

#: 認證維度（2026-09-20，`DECISION_20260920_COMPLETE_MEDIATION` §二 P0）。
#: 跟 `MEDIATION_FIELD` 同一個模式：**舊鏈沒有這一欄 ⇒ `None`＝沒量到**，
#: 一筆已歸檔資料都不會因為本檔多讀一個欄位而改判。
TIER_FIELD = "tier"
ATTESTED_FIELD = "attested"

#: 總判 → 退出碼。**單一真相來源**：`vacant_network/vrun/demo.py` 的防呆拿它當判準，
#: 不准在別處寫死第二份（同 `launcher.EXIT_REFUSED` 的作法）。
EXIT_OK, EXIT_BROKEN, EXIT_VOID = 0, 1, 3


def verify_chain_detailed(book: Logbook, who: PublicIdentity) -> list[dict]:
    """逐筆重跑 `Logbook.verify_chain` 的規則，回**失敗清單**（空＝全過）。

    規則逐字照抄那一支（seq 連續、prev_hash 串對、stream/branch 一致、簽章過），
    只是不提早 return，好讓一條壞鏈把所有壞點都吐出來。
    """
    fails: list[dict] = []
    if not book.entries:
        return fails
    genesis = book.entries[0]
    if genesis.stream_id != GENESIS_STREAM_ID:
        fails.append({"seq": genesis.seq, "type": genesis.type,
                      "reason": "genesis_stream_id_not_sentinel",
                      "got": genesis.stream_id, "want": GENESIS_STREAM_ID})
    expected_stream = genesis.hash()
    expected_branch = genesis.branch_id
    prev_hash = EMPTY_PREV_HASH
    expected_seq = 1
    for e in book.entries:
        if e.seq != expected_seq:
            fails.append({"seq": e.seq, "type": e.type, "reason": "seq_not_contiguous",
                          "got": e.seq, "want": expected_seq})
        if e.prev_hash != prev_hash:
            fails.append({"seq": e.seq, "type": e.type, "reason": "prev_hash_broken",
                          "got": e.prev_hash, "want": prev_hash})
        if e.seq > 1 and e.stream_id != expected_stream:
            fails.append({"seq": e.seq, "type": e.type, "reason": "stream_id_mismatch",
                          "got": e.stream_id, "want": expected_stream})
        if e.seq > 1 and e.branch_id != expected_branch:
            fails.append({"seq": e.seq, "type": e.type, "reason": "branch_id_mismatch",
                          "got": e.branch_id, "want": expected_branch})
        #: 驗簽失敗時的例外原文；沒有例外就是 None。純宣告，**執行期不產生
        #: 任何指令**（函式內的裸標註只進 AST 不進 bytecode）。
        exc_s: str | None
        try:
            sig_ok = who.verify(
                _signed_bytes(e.stream_id, e.branch_id, e.seq, e.prev_hash,
                              e.ts_ms, e.type, e.payload),
                bytes.fromhex(e.sig))
        except Exception as exc:                                  # noqa: BLE001
            sig_ok, exc_s = False, repr(exc)
        else:
            exc_s = None
        if not sig_ok:
            fails.append({"seq": e.seq, "type": e.type, "reason": "bad_signature",
                          "sig": e.sig[:32] + "…", "exception": exc_s,
                          "task_id": (e.payload or {}).get("task_id")
                          if isinstance(e.payload, dict) else None})
        prev_hash = e.hash()
        expected_seq += 1
    return fails


def mediation_of(verdicts: list) -> dict:
    """從 verdict 收據推出**中介維度**。與鏈的完整性（`chain_ok`）正交。

    回三個欄位＋四個數字。三種結論，**三種都要分得開**：

      `mediated=None`   這條鏈沒有記 `requests_seen`（舊鏈）⇒ **沒量到**。
                        不是 VOID：把沒說過的話塞進已歸檔資料是另一種說謊。
      `mediated=False`  有記，而且**有格子是 0** ⇒ 那一格的模型通道
                        一個 byte 都沒經過 ⇒ `void_reason="no_requests_seen"`。
      `mediated=True`   有記，而且每一格都 > 0。

    ⚠ `bool` 是 `int` 的子類，`isinstance(True, int)` 為真——所以這裡先把
      bool 踢掉再認 int，否則一個寫錯型別的 `requests_seen: false`
      會被讀成「0 通」而不是「這個欄位壞了」。

    ⚠ **這只擋得住「完全沒打」，擋不住「打了但打到別的地方」**
      （見模組 docstring 的誠實邊界）。
    """
    declared = absent = total = 0
    zero_ids: list = []
    ungated_ids: list = []
    for e in verdicts:
        p = e.payload if isinstance(e.payload, dict) else {}
        tid = p.get("task_id")
        if (p.get("accepted_is_null") is True
                or p.get("stop_reason") in UNGATED_STOP_REASONS):
            ungated_ids.append(tid)
        v = p.get(MEDIATION_FIELD)
        if isinstance(v, bool) or not isinstance(v, int):
            absent += 1
            continue
        declared += 1
        total += v
        if v == 0:
            zero_ids.append(tid)
    out: dict = {
        "mediated": None, "void_reason": None,
        "verdicts_with_requests_seen": declared,
        "verdicts_without_requests_seen": absent,
        # 一筆都沒宣告 ⇒ `None` 而不是 `0`：「沒量到」≠「量到 0」。
        "requests_seen_total": total if declared else None,
        "unmediated_task_ids": sorted(x for x in zero_ids if x is not None),
        "ungated_task_ids": sorted(x for x in ungated_ids if x is not None),
    }
    if declared == 0:
        return out                      # mediated 維持 None＝沒量到
    if zero_ids:
        out.update({"mediated": False, "void_reason": "no_requests_seen"})
    else:
        out["mediated"] = True
    return out


def attestation_of(verdicts: list) -> dict:
    """從 verdict 收據推出**認證維度**。與 `chain_ok`、`mediated` 都正交。

    三種結論，**三種都要分得開**（跟 `mediation_of` 同一條紀律）：

      `attested=None`   這條鏈沒有記 `tier`（舊鏈，或 `VACANT_ATTEST=off`）
                        ⇒ **沒量到**。不是「不合格」——把沒說過的話塞進
                        已歸檔資料是另一種說謊。
      `attested=False`  有記，而且**有格子不是 A 級** ⇒ 那一格的紀錄不足以
                        究責（`unattested_task_ids` 點名是哪幾格）。
      `attested=True`   有記，而且每一格都是 A 級。

    ⚠ 本函式**不動 `verdict`**。理由跟 `mediated` 當初一樣：級別低不代表鏈壞
      了，兩個維度混成一個就分不出「鏈被改過」與「這一跑沒受控」。
      要讓級別有牙齒用 `run_glob(..., require_tier="A")`（**預設關**）。
    """
    declared = absent = 0
    tiers: dict[str, int] = {}
    bad_ids: list = []
    for e in verdicts:
        pl = e.payload if isinstance(e.payload, dict) else {}
        t = pl.get(TIER_FIELD)
        if not isinstance(t, str):
            absent += 1
            continue
        declared += 1
        tiers[t] = tiers.get(t, 0) + 1
        if t != "A":
            bad_ids.append(pl.get("task_id"))
    out: dict = {
        "attested": None, "tier": None, "tiers": tiers,
        "verdicts_with_tier": declared, "verdicts_without_tier": absent,
        "unattested_task_ids": sorted(x for x in bad_ids if x is not None),
    }
    if declared == 0:
        return out                      # attested 維持 None＝沒量到
    out["tier"] = (next(iter(tiers)) if len(tiers) == 1 else "mixed")
    out["attested"] = not bad_ids
    return out


def verify_arm(run: pathlib.Path, arm: str, rows: list[dict]) -> dict:
    """一個 run 的一條臂鏈。回一列報表（含失敗原文）。"""
    chain = run / f"receipts_{arm}.ndjson"
    pub = run / f"receipts_{arm}.pub.json"
    rec: dict = {"run": run.name, "arm": arm,
                 "chain_file": _rel(chain),
                 "entries_n": 0, "verified_n": 0, "failed_n": 0,
                 "chain_ok": None, "logbook_verify_chain": None,
                 "stream_id": None, "head": None,
                 # 中介維度（與 `chain_ok` 正交）。提早不到這裡的兩條路
                 # （沒公鑰、空鏈）也要有這兩欄，否則呼叫端會看到欄位忽有忽無。
                 "mediated": None, "void_reason": None,
                 # 認證維度（與 `chain_ok`、`mediated` 都正交）。
                 # 提早回去的兩條路也要有這兩欄，否則呼叫端會看到欄位忽有忽無。
                 "attested": None, "tier": None,
                 "type_counts": {}, "failures": [], "verdict": "UNVERIFIABLE"}
    if not pub.exists():
        rec["failures"].append({"reason": "pubkey_file_missing", "path": str(pub)})
        return rec
    meta = json.loads(pub.read_text(encoding="utf-8"))
    who = PublicIdentity.from_hex(meta["vacant_id"], meta["pub_hex"])
    rec["vacant_id"] = meta["vacant_id"]
    book = Logbook.load(chain)
    rec["entries_n"] = len(book)
    if not book.entries:
        rec["failures"].append({"reason": "empty_chain"})
        return rec
    fails = verify_chain_detailed(book, who)
    bad_seqs = {f["seq"] for f in fails}
    rec["failures"] += fails
    rec["failed_n"] = len(bad_seqs)
    rec["verified_n"] = len(book) - len(bad_seqs)
    rec["chain_ok"] = not fails
    rec["logbook_verify_chain"] = bool(book.verify_chain(who))
    if rec["chain_ok"] != rec["logbook_verify_chain"]:
        rec["failures"].append({"reason": "detailed_vs_logbook_disagree",
                                "detailed": rec["chain_ok"],
                                "logbook": rec["logbook_verify_chain"]})
    rec["stream_id"] = book.stream_id()
    rec["head"] = book.head()
    rec["genesis_hash_is_stream_id"] = (book.entries[0].hash() == book.stream_id())
    counts: dict[str, int] = {}
    for e in book.entries:
        counts[e.type] = counts.get(e.type, 0) + 1
    rec["type_counts"] = dict(sorted(counts.items()))

    # ── 條數對帳：每題每臂一個 verdict ────────────────────────────────
    arm_rows = [r for r in rows if r.get("arm") == arm]
    vt = [e for e in book.entries if e.type in VERDICT_TYPES]
    at = [e for e in book.entries if e.type in ATTEMPT_TYPES]
    rec["rows_n"] = len(arm_rows)
    rec["verdict_n"] = len(vt)
    rec["attempt_n"] = len(at)
    if len(vt) != len(arm_rows):
        rec["failures"].append({"reason": "verdict_count_ne_rows",
                                "verdict_n": len(vt), "rows_n": len(arm_rows)})
    v_ids = {(e.payload or {}).get("task_id") for e in vt}
    r_ids = {r.get("task_id") for r in arm_rows}
    if v_ids != r_ids:
        rec["failures"].append({"reason": "verdict_task_ids_ne_rows",
                                "only_in_receipts": sorted(x for x in v_ids - r_ids
                                                           if x is not None),
                                "only_in_rows": sorted(x for x in r_ids - v_ids
                                                       if x is not None)})
    if len(vt) != len(v_ids):
        rec["failures"].append({"reason": "duplicate_verdict_for_task",
                                "verdict_n": len(vt), "distinct_task_ids": len(v_ids)})
    if len(at) < len(vt):
        rec["failures"].append({"reason": "attempt_fewer_than_verdict",
                                "attempt_n": len(at), "verdict_n": len(vt)})

    # ── 中介維度 ──────────────────────────────────────────────────────
    #  ⚠ **`chain_ok` 一個字都沒動**。零請求的那一格鏈是完整的，改成 False
    #    是另一種說謊；這裡新增的是一個獨立的維度，讓「鏈完整」與
    #    「中介發生過」分開講。
    rec.update(mediation_of(vt))
    # ── 認證維度 ──────────────────────────────────────────────────────
    #  ⚠ 同樣**一個字都不動 `chain_ok`**，也不動 `verdict`：級別低不代表
    #    鏈壞了。要讓級別有牙齒得明講（`run_glob(require_tier=...)`）。
    rec.update(attestation_of(vt))
    rec["verdict"] = ("BROKEN" if rec["failures"] else
                      "VOID" if rec["mediated"] is False else "OK")
    return rec


def verify_run(run: pathlib.Path) -> list[dict]:
    rows_p = run / "rows.jsonl"
    rows = ([json.loads(l) for l in rows_p.open(encoding="utf-8") if l.strip()]
            if rows_p.exists() else [])
    arms = sorted(p.name[len("receipts_"):-len(".ndjson")]
                  for p in run.glob("receipts_*.ndjson"))
    out = [verify_arm(run, a, rows) for a in arms]
    seen = {r.get("arm") for r in out}
    for rec in out:
        rec["arms_without_receipts"] = sorted(
            {r.get("arm") for r in rows} - seen - {None})
    return out


def _glob_dirs(pattern: str) -> list[pathlib.Path]:
    """相對 pattern 以 repo 根為基準；**絕對 pattern 照絕對解**。

    絕對那條是給 repo 以外的 run 目錄用的（`vacant run --run-dir ~/…`、
    `vacant demo gate`）。少了它，畫面上印給使用者複製的那行驗證指令
    就是一行跑不動的字——**能複製貼上才叫「你自己驗得出來」**。
    `pathlib.Path.glob` 在 3.11／3.12 不吃絕對 pattern（3.13 才吃），
    所以這裡自己把 anchor 切開，不靠版本差異。
    """
    p = pathlib.Path(pattern)
    if p.is_absolute():
        rel = str(p.relative_to(p.anchor))
        base = pathlib.Path(p.anchor)
        # 沒有萬用字元就不必 glob（也避開路徑裡有 `[` 之類字元時的誤判）
        cand = [p] if not any(c in rel for c in "*?[") else list(base.glob(rel))
        return sorted(d for d in cand if d.is_dir())
    return sorted(d for d in ROOT.glob(pattern) if d.is_dir())


def run_glob(pattern: str, *, require_tier: str | None = None) -> dict:
    """驗一批 run。

    `require_tier="A"` ＝ **展場那條線**（裁決 §三-3「展場只允許 A 級」）：
    每一條鏈都要是 A 級，不是就多一筆 `tier_below_required` 的失敗 ⇒ BROKEN。
    **預設 `None` ＝不要求**，所以既有 98 個歸檔 run 的判決逐字不變
    （它們連 `tier` 欄位都沒有 ⇒ `attested=None`＝沒量到）。
    """
    dirs = _glob_dirs(pattern)
    rows: list[dict] = []
    for d in dirs:
        rows += verify_run(d)
    if require_tier:
        for r in rows:
            if r.get("tier") != require_tier:
                r["failures"].append({
                    "reason": "tier_below_required",
                    "required": require_tier, "got": r.get("tier"),
                    "note": ("`tier=null` ＝**沒量到**，不是「不合格」——"
                             "但在要求級別的那條線上，沒量到一樣過不了")})
                r["verdict"] = "BROKEN"
    # `VOID` 不算進 `broken_chains_n`：那一欄的語意是「鏈壞了」，而 VOID 的鏈
    # 沒壞。**舊資料一筆都不會變**——沒有 `requests_seen` 欄位就不可能 VOID。
    broken = [r for r in rows if r["verdict"] not in ("OK", "VOID")]
    void = [r for r in rows if r["verdict"] == "VOID"]
    return {
        "glob": pattern, "runs_n": len(dirs), "chains_n": len(rows),
        "entries_total": sum(r["entries_n"] for r in rows),
        "verified_total": sum(r["verified_n"] for r in rows),
        "failed_total": sum(r["failed_n"] for r in rows),
        "broken_chains_n": len(broken),
        # ── 中介維度的總帳（三種結論分開數，不可合併）────────────────
        "void_chains_n": len(void),
        "mediated_chains_n": sum(1 for r in rows if r.get("mediated") is True),
        "unmediated_chains_n": sum(1 for r in rows if r.get("mediated") is False),
        "chains_without_requests_seen_n": sum(
            1 for r in rows if r.get("mediated") is None),
        "unmediated_task_ids": sorted(
            {t for r in rows for t in r.get("unmediated_task_ids", [])}),
        # ── 認證維度的總帳（三種結論分開數，不可合併）────────────────
        "require_tier": require_tier,
        "attested_chains_n": sum(1 for r in rows if r.get("attested") is True),
        "unattested_chains_n": sum(1 for r in rows
                                   if r.get("attested") is False),
        "chains_without_tier_n": sum(1 for r in rows
                                     if r.get("attested") is None),
        "tier_histogram": {
            t: sum(1 for r in rows if r.get("tier") == t)
            for t in sorted(str(x) for x in {r.get("tier") for r in rows}
                            if x is not None)},
        # 一批裡只要有一條零請求的鏈，**總判就不准是乾淨的 OK**。
        "verdict": ("UNVERIFIABLE" if not rows else
                    "BROKEN" if broken else
                    "VOID" if void else "OK"),
        "note": ("每一列＝一個 run 的一條臂鏈。`verified_n` 數的是**逐筆都過**的 "
                 "entry；`failures` 是原文（seq／type／原因），不是摘要。"
                 "`chain_ok` 是本檔逐筆重跑的結論、`logbook_verify_chain` 是 "
                 "`vacant_network/logbook.py` 那支的 bool——兩者必須一致，不一致算 BROKEN。"
                 "`mediated` 是**另一個維度**：鏈完整不代表中介發生過。"
                 "VOID＝鏈是好的、但那一格 `requests_seen == 0`，"
                 "所以它不是「模型通道被中介了」的證據。"
                 "`mediated=null`＝這條鏈沒記這件事（舊鏈），"
                 "**沒量到 ≠ 量到 0**。"
                 "⚠ 這個維度擋得住「完全沒打」，擋不住「打了但打到別的地方」"
                 "——那要看 run_<ARM>.json 的 wire_by_protocol 與 upstreams，"
                 "而那兩個欄位不在簽章鏈上。"
                 "`tier`／`attested` 是**第三個維度**：這一跑有沒有在圍牆裡跑過、"
                 "每一通有沒有對得上一個工具事件（A／B／B'／C，"
                 "`DECISION_20260920_COMPLETE_MEDIATION` §三）。"
                 "`tier=null`＝這條鏈沒記（舊鏈或 VACANT_ATTEST=off）＝**沒量到**。"
                 "⚠ 級別**不影響** verdict，除非明講 --require-tier。"),
        "chains": rows,
    }


def selftest() -> int:
    """乾淨路徑通過不算數：三種竄改都必須被指名抓到。

    ⚠ 2026-09-19 加上**中介維度的負控制**（H／I／J／K）。理由是舊的這一批
      只證明「抓得到壞鏈」，而那一天量到的那件事**鏈根本沒壞**：
      `/bin/true` 放在 agent 的位置，一通模型都不打，退出碼／`accepted`／
      `stop_reason`／`agent_rc`／`chain_ok` 五個欄位全部成立。
      抓不到那一格的驗章器，說的是「沒人改過這張收據」，
      不是「這張收據底下發生過什麼」。
    """
    import tempfile
    fails: list[str] = []

    def ck(label, cond, extra=""):
        if not cond:
            fails.append(f"{label}{(' — ' + extra) if extra else ''}")

    ident = Identity.generate()
    book = Logbook()
    for i in range(3):
        book.append("harness_attempt", {"task_id": f"t{i}", "turn": 1}, ident,
                    ts_ms=1_700_000_000_000 + i)
    for i in range(3):
        book.append("harness_verdict", {"task_id": f"t{i}", "accepted": True}, ident,
                    ts_ms=1_700_000_000_100 + i)
    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(td)
        book.save(d / "receipts_HMIX.ndjson")
        (d / "receipts_HMIX.pub.json").write_text(json.dumps(
            {"vacant_id": ident.vacant_id, "pub_hex": pub_to_hex(ident.pub)}),
            encoding="utf-8")
        rows = [{"arm": "HMIX", "task_id": f"t{i}"} for i in range(3)]
        rec = verify_arm(d, "HMIX", rows)
        ck("A_clean_chain_is_OK", rec["verdict"] == "OK" and rec["failures"] == []
           and rec["entries_n"] == 6 and rec["verified_n"] == 6
           and rec["verdict_n"] == 3 and rec["rows_n"] == 3,
           json.dumps(rec, ensure_ascii=False)[:400])
        ck("A2_stream_id_is_genesis_hash", rec["genesis_hash_is_stream_id"] is True)

        # 竄改 1：改 payload ⇒ 那一筆簽章必須紅（而且指得出 seq）
        lines = (d / "receipts_HMIX.ndjson").read_text(encoding="utf-8").splitlines()
        e = json.loads(lines[1])
        e["payload"]["task_id"] = "tX"
        bad = list(lines)
        bad[1] = json.dumps(e, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        (d / "receipts_HMIX.ndjson").write_text("\n".join(bad) + "\n", encoding="utf-8")
        r2 = verify_arm(d, "HMIX", rows)
        ck("B_tampered_payload_is_caught",
           r2["verdict"] == "BROKEN"
           and any(f["reason"] == "bad_signature" and f["seq"] == 2
                   for f in r2["failures"]),
           json.dumps(r2["failures"], ensure_ascii=False)[:300])

        # 竄改 2：整條鏈重存、但換一把公鑰 ⇒ 每一筆都要紅
        book.save(d / "receipts_HMIX.ndjson")
        other = Identity.generate()
        (d / "receipts_HMIX.pub.json").write_text(json.dumps(
            {"vacant_id": other.vacant_id, "pub_hex": pub_to_hex(other.pub)}),
            encoding="utf-8")
        r3 = verify_arm(d, "HMIX", rows)
        ck("C_wrong_pubkey_fails_every_entry",
           r3["verdict"] == "BROKEN" and r3["failed_n"] == 6
           and r3["verified_n"] == 0,
           str(r3["failed_n"]))

        # 竄改 3：刪掉中間一筆 ⇒ seq／prev_hash 都要紅（不是只有一個）
        (d / "receipts_HMIX.pub.json").write_text(json.dumps(
            {"vacant_id": ident.vacant_id, "pub_hex": pub_to_hex(ident.pub)}),
            encoding="utf-8")
        lines = (d / "receipts_HMIX.ndjson").read_text(encoding="utf-8").splitlines()
        (d / "receipts_HMIX.ndjson").write_text(
            "\n".join(lines[:2] + lines[3:]) + "\n", encoding="utf-8")
        r4 = verify_arm(d, "HMIX", rows)
        ck("D_deleted_entry_is_caught",
           r4["verdict"] == "BROKEN"
           and any(f["reason"] == "seq_not_contiguous" for f in r4["failures"])
           and any(f["reason"] == "prev_hash_broken" for f in r4["failures"]),
           json.dumps([f["reason"] for f in r4["failures"]], ensure_ascii=False))

        # 對帳牙齒：rows 多一題但收據沒有 ⇒ 條數與 task_id 兩條都要紅
        book.save(d / "receipts_HMIX.ndjson")
        r5 = verify_arm(d, "HMIX", rows + [{"arm": "HMIX", "task_id": "t9"}])
        ck("E_missing_verdict_for_a_row_is_caught",
           r5["verdict"] == "BROKEN"
           and any(f["reason"] == "verdict_count_ne_rows" for f in r5["failures"])
           and any(f["reason"] == "verdict_task_ids_ne_rows" for f in r5["failures"]),
           json.dumps([f["reason"] for f in r5["failures"]], ensure_ascii=False))

        # ── round530：R530 的兩個新型別（`ws_attempt`／`ws_verdict`）─────
        # 乾淨路徑要 OK，而且**竄改工作區樹雜湊必須被抓到**——樹雜湊是 R530
        # 唯一佐證「當時的目錄長這樣」的欄位，它被改掉而鏈還說 OK 的話，
        # 收據對 R530 就沒有意義。
        r530_ident = Identity.generate()
        r530 = Logbook()
        for i in range(2):
            r530.append("ws_attempt",
                        {"task_id": f"ow_0{i + 1}", "arm": "A-GATE", "attempt": 1,
                         "gate_round": 1, "ws_sha256": "a" * 64,
                         "verdict_sha256": "b" * 64,
                         "conversation_sha256": "c" * 64},
                        r530_ident, ts_ms=1_700_000_001_000 + i)
        for i in range(2):
            r530.append("ws_verdict",
                        {"task_id": f"ow_0{i + 1}", "arm": "A-GATE",
                         "accepted": True, "ws_start_sha256": "d" * 64,
                         "ws_end_sha256": "e" * 64, "verdict_sha256": "b" * 64,
                         "conversation_sha256": "c" * 64,
                         "stop_reason": "visible_pass"},
                        r530_ident, ts_ms=1_700_000_002_000 + i)
        r530_rows = [{"arm": "A-GATE", "task_id": f"ow_0{i + 1}"} for i in range(2)]
        r530.save(d / "receipts_A-GATE.ndjson")
        (d / "receipts_A-GATE.pub.json").write_text(json.dumps(
            {"vacant_id": r530_ident.vacant_id, "pub_hex": pub_to_hex(r530_ident.pub)}),
            encoding="utf-8")
        r6 = verify_arm(d, "A-GATE", r530_rows)
        ck("F_r530_types_are_recognised",
           r6["verdict"] == "OK" and r6["verdict_n"] == 2 and r6["attempt_n"] == 2
           and r6["type_counts"].get("ws_verdict") == 2
           and r6["type_counts"].get("ws_attempt") == 2,
           json.dumps(r6, ensure_ascii=False)[:400])

        lines = (d / "receipts_A-GATE.ndjson").read_text(encoding="utf-8").splitlines()
        e = json.loads(lines[0])
        e["payload"]["ws_sha256"] = "f" * 64
        bad = list(lines)
        bad[0] = json.dumps(e, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        (d / "receipts_A-GATE.ndjson").write_text("\n".join(bad) + "\n", encoding="utf-8")
        r7 = verify_arm(d, "A-GATE", r530_rows)
        ck("G_tampered_workspace_hash_is_caught",
           r7["verdict"] == "BROKEN"
           and any(f["reason"] == "bad_signature" and f["seq"] == 1
                   for f in r7["failures"]),
           json.dumps([f["reason"] for f in r7["failures"]], ensure_ascii=False))

        # ── 中介維度的負控制（2026-09-19）────────────────────────────
        #  舊 selftest 只證明「抓得到壞鏈」。而 2026-09-19 的隨傳隨到負控制
        #  （`/bin/true` 放在 agent 的位置）證明了一件更難看的事：**一通模型
        #  都不打的假拒交格，鏈是完整的、五個欄位全部成立**。所以這裡多造一個
        #  零請求的跑，證明驗章器**抓得到**——抓不到的話上面那些 PASS
        #  都只是在說「沒人改過這張收據」，不是「這張收據底下發生過什麼」。
        def _mk(sub: str, rows_: list[dict], verdict_payload: dict,
                attempt_payload: dict | None = None) -> pathlib.Path:
            """造一個最小的 run 目錄（rows.jsonl ＋ 一條臂鏈）。"""
            dd = d / sub
            dd.mkdir(parents=True, exist_ok=True)
            idt = Identity.generate()
            bk = Logbook()
            bk.append("ws_attempt", attempt_payload or {
                "task_id": verdict_payload["task_id"], "arm": "RUN-ON",
                "attempt": 1, "gate_round": 1, "ws_sha256": "a" * 64,
                "verdict_sha256": "b" * 64, "conversation_sha256": "c" * 64,
                "requests_seen": verdict_payload.get("requests_seen"),
            }, idt, ts_ms=1_700_000_003_000)
            bk.append("ws_verdict", verdict_payload, idt,
                      ts_ms=1_700_000_004_000)
            bk.save(dd / "receipts_RUN-ON.ndjson")
            (dd / "receipts_RUN-ON.pub.json").write_text(json.dumps(
                {"vacant_id": idt.vacant_id, "pub_hex": pub_to_hex(idt.pub)}),
                encoding="utf-8")
            (dd / "rows.jsonl").write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n"
                        for r in rows_), encoding="utf-8")
            return dd

        #: `ctl_norequest_refuse` 的逐欄複製：exit 20／accepted=false／
        #: visible_fail／agent_rc=0／鏈完整——**唯一的破綻是 requests_seen**。
        void_p = {"task_id": "ctl_norequest_refuse", "arm": "RUN-ON",
                  "accepted": False, "accepted_is_null": False,
                  "ws_start_sha256": "d" * 64, "ws_end_sha256": "e" * 64,
                  "verdict_sha256": "b" * 64, "conversation_sha256": "c" * 64,
                  "stop_reason": "visible_fail", "agent_rc": 0,
                  "requests_seen": 0}
        dv = _mk("void_run", [{"arm": "RUN-ON",
                               "task_id": "ctl_norequest_refuse"}], void_p)
        r8 = verify_run(dv)[0]
        ck("H_zero_request_cell_is_VOID_not_OK",
           r8["verdict"] == "VOID" and r8["mediated"] is False
           and r8["void_reason"] == "no_requests_seen"
           and r8["unmediated_task_ids"] == ["ctl_norequest_refuse"],
           json.dumps({k: r8.get(k) for k in
                       ("verdict", "mediated", "void_reason")},
                      ensure_ascii=False))
        ck("H2_VOID_does_not_lie_about_the_chain",
           r8["chain_ok"] is True and r8["logbook_verify_chain"] is True
           and r8["failures"] == [] and r8["failed_n"] == 0,
           "鏈是完整的，說它壞掉是另一種說謊")
        g1 = run_glob(str(dv))
        ck("H3_batch_verdict_reflects_it",
           g1["verdict"] == "VOID" and g1["broken_chains_n"] == 0
           and g1["void_chains_n"] == 1 and g1["unmediated_chains_n"] == 1
           and exit_code(g1) == EXIT_VOID,
           json.dumps({k: g1[k] for k in ("verdict", "void_chains_n")}))

        #: `--allow-no-suite`：**刻意沒有驗收**，但模型通道有流量。
        #: 那不是假拒交格，誤殺它等於把「沒量驗收」與「沒中介」混成一件事。
        ung_p = {**void_p, "task_id": "ungated_but_mediated",
                 "accepted": False, "accepted_is_null": True,
                 "stop_reason": "ungated", "requests_seen": 3}
        du = _mk("ungated_run", [{"arm": "RUN-ON",
                                  "task_id": "ungated_but_mediated"}], ung_p)
        r9 = verify_run(du)[0]
        ck("I_allow_no_suite_with_traffic_is_not_VOID",
           r9["verdict"] == "OK" and r9["mediated"] is True
           and r9["ungated_task_ids"] == ["ungated_but_mediated"]
           and run_glob(str(du))["verdict"] == "OK",
           json.dumps({k: r9.get(k) for k in
                       ("verdict", "mediated", "ungated_task_ids")},
                      ensure_ascii=False))

        #: 舊鏈（R460R／R529／R530）**沒有** `requests_seen` 這個欄位。
        #: 那是「沒量到」不是「量到 0」⇒ 判 OK、`mediated=None`。
        #: 這一條是已歸檔 6,468 筆 verdict 的可比性保險絲。
        leg_p = {k: v for k, v in void_p.items()
                 if k not in ("requests_seen", "agent_rc", "accepted_is_null")}
        leg_p["task_id"] = "legacy_no_field"
        dl = _mk("legacy_run", [{"arm": "RUN-ON", "task_id": "legacy_no_field"}],
                 leg_p, attempt_payload={
                     "task_id": "legacy_no_field", "arm": "RUN-ON",
                     "attempt": 1, "gate_round": 1, "ws_sha256": "a" * 64,
                     "verdict_sha256": "b" * 64,
                     "conversation_sha256": "c" * 64})
        r10 = verify_run(dl)[0]
        gl = run_glob(str(dl))
        ck("J_legacy_chain_without_the_field_is_not_VOID",
           r10["verdict"] == "OK" and r10["mediated"] is None
           and r10["void_reason"] is None
           and r10["requests_seen_total"] is None
           and r10["verdicts_without_requests_seen"] == 1
           and gl["verdict"] == "OK"
           and gl["chains_without_requests_seen_n"] == 1
           and exit_code(gl) == EXIT_OK,
           "沒量到 ≠ 量到 0——舊鏈不准被判 VOID")

        #: 壞鏈 ＋ 零請求同時成立時，**BROKEN 優先**（鏈壞了比較嚴重），
        #: 但 `mediated` 照樣講得出來——兩個維度不准互相吃掉。
        lines = (dv / "receipts_RUN-ON.ndjson").read_text(
            encoding="utf-8").splitlines()
        (dv / "receipts_RUN-ON.ndjson").write_text(
            lines[0] + "\n", encoding="utf-8")   # 刪掉 verdict 那一筆
        r11 = verify_run(dv)[0]
        ck("K_broken_wins_but_mediation_still_reported",
           r11["verdict"] == "BROKEN"
           and any(f["reason"] == "verdict_count_ne_rows"
                   for f in r11["failures"])
           and r11["mediated"] is None,   # verdict 沒了 ⇒ 這條鏈沒得問
           json.dumps([f["reason"] for f in r11["failures"]],
                      ensure_ascii=False))
    for f in fails:
        print(f"  FAIL {f}")
    print("selftest: " + ("PASS" if not fails else f"{len(fails)} FAILED"))
    return 1 if fails else 0


def render(out: dict) -> str:
    L = [f"═══ 收據鏈驗證 {out['glob']} ═══",
         f"run {out['runs_n']}　鏈 {out['chains_n']}　"
         f"entries {out['entries_total']}　驗過 {out['verified_total']}　"
         f"失敗 {out['failed_total']}　壞鏈 {out['broken_chains_n']}",
         f"中介：有 {out['mediated_chains_n']}　"
         f"**零請求 {out['unmediated_chains_n']}**　"
         f"沒記這件事 {out['chains_without_requests_seen_n']}（舊鏈；沒量到≠量到 0）",
         "",
         f"{'run':30}{'arm':9}{'條數':>6}{'驗過':>6}{'失敗':>6}"
         f"{'verdict':>8}{'rows':>6}  chain_head"]
    for r in out["chains"]:
        L.append(f"{r['run']:30}{r['arm']:9}{r['entries_n']:>6}{r['verified_n']:>6}"
                 f"{r['failed_n']:>6}{r.get('verdict_n', 0):>8}"
                 f"{r.get('rows_n', 0):>6}  {(r['head'] or '')[:16]}…  {r['verdict']}")
        for f in r["failures"]:
            L.append(f"    ! {json.dumps(f, ensure_ascii=False)}")
        if r.get("attested") is False:
            L.append(f"    ! 未認證 tier={r.get('tier')}：這條鏈的 "
                     f"{len(r['unattested_task_ids'])} 格不是 A 級"
                     f"（{', '.join(r['unattested_task_ids'][:6]) or '—'}）"
                     "——鏈可以是完整的，但那幾格的紀錄不足以究責")
        if r.get("mediated") is False:
            L.append(f"    ! VOID {r['void_reason']}：這條鏈的 "
                     f"{len(r['unmediated_task_ids'])} 格 requests_seen == 0"
                     f"（{', '.join(r['unmediated_task_ids'][:6]) or '—'}）"
                     "——鏈是完整的，但那幾格沒有中介發生過，"
                     "不可以拿來當「agent 被 Vacant 接住了」的證據")
    L += ["", f"總判：{out['verdict']}", out["note"]]
    return "\n".join(L)


def exit_code(out: dict) -> int:
    """總判 → 退出碼。**VOID 有自己的碼**，不與 BROKEN 同形。

    `0`＝乾淨；`3`＝鏈好但有零請求的格子；`1`＝鏈壞了／驗不動。
    合成一個「非 0」會讓「鏈壞了」與「這一跑沒有中介」在 CI 上同形，
    而那正是本檔這一輪要拆開的那件事。
    """
    return {"OK": EXIT_OK, "VOID": EXIT_VOID}.get(out["verdict"], EXIT_BROKEN)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", help="run 目錄的 glob（相對 repo 根），例如 'runs/g_r529_*'")
    ap.add_argument("--json", help="把報表寫成 JSON")
    ap.add_argument("--require-tier", choices=("A", "B", "B'"), default=None,
                    help="要求每一條鏈都到這一級（展場用 A）。"
                         "**預設不要求**——既有歸檔 run 的判決逐字不變。")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.glob:
        ap.error("要給 --glob 或 --selftest")
    out = run_glob(args.glob, require_tier=args.require_tier)
    print(render(out))
    if args.json:
        p = pathlib.Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON → {args.json}")
    return exit_code(out)


if __name__ == "__main__":
    raise SystemExit(main())
