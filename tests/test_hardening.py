"""Production 硬化驗收：原子寫入、並發鎖、輸入驗證、金鑰加密、solve 容錯。"""

from __future__ import annotations

import pytest

from vacant.atomic import atomic_write_bytes, atomic_write_text, file_lock
from vacant.body import now_ms
from vacant.envelope import Envelope, MAX_BODY_BYTES
from vacant.identity import Identity
from vacant.logbook import Logbook, MAX_PAYLOAD_BYTES


# --- 原子寫入 ---------------------------------------------------------------
def test_atomic_write_roundtrip_no_tmp_left(tmp_path):
    p = tmp_path / "x" / "f.txt"
    atomic_write_text(p, "hello")
    assert p.read_text() == "hello"
    atomic_write_text(p, "world")          # 覆寫
    assert p.read_text() == "world"
    # 不留暫存檔
    assert not list(tmp_path.rglob("*.tmp*"))


def test_atomic_write_bytes(tmp_path):
    p = tmp_path / "b.bin"
    atomic_write_bytes(p, b"\x00\x01\x02")
    assert p.read_bytes() == b"\x00\x01\x02"


# --- 並發鎖（同程序 reentrant 不適用；測互斥語意的取得/釋放）---------------
def test_file_lock_acquire_release(tmp_path):
    lp = tmp_path / ".lock"
    with file_lock(lp):
        pass
    with file_lock(lp):  # 釋放後可再取
        pass


# --- logbook payload 上限 + 原子 save 後仍可驗 -----------------------------
def test_logbook_payload_cap():
    idn = Identity.generate()
    lb = Logbook()
    with pytest.raises(ValueError):
        lb.append("X", {"big": "a" * (MAX_PAYLOAD_BYTES + 10)}, idn, ts_ms=now_ms())


def test_logbook_atomic_save_still_verifies(tmp_path):
    from vacant.identity import PublicIdentity
    idn = Identity.generate()
    lb = Logbook()
    for i in range(3):
        lb.append("INFERENCE", {"i": i}, idn, ts_ms=now_ms() + i)
    lb.save(tmp_path / "lb.ndjson")
    lb2 = Logbook.load(tmp_path / "lb.ndjson")
    assert lb2.verify_chain(PublicIdentity(idn.vacant_id, idn.pub))
    assert [e.seq for e in lb2.entries] == [1, 2, 3]


# --- Envelope 輸入驗證（不可信邊界）----------------------------------------
def _good(sender):
    return Envelope.create(sender, to="bob", seq=1, prev_hash="0" * 64, ts_ms=now_ms(),
                           kind="call", body={"x": 1}).to_json()


def test_envelope_from_json_rejects_malformed():
    s = Identity.generate()
    base = _good(s)
    # 缺欄位
    d = dict(base); del d["sig"]
    with pytest.raises(ValueError):
        Envelope.from_json(d)
    # seq 非整數
    d = dict(base); d["seq"] = "1"
    with pytest.raises(ValueError):
        Envelope.from_json(d)
    # prev_hash 非 64-hex
    d = dict(base); d["prev_hash"] = "zz"
    with pytest.raises(ValueError):
        Envelope.from_json(d)
    # sig 非 hex
    d = dict(base); d["sig"] = "nothex!!"
    with pytest.raises(ValueError):
        Envelope.from_json(d)
    # body 過大
    d = dict(base); d["body"] = {"blob": "a" * (MAX_BODY_BYTES + 100)}
    with pytest.raises(ValueError):
        Envelope.from_json(d)


def test_envelope_from_json_accepts_good():
    s = Identity.generate()
    env = Envelope.from_json(_good(s))
    from vacant.identity import PublicIdentity
    assert env.verify_sig(PublicIdentity(s.vacant_id, s.pub))


# --- 金鑰靜態加密（passphrase）---------------------------------------------
def test_private_key_passphrase_encryption(tmp_path):
    idn = Identity.generate()
    idn.save(tmp_path / "id", passphrase=b"correct horse")
    # 正確 passphrase 載得回
    again = Identity.load(tmp_path / "id", passphrase=b"correct horse")
    assert again.vacant_id == idn.vacant_id
    # 無 passphrase / 錯誤 → 失敗
    with pytest.raises(Exception):
        Identity.load(tmp_path / "id")
    with pytest.raises(Exception):
        Identity.load(tmp_path / "id", passphrase=b"wrong")


# --- Vacant.solve 對崩潰的腦容錯 -------------------------------------------
def test_vacant_solve_survives_crashing_brain():
    from vacant.agent import Vacant

    class CrashBrain:
        name = "crash"
        def generate(self, prompt):
            raise RuntimeError("boom")

    v = Vacant(CrashBrain(), k=3)
    r = v.solve("anything", verifier=lambda a: a == "RIGHT")  # 不該拋例外
    assert r.verified is False
    assert r.accountable is True   # 即使腦崩，簽章鏈仍完整可驗


# --- 跨重啟的防重放（持久化 ingress guard）---------------------------------
def test_replay_guard_persists_across_restart(tmp_path):
    from vacant.envelope import ReplayError
    from vacant.gateway import Gateway
    from vacant.host import Host
    from vacant.substrate import EchoSubstrate
    from vacant.tasks import make_task

    h = Host(tmp_path, substrate=EchoSubstrate(p_base=1.0))
    req = h.mint("requester", niches=[])
    h.mint("expert", niches=["reverse"])
    task = make_task(0, "reverse")
    req.call("reverse", task)  # expert ingress 接受 seq=1 並持久化 guard

    # 模擬 host 重啟：全新 Gateway（會從信任庫載回 ingress guard）
    expert2 = Gateway("expert", h.vacant_id("expert"), tmp_path, h.waker, h.registry)
    body = h.body("requester")
    replay = Envelope.create(
        body.identity, to=h.vacant_id("expert"), seq=1, prev_hash="0" * 64, ts_ms=now_ms(),
        kind="call", body={"prompt": task["prompt"], "task_id": task["task_id"], "niche": "reverse", "input": task["input"]},
    )
    with pytest.raises(ReplayError):   # 重啟後仍擋住 seq=1 重放
        expert2.ingress(replay)
