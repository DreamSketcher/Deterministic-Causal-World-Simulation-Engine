"""v0.12, stage 2b — the cell slice: the acceptance criteria, as tests.

The review fixed six criteria for the frame's unit of reading. Each one
is a test here, because "the frame is cheaper" is only true if the
cheaper reading is also the same reading:

1. equivalence — the slice matches the corresponding pairs of the full
   StateView;
2. causality — transition ids and their ticks are neither lost nor
   replaced;
3. reading — building the slice changes neither ``state.hash()`` nor
   ``journal.hash()``;
4. boundaries — an empty cell, the edge of the map, a subset scope and a
   ruleset without the newer fields;
5. complexity — the cost depends on the slice and the indexes, not on a
   scan of the whole state;
6. UI — the map, the situations, the goal cards and the orders all read
   the SAME slice, and the frame never builds a full view.
"""

from __future__ import annotations

import json

from causal_world.kernel.state import WorldState
from causal_world.observer.situation import (
    StateView,
    growth_limit,
    resettle_opportunities,
    situations,
)
from causal_world.observer.slice import CellSlice, WorldIndex
from causal_world.server.session import Session


# ---------------------------------------------------------------- helpers

def _session(tmp_path, ruleset: str = "player_resettle",
             agents: int = 54) -> Session:
    session = Session(
        seed=7, ruleset=ruleset, regions=2, agents=agents,
        max_ticks=200, db_dir=str(tmp_path),
    )
    for seq in range(1, 4):
        session.decide(seq, 6)  # no-op decision: steps the world
    return session


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, default=str)


# ----------------------------------------------------------- 1. equivalence

def test_the_slice_matches_the_full_view_pair_for_pair(tmp_path):
    s = _session(tmp_path)
    full = StateView.from_state(s.sim.state, tick_of=s._tick_of)
    view = s._frame_view()
    assert view.complete is True

    for prefix in ("cell:", "region:"):
        assert (tuple(full.entities_with_prefix(prefix))
                == tuple(view.entities_with_prefix(prefix)))
        for entity in full.entities_with_prefix(prefix):
            for field_name in s.sim.state.fields_of(entity):
                assert view.has(entity, field_name)
                assert view.get(entity, field_name) == full.get(entity, field_name)
                assert view.source(entity, field_name) == full.source(entity, field_name)

    # and the readers built on top of it agree exactly
    assert ([a.to_dict() for a in situations(view, current_tick=s.sim.state.tick,
                                             history=s._history)]
            == [a.to_dict() for a in situations(full, current_tick=s.sim.state.tick,
                                                history=s._history)])
    assert resettle_opportunities(view) == resettle_opportunities(full)


# ------------------------------------------------------------- 2. causality

def test_transition_ids_and_their_ticks_survive_the_slice(tmp_path):
    s = _session(tmp_path)
    view = s._frame_view()
    cell = next(c for c in view.cells
                if int(view.get(c, "population") or 0) > 0)
    tid = view.source(cell, "population")
    assert tid is not None
    # the id is a real, committed transition of this world
    assert s.sim.journal.by_id(tid).tick == s._tick_of(tid)
    # and the slice reports the same tick a full view with the same
    # resolver would: provenance is not dropped by the optimisation
    full = StateView.from_state(s.sim.state, tick_of=s._tick_of)
    assert view.tick_of(cell, "population") == full.tick_of(cell, "population")
    # the situations of the slice cite the same transition ids as the
    # full view, so a reader can trace the alert to the fact it rests on
    alerts = situations(view, current_tick=s.sim.state.tick,
                        history=s._history)
    assert alerts
    cited = {e["tid"] for alert in alerts for e in alert.evidence}
    assert cited
    full_alerts = situations(full, current_tick=s.sim.state.tick,
                             history=s._history)
    assert ({e["tid"] for a in full_alerts for e in a.evidence} == cited)


# ---------------------------------------------------------------- 3. reading

def test_building_the_slice_changes_no_hash(tmp_path):
    s = _session(tmp_path)
    state_before = s.sim.state.hash()
    journal_before = s.sim.journal.hash()
    view = s._frame_view()
    view.entities_with_prefix("cell:")
    growth_limit(view, view.cells[0], s.sim.state.tick)
    assert s.sim.state.hash() == state_before
    assert s.sim.journal.hash() == journal_before


# -------------------------------------------------------------- 4. boundaries

