"""G3 發射管線（vq-1zf.6）：接線＋假通道驗證，全程 0 真模型呼叫。

紅線（本測試即驗收）：
- 無核准/不合格核准 → RC 2、0 模型呼叫（fail-closed）
- 有效核准＋假通道 → 12 格跑通、hidden_after 全 UNKNOWN
- 成本缺值 → UNKNOWN（None），絕不填 0
- 撞日額度 → 停、不得重試
- full_rloop 第 2 輪僅在必要答案項缺失時才花（無額外呼叫）
- prompt 無 /srv/eval/hidden/、無 scorer.py（leak_guard）
"""
from __future__ import annotations

import copy
import json
import pathlib
import re

import pytest

import vacant_network.reqloop.g3 as g3
import vacant_network.reqloop.g3gate as g3gate

REPO = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = REPO / "ops" / "reqloop" / "g3_gate" / "manifest.json"
BASE = REPO / "ops" / "reqloop" / "g3_gate"


def _approval() -> dict:
    return {
        "schema": g3gate.APPROVAL_SCHEMA,
        "approved": True,
        "epic": "vq-1zf",
        "by": "測試核准者（假通道；非真發射）",
    }


def _plan():
    assert MANIFEST.is_file(), "g3_gate manifest 未凍結"
    return g3gate.G3Plan.load(MANIFEST)


def _full_answer(task_id: str) -> str:
    """依各 task 的 contract 產生「必要答案項齊全」的假答案。"""
    names = g3.required_answer_names(
        (BASE / "tasks" / task_id / "workspace" / "contract.md").read_text(encoding="utf-8"))
    return "\n".join(f"@{n}[1.00]" for n in names) + "\n"


class FakeChannel(g3.Channel):
    """假通道：記錄每次呼叫；擷取回合法 RequirementSet JSON，作答回 @name[value] 答案。"""

    def __init__(self, *, tokens: int | None = 1000,
                 answer_for: dict[str, str] | None = None) -> None:
        self.calls: list[dict] = []
        self.tokens = tokens
        self.answer_for = answer_for or {}

    def call(self, *, prompt: str, model: str, purpose: str, timeout_s: float) -> tuple[str, g3.RoundUsage]:
        self.calls.append({"model": model, "purpose": purpose, "prompt": prompt,
                           "timeout_s": timeout_s})
        usage = g3.RoundUsage(calls=1, tokens=self.tokens, wall_ms=5)
        if "擷取需求" in purpose:
            tid = purpose.split()[1]
            goal = (BASE / "tasks" / tid / "workspace" / "goal.md").read_text(encoding="utf-8")
            quote = next((ln.strip() for ln in goal.splitlines() if len(ln.strip()) >= 12), goal[:40])
            items = [{"id": "r1", "quote": quote, "deliverable": "answer.txt",
                      "kind": "explicit", "unverified": True}]
            return json.dumps(items, ensure_ascii=False), usage
        m = re.match(r"G3 (\S+?)/(\S+) r(\d+)$", purpose)
        assert m, f"作答 purpose 格式未預期：{purpose!r}"
        tid, arm = m.group(1), m.group(2)
        answer = self.answer_for.get(f"{tid}/{arm}", _full_answer(tid))
        return answer, usage


# ── 通道契約：Channel 是已宣告的抽象契約，非未完成占位 ───────────


def test_channel_is_abstract_contract():
    """Channel＝ABC 抽象契約（同 substrate.Substrate 慣例）：
    裸 Channel 不可實例化（TypeError）；未實作 call 的子類不可實例化；
    實作 call 的子類（FakeChannel/GlmChannel）可實例化且 isinstance 成立。
    """
    with pytest.raises(TypeError):
        g3.Channel()

    class _NoCall(g3.Channel):
        pass

    with pytest.raises(TypeError):
        _NoCall()

    fake = FakeChannel()
    assert isinstance(fake, g3.Channel)
    assert isinstance(g3.GlmChannel(), g3.Channel)


# ── 三臂內容契約（對齊 manifest.arm_defs，2026-11-08 凍結）──────────


