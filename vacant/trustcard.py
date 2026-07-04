"""trustcard — 信任狀組裝＋簽章＋人可讀渲染（12 §2；11 §8 T1 的載體）。

信任狀＝delegate 回傳的責任附件：誰交付（credit/n_obs/flag）、誰審過（簽章
review）、稽核狀態、鏈頭、host 簽章。

⚠️ 風險欄位必有、不可省（12 §2 引 JCOM 2026）：「只有正面出處」的標籤會觸發
捷思式信任陷阱——人看到出處反而更不查核。渲染永遠顯示稽核狀態的真實面
（`本件未稽核`／`INSUFFICIENT_DATA`／`PROBATION`），不得只在正面時渲染。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .body import now_ms
from .canonical import canonical_bytes

if TYPE_CHECKING:
    from .ecosystem import Ecosystem, Resident


def build_trust_card(
    *,
    ecosystem: "Ecosystem",
    task_id: str,
    spec_digest: str,
    deliverer: "Resident",
    reviews: list[dict[str, Any]],
    audit: dict[str, Any] | None,
) -> dict[str, Any]:
    score, obs = ecosystem.standing(deliverer)
    flags = ecosystem.flags(deliverer)
    card: dict[str, Any] = {
        "task_id": task_id,
        "spec_digest": spec_digest,
        "trust_on": ecosystem.trust_on,
        "deliverer": {
            "name": deliverer.name,
            "stream_id": (deliverer.body.logbook.stream_id() or deliverer.vacant_id)[-16:],
            "vacant_id": deliverer.vacant_id[-16:],
            "credit": {"score": round(score, 3), "n_obs": round(obs, 1),
                       "flags": flags},   # 風險欄位必有（可為空 list，不可缺鍵）
        },
        "reviews": [
            # 簽章存全文（可驗）；顯示層才截斷。截斷過的簽章驗不了＝形同無簽。
            {"reviewer": r["reviewer"], "verdict": r["verdict"],
             "weight": r["weight"], "sig": r["sig"]}
            for r in reviews
        ],
        "audit": {"performed": bool(audit and audit.get("ran")),
                  "passed": (audit or {}).get("passed")},
        "chain_head": deliverer.body.logbook.head()[-16:],
        "ts_ms": now_ms(),
    }
    # host 簽章：由交付居民自己的 key 簽整張卡（demo 期閘道與居民同 host；
    # 分離的 gateway keypair 屬上機工項，誠實標注簽者身份）。簽章存全文——
    # 截斷過的簽章驗不了＝形同無簽（顯示層才截斷）。
    card["signed_by"] = "deliverer"
    card["signer_pub_hex"] = deliverer.body.card.pub_hex  # 驗卡所需（halo 亦可查）
    card["host_sig"] = deliverer.body.identity.sign(canonical_bytes(card)).hex()
    return card


def verify_trust_card(card: dict[str, Any], pub_hex: str | None = None) -> bool:
    """獨立驗卡：不必信任送方。用 signer 公鑰重驗 host_sig 覆蓋的 canonical 內容。

    pub_hex 未給 → 用卡上自帶的 signer_pub_hex（此時驗的是「卡內部自洽」；
    要驗「簽者真是該居民」請傳 halo/registry 查到的 pub_hex）。"""
    from . import crypto
    d = dict(card)
    sig_hex = d.pop("host_sig", "")
    pub = pub_hex or d.get("signer_pub_hex", "")
    if not sig_hex or not pub:
        return False
    try:
        return crypto.verify(crypto.pub_from_hex(pub),
                             canonical_bytes(d), bytes.fromhex(sig_hex))
    except Exception:
        return False


def render_trust_card(card: dict[str, Any]) -> str:
    """人可讀三行渲染（附在答案尾部）。**第三行恆為風險欄、且顯眼**。

    風險欄紀律（12 §2 引 JCOM 2026 捷思陷阱）：稽核狀態與信用旗標一律如實顯示，
    未稽核（UNAUDITED）／稽核未過（AUDIT_FAIL）／觀測不足（INSUFFICIENT_DATA）／
    觀察期（PROBATION）都當風險列出——不得只在正面時渲染。即使無任何旗標，也明白
    標「✅ 無旗標」，讓「沒有風險」是被斷言的、而非讀者從空白腦補的。"""
    d = card["deliverer"]
    audit = card["audit"]
    # 稽核狀態如實併入風險旗標（未稽核 / 稽核未過都是風險，顯式列出、不可省）。
    flags: list[str] = list(d["credit"]["flags"])
    if not audit["performed"]:
        flags.append("UNAUDITED")
        audit_txt = "本件未稽核"
    elif audit["passed"]:
        audit_txt = "本件已稽核 ✓"
    else:
        flags.append("AUDIT_FAIL")
        audit_txt = "本件稽核 ✗ 未過"
    # 風險欄恆存在、顯眼。有旗標→⚠ 列全；無旗標→✅ 明白斷言「無」。
    risk_line = (
        "⚠ 風險：" + "，".join(flags) if flags
        else "✅ 風險：無旗標（已稽核通過、n≥30、非觀察期）"
    )

    if not card.get("trust_on"):
        # trust off：無出處/互審/稽核——這本身就是最大風險，仍給三行、風險欄不缺。
        return (
            "⚠ trust off：隨機路由、無互審、無稽核（本件無出處保證）\n"
            f"｜交付 …{d['vacant_id'][-6:]}｜鏈頭 …{card['chain_head'][-8:]}\n"
            f"{risk_line}"
        )
    n_pass = sum(1 for r in card["reviews"] if r["verdict"] == "PASS")
    return (
        f"✓ 由 …{d['vacant_id'][-6:]}（信用 {d['credit']['score']}，"
        f"{d['credit']['n_obs']} 次觀測）交付｜{n_pass}/{len(card['reviews'])} peer 通過｜{audit_txt}\n"
        f"｜鏈頭 …{card['chain_head'][-8:]}｜sig …{card['host_sig'][-8:]}\n"
        f"{risk_line}"
    )


def card_json(card: dict[str, Any]) -> str:
    return json.dumps(card, ensure_ascii=False, indent=2)
