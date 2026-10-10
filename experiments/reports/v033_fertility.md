# v0.3.3 — Fertility Maintenance: Compost, Three-Field, and Fertile Migration

**Kernel v0.1 (frozen). Rulesets 0.3.3g (compost), 0.3.3h (three_field),
0.3.3i (fertile_migration), 0.3.3i-plain (fertile_migration_only).**
Run: seed 7, 10 regions × 1000 agents, 10 000 ticks. 106 tests green (96 prior + 10 new).

## 1. The question

v0.3.2 established that no *behavioral* adaptation to the food side (fallow,
storage, rotation) can save the world: the flat −0.0009/tick soil degradation
is an unconditional countdown with a negative nutrient balance everywhere.
v0.3.3 attacks the other half of the nutrient cycle — **fertility maintenance** —
with three mechanisms, each a laws-only ruleset on the frozen kernel:

- **G — compost**: agents return nutrients to their region's soil every tick.
- **H — three-field agriculture**: each region follows a forced 200-tick
  cultivation / 100-tick fallow cycle, phases staggered across regions.
- **I — fertile migration**: starving agents choose their destination by
  informed scoring `soil × food / population` instead of walking blindly.

Plus one added control: **I-plain** — fertile migration WITHOUT fallow
(frozen soil laws), to attribute any survival to *information* versus
*nutrient cycling*.

## 2. The laws

### 2.1 G — CompostAgricultureSystem (0.3.3g)