def test_arm_specs_match_preregistration():
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert set(g3.ARM_SPECS) == set(raw["arms"])
    assert g3.ARM_SPECS["native_pi"]["requirement_list"] is False
    assert g3.ARM_SPECS["native_pi"]["max_rounds"] == 1
    assert g3.ARM_SPECS["reqlist_only"]["requirement_list"] is True
    assert g3.ARM_SPECS["reqlist_only"]["max_rounds"] == 1
    assert g3.ARM_SPECS["reqlist_only"]["localized_repair"] is False
    assert g3.ARM_SPECS["full_rloop"]["requirement_list"] is True
    assert g3.ARM_SPECS["full_rloop"]["localized_repair"] is True
    assert g3.ARM_SPECS["full_rloop"]["reverify_all"] is True
    assert g3.ARM_SPECS["full_rloop"]["max_rounds"] >= 2


def test_arm_order_matches_gate():
    assert list(g3.ARM_SPECS) == list(g3gate.ARM_ORDER) if hasattr(g3gate, "ARM_ORDER") else True


# ── CLI：--dry-run（0 模型呼叫）─────────────────────────────────────


def test_dry_run_rc0_zero_calls(tmp_path):
    fake = FakeChannel()
    rc = g3.main(["--dry-run"], channel=fake)
    assert rc == 0
    assert fake.calls == [], "dry-run 不得有任何模型呼叫"


# ── CLI：--fire 核准門 fail-closed ──────────────────────────────────


def test_fire_no_approval_rc2_zero_calls(tmp_path):
    fake = FakeChannel()
    rc = g3.main(["--fire"], channel=fake)
    assert rc == g3gate.RC_NOT_APPROVED == 2
    assert fake.calls == []


def test_fire_invalid_approval_rc2_zero_calls(tmp_path):
    fake = FakeChannel()
    bad1 = tmp_path / "a1.json"
    bad1.write_text(json.dumps({"schema": g3gate.APPROVAL_SCHEMA, "approved": False,
                                "epic": "vq-1zf", "by": "x"}), encoding="utf-8")
    bad2 = tmp_path / "a2.json"
    bad2.write_text(json.dumps({"schema": g3gate.APPROVAL_SCHEMA, "approved": True,
                                "epic": "vq-el4", "by": "x"}), encoding="utf-8")
    assert g3.main(["--fire", "--approval", str(bad1)], channel=fake) == 2
    assert g3.main(["--fire", "--approval", str(bad2)], channel=fake) == 2
    assert fake.calls == [], "不合格核准不得有任何模型呼叫"


def test_fire_tampered_manifest_rc1_before_approval(tmp_path):
    """完整性先於核准判定：篡改 manifest 的 sha→RC 1（即使核准文件有效）。"""
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    raw = copy.deepcopy(raw)
    t = raw["tasks"][0]
    fname = next(iter(t["files"]))
    t["files"][fname] = "0" * 64
    m = tmp_path / "manifest_tampered.json"
    m.write_text(json.dumps(raw), encoding="utf-8")
    appr = tmp_path / "approval.json"
    appr.write_text(json.dumps(_approval()), encoding="utf-8")
    fake = FakeChannel()
    rc = g3.main(["--fire", "--approval", str(appr), "--manifest", str(m)], channel=fake)
    assert rc == 1
    assert fake.calls == []


# ── 發射主體：有效核准＋假通道（12 格）─────────────────────────────


def test_fire_valid_approval_fake_channel_rc0_12cells(tmp_path):
    fake = FakeChannel(tokens=1000)
    plan = _plan()
    out = tmp_path / "out"
    result = g3.run_g3(plan, BASE, out, channel=fake, approval=_approval())
    # 12 格全跑（full_rloop 答案齊全→1 輪）
    assert len(result["cells"]) == 12
    assert all(c["status"] == "ok" for c in result["cells"])
    assert all(c["hidden_after"] == "UNKNOWN" for c in result["cells"])
    # 成本：4 擷取 + 12 作答 = 16 calls × 1000 tok
    t = result["totals"]
    assert t["model_calls"] == 16
    assert t["tokens"] == 16000
    # 結果落盤
    p = out / "g3_result.json"
    assert p.is_file()
    disk = json.loads(p.read_text(encoding="utf-8"))
    assert disk["schema"] == g3.SCHEMA_RESULT
    assert disk["stop_reason"] is None


