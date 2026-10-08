"""Canonical serialization.

Deterministic, platform-stable serialization used for:

* WorldState hashing (invariant I14),
* journal hashing,
* deterministic proposal ordering / transition id assignment.

Python's built-in ``hash()`` is per-process randomized and must never be
used for reproducibility. Everything here is stable text + SHA-256/BLAKE2b.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_token(value: Any) -> str:
    """Encode one scalar value with an explicit type tag.

    The type tag keeps ``1`` (int), ``1.0`` (float) and ``True`` (bool)
    distinct even though Python considers some of them equal.
    """
    if value is None:
        return "n:"
    if isinstance(value, bool):
        return "b:" + ("1" if value else "0")
    if isinstance(value, int):
        return f"i:{value}"
    if isinstance(value, float):
        return f"f:{value!r}"
    if isinstance(value, str):
        return f"s:{value}"
    raise TypeError(f"value of type {type(value).__name__!r} is not canonicalizable")


def canonical_json(obj: Any) -> str:
    """Compact, key-sorted JSON. Input must be lists/strings/numbers/None."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def state_payload(tick: int, data: dict[tuple[str, str], Any]) -> bytes:
    """Canonical bytes of (tick, entities, fields, values).

    Keys are sorted so dict insertion order can never influence the hash.
    """
    entries = [
        [entity, field, canonical_token(value)]
        for (entity, field), value in sorted(data.items())
    ]
    return canonical_json({"tick": tick, "data": entries}).encode("utf-8")
