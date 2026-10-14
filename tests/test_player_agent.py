"""v0.6 step 3: PlayerAgentSystem + input channel — the agency contract.

Pinned here (3d):
1. PlayerAgentSystem is registered only in the game ruleset (roster +
   attach() refusing research worlds);
2. NPC agents are untouched: every non-player draw is identical with and
   without a player acting;
3. the ``player.decision`` draw carries the player's value verbatim
   (threshold None, outcome == value) — Q1: a die can never veto a choice;
4. action OUTCOMES stay rng (disease rolls are seed oracle values even for
   the controlled agent), while a declared explore is forced (not a roll);
5. determinism: same seed + same decision stream -> bit-identical replay;
6. replay from the journal: DecisionStreamReader -> the same world again;
7. action_index=2 fires the exploration chain next tick;
8. out-of-range action_index: recorded, rejected, no crash;
9. controlled agent dead -> the system is inert and consumes nothing;
10. the default research world stays bit-identical to its pinned v0.2 hashes.
"""

from __future__ import annotations


import pytest

from causal_world import create_world
from causal_world.player import DecisionChannel, DecisionStreamReader, attach_player_channel
from causal_world.systems.exploration import ExplorationSystem
from causal_world.systems.player import PlayerAgentSystem
from causal_world.world.rules import get_ruleset
from helpers import RulesForTest, make_sim
from test_immune_ruleset import DEFAULT_JOURNAL_HASH, DEFAULT_STATE_HASH

GAME = "agent:0"

_SCHEMA = {
    "alive": bool,
    "region": str,
    "hunger": float,
    "health": float,
    "immune_memory": float,
    "immunity": float,
    "max_health": float,
    "risk_tolerance": float,
    "generation": int,
    "birth_tick": int,
    "parent_id": str,
    "infected": bool,
    "last_action": int,
    "population": int,
    "pop_base": int,
    "soil_fertility": float,
    "food_stock": float,
    "active": bool,
    "was_alive": bool,
    "type": str,
    "age": int,
    "resource_food": float,
    "resource_knowledge": float,
}


class Step3Rules(RulesForTest):
    ruleset_version = "step3-test"
    purposes = {
        "player.decision": "test",
        "agent.explore": "test",
        "agent.senescence": "test",
    }


def _agent(i, *, alive=True, region="region:0", risk=0.0, hunger=0.5, health=100.0):
    return {
        (f"agent:{i}", "alive"): alive,
        (f"agent:{i}", "region"): region,
        (f"agent:{i}", "hunger"): hunger,
        (f"agent:{i}", "health"): health,
        (f"agent:{i}", "immune_memory"): 0.0,
        (f"agent:{i}", "immunity"): 0.3,
        (f"agent:{i}", "max_health"): 100.0,
        (f"agent:{i}", "risk_tolerance"): risk,
        (f"agent:{i}", "generation"): 0,
        (f"agent:{i}", "birth_tick"): 0,
        (f"agent:{i}", "parent_id"): "none",
        (f"agent:{i}", "infected"): False,
        (f"agent:{i}", "last_action"): -1,
    }


_FIELDS = {
    **_agent(0),
    **_agent(1, region="region:1"),
    ("region:0", "population"): 1,
    ("region:0", "pop_base"): 1,
    ("region:0", "soil_fertility"): 0.5,
    ("region:0", "food_stock"): 50.0,
    ("region:1", "population"): 1,
    ("region:1", "pop_base"): 1,
    ("region:1", "soil_fertility"): 0.5,
    ("region:1", "food_stock"): 50.0,
}


def _player_world(actions=(), extra_systems=(), fields=None, no_player=False):
    channel = DecisionChannel(actions=list(actions))
    systems = [] if no_player else [PlayerAgentSystem(channel=channel, controlled=GAME)]
    systems.extend(extra_systems)
    sim = make_sim(
        Step3Rules(_SCHEMA),
        systems,
        seed=7,
        genesis_fields=dict(_FIELDS if fields is None else fields),
    )
    return sim, channel


def _transitions(sim, op):
    return [t for t in sim.journal.all() if t.operation == op]


# ---------------------------------------------------------------- 1 · roster


def test_player_system_is_game_ruleset_scoped():
    game = create_world(seed=7, ruleset=get_ruleset("player_life"), ticks=0)
    assert "PlayerAgentSystem" in {s.name for s in game.systems}
    for name in ("default", "immune", "compost"):
        sim = create_world(seed=7, ruleset=get_ruleset(name), ticks=0)
        assert "PlayerAgentSystem" not in {s.name for s in sim.systems}
    with pytest.raises(ValueError):
        attach_player_channel(sim, DecisionChannel())  # research: refuse