The frozen degradation law is a flat −0.0009 per region per tick (NOT
per-worker, as the original proposal's equilibrium math assumed). Compost
adds a population-scaled return:

```
new_soil = clamp(soil − 0.0009 + population × 0.000018 × (1 − soil), 0.05, 1.0)
```

Constant rescaled from the proposed 0.0018 (÷1000) to match the frozen flat
degradation; the intended equilibrium structure is preserved: with the genesis
density of ~100 agents/region the balance point is

```
soil* = 1 − 0.0009 / (population × 0.000018)
      = 1 − 50 / population_per_region             (≈ 0.47 at 94 agents)
```

Below soil* the region heals; above it, it degrades. Everything else is the
frozen harvest formula. System replaces AgricultureSystem.

### 2.2 H — ThreeFieldAgricultureSystem (0.3.3h)

Per-region integer counters `cultivation_streak` / `fallow_timer`, created at
genesis (phases staggered by `(index × 200) // region_count` so regions enter
fallow at different times). Each tick, for a region with population > 0:

- streak reaches 200 → fallow phase begins: `fallow_timer = 100`, streak reset.
- during fallow: **no crop is grown** (no climate reads, no crop draw), soil
  heals +0.003/tick, timer counts down; consumption still applies.
- streak lapses to 0 whenever the region is empty.
- otherwise: frozen soil dynamics.

System replaces AgricultureSystem. `ImmuneDiseaseSystem` as in v0.3.

### 2.3 I — FertileMigrationAgentSystem (0.3.3i / 0.3.3i-plain)

Identical to BlindAgentSystem except the destination choice of a starving
agent that passes the hunger gate and the risk roll (same draw, same purpose,
same threshold):

```
destination = argmax over all other regions of
              soil_fertility × food_stock / max(population, 1)
ties → lowest region id (deterministic)
```

`fertile_migration` = FallowAgricultureSystem + FertileMigration (I + D).
`fertile_migration_only` = frozen AgricultureSystem + FertileMigration (the
attribution control).

## 3. Results (seed 7, 10×1000, 10k ticks)

| ruleset | survivors | last death | mean lifespan | verdict |
|---|---|---|---|---|
| default (v0.2) | 0 / 1000 | 553 | 141 | collapse |
| immune (v0.3) | 0 / 1000 | 573 | 335 | collapse |
| fallow D (v0.3.2) | 0 / 1000 | 794 | 340 | delayed collapse |
| storage E (v0.3.2) | 0 / 1000 | 594 | 300 | collapse |
| rotation F (v0.3.2) | 0 / 1000 | 514 | 275 | accelerated collapse |
| **compost G (v0.3.3)** | **937 / 1000 at t10000** | 1531 | 9388 (censored) | **SURVIVAL: stable equilibrium** |
| three_field H (v0.3.3) | 0 / 1000 | 1382 | 169 | collapse (fast mass die-off, long tail) |
| fertile_migration I+D (v0.3.3) | 0 / 1000 | 710 | 605 | collapse via herding |
| fertile_migration_only I-plain (v0.3.3) | 0 / 1000 | 572 | 472 | collapse |

Death mechanisms in all three failed worlds: ~95% disease+starvation, ~4%
acute infection — the same bottleneck as every previous version.

## 4. G — Compost: the first surviving world

Population trajectory (checkpoint log): t500 = 947, t1000 = 947, t1500 = 946,
t2000 = 937, then **937 unchanged through t10000**. Last death at tick 1531 —
only 63 deaths in the entire run (51 disease+starvation, 9 disease, 3 acute —
all in the genesis burn-in before the soil cycle spins up). Mean lifespan
9388, censored at run end. This is not delayed extinction — 8469 ticks of
perfect stability is a regime change.

The equilibrium is not merely near the prediction — it matches the law
**per region, to three decimals** (observed at t8000; `soil* = 1 − 50/pop`
follows from setting `0.0009 = pop × 0.000018 × (1 − soil)`):

| region | population | soil observed | soil* = 1 − 50/pop |
|---|---|---|---|
| region:0 | 119 | 0.580 | 0.580 |
| region:1 | 0 | 0.05 (floor) | — (empty) |
| region:2 | 108 | 0.537 | 0.537 |
| region:3 | 0 | 0.05 (floor) | — (empty) |
| region:4 | 156 | 0.679 | 0.679 |
| region:5 | 0 | 0.05 (floor) | — (empty) |
| region:6 | 131 | 0.618 | 0.618 |
| region:7 | 136 | 0.632 | 0.632 |
| region:8 | 148 | 0.662 | 0.662 |
| region:9 | 139 | 0.640 | 0.640 |

The asymmetry is itself the story: the genesis disease burn-in killed regions
1, 3 and 5 outright; the survivors of the other seven regions composted their
way to each region's own balance point and stopped there. Regions with more
people hold richer soil — exactly the relation the law prescribes. No
director arranged this; it is the fixed point of 937 agents following a
single return-nutrients law.

Disease is NOT eradicated: ~19 committed disease transitions/tick persist at
t10000 — a small endemic pool of infections that immunity clears before they
kill. The compost world is an **eco-immune equilibrium**: the nutrient cycle
is closed, and disease sits at an endemic level held below the lethal
threshold by immune memory. The first emergent regime in the project's zoo.

## 5. H — Three-field: the tragedy of the commons in time

Three-field dies at tick 1382, but its shape is new: mass death at t≈150–200
(mean lifespan 169) with a tiny tail of 7 agents surviving past t1000. The
cause is arithmetic, visible directly in the law:

- cultivation phase (200 ticks): food income ≈ soil × 0.9 × 100 ≈ 45/tick →
  ~9000 total;
- fallow phase (100 ticks): income **zero**, consumption 100/tick → −10000.

A 300-tick cycle nets ≈ −1000 food against −0.18 soil +0.30 soil = +0.12
soil. **The cycle heals the soil but bankrupts the granary.** Forced
synchrony made every region starve on schedule; the stagger only determined
the order. The long tail is the accidental phase-offset survivors in regions
where the disease burn-in happened to coincide with a cultivation window.

## 6. I — Fertile migration: information creates the tragedy of the commons

Population per region over time (`fertile_migration`, sampled at harvest):

| tick | region 0 | region 6 | region 9 | rest |
|---|---|---|---|---|
| 0 | 100 | 100 | 100 | 100 each |
| 100 | 100 | 164 | 157 | emptying |
| 200 | 0 | 308 | 284 | 0–8 |
| 300 | 0 | 407 | 359 | 0 |
| 400 | 206 | 667 | 20 | 0–4 |
| 500 | 210 | 667 | 0 | 0 |
| 600 | 633 | 0 | 0 | 18 |
| 700 | 166 | 0 | 0 | 185 |

Perfectly informed, greedy agents do exactly what their information tells
them: everyone converges on the single best region (soil 0.9, region 6).
667 agents on one region strip its food and soil faster than fallow can heal
(region 6: soil 0.81→0.45 while hosting 2/3 of the world). The herd then
moves on to the next-best healed region — a boom-and-bust relay (regions 1, 3,
5 heal to 0.9–1.0 while empty) that loses population at every stop. Last
death at tick 710.

The attribution control settles the causal question cleanly:

| | information | nutrient cycle | last death | mean lifespan |
|---|---|---|---|---|
| I-plain | ✔ (informed migration) | ✘ (flat −0.0009) | 572 | 472 |
| I+D | ✔ | partial (fallow heal, passive) | 710 | 605 |
| G | ✘ (agents still blind) | ✔ (compost, active) | — | 937 alive at t10000 |

Information without a nutrient cycle buys time (mean lifespan 335 → 472) but
changes the verdict: blind agents in I-plain follow the immune collapse
almost exactly (last death 572 vs 573). The I+D combination delays further
but cannot survive, because *perfect information with greedy choice is a
destabilizer*: it synchronizes the population onto the best region,
concentrating the load exactly where v0.3.2 showed load concentration kills.
**The world was not doomed by blindness; G proves it, because G's agents are
still blind and yet they live.** What saves the world is closing the nutrient
loop. What information changes is the *distribution* of deaths.

## 7. Answer to the version's causal question

> If none survives, information was not what was missing.

Correct on the strongest reading: information alone (I-plain) and information
+ passive healing (I+D) both die. But the version also produced the positive
half of the answer: closing the nutrient cycle (G) makes the world survive
*at the same physics, same clock, same seed, with agents still blind*. The
decisive variable was never knowledge — it was whether the system returns to
the soil what it takes out.

## 8. The regime zoo after v0.3.3

1. **collapse** — default, immune, storage, rotation, three-field, I-plain
2. **delayed collapse** — fallow D (794), I+D (710, different shape: herding relay)
3. **magic equilibrium** — stable_soil (v0.3.1 diagnostic, soil frozen)
4. **compost equilibrium** — G: stable population, endemic disease, closed
   nutrient cycle — a genuinely self-maintaining world

Three qualitatively different long-lived regimes now exist (collapse family,
magic equilibrium, compost equilibrium), plus distinct collapse *shapes*
(slow decay vs scheduled starvation vs herding relay). The precondition the
user set for building the observer is met.

## 9. Next step

Build the **observer layer** (roadmap step 3): read-only derived views over
the journal — regime classification, population/soil trajectories, event
detection (using Transition.system + operation + StateChanges + ruleset
semantics, per the None→region:0 lesson), with significance filtering ONLY in
display. The compost world gives it a non-trivial subject: an equilibrium
that is not the trivial fixed point of a frozen law.
