"""G3 發射管線（vq-1zf.6＋AMEND-1）：接線＋假通道驗證，全程 0 真模型呼叫。

紅線（本測試即驗收）：
- 無核准/不合格核准 → RC 2、0 模型呼叫（fail-closed）
- 臂與預註冊定義不符（pi 臂缺 pi_channel 注入）→ RC 3、0 模型呼叫
  （核准過了也不發——conformance 門；詳見 test_reqloop_g3_conformance.py）
- AMEND-1（2026-11-11 人類裁決）：native_pi 接真 pi（PiChannel、本地模型
  lms1003qwen）；有效核准＋假 glm 通道＋假 pi 通道 → 12 格跑通、
  hidden_after 全 UNKNOWN
- 成本缺值 → UNKNOWN（None），絕不填 0
- 撞日額度 → 停、不得重試
- full_rloop 第 2 輪僅在已確認缺口時才花（無額外呼叫）
- prompt 無 /srv/eval/hidden/、無 scorer.py（leak_guard）
"""
from __future__ import annotations

import copy
import dataclasses
import json
import pathlib
import re

import pytest

import vacant_network.reqloop.g3 as g3
import vacant_network.reqloop.g3gate as g3gate

REPO = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = REPO / "ops" / "reqloop" / "g3_gate" / "manifest.json"
BASE = REPO / "ops" / "reqloop" / "g3_gate"
#: 凍結的三臂計畫含 native_pi（未接 pi_agent）→ 拒發；跑得通的臂組合
CONFORMING_ARMS = ("reqlist_only", "full_rloop")


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


def _plan_2arms():
    """兩臂（皆接線）版本的凍結計畫：native_pi 未接 pi_agent→conformance 拒發，
    其餘管線行為用這個版本驗。"""
    return dataclasses.replace(_plan(), arms=CONFORMING_ARMS)


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


# ── 發射主體：有效核准＋假通道（12 格，pi 臂走注入的假 pi 通道）───────


class FakePiChannel(g3.Channel):
    """native_pi 的假 pi 通道：router 依 purpose 臂名分流到此；回齊全答案。"""

    def __init__(self, *, tokens: int | None = 1000) -> None:
        self.calls: list[dict] = []
        self.tokens = tokens

    def call(self, *, prompt: str, model: str, purpose: str,
             timeout_s: float) -> tuple[str, g3.RoundUsage]:
        self.calls.append({"prompt": prompt, "purpose": purpose, "model": model,
                           "timeout_s": timeout_s})
        tid = purpose.split()[1].split("/")[0]
        names = g3.required_answer_names(
            (BASE / "tasks" / tid / "workspace" / "contract.md").read_text(encoding="utf-8"))
        answer = "\n".join(f"@{n}[1.00]" for n in names) + "\n"
        return answer, g3.RoundUsage(1, self.tokens, 5)


def test_three_arm_plan_refuses_without_pi_channel(tmp_path):
    """conformance：native_pi 已接線（AMEND-1）但 pi_channel 未注入→
    拒發（G3ArmsNotConformant）、0 模型呼叫。"""
    fake = FakeChannel(tokens=1000)
    fake_pi = FakePiChannel()
    with pytest.raises(g3.G3ArmsNotConformant) as ei:
        g3.run_g3(_plan(), BASE, tmp_path / "o", channel=fake,
                  approval=_approval())
    assert "pi_channel" in str(ei.value)
    assert fake.calls == [] and fake_pi.calls == []


