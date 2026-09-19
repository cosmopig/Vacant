"""忠實度：**分身演的那件事，要與 Vacant 真做的那件事同形**（v2，2026-09-19）。

人類的要求逐字：「可能現在的數位分身的邏輯跟我們真實的不太一樣，但就改好來，
改成最終版 VACANT 的邏輯忠實呈現。」對照表與逐條理由在
`decisions/DECISION_20260919_TWIN_V2_FIDELITY.md`。

`tests/test_twin_events.py` 守的是「生產端不准多說一句話」；這一組守的是
**生產端不准少說、也不准說成別的形狀**：

  · `accepted` 是三值（null ＝ 沒量），不准 `bool()` 壓成兩值
  · `blocked_by` 由 `stop_reason` 推，不准寫死一個字
  · **重試迴圈要看得見**——V1 的機制本體（閘門 → 回饋 → 再 spawn 一次）
    被壓成一次 `draft_done` ＋ 一次 `gate_ran`，等於把 R530／R532 量到
    有用的那一段從展件上刪掉
  · `revised` 的 `reviser` 是**同一個 worker**，不是別人（換人就是演別的系統）
  · 這條路上不存在的層（評審、抽樣稽核）一個事件都不發，`counters` 也不發 0
  · 證據等級要**逐格**跟著事件走（展場版鐵律 5）
  · `pack.visible` 要與 `accepted` 是同一次嘗試的結果
"""
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import build_viewer, pack as packlib, to_events  # noqa: E402

VIEWER = REPO / "examples" / "twin_viewer.html"
PACK = REPO / "ops" / "exhibit" / "twin" / "twin_pack.json"


