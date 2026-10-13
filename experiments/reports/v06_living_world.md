# v0.6 step 2 — the living world: heredity, ruins, senescence

**Kernel v0.1 (frozen). The resolver, the conflict rules and `step()` are
untouched; the research rulesets do not see a single new system.** v0.6 step
2 gives the game ruleset (`player_life`) a world that forgets nothing and
stands still nowhere: agents are *born* with inherited traits, extinct
regions leave *ruins* that survivors can loot, and the old *die*. Everything
below is four new systems (`systems/birth.py`, `systems/ruin.py`,
`systems/exploration.py`, `systems/senescence.py`), a genesis pool
(dormant agent slots + ruin slots, opt-in via ruleset duck-typing), and 19
new tests — **168/168 green**, default world bit-identical to its pinned
v0.2 hashes.

Design provenance: `experiments/proposals/v06_heredity_ruins_design.md`
(approved, with binding refinements U1–U4, O1–O6 and the four nuances).
This report documents what was built, every deviation from the approved
design (three of them, all data-forced), and the one thing the design did
not predict: a quantitative Malthusian law the experiment exposed.

## What "living" means, measured

The experiment is `experiments/v06_living_world.py` (not in the suite: at
~20 ms/tick and 400 entities, a 3600-tick run costs ~80 s). Headline table,
seed 7, 2 regions × 100 agents/region, 3600 ticks:

| config | extinction | births | max gen ever | senescent deaths | explores | ruin activate/collapse |
|---|---|---|---|---|---|---|
| control (senescence inert) | never | 56 | 4 | 0 | 0 | 1 / 1 |
| decision-1 spec (onset 250, max 350) | **t554** | 16 | 3 | 120 | 1 | 4 / 3 |
| long-life (onset 1500, max 2000) | **t2015** | 48 | 4 | 125 | 0 | 3 / 3 |

Every run is deterministic: two worlds under one seed produce identical
state **and** journal hashes (asserted in the suite and in the script).
Ruin counts confirm the oscillation fix (§2): activation events happen once
per extinction transition, never per tick.

## 1 · Heredity (2a): the mechanism works; the drift is one generation, and that is the honest result

`BirthSystem` (priority 30) activates pre-allocated dormant slots. A region
births when: at least one alive agent is older than `MATURITY=20` (O1),
`population < capacity = pop_base × (1 + soil)` (capacity *falls with soil*
— ecological pressure, O1), and per-capita food is above `BIRTH_FOOD_PC_MIN`.
The occasion rolls against `rate = 0.01 + 0.04 × food_surplus` per region
per tick (U1). Slot choice and parent choice are addressable draws over
sorted lists (nuances 2–3). Inheritance (O2): `immune_memory × 0.6 ± 0.05`;
`immunity = 0.30 + 0.4 × parent_memory ± 0.05`; `max_health` mean-reverting
around the 100 baseline ± 5; `risk = 0.7 × parent + 0.3 × fresh ± 0.05`.
Generation depth is a state field (`generation`, U2), never a chain walk.

The drift result, in the framing agreed on review (Decision 2):

```
v0.6 heredity result:
  - Mechanism validated: inheritance formulas exact, generation tracking works
  - Adaptation demonstrated: gen-0 naive (0.0) -> gen-1+ resistant (~0.6) in one generation
  - Plateau explained: three structural causes (immortality, saturation, random parent)
  - Directional climb deferred to v0.7 (requires senescence + selection differential)
  - This is not a failure — it's the honest output of the laws as written
```

Concretely, birth-time `immune_memory` per generation (journal
`agent.birth` transitions; the state-snapshot metric would be
age-confounded): the 3600-tick control run gives gen1 0.59, gen2 0.58,
gen3 0.59, gen4 0.50 (56 births across 4 generations) — a
**one-generation jump from naive 0.0, then a plateau**.
The three structural causes are exactly the ones the review accepted:
saturation (infection memory caps at 1.0 within a lifetime, and the plateau
value 0.6 is the 0.6-heritability fixed point), no selection differential
(random parent, nuance 3 — trait-weighted choice is v0.7+), and generation
shallowing — which is what senescence was added for. Chasing a prettier
10-generation curve by tuning the saturation curve would have been *tuning
toward a result* — the practice v0.6 exists to refuse.

**Deviation (data-forced).** The design's birth gates were calibrated so
tightly that the approved world produced *zero* births in 1800 ticks:
`BIRTH_FOOD_PC_MIN` was lowered 8.0 → 3.0, `FOOD_PC_RICH` 30 → 20, and the
capacity base 0.5 → 1.0 (`capacity = pop_base × (1 + soil)`), because the
compost world's per-capita food at equilibrium sits near 6–15 (below the
design's floor of 8 for most of the run) and a genesis 100-agent region
sat right at the design ceiling (~1.05 × pop_base at soil 0.55) whenever
soil dipped. The gates' *shape* (soil-driven capacity, food-driven rate,
rate cap U1) is exactly as approved.

## 2 · Ruins (2b): a state machine that cannot oscillate

`RuinSystem` (priority 31) owns one slot per region, born dormant. The
first world run exposed a bug the design allowed: activation triggered on
*being* extinct, so a region extinct **and** at zero food activated,
instantly collapsed (floor check) and re-activated — 860 activations and
859 collapses in 1800 ticks. The fix (approved as "fix now, not a design"):
a `was_alive` marker makes activation fire on the **transition into**
extinction, and activation seeds `resource_food = max(10, 0.1 × food_stock)`
so a starved camp still leaves explorable scraps. The full law, as tested:

