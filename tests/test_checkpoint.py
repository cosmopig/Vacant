"""V1 存檔點認證＋回溯稽核（18 §2；vacant/checkpoint.py＋ecosystem 整合）。

三條規格判準：①認證可離線驗簽；②竄改窗口內任一 episode → 驗證失敗；
③存檔點鏈斷點可偵測。外加：delegate 同步路徑不簽存檔點（離線作業紀律）、
wipe 收尾認證＋舊鏈歸檔（「記憶沒了，帳還在」）、信任狀事後升級。
"""

from __future__ import annotations

import json

from vacant.checkpoint import (
    issue_checkpoint,
    retro_audit_window,
    verify_checkpoint,
    verify_checkpoint_chain,
)
from vacant.identity import Identity
from vacant.logbook import Logbook
from vacant.memory import Episode, MemoryStream

GOOD = "def solve(s):\n    return s[::-1]"
BAD = "def solve(s):\n    return s"
CHECK = {"type": "run_python", "code": "assert solve('abc') == 'cba'"}


def _stream_with_episodes(n: int, ident: Identity) -> tuple[MemoryStream, dict, dict]:
    """造一條 n 筆 episode 的鏈＋對應 (answers, checks)（retro 原料）。"""
    stream = MemoryStream(Logbook(), ident)
    answers, checks = {}, {}
    for i in range(n):
        tid = f"t{i}"
        ans = GOOD if i % 3 else BAD  # 每三筆一壞（retro 有東西抓）
        answers[tid], checks[tid] = ans, CHECK
        stream.append(Episode(task_id=tid, spec_digest="s", answer_digest="a",
                              outcome="pass", ts_ms=i), ts_ms=i)
    return stream, answers, checks


def test_issue_and_verify_offline():
    """①認證可離線驗簽：簽發 → verify_checkpoint 四關全過；retro 結果如實。"""
    ident = Identity.generate()
    stream, answers, checks = _stream_with_episodes(5, ident)
    eps = [e for e in stream.logbook.entries if e.type == "EPISODE"]
    audits, missing = retro_audit_window(eps, answers, checks)
    assert sum(audits.values()) == 3 and len(audits) == 5 and not missing  # t0,t3 壞
    ckpt = issue_checkpoint(stream.logbook, ident, window=(eps[0].seq, eps[-1].seq),
                            retro_audits=audits, retro_missing=missing,
                            prev_checkpoint=None, ts_ms=99)
    ok, reason = verify_checkpoint(ckpt, stream.logbook)
    assert ok, reason
    assert ckpt["retro_audits"] == audits
    assert ckpt["prev_checkpoint_sig"] is None


def test_tampered_episode_in_window_fails():
    """②竄改窗口內任一 episode → entries_hash 不符 → 驗證失敗（溯及既往）。"""
    ident = Identity.generate()
    stream, answers, checks = _stream_with_episodes(5, ident)
    eps = [e for e in stream.logbook.entries if e.type == "EPISODE"]
    audits, missing = retro_audit_window(eps, answers, checks)
    ckpt = issue_checkpoint(stream.logbook, ident, window=(eps[0].seq, eps[-1].seq),
                            retro_audits=audits, retro_missing=missing,
                            prev_checkpoint=None, ts_ms=99)
    # 竄改窗口中間一筆 episode 的 payload
    victim = stream.logbook.entries[2]
    victim.payload["outcome"] = "TAMPERED"
    ok, reason = verify_checkpoint(ckpt, stream.logbook)
    assert not ok
    assert "entries_hash" in reason


