"""v0.12 memory audit: the streamed state hash keeps the canonical contract.

The materialised algorithm that shipped before the change is copied here
VERBATIM as ``legacy_state_payload`` / ``legacy_state_hash``. It is an
independent reference: the streamed implementation in
``kernel/canonical.py`` is never used to check itself.

Checked, per the v0.12 acceptance conditions:

1. byte sequences, not only final digests: the concatenated stream equals
   the legacy bytes, and the streamed hash equals the legacy digest;
2. empty state, genesis, every tick of the golden reference run, changed
   fields, provenance, every value type, and serialization edge cases;
3. the streamed path never builds the whole payload: ``state.hash()`` does
   not call ``state_payload`` and every streamed chunk stays bounded.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from causal_world import create_world
from causal_world.kernel import canonical
from causal_world.kernel.canonical import (
    canonical_json,
    canonical_token,
    hash_state,
    iter_state_payload,
    state_payload,
)
from causal_world.kernel.state import WorldState
from causal_world.world.rules import get_ruleset

GOLDEN = Path(__file__).parent / "golden" / "v012_reference.json"


# ----------------------------------------------------------- legacy reference
# Verbatim copy of kernel/canonical.py::state_payload and
# kernel/state.py::WorldState.hash as they were BEFORE the streamed change.

def legacy_state_payload(tick, data):
    entries = [
        [entity, field, canonical_token(value)]
        for (entity, field), value in sorted(data.items())
    ]
    return canonical_json({"tick": tick, "data": entries}).encode("utf-8")


def legacy_state_hash(tick, data) -> str:
    return hashlib.sha256(legacy_state_payload(tick, data)).hexdigest()


def streamed_bytes(tick, data) -> bytes:
    return b"".join(iter_state_payload(tick, data))


def assert_same(tick, data):
    legacy = legacy_state_payload(tick, data)
    assert streamed_bytes(tick, data) == legacy
    assert state_payload(tick, data) == legacy
    assert hash_state(tick, data) == hashlib.sha256(legacy).hexdigest()


# ------------------------------------------------------------- edge cases

def test_empty_state_bytes_and_hash():
    assert_same(0, {})
    assert streamed_bytes(0, {}) == b'{"data":[],"tick":0}'


@pytest.mark.parametrize("tick", [0, 1, 19, 10**12, -5])
def test_tick_values(tick):
    assert_same(tick, {("a:1", "f"): 1})


VALUES = [
    None, True, False, 0, 1, -1, 2**80, -(2**70),
    0.0, -0.0, 1.0, 1e16, 1e-300, 1 / 3, float("inf"), float("-inf"),
    float("nan"),
    "", "plain", 'quote"and\\backslash', "\n\t\r\x00\x1f\x7f",
    "ünïcödé — ж 中文", "\u2028\u2029", "emoji 🌍", "\ud800 lone surrogate",
    "s:looks-like-a-tag", "n:", "b:1",
]


@pytest.mark.parametrize("value", VALUES, ids=[repr(v)[:24] for v in VALUES])
def test_every_value_type_and_escape(value):
    assert_same(3, {("cell:x", "value"): value})


def test_type_tags_stay_distinct():
    # 1, 1.0 and True compare equal in Python but must hash differently.
    hashes = {hash_state(0, {("e", "f"): v}) for v in (1, 1.0, True)}
    assert len(hashes) == 3
    assert hash_state(0, {("e", "f"): 0.0}) != hash_state(0, {("e", "f"): -0.0})


def test_escaped_names_match():
    data = {
        ("agent:quote\"x", "field\\y"): 1,
        ("cell:ünï", "🌍"): "v",
        ("agent:\ud800", "f"): None,
        ("", ""): 0,
    }
    assert_same(7, data)


def test_key_order_is_sorted_not_insertion():
    a = {("b", "x"): 1, ("a", "y"): 2, ("a", "x"): 3}
    b = {("a", "x"): 3, ("a", "y"): 2, ("b", "x"): 1}
    assert_same(0, a)
    assert hash_state(0, a) == hash_state(0, b)


def test_changed_value_changes_hash():
    base = {("agent:1", "hunger"): 0.5}
    assert hash_state(4, base) != hash_state(4, {("agent:1", "hunger"): 0.5000001})
    assert hash_state(4, base) != hash_state(5, base)


def test_non_canonical_value_raises_in_both_paths():
    data = {("e", "f"): [1, 2]}
    with pytest.raises(TypeError):
        legacy_state_payload(0, data)
    with pytest.raises(TypeError):
        streamed_bytes(0, data)
    with pytest.raises(TypeError):
        hash_state(0, data)


# ------------------------------------------------- batch boundary behaviour

@pytest.mark.parametrize("n", [1, 2, 8191, 8192, 8193, 16384, 16385])
def test_batch_boundaries(n):
    data = {(f"cell:{i:06d}", "v"): i for i in range(n)}
    assert_same(2, data)


def test_chunks_are_bounded_and_ascii():
    data = {(f"agent:{i:07d}", "hunger"): i * 0.25 for i in range(50_000)}
    chunks = list(iter_state_payload(9, data))
    assert len(chunks) > 1
    # one batch of 8192 entries of this shape is ~0.4 MB; the whole payload
    # for 50k pairs is ~2.5 MB. No single chunk may hold the whole payload.
    total = sum(len(c) for c in chunks)
    assert max(len(c) for c in chunks) * 4 < total
    assert all(c.isascii() for c in chunks)
    assert b"".join(chunks) == legacy_state_payload(9, data)


# --------------------------------------------------------------- provenance

def test_provenance_is_not_part_of_the_state_hash():
    state = WorldState(tick=2)
    with state.unsealed():
        state.set("agent:1", "hunger", 0.5, transition_id=10)
        state.set("agent:1", "alive", True, transition_id=11)
    before = state.hash()
    with state.unsealed():
        state.set("agent:1", "hunger", 0.5, transition_id=999)
    assert state.hash() == before
    assert state.hash() == legacy_state_hash(state.tick, state.data)


# ----------------------------------------------------- real states: genesis

def test_genesis_state_matches_legacy():
    sim = create_world(seed=7, ruleset=get_ruleset("player_resettle"),
                       ticks=0, regions=2, agents=200)
    state = sim.state
    assert state.hash() == legacy_state_hash(state.tick, state.data)
    assert_same(state.tick, state.data)


# ------------------------------------------- every tick of the golden run

def test_every_golden_tick_matches_legacy_bytes():
    golden = json.loads(GOLDEN.read_text())
    config = golden["config"]
    sim = create_world(seed=config["seed"], ruleset=get_ruleset(config["ruleset"]),
                       ticks=0, regions=config["regions"], agents=config["agents"])
    recorded = {row["tick"]: row["state_hash"] for row in golden["ticks"]}
    seen = 0
    for step in range(config["ticks"] + 1):
        if step:
            sim.step()
        state = sim.state
        assert_same(state.tick, state.data)
        assert state.hash() == recorded[state.tick]  # the shipped contract
        seen += 1
    assert seen == config["ticks"] + 1


# ------------------------------------------------ no materialisation on hash

def test_state_hash_does_not_materialise_the_payload(monkeypatch):
    state = WorldState(tick=1)
    with state.unsealed():
        for i in range(2000):
            state.set(f"agent:{i}", "hunger", float(i), transition_id=i)

    def forbidden(*_a, **_k):
        raise AssertionError("state.hash() must not build state_payload()")

    monkeypatch.setattr(canonical, "state_payload", forbidden)
    digest = state.hash()  # the streamed path is used
    monkeypatch.undo()
    assert digest == legacy_state_hash(state.tick, state.data)
