# v0.5 — CausalQuery: from five hard-coded answers to any question

**Kernel v0.1 (frozen). No new laws, no new systems, no writes to any
archive.** v0.4 answered five questions with five bespoke functions and
hand-written SQL. v0.5 turns that into a composable, indexed, streaming
query API, so the *next* question is a one-liner instead of a new module:

```
JournalView (raw archive, read-only, mode=ro)
    -> QueryIndex   (derived indexes in a SEPARATE cache DB, lazy-built)
    -> CausalQuery  (immutable builder: filters + causal closures)
    -> generators   (lazy hydration in pages; early termination for free)
```

Modules: `query/index.py` (`QueryIndex`, `IndexStats`), `query/query.py`
(`CausalQuery`, `EntropyResult`, `DeltaProfileRow`, `TraceResult`).
`budget()` deliberately returns the observer's own `CausalBudgetReport` /
`BudgetEntry` (imported from `observer.budget`), so parity with L1 is
*structural*, not merely numeric — the same dataclass, filled from the
index instead of a Python scan. CLI: `python -m causal_world query --db
runs/x.db <build|count|budget|profile|writers|trace|readers|entropy|life>`.
Demo: `experiments/query_demo.py {immune|ecology}`.

The mandate from the v0.4 review, restated: (1) drill down to the
*write* level inside a transition — tell "harvest in
CompostAgricultureSystem" from "harvest in AgricultureSystem" by actual
deltas, not names; (2) make the L1 law-discovery reproducible to 4
decimals through the query path; (3) make Q5-style emergent comparisons
(entropy 3.105 vs 1.699) trivial. All three are done below.

## Indexes: reuse the archive, add only what's missing

The proposal called for four indexes. The archive schema **already
persists three of them**: `history(entity, field, tid)`,
`dependents(source, target)`, and `idx_transitions_op_status`. QueryIndex
ATTACHes the archive `mode=ro` and reuses those; it adds only the three
that don't exist:

| added index | immune rows | answers |
|---|---|---|
| `idx_writes(entity, field, tid, tick, delta, old, new)` | 1,730,066 | write-level drill-down: budgets, delta profiles, value distributions |
| `idx_reads(source_tid, reader_tid, entity, field)` | 54,348,027 | causal closures refined by WHICH entity/field was read |
| `idx_entity(entity, tid, tick, role)` | 22,392,537 | timelines: "the whole life of agent X" |

The build is a **single SQLite pass** (`INSERT .. SELECT` with
`json_each` over the attached archive), not a Python row loop — the
difference between minutes and hours on a dense journal. The `delta`
column is computed in SQL (`new - old` when both numeric, else NULL), so
non-numeric writes never break L1 parity.

**Lazy indexes, for real.** `idx_reads` is ~50x the transition count in a
dense world and is needed *only* for causal closures. `build()` takes
`include_reads` / `include_entity` flags; a writes-only index answers
budget / delta_profile / entropy / writers. The compost cache below is
1.4 GB writes-only vs the 5 GB full immune cache — you pay only for the
provenance you query.

**Incremental by construction.** `qmeta.last_tid` marks the frontier. A
longer archive of the *same world* (identity = seed, regions, agents,
ruleset name/version, rng version — verified on open, **not** the file
name) extends the cache instead of rebuilding: determinism guarantees the
journal prefix is byte-identical, so re-running seed 7 to 10k ticks
reuses the 5k-tick cache. A cache from a different world is wiped and
rebuilt, never mixed (`test_identity_mismatch_rebuilds`). Re-opening the
immune cache after a full build was a **0.5 s no-op** (`incremental`).

The cache is a derived artifact (`synchronous=OFF`, reconstructible from
the archive); the **archive stays `mode=ro`** — the query engine
physically cannot modify the world's record
(`test_archive_untouched_by_indexing` hashes the archive file SHA-256
before/after build + every query type).

