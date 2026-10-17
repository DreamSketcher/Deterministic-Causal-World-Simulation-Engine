# Deterministic Causal World Simulation Engine

> **CAUSAL KERNEL v0.1 — frozen** (tag `v0.1.0`). The kernel architecture is
> not extended silently; anything considered redundant goes through an
> explicit proposal first. v0.2 added observability and scale around the
> frozen kernel; v0.3 adds a **ruleset variant** (immune memory) — a change
> of laws, never of kernel; v0.4–v0.5 add a strictly **read-only** observer
> and query engine over the recorded journal. See the [roadmap](#roadmap).

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
├── query/         index.py query.py             (v0.5, read-only cache)
├── world/         generator.py rules.py
├── cli.py         __main__.py
tests/             35 test modules + helpers.py
experiments/       survival.py compare_rulesets.py observer_demo.py
                   query_demo.py _regen_archive.py
                   reports/   (v0.2 … v0.5 write-ups)
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
python -m pytest          # 383 tests
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

> **Kernel footnote (added v0.6 — freeze honesty).** v0.2 made exactly
> two edits inside `src/causal_world/kernel/`, both *hash-neutral*,
> neither architectural: an **added** `parse_canonical_token()` helper in
> `canonical.py` (inverse of `canonical_token`, for archive payload
> round-trips; currently zero callers) and `slots=True` on the four
> transition dataclasses in `transition.py` (memory optimization for the
> 1000-agent scale-up). The hashing path (`canonical_token`,
> `state_payload`, `sha256_hex`, journal hashing) is byte-unchanged.
> **Empirically verified (v0.6):** the default world (seeds 42 and 7,
> 2×10, 100 ticks) run on a checked-out `v0.1.0` kernel and on HEAD
> produces **bit-identical** `state_hash` *and* `journal_hash` (seed 42
> equals the pinned `DEFAULT_*_HASH` in `tests/test_immune_ruleset.py`).
> Reproduce: `git diff v0.1.0 HEAD -- src/causal_world/kernel/`. So the
> precise claim is *architecturally frozen and behaviorally identical to
> v0.1.0* — not literally byte-identical.

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
change. `src/causal_world/kernel/` is architecturally frozen —
*behaviorally identical* to tag `v0.1.0` (its only two diffs are the
hash-neutral v0.2 edits, see the kernel footnote in the v0.2 section) —
and the default world stays **bit-identical** to v0.2 (same state hash
*and* journal hash — pinned in `tests/test_immune_ruleset.py`, and
re-verified in v0.6 against a checked-out `v0.1.0` kernel).

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

## v0.5 — CausalQuery: from five answers to any question

v0.4 hard-coded five questions. v0.5 turns the journal into an indexed,
composable, **streaming** query API so the *next* question is a one-liner,
not a new module. Still read-only: the archive stays `mode=ro` and its
SHA-256 is unchanged by indexing + every query
(`test_archive_untouched_by_indexing`); the index lives in a separate
derived cache DB. Full write-up:
[`experiments/reports/v05_query_engine.md`](experiments/reports/v05_query_engine.md).

```
JournalView (mode=ro) -> QueryIndex (lazy cache) -> CausalQuery (builder) -> generators
```

- **Reuse + add.** The archive already persists `history`,
  `dependents`, and `(operation,status)`; QueryIndex ATTACHes them
  read-only and adds only `idx_writes` (entity,field→delta),
  `idx_reads` (source→reader, refined by entity+field), `idx_entity`
  (entity→timeline). Build is a **single SQL pass** (`INSERT..SELECT` +
  `json_each`), incremental by `last_tid`, keyed on *world identity*
  (seed/sizes/ruleset, not file name) — a longer re-run of the same
  world extends the cache, never rebuilds.
- **Lazy indexes.** `idx_reads` is ~50× the transition count and only
  needed for causal closures; `build(include_reads=False)` gives a
  writes-only cache (compost: 1.4 GB vs 5 GB full) that still answers
  budget / profile / entropy / writers.
- **Five primitives.** filters (`system`/`operation`/`entity`/`field`/
  `writes_to`/`ticks`/`committed_only`), closures (`caused_by` =
  downstream, `caused` = upstream), `trace(tid, direction, depth)`,
  aggregations (`budget`/`count`/`entropy`/`delta_profile`), and
  `execute()` — a generator that keyset-paginates and hydrates one page
  at a time, so a 19 GB journal is never a Python list.
- **The three v0.4 mandates, met.** (1) *Drill to the write level*:
  `delta_profile` separates `CompostAgricultureSystem.harvest`
  (equilibrium mean **+8.1e-6**, all-positive — soil recovery) from
  `AgricultureSystem.harvest` (**−0.5745** net, depletion) by delta
  sign, not name. (2) *L1 to 4 decimals through the query path*:
  `budget()` == observer L1 to 1e-12, full and windowed. (3) *Emergent
  comparisons made trivial*: migration entropy **3.105** bits (blind,
  10 destinations) vs **1.699** bits (informed, 5 destinations, 43.7 %
  top region) — the v0.4 numbers, now one line each.
- **Speed.** On the 7.7 M-transition compost archive: `budget(region:4,
  soil_fertility)` in **22.8 ms** where L1 `CausalBudget.analyze()` did
  **not finish in 120 s**; first page of `committed_only().execute()`
  (10 of 1,072,067) in **13 ms**. Removing a needless `SELECT DISTINCT`
  on the unique PK cut the first page from 5,671 ms → 13 ms (~436×).
- **CLI**: `python -m causal_world query --db runs/x.db
  <build|count|budget|profile|writers|trace|readers|entropy|life>`;
  demo `python3 experiments/query_demo.py {immune|ecology}`.

Tests: 121 → **142** (`tests/test_query_engine.py`: build correctness +
determinism (content-hash) + incremental≡full + identity-mismatch
rebuild, filter parity vs raw-journal scan, budget≡L1 and
entropy≡migration_stats to 1e-12, `caused_by`/`caused` vs manual read
sources, backward/forward trace causality + depth/`max_nodes` caps +
no-loops, `execute()` is a lazy id-ordered generator, delta_profile
drill-down, archive-untouched hash).

## v0.7 — Living world: the player governs the world, not only their avatar

The design, the cycle and the prototype plan live in
**`experiments/proposals/v07_living_world_design.md`** (also in Russian).
This section is the operational summary.

v0.6 made the player one agent inside a world. v0.7 makes the **world**
the object: the player is a steward, a researcher and a law-maker at once.
The kernel is untouched; everything below is a ruleset, a system, or a
read-only observer over the recorded journal.

**Three new layers.**

1. **Civic layer — the player issues laws.** A *decree* is a normal
   committed transition (`player.directive`) that changes the law
   parameters of ONE region; the law systems read them, so a decree
   never competes with the ecology for a field. Three kinds, each a
   measured trade-off: `amend` (labour to compost: soil 0.50 → ~0.76,
   −25 % harvest), `water` (irrigation: +rain, soil mined faster),
   `rest` (fallow: the soil heals, the people eat the stores). A decree
   enacted at tick T enters force at **T+1** — derived from the one
   snapshot per tick, not configured. New ruleset `player_civic` (0.7.0);
   without decrees it is bit-identical to the base law.
2. **Counterfactual sandbox — determinism as a gameplay advantage.**
   `sandbox.py` reads the decision stream AND the decree ledger back out
   of an archive, re-runs the world with **one** changed decision, and
   compares the two runs with the same `CausalComparator` the lab uses:
   divergence tick (+ transition id), survivors, soil deltas, structural
   budget diff. The base of a counterfactual is the *recorded* world — a
   fork that changed two factors at once would be a lie.
3. **Hypothesis verdicts — fact, confirmed link, hypothesis.** A player's
   claim is *tested* against the record: `confirmed` (the edge exists),
   `refuted` (it does not), or `unresolved` (the record does not settle
   it). Never a narrative, never a silent upgrade of a guess into a fact.

**The loop, in one command:**

```bash
python -m causal_world civic --seed 7 --regions 3 --agents 100 --ticks 120 \
    --decree 20:amend:region:0:0.25 \
    --hypothesis CivicAgricultureSystem:agriculture.harvest:region:0:soil_fertility \
    --fork-at 50 --fork-action 0
```

OBSERVE (budgets, regime, series) → UNDERSTAND (a claim, tested against
the journal) → INTERVENE (a decree and/or a decision, through ordinary
transitions) → VERIFY (the counterfactual, diffed mechanically).

**The living map and the analytical mode** (one port, three roles):

```bash
python -m causal_world serve --port 8765 --db-dir runs/
#   http://localhost:8765/   map + analytical mode
#   ws://localhost:8765/ws   the v0.6 session protocol (unchanged)
#   /analyze?entity=region:0&field=soil_fertility   read-only analysis
```

The map draws what the server sent in the frame's `world` section (the
section the v0.6 contract already prescribed in §1.5); the analytical
mode reads the **archive**, not the server's memory, and answers with
budgets, confirmed links (by transition id) and the dynamics. Clicking a
region on the map opens its budget; the two views cite the same ids.

