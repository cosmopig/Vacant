"""`VacantClient` — the caller-side SDK class.

A thin object wrapper around `protocol.dispatch.call_capability` /
`call_local` that holds the client's keypair + transport + registry
search adapter so callers don't have to pass them on every call.

Usage:

    async with VacantClient.ephemeral(registry_url="http://reg") as cli:
        result = await cli.call_capability("summarize", "please summarize ...")

The class is small (≈100 lines of logic) on purpose: anything the SDK
doesn't expose is intentional — clients are not residents and should
not be reaching into runtime, spawn, or aggregator surfaces.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from vacant.client.transport import (
    AggregationSearch,
    HttpDispatchTransport,
    HttpRegistryAggregationSearch,
)
from vacant.core.crypto import SigningKey, keygen
from vacant.core.errors import CoreError
from vacant.core.types import (
    BehaviorBundle,
    CapabilityCard,
    ResidentForm,
    SubstrateSpec,
    VacantId,
)
from vacant.core.types import Logbook as _Logbook
from vacant.protocol.dispatch import (
    DispatchResult,
    DispatchTransport,
)
from vacant.protocol.dispatch import (
    call_capability as dispatch_call_capability,
)
from vacant.protocol.dispatch import (
    call_local as dispatch_call_local,
)
from vacant.protocol.envelope import A2AMessage, A2APart, SelfEval

__all__ = [
    "VacantCallResult",
    "VacantClient",
    "VacantClientError",
]


class VacantClientError(CoreError):
    """Raised when the SDK can't fulfil a call (no registry, no transport,
    bad payload, etc.)."""


@dataclass(frozen=True)
class VacantCallResult:
    """High-level result of a successful SDK call.

    Hides the lower-level `DispatchResult` shape behind a friendlier
    surface — most SDK users just want `response_text` and `self_eval`,
    not the full envelope chain metadata.

    Attributes:
        response_text: Concatenated `parts[].text` from the response.
        self_eval: The responder vacant's 5D self-assessment +
            confidence, if present. `None` if the response didn't carry
            one (older vacants).
        target_vacant_id: The vacant we ended up calling. Useful for
            metrics + dashboards.
        dispatch: The full underlying `DispatchResult` for callers that
            need envelope-level access (replay store integration, etc.).
    """

    response_text: str
    self_eval: SelfEval | None
    target_vacant_id: VacantId
    dispatch: DispatchResult


class VacantClient:
    """Caller-side SDK over A2A.

    Holds a keypair (ephemeral by default — clients are not residents,
    they have no halo) and a transport pair (discovery via
    `AggregationSearch`; direct A2A POST via `DispatchTransport`).
    """

    def __init__(
        self,
        *,
        signing_key: SigningKey,
        client_form: ResidentForm,
        transport: DispatchTransport,
        aggregation_search: AggregationSearch | None = None,
        owns_transport: bool = False,
    ) -> None:
        self._sk = signing_key
        self._form = client_form
        self._transport = transport
        self._agg = aggregation_search
        self._owns_transport = owns_transport
        self._closed = False

    @property
    def client_vacant_id(self) -> VacantId:
        """The ephemeral pubkey-derived id the SDK uses as caller.

        Exposed for dashboards / debugging; the SDK consumer rarely
        needs it because clients aren't discoverable.
        """
        return self._form.identity

    @classmethod
    def ephemeral(
        cls,
        *,
        registry_url: str | None = None,
        transport: DispatchTransport | None = None,
        aggregation_search: AggregationSearch | None = None,
    ) -> VacantClient:
        """Build a one-off client with a fresh keypair.

        `registry_url` wires up an `HttpRegistryAggregationSearch` for
        you. Pass `aggregation_search=` explicitly to inject a custom
        discovery adapter (e.g. unit tests, in-process aggregation).

        `transport=None` defaults to an `HttpDispatchTransport`. Pass a
        custom one to share an `httpx.AsyncClient` across many clients
        or to inject a test stub.
        """
        sk, vk = keygen()
        vid = VacantId.from_verify_key(vk)
        # Clients don't have logbooks or capability cards — they're not
        # residents. We construct a minimal `ResidentForm` whose
        # `identity` is the only load-bearing field for outgoing calls.
        # ResidentForm requires a BehaviorBundle even though we won't run
        # one (the SDK is caller-side). We construct a no-op bundle so
        # the model invariants are satisfied; nothing in this codebase
        # *executes* it because clients don't accept inbound A2A calls.
        form = ResidentForm(
            identity=vid,
            logbook=_Logbook(),
            behavior_bundle=BehaviorBundle(
                system_prompt="vacant-client (caller-side SDK; not a resident)",
            ),
            substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
            capability_card=_dummy_card_for(vid, sk),
        )
        owns_transport = transport is None
        actual_transport: DispatchTransport = transport or HttpDispatchTransport()
        agg = aggregation_search
        if agg is None and registry_url:
            agg = HttpRegistryAggregationSearch(registry_url=registry_url)
        return cls(
            signing_key=sk,
            client_form=form,
            transport=actual_transport,
            aggregation_search=agg,
            owns_transport=owns_transport,
        )

    async def call_capability(
        self,
        capability_query: str,
        prompt_text: str,
        *,
        self_eval: SelfEval | None = None,
    ) -> VacantCallResult:
        """Discover a vacant via the registry and call it.

        Args:
            capability_query: Free-text capability descriptor used by
                the registry's `search_capability`. The registry picks
                a match; the SDK forwards it without scoring.
            prompt_text: The actual user prompt; wrapped in an
                `A2APart(type="text")`.
            self_eval: Optional client-side 5D self-assessment. Clients
                usually don't have one, but the field is there for
                callers that *are* themselves vacants reaching out.

        Returns:
            `VacantCallResult` carrying response text + responder's
            self-eval.

        Raises:
            VacantClientError: If no `aggregation_search` is configured.
        """
        if self._agg is None:
            raise VacantClientError(
                "call_capability requires an aggregation_search; "
                "pass registry_url= to VacantClient.ephemeral or inject one"
            )
        payload = self._make_payload(prompt_text, self_eval)
        dispatch = await dispatch_call_capability(
            query=capability_query,
            requester=self._form,
            requester_signing_key=self._sk,
            payload=payload,
            transport=self._transport,
            aggregation_search=self._agg,
        )
        return _extract_result(dispatch)

    async def call_local(
        self,
        target_card: CapabilityCard,
        prompt_text: str,
        *,
        self_eval: SelfEval | None = None,
    ) -> VacantCallResult:
        """Direct call against a known `CapabilityCard`.

        Bypasses discovery — useful for owner/parent paths against
        LOCAL-visibility vacants, or for tests that don't want to
        spin up a registry.
        """
        payload = self._make_payload(prompt_text, self_eval)
        dispatch = await dispatch_call_local(
            target_card=target_card,
            requester=self._form,
            requester_signing_key=self._sk,
            payload=payload,
            transport=self._transport,
        )
        return _extract_result(dispatch)

    async def __aenter__(self) -> VacantClient:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close any resources the SDK owns. Idempotent."""
        if self._closed:
            return
        self._closed = True
        if self._owns_transport and isinstance(self._transport, HttpDispatchTransport):
            await self._transport.aclose()

    # --- internals ----------------------------------------------------------

    def _make_payload(self, prompt_text: str, self_eval: SelfEval | None) -> A2AMessage:
        return A2AMessage(
            role="ROLE_USER",
            parts=[A2APart(type="text", text=prompt_text)],
            self_eval=self_eval,
        )