# ---------------------------------------------------- 2 · NPCs see no player


def test_npc_draws_identical_with_and_without_player():
    # a live ruin gives every co-resident agent per-tick explore rolls; the
    # player acting (incl. moving next door) must not touch agent:1's dice
    ruin = {
        ("ruin:1:0", "region"): "region:1",
        ("ruin:1:0", "active"): True,
        ("ruin:1:0", "was_alive"): False,
        ("ruin:1:0", "type"): "granary",
        ("ruin:1:0", "age"): 5,
        ("ruin:1:0", "resource_food"): 50.0,
        ("ruin:1:0", "resource_knowledge"): 0.0,
    }
    fields = {**_FIELDS, **ruin}
    fields[("agent:1", "risk_tolerance")] = 0.2

    def npc_draws(sim):
        return [
            (t.tick, d.entity, d.purpose, d.value)
            for t in sim.journal.all()
            for d in t.random_draws
            if d.entity != GAME and t.operation != "player.act"
        ]

    with_player, _ = _player_world(
        actions=[2, 0, 1, 5, 3, 4, 6], extra_systems=[ExplorationSystem()],
        fields=fields,
    )
    plain, _ = _player_world(
        actions=[], extra_systems=[ExplorationSystem()], fields=fields,
        no_player=True,
    )
    for _ in range(7):
        with_player.step()
        plain.step()
    assert npc_draws(plain)  # the comparison is not vacuous
    assert npc_draws(with_player) == npc_draws(plain)


# --------------------------------------------------- 3 · the value is recorded


def test_decision_value_recorded_verbatim():
    sim, _ = _player_world(actions=[3])
    sim.step()
    (t,) = _transitions(sim, "player.act")
    (d,) = t.random_draws
    assert d.purpose == "player.decision"
    assert d.value == 3.0            # the player's choice, not a seed roll
    assert d.threshold is None       # Q1: no probability can veto it
    assert d.outcome == 3.0
    assert t.writes[0].new == 3      # last_action follows the stream


def test_action_effects_match_the_card():
    # one fresh world per action: exactly one step, then diff the state
    expected = {
        0: {"hunger": 0.2, "health": 95.0},                     # work
        1: {"region": "region:1"},                              # migrate
        2: {"hunger": 0.5},  # explore with no ruin nearby: inert choice
        3: {"health": 100.0, "immunity": 0.35},                 # heal (capped)
        4: {"hunger": 0.45, "health": 99.0},                     # trade
        5: {"health": 100.0, "hunger": 0.55},                    # rest
        6: {"hunger": 0.51},                                    # no-op (idle burn)
    }
    for action, want in expected.items():
        sim, _ = _player_world(actions=[action])
        sim.step()
        st = sim.state
        assert st.get(GAME, "last_action") == action
        for field, value in want.items():
            got = st.get(GAME, field)
            assert abs(got - value) < 1e-9 if isinstance(value, float) else got == value, (
                f"action {action} ({field}): {got} != {value}"
            )


# --------------------------------------------------------- 4 · outcome is rng


def test_explore_action_fires_immediately_and_forced():
    # the player sits with an active ruin (risk 0.0: by chance they would
    # NEVER explore) — action 2 executes the find on THIS tick, forced.
    ruin = {
        ("ruin:1:0", "region"): "region:1",
        ("ruin:1:0", "active"): True,
        ("ruin:1:0", "was_alive"): False,
        ("ruin:1:0", "type"): "granary",
        ("ruin:1:0", "age"): 5,
        ("ruin:1:0", "resource_food"): 50.0,
        ("ruin:1:0", "resource_knowledge"): 0.0,
    }
    fields = {**_FIELDS, **ruin}
    fields[("agent:0", "region")] = "region:1"
    sim, _ = _player_world(actions=[2], fields=fields)
    sim.step()
    (t,) = _transitions(sim, "player.act")
    (d,) = t.random_draws
    assert d.value == 2.0 and d.threshold is None   # declared, not rolled
    writes = {(c.entity, c.field): c.new for c in t.writes}
    # the find is on the player's OWN transition (AUTOPSY points at the ruin)
    assert writes[(GAME, "hunger")] == 0.0           # 0.2 * 50 relief, clamped
    assert writes[("ruin:1:0", "resource_food")] == 40.0  # one 10 draw-down
    assert sim.state.get("ruin:1:0", "age") == 5     # no RuinSystem: untouched


def test_explore_with_nothing_to_find_is_recorded_but_inert():
    # no active ruin in the player's region: the choice is journaled
    # (last_action=2) but no bonus/draw-down writes fire
    sim, _ = _player_world(actions=[2])
    sim.step()
    (t,) = _transitions(sim, "player.act")
    assert {(c.entity, c.field) for c in t.writes} == {(GAME, "last_action")}
    assert sim.state.get(GAME, "last_action") == 2