def test_fire_valid_approval_fake_channels_rc0_12cells(tmp_path):
    fake = FakeChannel(tokens=1000)
    fake_pi = FakePiChannel(tokens=1000)
    plan = _plan()
    out = tmp_path / "out"
    result = g3.run_g3(plan, BASE, out, channel=fake, pi_channel=fake_pi,
                       approval=_approval())
    # 三臂 4 題＝12 格全跑（AMEND-1：native_pi 走 pi 通道；其餘臂答案齊全→1 輪）
    assert len(result["cells"]) == 12
    assert all(c["status"] == "ok" for c in result["cells"])
    assert all(c["hidden_after"] == "UNKNOWN" for c in result["cells"])
    # native_pi 4 格都由 pi 通道服務（router 依臂名分流）
    assert len(fake_pi.calls) == 4
    assert sorted(c["purpose"].split()[1] for c in fake_pi.calls) == [
        f"{t['task_id']}/native_pi" for t in plan.tasks]
    # 成本：4 擷取 + 12 作答 = 16 calls × 1000 tok（glm 與 pi 同額度界）
    t = result["totals"]
    assert t["model_calls"] == 16
    assert t["tokens"] == 16000
    # 結果落盤
    p = out / "g3_result.json"
    assert p.is_file()
    disk = json.loads(p.read_text(encoding="utf-8"))
    assert disk["schema"] == g3.SCHEMA_RESULT
    assert disk["stop_reason"] is None
    # content_reverify 全臂在帳上（native_pi/reqlist_only 未啟用；full_rloop
    # 啟用，擷取清單 unverified→verdict UNKNOWN，絕不假 PASS）
    for c in disk["cells"]:
        assert "content_reverify" in c
        if c["arm"] == "full_rloop":
            assert c["content_reverify"]["enabled"] is True
        else:
            assert c["content_reverify"]["enabled"] is False


def test_amend2_pi_arm_600s_glm_arms_and_extract_300s(tmp_path):
    """AMEND-2（2026-11-11，票 P20261111_0645-1）：pi 臂每格牆時＝
    budget.timeout_s_per_round_pi（600s）；glm 臂與擷取維持
    budget.timeout_s_per_round（300s）——per-channel cap 分流。

    首發實證：唯一成功的 pi 格用 278s（貼著 300s 線），3× pi 格 300s 超時；
    glm 臂的 8 個失敗是 token_limit（非牆時）——兩類 infra 失敗分開歸因、分開修。"""
    fake = FakeChannel(tokens=1000)
    fake_pi = FakePiChannel(tokens=1000)
    plan = _plan()
    g3.run_g3(plan, BASE, tmp_path / "o", channel=fake,
              pi_channel=fake_pi, approval=_approval())
    assert fake_pi.calls, "native_pi 格必須由 pi 通道服務"
    assert {c["timeout_s"] for c in fake_pi.calls} == {600}, \
        "pi 臂每格牆時必須是 AMEND-2 的 600s（實測："
    assert fake.calls, "glm 通道（擷取＋兩臂）必須有呼叫"
    assert {c["timeout_s"] for c in fake.calls} == {300}, \
        "glm 臂＋擷取每輪牆時必須維持 300s（AMEND-2 不改 glm）"


def test_glm_channel_passes_explicit_max_tokens_total():
    """glm 臂 token_limit 修復（票 P20261111_0645-1，選項 a：提升 glm 上限）：
    GlmChannel 必須顯式傳 --max-tokens——vibe help 原文「Maximum total prompt +
    completion tokens」：該參數是 prompt+completion 總預算，不是 completion 上限。
    首發 8×「Stopped: token_limit」實證：answer prompt input 32609–39266 tok
    （vibe_calls.jsonl）全部 > glm CLI 預設 30000→completion 被擠成 55–181 tok；
    擷取 call（input 5.7K tok）在 30000 內→全成。新 cap 必須 > 首發最大 prompt。"""
    import inspect
    src = inspect.getsource(g3.GlmChannel)
    assert "--max-tokens" in src, "GlmChannel 必須顯式傳 --max-tokens（不能靠 CLI 預設 30000）"
    assert "GLM_MAX_TOKENS_TOTAL" in src
    assert g3.GLM_MAX_TOKENS_TOTAL > 39266, \
        "cap 必須 > 首發最大 answer prompt input（39266 tok）＋completion 空間"
    assert g3.GLM_MAX_TOKENS_TOTAL > 30000, "cap 不得低於舊預設（放寬方向）"


