"""Deterministic replay: same seed + versions + initial state = same run
(spec §36, invariant I14)."""

from __future__ import annotations

from causal_world import create_world
from causal_world.causal.trace import trace_back, trace_record
from causal_world.kernel.transition import TransitionStatus
from causal_world.world.rules import DefaultWorldRules


def test_replay_state_and_journal_identical():
    sim1 = create_world(seed=42, ticks=100)
    sim2 = create_world(seed=42, ticks=100)

    assert sim1.state.hash() == sim2.state.hash()
    assert sim1.journal.hash() == sim2.journal.hash()
    assert sim1.state.data == sim2.state.data
    assert sim1.state.provenance == sim2.state.provenance


def test_fingerprints_identical_on_replay():
    f1 = create_world(seed=42, ticks=100).fingerprint()
    f2 = create_world(seed=42, ticks=100).fingerprint()
    assert f1 == f2
    assert f1["initial_state_hash"] == f2["initial_state_hash"]
    assert f1["final_state_hash"] == f2["final_state_hash"]


def test_causal_traces_identical_on_replay():
    sim1 = create_world(seed=42, ticks=100)
    sim2 = create_world(seed=42, ticks=100)

    traced = 0
    for t1 in sim1.journal.committed():
        if t1.operation in ("disease.infect", "agent.death"):
            node1 = trace_back(sim1.index, t1.id, depth=6)
            node2 = trace_back(sim2.index, t1.id, depth=6)
            assert trace_record(node1) == trace_record(node2)
            traced += 1
    assert traced >= 1, "the seed-42 world must contain traceable events"


def test_initial_state_hash_is_reproducible():
    sim1 = create_world(seed=7)
    sim2 = create_world(seed=7)
    assert sim1.initial_state_hash == sim2.initial_state_hash
    assert sim1.initial_state_hash is not None


def test_different_seeds_diverge():
    f1 = create_world(seed=1, ticks=60).fingerprint()
    f2 = create_world(seed=2, ticks=60).fingerprint()
    assert f1["final_state_hash"] != f2["final_state_hash"]


def test_same_seed_different_ruleset_version_is_distinguishable():
    class RenamedRules(DefaultWorldRules):
        ruleset_version = "0.2.0"

    f_old = create_world(seed=42, ticks=10).fingerprint()
    f_new = create_world(seed=42, ticks=10, ruleset=RenamedRules()).fingerprint()
    assert f_old["ruleset_version"] != f_new["ruleset_version"]
    assert f_old["final_state_hash"] == f_new["final_state_hash"], (
        "renaming the ruleset without changing laws keeps physics identical"
    )


def test_rng_version_change_changes_physics():
    class V2Rng(DefaultWorldRules):
        rng_version = "blake2b-v2"

    f_old = create_world(seed=42, ticks=50).fingerprint()
    f_new = create_world(seed=42, ticks=50, ruleset=V2Rng()).fingerprint()
    assert f_old["final_state_hash"] != f_new["final_state_hash"]


def test_journal_records_rejected_transitions_too():
    sim1 = create_world(seed=42, ticks=100)
    sim2 = create_world(seed=42, ticks=100)
    rejected1 = [(t.id, t.operation, t.reject_reason) for t in sim1.journal.rejected()]
    rejected2 = [(t.id, t.operation, t.reject_reason) for t in sim2.journal.rejected()]
    assert rejected1 == rejected2
    assert all(t.status is TransitionStatus.REJECTED for t in sim1.journal.rejected())
