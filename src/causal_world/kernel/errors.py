"""Kernel error types.

These exceptions guard the hard invariants of the kernel. They are raised
on *misuse* of the primitives (e.g. mutating sealed state directly, drawing
from an undeclared random purpose, reading a field that does not exist).
"""

from __future__ import annotations


class KernelError(Exception):
    """Base class for all kernel-level invariant violations."""


class SealedStateError(KernelError):
    """WorldState was mutated outside of a committed transition.

    Invariant I1: WorldState changes only through committed transitions.
    """


class SnapshotError(KernelError):
    """Attempted to mutate or misuse an immutable Snapshot."""


class UnknownPurposeError(KernelError):
    """A random draw was requested for a purpose not in the registry.

    Purposes are part of the world rules; undeclared randomness is forbidden.
    """


class MissingFieldError(KernelError):
    """A system tried to read an (entity, field) that is not in the snapshot."""


class BuilderError(KernelError):
    """Invalid use of a TransitionBuilder."""


class GenesisError(KernelError):
    """The genesis (initial state) transitions failed to validate/commit."""
