"""P6 — protocol: envelope, dispatch, MCP bridge, replay protect."""

from vacant.protocol.capability_card import (
    MAX_SUPPORTED_HALO_VERSION,
    MIN_SUPPORTED_HALO_VERSION,
    deserialize,
    serialize,
)
from vacant.protocol.dispatch import (
    DispatchResult,
    DispatchTransport,
    build_envelope,
    call_capability,
    call_local,
    make_httpx_transport,
)
from vacant.protocol.envelope import (
    A2A_VACANT_METADATA_KEY,
    A2AMessage,
    A2APart,
    VacantEnvelope,
    from_a2a_jsonrpc,
    to_a2a_jsonrpc,
)
from vacant.protocol.errors import (
    ChainForkError,
    EnvelopeFormatError,
    EnvelopeSignatureError,
    ProtocolError,
    ReplayDetectedError,
    TargetNotFoundError,
    TargetUnavailableError,
    UnsupportedHaloVersionError,
)
from vacant.protocol.mcp_adapter import (
    MCPClientSubstrate,
    MCPTransport,
    VacantAsMCPServer,
)
from vacant.protocol.replay_protect import (
    InMemoryReplayStore,
    PairKey,
    ReplayState,
    ReplayStore,
    SqliteReplayStore,
    check_envelope,
)
from vacant.protocol.serve import (
    BehaviorHandler,
    build_a2a_app,
    build_a2a_router,
    make_response_envelope,
)

__all__ = [
    "A2A_VACANT_METADATA_KEY",
    "MAX_SUPPORTED_HALO_VERSION",
    "MIN_SUPPORTED_HALO_VERSION",
    "A2AMessage",
    "A2APart",
    "BehaviorHandler",
    "ChainForkError",
    "DispatchResult",
    "DispatchTransport",
    "EnvelopeFormatError",
    "EnvelopeSignatureError",
    "InMemoryReplayStore",
    "MCPClientSubstrate",
    "MCPTransport",
    "PairKey",
    "ProtocolError",
    "ReplayDetectedError",
    "ReplayState",
    "ReplayStore",
    "SqliteReplayStore",
    "TargetNotFoundError",
    "TargetUnavailableError",
    "UnsupportedHaloVersionError",
    "VacantAsMCPServer",
    "VacantEnvelope",
    "build_a2a_app",
    "build_a2a_router",
    "build_envelope",
    "call_capability",
    "call_local",
    "check_envelope",
    "deserialize",
    "from_a2a_jsonrpc",
    "make_httpx_transport",
    "make_response_envelope",
    "serialize",
    "to_a2a_jsonrpc",
]
