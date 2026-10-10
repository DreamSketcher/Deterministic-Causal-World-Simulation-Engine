"""Scaling the world never shifts existing entities (invariant I8) and the
default world stays bit-identical to the frozen v0.1."""

from __future__ import annotations

from causal_world import create_world


def test_default_world_is_bit_identical_to_v01():
    """Known v0.1.0 fingerprint anchor for seed 42 / 100 ticks."""
    sim = create_world(seed=42, ticks=100)
    assert sim.state.hash().startswith("97d61d4274e4bfb4")


def test_agent_genesis_invariant_under_scaling():
    """Adding more agents/regions must not change agent:0..agent:9 drawn
    attributes: draws are addressable per entity, no sequential stream.
    (The region ASSIGNMENT is topology — i % region_count — and may differ
    when the number of regions changes; what must not shift is anything
    produced by the RNG.)"""
    small = create_world(seed=11)
    large = create_world(seed=11, regions=10, agents=1000)

    fields = ["alive", "infected", "health", "hunger", "immunity", "risk_tolerance"]
    for i in range(10):
        agent = f"agent:{i}"
        for field in fields:
            assert small.state.get(agent, field) == large.state.get(agent, field), (
                f"{agent}.{field} shifted when scaling the world"
            )
        assert small.state.get_source(agent, "health") is not None
        assert large.state.get_source(agent, "health") is not None


def test_region_genesis_invariant_under_scaling():
    small = create_world(seed=11)
    large = create_world(seed=11, regions=10, agents=1000)
    for field in ("temperature_base", "rainfall_base", "soil_fertility", "disease_base"):
        assert small.state.get("region:0", field) == large.state.get("region:0", field)
        assert small.state.get("region:1", field) == large.state.get("region:1", field)


def test_extensive_food_buffer_only_beyond_default_density():
    """Food scales with agents-per-region only beyond the default density,
    so the default world is untouched."""
    default = create_world(seed=11)
    doubled = create_world(seed=11, regions=2, agents=20)
    # 10 agents per region now: buffer doubles.
    ratio = doubled.state.get("region:0", "food_stock") / default.state.get(
        "region:0", "food_stock"
    )
    assert abs(ratio - 2.0) < 1e-9