def test_an_empty_cell_is_a_cell_not_an_absence(tmp_path):
    s = _session(tmp_path)
    view = s._frame_view()
    # cell:0:4 is claimed but empty in this world: land, with soil and a
    # food reserve, and it must read as a cell rather than vanish
    empty = "cell:0:4"
    assert int(view.get(empty, "population") or 0) == 0
    assert view.has(empty, "soil_fertility")
    assert view.get(empty, "soil_fertility") is not None
    # a wild parcel is land, not an alert — that is the world's rule,
    # and the slice must not turn "no alert" into "no cell"
    assert all(a.scope != empty for a in
               situations(view, current_tick=s.sim.state.tick,
                          history=s._history))


def test_the_edge_of_the_map_is_read_like_any_other_cell(tmp_path):
    s = _session(tmp_path)
    view = s._frame_view()
    corner = "cell:0:0"
    assert corner in view.cells
    assert (view.get(corner, "cell_x"), view.get(corner, "cell_y")) == (0, 0)
    assert view.get(corner, "population") is not None


def test_a_subset_slice_says_it_is_not_the_whole_world(tmp_path):
    s = _session(tmp_path)
    index = WorldIndex.from_state(s.sim.state, journal=s.sim.journal)
    one = CellSlice.from_state(s.sim.state, index, cells=["cell:1:2"])
    assert one.cells == ("cell:1:2",)
    assert one.complete is False
    assert one.regions == ("region:1",)
    # a cell the world does not have is not invented
    nothing = CellSlice.from_state(s.sim.state, index, cells=["cell:9:9"])
    assert nothing.cells == ()
    assert nothing.complete is False


def test_an_older_ruleset_has_the_missing_fields_absent_not_zero(tmp_path):
    s = _session(tmp_path, ruleset="player_spatial")
    view = s._frame_view()
    cell = view.cells[0]
    # v0.10/v0.11 fields do not exist in this world: `get` reads None,
    # and `has` says so — the map must not draw a resettlement that
    # never happened
    assert not view.has(cell, "resettled_in")
    assert view.get(cell, "resettled_in") is None


# --------------------------------------------------------------- 5. complexity

def test_the_slice_never_scans_the_state(tmp_path, monkeypatch):
    """A frame must not pay for the entities it does not read.

    The index is built ONCE; after that, the slice answers from it. To
    prove it, the state's scanning reads are made to fail: a slice that
    still worked by scanning would raise here.
    """
    s = _session(tmp_path)
    index = WorldIndex.from_state(s.sim.state, journal=s.sim.journal)

    def boom(*_args, **_kwargs):
        raise AssertionError("the frame scanned the whole state")

    monkeypatch.setattr(WorldState, "entities", boom)
    monkeypatch.setattr(WorldState, "entities_with_prefix", boom)
    monkeypatch.setattr(WorldState, "fields_of", boom)

    view = CellSlice.from_state(s.sim.state, index, tick_of=s._tick_of)
    assert view.cells
    situations(view, current_tick=s.sim.state.tick, history=s._history)
    growth_limit(view, view.cells[0], s.sim.state.tick)
    resettle_opportunities(view)


def test_the_index_tracks_moves_and_deaths(tmp_path):
    s = _session(tmp_path)
    view = s._frame_view()
    for cell in view.cells:
        expected = sorted(
            agent for agent in s.sim.state.entities_with_prefix("agent:")
            if s.sim.state.get(agent, "alive")
            and s.sim.state.get(agent, "cell") == cell
        )
        assert list(view.agents_in_cell(cell)) == expected
    alive = sum(1 for a in s.sim.state.entities_with_prefix("agent:")
                if s.sim.state.get(a, "alive"))
    assert view.alive_agents == alive
    assert view.pool_stats() == (
        sum(1 for a in s.sim.state.entities_with_prefix("agent:")
            if s.sim.state.has(a, "region")),
        sum(1 for a in s.sim.state.entities_with_prefix("agent:")
            if s.sim.state.get(a, "region") == "none"),
    )


# --------------------------------------------------------------------- 6. UI

def test_every_reader_of_the_frame_uses_the_same_slice(tmp_path):
    s = _session(tmp_path)
    full = StateView.from_state(s.sim.state, tick_of=s._tick_of)
    view = s._frame_view()
    # the map, the situations, the goal cards and the resettlement card
    # all come from ONE representation; compared against the full view
    # the output is byte-identical
    assert _json(s._world_view(view)) == _json(s._world_view(full))


def test_the_frame_path_never_builds_a_full_view(tmp_path, monkeypatch):
    s = _session(tmp_path)

    def boom(*_args, **_kwargs):
        raise AssertionError("a frame built a full StateView")

    # CellSlice overrides from_state, so this only forbids the full one
    monkeypatch.setattr(StateView, "from_state", classmethod(boom))
    seq = 4
    frame = s.decide(seq, 6)
    assert frame["world"]["cells"]
    assert frame["world"]["situations"] is not None
    assert frame["world"]["goals"] is not None