## Build measurements (seed-7 archives, 2-core sandbox, contended)

| archive | transitions | journal | index built | cache |
|---|---|---|---|---|
| immune 0.3.0, 10k ticks | 1,076,375 | 4.18 GB | full 839 s / incremental 0.5 s | 4,980 MB (writes+reads+entity) |
| compost G, 4k ticks | 7,724,693 | 5.70 GB | writes-only 130.6 s | 1,417 MB |
| fertile migration, 1.5k ticks | 1,256,844 | 1.33 GB | writes-only 20.0 s | 234 MB |

The immune full build ran while two other simulations shared the two
cores; a solo build is materially faster. The point is not the wall
clock — it's that after the one pass, every query below is milliseconds
on journals where the v0.4 observer path is minutes-to-never.

### The query speedup, concretely

On the 7.7M-transition compost archive:

| query | v0.5 indexed | v0.4 observer |
|---|---|---|
| `budget("region:4","soil_fertility",0,3999)` | **22.8 ms** | L1 `CausalBudget.analyze()` did **not finish in 120 s** (O(n) Python scan) |
| `operation("agent.migrate").committed_only().count()` | **1.5 ms** | full journal scan |
| first page of `committed_only().execute()` (10 of 1,072,067) | **13 ms** | — |

Both return the *same numbers* the observer does — the speedup is pure
index, with parity proven to 1e-12 in tests.

## The six spec questions, through the API

All output below is real, from `experiments/query_demo.py` on the seed-7
archives (full log in the repo history / demo stdout).

### 1. "Why did this agent die?" — backward trace

```
death: t400 T635428 AgentSystem.agent.death of agent:137
backward trace: 9360 nodes (max depth 6)
  d0 t400 T635428 agent.death        [alive=True, health=0.123, hunger=1.0]
  d1 t399 T634352 agent.health       [health=2.123, hunger=1.0]
  d1 t399 T634825 agent.metabolism   [hunger=1.0, immunity=0.0, region:9]
  d1 t366 T596347 disease.recover    [infected=True, immunity=0.098]  DRAW recovery 0.104<0.120
  d2 t363 T592833 disease.infect     [infected=False, immunity=0.117] DRAW infection 0.002<0.016
  d2 t357 T585850 agent.migrate      [hunger=0.823, region:8]         DRAW decision 0.029<0.074
```

The trace reads as a biography: agent:137 was infected (t363), its
immunity collapsed to 0.0, hunger hit the 1.0 cap (starvation), health
decayed 4.1 -> 2.1 -> 0.123, and it died at t400. `trace()` returns the
9,360-node ancestor cone because a death reads *shared region state*, so
the cone legitimately reaches back to genesis — the API gives the whole
cone; the demo sorts by depth to surface the proximate causes.

### 2. "Who read what transition #N wrote?" — forward closure

```
source: t300 T520977 AgricultureSystem.agriculture.harvest
        [('region:0','food_stock',0.0), ('region:0','soil_fertility',-0.0009)]
  depth 1: 1 dependent    depth 2: 2    depth 3: 3  (e.g. t301 T522139 harvest)
```

Precise, not over-reporting: by t300 region:0 was depopulated (the immune
world goes extinct ~t573), so only the next harvest read that soil. The
closure follows `idx_reads.source_tid -> reader_tid`, so it counts
transitions that read *this* transition's writes, refined by entity+field.

### 3. "All writers of region:4.soil_fertility, ticks A..B"

```
immune  (t0..9999): 10001 writes, net -0.574505
    AgricultureSystem.agriculture.harvest:        -0.574505 (639 effective)
compost (t0..3999):  4001 writes, net +0.054924
    CompostAgricultureSystem.harvest (inflow):    +0.094178 (2643 effective)
    CompostAgricultureSystem.harvest (outflow):   -0.039254 (1357 effective)
```

