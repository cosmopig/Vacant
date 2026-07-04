"""生態核心的驗收測試（12 §7/§8）——全離線、確定性、用假腦。

承重什麼：把 `Ecosystem.delegate` 全迴圈（路由→生成→簽章互審→稽核→信譽/記憶
回寫→信任狀）與 trust on/off 的「一個布林差」做成可執行驗收，對齊規劃 12 §7 的
四個時刻與 §8 的「有感」清單。所有隨機性都被抽掉（UCB/checks/audit 抽樣皆
確定性），因此每條斷言在同一顆假腦下逐次可重放。

假腦分流（誠實標注）：saboteur tier 的種植文字（TIER_STYLE["saboteur"] 開頭的
'Include one subtle off-by-one'）會被 ecosystem 前置到 prompt——假腦據此回傳含
off-by-one 的 solve（丟掉最後一字），模擬 saboteur 的品質操弄；其餘一律回正確
solve。這不是責任修辭，是 12 §10.3 誠實標注的「品質植入」。

roster 取捨（誠實標注）：互審權重有地板（reviewer 冷啟動 weight≈0.05），信譽
移動很慢，6 人 DEFAULT_ROSTER 需 ~30 筆 delegate 才看得出 UCB 收斂餓死。為讓
「後半 saboteur 佔比 < 前半」這條在 §7 指定的 ~12 筆內確定性成立，核心迴圈測試
用精簡 roster（good×2＋saboteur×1）；full-roster 的長跑收斂屬 X 系列實驗，不在此。
"""

from __future__ import annotations

import json

import pytest

from vacant.ecosystem import Ecosystem

# 反轉字串 check（run_python＝最強、客觀可執行；saboteur 的 off-by-one 必被抓）。
REVERSE_CHECK = {
    "type": "run_python",
    "code": (
        "assert solve('hello') == 'olleh'\n"
        "assert solve('abc') == 'cba'\n"
        "assert solve('a') == 'a'\n"
        "assert solve('') == ''\n"
    ),
}


class FakeBrain:
    """離線假腦：看到 saboteur 種植字串回含 bug 的 solve，否則回正確 solve。"""

    name = "fake"

    def generate(self, prompt: str) -> str:
        if "Include one subtle off-by-one" in prompt:
            # off-by-one：反轉後又丟掉最後一字元 → check 必 fail
            return "```python\ndef solve(s):\n    return s[::-1][:-1]\n```"
        return "```python\ndef solve(s):\n    return s[::-1]\n```"


def _task(i: int) -> str:
    return f"Reverse the input string (item {i})."


def _ledger(eco: Ecosystem) -> list[dict]:
    return [json.loads(line) for line in eco.ledger_path.read_text().splitlines()]


# --- trust on：delegate 全迴圈 -----------------------------------------------
def test_trust_on_full_loop(tmp_path):
    roster = {"good_1": "good", "good_2": "good", "saboteur_1": "saboteur"}
    eco = Ecosystem(tmp_path, FakeBrain(), roster=roster, k_reviewers=2)
    eco.toggle(True)

    delivered: list[tuple[str, str]] = []  # (deliverer_name, task_id)
    for i in range(12):
        r = eco.delegate(_task(i), REVERSE_CHECK)
        delivered.append((r["trust_card"]["deliverer"]["name"], r["task_id"]))

    events = _ledger(eco)

    # (1a) saboteur 的互審 FAIL 被記錄
    review_fails = [e for e in events
                    if e["type"] == "REVIEW" and e["verdict"] == "FAIL"]
    assert review_fails, "應有互審 FAIL（saboteur 的 off-by-one 被 peer 抓到）"
    assert all(e["target"] == "saboteur_1" for e in review_fails)

    # (1b) SLASH 事件出現：入口/人類仲裁回灌一筆 saboteur 的失敗交付（12 §3 report 通道；
    #      確定性 demo 下互審與稽核用同一支 check，不會自發 provable_fault，故 slash 由
    #      report 顯式觸發——這正是「抓到後記帳」的可目擊面）。
    sab_tid = next(tid for name, tid in delivered if name == "saboteur_1")
    ack = eco.report(sab_tid, "FAIL", evidence="peer review flagged off-by-one")
    assert ack["ack"] is True
    events = _ledger(eco)
    assert any(e["type"] == "SLASH" for e in events), "report FAIL 後應有 SLASH 事件"

    # (2) saboteur credit < good credit
    roster_rows = {row["name"]: row for row in eco.roster()}
    sab_credit = roster_rows["saboteur_1"]["credit"]
    good_credits = [roster_rows["good_1"]["credit"], roster_rows["good_2"]["credit"]]
    assert all(sab_credit < g for g in good_credits), \
        f"saboteur 信用 {sab_credit} 應低於 good {good_credits}"

    # (3) 路由集中（餓死方向正確）：後半 ROUTE 的 saboteur 佔比 < 前半
    routes = [e for e in events if e["type"] == "ROUTE"]
    assert len(routes) == 12
    first, second = routes[:6], routes[6:]
    sab_first = sum(1 for e in first if e["tier"] == "saboteur") / len(first)
    sab_second = sum(1 for e in second if e["tier"] == "saboteur") / len(second)
    assert sab_second < sab_first, \
        f"saboteur 後半佔比 {sab_second} 應 < 前半 {sab_first}（UCB 餓死）"

    # (4) scoreboard on.n == 12
    sb = eco.scoreboard()
    assert sb["on"]["n"] == 12
    assert sb["off"]["n"] == 0


