"""Snapshot: immutability, isolation, shared view (spec §4, §5, §38)."""

from __future__ import annotations

import pytest

from causal_world.kernel.snapshot import Snapshot
from causal_world.systems.base import System

from helpers import RulesForTest, make_sim

REGION = "region:0"
SCHEMA = {"temperature": float}


class TempWriter(System):
    """Proposes temperature += 7 (18 -> 25 on the first tick)."""

    name = "TempWriter"

    def compute(self, snapshot, rng, context):
        b = context.builder("temp.write")
        current = b.read(REGION, "temperature")
        b.write(REGION, "temperature", current + 7.0)
        return [b.build()]


class TempReader(System):
    """Records whatever temperature its snapshot shows."""

    name = "TempReader"
    seen: list[float] = []
    seen_snapshot_ids: list[int] = []

    def compute(self, snapshot, rng, context):
        TempReader.seen.append(snapshot.get(REGION, "temperature"))
        TempReader.seen_snapshot_ids.append(id(snapshot))
        return []


class SnapshotIdProbe(System):
    name = "SnapshotIdProbe"
    ids: list[int] = []

    def compute(self, snapshot, rng, context):
        SnapshotIdProbe.ids.append(id(snapshot))
        return []


@pytest.fixture()
def isolated_world():
    TempReader.seen = []
    TempReader.seen_snapshot_ids = []
    rules = RulesForTest(SCHEMA)
    return make_sim(
        rules,
        [TempWriter(), TempReader()],
        seed=0,
        genesis_fields={(REGION, "temperature"): 18.0},
    )


def test_snapshot_isolation_spec38(isolated_world):
    """Same tick: writer proposes 18 -> 25, reader must still see 18."""
    isolated_world.step()
    assert TempReader.seen == [18.0], "reader must see the pre-tick value"
    assert isolated_world.state.get(REGION, "temperature") == 25.0

    # Next tick: 25 becomes visible.
    isolated_world.step()
    assert TempReader.seen == [18.0, 25.0]


def test_all_systems_receive_the_same_snapshot():
    SnapshotIdProbe.ids = []
    TempReader.seen = []
    TempReader.seen_snapshot_ids = []
    rules = RulesForTest(SCHEMA)
    sim = make_sim(
        rules,
        [TempWriter(), SnapshotIdProbe(), TempReader()],
        seed=0,
        genesis_fields={(REGION, "temperature"): 18.0},
    )
    sim.step()
    assert len(SnapshotIdProbe.ids) == 1
    assert TempReader.seen_snapshot_ids == SnapshotIdProbe.ids


def test_snapshot_is_immutable():
    import dataclasses

    sim = make_sim(
        RulesForTest(SCHEMA),
        [],
        seed=0,
        genesis_fields={(REGION, "temperature"): 18.0},
    )
    snap = sim.snapshot()
    with pytest.raises(TypeError):
        snap.data[(REGION, "temperature")] = 99.0  # type: ignore[index]
    with pytest.raises((TypeError, dataclasses.FrozenInstanceError)):
        snap.tick = 5  # type: ignore[misc]
    assert snap.get(REGION, "temperature") == 18.0


def test_snapshot_isolated_from_later_commits(isolated_world):
    snap = isolated_world.snapshot()
    assert snap.get(REGION, "temperature") == 18.0
    isolated_world.step()  # commits 18 -> 25
    assert isolated_world.state.get(REGION, "temperature") == 25.0
    # The frozen view is untouched by the commit.
    assert snap.get(REGION, "temperature") == 18.0
    assert snap.get_source(REGION, "temperature") != isolated_world.state.get_source(
        REGION, "temperature"
    )


def test_snapshot_provenance_is_an_independent_copy():
    sim = make_sim(
        RulesForTest(SCHEMA),
        [TempWriter()],
        seed=0,
        genesis_fields={(REGION, "temperature"): 18.0},
    )
    snap = Snapshot.from_state(sim.state)
    genesis_source = sim.state.get_source(REGION, "temperature")
    sim.step()  # new committed writer for temperature
    assert snap.get_source(REGION, "temperature") == genesis_source
    assert sim.state.get_source(REGION, "temperature") != genesis_source


def test_snapshot_never_reaches_into_live_state(isolated_world):
    """A snapshot taken before a step keeps the old provenance forever."""
    before = isolated_world.snapshot()
    isolated_world.run(3)
    assert before.tick == 0
    assert before.get(REGION, "temperature") == 18.0
