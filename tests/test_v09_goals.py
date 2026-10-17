"""v0.9 tests — the goal layer: a problem is solved only if the SYSTEM
survived it.

The centre of these tests is the case the v0.9 review named: a famine
whose signal disappears because the people it was about are dead. The
layer must call that a collapse, never a resolution. Everything else here
exists to keep the verdicts honest in the other directions too (a real
recovery is not punished, a problem that moved next door is not called
solved).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from causal_world.observer.goal import (  # noqa: E402
    RECOVERY_TICKS,
    Goal,
    episodes,
    evaluate,
    goals,
    summary,
)
from causal_world.observer.situation import (  # noqa: E402
    THIN_SOIL,
    Alert,
    FieldHistory,
    StateView,
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def history(*, pops, food, soil, cells=("cell:0:0",)):
    """A history in which every series is given per tick."""
    h = FieldHistory()
    for cell in cells:
        for tick, p in enumerate(pops):
            h.add(cell, "population", tick, p)
        for tick, f in enumerate(food):
            h.add(cell, "food_stock", tick, f)
        for tick, s in enumerate(soil):
            h.add(cell, "soil_fertility", tick, s)
    return h


def view(*, cells=("cell:0:0",), population=0, food=0.0, soil=0.47):
    """A StateView with just the fields the goal layer reads."""
    values = {}
    for index, cell in enumerate(cells):
        values[(cell, "population")] = (population, 100 + index, 9)
        values[(cell, "food_stock")] = (food, 200 + index, 9)
        values[(cell, "soil_fertility")] = (soil, 300 + index, 9)
        values[(cell, "region")] = ("region:0", 1, 0)
        values[(cell, "cell_x")] = (index % 2, 2, 0)
        values[(cell, "cell_y")] = (index // 2, 3, 0)
    return StateView(values)


def famine_alert(cell="cell:0:0", since=2):
    return Alert(
        kind="famine", scope=cell, severity=0.9, since_tick=since,
        message=f"{cell}: закрома опустела",
    )


# ----------------------------------------------------------------------
# 1. Episodes: when did the problem exist
# ----------------------------------------------------------------------
def test_episode_opens_and_closes_with_hysteresis():
    # famine from tick 2 to 8, then calm
    pops = [10] * 20
    food = [100, 100, 5, 5, 5, 5, 5, 5, 5, 100, 100, 100, 100, 100,
            100, 100, 100, 100, 100, 100]
    h = history(pops=pops, food=food, soil=[0.47] * 20)
    eps = episodes(h, "cell:0:0", "feed")
    assert len(eps) == 1
    goal = eps[0]
    assert goal.opened_tick == 2
    # the signal stops at tick 9; the episode closes after RECOVERY_TICKS
    assert goal.closed_tick == 9
    assert goal.closed_tick - 2 >= RECOVERY_TICKS


def test_one_good_tick_does_not_close_a_famine():
    food = [5, 5, 5, 100, 5, 5, 5, 5, 5, 5, 5, 5]
    h = history(pops=[10] * 12, food=food, soil=[0.47] * 12)
    eps = episodes(h, "cell:0:0", "feed")
    assert len(eps) == 1
    assert eps[0].closed_tick is None  # still open: a blip is not a solution


# ----------------------------------------------------------------------
# 2. The verdict: signal gone is not enough
# ----------------------------------------------------------------------
def test_famine_that_ends_with_the_people_is_a_collapse():
    """The case from the review: the threshold improved because everyone died."""
    pops = [10] * 8 + [8, 5, 3, 2, 1, 0, 0, 0, 0, 0, 0, 0]
    food = [5] * 8 + [100] * 12
    soil = [0.47] * 20
    h = history(pops=pops, food=food, soil=soil)
    goal = episodes(h, "cell:0:0", "feed")[0]
    verdict = evaluate(goal, h, view(population=0), [], tick=60)
    assert verdict.status == "collapsed"
    assert verdict.solved is False
    assert "людей" in verdict.reason and "не решение" in verdict.reason
    assert verdict.population_close == 0


def test_famine_that_ends_after_losing_half_the_people_is_a_collapse():
    pops = [10] * 8 + [5] * 12
    food = [5] * 8 + [100] * 12
    h = history(pops=pops, food=food, soil=[0.47] * 20)
    goal = episodes(h, "cell:0:0", "feed")[0]
    verdict = evaluate(goal, h, view(population=5), [], tick=60)
    assert verdict.status == "collapsed"
    assert "больше половины" in verdict.reason


def test_famine_that_ends_with_two_lost_people_is_resolved_with_cost():
    pops = [10] * 8 + [7] * 12
    food = [5] * 8 + [100] * 12
    h = history(pops=pops, food=food, soil=[0.47] * 20)
    goal = episodes(h, "cell:0:0", "feed")[0]
    verdict = evaluate(goal, h, view(population=7), [], tick=60)
    assert verdict.status == "resolved_with_cost"
    assert verdict.solved is True


def test_a_real_recovery_is_resolved_not_punished():
    pops = [10] * 20
    food = [5] * 8 + [100] * 12
    h = history(pops=pops, food=food, soil=[0.47] * 20)
    goal = episodes(h, "cell:0:0", "feed")[0]
    verdict = evaluate(goal, h, view(population=10, food=100), [], tick=60)
    assert verdict.status == "resolved"
    assert verdict.solved is True
    assert "система цела" in verdict.reason


def test_a_famine_that_moved_next_door_is_transferred():
    """People are fine here, the problem simply appeared at the neighbour."""
    pops = [10] * 20
    food = [5] * 8 + [100] * 12
    h = history(pops=pops, food=food, soil=[0.47] * 20)
    goal = episodes(h, "cell:0:0", "feed")[0]
    moved = famine_alert("cell:0:1", since=12)
    v = view(cells=("cell:0:0", "cell:0:1"), population=10)
    verdict = evaluate(goal, h, v, [moved], tick=60)
    assert verdict.status == "transferred"
    assert verdict.solved is False
    assert any("cell:0:1" in r for r in verdict.related)


def test_an_older_problem_next_door_is_not_transfer():
    """A neighbour that was already starving did not catch our famine."""
    pops = [10] * 20
    food = [5] * 8 + [100] * 12
    h = history(pops=pops, food=food, soil=[0.47] * 20)
    goal = episodes(h, "cell:0:0", "feed")[0]
    old = famine_alert("cell:0:1", since=0)
    v = view(cells=("cell:0:0", "cell:0:1"), population=10)
    verdict = evaluate(goal, h, v, [old], tick=60)
    assert verdict.status == "resolved"


def test_an_open_famine_is_active():
    food = [5] * 20
    h = history(pops=[10] * 20, food=food, soil=[0.47] * 20)
    goal = episodes(h, "cell:0:0", "feed")[0]
    verdict = evaluate(goal, h, view(population=10, food=0), [famine_alert()],
                       tick=19)
    assert verdict.status == "active"
    assert verdict.solved is False


def test_soil_goal_resolves_only_with_people_still_there():
    soil = [0.30] * 8 + [0.50] * 12
    h = history(pops=[10] * 20, food=[100] * 20, soil=soil)
    goal = episodes(h, "cell:0:0", "restore_soil")[0]
    verdict = evaluate(goal, h, view(population=10, soil=0.50), [], tick=60)
    assert verdict.status == "resolved"
    assert verdict.soil_close > THIN_SOIL

    # same land recovery, but the people are gone
    h2 = history(pops=[10] * 8 + [0] * 12, food=[100] * 20, soil=soil)
    goal2 = episodes(h2, "cell:0:0", "restore_soil")[0]
    verdict2 = evaluate(goal2, h2, view(population=0, soil=0.50), [], tick=60)
    assert verdict2.status == "collapsed"


def test_soil_below_the_line_stays_an_open_goal():
    soil = [0.20] * 8 + [0.34] * 12  # never crosses THIN_SOIL = 0.35
    h = history(pops=[10] * 20, food=[100] * 20, soil=soil)
    eps = episodes(h, "cell:0:0", "restore_soil")
    assert eps and eps[0].closed_tick is None


def test_a_freshly_closed_goal_is_settling_not_solved():
    pops = [10] * 20
    food = [5] * 8 + [100] * 12
    h = history(pops=pops, food=food, soil=[0.47] * 20)
    goal = episodes(h, "cell:0:0", "feed")[0]
    verdict = evaluate(goal, h, view(population=10), [], tick=goal.closed_tick + 3)
    assert verdict.status == "settling"
    assert verdict.solved is False
    assert "рано" in verdict.reason


# ----------------------------------------------------------------------
# 3. The feed
# ----------------------------------------------------------------------
def test_the_feed_contains_open_goals_before_closed_ones():
    pops = [10] * 10 + [0] * 10
    food = [5] * 10 + [100] * 10
    h = history(pops=pops, food=food, soil=[0.47] * 20)
    v = view(population=0)
    verdicts = goals(h, v, [], tick=19, scopes=["cell:0:0"])
    assert verdicts
    # the feed is computed from the history even when the alert feed is
    # silent; a closed episode after the window is dropped
    assert all(v.goal.kind in ("feed", "restore_soil", "resettle")
               for v in verdicts)
    counts = summary([verdicts[0]])
    assert counts["total"] == 1


def test_goal_episode_kind_and_signal_are_reported():
    g = Goal("feed", "cell:0:0", "famine", 3, 10)
    assert g.duration == 7
    assert g.to_dict()["closed_tick"] == 10
    assert Goal("feed", "cell:0:0", "famine", 3).duration is None


def test_episodes_are_empty_without_history():
    assert episodes(FieldHistory(), "cell:0:0", "feed") == []