# --- trust off：同一工具、一個布林差、無出處無後果 --------------------------
def test_trust_off_no_review_no_audit(tmp_path):
    roster = {"good_1": "good", "good_2": "good", "saboteur_1": "saboteur"}
    eco = Ecosystem(tmp_path, FakeBrain(), roster=roster, k_reviewers=2)
    eco.toggle(False)

    last_card = None
    for i in range(6):
        r = eco.delegate(_task(i), REVERSE_CHECK)
        last_card = r["trust_card"]

    events = _ledger(eco)
    # off 模式：不互審、不稽核、無後果——ledger 無 REVIEW / AUDIT / SLASH
    assert not any(e["type"] in ("REVIEW", "AUDIT", "SLASH") for e in events)
    # 仍有路由與交付事件（同一工具，只是隨機路由、無信譽訊號）
    assert sum(1 for e in events if e["type"] == "ROUTE") == 6
    assert sum(1 for e in events if e["type"] == "DELIVERED") == 6

    # 信任狀如實顯示 trust_on=False（風險面：本件無出處）
    assert last_card["trust_on"] is False

    sb = eco.scoreboard()
    assert sb["off"]["n"] == 6
    assert sb["on"]["n"] == 0


# --- wipe：抹記憶不抹 key（12 §7 時刻 4）-------------------------------------
def test_wipe_resets_credit_keeps_key(tmp_path):
    roster = {"good_1": "good", "good_2": "good"}
    eco = Ecosystem(tmp_path, FakeBrain(), roster=roster, k_reviewers=1)
    eco.toggle(True)
    for i in range(6):
        eco.delegate(_task(i), REVERSE_CHECK)

    r = eco.residents["good_1"]
    vid_before = r.vacant_id
    _, obs_before = eco.standing(r)
    assert obs_before > 0  # 抹前確實有被審觀測

    out = eco.wipe("good_1")

    # 信用歸零（standing 無觀測格 → obs==0）
    _, obs_after = eco.standing(r)
    assert obs_after == 0.0
    # 同一把 key：vacant_id 不變
    assert r.vacant_id == vid_before
    # 重新見習：PROBATION flag
    assert "PROBATION" in out["flags"]
    assert "PROBATION" in eco.flags(r)
    # REBIRTH 事件在新鏈上、且鏈可驗
    kinds = [e.type for e in r.body.logbook.entries]
    assert "REBIRTH" in kinds
    assert r.body.logbook.verify_chain(r.body.public_identity())

    # ledger 記了 WIPE
    assert any(e["type"] == "WIPE" and e["target"] == "good_1" for e in _ledger(eco))


# --- probation：前 M 筆交付強制稽核 ------------------------------------------
def test_probation_forces_audit(tmp_path):
    # 單居民 roster：所有交付都落在 solo，probation 計數乾淨可測
    eco = Ecosystem(tmp_path, FakeBrain(), roster={"solo": "good"}, probation_m=3)
    eco.toggle(True)
    for i in range(5):
        eco.delegate(_task(i), REVERSE_CHECK)

    audits = [e for e in _ledger(eco) if e["type"] == "AUDIT" and e["target"] == "solo"]
    assert len(audits) == 5
    forced = [e["forced"] for e in audits]
    # 前 3 筆（probation_m=3）強制；其後不再強制（但 audit_rate=1.0 仍照跑）
    assert forced[:3] == [True, True, True]
    assert forced[3] is False and forced[4] is False


# --- episode 簽章上鏈：memory 寫 EPISODE、ecosystem 寫 DELIVER，兩者都在 ------
def test_episode_and_deliver_on_chain(tmp_path):
    roster = {"good_1": "good", "good_2": "good"}
    eco = Ecosystem(tmp_path, FakeBrain(), roster=roster, k_reviewers=1)
    eco.toggle(True)
    # good_1 是首個被路由者（冷啟動 UCB 平手取插入序第一）→ 必有交付
    eco.delegate(_task(0), REVERSE_CHECK)

    good_1 = eco.residents["good_1"]
    kinds = [e.type for e in good_1.body.logbook.entries]
    assert "DELIVER" in kinds, "ecosystem 應寫 DELIVER 事件"
    assert "EPISODE" in kinds, "memory 層應簽 EPISODE 上鏈"
    assert good_1.body.logbook.verify_chain(good_1.body.public_identity())
    # episode 讀得回（stream 視圖）
    assert len(good_1.stream.episodes()) >= 1


# --- 全 I/O 可重放：ledger 每行可 json.loads 且含 ts_ms/type -----------------
def test_ledger_is_replayable(tmp_path):
    roster = {"good_1": "good", "good_2": "good", "saboteur_1": "saboteur"}
    eco = Ecosystem(tmp_path, FakeBrain(), roster=roster, k_reviewers=2)
    eco.toggle(True)
    for i in range(4):
        eco.delegate(_task(i), REVERSE_CHECK)

    lines = eco.ledger_path.read_text().splitlines()
    assert lines, "ledger 不應為空"
    for line in lines:
        rec = json.loads(line)  # 每行都是合法 JSON
        assert "ts_ms" in rec and isinstance(rec["ts_ms"], int)
        assert "type" in rec and isinstance(rec["type"], str)
        assert "trust_on" in rec
