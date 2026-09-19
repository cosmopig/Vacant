"""V/GT 動態稽核 v3（round534）：**十條臂都要被掃到，而且掃得動**。

這支在架構裡承重什麼
────────────────────
`harness_vgt_audit.audit_run()` 在 v1／v2 之下開頭就是
`if arm not in VARIANTS: continue`，而 `VARIANTS = ("HPI","HOC","HMIX")`。
於是 `OFF`／`OFF5`／`CONFORM`／`EQ5`／`ON`／`ONR`／`CALIBRATION` **從來沒有被
動態稽核掃過一次**，而我們拿那份輸出講過「整個 run V/GT CLEAN」。
方向不是中性的：Δ_C ＝ HMIX − CONFORM，沒驗過的是被減數那一側。

這裡釘三件事，少一件 v3 就等於沒改：

1. **範圍**：`audit_run(scope="v3")` 逐臂真的掃到了（`per_arm` 有那一臂）。
2. **牙齒**：逐臂各做一次負向控制——把一個**真的**只在隱藏側出現的 repr
   塞進 harness 自己寫的文字裡，十條臂都必須判 `VIOLATION`。
   抓不到就是量具沒有牙齒，不是通過。
3. **fail-closed**：某一臂在 `calls.jsonl` 裡有紀錄卻 0 筆進稽核 ⇒
   verdict 是 `UNVERIFIABLE` 不是 `CLEAN`。這一條是「沒有檢查不准冒充
   沒有違規」的可執行版本，也正是這個洞躲了這麼久的原因（跳過是靜音的）。

零 API 呼叫、零機時：輸入只有釘死的題庫與本檔自己寫出來的 `calls.jsonl`。
"""
from __future__ import annotations

import json

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain.harness_vgt_audit import (AUDITED_ARMS,  # noqa: E402
                                        CLASSIC_ARMS, MODEL_QUOTE_EXCUSE,
                                        audit_run, hidden_only_needles,
                                        scope_arms)
from ops.gain.harness_arms import VARIANTS  # noqa: E402


@pytest.fixture(scope="module")
def task():
    """一題真的 LCB v2 題目（本機就有，不必等 VM 的 EvalPlus 官方包）。"""
    from vacant_network.codebench import LiveCodeBenchLoader
    try:
        tasks = list(LiveCodeBenchLoader(version="v2").iter_tasks("vgt-allarms"))
    except (FileNotFoundError, ValueError) as exc:               # pragma: no cover
        pytest.skip(f"LCB v2 題庫不在本機：{exc}")
    for t in tasks:
        needles, _ = hidden_only_needles(t)
        if needles:
            return t
    pytest.skip("這份題庫一題都沒有非瑣碎 needle ⇒ 負控沒有對象")


@pytest.fixture(scope="module")
def needle(task):
    needles, _skipped = hidden_only_needles(task)
    assert needles, "一個 needle 都不剩 ⇒ 量具等於關掉，不是通過"
    return needles[0]


def _calls(tmp_path: pathlib.Path, records: list[dict]) -> pathlib.Path:
    (tmp_path / "calls.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8")
    return tmp_path


def _classic_record(arm: str, task_id: str, prompt: str, system: str = "你是一位程式設計師。"):
    """古典臂的**真實**落盤形狀：`system` ＋ `prompt`，沒有 `messages`。

    實測 179 份 `calls.jsonl` 裡七個古典臂全部長這樣
    （`gain_run` 那幾支都走 `agent.generate(prompt, ...)`）。
    """
    return {"meta": {"arm": arm, "task_id": task_id}, "role": "gen",
            "system": system, "prompt": prompt, "response": "```python\npass\n```"}


def _harness_record(arm: str, task_id: str, text: str, system: str = "s"):
    """H 臂的形狀：`messages` 多輪。"""
    return {"meta": {"arm": arm, "task_id": task_id, "kind": "build",
                     "turn": 1, "wire_mode": "multiturn"},
            "system": system, "messages": [{"role": "user", "content": text}],
            "response": "```python\npass\n```"}


