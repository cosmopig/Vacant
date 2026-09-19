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
import re
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
    # ⚠ 只數 **ON 臂**。2026-09-19 起同一格還有一串 `arm: "OFF"` 的事件
    #   （反事實那一臂，一次 spawn、沒有閘門）。不濾就會把 OFF 的那一筆
    #   `draft_done` 算進 ON 的迴圈裡。
    on = [e for e in evs if e.get("arm") == to_events.ARM_ON]
    gates = [e for e in on if e["type"] == "gate_ran"]
    drafts = [e for e in on if e["type"] == "draft_done"]
    revised = [e for e in on if e["type"] == "revised"]
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
    # ⚠ 2026-09-19 改名：重試臂在 `retry_arm`，`arm` 專職分 ON／OFF。
    #   兩個意思擠在同一個欄位裡，patch 過的電視按 `arm` 分組時
    #   `revised` 會掉進第三組，那一格的重改拍就從 ON 那一串裡消失。
    assert rv[0]["retry_arm"] == "revise"
    assert rv[0]["arm"] == to_events.ARM_ON, "重改是 ON 臂的事，OFF 臂沒有迴圈"


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
    # 兩臂都要清。只清 ON 的話，OFF 的事後稽核訊息會把路徑整串印上展場螢幕。
    off = msg.replace("_frozen_RUN-ON", "_frozen_RUN-OFF")
    out2 = packlib.redact_paths(off, tmp_path / "elsewhere")
    assert "/Users/" not in out2, "OFF 臂的路徑沒有被清掉"


# ── 七、反事實那一臂：**跑過**，而且不准長得像裁決（2026-09-19 傍晚）──────

def test_the_counterfactual_arm_was_actually_run(pack):
    """展場主視覺的那句「同題關掉這層」，底下要真的有一跑。

    在此之前電視印「同題關掉這層：**也擋下**」，而 `liveAssemble` 寫死
    `OFF: null`——那一臂**一次都沒跑過**。`t.OFF || {}` 讓 `off.accepted`
    是 undefined，畫面照樣印出「也擋下」。**替一個沒發生的反事實作證**
    （對照表 A4：「展場的主視覺就是這個對照，這條錯得最貴」）。
    """
    offs = [c.get("off") for c in pack["cells"]]
    assert all(o and o.get("ran") for o in offs), "有格子沒有 OFF 臂"
    for c in pack["cells"]:
        o = c["off"]
        if o.get("infra_void"):
            continue
        assert o["requests_seen"] > 0, \
            f"{c['cell_id']}：OFF 臂沒有任何一通被中介到，證明不了它真的跑過"
        assert o["same_start_as_on"], \
            f"{c['cell_id']}：兩臂的起點不同 ⇒「唯一差別是那一層」這句話說不出口"


def test_the_off_arm_has_no_verdict_and_no_receipt(pack):
    """OFF ＝ 沒有這一層。它**沒有裁決、沒有收據**，這兩件事要在資料上看得見。

    · `accepted` 恆為 `null`（＝沒量）。壓成 `false` 就是把「沒有這一層」
      演成「這一層在另一邊也判了」——那會讓觀眾以為關掉之後還是有人在擋。
    · `has_receipt` 恆為 `false`。這是展件最值得看的一格差別：
      ON 那邊有一條從創世驗得到鏈頭的鏈，OFF 這邊**什麼都沒有**。
    """
    for c in pack["cells"]:
        o = c["off"]
        assert o["accepted"] is None, c["cell_id"]
        assert o["has_receipt"] is False, c["cell_id"]
        if not o.get("infra_void"):
            assert o["stop_reason"] == "ungated", c["cell_id"]


def test_the_post_hoc_audit_never_pretends_to_be_a_verdict(pack, events):
    """事後稽核要自己說它是事後的，否則它與當場的裁決在資料上分不開。"""
    for c in pack["cells"]:
        pa = (c["off"] or {}).get("postaudit")
        if pa is None:
            continue
        assert pa["when"] == "after_the_run"
        assert pa["is_verdict"] is False and pa["signed"] is False
        assert "事後" in pa["note"]
    pas = [e for e in events if e["type"] == "postaudit"]
    assert pas, "OFF 臂跑了卻一筆事後稽核都沒有 ⇒ 展場沒有東西可以對照"
    for e in pas:
        assert e["arm"] == to_events.ARM_OFF
        assert e["is_verdict"] is False and e["signed"] is False


def test_validate_rejects_an_off_arm_that_claims_a_gate_or_a_receipt(events):
    """負控制：把 OFF 臂寫成有閘門／有收據／有裁決，契約自檢要咬人。"""
    for bad_ev in (
        {"type": "gate_ran", "ts": "9999", "task_id": "x",
         "arm": to_events.ARM_OFF, "passed": False},
        {"type": "receipt", "ts": "9999", "task_id": "x",
         "arm": to_events.ARM_OFF, "sha256": "deadbeef"},
        {"type": "verdict", "ts": "9999", "task_id": "x",
         "arm": to_events.ARM_OFF, "accepted": False, "meets_demand": None},
    ):
        assert to_events.validate(events + [bad_ev]), bad_ev["type"]


