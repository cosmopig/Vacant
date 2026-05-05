"""Error hierarchy for `vacant.identity`."""

from __future__ import annotations

from vacant.core.errors import CoreError


class IdentityError(CoreError):
    """Base class for `vacant.identity` errors."""


class KeyVaultError(IdentityError):
    """The vault could not satisfy a `store / load / delete` operation."""


class KeyNotFoundError(KeyVaultError):
    """The requested `key_id` is absent from the vault."""


class KeyRevokedError(IdentityError):
    """A revoked key was used (or attempted to be used) for signing."""


class LayerPromotionError(IdentityError):
    """An L0 → L1 → L2 → L3 promotion failed an invariant check."""


class AttestationError(IdentityError):
    """A peer attestation failed signature, freshness, or revocation checks."""


class FederationError(IdentityError):
    """A federated attestation failed M-of-N verification or rotation."""