Tests: 233 → **252** (`tests/test_v07_civic.py`: the decree is a
committed transition, in force on T+1, scoped to one region; the base law
is untouched; the ledger is recoverable from the archive alone; a fork
changes exactly one factor and keeps the base ledger; hypothesis verdicts
are confirmed/refuted/unresolved; rejected transitions are not facts).

## v0.8 — Spatial living world: cells, a stable horizon, a world that speaks

The design, the measurements and the honest limits live in
**`experiments/proposals/v08_spatial_demography_design.md`** (Russian).
This section is the operational summary.

v0.7 gave the player a *world of regions* — one soil, one food stock, one
population per region — and the world had a measured defect: it died at
**tick 248** whatever the player did. The diagnosis
(`experiments/reports/v08_demography.md`) is in the record, and the
probes are unambiguous: ageing is not the killer, disease is not the
killer, and **raising the birth rate ×10 does not save the world either**
(exit tick 257). The killer is structural: the compost law returned
nutrients in proportion to the POPULATION while the degradation was
flat, so every death lowered the soil, which lowered the harvest, which
starved the survivors — a spiral.

v0.8 changes the MODEL, as new rulesets over the frozen kernel:

1. **Cells.** A region owns a grid of cells (`cell:{region}:{index}`),
   each with its own soil, food store, people, rainfall factor and
   **law**. Food is local; migration moves people to the better
   *neighbouring* cell. The cells are born through the normal genesis
   path (`extra_genesis_entities`), so they carry provenance from tick 0.
2. **Soil per worker, not per head.** Degradation and the nutrient
   return both scale with the labour applied to the field, so the
   equilibrium soil (0.47) is a property of the labour regime and **not
   of the head count** — a cell whose people died keeps its land. The
   v0.7 death spiral is gone by construction (measured: a cell with 11
   people and a cell with 0 both sit at soil ≈ 0.47).
3. **Births per adult.** Conception is a per-adult probability gated by
   the cell's food and carrying capacity, so the supply of newborns
   scales with the number of adults (54 agents → 23 births / 200 ticks,
   108 agents → 47). The dormant pool is sized for the horizon (6×) and
   its exhaustion is an observable end state, not a silent failure.
4. **Nursery — a model policy, not a mortality compensation.** A cell's
   `nursery` raises the conception rate and the newborn's health; it does
   **not** touch the death rate. The journal shows the new threshold:
   `birth.conceive` at 0.04 in the nursery cell against 0.02 next door.
5. **The situation layer — the world speaks about itself.**
   `observer/situation.py` computes a feed of problems (famine, hunger,
   surplus, thin soil, abandoned cell, birth stall, exhausted reserve of
   lives) from the state — each with a severity, the tick it has been
   true since, and the **transition ids** the claim rests on. It is
   silent when the world is healthy. The same code serves the live world
   and the recorded archive.