def test_evidence_level_is_derived_per_cell_never_declared(pack):
    """證據等級**逐格**從落盤資料推，宣告蓋不過去（展場版鐵律 5）。

    `requests_seen == 0` ⇒ L-none，即使這一批宣告 `--evidence L-real`。
    這一條是可執行的 fail-closed，不是一句承諾。
    """
    for c in pack["cells"]:
        assert c["evidence"] == packlib.evidence_level(
            requests_seen=c["requests_seen"],
            declared=c["declared_evidence"]), c["cell_id"]
        if c["requests_seen"] == 0:
            assert c["evidence"] == "L-none", c["cell_id"]
    # fail-closed 的負控制：宣告 L-real 配 0 通，還是 L-none。
    assert packlib.evidence_level(requests_seen=0, declared="L-real") == "L-none"
    assert packlib.evidence_level(requests_seen=3, declared="") == "L-unknown"


def test_the_withheld_name_really_is_withheld(pack):
    """展件的整個故事都壓在這一句上：**客戶要的那個名字沒寫在需求裡**。

    「扣住／寫明」那一組反事實，差別必須**就是**那個名字：
    `TASK.md` 裡沒有它、`TASK_explicit.md` 裡有它。哪一題其實寫了，
    那一格在展場上講的故事就是假的——而那不是頁面的錯，是題庫選錯了，
    所以判準放在這裡，不放在頁面。

    ⚠ 只讀 `TASK.md`／`TASK_explicit.md` 與 `meta.json`，
      **不讀 `hidden/` 一個 byte**（V/GT 紅線）。
    """
    bank = REPO / "ops" / "gain" / "r535" / "bank"
    seen = 0
    for task_id in sorted({c["task_id"] for c in pack["cells"]}):
        d = bank / task_id
        if not d.is_dir():
            pytest.skip(f"題庫不在這個工作樹裡：{task_id}")
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        held = (d / "TASK.md").read_text(encoding="utf-8")
        explicit = (d / "TASK_explicit.md").read_text(encoding="utf-8")
        for name in meta["required_names"]:
            word = re.compile(r"\b%s\b" % re.escape(name))
            assert not word.search(held), \
                f"{task_id}：扣住版的題面裡其實寫了 {name!r}，那一格的故事是假的"
            assert word.search(explicit), \
                f"{task_id}：寫明版的題面裡反而沒有 {name!r}"
            seen += 1
    assert seen, "一個名字都沒檢查到"


def test_a_killed_attempt_is_distinguishable_from_one_that_just_failed(pack, events):
    """**被牆鐘上限砍掉**與**自己跑完但沒過**不可以在資料上同形。

    兩者的 `stop_reason` 都是 `visible_fail`——launcher 砍掉 agent 之後照樣凍結
    工作區、照樣送驗收，那是對的（它交出來的就是那些位元組）。但展場上這是
    兩個故事：一個是「它做不出來」，一個是「**我們沒等它**」。
    只有 `stop_reason` 的話，第二個會被講成第一個。

    真的發生過：`s1_30_ord_suffix__held` 三位居民共 8 次嘗試全部 300 秒被砍，
    那一題的「拒交」有一部分是我們的 `--timeout` 造成的，不是模型的行為。
    """
    for c in pack["cells"]:
        assert "any_attempt_timed_out" in c, c["cell_id"]
        for a in c["attempts"]:
            assert "agent_timed_out" in a, c["cell_id"]
        assert c["any_attempt_timed_out"] == any(
            a["agent_timed_out"] for a in c["attempts"]), c["cell_id"]
    # 事件流上也要帶著，否則電視拿不到資料就只能照 stop_reason 講
    drafts = [e for e in events if e["type"] == "draft_done"]
    assert drafts and all("timed_out" in e for e in drafts)
    killed = [e for e in drafts if e["timed_out"]]
    for e in killed:
        assert e["timed_out_note"], "被砍掉的那一次要講得出它為什麼沒過"
    # 負控制：這一批真的有被砍掉的格，這條測試才不是空轉
    assert killed, "這一批沒有任何一次被砍掉——若屬實請改掉這條測試的敘述"


def test_infra_void_cells_are_marked_not_counted_as_refusals(pack):
    """鐵律 3：「沒量到」≠「量到 0」。跑掛的格**不進 `cells`**，進 `void_cells`。

    把 `infra_void` 當成拒交格，展場上就會變成
    「Vacant 擋住了一件**根本沒發生**的交付」。
    """
    assert "void_cells" in pack, "資料包要說得出哪些格跑掛了"
    for c in pack["cells"]:
        assert not c.get("infra_void"), c["cell_id"]
    for v in pack["void_cells"]:
        assert v["infra_void"] or v["stop_reason"], v["cell_id"]
    assert pack["void"] == len(pack["void_cells"])
