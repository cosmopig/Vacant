"""release — **PASS 才鑄得出來的放行憑證**（2026-09-20 裁決 §四 P0 第一塊）。

這支在架構裡承重什麼：把「拒交」從**一個需要呼叫者合作的協定**，變成
**一個呼叫者拿不到的能力**。

🔴 為什麼非做不可（abpi 那批自己就是反例）：
`launcher.py:676` 判 `refused` 只是寫一個欄位、`:789` 回退出碼 20，
**沒有任何一行動工作區**；而那一批的 harness `abpi_cell.sh:112`
`[ -f "$ws/solution.py" ] && cp …` **不看 rc** ⇒ 59 個拒交格裡有檔案的那 7 格，
檔案照樣被複製出去計分。Fable 稽核的原話：

    D(artifact) = REJECT   ≠   publish(artifact) = IMPOSSIBLE

⇒ 出口不應該是一行 `exit 20`，而應該是一個**沒有憑證就叫不動的東西**。

## 語意從哪來（不是自創）

2026-09-20 直驗過 SLSA（落盤在 `參考文獻/_引用備份/2026-09-20_附身先行研究`）：

- **VSA（Verification Summary Attestation, SLSA v1.2）** 的欄位骨架——把
  artifact digest、verifier identity、policy digest、`PASSED|FAILED`、
  verification time 綁在同一張簽章裡。
  ⚠ **不是照抄**：VSA 的 `resourceUri`／`verifiedLevels` 是必填而我們沒有對應物，
  `timeVerified` 在 v1.0 必填、v1.1 起改選填。**照著那份 deep research 報告去對齊
  會做出「以為必填的可省、真正必填的沒做」的東西**——所以這裡是**取其結構、
  自訂欄位**，並在 `coverage` 沿用它的三態。
- **coverage 的三態**沿用 VSA `dependencyLevels`（MUST 級，v1.0 起未變）：
  `None` ＝ *the verifier makes no claims*、有值才是宣稱。
  ＋ SLSA Provenance **v0.2** `metadata.completeness.*` 的 **fail-closed**：
  **沒有旗標就視為不完整**。

## ⚠ 誠實邊界（改碼請保留）

1. **這一層只綁「願意用 publisher 的呼叫者」。** 拿得到檔案的人照樣 `cp`。
   真正的強制要靠**呼叫者對目的地沒有寫入能力**（OS 權限／另一個行程／
   另一組憑證），那不是本檔做得到的。本檔做的是：**讓「照規矩來」這條路
   在沒有 PASS 的時候不存在**，而不是讓別的路消失。
2. **簽章證明的是「這張憑證是那個 verifier 簽的」**，不是「那個 verifier 判得對」。
   判得對不對由 `verdict_sha256` 指向的驗收結果負責。
3. **`coverage` 是宣稱不是保證。** `model_wire="lower_bound"` 的意思是
   「我們知道自己可能少算」——它**不會**因為寫進簽章就變成完整。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import time

from .. import __version__
from ..identity import Identity, PublicIdentity

#: 逐字凍結——驗證端引用這個常數，不是字面字串。
RELEASE_SCHEMA = "vacant-release/1"

#: 預設有效期。放行憑證**會過期**，理由是 §誠實邊界 1 的必然結果：
#: 一張永久有效的憑證等於把「那一刻通過了」讀成「永遠可以發」。
DEFAULT_TTL_S = 3600.0


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def _canon(payload: dict) -> bytes:
    """簽章對象的正規化位元組。排序 key ⇒ 欄位順序不影響簽章。"""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def coverage_of(summary: dict) -> dict:
    """從 `run_<ARM>.json` 抽出 coverage。**三態：`None` ＝沒宣稱。**

    ⚠ 每一欄的 `None` 都要能講出「為什麼沒宣稱」，否則它會被讀成 0／False。
    """
    mw = summary.get("model_wire") or {}
    att = summary.get("attestation") or {}
    enc = att.get("enclosure") or {}
    rec = att.get("reconciled") or {}
    hook = att.get("framework_hook") or {}

    # 出網有沒有被強制：只有**圍牆真的套上**才算 enforced。
    # `applied is False` ⇒ 明確沒有（不是沒量到）；`None` ⇒ 沒量到。
    if enc.get("applied") is True:
        egress = "enforced"
    elif enc.get("applied") is False:
        egress = "unenforced"
    else:
        egress = None

    # 工具對帳：掛鉤沒裝 ⇒ `canary_fired` 是 None ⇒ **沒量到**，不是 0。
    if rec.get("unexplained") is None:
        tool = None if hook.get("canary_fired") is None else "incomplete"
    elif rec.get("unexplained") == 0:
        tool = "complete"
    else:
        tool = "incomplete"

    return {
        # `exact` / `lower_bound` / None（沒有 model_wire 區塊的舊跑）
        "model_wire": mw.get("count_semantics") or None,
        "network_egress": egress,
        "tool_correlation": tool,
        # 🔴 本檔**不宣稱**交付物被扣住——那要靠 publisher 端與 OS 權限，
        #    而這張憑證管不到別人的 `cp`。恆為 None，並附理由。
        "artifact_externalization": None,
        "note": ("三態：None ＝ 沒有宣稱（VSA dependencyLevels 語意）。"
                 "artifact_externalization 恆為 None——這一層擋不住呼叫者自己複製檔案。"),
    }


def mint(summary: dict, *, ident: Identity, artifact_path: pathlib.Path | None = None,
         artifact_sha256: str | None = None, ttl_s: float = DEFAULT_TTL_S,
         now: float | None = None) -> dict:
    """PASS 才鑄得出放行憑證。**FAIL 回一張「鑄不出來」的紀錄，不是丟例外。**

    回 `{"minted": bool, "reason": str, "token": dict|None}`。

    ⚠ **`accepted` 必須嚴格是 `True`。** `None`（`--allow-no-suite`：明講這次不量）
      與 `False` 都鑄不出來——「沒量」不是「通過」，這是三態鐵律在出口的樣子。
    """
    now = time.time() if now is None else now
    accepted = summary.get("accepted")
    if accepted is not True:
        return {"minted": False, "token": None,
                "reason": ("accepted is None（沒有跑驗收 ⇒ 沒有通過）"
                           if accepted is None else
                           f"accepted={accepted!r}（沒通過）"),
                "verdict": "FAILED" if accepted is False else "UNVERIFIED"}

    if artifact_sha256 is None:
        if artifact_path is None:
            raise ValueError("要嘛給 artifact_path 要嘛給 artifact_sha256")
        artifact_sha256 = sha256_file(pathlib.Path(artifact_path))

    payload = {
        "schema": RELEASE_SCHEMA,
        "run_id": summary.get("task_id"),
        "arm": summary.get("arm"),
        "verdict": "PASSED",
        "artifact": {"sha256": artifact_sha256},
        # 工作區整體的收尾雜湊——用來抓「憑證對的是另一份交付」。
        "workspace": {"ws_end_sha256": summary.get("ws_end_sha256")},
        # policy ＝ 這一跑是拿什麼判的。
        "policy": {"verdict_sha256": summary.get("verdict_sha256"),
                   "visible_passed": summary.get("visible_passed"),
                   "visible_total": summary.get("visible_total")},
        "coverage": coverage_of(summary),
        "verifier": {"id": ident.vacant_id, "version": __version__,
                     "component": "vacant_network.vrun.release"},
        "verified_at": round(now, 3),
        "expires_at": round(now + ttl_s, 3),
    }
    sig = ident.sign(_canon(payload))
    return {"minted": True, "reason": "accepted is True", "verdict": "PASSED",
            "token": {"payload": payload, "sig_hex": sig.hex()}}


def verify(token: dict, *, pub_hex: str, vacant_id: str = "",
           artifact_path: pathlib.Path | None = None,
           artifact_sha256: str | None = None,
           now: float | None = None,
           require_coverage: dict | None = None) -> dict:
    """驗一張放行憑證。回 `{"ok": bool, "reasons": [...], "checked": {...}}`。

    ⚠ **`ok` 為 True 需要每一項都過。** 任何一項不確定 ⇒ False，
      fail-closed（SLSA v0.2 completeness 的措辭：沒有旗標即視為不完整）。

    `require_coverage` 例：`{"model_wire": "exact", "network_egress": "enforced"}`
    ——**要求哪些 coverage 由呼叫端決定**，因為「夠不夠」是政策不是事實。
    """
    now = time.time() if now is None else now
    reasons: list[str] = []
    checked: dict = {}

    payload = (token or {}).get("payload")
    sig_hex = (token or {}).get("sig_hex")
    if not isinstance(payload, dict) or not sig_hex:
        return {"ok": False, "reasons": ["憑證格式不對（缺 payload 或 sig_hex）"],
                "checked": {}}

    if payload.get("schema") != RELEASE_SCHEMA:
        reasons.append(f"schema 不是 {RELEASE_SCHEMA}：{payload.get('schema')!r}")

    # 1) 簽章
    try:
        pub = PublicIdentity.from_hex(vacant_id or payload.get("verifier", {})
                                      .get("id", ""), pub_hex)
        sig_ok = pub.verify(_canon(payload), bytes.fromhex(sig_hex))
    except Exception as exc:                                    # noqa: BLE001
        sig_ok = False
        reasons.append(f"簽章驗不動：{type(exc).__name__}")
    checked["signature"] = sig_ok
    if not sig_ok:
        reasons.append("簽章不符")

    # 2) 判決
    checked["verdict"] = payload.get("verdict")
    if payload.get("verdict") != "PASSED":
        reasons.append(f"verdict 不是 PASSED：{payload.get('verdict')!r}")

    # 3) 交付物雜湊——**這是擋「憑證對的是另一份東西」的那一關**
    if artifact_sha256 is None and artifact_path is not None:
        artifact_sha256 = sha256_file(pathlib.Path(artifact_path))
    want = (payload.get("artifact") or {}).get("sha256")
    checked["artifact_sha256_expected"] = want
    checked["artifact_sha256_actual"] = artifact_sha256
    if artifact_sha256 is None:
        reasons.append("沒有交付物可比對（沒量到 ⇒ 不放行，fail-closed）")
    elif artifact_sha256 != want:
        reasons.append("交付物雜湊對不上憑證")

    # 4) 過期
    exp = payload.get("expires_at")
    checked["expires_at"] = exp
    checked["now"] = round(now, 3)
    if not isinstance(exp, (int, float)):
        reasons.append("憑證沒有 expires_at（fail-closed）")
    elif now > exp:
        reasons.append(f"憑證已過期（{round(now - exp, 1)} 秒前）")

    # 5) coverage 要求
    cov = payload.get("coverage") or {}
    checked["coverage"] = cov
    for k, want_v in (require_coverage or {}).items():
        got = cov.get(k)
        if got != want_v:
            reasons.append(
                f"coverage.{k} ＝ {got!r}，要求 {want_v!r}"
                + ("（None ＝ 沒有宣稱，不是達成）" if got is None else ""))

    return {"ok": not reasons, "reasons": reasons, "checked": checked}