def _record_for(arm: str, task_id: str, text: str, **kw):
    return (_harness_record(arm, task_id, text, **kw) if arm in VARIANTS
            else _classic_record(arm, task_id, text, **kw))


# ── 1. 範圍：v3 的名單就是十條臂，v1／v2 凍結在三條 ─────────────────────
def test_scope_arms_v3_covers_every_arm_the_runner_can_emit():
    """`AUDITED_ARMS` 必須涵蓋 `gain_run.KNOWN_ARMS` ＋ CALIBRATION ＋ H 三臂。

    ⚠ `KNOWN_ARMS` 是 `gain_run.main()` 裡的區域常數（import 不到），所以從
      **原始碼**把它讀回來——`gain_run.py` 一個字都不准改（`FROZEN_SOURCE_SHA`
      與 `r493_appendix_prose_census.py` 的絕對行號釘在上面）。
      讀不到 9 個名字就當場失敗，免得正則漂掉之後這條測試變成空跑。
    """
    import re as _re

    src = (ROOT / "ops" / "gain" / "gain_run.py").read_text(encoding="utf-8")
    block = _re.search(r"KNOWN_ARMS = \{([^}]*)\}", src)
    assert block, "在 gain_run.py 找不到 KNOWN_ARMS ⇒ 這條測試沒接上"
    known = set(_re.findall(r'"([A-Z0-9]+)"', block.group(1)))
    assert len(known) == 9, sorted(known)
    assert known <= set(AUDITED_ARMS), sorted(known - set(AUDITED_ARMS))
    assert "CALIBRATION" in AUDITED_ARMS, \
        "calibrate_pool 也在送 prompt，漏掉它就是給同一個洞開一個小號"
    assert set(VARIANTS) <= set(AUDITED_ARMS)
    assert set(scope_arms("v3")) == set(AUDITED_ARMS)
    # v1／v2 的臂範圍是**凍結的歷史**：R460 收官那 90／0 釘在上面，不准動。
    assert set(scope_arms("v1")) == set(scope_arms("v2")) == set(VARIANTS)


@pytest.mark.parametrize("arm", AUDITED_ARMS)
def test_v3_actually_audits_each_arm(arm, task, tmp_path):
    """正向：每一臂都真的有紀錄進稽核（`per_arm` 不是空的）。"""
    rec = [_record_for(arm, task["task_id"], task["prompt"])]
    r = audit_run(_calls(tmp_path, rec), {task["task_id"]: task}, scope="v3")
    assert r["per_arm"] == {arm: 1}, r["per_arm"]
    assert r["verdict"] == "CLEAN", r["violations"][:3]
    assert r["needles_unique_scanned"] > 0, \
        "一個 needle 都沒掃 ⇒ 量具沒接上，不是通過"


# ── 2. 負向控制：逐臂各一次，抓不到就是沒有牙齒 ──────────────────────────
@pytest.mark.parametrize("arm", AUDITED_ARMS)
def test_negative_control_planted_hidden_repr_is_caught_per_arm(
        arm, task, needle, tmp_path):
    """把**真的**隱藏 repr 塞進 harness 自己寫的 user 文字 ⇒ 十條臂都要紅。

    刻意接在題目原文**後面**：規則 (a) 逐字扣掉的是 `task['prompt']`，
    扣完剩下的那一段就是 harness 自己寫的 —— 負控要打的正是那一段。
    """
    text = task["prompt"] + f"\n\nHint: make sure it returns {needle} there.\n"
    rec = [_record_for(arm, task["task_id"], text)]
    r = audit_run(_calls(tmp_path, rec), {task["task_id"]: task}, scope="v3")
    assert r["verdict"] == "VIOLATION", (arm, r["per_arm"])
    assert r["violations"][0]["rule"] == "hidden_case_leak"
    assert r["violations"][0]["arm"] == arm