# ------------------------------------------------------ 5 + 6 · replay story


def _game_run(actions, ticks, seed=7):
    sim = create_world(
        seed=seed, ruleset=get_ruleset("player_life"), ticks=0,
        regions=2, agents=20,
    )
    channel = DecisionChannel(actions=list(actions))
    attach_player_channel(sim, channel)
    for _ in range(ticks):
        sim.step()
    return sim


def test_determinism_given_stream():
    script = [0, 2, 1, 5, 0, 6, 2, 1, 3, 0] * 6  # 60 ticks
    a = _game_run(script, 60)
    b = _game_run(script, 60)
    assert a.state.hash() == b.state.hash()
    assert a.journal.hash() == b.journal.hash()
    # and a different stream genuinely diverges (the player is causal)
    c = _game_run([5] * 60, 60)
    assert c.journal.hash() != a.journal.hash()


def test_replay_from_journal_is_bit_identical():
    script = [0, 2, 1, 99, 5, 6, 2, 0, 3, 4] * 8  # includes rejects
    live = _game_run(script, 80)
    replay_stream = DecisionStreamReader.actions_from(live.journal, GAME)
    # every live tick while alive committed exactly one decision record
    assert len(replay_stream) >= 60
    replay = _game_run(replay_stream, 80)
    assert replay.state.hash() == live.state.hash()
    assert replay.journal.hash() == live.journal.hash()
    # the recovered stream also contains the reject (recorded, not dropped)
    assert 99 in replay_stream


# -------------------------------------------------------- 8 · bad index: no crash


def test_out_of_range_recorded_rejected_not_crashed():
    sim, channel = _player_world(actions=[99])
    sim.step()
    (t,) = _transitions(sim, "player.act")
    (d,) = t.random_draws
    assert d.value == 99.0                  # attempt kept verbatim for replay
    assert len(t.writes) == 1               # the record and nothing else
    assert t.writes[0].field == "last_action" and t.writes[0].new == -1
    assert sim.state.get(GAME, "hunger") == 0.5   # no effect fired
    assert channel.pending == 0             # and the bad value WAS consumed


# ------------------------------------------------------------- 9 · death inert


def test_dead_player_consumes_nothing():
    fields = dict(_FIELDS)
    for k in list(fields):
        if k == (GAME, "alive"):
            fields[k] = False
    sim, channel = _player_world(actions=[0, 1, 2], fields=fields)
    for _ in range(5):
        sim.step()
    assert _transitions(sim, "player.act") == []   # inert: no decisions
    assert channel.pending == 3                     # stream untouched -> replay stays aligned


# ------------------------------------------ 10 · the research world is frozen


def test_default_world_bit_identical():
    sim = create_world(seed=42, ticks=100)
    assert sim.state.hash() == DEFAULT_STATE_HASH
    assert sim.journal.hash() == DEFAULT_JOURNAL_HASH


# ---------------------------------------------------------- channel semantics


def test_channels_blocking_and_default():
    idle = DecisionChannel(block=False, default_action=6)
    assert idle.next_action() == 6              # empty non-blocking -> idle
    blocking = DecisionChannel(block=True, timeout=0.05)
    import time

    t0 = time.time()
    assert blocking.next_action() == 6           # live server: waits for the
    assert time.time() - t0 >= 0.04              # client, then idles after
    # (never blocks a simulation tick forever)
    delivered = DecisionChannel()
    delivered.deliver(1)
    assert delivered.next_action() == 1          # FIFO order preserved


def test_attach_requires_player_roster():
    game = create_world(seed=7, ruleset=get_ruleset("player_life"), ticks=0)
    ch = attach_player_channel(game, DecisionChannel(actions=[6]))
    assert ch is not None
    names = {s.name for s in game.systems}
    assert "PlayerAgentSystem" in names


def test_channel_from_helper_replays_the_recorded_stream():
    # regression for P3: channel_from once called cls(...) on the reader
    # itself (TypeError, silently dead because no test used the helper)
    game = create_world(seed=3, ruleset=get_ruleset("player_life"), ticks=0,
                        regions=2, agents=8)
    attach_player_channel(game, DecisionChannel(actions=[0, 6, 99, 2]))
    for _ in range(4):
        game.step()
    ch = DecisionStreamReader.channel_from(game.journal)
    actions = [ch.next_action() for _ in range(4)]
    assert actions == DecisionStreamReader.actions_from(game.journal)
    assert actions == [0, 6, 99, 2]  # rejects verbatim, aligned per live tick