def test_arms_same_task_input_and_arm_specific_prompt(tmp_path):
    """三臂同任務＝同輸入 sha；需求清單只進帶清單的臂；pi 臂 prompt 用
    凍結 instruction（工作區有真檔案，不內嵌資料預覽）。"""
    fake = FakeChannel(tokens=1000)
    fake_pi = FakePiChannel(tokens=1000)
    plan = _plan()
    result = g3.run_g3(plan, BASE, tmp_path / "o", channel=fake,
                        pi_channel=fake_pi, approval=_approval())
    by_task = {}
    for c in result["cells"]:
        by_task.setdefault(c["task"], []).append(c)
    for tid, cells in by_task.items():
        assert len(cells) == 3
        shas = {c["input_sha256"] for c in cells}
        assert len(shas) == 1, "三臂同任務＝同輸入（same_draft_same_budget）"
        reqlist = [c["prompt"] for c in fake.calls if c["purpose"] == f"G3 {tid}/reqlist_only r1"][0]
        full = [c["prompt"] for c in fake.calls if c["purpose"] == f"G3 {tid}/full_rloop r1"][0]
        native = [c["prompt"] for c in fake_pi.calls if c["purpose"].startswith(f"G3 {tid}/native_pi")][0]
        assert "【需求清單" in reqlist
        assert "【需求清單" in full
        assert "【需求清單" not in native
        # glm 兩臂的任務＋資料段逐字相同（只改臂段）
        def task_block(p: str) -> str:
            return p.split("【本輪要求】")[0]
        assert task_block(reqlist) == task_block(full)
        # pi 臂的 prompt 逐字以凍結 instruction.txt 為本（不自撰任務）
        frozen_instr = (BASE / "tasks" / tid / "instruction.txt").read_text(encoding="utf-8").strip()
        assert frozen_instr in native
        assert "data_preview" not in native and "--- goal.md ---" not in native


def test_prompts_contain_no_hidden_or_scorer(tmp_path):
    fake = FakeChannel(tokens=100)
    g3.run_g3(_plan_2arms(), BASE, tmp_path / "o", channel=fake, approval=_approval())
    for c in fake.calls:
        assert "/srv/eval" not in c["prompt"]
        assert "scorer.py" not in c["prompt"]
        assert "hidden" not in c["prompt"].lower() or "hidden_after" in c["prompt"]


# ── 成本缺值＝UNKNOWN，絕不填 0 ────────────────────────────────────


def test_missing_usage_totals_unknown_not_zero(tmp_path):
    fake = FakeChannel(tokens=None)  # raw usage 缺 tokens
    result = g3.run_g3(_plan_2arms(), BASE, tmp_path / "o", channel=fake, approval=_approval())
    t = result["totals"]
    assert t["model_calls"] == 12  # 呼叫數是事實，仍可數
    assert t["tokens"] is None, "缺值必須 UNKNOWN（None），不得填 0"
    assert t["tokens_missing"] is True
    for c in result["cells"]:
        assert c["status"] == "ok"


# ── 撞日額度→停、不重試（fail-closed）─────────────────────────────


def test_quota_exceeded_stops_no_retry(tmp_path):
    import dataclasses
    fake = FakeChannel(tokens=6000)
    plan = _plan_2arms()
    plan = dataclasses.replace(plan, budget=dict(plan.budget, daily_token_cap=12000))  # 小額度以便測試
    result = g3.run_g3(plan, BASE, tmp_path / "o", channel=fake, approval=_approval())
    # t1 擷取(6000)＋t1/reqlist(6000)＝12000 撞額→之後全停
    assert result["stop_reason"] == "quota"
    assert len(fake.calls) == 2, "撞額後不得再呼叫（不重試）"
    assert sum(1 for c in result["cells"] if c["status"] == "not_run") == 7
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
    plan = _plan_2arms()
    # 全部齊全→每格 1 輪（12 calls）
    fake = FakeChannel(tokens=10)
    r1 = g3.run_g3(plan, BASE, tmp_path / "o1", channel=fake, approval=_approval())
    assert all(len(c["rounds"]) == 1 for c in r1["cells"])
    assert len(fake.calls) == 12
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


