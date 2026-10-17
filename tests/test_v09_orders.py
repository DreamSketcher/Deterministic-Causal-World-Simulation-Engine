"""v0.9 tests — the contract of an order: never lost silently.

The v0.8 harness could put two decrees on one tick; the second overwrote
the first and the journal showed only one. The world was correct and the
player was lied to. These tests pin the fix:

* an order is either accepted, queued for the first free tick, or
  refused — and the answer reaches the client in the frame;
* two orders for one tick both land in the journal, on different ticks;
* the protocol answer of the session says which of the three happened;
* a refused order still does not consume the decision slot.
"""

from __future__ import annotations

import pytest

from causal_world import create_world
from causal_world.observer.journal import JournalView
from causal_world.player import DecisionChannel, attach_player_channel
from causal_world.systems.directive import (
    DIRECTIVE_AMEND,
    DIRECTIVE_NURSERY,
    Directive,
    DirectiveChannel,
    DirectiveSystem,
)
from causal_world.world.rules import get_ruleset


# ---------------------------------------------------------------- channel


def test_a_free_tick_accepts_the_order():
    channel = DirectiveChannel()
    answer = channel.schedule(20, Directive(DIRECTIVE_AMEND, "cell:0:0", 0.15))
    assert answer.status == "accepted"
    assert answer.tick == 20
    assert answer.to_dict()["name"] == "amend"
    assert channel.at(20).param == 0.15


def test_a_second_order_for_one_tick_is_queued_not_dropped():
    channel = DirectiveChannel()
    first = channel.schedule(20, Directive(DIRECTIVE_AMEND, "cell:0:0", 0.15))
    second = channel.schedule(20, Directive(DIRECTIVE_NURSERY, "cell:0:1", 1.0))
    assert first.accepted and second.queued

    # the first order owns the tick it asked for
    assert channel.at(20).kind == DIRECTIVE_AMEND
    # the second is enacted at the first free tick after it
    assert channel.at(21).kind == DIRECTIVE_NURSERY
    assert channel.at(21).region == "cell:0:1"
    # and it is no longer pending
    assert channel.pending() == []


def test_a_queued_order_does_not_displace_an_explicit_one():
    channel = DirectiveChannel()
    channel.schedule(20, Directive(DIRECTIVE_AMEND, "cell:0:0", 0.15))
    channel.schedule(20, Directive(DIRECTIVE_NURSERY, "cell:0:1", 1.0))
    channel.schedule(21, Directive(DIRECTIVE_AMEND, "cell:0:2", 0.2))
    assert channel.at(21).region == "cell:0:2"  # the explicit order wins
    assert channel.at(22).kind == DIRECTIVE_NURSERY  # the queue moves on


def test_the_queue_has_a_bound_and_refuses_beyond_it():
    channel = DirectiveChannel()
    channel.schedule(20, Directive(DIRECTIVE_AMEND, "cell:0:0", 0.15))
    for i in range(DirectiveChannel.MAX_PENDING):
        answer = channel.schedule(
            20, Directive(DIRECTIVE_NURSERY, f"cell:0:{i % 4}", 1.0)
        )
        assert answer.queued
    refused = channel.schedule(
        20, Directive(DIRECTIVE_AMEND, "cell:0:1", 0.25)
    )
    assert refused.rejected
    assert "очередь" in refused.message
    assert len(channel.pending()) == DirectiveChannel.MAX_PENDING


def test_the_answers_are_plain_data_for_the_client():
    channel = DirectiveChannel()
    channel.schedule(10, Directive(DIRECTIVE_AMEND, "cell:0:0", 0.15))
    answer = channel.schedule(10, Directive(DIRECTIVE_AMEND, "cell:0:1", 0.25))
    payload = answer.to_dict()
    assert payload["status"] == "queued"
    assert payload["target"] == "cell:0:1"
    assert payload["param"] == 0.25
    assert payload["tick"] is None  # the journal decides the real tick


# ------------------------------------------------------- in a real world


def test_both_orders_of_one_tick_are_in_the_journal(tmp_path):
    """The regression the review found: nothing is overwritten silently."""
    db = str(tmp_path / "queued.db")
    sim = create_world(
        seed=7, ruleset=get_ruleset("player_spatial"), ticks=0,
        regions=2, agents=54, persist=db,
    )
    attach_player_channel(sim, DecisionChannel(actions=[6] * 80))
    channel = DirectiveChannel()
    for system in sim.systems:
        if isinstance(system, DirectiveSystem):
            system.channel = channel

    channel.schedule(10, Directive(DIRECTIVE_AMEND, "cell:0:0", 0.15))
    answer = channel.schedule(10, Directive(DIRECTIVE_NURSERY, "cell:0:1", 1.0))
    assert answer.queued

    sim.run(30)
    sim.journal.commit()
    sim.journal.close()

    with JournalView(db) as view:
        rows = []
        for t in view:
            if t.operation != "player.directive":
                continue
            if t.status.value != "COMMITTED":
                continue
            rows.append(
                (
                    t.tick,
                    int(t.random_draws[0].value),
                    t.random_draws[0].entity,
                )
            )
    assert (10, DIRECTIVE_AMEND, "cell:0:0") in rows
    assert (11, DIRECTIVE_NURSERY, "cell:0:1") in rows
    assert len(rows) == 2


# ------------------------------------------------------------ the session


def _session(tmp_path, name="s.db"):
    from causal_world.server.session import Session
    return Session(
        seed=7, ruleset="player_spatial", regions=2, agents=54,
        db_path=str(tmp_path / name), max_ticks=200,
    )


def test_the_frame_reports_what_happened_to_the_order(tmp_path):
    session = _session(tmp_path)
    try:
        session.decide(1, 6)
        frame = session.decide(
            2, 6, {"kind": 0, "target": "cell:1:0", "param": 0.15}
        )
        assert frame["decree"]["status"] == "accepted"
        assert frame["decree"]["tick"] == 2
        assert frame["decree"]["name"] == "amend"
        assert frame["orders"]["pending"] == []
        assert any(
            o["tick"] >= frame["tick"] for o in frame["orders"]["scheduled"]
        )
    finally:
        session.close()


def test_an_order_for_an_occupied_tick_is_queued_and_says_so(tmp_path):
    session = _session(tmp_path, "q.db")
    try:
        session.decide(1, 6)
        next_tick = session.sim.state.tick + 1
        # occupy the tick the next order would take
        session.decrees.schedule(
            next_tick, Directive(DIRECTIVE_AMEND, "cell:0:0", 0.1)
        )
        frame = session.decide(
            2, 6, {"kind": 3, "target": "cell:0:1", "param": 1.0}
        )
        assert frame["decree"]["status"] == "queued"
        assert frame["orders"]["pending"]
        pending = frame["orders"]["pending"][0]
        assert pending["name"] == "nursery"
        assert pending["requested_tick"] == next_tick
    finally:
        session.close()


def test_a_refused_order_keeps_the_decision_slot_open(tmp_path):
    from causal_world.server.session import ProtocolError

    session = _session(tmp_path, "r.db")
    try:
        session.decide(1, 6)
        with pytest.raises(ProtocolError) as err:
            session.decide(
                2, 6, {"kind": 0, "target": "cell:9:9", "param": 0.1}
            )
        assert err.value.code == "unknown_target"
        assert session.last_seq == 1  # the slot is still seq 2
        frame = session.decide(2, 6)  # the same seq works
        assert frame["seq"] == 2
    finally:
        session.close()
