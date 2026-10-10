"""Full-world integration tests: tick loop, divergence, order independence,
causal reconstruction, observer separation (spec §44-§47, §51)."""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

import pytest

from causal_world import create_world
from causal_world.causal.trace import collect_ancestors, trace_back
from causal_world.kernel.transition import TransitionStatus
from causal_world.observer.events import events_from_journal
from causal_world.observer.observability import Observability

SRC = pathlib.Path(__file__).parent.parent / "src" / "causal_world"


def test_world_scale_and_activity():
    sim = create_world(seed=42, ticks=100)
    state = sim.state
    assert len(state.entities_with_prefix("region:")) == 2
    assert len(state.entities_with_prefix("agent:")) == 10
    assert state.tick == 100
    assert len(sim.journal) > 1000
    assert sim.journal.committed(), "world must commit transitions"


def test_divergence_across_seeds_spec44():
    """Seeds 1..5 must produce distinct state fingerprints for this world.
    (Not a universal law of the kernel — an expected property of this
    sufficiently rich test world.)"""
    hashes = [create_world(seed=s, ticks=100).state.hash() for s in range(1, 6)]
    assert len(set(hashes)) == 5, f"worlds must diverge: {hashes}"


def test_system_order_independence_spec45():
    default_order = ["ClimateSystem", "AgricultureSystem", "DiseaseSystem", "AgentSystem"]
    reversed_order = list(reversed(default_order))

    sim1 = create_world(seed=9, system_order=default_order, ticks=40)
    sim2 = create_world(seed=9, system_order=reversed_order, ticks=40)

    assert sim1.state.hash() == sim2.state.hash()
    assert sim1.state.data == sim2.state.data
    assert sim1.journal.hash() == sim2.journal.hash()

    # Also a third arbitrary permutation.
    shuffled = ["DiseaseSystem", "AgricultureSystem", "ClimateSystem", "AgentSystem"]
    sim3 = create_world(seed=9, system_order=shuffled, ticks=40)
    assert sim3.state.hash() == sim1.state.hash()
    assert sim3.journal.hash() == sim1.journal.hash()


def _find_death(sim):
    for t in sim.journal.committed():
        for w in t.writes:
            if w.field == "alive" and w.old is True and w.new is False:
                return t
    return None


def test_causal_reconstruction_spec46():
    """trace_back must mechanically rebuild the dependency chain —
    no manual causes=[...] anywhere."""
    sim = create_world(seed=42, ticks=100)
    death = _find_death(sim)
    assert death is not None, "seed 42 must produce at least one death"

    node = trace_back(sim.index, death.id, depth=12)
    ancestor_ids = collect_ancestors(node)
    ancestor_transitions = [sim.index.get(tid) for tid in ancestor_ids]
    systems_seen = {t.system for t in ancestor_transitions}
    operations_seen = {t.operation for t in ancestor_transitions}

    # The chain of a death reaches back through metabolism/food into
    # climate within a 12-tick window.
    assert "AgentSystem" in systems_seen
    assert "AgricultureSystem" in systems_seen
    assert "ClimateSystem" in systems_seen
    assert "climate.step" in operations_seen
    assert "agriculture.harvest" in operations_seen

    # Every edge exists only because some read recorded a source write.
    for t in ancestor_transitions:
        for r in t.reads:
            if r.source_transition is not None:
                source = sim.index.get(r.source_transition)
                assert source.status is TransitionStatus.COMMITTED
                assert any(
                    w.entity == r.entity and w.field == r.field and w.new == r.value
                    for w in source.writes
                ), "read value must equal what its source transition wrote"


def test_reverse_dependency_index():
    sim = create_world(seed=42, ticks=30)
    climate_tid = next(
        t.id for t in sim.journal.committed() if t.operation == "climate.step"
    )
    dependents = sim.index.dependents_of(climate_tid)
    assert dependents, "climate writes must be read by later transitions"
    dependents_transitions = {sim.index.get(d).operation for d in dependents}
    assert "agriculture.harvest" in dependents_transitions


def test_events_are_derived_not_fundamental():
    sim = create_world(seed=42, ticks=100)
    events = events_from_journal(sim.journal)
    assert events
    for event in events:
        # Every event points back at a real committed transition.
        t = sim.journal.by_id(event.transition_id)
        assert t.status is TransitionStatus.COMMITTED
        assert event.tick == t.tick
    types = {e.type for e in events}
    assert "infection" in types
    assert "death" in types


def test_observability_is_read_only_spec11():
    sim = create_world(seed=5, ticks=50)
    before_state = sim.state.hash()
    before_journal = sim.journal.hash()

    obs = Observability(sim)
    obs.events()
    obs.statistics()
    for agent in sim.state.entities_with_prefix("agent:")[:3]:
        obs.biography(agent)
        obs.rejected_actions(agent)
    if sim.journal.committed():
        some_id = sim.journal.committed()[-1].id
        obs.trace(some_id, depth=4)
        obs.render_trace(some_id, depth=2)

    assert sim.state.hash() == before_state
    assert sim.journal.hash() == before_journal


def test_llm_independence_spec47():
    """The simulation must run with zero LLM/agent-framework dependencies:
    every import in the package is either stdlib or causal_world itself."""
    stdlib = set(sys.stdlib_module_names)
    offenders = []
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module.split(".")[0]]
            else:
                continue
            for name in names:
                if name not in stdlib and name != "causal_world":
                    offenders.append(f"{path.name}: {name}")
    assert not offenders, f"external dependencies found: {offenders}"
    assert not any("llm" in p.name.lower() for p in SRC.rglob("*.py"))


def test_cli_run_and_trace():
    run = subprocess.run(
        [sys.executable, "-m", "causal_world", "run", "--seed", "5", "--ticks", "30"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run.returncode == 0, run.stderr
    assert "World seed:       5" in run.stdout
    assert "Fingerprint:" in run.stdout
    assert "Final state:" in run.stdout

    # Find a committed transition id in the same world for the trace command.
    sim = create_world(seed=5, ticks=30)
    target = sim.journal.committed()[-1].id
    trace = subprocess.run(
        [
            sys.executable, "-m", "causal_world", "trace",
            "--seed", "5", "--ticks", "30", "--transition", str(target), "--depth", "2",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert trace.returncode == 0, trace.stderr
    assert f"T{target} " in trace.stdout
    assert "READ" in trace.stdout or "WRITE" in trace.stdout

    missing = subprocess.run(
        [
            sys.executable, "-m", "causal_world", "trace",
            "--seed", "5", "--ticks", "5", "--transition", "999999",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert missing.returncode == 2
    assert "does not exist" in missing.stderr


def test_100_ticks_minimum_scale():
    """Definition of Done: 2 regions, 10 agents, >= 100 ticks."""
    sim = create_world(seed=2, ticks=100)
    assert sim.state.tick == 100
    stats_ops = {t.operation for t in sim.journal.committed()}
    assert {"climate.step", "agriculture.harvest", "disease.environment",
            "agents.census", "agent.metabolism"} <= stats_ops
