"""Cover the substrate base contract so coverage doesn't dip."""

from __future__ import annotations

import pytest

from vacant.substrate import SubstrateBackend, SubstrateRequest, SubstrateResponse
from vacant.substrate.errors import SubstrateError


def test_substrate_request_response_models() -> None:
    req = SubstrateRequest(system_prompt="be honest", user_prompt="hi")
    assert req.tools == []
    res = SubstrateResponse(text="hello", model_id="mock")
    assert res.usage == {}


def test_substrate_backend_is_abstract() -> None:
    with pytest.raises(TypeError):
        SubstrateBackend()  # type: ignore[abstract]


def test_substrate_error_is_subclass_of_core() -> None:
    from vacant.core.errors import CoreError

    assert issubclass(SubstrateError, CoreError)


@pytest.mark.asyncio
async def test_deterministic_substrate_canned_hit_and_miss() -> None:
    from vacant.substrate.deterministic import DeterministicSubstrate, _prompt_key

    req = SubstrateRequest(system_prompt="sys", user_prompt="hello-world")
    key = _prompt_key(req)
    sub = DeterministicSubstrate(canned={key: "canned answer"}, model_label="d-x")
    assert sub.name == "deterministic:d-x"

    hit = await sub.infer(req)
    assert hit.text == "canned answer"
    assert hit.proof == {"prompt_hash": key, "canned_hit": True}
    assert hit.model_id == "d-x"
    assert hit.usage["input_tokens"] == len("hello-world")

    miss = await DeterministicSubstrate().infer(req)
    assert miss.proof["canned_hit"] is False
    assert miss.text.startswith("[det-1#")
