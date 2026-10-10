"""Validation interfaces.

The kernel itself never hardcodes world rules (spec §13.4). World-specific
invariants (``food_stock >= 0`` etc.) live in a ``WorldRuleValidator``
implementation supplied by the ruleset.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from causal_world.kernel.transition import Transition

if TYPE_CHECKING:  # pragma: no cover
    from causal_world.kernel.snapshot import Snapshot


class WorldRuleValidator(ABC):
    """Pluggable world-law validator.

    Implementations must be pure and deterministic: given the same
    transition and snapshot they must return the same list of violations.
    """

    #: Version of the world rules. Changing rules changes the fingerprint.
    ruleset_version: str = "0.0.0"

    #: Version of the addressable RNG scheme.
    rng_version: str = "blake2b-v1"

    #: Random purposes declared by this ruleset: name -> description.
    purposes: dict[str, str] = {}

    @abstractmethod
    def validate_transition(
        self, transition: Transition, snapshot: "Snapshot"
    ) -> list[str]:
        """Return a list of violation messages (empty list = valid)."""

    def field_type(self, field_name: str) -> type | None:
        """Declared type of a field, or None when the field is unknown.

        The resolver rejects writes to unknown fields and writes whose new
        value type does not match exactly (spec §13.3). A ruleset that
        declares no schema rejects every write — schemas are mandatory.
        """
        return None
