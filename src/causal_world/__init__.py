"""Deterministic Causal World Simulation Engine.

Layers (bottom-up):

    KERNEL      WorldState, Snapshot, Transition, StateRead, StateChange,
                RandomDraw, RandomSource, validation primitives.
    SYSTEMS     ClimateSystem, AgricultureSystem, DiseaseSystem, AgentSystem.
    SIMULATION  Snapshot -> Plan -> Resolve -> Commit -> Index tick loop.
    CAUSAL      Transition history, provenance index, reverse dependencies.
    OBSERVER    Read-only derived views: EventView, statistics, observability.

The kernel contains no narrative semantics. Events, biographies and
statistics are derived representations built on top of the transition
journal and the causal index.
"""

from __future__ import annotations

__version__ = "0.1.0"  # kernel_version used in run fingerprints

KERNEL_VERSION = __version__

from causal_world.simulation.engine import Simulation, create_world  # noqa: E402

__all__ = ["__version__", "KERNEL_VERSION", "Simulation", "create_world"]