def test_three_arms_same_task_input_and_list_only_for_two_arms(tmp_path):
    fake = FakeChannel(tokens=1000)
    plan = _plan()
    result = g3.run_g3(plan, BASE, tmp_path / "o", channel=fake, approval=_approval())
    by_task = {}
    for c in result["cells"]:
        by_task.setdefault(c["task"], []).append(c)
    for tid, cells in by_task.items():
        assert len(cells) == 3
        shas = {c["input_sha256"] for c in cells}
        assert len(shas) == 1, "三臂同任務＝同輸入（same_draft_same_budget）"
    # 需求清單只進 reqlist_only/full_rloop 的 prompt
    def prompts_of(arm: str) -> list[str]:
        return [r["prompt"] for c in fake.calls if re.search(rf"/{arm} r1$", c["purpose"])]
    for tid in list(by_task):
        native = [c["prompt"] for c in fake.calls if c["purpose"] == f"G3 {tid}/native_pi r1"][0]
        reqlist = [c["prompt"] for c in fake.calls if c["purpose"] == f"G3 {tid}/reqlist_only r1"][0]
        full = [c["prompt"] for c in fake.calls if c["purpose"] == f"G3 {tid}/full_rloop r1"][0]
        assert "【需求清單" not in native
        assert "【需求清單" in reqlist
        assert "【需求清單" in full
        # 任務＋資料段三臂逐字相同（只改臂段）
        def task_block(p: str) -> str:
            return p.split("【本輪要求】")[0]
        assert task_block(native) == task_block(reqlist) == task_block(full)


def test_prompts_contain_no_hidden_or_scorer(tmp_path):
    fake = FakeChannel(tokens=100)
    g3.run_g3(_plan(), BASE, tmp_path / "o", channel=fake, approval=_approval())
    for c in fake.calls:
        assert "/srv/eval" not in c["prompt"]
        assert "scorer.py" not in c["prompt"]
        assert "hidden" not in c["prompt"].lower() or "hidden_after" in c["prompt"]


# ── 成本缺值＝UNKNOWN，絕不填 0 ────────────────────────────────────


def test_missing_usage_totals_unknown_not_zero(tmp_path):
    fake = FakeChannel(tokens=None)  # raw usage 缺 tokens
    result = g3.run_g3(_plan(), BASE, tmp_path / "o", channel=fake, approval=_approval())
    t = result["totals"]
    assert t["model_calls"] == 16  # 呼叫數是事實，仍可數
    assert t["tokens"] is None, "缺值必須 UNKNOWN（None），不得填 0"
    assert t["tokens_missing"] is True
    for c in result["cells"]:
        assert c["status"] == "ok"


# ── 撞日額度→停、不重試（fail-closed）─────────────────────────────


def test_quota_exceeded_stops_no_retry(tmp_path):
    import dataclasses
    fake = FakeChannel(tokens=6000)
    plan = _plan()
    plan = dataclasses.replace(plan, budget=dict(plan.budget, daily_token_cap=12000))  # 小額度以便測試
    result = g3.run_g3(plan, BASE, tmp_path / "o", channel=fake, approval=_approval())
    # t1 擷取(6000)＋t1/native(6000)＝12000 撞額→之後全停
    assert result["stop_reason"] == "quota"
    assert len(fake.calls) == 2, "撞額後不得再呼叫（不重試）"
    assert sum(1 for c in result["cells"] if c["status"] == "not_run") == 11
    assert result["totals"]["cells_run"] == 1
    q = result["quota"]
    assert q["known_tokens"] == 12000 and q["daily_token_cap"] == 12000


def test_quota_guard_blocks_before_call():
    class Counting(g3.Channel):
        def __init__(self):
            self.n = 0
        def call(self, **kw):
            self.n += 1
            return "x", g3.RoundUsage(1, 100, 1)

    ch = Counting()
    guard = g3.QuotaGuard(ch, daily_token_cap=250)
    kw = dict(prompt="p", model="m", purpose="t", timeout_s=1)
    guard.call(**kw)  # known=100
    guard.call(**kw)  # known=200
    guard.call(**kw)  # known=300 ≥ 250 → 之後停
    with pytest.raises(g3.G3QuotaError):
        guard.call(**kw)
    assert ch.n == 3, "撞額後的呼叫必須被擋下（0 實際呼叫）"