def test_checkpoint_chain_break_detected():
    """③存檔點鏈斷點可偵測：抽掉中間環／嫁接鏈頭都失敗。"""
    ident = Identity.generate()
    stream, answers, checks = _stream_with_episodes(5, ident)
    eps = [e for e in stream.logbook.entries if e.type == "EPISODE"]
    ckpts = []
    prev = None
    for w in range(2):
        ck = issue_checkpoint(stream.logbook, ident, window=(eps[w].seq, eps[w].seq),
                              retro_audits={}, retro_missing=[], prev_checkpoint=prev,
                              ts_ms=w)
        ckpts.append(ck)
        prev = ck
    ok, _ = verify_checkpoint_chain(ckpts)
    assert ok
    # 抽掉第一環（第二枚的 prev 指向不存在的環）
    ok, reason = verify_checkpoint_chain(ckpts[1:])
    assert not ok and "鏈頭被嫁接" in reason
    # 竄改 prev 指針
    forged = dict(ckpts[1], prev_checkpoint_sig="0" * 64)
    ok, _ = verify_checkpoint_chain([ckpts[0], forged])
    assert not ok and "不接續" in _


# --- ecosystem 整合 -----------------------------------------------------------
class _GoodBrain:
    name = "fake-good"

    def generate(self, prompt: str) -> str:
        return f"```python\n{GOOD}\n```"


def _eco(tmp_path, **kw):
    from vacant.ecosystem import Ecosystem
    return Ecosystem(tmp_path, _GoodBrain(),
                     roster={"good_1": "good", "good_2": "good", "good_3": "good"}, **kw)


def test_delegate_never_issues_checkpoint_in_sync_path(tmp_path):
    """離線紀律（16 §B1）：delegate 再多次也不會自動簽存檔點。"""
    eco = _eco(tmp_path)
    for i in range(6):
        eco.delegate(f"Reverse item {i}", CHECK)
    assert not eco.checkpoints_dir.exists() or not list(eco.checkpoints_dir.rglob("ckpt_*.json"))


def test_checkpoint_upgrades_trust_card_and_survives_wipe(tmp_path):
    """事後升級（trust_card.retro_audit）＋ wipe 收尾＋歸檔鏈可離線驗證。"""
    from vacant.checkpoint import DEFAULT_WINDOW_EPISODES
    from vacant.ecosystem import Ecosystem
    # 單居民 roster：20 筆交付全落在同一條 episode 鏈上（滿窗）
    eco = Ecosystem(tmp_path, _GoodBrain(), roster={"solo": "good"})
    tids = []
    for i in range(DEFAULT_WINDOW_EPISODES):  # 打滿一窗
        r = eco.delegate(f"Reverse item {i}", CHECK)
        tids.append(r["task_id"])
    # 交付當下：retro_audit 如實為 null（尚未回溯）
    assert eco.trust_card(tids[0])["retro_audit"] is None
    # 離線簽發 → 信任狀升級
    ckpt = eco.issue_checkpoint("solo")
    assert ckpt is not None
    upgraded = [t for t in tids if eco.trust_card(t)["retro_audit"]]
    assert upgraded, "沒有任何信任狀被事後升級"
    for t in upgraded:
        ra = eco.trust_card(t)["retro_audit"]
        assert ra["checkpoint_seq"] >= 1 and ra["passed"] is True
    # CHECKPOINT 事件入 ledger
    types = [json.loads(x)["type"] for x in eco.ledger_path.read_text().splitlines()]
    assert "CHECKPOINT" in types

    # wipe：收尾存檔點（force）＋舊鏈歸檔——「記憶沒了，帳還在」
    who = eco.trust_card(upgraded[0])["deliverer"]["name"]
    eco.delegate("one more for partial window", CHECK)
    eco.wipe(who)
    r = eco.residents[who]
    archives = list(r.body.trust_dir.glob("logbook.archive-*.ndjson"))
    assert archives, "wipe 未歸檔舊鏈"
    # 歸檔鏈載回後，wipe 前簽發的存檔點仍可離線驗證
    from vacant.logbook import Logbook
    archived = Logbook.load(archives[0])
    all_ckpts = eco._checkpoints_of(who)
    assert all_ckpts
    for _, ck in all_ckpts:
        ok, reason = verify_checkpoint(ck, archived)
        assert ok, reason
    # 存檔點鏈跨 wipe 完整（prev_checkpoint_sig 環環相扣）
    ok, _ = verify_checkpoint_chain([ck for _, ck in all_ckpts])
    assert ok
