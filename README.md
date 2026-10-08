# Deterministic Causal World Simulation Engine

> **CAUSAL KERNEL v0.1 — frozen** (tag `v0.1.0`). The kernel architecture is
> not extended silently; anything considered redundant goes through an
> explicit proposal first. v0.2 work adds observability and scale around the
> frozen kernel, never inside it. See the [roadmap](#roadmap).

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
├── simulation/    engine.py resolver.py journal.py
├── systems/       base.py climate.py agriculture.py disease.py agents.py
├── causal/        index.py trace.py
├── observer/      events.py statistics.py observability.py
├── world/         generator.py rules.py
├── cli.py         __main__.py
tests/             7 test modules + helpers.py (51 tests)
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
| `ruleset_version` | `0.1.0` | world laws / schema / purposes changed |
| `rng_version` | `blake2b-v1` | draw algorithm changed |

Changing the RNG algorithm or the semantics of a purpose is a **ruleset**
change. The run fingerprint records all versions plus initial/final state
hashes, so "same world" is distinguishable from "same seed, other ruleset".

## Tests

```bash
python -m pytest          # 51 tests
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

## Roadmap

```
v0.1  Deterministic causal kernel            (frozen, tag v0.1.0)
v0.2  1000 agents / 10k ticks survival run   (this branch)
v0.3  Statistical observer
v0.4  Causal query engine
v0.5  Biography generator
v0.6  LLM as causal-trace interpreter (observer adapter only)
v0.7  100k+ agents: memory layout, sparse state, batching,
      spatial partitioning, parallel execution, compressed provenance
v1.0  Large artificial world
```

Order matters: while the system is small we can still *prove* its
fundamental properties. New systems, economy, culture or an LLM come only
after each stage's experiment has been run.
