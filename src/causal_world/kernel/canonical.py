"""Canonical serialization.

Deterministic, platform-stable serialization used for:

* WorldState hashing (invariant I14),
* journal hashing,
* deterministic proposal ordering / transition id assignment,
* persisted transition payloads.

Python's built-in ``hash()`` is per-process randomized and must never be
used for reproducibility. Everything here is stable text + SHA-256/BLAKE2b.
"""

from __future__ import annotations

import hashlib
import json
from json.encoder import encode_basestring_ascii as _encode_ascii
from typing import Any, Iterator


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


def parse_canonical_token(token: str) -> Any:
    """Inverse of :func:`canonical_token`."""
    tag, _, rest = token.partition(":")
    if tag == "n":
        return None
    if tag == "b":
        return rest == "1"
    if tag == "i":
        return int(rest)
    if tag == "f":
        return float(rest)
    if tag == "s":
        return rest
    raise ValueError(f"unknown canonical token tag {tag!r}")


def canonical_json(obj: Any) -> str:
    """Compact, key-sorted JSON. Input must be lists/strings/numbers/None."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def state_payload(tick: int, data: dict[tuple[str, str], Any]) -> bytes:
    """Canonical bytes of (tick, entities, fields, values) — materialised.

    Keys are sorted so dict insertion order can never influence the hash.

    This builds the whole entry list and the whole JSON string in memory.
    It is kept as the explicit, materialised form of the contract (and as
    the reference the streamed form is tested against). State hashing does
    NOT use it: see :func:`hash_state`.
    """
    entries = [
        [entity, field, canonical_token(value)]
        for (entity, field), value in sorted(data.items())
    ]
    return canonical_json({"tick": tick, "data": entries}).encode("utf-8")


# ----------------------------------------------------------------------
# Streamed form (v0.12 memory audit).
#
# The bytes below are EXACTLY ``state_payload(tick, data)``: the object
# ``{"data": [...], "tick": N}`` with sorted keys, compact separators and
# ASCII-escaped strings (json.dumps defaults). The difference is only how
# they are produced: entries are encoded in bounded batches and fed to
# sha256 as they are built, so no full entry list, no full JSON string and
# no full bytes object ever exists. Peak Python allocation is O(batch),
# not O(pairs). tests/test_v012_streamed_hash.py holds the old function as
# an independent reference and compares the byte streams.
# ----------------------------------------------------------------------

_STREAM_BATCH = 8192


def iter_state_payload(tick: int, data: dict[tuple[str, str], Any]) -> Iterator[bytes]:
    """Yield the canonical state payload in bounded ASCII chunks.

    Concatenating the chunks gives :func:`state_payload` byte for byte.
    The only per-pair intermediate is the sorted key list (references,
    8 bytes per pair); values are canonicalised one at a time.
    """
    yield b'{"data":['
    batch: list[str] = []
    first = True
    for key in sorted(data):
        entity, field = key
        token = canonical_token(data[key])
        piece = (
            ('["' + _escape(entity) + '","' + _escape(field)
             + '","' + _escape(token) + '"]')
        )
        batch.append(piece if first else "," + piece)
        first = False
        if len(batch) >= _STREAM_BATCH:
            yield "".join(batch).encode("ascii")
            batch.clear()
    if batch:
        yield "".join(batch).encode("ascii")
    yield ('],"tick":' + json.dumps(tick) + "}").encode("ascii")


def hash_state(tick: int, data: dict[tuple[str, str], Any]) -> str:
    """sha256 of :func:`state_payload`, computed without materialising it."""
    hasher = hashlib.sha256()
    for chunk in iter_state_payload(tick, data):
        hasher.update(chunk)
    return hasher.hexdigest()


def _escape(text: str) -> str:
    # encode_basestring_ascii is the C routine json.dumps uses for strings
    # with ensure_ascii=True; [1:-1] strips the surrounding quotes.
    return _encode_ascii(text)[1:-1]
