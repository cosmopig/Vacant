"""通用驗證器（`vacant_network/genverify.py`）：三值、確定性優先、token 上限。"""
from vacant_network import genverify as gv
from vacant_network.genverify import ACCEPTED, REJECTED, UNKNOWN, Criterion, JudgeResult, Spec


def test_unknown_is_never_accepted():
    assert gv.aggregate([ACCEPTED, UNKNOWN]) == UNKNOWN
    assert gv.aggregate([ACCEPTED, REJECTED, UNKNOWN]) == REJECTED
    assert gv.aggregate([ACCEPTED, ACCEPTED]) == ACCEPTED
    assert gv.aggregate([]) == UNKNOWN  # 沒有準則 ⇒ 沒有東西被驗過


def test_numbers_supported_only_rejects_or_unknown():
    sp = Spec("t", [], sources={"s": "Revenue was 1,250 in 2023."})
    v, _ = gv.chk_numbers_supported("Revenue was 1250 in 2023.", {}, sp)
    assert v == UNKNOWN  # 全部找得到 ≠ 有根據
    v, ev = gv.chk_numbers_supported("Revenue was 1300 in 2023.", {}, sp)
    assert v == REJECTED and "1300" in ev


def test_extractive_never_rejects():
    sp = Spec("t", [], sources={"s": "the cat sat on the mat today"})
    assert gv.chk_extractive("the cat sat on the mat", {"min_ratio": 0.9}, sp)[0] == ACCEPTED
    assert gv.chk_extractive("a dog ran far away quickly", {"min_ratio": 0.9}, sp)[0] == UNKNOWN


def _judge(verdict, quote=None, tokens=100):
    calls = []

    def f(spec, out, crits):
        calls.append([c.id for c in crits])
        return {c.id: JudgeResult(verdict, tokens, quote=quote) for c in crits}
    return f, calls


def test_deterministic_first_judge_only_for_residual():
    sp = Spec("t", [Criterion("w", "check", "word_count", {"relation": "at most", "n": 10}),
                    Criterion("tone", "judge", question="Is it polite?")])
    j, calls = _judge(ACCEPTED)
    r = gv.evaluate(sp, "hello there", j)
    assert calls == [["tone"]] and r["verdict"] == ACCEPTED and r["judge_tokens"] == 100


def test_short_circuit_spends_zero_tokens_after_deterministic_reject():
    sp = Spec("t", [Criterion("w", "check", "word_count", {"relation": "at most", "n": 1}),
                    Criterion("tone", "judge", question="Is it polite?")])
    j, calls = _judge(ACCEPTED)
    r = gv.evaluate(sp, "hello there friend", j)
    assert r["verdict"] == REJECTED and calls == [] and r["judge_tokens"] == 0


def test_token_cap_is_enforced_before_the_call():
    sp = Spec("t", [Criterion("tone", "judge", question="Is it polite?")], judge_token_cap=5,
              sources={"s": "x" * 400})
    j, calls = _judge(ACCEPTED)
    r = gv.evaluate(sp, "hello", j)
    assert calls == [] and r["verdict"] == UNKNOWN and r["judge_skipped"] == "over_token_cap"


def test_require_quote_downgrades_unverifiable_judgement():
    sp = Spec("t", [Criterion("f", "judge", question="Supported?")],
              sources={"s": "Paris is the capital of France."})
    j, _ = _judge(REJECTED, quote="Berlin is lovely")
    assert gv.evaluate(sp, "Paris is the capital of Italy.", j,
                       require_quote=True)["verdict"] == UNKNOWN
    j, _ = _judge(REJECTED, quote="capital of Italy")
    assert gv.evaluate(sp, "Paris is the capital of Italy.", j,
                       require_quote=True)["verdict"] == REJECTED


def test_no_judge_leaves_judge_criteria_unknown():
    sp = Spec("t", [Criterion("tone", "judge", question="Polite?")])
    r = gv.evaluate(sp, "hi", None)
    assert r["verdict"] == UNKNOWN and r["judge_skipped"] == "no_judge"


def test_spec_hash_depends_on_criteria_and_sources():
    a = Spec("t", [Criterion("w", "check", "word_count", {"relation": "at most", "n": 5})])
    b = Spec("t", [Criterion("w", "check", "word_count", {"relation": "at most", "n": 6})])
    c = Spec("t", a.criteria, sources={"s": "x"})
    assert len({a.sha256(), b.sha256(), c.sha256()}) == 3
    assert a.sha256() == Spec("t", list(a.criteria)).sha256()


def test_basic_checks():
    assert gv.chk_json_parses('```json\n{"a":1}\n```', {}, None)[0] == ACCEPTED
    assert gv.chk_json_parses("{a:1}", {}, None)[0] == REJECTED
    assert gv.chk_forbids("I love Cats", {"keywords": ["cat"]}, None)[0] == ACCEPTED
    assert gv.chk_forbids("I love cat", {"keywords": ["cat"]}, None)[0] == REJECTED
    assert gv.chk_case("abc def", {"case": "lower"}, None)[0] == ACCEPTED
    assert gv.chk_regex_count("* a\n* b\n", {"pattern": r"^\s*\*\s", "relation": "exactly",
                                             "n": 2}, None)[0] == ACCEPTED


def test_screen_criterion_only_vetoes():
    """反證型檢查：沒找到反證不擋 accepted；找到反證一票否決。"""
    sp = Spec("t", [Criterion("n", "check", "numbers_supported", screen=True),
                    Criterion("w", "check", "word_count", {"relation": "at most", "n": 10})],
              sources={"s": "It cost 1500 dollars."})
    assert gv.evaluate(sp, "It cost 1500 dollars.")["verdict"] == ACCEPTED
    assert gv.evaluate(sp, "It cost 1700 dollars.")["verdict"] == REJECTED
