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