@pytest.mark.parametrize("arm", AUDITED_ARMS)
def test_negative_control_system_prompt_gets_no_excuse_per_arm(
        arm, task, needle, tmp_path):
    """`system` 一格豁免都不給——十條臂逐臂各驗一次。"""
    rec = [_record_for(arm, task["task_id"], task["prompt"],
                       system=f"你是一位程式設計師。記得答案是 {needle}。")]
    r = audit_run(_calls(tmp_path, rec), {task["task_id"]: task}, scope="v3")
    assert r["verdict"] == "VIOLATION", (arm, r["per_arm"])
    assert r["violations"][0]["role"] == "system"


@pytest.mark.parametrize("arm", CLASSIC_ARMS)
def test_negative_control_check_code_identifier_per_classic_arm(
        arm, task, tmp_path):
    """驗收碼原始碼被貼進古典臂的 prompt ⇒ `check_code_identifier`。"""
    text = task["prompt"] + "\n\n" + task["visible_check"]["code"]
    rec = [_record_for(arm, task["task_id"], text)]
    r = audit_run(_calls(tmp_path, rec), {task["task_id"]: task}, scope="v3")
    assert r["verdict"] == "VIOLATION"
    assert "check_code_identifier" in {v["rule"] for v in r["violations"]}


# ── 3. fail-closed：沒掃到的臂不准冒充乾淨 ──────────────────────────────
def test_arm_present_but_never_audited_is_unverifiable(task, tmp_path):
    """`A-SOLO`（R530 的臂）混進來 ⇒ v3 判 UNVERIFIABLE，不是 CLEAN。

    這一條是 round534 的核心：**跳過必須有聲音**。
    """
    rec = [_classic_record("OFF", task["task_id"], task["prompt"]),
           {"meta": {"arm": "A-SOLO", "task_id": task["task_id"]},
            "system": "s", "prompt": task["prompt"]}]
    r = audit_run(_calls(tmp_path, rec), {task["task_id"]: task}, scope="v3")
    assert r["verdict"] == "UNVERIFIABLE", r
    assert r["arms_present_not_audited"] == ["A-SOLO"]
    assert r["arms_present"]["A-SOLO"] == 1 and not r["per_arm"].get("A-SOLO")


def test_no_records_at_all_is_unverifiable(tmp_path):
    """只有 preflight（沒有任何 arm）⇒ UNVERIFIABLE。`audit_run` 原本沒有這一格。"""
    rec = [{"meta": {"model": "m"}, "role": "preflight",
            "system": "You are a helpful assistant.", "prompt": "Reply with exactly: OK"}]
    r = audit_run(_calls(tmp_path, rec), {}, scope="v3")
    assert r["verdict"] == "UNVERIFIABLE" and r["records_audited"] == 0


def test_v2_still_reports_the_arms_it_did_not_audit(task, tmp_path):
    """v2 的**判準**凍結，但它現在必須說出自己跳過了哪幾條臂。

    舊判準可以凍結，不准繼續靜音——`arms_present_not_audited` 就是那個聲音。
    """
    rec = [_classic_record("CONFORM", task["task_id"], task["prompt"]),
           _harness_record("HMIX", task["task_id"], task["prompt"])]
    r = audit_run(_calls(tmp_path, rec), {task["task_id"]: task}, scope="v2")
    assert r["verdict"] == "CLEAN"                 # v2 的判準沒有被改掉
    assert r["per_arm"] == {"HMIX": 1}
    assert r["arms_present_not_audited"] == ["CONFORM"]


