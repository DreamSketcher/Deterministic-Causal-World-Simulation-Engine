"""v0.12, шаг 2a — карточка мира строится за один проход.

Профиль (шаг 1) показал, что `StateView.from_state` квадратичен:
4.6 с на 500 живых и 17.8 с на 1 000. Причина — не модель, а
реализация: для каждой сущности вызывался `fields_of`, а он сканирует
всё состояние.

Здесь проверяется ровно одно: **новый проход даёт тот же словарь**, что
и старый. Это и есть ворота эквивалентности для оптимизации
представления: внутренняя структура может измениться, значения,
провенанс и набор ключей — нет.
"""

from __future__ import annotations

from causal_world import create_world
from causal_world.observer.situation import StateView
from causal_world.world.rules import get_ruleset


def _slow_from_state(state) -> dict:
    """The old implementation, kept here as the reference to compare to.

    It is deliberately the same code the library used before the fix: a
    test that compared the new view to itself would prove nothing.
    """
    values = {}
    for entity in state.entities():
        for name in state.fields_of(entity):
            values[(entity, name)] = (
                state.get(entity, name),
                state.get_source(entity, name),
                None,
            )
    return values


def _world(agents: int = 54):
    sim = create_world(
        seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
        regions=2, agents=agents,
    )
    sim.run(3)
    return sim


def test_the_one_pass_view_is_the_same_mapping() -> None:
    sim = _world()
    view = StateView.from_state(sim.state)
    assert view._values == _slow_from_state(sim.state)


def test_it_keeps_every_key_including_the_v011_fields() -> None:
    sim = _world()
    view = StateView.from_state(sim.state)
    # v0.11 fields on a cell are part of the card; a missing key would
    # silently become None in the UI, which is exactly the kind of lie
    # this repository refuses.
    cells = view.entities_with_prefix("cell:")
    assert cells
    for name in ("resettled_in", "resettled_out", "resettle_state"):
        for cell in cells:
            if sim.state.has(cell, name):
                assert (cell, name) in view._values


def test_reading_the_view_does_not_touch_the_state() -> None:
    sim = _world()
    before_hash = sim.state.hash()
    before_tick = sim.state.tick
    view = StateView.from_state(sim.state)
    view.entities_with_prefix("cell:")
    view.get("cell:0:0", "population")
    assert sim.state.hash() == before_hash
    assert sim.state.tick == before_tick
