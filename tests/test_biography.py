"""v0.6 step 4: BiographyCard — the causal ledger of one life as data.

Contract under test (consult pack §7): six index queries, no new
CausalQuery API; sections meta/death/causes/conditions/decisions/legacy;
choice-vs-chance-vs-law straight from draw typing; consecutive identical
decisions grouped for presentation while the journal stays complete; the
card is a pure function of the archive (fingerprint golden + identical cards
from two independent runs of seed+stream — the card-level leg of the P1
«transport must not change the result» check).

The scripted life reuses the step-3 E2E recipe (seed 7, 2x30 agents/region,
rng(99) action script): the controlled agent dies of infection at t51 — so
death, die-probability and the cause trace are asserted on FACTS, not
mocks.
"""

from __future__ import annotations

import random

import pytest

from causal_world import create_world
from causal_world.observer import biography as bio
from causal_world.player import DecisionChannel, attach_player_channel
from causal_world.query.query import CausalQuery
from causal_world.world.rules import get_ruleset


def _script(n=200):
    rng = random.Random(99)
    out = []
    for _ in range(n):
        r = rng.random()
        out.append(2 if r < 0.25 else 1 if r < 0.4 else 0 if r < 0.7 else 6)
    return out


def _play(tmp_path, name, actions, ticks, seed=7, agents=60):
    db = str(tmp_path / f"{name}.db")
    sim = create_world(
        seed=seed, ruleset=get_ruleset("player_life"), ticks=0,
        regions=2, agents=agents, persist=db,
    )
    attach_player_channel(sim, DecisionChannel(actions=list(actions)))
    for _ in range(ticks):
        sim.step()
    # The archive commits in batches; a reader (JournalView, mode=ro) sees
    # the run only once finalized. Same contract as v0.4/v0.5: read closed
    # archives (the step-5 server will flush per delivered decision batch).
    sim.journal.close()
    return db


# ---------------------------------------------------------------- main story


def test_card_of_a_scripted_life(tmp_path):
    db = _play(tmp_path, "life", _script(100), 100)
    card = bio.build_biography(db, "agent:0")

    m = card.meta
    assert m.agent == "agent:0"
    assert m.alive_at_end is False
    assert m.committed > 1000 and m.transitions >= m.committed
    assert m.seed == "7" and m.ruleset_version and m.rng_version

    d = card.death
    assert d is not None
    assert (d.tick, d.operation) == (51, "disease.infect")  # the E2E fact
    assert d.die is not None
    purpose, roll, thr = d.die
    assert purpose == "disease.infection" and roll < thr      # chance, quantified

    c = card.causes
    assert c is not None and c.nodes
    assert c.root_tid == d.tid
    assert c.nodes[-1].tid == d.tid          # trace order: deepest first, root last
    assert {n.kind for n in c.nodes} <= set(bio.CAUSE_KINDS)
    assert any(n.kind == "chance" for n in c.nodes)
    assert any(n.kind == "law" for n in c.nodes)  # the health backlog walks back

    conds = card.conditions
    assert conds and {r.field for r in conds} <= {"hunger", "health"}
    hunger = [r for r in conds if r.field == "hunger"]
    assert any(r.negative > 0 for r in hunger)  # metabolism ate at him

    decisions = card.decisions
    assert decisions
    assert sum(g.count for g in decisions) == 52  # one node per live tick
    labels = {g.label for g in decisions}
    assert labels & {"work", "explore", "migrate", "idle"}

    assert len(card.fingerprint()) == 64


def test_card_is_a_pure_function_of_the_archive(tmp_path):
    db = _play(tmp_path, "life2", _script(60), 60)
    a = bio.build_biography(db, "agent:0")
    b = bio.build_biography(db, "agent:0")  # reuses the built cache
    assert a.fingerprint() == b.fingerprint()


def test_replay_over_two_runs_identical_card(tmp_path):
    s = _script(100)
    db1 = _play(tmp_path, "run1", s, 100)
    db2 = _play(tmp_path, "run2", s, 100)
    c1 = bio.build_biography(db1, "agent:0")
    c2 = bio.build_biography(db2, "agent:0")
    assert c1.fingerprint() == c2.fingerprint()
    assert c1 == c2


# ------------------------------------------------------- decisions: reject &
#                                                                   grouping


def test_reject_recorded_and_runs_grouped(tmp_path):
    actions = [6] * 8 + [99] + [0] * 4 + [6] * 8
    db = _play(tmp_path, "small", actions, 20, agents=40)
    card = bio.build_biography(db, "agent:0")
    groups = card.decisions

    idle0 = groups[0]
    assert (idle0.label, idle0.count, idle0.first_tick) == ("idle", 8, 0)
    rej = next(g for g in groups if not g.applied)
    assert rej.label == "rejected(99)" and rej.raw == (99,)
    work = next(g for g in groups if g.label == "work")
    assert work.count >= 3          # runs of four collapse into ONE node line
    assert work.first_tick == 9
    assert sum(g.count for g in groups) == 20  # nothing silently dropped


# ------------------------------------------------------------ NPC biography


def test_npc_card_is_law_and_chance_only(tmp_path):
    db = _play(tmp_path, "npc", _script(30), 30, agents=40)
    card = bio.build_biography(db, "agent:1")
    assert card.decisions == ()          # nobody was at the wheel for him
    md = card.to_markdown()
    assert "pure law and chance" in md
    assert card.conditions  # metabolism still explains him
    assert any("metabolism" in r.operation for r in card.conditions)


def test_alive_at_end_has_no_death_section(tmp_path):
    db = _play(tmp_path, "short", _script(20), 20, agents=40)
    card = bio.build_biography(db, "agent:0")
    if card.meta.alive_at_end:
        assert card.death is None and card.causes is None
        assert "No death transition" in card.to_markdown()
    else:  # a 20-tick world may already have killed him: still a valid card
        assert card.death is not None


# --------------------------------------------------------- query budget law


def test_query_budget_is_six(tmp_path, monkeypatch):
    # class-level patch: CausalQuery filters return clones of the same class,
    # so the counter sees queries from any chained copy
    calls = {"n": 0}
    for name in ("list", "delta_profile", "trace"):
        fn = getattr(CausalQuery, name)

        def counted(self, *a, _fn=fn, **k):
            calls["n"] += 1
            return _fn(self, *a, **k)

        monkeypatch.setattr(CausalQuery, name, counted)
    db = _play(tmp_path, "budget", _script(100), 100)
    bio.build_biography(db, "agent:0")
    # death, decisions, profile(hunger), profile(health), trace, legacy — six
    assert calls["n"] == 6


def test_to_markdown_contains_every_section(tmp_path):
    db = _play(tmp_path, "md", _script(100), 100)
    md = bio.build_biography(db, "agent:0").to_markdown()
    for header in (
        "# Biography of agent:0",
        "## Death",
        "## Necessary causes",
        "## Conditions",
        "## Decisions",
        "## Legacy",
    ):
        assert header in md
    assert "the die: roll" in md  # chance is quantified, not narrated
