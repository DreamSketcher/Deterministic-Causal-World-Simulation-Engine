"""Addressable deterministic randomness.

Invariant I7: a draw depends only on (world_seed, rng_version, tick, entity,
purpose, index). Invariant I8: it never depends on call order, on how many
other entities exist, or on any sequential RNG stream.

There is NO global RNG state. Every draw is a pure function of its context
keyed through BLAKE2b. ``random.random()`` and sequential generators are
banned inside the simulation (spec §29).
"""

from __future__ import annotations

from hashlib import blake2b

from causal_world.kernel.errors import UnknownPurposeError


class PurposeRegistry:
    """The set of random purposes declared by the world rules.

    A purpose is part of the ruleset: adding/removing purposes or changing
    their semantics is a ruleset change (spec §9).
    """

    def __init__(self) -> None:
        self._purposes: dict[str, str] = {}

    def declare(self, purpose: str, description: str = "") -> None:
        self._purposes[purpose] = description

    def require(self, purpose: str) -> None:
        if purpose not in self._purposes:
            raise UnknownPurposeError(
                f"random purpose {purpose!r} is not declared in the ruleset"
            )

    def __contains__(self, purpose: str) -> bool:
        return purpose in self._purposes

    def declared(self) -> list[str]:
        return sorted(self._purposes)


class RandomSource:
    """Stateless, addressable deterministic random source."""

    def __init__(
        self,
        world_seed: int,
        rng_version: str,
        purposes: PurposeRegistry | None = None,
    ) -> None:
        self.world_seed = int(world_seed)
        self.version = rng_version
        self.purposes = purposes

    def draw(self, tick: int, entity: str, purpose: str, index: int = 0) -> float:
        """Return a deterministic float in [0, 1) for this exact context.

        The same arguments always give the same value for a given seed and
        rng_version, regardless of what else is drawn, in which order, or
        whether other entities exist at all.
        """
        if self.purposes is not None:
            self.purposes.require(purpose)
        payload = (
            f"causal-world-rng|{self.version}|seed={self.world_seed}|"
            f"tick={tick}|entity={entity}|purpose={purpose}|index={index}"
        ).encode("utf-8")
        digest = blake2b(payload, digest_size=8).digest()
        return int.from_bytes(digest, "big") / float(1 << 64)