@pytest.fixture(scope="module")
def pack():
    return json.loads(PACK.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def events(pack):
    return to_events.build(pack, verify_url="twin_viewer.html",
                           t0_ms=1_789_000_000_000)


def _cell_with(pack, **over):
    """拿一格真的出來改欄位——形狀與簽章鏈都留著，只動被點名的那幾個。"""
    c = json.loads(json.dumps(pack["cells"][0]))
    c.update(over)
    return c


# ── 一、「沒量」不可以長成「量到沒過」 ────────────────────────────

def test_accepted_is_three_valued_not_boolean(pack):
    """`--allow-no-suite` 那一格 `accepted` 是 **null（沒量）**，不是 false。

    電視那條 `meets_demand: !!v.meets_demand` 把 null 收斂成 false 是同一種錯；
    這一條守的是**我們自己這一端**不准犯它（v1 的 `to_events` 真的犯了）。
    """
    c = _cell_with(pack, stop_reason="ungated")
    chain = [json.loads(ln) for ln in c["chain"]]
    for d in chain:
        if d["type"] == "ws_verdict":
            d["payload"]["accepted_is_null"] = True
    c["chain"] = [json.dumps(d, ensure_ascii=False) for d in chain]
    evs = to_events.events_for_cell(c, verify_url="x", ts_ms=0)
    v = [e for e in evs if e["type"] == "verdict"][0]
    assert v["accepted"] is None, "「沒量」被壓成了「量到沒過」"
    assert v["blocked_by"] is None, "沒量不是被擋下"
    assert v["stop_reason"] == "ungated"


def test_validate_rejects_ungated_with_a_boolean_accepted(pack):
    evs = to_events.build(pack, verify_url="x", t0_ms=0)
    for e in evs:
        if e["type"] == "verdict":
            e["stop_reason"] = "ungated"
            e["accepted"] = False
            break
    assert to_events.validate(evs), "「沒量卻給了布林」必須被擋下"


# ── 二、四種收尾不可以講成一件事 ──────────────────────────────────

def test_blocked_by_is_derived_from_stop_reason_not_hardcoded(pack):
    """v1 把 `blocked_by` 寫死 `"gate"`，等於把四種收尾講成一件事。"""
    got = {}
    for stop in ("visible_fail", "attempts_exhausted", "no_suite", "visible_pass"):
        c = _cell_with(pack, stop_reason=stop)
        evs = to_events.events_for_cell(c, verify_url="x", ts_ms=0)
        got[stop] = [e for e in evs if e["type"] == "verdict"][0]["blocked_by"]
    assert got["visible_pass"] is None
    assert got["visible_fail"] == got["attempts_exhausted"] == got["no_suite"] == "gate"
    c = _cell_with(pack, stop_reason="attempts_exhausted")
    evs = to_events.events_for_cell(c, verify_url="x", ts_ms=0)
    assert [e for e in evs if e["type"] == "verdict"][0]["stop_reason"] \
        == "attempts_exhausted", "壓縮過的那個字旁邊要留著原始理由"


def test_blocked_by_is_never_review(pack):
    """`review` 永遠不該出現：這條路上沒有評審層。"""
    assert "review" not in set(to_events.BLOCKED_BY.values())


# ── 三、V1 的機制本體要看得見 ─────────────────────────────────────

def _two_attempt_cell(pack):
    base = pack["cells"][0]
    a1 = json.loads(json.dumps(base["attempts"][0]))
    a1["visible"] = {"all_pass": False, "passed": 1, "total": 2,
                     "cases": [{"case": "check_02_mul", "ok": False}]}
    a1["stop_reason"] = "visible_fail"
    a2 = json.loads(json.dumps(a1))
    a2.update({"attempt": 2, "feedback_in_prompt_bytes": 512,
               "stop_reason": "visible_pass",
               "visible": {"all_pass": True, "passed": 2, "total": 2, "cases": []}})
    return _cell_with(pack, attempts=[a1, a2], attempts_used=2, retry="revise")


def test_retry_loop_is_visible_one_gate_per_attempt(pack):
    """**閘門 → 回饋 → 再 spawn 一次**，每一次都要自己說一次話。

    v1 把整個迴圈壓成一次 `draft_done` ＋ 一次 `gate_ran`
    ⇒ 展件在演 Vacant，卻把 R530／R532 量到有用的那一段刪掉了。
    """
    c = _two_attempt_cell(pack)
    evs = to_events.events_for_cell(c, verify_url="x", ts_ms=0)
    gates = [e for e in evs if e["type"] == "gate_ran"]
    drafts = [e for e in evs if e["type"] == "draft_done"]
    revised = [e for e in evs if e["type"] == "revised"]
    assert [g["passed"] for g in gates] == [False, True], "兩次閘門要各說各的"
    assert [g["attempt"] for g in gates] == [1, 2]
    assert len(drafts) == 2 and [d["attempt"] for d in drafts] == [1, 2]
    assert drafts[0]["feedback_bytes"] == 0, \
        "第 1 次的回饋位元組恆為 0 ＝ 與「沒有 Vacant」時逐位元相同"
    assert drafts[1]["feedback_bytes"] == 512
    assert len(revised) == 1, "沒過而且還有額度 ⇒ 剛好一次重改"
    assert to_events.validate(evs + [
        {"type": "counters", "ts": "9999", "task_id": "-"}]) == []


def test_reviser_is_the_same_worker_never_someone_else(pack):
    """Vacant 的重改是**同一個 agent 帶著自己的失敗原文再跑一次**。

    電視的 `revised` 原本演的是「評審推翻之後換人重寫」。換人就是演了別的系統。
    """
    c = _two_attempt_cell(pack)
    evs = to_events.events_for_cell(c, verify_url="x", ts_ms=0)
    rv = [e for e in evs if e["type"] == "revised"]
    assert rv and all(e["reviser"] == c["resident"] for e in rv)
    assert "VACANT_FEEDBACK" in rv[0]["transition"], "哪一條臂要逐字寫出來"
    assert rv[0]["arm"] == "revise"


def test_resample_and_revise_do_not_say_the_same_thing(pack):
    """兩條臂的差別**就是**實驗處理本身，不可以共用一句話。"""
    assert to_events.TRANSITION["revise"] != to_events.TRANSITION["resample"]
    assert "重置" in to_events.TRANSITION["resample"]
    assert "保留工作區" in to_events.TRANSITION["revise"]


# ── 四、不存在的層，一個事件都不發 ────────────────────────────────

def test_no_event_invents_a_layer_that_does_not_exist(events):
    """`vacant run` 沒有評審層、沒有抽樣稽核層、沒有路由層。"""
    kinds = {e["type"] for e in events}
    for never in to_events.NEVER:
        assert never not in kinds, never
    ctr = [e for e in events if e["type"] == "counters"]
    assert ctr and "audited" not in ctr[0], \
        "發 audited:0 就是把沒有的層畫成「有，只是這次沒抽中」"
    assert "on_leaked" not in ctr[0] and "off_leaked" not in ctr[0], \
        "漏出要隱藏測資才答得出來，而隱藏測資不進展件"


def test_validate_rejects_the_layers_that_do_not_exist(events):
    for never in to_events.NEVER:
        broken = events + [{"type": never, "ts": "9999", "task_id": "x"}]
        assert to_events.validate(broken), never


def test_routed_says_out_loud_that_there_is_no_routing_layer(events):
    for e in events:
        if e["type"] == "routed":
            assert e["basis"] == "random"
            assert "沒有路由層" in e["basis_note"], \
                "電視畫面上寫著「依信譽紀錄路由」——事件要帶著反證"


# ── 五、證據等級要逐格跟著走（展場版鐵律 5）────────────────────────

def test_evidence_level_rides_along_so_the_tv_can_label_each_cell(pack, events):
    """電視的誠實列在活模式寫死「判決與數字＝正在發生的真實 agent」。

    那句話對 L-none 的格子是假的。電視要有資料才改得對，所以事件要帶著。
    """
    lv = {c["cell_id"]: c["evidence"] for c in pack["cells"]}
    opened = [e for e in events if e["type"] == "task_opened"]
    assert opened and all(e["evidence"] == lv[e["task_id"]] for e in opened)
    assert all(e["evidence_note"] for e in opened), "標籤要附得出理由"
    ctr = [e for e in events if e["type"] == "counters"][0]
    assert ctr["evidence_counts"], "整批的等級分佈也要給，不然只能相信"


def test_receipt_carries_both_hashes_separately(events):
    """收據 hash 與題面 hash 是兩個東西，不准共用一個欄位。

    電視 v1 的 `prompt_sha256: get("receipt").sha256 || …` 把收據雜湊塞進一個
    叫 `prompt_sha256` 的欄位，活模式下畫面會顯示鏈頭而不是題面雜湊。
    生產端能做的是**兩個都帶**，讓 patch 過的電視分得開。
    """
    prompts = {e["task_id"]: e["prompt_sha256"]
               for e in events if e["type"] == "task_opened"}
    n = 0
    for e in events:
        if e["type"] == "receipt":
            n += 1
            assert e["prompt_sha256"] == prompts[e["task_id"]]
            assert e["sha256"] == e["chain_head"]
            assert e["sha256"] != e["prompt_sha256"], "兩個 hash 不該相等"
    assert n


# ── 六、pack：`visible` 要與 `accepted` 是同一次 ───────────────────

def test_pack_visible_is_the_last_attempt_not_the_first(pack):
    """一格「第 1 次沒過、第 3 次過」的 run，不可以在資料上長成
    「驗收沒過 ＋ 收下了」——那正是「收下了，其實漏出」那句話的形狀。
    """
    for c in pack["cells"]:
        assert c["visible"]["attempt"] == c["attempts_used"], c["cell_id"]
        if c["attempts"]:
            last = c["attempts"][-1]
            assert last["visible"]["all_pass"] == c["visible"]["all_pass"], \
                c["cell_id"]
            # 而且閘門結果要與簽章覆蓋的裁決同號（沒量的格子除外）
            if c["accepted"] is not None:
                assert bool(c["accepted"]) == bool(c["visible"]["all_pass"]), \
                    c["cell_id"]


def test_pack_carries_every_attempt_not_just_the_count(pack):
    for c in pack["cells"]:
        assert len(c["attempts"]) == c["attempts_used"], c["cell_id"]
        for a in c["attempts"]:
            assert "requests_seen" in a and "feedback_in_prompt_bytes" in a


def test_pack_has_no_absolute_build_paths():
    """建置這台機器的目錄結構不准印上展場螢幕。

    ⚠ 真的漏過：`redact_paths` 只比對「現在的 run_dir」，換一個 worktree
    重跑 `pack.py`，訊息裡當初那一台的絕對路徑就整串留下來。
    """
    raw = PACK.read_text(encoding="utf-8")
    for bad in ("/Users/", "/home/", "/private/var/", "worktrees/agent-"):
        assert bad not in raw, f"{bad} 漏進 twin_pack.json"
    html = VIEWER.read_text(encoding="utf-8")
    embedded = build_viewer.extract_block(html, "twin-pack")
    for bad in ("/Users/", "/home/", "worktrees/agent-"):
        assert bad not in embedded, f"{bad} 漏進展件頁面"


def test_redaction_survives_a_moved_run_dir(tmp_path):
    """路徑清洗必須與「現在在哪」無關——這正是漏出來的那一條。"""
    msg = ("ImportError: cannot import name 'mul' from 'solution' "
           "(/Users/someone/elsewhere/runs/x/_frozen_RUN-ON/solution.py)")
    out = packlib.redact_paths(msg, tmp_path / "a_completely_different_dir")
    assert "/Users/" not in out
    assert "<凍結快照>" in out
    assert "cannot import name 'mul'" in out, "訊息本體一個字都不准少"