* **region alive**: note `was_alive`; an active ruin **persists without
  aging** (an ancestral granary kept by the settlement does not rot — and
  a ruin explored down to its floor collapses even in a live region);
* **pop 0 ∧ was_alive**: activate/reset the slot (type derived from region
  state: granary/settlement/camp; `age=0`; reserve seeded; nuance 4 — the
  *same* slot is reused on re-extinction, never a second one);
* **pop 0 ∧ active**: age; collapse past `RUIN_MAX_AGE=1200` or once the
  reserve hits the floor;
* **pop 0 ∧ dormant ∧ not was_alive**: silence (no phantom ruins for never-
  inhabited regions, no re-activation loops).

`resource_food` is written only by activation (RuinSystem) or depletion
(ExplorationSystem) and those provably never collide (activation only fires
on inactive slots, depletion only on active ones). World-scale counts after
the fix: 1–4 activations per 3600-tick run, each one an actual extinction
event — the 860:859 churn is gone, regression-tested
(`test_ruin_extinction_activates_once_then_ages_no_oscillation`).

## 3 · Exploration: mechanism validated under control, natural firing is rare — by design

`ExplorationSystem` (priority 40): an alive agent co-resident with an active,
non-empty ruin rolls `p = clamp(0.02 + 0.10 × risk_tolerance, 0, 0.15)`; a hit
writes the agent's hunger relief (`0.2 × reserve`, in the agent's OWN
transition, reading the RUIN — so a biography query can point at the ruin) and
draws the reserve down by 10 per explorer in one aggregated `ruin.deplete`
(never per-explorer writes: conflict-free by construction).

Decision 3 stands as reviewed: in a healthy compost world ruins mark dead
regions and survivors have no incentive to walk into one, so natural firing
is ~0–1 events per world-run (and when it happens, it does so because a
migrant actually walked into the dying region — the trace exists). The
mechanism is validated by the forced scenario (agents planted in a ruined
region: explore fires, bonus lands in the trace, reserve drains to exactly
zero, the emptied ruin collapses and stays collapsed). Gameplay salience is
phase 4 (player-driven expeditions, ruins that persist across lives);
adjacent-region exploration waits for a topology in v0.7.

## 4 · Senescence: shipped as approved — and the world told us a law

`SenescenceSystem` (priority 25, game-ruleset only): past `SENESCENCE_ONSET=250`
an agent faces `death_prob = (age − onset)/(max − onset) × 0.05` per tick,
capped at `MAX_LIFESPAN=350` (Decision 1's numbers, verbatim). Research
worlds never name the system; the default world's pinned hashes are
untouched; the death write (`alive False`, `health 0`) is an addressable
`agent.senescence` draw. Nobody dies before onset — tested exactly at the
boundary.

Turnover is real: the immortal control keeps 115 gen-0 survivors forever;
with senescence, gen-0 is gone by t500 and the living are gen1–3 (and one
agent who died of old age while carrying a granary in his trace).

What the design did not predict, and the report must state: **any death
pressure at these rates kills the world.** The math is a one-line balance:
a region can birth at `rate ≤ 0.05` per tick (U1, approved), and every
post-lifespan adult dies at `λ = 0.05` per tick — so the sustainable
population is `N_eq = rate/λ ≈ 1 agent/region`, while the compost soil
feedback needs a few dozen mouths to keep fertility above its 0.05 floor.
Any fixed lifespan therefore dooms the cohort-wave: the synchronized genesis
generation ages together, all die inside ~100 ticks, births refill 30× too
slowly, soil crashes, and the famine finishes the world. The sweep confirms
no escape hatch inside the approved knobs (2×100/region, seed 7, 1800 ticks):

| onset/max | population at t1800 | fate |
|---|---|---|
| ∞ (control) | 160 | persists, frozen |
| 400/600 | 0 | wave at ~t600 |
| 600/900 | 0 | wave at ~t900 |
| 1000/1400 | 0 | wave at ~t1400 |
| 1500/2000 | 45 | wave at t2015 |

Per Decision 2's own principle we did **not** calibrate toward a livelier
curve. The finding is the deliverable: *the engine now exposes a
quantitative Malthusian constraint — a living world with turnover needs the
birth ceiling and the death pressure calibrated jointly against the soil
viability floor; that is a v0.6.1 agenda item (pool regeneration, birth-rate
redesign, or a food law with a stronger small-N feedback), not a v0.6 knob
to fudge.* For the game itself the numbers are fine where they matter:
a LIFE session spans ~100–350 ticks (players and their grandparents age
and die inside the window; ruins from the previous life commemorate it).

## Honest footnotes

* One experiment bug worth recording: `create_world(agents=N)` is TOTAL
  agents, not per region — an early sweep ran "2×100" as 2×50 and "7×40"
  as a sub-viable basin, which initially mis-attributed a known small-world
  collapse to senescence. The control run reproducing the pre-senescence
  trajectory exactly (N=160, soil 0.36 @ t1800) is what caught it.
* The design's four ruin types included a "mine" branch derived from
  `metal`/`workers` (O4); the schema has no such fields at extinction, so
  type derives from food stock and soil (granary/settlement/camp) — as
  flagged and adapted during review.
* Ruin `resource_knowledge` exists and is untouched (0.0) until v0.6.1
  gives knowledge a use (O3).
* `player.decision` action 2 ("explore") for the LIFE card (U3) is step 3
  work — this step ships the NPC law; the player action will reuse the same
  transition shape.

## Reproduce

```
python experiments/v06_living_world.py                 # all three configs
python experiments/v06_living_world.py --onset 250 --max-age 350   # one
python -m pytest tests/ -q                             # 168 green, ~80 s
```