def test_quota_guard_unknown_usage_bounded_by_call_cap():
    """r1376（真產品 bug）：token 用量全 UNKNOWN 時 token cap 不可測→舊碼放行
    無限呼叫＝fail-open（實證：cap=250 仍放行 50 次）。呼叫數恆可測，故以 max_calls
    兜底——工作量的界不得依賴「用量恰好被測到」。缺值仍報 UNKNOWN（不假裝 0），
    但放行必須有界。"""
    class Unknown(g3.Channel):
        def __init__(self):
            self.n = 0
        def call(self, **kw):
            self.n += 1
            return "x", g3.RoundUsage(1, None, 1)  # tokens=None（UNKNOWN）

    ch = Unknown()
    guard = g3.QuotaGuard(ch, daily_token_cap=250, max_calls=5)
    kw = dict(prompt="p", model="m", purpose="t", timeout_s=1)
    allowed = 0
    for _ in range(50):
        try:
            guard.call(**kw)
            allowed += 1
        except g3.G3QuotaError:
            break
    assert allowed == 5, f"unknown-usage 時呼叫必須被 max_calls 兜底，實際放行 {allowed} 次"
    assert ch.n == 5


def test_quota_guard_no_backstop_preserves_legacy_behavior():
    """max_calls=None（預設）＝不啟用後備——既有呼叫形狀不變（token cap 仍為唯一界）。"""
    class Unknown(g3.Channel):
        def __init__(self):
            self.n = 0
        def call(self, **kw):
            self.n += 1
            return "x", g3.RoundUsage(1, None, 1)

    ch = Unknown()
    guard = g3.QuotaGuard(ch, daily_token_cap=10**9)  # 大 cap，token 界不觸發
    kw = dict(prompt="p", model="m", purpose="t", timeout_s=1)
    for _ in range(10):
        guard.call(**kw)  # 不該被呼叫數擋下（未啟用後備）
    assert ch.n == 10, "max_calls=None 時不得以呼叫數擋下（保留既有行為）"


# ── full_rloop：第 2 輪僅在必要答案項缺失時才花 ──────────────────


def test_full_rloop_second_round_only_when_missing(tmp_path):
    plan = _plan()
    # 全部齊全→每格 1 輪（16 calls）
    fake = FakeChannel(tokens=10)
    r1 = g3.run_g3(plan, BASE, tmp_path / "o1", channel=fake, approval=_approval())
    assert all(len(c["rounds"]) == 1 for c in r1["cells"])
    assert len(fake.calls) == 16
    # 某 task 的 full_rloop 缺一個必要項→該格 2 輪（多 1 次呼叫）
    tid = plan.tasks[0]["task_id"]
    full = _full_answer(tid).splitlines()
    partial = "\n".join(full[:1]) + "\n"  # 只剩第一個答案項
    fake2 = FakeChannel(tokens=10, answer_for={f"{tid}/full_rloop": partial})
    r2 = g3.run_g3(plan, BASE, tmp_path / "o2", channel=fake2, approval=_approval())
    cell = next(c for c in r2["cells"] if c["task"] == tid and c["arm"] == "full_rloop")
    assert len(cell["rounds"]) == 2
    p2 = [c for c in fake2.calls if c["purpose"] == f"G3 {tid}/full_rloop r2"][0]
    assert "上一稿與缺口" in p2["prompt"] and "只修未滿足的條目" in p2["prompt"]
    # 其他 task 的 full_rloop 仍 1 輪
    assert sum(1 for c in r2["cells"] if c["arm"] == "full_rloop" and len(c["rounds"]) == 2) == 1


# ── 管線級：GlmChannel 不持金鑰、只走 glm CLI（靜態檢查）─────────


def test_glm_channel_uses_cli_only():
    import inspect
    src = inspect.getsource(g3.GlmChannel)
    assert "subprocess.run" in src and "self.glm_bin" in src
    assert "vibe_calls.jsonl" in src, "成本必須從 raw usage（vibe_calls.jsonl）讀"
    # 本模組不該出現金鑰/直連 vibe 的字樣
    mod = inspect.getsource(g3)
    assert "sk-" not in mod
    assert "vibe.completions" not in mod


def test_rc_codes_match_gate():
    assert (g3.RC_OK, g3.RC_PLAN, g3.RC_NOT_APPROVED) == (0, 1, 2)
    assert g3.RC_NOT_APPROVED == g3gate.RC_NOT_APPROVED
