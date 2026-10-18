"""v0.13 — ADR v13-1: health reaching zero is death for the controlled agent.

Before the fix, ``work`` and ``trade`` clamped health at 0 without writing
``alive=false``: the controlled agent stayed alive with zero health until an
infection happened to finish it (tick 45 in the Godot slice). The contract is
the one every other lethal path already follows: ``agent.death`` writes
``alive=false`` and ``health=0`` in the same transition.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from causal_world.server.session import Session

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_player_agent import (  # noqa: E402
    _FIELDS,
    GAME,
    _player_world,
    _transitions,
)


def _with_health(value: float) -> dict:
    return {**_FIELDS, (GAME, "health"): value}


# ------------------------------------------------------------ transitions


def test_lethal_work_is_decision_plus_death_in_the_same_tick():
    sim, _ = _player_world(actions=[0], fields=_with_health(3.0))  # cost 5
    sim.step()
    # the decision record stays a player.act: replay and continuity read it
    (decision,) = _transitions(sim, "player.act")
    assert decision.random_draws[0].value == 0.0
    assert "health" not in {w.field for w in decision.writes}
    assert {w.field for w in decision.writes} == {"last_action", "hunger"}
    # the death is the existing agent.death contract, in the same tick
    (death,) = _transitions(sim, "agent.death")
    assert death.system == "PlayerAgentSystem"
    assert death.tick == decision.tick
    writes = {w.field: w.new for w in death.writes}
    assert writes == {"alive": False, "health": 0.0}
    assert sim.state.get(GAME, "alive") is False
    assert sim.state.get(GAME, "health") == 0.0


def test_decision_stream_survives_a_lethal_action():
    from causal_world.player import DecisionStreamReader

    sim, _ = _player_world(actions=[0], fields=_with_health(3.0))
    sim.step()
    assert DecisionStreamReader.actions_from(sim.journal, GAME) == [0]


def test_work_above_cost_stays_an_ordinary_action():
    sim, _ = _player_world(actions=[0], fields=_with_health(20.0))
    sim.step()
    assert _transitions(sim, "agent.death") == []
    (t,) = _transitions(sim, "player.act")
    assert sim.state.get(GAME, "alive") is True
    assert abs(sim.state.get(GAME, "health") - 15.0) < 1e-9


def test_trade_is_lethal_the_same_way():
    sim, _ = _player_world(actions=[4], fields=_with_health(0.5))  # cost 1
    sim.step()
    assert len(_transitions(sim, "player.act")) == 1
    (t,) = _transitions(sim, "agent.death")
    assert sim.state.get(GAME, "alive") is False
    assert sim.state.get(GAME, "health") == 0.0


def test_health_never_negative_and_alive_implies_positive_for_work_trade():
    for start in (0.0001, 1.0, 4.99, 5.0, 5.01):
        sim, _ = _player_world(actions=[0], fields=_with_health(start))
        sim.step()
        alive = sim.state.get(GAME, "alive")
        health = sim.state.get(GAME, "health")
        assert health >= 0.0
        assert not (alive and health <= 0.0), start


# ------------------------------------------------------------ whole life


def _life(seed: int, max_presses: int = 200):
    """Play ``work`` until the life ends. Returns (frames, session, open)."""
    s = Session(
        seed=seed,
        ruleset="player_resettle",
        regions=2,
        agents=54,
        max_ticks=200,
        db_dir=tempfile.mkdtemp(prefix=f"v13_{seed}_"),
    )
    frames = []
    for seq in range(1, max_presses + 1):
        f = s.decide(seq, 0)
        frames.append(f)
        if not f["alive"]:
            break
    return frames, s


def test_no_zombie_ticks_in_the_controlled_life():
    for seed in (1, 3, 7, 9):
        frames, s = _life(seed)
        try:
            for f in frames:
                you = f["you"]
                assert not (f["alive"] and you["health"] <= 0.0), (seed, f["tick"])
            assert not frames[-1]["alive"], seed
            # the death tick is the tick the health reaches zero
            assert frames[-1]["you"]["health"] == 0.0
        finally:
            if s.state != "finalized":
                s.close()


def test_slice_seed7_dies_when_health_runs_out_and_is_classified_exhaustion():
    frames, s = _life(7)
    try:
        assert frames[-1]["tick"] == 14, frames[-1]["tick"]  # was 45 before v13-1
        autopsy = s.autopsy()
        assert autopsy["operation"] == "agent.death"
        assert autopsy["label"] == "exhaustion"
    finally:
        if s.state != "finalized":
            s.close()