# ── 4. ON 臂的作者歸屬豁免：夠寬能用、夠窄擋得住 ────────────────────────
def test_on_review_prompt_quoting_the_models_own_code_is_excused(
        task, needle, tmp_path):
    """`arm_on` 的評審 prompt 逐字嵌模型自己的初稿 ⇒ 豁免（留證不靜音）。"""
    code = f"def f():\n    return {needle}\n"
    gen = {"meta": {"arm": "ON", "phase": "initial", "task_id": task["task_id"]},
           "role": "gen", "system": "s", "prompt": task["prompt"],
           "response": f"```python\n{code}```"}
    review = {"meta": {"arm": "ON", "task_id": task["task_id"], "target": "w0"},
              "role": "review", "system": "reviewer",
              "prompt": (f"題目：\n{task['prompt']}\n\n候選解答：\n"
                         f"```python\n{code}```\n"),
              "response": "PASS"}
    r = audit_run(_calls(tmp_path, [gen, review]),
                  {task["task_id"]: task}, scope="v3")
    assert r["verdict"] == "CLEAN", r["violations"][:3]
    assert r["excused_by_rule"][MODEL_QUOTE_EXCUSE] >= 1
    assert all(e["excused_as"] == MODEL_QUOTE_EXCUSE for e in r["excused"])


def test_the_quote_excuse_does_not_cover_text_outside_the_quote(
        task, needle, tmp_path):
    """負控：同一則訊息裡，引文**之外**再出現一次 ⇒ 照樣 VIOLATION。

    判準是「**每一次**出現都落在引文區間內」。用「出現過一次在引文裡就整筆放行」
    就會讓這一格變成把 GT 藏在程式碼旁邊的通行證。
    """
    code = f"def f():\n    return {needle}\n"
    gen = {"meta": {"arm": "ON", "phase": "initial", "task_id": task["task_id"]},
           "role": "gen", "system": "s", "prompt": task["prompt"],
           "response": f"```python\n{code}```"}
    review = {"meta": {"arm": "ON", "task_id": task["task_id"], "target": "w0"},
              "role": "review", "system": "reviewer",
              "prompt": (f"題目：\n{task['prompt']}\n\n候選解答：\n"
                         f"```python\n{code}```\n"
                         f"（順帶一提，正確答案是 {needle}）\n"),
              "response": "PASS"}
    r = audit_run(_calls(tmp_path, [gen, review]),
                  {task["task_id"]: task}, scope="v3")
    assert r["verdict"] == "VIOLATION", r["excused_by_rule"]


def test_the_quote_excuse_only_looks_backwards(task, needle, tmp_path):
    """負控：引文來源出現在**後面**（還沒被模型寫出來）⇒ 不給豁免。

    引用必然晚於被引用者。反過來的順序代表那段文字不可能是回聲。
    """
    code = f"def f():\n    return {needle}\n"
    review = {"meta": {"arm": "ON", "task_id": task["task_id"], "target": "w0"},
              "role": "review", "system": "reviewer",
              "prompt": (f"題目：\n{task['prompt']}\n\n候選解答：\n"
                         f"```python\n{code}```\n"),
              "response": "PASS"}
    gen = {"meta": {"arm": "ON", "phase": "initial", "task_id": task["task_id"]},
           "role": "gen", "system": "s", "prompt": task["prompt"],
           "response": f"```python\n{code}```"}
    r = audit_run(_calls(tmp_path, [review, gen]),
                  {task["task_id"]: task}, scope="v3")
    assert r["verdict"] == "VIOLATION", r["excused_by_rule"]


def test_v2_does_not_gain_the_new_excuse_key(task, tmp_path):
    """v2 的 `excused_by_rule` 只准有三個鍵——`replay/r460/vgt_v2_*.json` 對得上。"""
    rec = [_harness_record("HMIX", task["task_id"], task["prompt"])]
    r = audit_run(_calls(tmp_path, rec), {task["task_id"]: task}, scope="v2")
    assert set(r["excused_by_rule"]) == {
        "visible_check_source", "model_own_selftest_same_request",
        "got_sandbox_echo"}
