"""Error hierarchy for `vacant.protocol`."""

from __future__ import annotations

from vacant.core.errors import CoreError


class ProtocolError(CoreError):
    """Base class for `vacant.protocol` errors."""


class EnvelopeSignatureError(ProtocolError):
    """Envelope signature failed to verify against the claimed sender."""


class EnvelopeFormatError(ProtocolError):
    """Envelope is malformed (wrong shape, missing fields, etc.)."""


class UnsupportedHaloVersionError(ProtocolError):
    """Capability card halo_version is unknown to this build."""


class ReplayDetectedError(ProtocolError):
    """An incoming envelope was a replay (sequence_no <= last seen)."""


class ChainForkError(ProtocolError):
    """An incoming envelope's prev_envelope_hash does not match the
    stored per-pair chain tip."""


class TargetUnavailableError(ProtocolError):
    """Target vacant cannot accept calls (SUNK / ARCHIVED / HIBERNATING)."""


class TargetNotFoundError(ProtocolError):
    """Target vacant has no capability card / no endpoint."""