**The measured vertical slice** (seed 7, 2 regions, 54 agents, 8 cells,
900 ticks — the same world twice, one difference: the player's decrees):

| | without decrees | with decrees |
|---|---|---|
| alive at tick 900 | 37 | **80** |
| births | 105 | **206** |
| deaths by hunger | 37 | **0** |
| the poor region | extinct by tick ~120 | alive (39 people) |

The decrees: `amend 0.15` on the four cells of the poor region at ticks
20–23, then `water 1.0` on the same cells at ticks 24–27 (the channel
holds **one** order per tick — two orders in one tick overwrite each
other, silently).

```bash
python -m causal_world civic --seed 7 --ruleset player_spatial \
    --regions 2 --agents 54 --ticks 300 \
    --decree 20:amend:cell:1:0:0.15 --decree 24:water:cell:1:0:1.0
```

New rulesets: `player_spatial` (0.8.0, 2×2 cells per region) and
`player_spatial3` (0.8.0-s3, 3×3 — a different world shape is a
different ruleset, not a setting). The map draws the cells; the frame
carries the cells and the situation feed; the analytical mode reads the
archive and answers for a **cell** (its own soil curve, its budget, its
confirmed links by transition id).

The v0.6 world is bit-identical (pinned hashes, asserted in the suite);
the v0.7 world is untouched (the spatial systems are a separate ruleset).

Tests: 252 → **273** (`tests/test_v08_spatial.py`: the grid genesis, the
per-worker soil equilibrium, the per-adult birth law, the nursery
threshold, one-cell decrees in force on T+1, informed migration, the
situation layer with real evidence, the server frame, the frozen v0.6
world).

## v0.9 — The verifiable loop: orders, goals, reproducibility, the ceiling

v0.8 showed that a player CAN change a world. v0.9 asks the harder
question: is the change *checkable*, is it *reproducible*, and does the
game know when a problem is actually solved? The kernel is untouched;
everything below is observer, protocol and model policy.

### 1. An order is never lost silently

`DirectiveChannel.schedule` now returns an explicit answer:

| status | meaning |
|---|---|
| `accepted` | the tick is free; the order enters force on it |
| `queued` | the tick is taken; the order waits for the first free tick |
| `rejected` | the queue is full (`MAX_PENDING = 8`) — nothing was enacted |

The frame carries `decree` (the answer to the order of this message) and
`orders` (what waits / what is on the calendar). The journal remains the
truth about WHEN an order was enacted: `player.directive` is written on
the tick it actually took effect. The web client shows the answer in
plain words; a refusal still does not consume the decision slot.

### 2. A goal is solved only if the system survived it

`observer/goal.py` turns an episode of a problem into a goal and gives it
one of six verdicts: `active`, `settling`, `resolved`,
`resolved_with_cost`, `collapsed`, `transferred`. The verdict reads the
signal, the affected system (population and soil at opening vs closing)
and the neighbouring problems that appeared after the goal opened.

The case from the review is a test of its own: a famine whose signal
disappears because the people died is `collapsed`, never `resolved`. A
closed goal is watched for `SETTLE_TICKS = 20` before it may be called
solved — a famine that ends today can still kill this week.

The layer runs on the live world (the server keeps a `FieldHistory` of
population / food / soil per cell) and on archives (`/analyze` builds the
same history from the journal), so the game and the lab cannot disagree.

### 3. The effect survives other starting conditions — but not everywhere

`experiments/v09_reproducibility.py`: seeds 7/11/23 × 36/54/72 agents ×
{no orders, one fixed order protocol}, 600 ticks, no per-seed tuning.

| measure | Δ>0 | Δ=0 | Δ<0 | mean Δ |
|---|---:|---:|---:|---:|
| alive | 8 | 1 | 0 | +24.6 |
| births | 9 | 0 | 0 | +37.4 |
| deaths | 0 | 3 | 6 | −12.4 |
| mean soil | 9 | 0 | 0 | +0.066 |
| extinct cells | 0 | 3 | 6 | −2.4 |

No trade-off pair in the grid: the protocol never improved one measure at
the cost of another. But the honest part is where it does nothing: seed
11 at 54 agents is 74 alive with and without orders (the baseline is
already at 93% of the world's capacity), and the intervention cannot
create room that the law does not have.

### 4. The ceiling is measured, not assumed

Capacity of a cell is `pop_base × (1 + soil)`, and the birth law refuses
conception at the line. In a saturated world (88% full) a nursery in
every cell bought **+1 birth in 100 ticks** (60 → 61). The lever is real;
the ceiling makes it inert. This is why v0.9 does **not** ship resettlement
or long-term charters: redistributing people between full cells cannot
change the outcome, and adding levers whose effect cannot be measured is
the opposite of the repo's method. The next policy must change capacity
itself.

### 5. One situation, the whole loop

`experiments/v09_scenario.py` walks the loop on two archives: the world
names the first event (`hunger` at tick 57 with its transition ids), the
causal budget says what drained the store (−165.6 net, agriculture
−172.3), eight orders are accepted, the goal layer returns 6 `resolved` /
0 `collapsed`, the archives diverge at tick 58 (T9413), and the success
creates the next problem — 77 alive against 38 in the control, 93% of the
world's capacity occupied, and `birth_stall` in the cell that has no room
left.

Commands:

```
python3 experiments/v09_reproducibility.py --ticks 600
python3 experiments/v09_scenario.py --ticks 600
python3 -m causal_world serve --host 0.0.0.0 --port 8811
```

Tests: **297** — the new `tests/test_v09_orders.py` (9: the queue, the
bounds, both orders in the journal, the frame answer) and
`tests/test_v09_goals.py` (15: episodes, the collapse-by-extinction case,
settling, transfer, cost). The v0.6 frozen world still hashes bit-for-bit.

## v0.10 — Capacity: a named limit, priced land, and an honest window

The v0.9 grid left three questions open, and this stage answers them with
measurements rather than with new policy surface.

### 1. A limit is now named, not guessed

`situation.growth_limit` no longer says "capacity or food". It reads the
birth law's own arithmetic and returns one of:

| limit | condition |
|---|---|
| `capacity` | `population >= round(pop_base × (1 + soil))` — the law's rounding, not a float compare |
| `food` | `food_stock / population <= 3.0` |
| `soil` | `soil_fertility < 0.35` with room and food available |
| `adults` | no living agent in the cell is older than the reproduction age (20) |
| `pool` | the world has no free lives (dormant slots) left |
| `none` | no gate of the law is closed at this instant |

The last two came out of measurement: at tick 400 three cells sat below
capacity with food in store and still had no births. A reader that says
"nothing" there lies to the player; so the observer says which gate is
shut. `birth_stall` carries `detail["limit"]`, and the map prints
`предел N · лимит: ёмкость`.

### 2. Land is a transition, not a config edit

`CapacityRules` (0.10.0) adds two levers, both ordinary journaled
transitions:

* **claim** (`DIRECTIVE_CLAIM = 4`) — 90 food from the region's richest
  cell turns a wild parcel (`land_active = 0`, `cell:{r}:4..5`) into
  farmed land. `claim_done` / `claim_no_food` / `claim_already` are
  explicit answers; a refusal is visible in the journal, never silent.
* **terrace** (`DIRECTIVE_TERRACE = 5`) — 60 food + 0.04 soil for
  `+2 pop_base`, at most three per cell; costs are checked against the
  `old − new` writes of the SAME transition, because a snapshot taken
  before the tick would compare against food the world already ate.

Wild parcels are filtered out of ecology, alerts, goals and migration
(`spatial.is_active`); they are land in the snapshot, not hidden state.

### 3. The verdict window is measured, not chosen

`evaluate(..., settle_ticks)` takes the window as a parameter, and
`experiments/v010_settle_sensitivity.py` replays ONE archive (seed 7,
54 agents, 600 ticks) at 20 / 50 / 100 ticks:

**8 of 21 goals change verdict** in at least one window. The usual
pattern is `resolved` at 20 becoming `settling` at 50/100; one goal goes
`resolved → resolved_with_cost → settling`. The UI must therefore show
the horizon next to a verdict, or "solved" reads as a property of the
world instead of a property of the observation.

`transferred` is now always `confidence="hypothesis"` with text starting
"ПРЕДПОЛОЖЕНИЕ (не доказано)", and a `renew` episode can never become
`transferred` — a birth stall is not a problem that moves next door.
`test_a_renew_goal_never_becomes_transferred` pins this.

### 4. Three arms: price and result

`experiments/v010_capacity.py` — seed 7, 54 agents, the v0.8 protocol
until tick 400 (the world at its ceiling), then 200 ticks:

| arm | alive | capacity | births | food paid |
|---|---:|---:|---:|---:|
| control | 73 | 83 | 13 | 0 |
| claim | 73 | 92 | 13 | 180 |
| terrace | 84 | 95 | 24 | 240 |

The claim is a **measured failure as a growth policy**: room grew by 9,
but nobody moved in, because migration in the law fires on hunger and a
fed world does not hunger. The report says so instead of hiding it; the
`resettle` goal stays open. Terraces are a success with a price: +12
capacity, 24 births against 13, no soil difference at report precision.

### 5. Regimes mix, so a single grid is not proof

`experiments/v010_regimes.py` — 24 points (seeds 7/11/23/31 × 36/54/72 ×
baseline/decrees), 600 ticks. The regime is read from the baseline
world's OUTCOME (fall ≥ 15 % → `degradation`; final saturation ≥ 85 % →
`saturation`; otherwise `equilibrium`), never from one window:

| regime | points | mean Δ alive | mean Δ births |
|---|---:|---:|---:|
| degradation | 6 | +26.7 | +37.7 |
| equilibrium | 2 | +42.5 | +66.0 |
| saturation | 4 | +4.8 | +11.5 |

In v0.9 "0 trade-offs in 9" sounded like a property of the law. It is a
property of the basket: in saturation the same protocol buys +4.8 people
and costs food and soil. So the interface must show the regime beside
the effect — the same lever is a cure in degradation and a spend in
saturation.

Commands:

```
python3 experiments/v010_regimes.py --ticks 600
python3 experiments/v010_settle_sensitivity.py --ticks 600
python3 experiments/v010_capacity.py
python3 -m causal_world civic --ruleset player_capacity --ticks 40 \
        --decree 10:claim:cell:0:4 --decree 12:terrace:cell:0:0
python3 -m causal_world serve --host 0.0.0.0 --port 8811
```

Tests: **318** — `tests/test_v010_capacity.py` (20: wild land is not
ecology, claim price and refusal, terrace cost checked by the same
transition, the four limits, `renew` episodes, the sensitivity of the
settle window, `transferred` is a hypothesis, a renew goal never becomes
transferred, the server frame). The v0.6 frozen world still hashes
bit-for-bit.

Honest limits: one seed and one protocol in the capacity arms; the
"starvation death" is a proxy (hunger ≥ 0.75 on the last living tick),
not a cause read from a transition; the measures are dependent and do not
give independent confirmations; the window sensitivity is measured in one
world; `growth_limit` names a closed gate now, it does not predict a
birth.

## v0.11 — Resettlement: using the land the player opened

v0.10 ended on a measured failure: a claim creates room, but the people
do not come. The world's own migration fires on HUNGER and moves to a
neighbouring cell, so a fed world never uses the land it was given.
Capability CREATION and capability USE were two mechanisms, and only one
of them existed. This stage adds the second — a priced, atomic,
intra-regional move of people, with both sides of the move recorded.

### 1. The order says where and how many, not who

`resettle` (`DIRECTIVE_RESETTLE = 6`) names a DESTINATION cell and a
count (`0` = as many as the cell can take). The world chooses the donor
deterministically: the most over-capacity cell of the SAME region, then
the shortest distance, then the id. It never empties its source (at most
`population - 1`) and records who paid:

* `agent.cell` of every mover changes in the SAME transition;
* the source loses population, workers and transport food;
* the destination gains population, and records `resettled_in`,
  `resettle_moved`, `resettle_cost`, `last_source`, `last_resettle_tick`;
* the source records `resettled_out`.

The resolver commits all of it or none, so a partial move is not
representable. The price is `4.0 + 0.5 × distance` food per migrant,
paid by the source cell; a source that cannot pay moves nobody.

Answers are facts in the journal (`resettle_state`): `1` done, `-1` no
room, `-2` wild land (claim first), `-3` not habitable (soil or food
reserve), `-4` no transport food, `-5` no donor.

### 2. Room is not the same as habitable

`resettle_opportunities` builds the destination card the player sees,
with the SAME arithmetic the system applies: room, soil ≥ 0.35,
food ≥ 3.0 per head, donor, distance, price and the maximum number of
people. A row is a reading, not a promise; the law still answers when
the order is enacted. The web client lists the card and fills the order
form from it; the CLI prints who accepted whom.

The reserve is required even in an EMPTY cell (the law divides by
`max(population, 1)`), and a claimed parcel starts with 25 food that
spoils and is not replenished until workers live there. So the card
turns from "ok" to "no reserve" if the player waits: new land must be
settled while its reserve lasts. This is also where a live run caught a
real mismatch — the card said `ok` where the law refused with `-3` — and
the check was fixed in the observer, not relaxed in the law.

### 3. The verdict has two sides

A `resettle` goal lives on the destination, but a move can improve the
destination while draining the source. `evaluate` reads `last_source`
and the source's population history: if the source lost more than 20 %
of its people, the verdict is `resolved_with_cost` with the numbers in
the reason. The evidence cites both the move's `resettled_in` transition
and the source's population transition.

The horizon lesson of v0.10 stays visible: in the single-seed run one
new cell was populated, got `resolved` on its 20-tick window, and was
abandoned again later — the feed shows the OLD verdict and the NEW
`active` episode side by side. A verdict is a statement about its
horizon; the current state is shown next to it, not replaced by it.

### 4. Counterfactual: claim alone still does nothing

`experiments/v011_resettle.py` — seed 7, 54 agents, the v0.8 protocol to
tick 400, then 200 ticks in three arms:

| arm | alive | births | capacity | moved | food paid | occupied cells |
|---|---:|---:|---:|---:|---:|---:|
| control | 73 | 13 | 83 | 0 | 0 | 8/8 |
| claim | 73 | 13 | 92 | 0 | 180 | 8/10 |
| resettle | 80 | 20 | 92 | 8 | 218 | 9/10 |

Claim alone reproduces the v0.10 failure. With the move, births rise by
seven; 8 people are actually moved into the opened land, and 3 of them
are still living there at the end of the arm (the rest died or migrated
— visible in the journal). The move's transitions change the sum of cell
populations by **+0** and write **no** capacity field: resettlement
redistributes people, it never creates them or the land's ceiling.

### 5. The grid, repeated: one variable, all regimes

`experiments/v011_grid.py` — the same 12 points (seeds 7/11/23/31 ×
36/54/72), 600 ticks, FOUR worlds per point: no orders (regime control),
the v0.8 protocol, protocol + claims, protocol + claims + resettlement.

| regime | points | Δ claim: alive | Δ resettle: alive | Δ resettle: births | Δ resettle: occupied cells |
|---|---:|---:|---:|---:|---:|
| degradation | 5 | +0.0 | +5.6 | +5.6 | +1.0 |
| equilibrium | 2 | +0.0 | +5.5 | +5.5 | +1.5 |
| saturation | 5 | +0.0 | +8.2 | +8.2 | +2.0 |

In saturation the moves write zero capacity fields and change the sum of
population by `+0`; capacity itself stays put (`64 → 64`, `92 → 92`, …;
the one `120 → 119` is a soil drift, not a write of the transition). The
extra people come from BIRTHS inside the capacity that already existed,
not from a new ceiling. The grid also cross-checks v0.10: all 12
PROTOCOL worlds (the v0.8 orders, no capacity lever) match it number for
number, so the new ruleset is inert when its lever is unused. The regime
itself is read from the BASELINE arm — a world with no orders at all.

Commands:

```
python3 experiments/v011_resettle.py
python3 experiments/v011_grid.py --ticks 600
python3 -m causal_world civic --ruleset player_resettle --ticks 40 \
        --decree 5:claim:cell:0:4 --decree 10:resettle:cell:0:4:4
python3 -m causal_world serve --host 0.0.0.0 --port 8811
```

Tests: **337** — `tests/test_v011_resettle.py` (19: atomic move, agent
conservation, price from the source, refusals, deterministic donor,
source-side verdict, opportunity card, no capacity writes, same seed
same world, server card). The v0.6 frozen world still hashes
bit-for-bit.

Honest limits: the move is intra-regional (cross-region caravans need
trade and corridors that the model does not have); one protocol and one
strain of orders; "starvation death" is still a proxy; the mover rule is
"least hungry first", which in a fed world degenerates to id order (v0.11.1
measures it), and children can be sent. The +600 horizon is checked in
v0.11.1: the settlement persists in 6 of 8 new cells, as descendants,
not as founders.

## v0.11.1 — before scaling: three checks

The v0.11 chain is closed, but the review named what it does not prove:
a settlement can appear and vanish, the world chooses WHO leaves by a
rule nobody had measured, and the first scaling step must be a profile.
This stage adds no law to the world; it measures all three and writes
down the order of v0.12.

### 1. The long horizon: a settlement, not a founder effect

`experiments/v011_settlement.py` — the same three arms as the v0.11
counterfactual, but the player leaves after tick 416 and the world is
watched to tick 1020 (600+ ticks without a single order). Four seeds.

* **6 of 8** new cells still have people at +600. The two that emptied
  did so with **zero deaths inside the cell**: their people migrated
  away, which is a different outcome and is reported separately.
* At +200 the movers are alive 23/33 (70%) and the stayers 215/321
  (67%): on this horizon the move is not deadlier than staying.
* The settlement is **descendants, not founders**: 0/33 movers and
  0/321 stayers are alive at +600; the cells hold 1–4 people born there.
  The settlement survives; it does not grow.
* The move costs the source less than the noise of natural history in
  every seed: the end population of the donor cell differs from the
  SAME cell in the claim arm by −1…+3.
* Δ resettle − claim in alive at +600: +3, +11, +8, +3 (mean +6.2) —
  the direction of the short window holds, the size is smaller.

Report: `experiments/reports/v011_settlement.md`.

### 2. Who leaves: the policy is measurable, and the default is not "hunger"

`experiments/v011_selection.py` replaces ONE method (`_choose_movers`)
and keeps donor, count, price, destination and seed identical, across
four policies and four seeds:

| policy | moved | children | mean age | alive at +200 | survival |
|---|---:|---:|---:|---:|---:|
| `hungry` (world default) | 33 | 1 | 79.4 | 26 | 79% |
| `youngest` | 34 | 14 | 26.7 | 34 | 100% |
| `oldest` | 30 | 0 | 134.2 | 12 | 40% |
| `random` (hash, no RNG stream) | 33 | 4 | 82.5 | 27 | 82% |

The important measurement is not that the youngest survive best — age is
the main mortality factor, so that comparison is confounded by
construction. It is that **in all four seeds, every candidate had hunger
0.0**. The "least hungry first" rule therefore degenerates to the id
tie-break: the world is not choosing the hungry, it is choosing the
lowest id and calling it hunger. A child can leave alone (41% of movers
under `youngest`), because the model has no households.

No household model is introduced. The question was measured on the
current model; the next step is to decide whether the tie-break is
intended, not to hide it behind a new subsystem.

Report: `experiments/reports/v011_selection.md`; the extreme cases
(donor of one person, a source of two, equal donors, a child mover) are
pinned in `tests/test_v011_selection.py` (8 tests).

### 3. Profile: the analytics wall is closer than the engine wall

`experiments/v012_profile.py` builds each size in a SEPARATE process and
measures genesis, the phases of a tick, peak RSS, archive growth and the
cost of reading:

| living at start | slots | tick, s | commit, s | peak RSS, MB | journal, MB/tick |
|---:|---:|---:|---:|---:|---:|
| 500 | 3.5k | 0.15 | 0.02 | 57 | 0.4 |
| 1000 | 7k | 0.31 | 0.04 | 84 | 0.7 |
| 2000 | 14k | 0.66 | 0.10 | 145 | 1.5 |
| 4000 | 28k | 1.49 | 0.18 | 256 | 2.9 |
| 8000 | 56k | 2.99 | 0.25 | 464 | 5.9 |
| 16000 | 112k | 6.10 | 0.33 | 878 | 12.0 |

`journal, MB/tick` is the logical payload of the records, not the file
growth; the SQLite file is ~3x larger and includes genesis.

A tick at 16k living is 48% prefix scans of the state, 20% the spatial
system, 14% disease, 14% journal record, 8% id assignment. No single
law dominates: the repeating scan `entities_with_prefix` — 14 calls per
tick, each walking all 1.57M (entity, field) pairs — is the largest
single line. The projection to 100k LIVING (700k slots) is 40 s/tick,
5.5 GB peak RSS and 75 MB/tick of records (245 MB/tick of archive file);
the memory wall is below the machine's 4.1 GB, so the first v0.12
checkpoint is **failed by the current representation**, with numbers
rather than an opinion.

The reader is worse. `StateView.from_state` takes 4.6 s at 500 living
and 17.8 s at 1000; the exponent is 2.17 — quadratic, because
`fields_of` scans the whole state per entity. At 100k one frame would
take ~108 hours — not milliseconds. This is a defect of the observer, not of
the model: the same dictionary can be built in one pass without changing
a value, but the fix must come with an equivalence test (v0.12,
stage 2), not before it.

Reports: `experiments/reports/v012_profile.md`; the stage document is
`experiments/proposals/v11_1_prescale_checks.md` (Russian), the v0.12
plan is `experiments/proposals/v12_scaling_design.md`, and the playtest
protocol (not executed here) is
`experiments/proposals/v011_playtest_protocol.md`.

Tests: **348** — the v0.11 suite plus `tests/test_v011_selection.py`
(8: default policy, age is not an input, one-method override, donor
ranking, a one-person cell is not a donor, a move never empties its
source, the source is recorded) `tests/test_v012_reader.py`
(3: the one-pass view equals the old mapping, the v0.11 cell fields are
kept, reading does not change the state hash) and
`tests/test_v012_slice.py` (11: the six acceptance criteria of 2b).

Commands:

```
python3 experiments/v011_settlement.py
python3 experiments/v011_selection.py
python3 experiments/v012_profile.py --ticks 3
```

## v0.12 — stage 2a: the reader, one pass

The profile named `StateView.from_state` as a quadratic defect of the
observer. The fix is a single pass over the stored pairs instead of
`fields_of()` per entity; the mapping is unchanged, key for key, value
for value, provenance included.

| living | pairs | before | after | speed-up |
|---:|---:|---:|---:|---:|
| 500 | 49k | 4.71 s | 0.016 s | 287× |
| 1000 | 98k | 17.78 s | 0.037 s | 482× |
| 2000 | 196k | 88.71 s | 0.104 s | 853× |

`tests/test_v012_reader.py` pins the equality against the old
implementation and checks that reading does not touch the state hash.
Report: `experiments/reports/v012_reader.md`.

The quadratic wall is gone, but 100k is not: a full view is a dict of
~9.8M pairs, which even linearly takes seconds. The next step is a
CELL-SCOPED read — a frame needs one cell and its neighbourhood, not the
whole world. That is still a read, not a new model, and it will come
with the same equivalence check.

## v0.12 — stage 2b: a frame reads the cells, not the world

After 2a a full view is linear, but it is still the whole world: 1.57M
(entity, field) pairs at 16k living, ~9.8M at 100k, and the server built
it THREE times per frame (map, situations, goals). Stage 2b changes the
unit of reading.

`src/causal_world/observer/slice.py`:

* `WorldIndex` — the indexes a frame needs (entities by prefix, fields
  per cell/region, who lives where, the dormant pool). Built once by one
  pass, then advanced by the COMMITTED writes of each tick: O(writes),
  not O(world). Rejected proposals are not applied — they never touched
  the state.
* `CellSlice` — a `StateView` over the cells and their owner regions,
  with the same `get`/`source`/`tick_of` and the same provenance, plus
  `agents_in_cell`, `free_lives`, `pool_stats` from the index. Its
  `complete` flag tells a reader whether it is the whole world; a subset
  may not pretend otherwise.

The session builds ONE slice per frame and passes it to the map, the
situation feed, the goal cards and the resettlement card.
`_situation_alerts` and `_goals` build a slice when none is given, never
a full view, and `_sample_history` samples through the same slice.

Acceptance, as tests (`tests/test_v012_slice.py`, 11):

| criterion | what is pinned |
|---|---|
| equivalence | every slice pair equals the full view's pair (keys, values, provenance) |
| causality | transition ids and their ticks survive; alerts cite the same ids |
| reading | `state.hash()` and `journal.hash()` do not change |
| boundaries | empty cell, map edge, subset (`complete=False`), older ruleset |
| complexity | the state's scanning reads raise if a frame calls them |
| UI | map, situations, goals and resettlement come from one slice; the frame path never builds a full view |

Cost (`experiments/reports/v012_slice.md`, 2 CPU / 4.1 GB):

| living | pairs in the world | pairs in the slice | old frame, s | new frame, s | tick incl. index, s |
|---:|---:|---:|---:|---:|---:|
| 500 | 49k | 360 | 0.153 | 0.0020 | 0.021 |
| 1000 | 98k | 360 | 0.348 | 0.0030 | 0.050 |
| 2000 | 196k | 360 | 0.783 | 0.0053 | 0.089 |
| 4000 | 392k | 360 | 1.592 | 0.0095 | 0.182 |

The frame is two orders of magnitude cheaper. The whole tick is 7–9×
cheaper in this measurement, where the journal is in memory. On the
SQLite archive the index advance paid for deserialising the whole tick;
stage 2d removed the reads and draws from that path with
`writes_at_tick` (3.4× cheaper) — enough to stop paying for what the
index does not use, not enough to make a 100k tick's own writes free.

## v0.12 — stage 2c: the state keeps its own index

The profile's largest single line was `entities_with_prefix`: 14 calls
per tick, each walking all 1.57M `(entity, field)` pairs at 16k living —
48% of a tick. The systems ask the SNAPSHOT, so the fix is split in two:

* `WorldState` keeps entities grouped by their id prefix (`agent:`,
  `cell:`, `region:`). A group is added when the first pair of an entity
  is written. It is derived data: excluded from equality, from
  `state.hash()` and from the canonical payload. Only `engine.py` builds
  a state; a hand-made one builds its groups once in the constructor.
* `Snapshot.from_state` copies those groups instead of rescanning the
  pairs. The copy is O(entities), and it is a copy: a later commit can
  never leak into a frozen snapshot. An arbitrary (non-group) prefix
  still scans the entities, never the pairs.

The answers are exactly the lists a full scan produces. That is not an
opinion: `tests/golden/v012_reference.json` records `state_hash`,
`journal_hash` and the transition count AFTER EVERY TICK of a reference
run (seed 7, `player_resettle`, 2 regions, 54 agents, 40 ticks — 41
rows, 6052 transitions), written BEFORE the change by
`experiments/v012_reference.py` (`--check` recomputes and compares).

`tests/test_v012_equivalence.py` (10) pins the four invariants of the
stage plus the recovery case the project has already lived through:

| invariant | what the test does |
|---|---|
| state identity | `state.hash()` matches the golden after every tick |
| journal identity | `journal.hash()` and the transition id sequence do not move |
| deterministic replay | two runs agree tick by tick, not only at the end |
| derived index | full rebuild and `advance` through COMMITTED writes agree after every tick, for `player_resettle` and `player_civic` |
| restart | `replay_head` restores state and journal; rebuild equals advance |
| continuation | 4 ticks after a restart equal 4 ticks of a world that never stopped |
| entity groups | state groups answer like a scan, a snapshot's groups are a copy, groups are outside identity |

Cost of the same protocol, 2 CPU / 4.1 GB:

| living | tick, s | commit, s | peak RSS, MB | journal, MB/tick |
|---:|---:|---:|---:|---:|
| 500 | 0.118 | 0.015 | 57 | 0.4 |
| 1000 | 0.209 | 0.026 | 88 | 0.7 |
| 2000 | 0.459 | 0.050 | 145 | 1.5 |
| 4000 | 0.952 | 0.103 | 262 | 2.9 |
| 8000 | 2.074 | 0.146 | 461 | 5.9 |
| 16000 | 4.121 | 0.271 | 873 | 12.0 |

Against stage 2a the tick is 68% cheaper at 16k (6.101 → 4.121 s), and
the prefix reads themselves are 400–700× cheaper (14 scans, 0.500 s →
0.001 s at 4000) because the answer is built once per state, not once
per tick. The index rebuild is still O(pairs) and `advance` O(writes):
0.244 s vs 0.010 s at 4000, equality checked after each tick. After a
restart the index rebuilds in 0.003 s from the saved state and journal.

What this stage does NOT do: it does not change the memory model of the
state. Pairs stay pairs; the snapshot still copies data and provenance
(the 2.6% line of the profile) because the contract "a snapshot never
reads the live state" is worth more than those 2.6%. 100k was still not
run — that is the checkpoint after 2d.

Reports: `experiments/reports/v012_state.md` (prefix scan vs index,
rebuild vs advance, restart) and `experiments/reports/v012_profile_stage2.md`
(the same protocol after the change).

## v0.12 — stage 2d: the journal is batched, indexed and measured

Stage 2d is accepted in three independent groups, not one "faster"
number. A representation change that speeds up storage but changes what
the journal means is a failure, so the groups are tested separately:

| group | what must hold |
|---|---|
| logical history | the same ordered transitions, ids, causal sources, ticks, values and replay; `journal.hash()` equals the golden reference AFTER EVERY TICK |
| physical storage | batches and indexes lose no records; the derived index rebuilt from the journal alone equals the incrementally maintained one after every tick |
| access | indexed queries return the same rows in the same order as the sequential scan; replay to a tick reproduces state and journal prefix; a restart restores the index and does not diverge |

`journal.hash()` is not used as the only proof: the tests compare every
transition field by field with the in-memory journal, because a hash
collision is possible and an index error need not touch the hash at all.

What changed:

* `record()` stages transitions and writes one batch per table with
  `executemany` inside the SAME open transaction. The canonical hash
  chain still advances per transition at the commit boundary. The first
  record of a cycle is flushed at once, so SQLite's write lock is taken
  where the single-row writer took it (the second-writer test is
  unchanged), and a batch is invisible to readers until commit.
* `add()` stages the causal-index rows: latest writer, history of a
  field, read dependents.
* `idx_transitions_tick` makes a tick query read one tick instead of the
  whole journal.
* `writes_at_tick()` returns `(tid, entity, field, new)` for COMMITTED
  writes only, without building `Transition`/`StateRead`/`RandomDraw`.
  The 2b cell index now advances from this projection, not from full
  transitions.
* `transitions_for_entity/field` are answered by the `history` index;
  a non-COMMITTED status falls back to a scan, because rejected
  proposals never enter the index. `at_tick`/`between_ticks` are on the
  read-only `JournalView` too.
* `rebuild_index()` + `index_digest()` prove the index is derived and
  checkable; `replay_until(tick)` replays the world to an arbitrary tick
  read-only and verifies the journal prefix.

Acceptance, as tests (`tests/test_v012_journal.py`, 14):

| criterion | what is pinned |
|---|---|
| journal identity | the archived golden matches state hash, journal hash and transition count after every tick |
| history content | every transition equals the in-memory one; a batch of one and a batch of a million produce the same rows and hash |
| derived index | full rebuild equals the incremental index (digest and counts) after every tick; a reopen restores it without a rebuild; if the derived tables are deleted, the journal alone rebuilds them |
| query equivalence | id, tick, range, entity and field equal the linear scan in the same order, through the writer and through the read-only view |
| rejected rows | rejected transitions are in the journal, absent from the index, and found by the scan fallback |
| commit boundary | a batch is invisible to a second connection until commit; a SQLite rollback cannot resurrect staged rows |
| replay | `replay_until(k)` gives the same state hash and journal prefix, including `k=0` (genesis and the first step share tick 0, so the zero-step prefix is recorded as additive meta); `replay_head` still gives the full archive |
| restart | the index digest survives; three ticks after a restart equal three ticks of a world that never stopped |
| frame path | `writes_at_tick` equals the full-transition projection; the cell index advanced from it equals a fresh rebuild |

Cost, the same protocol as stages 1/2c (2 CPU / 4.1 GB, seed 7,
`player_resettle`, 2 regions, 3 ticks; genesis committed before timing
so the first tick is not charged for it):

| living | tick + commit before, s | after, s | record before, s | record after, s | add before, s | add after, s |
|---:|---:|---:|---:|---:|---:|---:|
| 500 | 0.106 | 0.095 | 0.030 | 0.023 | 0.023 | 0.001 |
| 1000 | 0.225 | 0.238 | 0.061 | 0.061 | 0.048 | 0.002 |
| 2000 | 0.489 | 0.447 | 0.135 | 0.099 | 0.097 | 0.063 |
| 4000 | 0.990 | 0.932 | 0.250 | 0.201 | 0.198 | 0.124 |

The write side is a few percent, and at 1000 the sign is within run
noise. That is the honest result: `record` is dominated by two canonical
JSON serializations per transition (the stored payload and the hash
record), not by the number of SQL statements. The profile at 16k living
still shows `record` at 26% of the tick and `canonical_json` at 14%;
`sqlite3.execute` disappeared from the top list (it was 17%). A change
that would halve it means changing the journal format or the hash
definition, and neither is a 2d decision.

The read side is where the stage pays. Queries measured on a 12-tick
journal, with the same SQL forced through a scan (`+tick`) for the
before column:

| living | one tick: index, s | one tick: scan, s | tick writes: projection, s | tick writes: scan, s | entity: index, s | entity: scan, s |
|---:|---:|---:|---:|---:|---:|---:|
| 500 | 0.017 | 0.019 | 0.006 | 0.007 | 0.0015 | 0.76 |
| 1000 | 0.036 | 0.042 | 0.011 | 0.015 | 0.0014 | 1.46 |
| 2000 | 0.078 | 0.086 | 0.023 | 0.031 | 0.0015 | 3.00 |
| 4000 | 0.176 | 0.190 | 0.052 | 0.067 | 0.0017 | 6.55 |

The entity and field queries went from a full journal scan to one index
lookup (hundreds to thousands of times cheaper). The frame path is the
`writes_at_tick` column: 3.4× cheaper than full transitions, because it
does not build reads, draws or `Transition` objects. A tick query still
deserialises its own tick — the index removes OTHER ticks, not the cost
of the tick itself. A multi-tick range with `ORDER BY id` is slightly
SLOWER through the tick index (0.776 s vs 0.731 s at 4000): the index
forces a sort, and that is published rather than hidden. This is the
remaining wall for 2e and the 100k checkpoint, not a reason to claim a
win.

Storage at 4000 living: 88.7 MB file, of which the new tick index is
0.47 MB; the causal index (`latest_writer` + `history` + `dependents`)
is still comparable to the journal itself. No attempt was made to shrink
it in 2d — the stage measures it. Profile at 16k living: tick 4.121 →
3.846 s, tick + commit 4.392 → 4.224 s (−3.8%), peak RSS 873 → 888 MB
(+1.7%, staging buffers and the tick index). 100k was not run.

Reports: `experiments/reports/v012_journal.md` (three groups, before and
after) and `experiments/reports/v012_profile_stage3.md` (the same
protocol after 2d).

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
v0.5  Causal query engine: indexed, streaming, composable queries over
      the frozen journal — read-only, cache is derived (this branch)
v0.6  Biography generator
v0.7  Living world: civic layer (player-issued, region-scoped laws),
      counterfactual sandbox, hypothesis verdicts, living map + analytical
      mode; LLM as causal-trace interpreter (observer adapter only)
v0.8  Spatial living world: cells with their own soil, food, people
      and law; soil per worker (no death spiral); births per adult;
      the nursery policy; the situation feed — the world that says what
      is wrong (this branch)
v0.9  Verifiable loop: explicit order contract (accepted / queued /
      rejected), goals with honest completion (collapse ≠ resolution),
      reproducibility grid over seeds and starting populations, measured
      capacity ceiling; the success creates the next problem (this branch)
v0.10 Capacity policy: wild land claimed by a priced transition, terraces
      that buy capacity with food and soil, a named growth limit, and a
      measured verdict window; resettlement is measured as missing, not
      shipped (this branch)
v0.11 Resettlement: a priced, atomic, intra-regional move of people;
      the destination card names room, habitability, donor and price;
      verdicts account for both the destination and the source; the
      lever is inert when unused
v0.11.1 Pre-scaling checks: the +600 settlement horizon, the mover
      policy (the hunger rule degenerates to id order), and a profile
      that puts the analytics wall in front of the engine wall
      (this branch)
v0.12 Scaling, measured: stage 1 profile (done) → 2a observer one-pass
      (done) → 2b cell slice (done: frame 118× cheaper, 6 criteria in
      tests) → 2c state/snapshot (done: golden per tick, tick 32%
      cheaper, groups derived and checked) → 2d journal (done: batches,
      tick index, write projection; history unchanged) → checkpoint
      100k × 20 with simulation, index update, frame and history storage
      measured separately → 2e/2f only if the checkpoint names them →
      resettlement policy as a separate ruleset variant. Checkpoint:
      100k living pass a fixed horizon with tick time, peak RSS and
      journal growth published; analytics ≤ 250 ms/frame
v1.0  Large artificial world
```

Order matters: while the system is small we can still *prove* its
fundamental properties. New systems, economy, culture or an LLM come only
after each stage's experiment has been run.