# ── r1419：GlmChannel raw usage 型別混淆（vq-el4.94）─────────────
# vibe_calls.jsonl 由外部 glm CLI 寫（被驗方自我聲明）；舊碼 `int(rec.get(
# "total_tokens"))` 把 JSON bool 當 int（false→0：實際耗 token 的呼叫記成本 0；
# true→1）、負數（-100→QuotaGuard known_tokens 被扣減、日額度更遲才觸發）、
# float（截斷）／string（自我聲明文字）全靜默接受＝quota fail-open（r1376 同族：
# 工作量的界不得依賴「用量恰好被測到」；r1405 strict-int／r1408 預算同族）。修＝
# 嚴 int≥0，否則 UNKNOWN（None，不填 0）。


def _fake_glm(tmp_path: pathlib.Path, usage_lines: list[str]) -> tuple[pathlib.Path, pathlib.Path]:
    """造假 glm 可執行檔：每次呼叫把 usage_lines 逐行追加進 state/vibe_calls.jsonl、rc 0。"""
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    log = state / "vibe_calls.jsonl"
    binpath = tmp_path / "fakeglm.py"
    body = "\n    ".join(f"f.write({line!r} + '\\n')" for line in usage_lines)
    binpath.write_text(
        "#!/usr/bin/env python3\nimport pathlib\n"
        f"p = pathlib.Path(r'{log}')\n"
        "with p.open('a', encoding='utf-8') as f:\n"
        f"    {body}\n"
        "print('answer text')\n",
        encoding="utf-8")
    binpath.chmod(0o755)
    return binpath, state


def _glm_call_once(tmp_path: pathlib.Path, usage_lines: list[str]) -> g3.RoundUsage:
    binpath, state = _fake_glm(tmp_path, usage_lines)
    ch = g3.GlmChannel(glm_bin=str(binpath), state_dir=state)
    _, usage = ch.call(prompt="p", model="m", purpose="t", timeout_s=10)
    return usage


def test_glm_channel_bool_total_tokens_unknown_not_zero(tmp_path):
    """r1419 負控：JSON bool 不是可數 token——false 被舊碼讀成 0（成本記 0，
    fail-open）、true 被讀成 1（被驗方自我聲明）。嚴 int 否則 UNKNOWN。"""
    for val in ("false", "true"):
        usage = _glm_call_once(tmp_path / val, ['{"total_tokens": ' + val + '}'])
        assert usage.tokens is None, f"total_tokens={val} 應 UNKNOWN，實得 {usage.tokens!r}"


def test_glm_channel_negative_total_tokens_unknown_not_negative(tmp_path):
    """r1419 負控：負數被舊碼回 -100→QuotaGuard known_tokens 被扣減＝日額度更遲
    觸發、更多呼叫獲准（fail-open 方向）。嚴 int≥0。"""
    usage = _glm_call_once(tmp_path / "neg", ['{"total_tokens": -100}'])
    assert usage.tokens is None, f"total_tokens=-100 應 UNKNOWN，實得 {usage.tokens!r}"


def test_glm_channel_float_string_total_tokens_unknown(tmp_path):
    """r1419 負控：float（123.5→截斷 123）／string（'123' 自我聲明文字）不是
    可信計數→UNKNOWN（同 r1405 strict-int 族；門不得信被驗方的自我聲明）。"""
    for val in ('123.5', '"123"'):
        usage = _glm_call_once(tmp_path / val.replace("\"", "").replace(".", "_"),
                               ['{"total_tokens": ' + val + '}'])
        assert usage.tokens is None, f"total_tokens={val} 應 UNKNOWN，實得 {usage.tokens!r}"


def test_glm_channel_int_total_tokens_still_counts(tmp_path):
    """r1419 正控：真 glm CLI 形狀（嚴格 int，實測 vibe_calls.jsonl 如 10164）仍
    正常計數；每次呼叫只讀自己新增的 usage 行（非跨呼叫累計）。"""
    binpath, state = _fake_glm(tmp_path / "ok", ['{"total_tokens": 123}'])
    ch = g3.GlmChannel(glm_bin=str(binpath), state_dir=state)
    _, u1 = ch.call(prompt="p", model="m", purpose="t", timeout_s=10)
    assert u1.tokens == 123
    _, u2 = ch.call(prompt="p", model="m", purpose="t", timeout_s=10)
    assert u2.tokens == 123, "第二呼只讀自己的新行（123），不是累計 246"


