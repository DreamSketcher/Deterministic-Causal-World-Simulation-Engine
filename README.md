# Deterministic Causal World Simulation Engine

> **CAUSAL KERNEL v0.1 — frozen** (tag `v0.1.0`). The kernel architecture is
> not extended silently; anything considered redundant goes through an
> explicit proposal first. v0.2 added observability and scale around the
> frozen kernel; v0.3 adds a **ruleset variant** (immune memory) — a change
> of laws, never of kernel. See the [roadmap](#roadmap).

A minimal **executable kernel** for an artificial world in which every
change is a recorded, atomic, causally-explainable **Transition**.

```
seed + kernel version + ruleset version + initial state + deterministic laws
                ↓
        identical world, every time
```

The same `world_seed` + ruleset + initial conditions always produce a
bit-identical run; causality is not declared by hand — it is reconstructed
mechanically from recorded reads and provenance.

---

## Core principles

1. **WorldState changes only through committed transitions.** No system,
   observer, or tool writes state directly. The state object is *sealed*;
   only the engine's commit step opens the seal.
2. **Transitions are atomic.** Every write in a transition commits, or none
   do. `infected F→T` + `health 73→58` can never apply halfway.
3. **One immutable Snapshot per tick.** All systems compute from the same
   frozen view (data **and** provenance). Same-tick writes become visible
   only on the next tick.
4. **Addressable deterministic randomness.** A draw is a pure function of
   `(world_seed, rng_version, tick, entity, purpose, index)` via BLAKE2b.
   There is no global RNG stream, so results never depend on call order,
   iteration order, or how many other entities exist.
5. **Causality is data.** `Transition A` writes `X`; `Transition B`'s
   snapshot read of `X` records `source_transition = A` — hence `A → B`.
   Events, biographies, statistics and narratives are *derived* observer
   views, never inputs to the physics.

## Architecture

```
┌─────────────────────────────────────────────┐
│              OBSERVER LAYER                 │   read-only
│  EventView · Statistics · Observability     │────────────────┐
└──────────────────────┬──────────────────────┘               │
                       │                                      │
┌──────────────────────▼──────────────────────┐               │
│               CAUSAL INDEX                  │◄──────────────┘
│  transition history · provenance index      │
│  reverse dependency index · trace_back      │
└──────────────────────┬──────────────────────┘
┌──────────────────────▼──────────────────────┐
│               SIMULATION                    │
│  Snapshot → Plan → Resolve → Commit → Index │
└──────────────────────┬──────────────────────┘
┌──────────────────────▼──────────────────────┐
│                 SYSTEMS                     │
│  ClimateSystem · AgricultureSystem          │
│  DiseaseSystem · AgentSystem                │
└──────────────────────┬──────────────────────┘
┌──────────────────────▼──────────────────────┐
│                  KERNEL                     │
│  WorldState · Snapshot · Transition         │
│  StateRead · StateChange · RandomDraw       │
│  RandomSource · PurposeRegistry · Validation│
└─────────────────────────────────────────────┘
```

Layers point strictly downward. The observer layer has no write capability:
`WorldState` is sealed and systems only ever receive frozen snapshots.

### Project layout

```
src/causal_world/
├── kernel/        state.py snapshot.py transition.py random.py
│                  validation.py canonical.py errors.py
├── simulation/    engine.py resolver.py journal.py archive.py
├── systems/       base.py climate.py agriculture.py disease.py agents.py
│                  immune_disease.py diagnostic.py food.py fertility.py
├── causal/        index.py trace.py
├── observer/      events.py statistics.py observability.py
│                  journal.py budget.py series.py deaths.py regime.py
│                  compare.py compress.py        (v0.4, read-only)
├── world/         generator.py rules.py
├── cli.py         __main__.py
tests/             12 test modules + helpers.py (121 tests)
experiments/       survival.py compare_rulesets.py observer_demo.py
                   reports/   (v0.2 … v0.4 write-ups)
```

## The tick loop

```
BEGIN TICK → SNAPSHOT → PLAN → RESOLVE → COMMIT → INDEX → END TICK
```

* **SNAPSHOT** — one frozen copy of `(data, provenance)` shared by all systems.
* **PLAN** — each system gets `compute(snapshot, rng, context)` and returns
  *proposed* transitions. Systems never see each other's current-tick writes.
* **RESOLVE** — every proposal is validated (tick consistency, old-value
  consistency, type schema, ruleset invariants), then write-conflicts are
  settled deterministically.
* **COMMIT** — the **only** place `WorldState` changes: all writes of each
  surviving transition are applied together with their provenance.
* **INDEX** — every transition (committed **and** rejected) goes to the full
  journal; the causal index updates provenance and dependency edges.

### Transition ids and conflict resolution

Transition ids are assigned from the **canonically sorted** set of a tick's
proposals (content-based key), never from system execution order. Conflicts
(two transitions writing the same `(entity, field)`) are resolved by an
explicit, deterministic rule:

```
1. higher transition priority wins;
2. tie → higher system priority wins;
3. tie → lower transition id wins.
```

Losers are **rejected wholesale** — a transition is never rewritten into a
different transition ("A requested 70, give A 50" is forbidden). If a model
needs partial allocation, it must be expressed as a separate transition.

## Quickstart

```bash
pip install -e .          # Python >= 3.10, stdlib only
python -m causal_world run --seed 42 --ticks 100
python -m causal_world run --seed 42 --ticks 100 --stats
python -m causal_world trace --seed 42 --ticks 100 --transition 94
```

`run` prints the world summary plus the **run fingerprint**:

```
World seed:       42
Ruleset:          0.1.0
RNG:              blake2b-v1
...
Final state:      97d61d4274e4bfb4…
Transitions:      2470
Rejected:         43

Fingerprint:
{ "seed": 42, "kernel_version": "0.1.0", "ruleset_version": "0.1.0",
  "rng_version": "blake2b-v1", "ticks": 100,
  "initial_state_hash": "…", "final_state_hash": "…" }
```

`trace` prints one transition exactly as recorded, plus its backward causal
tree — inputs with their source transitions, random realizations, writes:

```
T94 DiseaseSystem.disease.infect  [COMMITTED] tick=2

READ
  agent:9.health = 91.183948 ← T48
  agent:9.hunger = 0.102199 ← T58
  agent:9.immunity = 0.359363 ← T58
  region:1.disease_load = 0.162454 ← T66
RANDOM
  disease.infection@agent:9#0 = 0.000378
  threshold = 0.037926
  outcome = true
WRITE
  agent:9.health: 91.183948 → 79.661896
  agent:9.infected: false → true
```

That is the whole explanation of "agent 9 got infected": no narrative was
stored — it is mechanically reconstructed from the journal.

## The world (MVP)

* **2 regions**, **10 agents**, generated deterministically from the seed
  through the addressable RNG (`genesis.attribute` purposes).
* `ClimateSystem` — mean-reverting temperature/rainfall + addressable noise.
* `AgricultureSystem` — `climate × soil × workers × crop_variance = harvest`,
  then `food + harvest − spoilage − consumption`.
* `DiseaseSystem` — environmental disease load (reservoir + prevalence),
  per-agent infection roll → one **atomic** transition
  (`infected F→T`, `health X→X−damage`, possibly `alive T→F`), recovery roll.
* `AgentSystem` — census (population/workers), metabolism (hunger/immunity),
  health/death, risk-tolerance-gated migration.

Field ownership is designed so systems rarely collide, but when they do
(e.g. an infection and a health update targeting the same agent in one
tick), the resolver settles it deterministically — infection transitions
carry transition priority 2.

## Critical invariants

Enforced by construction and by the test suite:

* **I1.** WorldState changes only through committed transitions
  (`WorldState` is sealed; `state.set()` outside a commit raises).
* **I2.** Every committed write belongs to exactly one committed transition.
* **I3.** A transition is atomic — all writes or none.
* **I4.** Every system computes from the same snapshot of a tick.
* **I5.** Snapshot contains data **and** provenance.
* **I6.** Reads reference provenance from their snapshot — never from the
  live index.
* **I7.** Randomness is addressable and deterministic.
* **I8.** Randomness does not depend on execution order, iteration order, or
  the presence of other entities (no global RNG stream exists).
* **I9.** Conflict resolution is deterministic (explicit priority rule,
  canonical ordering everywhere).
* **I10.** Rejected transitions never modify world state — but they remain
  in the full journal with their reason.
* **I11.** Observability cannot modify simulation (read-only adapters only).
* **I12.** Events are derived from primitive state changes (`EventView`),
  never fundamental.
* **I13.** Causal relationships are reconstructed from data dependencies —
  no hand-written `causes=[...]` anywhere.
* **I14.** Same seed + same versions + same initial state = same run
  (identical state hash, journal hash, fingerprints, causal traces).
* **I15.** The kernel contains no narrative semantics.

## What this project deliberately does NOT do

* No story generation: no plot points, dramatic events, protagonists, quests.
* No hidden director: no `make_interesting()`, `increase_drama()`,
  `ensure_conflict()`, `spawn_event_for_narrative()`.
* No manual causality: no `causes=["hunger", "disease"]` lists.
* No global RNG: no `random.random()` / sequential generators in the
  simulation.
* No state mutation from systems or observers: no `state.set(...)` inside
  `compute()`.
* No LLM anywhere: an LLM narrative layer would be a pluggable *observer
  adapter* over the journal/traces — never a kernel dependency.
* No significance thresholds in the kernel: every transition is recorded;
  filtering happens only in the observer layer.

## Versioning

| component | value | change means |
|---|---|---|
| `kernel_version` | `0.1.0` | engine mechanics changed |
| `ruleset_version` | `0.1.0` (`default`) / `0.3.0` (`immune`) | world laws / schema / purposes changed |
| `rng_version` | `blake2b-v1` | draw algorithm changed |

Changing the RNG algorithm or the semantics of a purpose is a **ruleset**
change. The run fingerprint records all versions plus initial/final state
hashes, so "same world" is distinguishable from "same seed, other ruleset".

## Tests

```bash
python -m pytest          # 96 tests
```

| spec test | where |
|---|---|
| #1 deterministic replay (state, journal, traces, fingerprint) | `test_determinism.py` |
| #2 random addressability (order, removal) | `test_random.py` |
| #3 snapshot isolation (18 vs 25) | `test_snapshot.py` |
| #4 provenance (`soil 0.6→0.7`, read source = writer) | `test_provenance.py` |
| #5 same-tick provenance (reads pre-snapshot writer) | `test_provenance.py` |
| #6 atomicity on rejection (both variables checked) | `test_atomicity.py` |
| #7 successful atomicity (both writes + provenance) | `test_atomicity.py` |
| #8 no magic state changes (journal replay proof) | `test_atomicity.py` |
| #9 divergence across seeds 1–5 | `test_simulation.py` |
| #10 system order independence | `test_simulation.py` |
| #11 causal reconstruction via `trace_back` | `test_simulation.py` |
| #12 LLM independence (stdlib-only import audit) | `test_simulation.py` |

Plus conflict-resolution tests (`test_conflicts.py`): explicit winner rule,
order independence, no value rewriting.

Plus the v0.3 ruleset contract (`test_immune_ruleset.py`): default world
bit-identity pinned, deterministic replay of the immune world, atomic
`immune_memory` growth with provenance, same addressable draw stream as
the baseline, schema invariant enforced by the ruleset.

Plus the v0.3.1 surgery checks (`test_diagnostic_rulesets.py`): each
diagnostic ruleset cuts exactly its link — no infection writes health in
`iron_health`, soil is never written after genesis in `stable_soil`,
infection reads no hunger and immunity ignores hunger in
`no_hunger_immunity`, no disease operations in the control — and every
variant replays bit-identically on the shared draw stream.

## v0.2 — Causal survival experiment

The next step is deliberately **not** "more systems". The kernel is frozen;
the experiment scales the *same* world and compares two kinds of
explanation: **statistical regularity** (correlations) vs **individual
causality** (mechanical death traces).

```bash
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 \
    --ticks 10000 --db runs/survival_seed7.db \
    --report experiments/reports/survival_seed7.md
```

What v0.2 adds **around** the frozen kernel:

* `SqliteArchive` — one SQLite file serving as BOTH the journal and the
  causal index. Identical semantics and the *identical journal hash*
  definition as the in-memory stores (verified by test), constant ~30 MB
  RAM at any run length.
* Generator scaling: `regions`/`agents` parameters. Addressable RNG
  guarantees existing entities never shift when the world grows (I8); the
  default 2×10 world remains bit-identical to v0.1. Food buffer is an
  extensive initial condition and scales with per-region population.
* `experiments/survival.py` — per-agent survival records
  (`agent_id, birth_tick, death_tick, lifespan, death_transition`),
  lifespan distribution, Pearson/Spearman correlations, and a mechanical
  death-mechanism classification built purely from `trace_back`
  (acute infection / epidemic disease / starvation).
* 61 tests, including memory↔archive parity and scale-invariance tests.

Read the results: [`experiments/reports/`](experiments/reports/).

### First results (seed 7, 10 regions × 1000 agents × 10 000 ticks)

Simulation: **689 s**, analysis from the committed archive: **~5 s**,
peak RAM ≈ 30 MB, archive ≈ 4 GB (`runs/`, gitignored, regenerable).

1. **Ruleset 0.1.0 is not viable at scale — and the kernel proves it.**
   The population goes extinct by tick 553 (median lifespan 82 ticks,
   no censoring: all 1000 deaths traced). Mechanically, every death is
   disease-mediated: `disease` 51.2 %, `disease+starvation` 37.2 %,
   `acute_infection` 11.6 %. The cause is structural: there is **no
   immune memory** — recovered agents are immediately susceptible again,
   and at high density the disease never stochastically dies out, so
   reinfection cycles (~36 health each) grind the population down. In the
   small 2×10 world the same laws survive because the disease *can* go
   locally extinct — a genuine scale-emergent property, found by running,
   not by arguing.
2. **Statistical regularity vs individual causality.** Pearson:
   `infection_count` +0.89, `avg_social_density` −0.90, `migration_count`
   +0.41 with lifespan. The first is a pure **time-at-risk confound**
   (longer life ⇒ more exposure opportunities) — the report flags such
   variables explicitly. Migrants live longer on average (194 vs 106
   ticks) **but die of different mechanisms**: stayers die mostly of
   pure/acute disease (99 acute, 443 disease, 57 with starvation),
   migrants mostly with a starvation component (17 / 69 / 315). Same
   observable, different causal pathways — exactly the comparison the
   experiment exists for.
3. **Every death has a mechanical explanation.** Example from the report:
   `agent:0` died at tick 73; the trace shows recovery at tick 62, then
   infection at tick 65 (roll `0.052457 < threshold 0.059782` at
   `disease_load = 0.439`), then health erosion 70 → 30 → 19 → … → 0.
   No narrative was stored — the explanation is reconstructed.

A ruleset variant with immune memory is the obvious v0.3 candidate — it
is proposed, not silently introduced: the v0.1 laws are frozen.

## v0.3 — Immune memory: a different law, same kernel, same dice

Implemented as a **separate ruleset** (`"0.3.0"`, selectable via
`--ruleset immune` in the CLI and the experiment runner), not as a kernel
change. `src/causal_world/kernel/` is byte-identical to tag `v0.1.0`, and
the default world stays **bit-identical** to v0.2 (same state hash *and*
journal hash — pinned in `tests/test_immune_ruleset.py`).

The new law, in full:

* new agent field `immune_memory ∈ [0, 1]`, naive (`0.0`) at genesis —
  injected through a duck-typed `extra_genesis_fields` hook, so the
  default generator path is untouched;
* infection probability scaled by `1 − 0.85·memory`;
* infection damage attenuated by `1 − 0.60·memory`;
* every infection teaches: `+0.35` memory, written **atomically inside the
  same transition** that writes `infected` and `health`;
* recovery probability gains `+0.20·memory`.

Design point — **same dice**: the immune world draws from the exact same
addressable stream as ruleset 0.1.0 under the same seed (same purposes,
same `(tick, entity, purpose, index)` addresses, same `rng_version`).
Every divergence between the two runs is therefore attributable to the
laws alone.

### Result (seed 7, 10 regions × 1000 agents × 10 000 ticks)

Simulation 697 s, analysis ~9 s; full report:
[`experiments/reports/survival_seed7_immune.md`](experiments/reports/survival_seed7_immune.md).

| quantity | ruleset 0.1.0 | ruleset 0.3.0 |
|---|---|---|
| extinction tick | 553 | **573** |
| mean lifespan | 141 | **335** |
| median lifespan | 82 | **396** |
| dominant death mechanism | `disease` 51.2 % | `disease+starvation` 95.4 % |
| acute infections | 11.6 % | 3.9 % |
| corr(density, lifespan) | **−0.90** | **+0.68** |

Three findings:

1. **Memory changes the trajectory, not the verdict.** Mean lifespan more
   than doubles and reinfection damage collapses, but at this density the
   population still goes extinct — only ~20 ticks later. One law is not
   enough; the collapse is structural (endemic load + food pressure), not
   a single-mechanism failure.
2. **The death mechanism mix flips.** Acute single-infection deaths almost
   vanish (11.6 % → 3.9 %): memory blunts damage below lethality. Almost
   everyone now dies in a slow `disease+starvation` chain (37.2 % →
   95.4 %) — immune agents survive each infection but are worn down across
   many of them while the food base is under pressure.
3. **A correlation reverses sign between rulesets.** Social density is
   nearly perfectly lethal in the baseline (−0.90) and *positively*
   correlated with lifespan in the immune world (+0.68). Same observable,
   same seed, same dice — opposite statistical story, because the causal
   structure behind it changed. This is exactly why the project separates
   per-death mechanical traces from population statistics.

Every death in both runs has a trace; in the immune world the traces show
`immune_memory` as a causal input of the killing infection (e.g.
`agent:102`: memory 0.7 read at the tick-79 infection that finished it).

## v0.3.1 — structural diagnosis: which link is the bottleneck?

The immune world still collapsed (tick 573 vs 553 — noise). Four more
laws-only rulesets, each severing exactly one link of the presumed spiral,
same seed and scale. Full write-up:
[`experiments/reports/v031_diagnosis.md`](experiments/reports/v031_diagnosis.md).

| measure | 0.1.0 | 0.3.0 immune | A: no infection damage | B: no soil depletion | C: no hunger→susceptibility | control: no disease |
|---|---|---|---|---|---|---|
| survivors | 0/1000 | 0/1000 | 0/1000 | **950/1000** | 0/1000 | 0/1000 |
| extinction tick | 553 | 573 | 573 | — | 573 | 573 |
| median lifespan | 82 | 396 | 407 | 4000¹ | 405 | 407 |
| dominant mechanism | disease | dis+starv | dis+starv | (50 early deaths) | dis+starv | **starvation** |

¹ Censored at the 4000-tick run (archive size limit); last death at tick
83, then 3917 ticks with zero deaths.

Three results define the stage:

1. **The collapse clock ignores the disease variables.** Four rulesets —
   full memory, zero infection damage, severed hunger↔susceptibility loop,
   and *no pathogen at all* — go extinct on the **same tick (573)** with
   near-identical lifespan distributions. In the no-disease control every
   death traces to pure starvation.
2. **Stop the soil countdown and the world survives.** Soil fertility in
   the frozen laws depletes unconditionally (−0.0009/tick, floor 0.05,
   no restoration). With that one write removed, 950/1000 agents are alive
   at run end — disease fully active, but no longer lethal.
3. **The spiral is real but not the bottleneck.** The
   infection→health→hunger→susceptibility loop shapes *how* agents die
   (the mechanism mix); the *time* of collapse is set by a terminal
   abiotic resource. Also found while cutting: the proposed
   "health→labor→harvest" link never existed — harvest already ignores
   health; the real food-side link was the soil clock.

The bottleneck is the soil countdown. The next experiments were the food
side (v0.3.2) and the fertility side (v0.3.3) — mechanisms *within* the
laws instead of removing the clock — which produced five genuinely
different regimes to compare, and with them the need for the observer.

## v0.3.2 — living WITH the soil clock: three food mechanisms

The clock stays; three laws-only rulesets (on top of immune memory) test
whether the population can adapt around it. Full write-up:
[`experiments/reports/v032_food.md`](experiments/reports/v032_food.md).

| ruleset | law | extinction tick | vs immune (573) |
|---|---|---|---|
| D `fallow` | abandoned regions recover +0.0015/tick | **794** | delayed |
| E `storage` | stock-dependent spoilage (tiny stocks barely rot, surpluses rot at 4 %) | 594 | ≈ same |
| F `crop_rotation` | stable labor load degrades 50 % faster, fluctuating load rests the soil | **514** | *earlier* |

None survives, and each failure is informative:

1. **D produced the first self-generated spatial pattern** — the
   population concentrated into 2–3 regions while abandoned regions
   healed to full fertility (no director), deaths even paused between
   waves — but migration is a hunger-gated random walk, so the healed
   land was never recolonized. A delay, not a rescue.
2. **E proves the collapse is an average deficit, not a peak deficit** —
   smoothing spoilage changes nothing when the soil no longer produces.
3. **F shows a feedback that activates only after the crisis is not a
   stabilizer** — while everyone farms, the load is stable, the penalty
   sits at maximum, and degradation runs 50 % faster.
4. **The arithmetic closes the case.** Per-capita harvest < consumption
   below soil ≈ 0.38 (typical climate); the frozen clock reaches that in
   ~190 ticks from genesis and floors at 0.05. No mechanism in this
   family adds fertility *where farming happens*, so survival is decided
   by the degradation rate itself — the next experiment is a maintenance
   mechanism there (still a ruleset, kernel untouched).

Tests: 87 → **96** (`tests/test_food_rulesets.py` pins each law exactly:
fallow recovery, spoilage arithmetic, the rotation statistic and penalty,
plus replay/draw-stream/bit-identity contracts).

## v0.3.3 — closing the nutrient loop: the first surviving world

Three fertility-maintenance rulesets on the frozen kernel, plus an
attribution control. Full write-up:
[`experiments/reports/v033_fertility.md`](experiments/reports/v033_fertility.md).

| ruleset | law | outcome |
|---|---|---|
| G `compost` | soil gets back `population × 0.000018 × (1 − soil)`/tick | **937/1000 alive at t10000 — stable equilibrium** |
| H `three_field` | forced 200-tick cultivation / 100-tick fallow cycle, staggered phases | extinct t1382 (mass die-off ≈t170, tiny tail) |
| I `fertile_migration` | informed destination choice `soil × food / pop` + fallow | extinct t710 (herding relay) |
| I-plain `fertile_migration_only` | same information, frozen soil laws | extinct t572 (≈ immune baseline) |

- **G is the first self-maintaining world.** Last death at tick 1531,
  population locked at 937 afterwards; each inhabited region's soil sits
  at its analytically predicted balance point `1 − 50/population` (agree-
  ment to three decimals per region);
  disease persists as a small endemic pool that immune memory holds below
  the lethal threshold. Same physics, same clock, same seed, agents still
  blind — the only change is that what is taken out of the soil is
  returned to it.
- **H heals the soil but bankrupts the granary**: a 300-tick cycle nets
  +0.12 soil but ≈ −1000 food (100 fallow ticks of zero harvest at full
  consumption). Forced synchrony starves every region on schedule.
- **I proves information is not what was missing.** Perfectly informed,
  greedy agents converge on the single best region (667/1000 at peak),
  strip it, and relay booms-and-busts across the map until extinction —
  the tragedy of the commons in space. With frozen soil laws (I-plain)
  the same information reproduces the immune collapse almost exactly.

Verdict: the decisive variable was never knowledge — it is whether the
system returns to the soil what it takes out.

Tests: 96 → **106** (`tests/test_fertility_rulesets.py`: compost balance
point and floor, three-field flip/fallow/countdown mechanics and phase
stagger, informed destination choice with tie-break, attribution-control
parity, replay contracts).

## v0.4 — the observer: budgets, regimes, causal comparison

The read-only layer that turns the journal into the world's balance
sheet. No new laws, no new systems, no write capability — `JournalView`
opens archives `mode=ro`. Full write-up:
[`experiments/reports/v04_observer.md`](experiments/reports/v04_observer.md).

| layer | question | module |
|---|---|---|
| L1 CausalBudget | who put how much into each variable, and took out? | `observer/budget.py` |
| L2 RegimeClassifier | collapse / equilibrium / oscillation / decline? | `observer/regime.py` |
| L3 CausalComparator | why does regime A differ from regime B? | `observer/compare.py` |
| L4 NarrativeCompressor | one causal trace → human text (no LLM yet) | `observer/compress.py` |

- **L2 classifies from derived series only** (population/soil replayed
  from committed writes; no ruleset knowledge): immune → COLLAPSE t573,
  fertile_migration → COLLAPSE t710 with *recovering* soil, compost →
  EQUILIBRIUM — the three regimes distinguished by shape, not by labels.
- **L1 answers the v0.3.3 verdict in one line**: the immune soil budget
  has inflows `(none)`, net −0.57 to the 0.05 floor (only 639 of 10 000
  soil writes change anything — the floor turns the rest into no-ops);
  the compost budget balances around zero in the equilibrium window.
- **L3 finds the single structural difference** between 0.3.0 and G:
  regime G has a fertility inflow that 0.3.0 lacks. Because compost
  shares the frozen harvest transition, the difference lives at the
  *system* level (`CompostAgricultureSystem` vs `AgricultureSystem`),
  which the comparator reports as-is.
- **Q5 quantified**: in the informed-migration world 939/1000 agents
  make 18 772 moves with destination entropy 1.70 bits and a 43.7 %
  share for the top region — herding, measured. The compost world has
  zero migrations: the hunger gate never opens.
- **CLI**: `python -m causal_world observe --db runs/x.db --classify
  --budget region:4 soil_fertility [--compare-db y.db] [--explain-death
  agent:7]`.

Tests: 106 → **121** (`tests/test_observer.py`: budget arithmetic,
SQL≡Python parity, read-only file-hash guarantee, synthetic + archived
regime classification, no-ruleset-knowledge guarantee, comparator,
migration entropy, template/LLM-hook compression).

## Roadmap

```
v0.1  Deterministic causal kernel            (frozen, tag v0.1.0)
v0.2  1000 agents / 10k ticks survival run
v0.3  Immune-memory ruleset variant          (this branch — laws-only
      proposal implemented on the frozen kernel, same draw stream)
v0.3.1  Structural diagnosis: 4 sever-one-link rulesets → the collapse
      bottleneck is the soil countdown, not the disease spiral
v0.3.2  Living WITH the clock: fallow / storage / rotation — none saves
      the population; survival is decided by the degradation rate
v0.3.3  Closing the nutrient loop: compost produces the first surviving
      world; information (fertile migration) only reshapes the collapse
v0.4  Observer: causal budgets, regime classifier, comparator,
      narrative templates — read-only, no LLM
v0.5  Causal query engine
v0.6  Biography generator
v0.7  LLM as causal-trace interpreter (observer adapter only)
v0.8  100k+ agents: memory layout, sparse state, batching,
      spatial partitioning, parallel execution, compressed provenance
v1.0  Large artificial world
```

Order matters: while the system is small we can still *prove* its
fundamental properties. New systems, economy, culture or an LLM come only
after each stage's experiment has been run.