# --- helpers ----------------------------------------------------------------


def _extract_result(dispatch: DispatchResult) -> VacantCallResult:
    """Compress a `DispatchResult` into a `VacantCallResult`."""
    response_env = dispatch.response_envelope
    # Concatenate text parts; vacants usually return one text part but
    # the protocol allows several.
    text = "".join(part.text for part in response_env.payload.parts if part.type == "text")
    return VacantCallResult(
        response_text=text,
        self_eval=response_env.payload.self_eval,
        target_vacant_id=response_env.from_vacant_id,
        dispatch=dispatch,
    )


def _dummy_card_for(vid: VacantId, signing_key: SigningKey) -> CapabilityCard:
    """Build a minimal self-signed `CapabilityCard` for the client.

    The SDK doesn't publish this — it only exists so `ResidentForm`'s
    constructor invariants are satisfied. The card has no `endpoint`,
    so even if someone discovers it they can't call back.
    """
    return CapabilityCard(
        vacant_id=vid,
        capability_text="vacant-client (ephemeral, no endpoint)",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        endpoint="",
    ).signed(signing_key)


# Re-export commonly used types so SDK consumers don't have to drill
# into vacant.protocol / vacant.core for the basics.
__all__ += ["A2AMessage", "A2APart", "CapabilityCard", "SelfEval"]

_ = Awaitable, Callable, Any  # keep mypy/ruff happy for re-exports above