def test_glm_channel_multi_line_usage_sums(tmp_path):
    """r1419 正控：一次呼叫產生多行 usage（如 glm 內部多階段）→ 加總（舊行為保留）。"""
    usage = _glm_call_once(tmp_path / "multi", ['{"total_tokens": 100}', '{"total_tokens": 50}'])
    assert usage.tokens == 150


def test_glm_channel_mixed_good_and_bad_line_unknown(tmp_path):
    """r1419 負控：一次呼叫的多行中任一行不可信（100＋false）→ 整呼 UNKNOWN
    （不得 100+0=100 把壞行洗成 0 混入總計）。"""
    usage = _glm_call_once(tmp_path / "mixed", ['{"total_tokens": 100}', '{"total_tokens": false}'])
    assert usage.tokens is None, f"混入 bool 行應整呼 UNKNOWN，實得 {usage.tokens!r}"


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


# ── 無工具覆寫指令（P20261111_0840-1 項 1／AMEND-3 核准）─────────────


def _agent_style_task() -> dict:
    """agent 式任務文本（原為工具使用者所寫：讀檔＋寫檔指令）。"""
    return {
        "instruction": ("讀取 data/airfare.csv，計算 fare 的均值與標準差，"
                        "把結果寫進 answer.txt。"),
        "goal": "計算 fare 的均值與標準差。",
        "contract": "@mean_fare[...]\n@std_dev_fare[...]\n",
        "data": {"airfare.csv": "fare\n1.0\n2.0\n3.0\n"},
    }


def test_cell_prompt_no_tool_override_negative_control():
    """P20261111_0840-1 負控制（先紅後綠）：現版 prompt 對 agent 式任務文本
    缺無工具覆寫——模型照文本做 agent 動作（讀檔/寫檔）撞 --max-turns 1
    --enabled-tools none → turn_limit（fire a/b：glm 臂 8/8 turn_limit、
    9-15s、輸出 67-164 tok）。修法後：build_cell_prompt（含 round>=2 修復輪）
    頂部必須有顯式無工具覆寫。本測試對現版碼必紅、對修法碼必綠。"""
    task = _agent_style_task()
    spec = dict(g3.ARM_SPECS["reqlist_only"])
    p1 = g3.build_cell_prompt(task, spec, round_no=1)
    p2 = g3.build_cell_prompt(task, spec, round_no=2,
                             prev_draft="@mean_fare[1.00]\n", feedback="缺口：@std_dev_fare")
    for label, p in (("round1", p1), ("round2", p2)):
        assert "你沒有任何工具" in p, (
            f"{label} prompt 無無工具覆寫（agent 式任務文本＋無工具通道→turn_limit，見 fire a/b）")
        assert "不要讀檔、不要寫檔" in p, f"{label} prompt 未明令禁止讀檔/寫檔"


def test_cell_prompt_no_tool_override_before_task_text():
    """P20261111_0840-1 正控制：覆寫指令存在且位於任務文本之前（票面驗收）；
    round 1 與 round>=2 修復輪都在頂部；覆寫不改變臂段（三臂同源指令不變）。"""
    task = _agent_style_task()
    for arm in ("reqlist_only", "full_rloop"):
        spec = dict(g3.ARM_SPECS[arm])
        p1 = g3.build_cell_prompt(task, spec, round_no=1)
        p2 = g3.build_cell_prompt(task, spec, round_no=2,
                                 prev_draft="d", feedback="f")
        for label, p in (("round1", p1), ("round2", p2)):
            assert g3.NO_TOOL_OVERRIDE in p, f"{arm}/{label} 無覆寫常數"
            assert p.index(g3.NO_TOOL_OVERRIDE) < p.index(task["instruction"].strip()), (
                f"{arm}/{label}：覆寫必須在任務文本之前")
            # 覆寫在最頂（第一行）——「頂部加顯式覆寫」的如實形
            assert p.startswith(g3.NO_TOOL_OVERRIDE), f"{arm}/{label}：覆寫必須在 prompt 頂部"
        # 臂段指令不被覆寫吞掉
        assert g3.ARM_SPECS[arm]["instruction"] in p1