The immune net (**-0.5745**, 639 effective writes) reproduces the v0.4
finding exactly. Compost flips the sign to **+0.0549**: the same-named
`harvest` operation *regenerates* soil there.

### 4. "Migration entropy: G vs I" — one line each

```
compost (blind):     1140 moves, entropy 3.105 bits, 10 destinations
informed migration: 18772 moves, entropy 1.699 bits,  5 destinations, top region:0 (43.7%)
```

v0.4 needed a bespoke ~40-line `migration_stats()` for this. v0.5:

```python
q.operation("agent.migrate").committed_only() \
 .entropy(by="write:region", actual_changes_only=True)
```

and it returns **3.105** and **1.699** — bit-for-bit the v0.4 numbers
(`test_entropy_matches_migration_stats` asserts equality to 1e-12).
Blind migration spreads over all 10 regions (high entropy); informed
migration concentrates on the 5 fertile ones, 43.7% into region:0 (low
entropy). The emergent contrast is now a two-line comparison.

### Drill-down: the v0.4 signal, generalized (mandate #1)

`delta_profile` tells the two `agriculture.harvest` laws apart by the
*sign of the actual deltas*, not the operation name:

```
immune region:4 soil (full):
    AgricultureSystem.harvest:          n=10000  +0/-639   mean -0.000057451
compost region:4 soil (equilibrium t2000..3999):
    CompostAgricultureSystem.harvest:   n=2000   +2000/-0  mean +0.000008080
                                        range [+0.000000165, +0.000045544]
```

At equilibrium *every* compost harvest write is positive (soil recovery);
the immune harvest is negative when it fires at all (639 of 10,000
attempts were effective; the rest were no-op reads that wrote nothing).
This is exactly the "compost_recovery is a signal, not a limitation"
point from the v0.4 review, now readable straight off the index.

### 5. "Which random draws decided this agent's fate?" — close calls

```
agent:137: 20789 transitions, 12 close-call draws (|value-threshold|<0.05)
    t61  disease.infect  infection: 0.0134 vs 0.0402 -> passed
    t62  disease.recover recovery:  0.1408 vs 0.1822 -> passed
    t129 disease.infect  infection: 0.0152 vs 0.0261 -> passed
    t235 agent.migrate   decision:  0.0638 vs 0.0736 -> passed
```

The draws are addressed and reproducible; a close call is a draw whose
value landed within 0.05 of its threshold — the knife-edges where a
different RNG stream would have changed this life.

### 6. "Counterfactual: what depends on transition #N?"

```
source: t100 T202620 ImmuneDiseaseSystem.disease.infect
  depth 1:     10 transitions depend on it   (2 ms)
  depth 3:    423 transitions                (53 ms)
  depth 6: 419,925 transitions               (59.6 s)
```

One infection at t100 is upstream of **420k** transitions by depth 6 —
the counterfactual footprint of a single early event in an epidemic
world. Depth 3 (423, 53 ms) is the practical query; depth 6 shows the
true reach and why closures are depth-bounded.

### Streaming on a million-transition journal (mandate: never materialize)

```
first 10 of 1,072,067 committed transitions in 13 ms (pages of 500)
```

`execute()` is a generator: it keyset-paginates tids (`WHERE tid > ?
ORDER BY tid LIMIT 500`) and hydrates one page at a time, so a 19 GB
journal is never a Python list. `test_execute_is_lazy_iterator` asserts
`isinstance(execute(), types.GeneratorType)`, id ordering, and that
pulling a few items does not exhaust the stream.

**Perf fix found by the demo.** The first page originally took
**5,671 ms**: the compiled SQL was `SELECT DISTINCT t.id AS tid ...`,
and `DISTINCT` forced SQLite to materialize the full 1.07M-id dedup set
before the keyset `LIMIT` could apply. But `t.id` is the archive PRIMARY
KEY (already unique) and every filter is `EXISTS`/`IN` (non-fan-out), so
`DISTINCT` deduped nothing. Removing it lets SQLite flatten the wrapper
and push `ORDER BY tid LIMIT` onto the PK scan: **5,671 ms -> 13 ms
(~436x)** for the first page, with identical results (all 142 tests
still green).

