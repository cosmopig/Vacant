"""可攜簽章憑證 attestation：讓「已驗證」離開 vacant 仍可被獨立核對（P2）。"""

from __future__ import annotations

from vacant import crypto
from vacant.agent import Vacant
from vacant.attest import make_attestation, verify_attestation
from vacant.body import now_ms
from vacant.identity import Identity


def test_attestation_roundtrip_and_answer_binding():
    idn = Identity.generate()
    att = make_attestation(idn, prompt="p", answer="a", check="equals",
                           verified=True, ts_ms=now_ms())
    assert verify_attestation(att)                  # 自洽
    assert verify_attestation(att, answer="a")      # 答案雜湊對得上
    assert not verify_attestation(att, answer="b")  # 換了答案 → 不符


def test_tamper_on_claim_or_sig_detected():
    idn = Identity.generate()
    att = make_attestation(idn, prompt="p", answer="a", check="c", verified=True, ts_ms=1)
    bad_claim = dict(att); bad_claim["verified"] = False
    assert not verify_attestation(bad_claim)        # 竄改 verified
    bad_ans = dict(att); bad_ans["answer_sha256"] = "00" * 32
    assert not verify_attestation(bad_ans)          # 竄改 answer 雜湊
    bad_sig = dict(att); bad_sig["sig"] = "0" * len(att["sig"])
    assert not verify_attestation(bad_sig)          # 偽簽章


def test_impersonation_by_pub_swap_fails():
    idn, other = Identity.generate(), Identity.generate()
    att = make_attestation(idn, prompt="p", answer="a", check="c", verified=True, ts_ms=1)
    # 換成別人的 pub（vacant_id 仍是 idn 的）→ vacant_id 不再由 pub 重算 → 失敗
    bad = dict(att); bad["pub"] = crypto.pub_to_hex(other.pub)
    assert not verify_attestation(bad)


def test_solve_emits_independently_verifiable_attestation():
    class FakeBrain:
        name = "fake"

        def __init__(self) -> None:
            self.n = 0

        def generate(self, prompt: str) -> str:
            self.n += 1
            return "RIGHT" if self.n >= 2 else "WRONG"  # 先錯後對 → verify-fix 救回

    v = Vacant(FakeBrain(), k=3)
    r = v.solve("q", lambda a: a == "RIGHT", check_desc="equals")
    assert r.verified and r.attestation is not None
    assert verify_attestation(r.attestation, answer=r.answer)   # 任何人可獨立驗


def test_no_attestation_without_signing_identity():
    v = Vacant(type("B", (), {"name": "b", "generate": lambda self, p: "x"})(), k=1, sign=False)
    r = v.solve("q", lambda a: True)
    assert r.attestation is None and r.accountable is False
