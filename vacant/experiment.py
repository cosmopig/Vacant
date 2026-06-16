"""G7 驗證實驗 — C0/C1/C2/C3 等算力對照 + 信任性質演示。架構總規格 §11 / §10。

頭條指標：隨輪數的學習曲線 + 路由收斂。C3 − C2 = 信任層淨貢獻
（把 AutoHarness 引擎的功勞與信任層的功勞分開）。

對照（等算力＝同呼叫次數、同一顆 substrate、可檢查任務、固定種子可重現）：
  C0 裸 substrate 單次          —— 無閘道、無持久、無路由
  C1 naive orchestration        —— 隨機路由、無信譽、無累積（每輪換新身體）
  C2 +自合成/累積               —— 持久累積開（skill 越學越多），但路由隨機
  C3 +Vacant 信任組合           —— 持久累積 + UCB 信譽路由 + 互查 + 究責

本機（Intel Mac 無 GPU）跑 EchoSubstrate（A 層機制模擬）；換 HermesACPSubstrate
即為 3090 上的 B 層系統消融。全程零 API、零 GPU、完全確定性。
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .body import now_ms
from .envelope import Envelope, ReplayError
from .gateway import BadSignature, Gateway
from .host import Host
from .identity import Identity
from .substrate import EchoSubstrate
from .tasks import NICHES as _ALL_NICHES
from .tasks import make_task, task_stream

P_BASE = 0.34   # 裸 base model 偶爾解對可檢查任務的機率（demo 用，待 M2 實測校準）
N_TASKS = 120
N_EXPERTS = 4


# === 各對照條件：回傳每輪是否正確（0/1）====================================
def run_c0(root: Path) -> list[int]:
    """C0：每題在一個全新的、無累積的身體上單次推論。"""
    sub = EchoSubstrate(p_base=P_BASE)
    out = []
    for i, task in enumerate(task_stream(N_TASKS)):
        home = root / f"round_{i}" / "home"  # 每輪換新身體 → 零累積
        home.mkdir(parents=True, exist_ok=True)
        res = sub.run(home, task["prompt"], task)
        out.append(int(task["check"](res.output)))
    return out


def run_c1(root: Path) -> list[int]:
    """C1：隨機路由到多個 expert，但每輪換新身體（無累積、無信譽）。"""
    sub = EchoSubstrate(p_base=P_BASE)
    experts = [f"e{j}" for j in range(N_EXPERTS)]
    out = []
    for i, task in enumerate(task_stream(N_TASKS)):
        # 確定性「隨機」路由（可重現）
        j = int(task["task_id"], 16) % N_EXPERTS
        home = root / experts[j] / f"round_{i}" / "home"
        home.mkdir(parents=True, exist_ok=True)
        res = sub.run(home, task["prompt"], task)
        out.append(int(task["check"](res.output)))
    return out


def _run_hosted(root: Path, mode: str) -> tuple[list[int], list[str]]:
    """C2/C3 共用：真正的 Host + gateway 迴圈（持久累積開）。mode 決定路由方式。"""
    h = Host(root, substrate=EchoSubstrate(p_base=P_BASE))
    req = h.mint("requester", niches=[])
    for j in range(N_EXPERTS):
        h.mint(f"e{j}", niches=list(_ALL_NICHES))
    out, picks = [], []
    for i, task in enumerate(task_stream(N_TASKS)):
        oc = req.call(task["niche"], task, mode=mode)
        out.append(int(oc.correct))
        picks.append(oc.callee_id)
    return out, picks


def run_c2(root: Path) -> list[int]:
    """C2：持久累積開，但路由隨機（無信任層）。"""
    return _run_hosted(root, "random")[0]


def run_c3(root: Path) -> tuple[list[int], list[str]]:
    """C3：持久累積 + UCB 信譽路由（全開）。"""
    return _run_hosted(root, "reputation")


# === 信任性質演示（§10：prevents / detects）================================
@dataclass
class TrustChecks:
    impersonation_rejected: bool
    replay_rejected: bool
    tamper_detected: bool
    attributable: bool


def demo_trust_properties(root: Path) -> TrustChecks:
    h = Host(root, substrate=EchoSubstrate(p_base=1.0))
    req = h.mint("requester", niches=[])
    expert = h.mint("expert", niches=list(_ALL_NICHES))
    task = make_task(0, "reverse")

    # 正常一次 → 取得歸屬證據（logbook 有簽章紀錄）
    req.call("reverse", task)
    expert_body = h.body("expert")
    attributable = (
        any(e.type == "A2A_IN" for e in expert_body.logbook.entries)
        and expert_body.logbook.verify_chain(expert_body.public_identity())
    )

    # 冒名：mallory 簽，宣稱來自 requester
    mallory = Identity.generate()
    forged = Envelope.create(
        mallory, to=expert.vacant_id, seq=99, prev_hash="0" * 64, ts_ms=now_ms(),
        kind="call", body={"prompt": "x", "task_id": "t", "niche": "reverse", "input": "ab"},
    )
    forged.frm = h.vacant_id("requester")
    try:
        expert.ingress(forged)
        impersonation_rejected = False
    except BadSignature:
        impersonation_rejected = True

    # replay：重送 seq=1 的舊信封
    replay = Envelope.create(
        h.body("requester").identity, to=expert.vacant_id, seq=1, prev_hash="0" * 64,
        ts_ms=now_ms(), kind="call",
        body={"prompt": task["prompt"], "task_id": task["task_id"], "niche": "reverse", "input": task["input"]},
    )
    try:
        expert.ingress(replay)
        replay_rejected = False
    except ReplayError:
        replay_rejected = True

    # tamper：竄改 logbook 任一筆 → 驗鏈被抓
    lb = h.body("expert").logbook
    if lb.entries:
        lb.entries[0].payload = {"tampered": True}
    tamper_detected = not lb.verify_chain(h.body("expert").public_identity())

    return TrustChecks(impersonation_rejected, replay_rejected, tamper_detected, attributable)


# === 報表 ===================================================================
def _window_acc(seq: list[int], lo: float, hi: float) -> float:
    a, b = int(len(seq) * lo), int(len(seq) * hi)
    chunk = seq[a:b]
    return sum(chunk) / len(chunk) if chunk else 0.0


def run(root: Path) -> str:
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    checks = demo_trust_properties(root / "trust")
    c0 = run_c0(root / "c0")
    c1 = run_c1(root / "c1")
    c2 = run_c2(root / "c2")
    c3, picks = run_c3(root / "c3")

    lines: list[str] = []
    P = lines.append
    P("=" * 64)
    P("Vacant Phase 1 — 驗證實驗（A 層機制模擬，CPU、零 GPU、零 API）")
    P("=" * 64)
    P("")
    P("【信任性質】§10 prevents / detects（key custody 假設下）")
    P(f"  冒名被拒（簽章）         : {'✓' if checks.impersonation_rejected else '✗'}")
    P(f"  replay 被拒（seq 單調）  : {'✓' if checks.replay_rejected else '✗'}")
    P(f"  竄改被抓（hash chain）   : {'✓' if checks.tamper_detected else '✗'}")
    P(f"  動作可歸屬（簽章 logbook）: {'✓' if checks.attributable else '✗'}")
    P("")
    P(f"【學習曲線】等算力對照，每條 {N_TASKS} 題、{N_EXPERTS} 個 expert、p_base={P_BASE}")
    P(f"  {'條件':<26}{'前 1/3':>8}{'後 1/3':>8}{'整體':>8}")
    for name, seq in [
        ("C0 裸 substrate 單次", c0),
        ("C1 naive（隨機+無累積）", c1),
        ("C2 +累積（隨機路由）", c2),
        ("C3 +Vacant 信任組合", c3),
    ]:
        early = _window_acc(seq, 0.0, 1 / 3)
        late = _window_acc(seq, 2 / 3, 1.0)
        overall = sum(seq) / len(seq)
        P(f"  {name:<24}{early:>8.0%}{late:>8.0%}{overall:>8.0%}")
    net = _window_acc(c3, 2 / 3, 1.0) - _window_acc(c2, 2 / 3, 1.0)
    P("")
    P(f"  C3 − C2（後 1/3）= 信任層淨貢獻 ≈ {net:+.0%}")
    P("")
    P("【路由收斂】C3 後 20 題各 expert 被選次數")
    tail = picks[-20:]
    from collections import Counter

    counts = Counter(tail)
    for vid, n in counts.most_common():
        P(f"  …{vid[-8:]} : {'█' * n} {n}")
    P("")
    P("註：數字為設計級 A 層模擬，非模型實測；上機（3090+vLLM+Hermes）跑 B 層")
    P("    系統消融以校準（§11、§12 M2）。實驗完全確定性、可重現。")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    import tempfile

    print(run(Path(tempfile.mkdtemp(prefix="vacant-exp-")) / "exp"))