## Parity guarantees (121 -> 142 tests, all green)

The engine is only trustworthy if every answer equals the frozen truth:

* `budget()` == observer L1 `CausalBudget.analyze()` to 1e-12, full
  range and windows, including inflow/outflow entries
  (`test_budget_matches_observer_l1`, `test_budget_window`);
* `entropy(by="write:region")` == v0.4 `migration_stats()` to 1e-12
  (`test_entropy_matches_migration_stats`);
* `caused_by(tid,1)` == manual scan of reads' `source_transition`;
  `caused(tid,1)` == the transition's own read sources
  (`test_caused_by_direct_matches_archive_dependents`,
  `test_caused_matches_reads_sources`);
* every filter count == Python-side scan of the raw journal
  (`test_filter_parity_against_raw_journal`,
  `test_entity_and_field_filters`, `test_tick_window_and_committed`);
* builds are deterministic: two fresh caches hash identically;
  incremental == full content-hash; identity mismatch rebuilds
  (`test_build_is_deterministic`, `test_incremental_build_matches_full`,
  `test_identity_mismatch_rebuilds`);
* `execute()` is a lazy generator in id order; `list(limit)` truncates;
* forward traces are depth- and node-capped, never loop
  (`test_trace_forward_and_depth_limit`, `test_trace_never_loops`);
* `delta_profile` distinguishes CompostAgricultureSystem (positive mean)
  from AgricultureSystem (negative) on the same operation name
  (`test_delta_profile_drilldown`);
* the archive file is byte-identical after indexing + all queries
  (`test_archive_untouched_by_indexing`).

## Naming note

The spec's causal vocabulary is kept exactly, with unambiguous aliases:
`caused_by(tid)` = downstream dependents (read what tid wrote; alias
`dependents_of`), `caused(tid)` = upstream ancestors (their writes were
read by tid; alias `ancestors_of`). `trace(tid, direction, depth)`
returns a `TraceResult` (nodes + per-node depth + truncation flag).

## Design deviations (documented, per the v0.4 style)

1. **Attach + derived-only indexes.** Reuse the archive's three existing
   indexes; add only `idx_writes`/`idx_reads`/`idx_entity`. No
   duplication, smaller cache, and the archive never leaves `mode=ro`.
2. **Pure-SQL single-pass build**, not a Python loop — orders of
   magnitude faster on dense journals.
3. **Identity = world, not file.** Same-world longer archives extend the
   cache; the file name is irrelevant (determinism guarantees prefix
   identity).
4. **Level-BFS trace with truncation.** `trace()` expands breadth-first
   and stops at `max_nodes` (default 50k), setting `truncated=True`
   rather than silently dropping — a death's ancestor cone can reach
   genesis (9,360 nodes at depth 6), so the cap matters.
5. **`delta=NULL` for non-numeric writes** keeps L1 parity (the budget
   ignores non-numeric deltas exactly as the observer does).
6. **Optional read/entity indexes** (`include_reads`, `include_entity`):
   the lazy-index principle — build the provenance you actually query.
7. **No `SELECT DISTINCT`** on a unique PK — the 436x streaming fix.

## What v0.5 makes possible next

Biographies (v0.6) are now a query, not a scan: `timeline(agent)` +
`trace(death)` + per-life `entropy` compose into a life story with no new
plumbing. The LLM interpreter (v0.7) receives exactly the structured
`TraceResult` / `DeltaProfileRow` / `EntropyResult` objects it needs. And
any question of the form "who / what / when / how-much depends on X" is a
composition of five primitives — filter, close, trace, aggregate,
stream — over an index that is built once and never touches the frozen
world.
