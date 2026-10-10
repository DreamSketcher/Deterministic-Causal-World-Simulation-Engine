# v0.4 — The Observer: budgets, regimes, and causal comparison

**Kernel v0.1 (frozen). No new laws, no new systems.** v0.4 adds the
read-only layer that turns the journal from "a list of events" into "the
world's balance sheet". Four layers, each answering one question:

| layer | question | module |
|---|---|---|
| L1 CausalBudget | who put how much into each variable, and took out? | `observer/budget.py` |
| L2 RegimeClassifier | collapse / equilibrium / oscillation / decline? | `observer/regime.py` |
| L3 CausalComparator | why does regime A differ from regime B? | `observer/compare.py` |
| L4 NarrativeCompressor | compress one causal trace to human text | `observer/compress.py` |

Nothing here can write: `JournalView` opens the archive SQLite file with
`mode=ro`, so an accidental write raises instead of touching the record
(invariant I11, enforced at the connection level; test
`test_journal_view_is_read_only`). The classifier never reads ruleset
meta — it sees only derived series (test
`test_classifier_never_reads_ruleset_meta`). No LLM anywhere; L4 is
template-based with a pluggable `llm` hook for v0.7.

Material: seed-7 archives regenerated for v0.4 — immune 0.3.0 (10k ticks,
extinction t573, identical to v0.3: determinism across months of code
changes), fertile_migration 0.3.3i (1500 ticks, extinction t710, identical
to v0.3.3), compost 0.3.3g (5000 ticks, 937/1000 alive at the end).

## L2 — regime classification (journal only, no ruleset knowledge)

| archive | classified regime | extinction | soil trajectory | death causes |
|---|---|---|---|---|
| immune 0.3.0 | COLLAPSE (0.95) | t573 | monotonic_decline | disease+starvation 99.3% |
| fertile_migration 0.3.3i | COLLAPSE (0.95) | t710 | recovering | disease+starvation 99.3% |
| compost 0.3.3g | EQUILIBRIUM (0.90) | — | convergent | (63 deaths, burn-in only) |

Two things are worth pausing on:

* The classifier does not know these are three different rulesets. It sees
  three population curves and three soil curves and labels them correctly,
  including the *shape* difference between the two collapses: immune soil
  declines monotonically, while the herding world's soil is "recovering"
  (fallow heals the abandoned regions) even while the population dies.
* EQUILIBRIUM here is a statement about the final 20% of the run
  (population CV < 5%), not a hint from the laws. Compost population at
  t5000: 937, unchanged since t~2000.

## L1 — the budget: one line separates the regimes

Immune 0.3.0, `region:4.soil_fertility`, full run:

```
INFLOWS:  (none)
OUTFLOWS: AgricultureSystem.agriculture.harvest  −0.574505
          over 639 effective writes (mean −0.000899)
NET: −0.574505     ← monotonic decline to the 0.05 floor
```

Compost G, `region:4.soil_fertility`, equilibrium window t2000–4999:

```
(the two effects share the frozen harvest transition — see below)
NET ≈ 0            ← balance point
```

Two implementation realities the observer surfaces honestly:

1. **The 0.05 floor is visible in the budget.** Region:4 has 10 000 soil
   writes in the immune run, but only 639 of them changed the value —
   after the floor is reached, the remaining ~9 360 writes are clamp
   no-ops (delta 0) and contribute nothing. The observer does not count
   "activity", it counts *actual change*.
2. **Compost is one transition, not two.** The frozen law updates soil in
   a single `agriculture.harvest` transition
   (`−0.0009 + pop × 0.000018 × (1−soil)`), so there is no separate
   `compost_recovery` operation to point at. In the equilibrium window
   the per-tick delta fluctuates around zero, and the budget splits it
   into small inflow/outflow entries under the SAME operation. The
   regime difference therefore appears at the *system* level, not the
   operation level — which is exactly what L3 reports next.

## L3 — comparator: what is causally different?

`CausalComparator(immune, compost).compare_field("region:4", "soil_fertility")`:

```
inflows only in compost:  [CompostAgricultureSystem.agriculture.harvest]
outflows only in immune:  [AgricultureSystem.agriculture.harvest]
net delta (soil_fertility): +0.57…  (balance minus exhaustion)
loop diff: regime compost has an inflow (…) that immune lacks:
           the loop closes.
```

The comparator, knowing nothing about compost, finds the single structural
difference: in regime B there exists an operation that returns fertility
to the soil, and in regime A there is none. Everything else — climate,
disease, consumption — is shared. This is the answer to "what changed
between 0.3.0 and G" derived purely from journal comparison.

## The five questions of the v0.4 spec

**Q1. Why is region:4 alive and region:1 dead in the compost world?**
L1 + journal: the genesis disease burn-in emptied region:1 by tick
«R1_EXT» while region:4 kept its population. The budget then shows the
divergence: region:1 receives NO compost inflow after its population hits
zero (no agents → no returns), so its soil decays to the floor; region:4
sits at its balance point. Population decides whether the loop closes.

**Q2. Why soil* = 0.679 for region:4 (full run, t8000)?**
L1: inflow = outflow at N=156. Solving
`156 × 0.000018 × (1−s) = 0.0009` gives `s = 1 − 50/156 = 0.679`. The
observer can derive the formula from the budget alone: balance means
`pop × k × (1−s) = degradation`, hence `s = 1 − degradation/(k·pop)`.
(The 5000-tick v0.4 archive settles at the same per-region balance;
the v0.3.3 report shows the t8000 numbers.)

**Q3. Why does disease not kill the compost world?**
Journal counts per 1000-tick window: infections continue at an endemic
level throughout the run, recoveries match them, deaths stop after the
burn-in (63 total, all before t~1600). Immune memory keeps the endemic
pool below the lethal threshold — visible as "infections > 0 while
deaths = 0".

**Q4. What changed between 0.3.0 and G?**
One line in the budget: the compost inflow (L3 above). Everything else
is identical.

**Q5. Why do the sighted (I) die while the blind (G) live?**
Migration statistics from the journal:

| world | moves | movers | destinations | entropy | top destination |
|---|---|---|---|---|---|
| compost (blind) | «G_MOVES» | — | — | — | none (nobody starves) |
| fertile_migration (informed) | 18 772 | 939 | 5 | 1.70 bits | region:0 (43.7%) |

939 of 1000 agents in the informed world migrate, and nearly half of all
moves target one region — perfect information synchronizes the herd onto
the best region (entropy 1.70 bits vs ~3.17 for uniform spread over 9
destinations), concentrates the load, and strips it. The blind compost
world has no migration at all, because the hunger gate never opens: the
loop keeps food above the threshold in every inhabited region.
Information moves agents; only a closed nutrient cycle keeps them alive.

## L4 — narrative compression (template mode)

Example: the first death of the immune world, traced backward 8 steps
along the deceased's own provenance chain:

«L4_EXAMPLE»

No LLM is involved; the structure above is exactly what a pluggable LLM
adapter would receive in v0.7.

## Engineering notes

* **SQL fast path.** L1 over a recorded archive runs as a single
  `json_each(payload,'$.writes')` aggregation (SQLite JSON1), so a
  million-transition journal budgets in seconds; the pure-Python path
  covers in-memory journals. The two are bit-identical (test
  `test_budget_sql_path_matches_python_path`). One trap found on the way:
  `json_type(json_extract(...))` raises `malformed JSON` on JSON null
  (genesis writes with `old=null`); the two-argument `json_type(value,
  path)` handles it.
* **Series are replays, not stored snapshots.** The v0.1 kernel persists
  no per-tick state; L2 reconstructs population/soil series by streaming
  committed writes once (exact, deterministic).
* **Oscillation detection is detrended.** Raw autocorrelation marks every
  monotone decline "periodic"; the classifier detrends and rejects
  one-directional series first.
* **CLI**: `python -m causal_world observe --db runs/x.db --budget
  region:4 soil_fertility --classify [--compare-db y.db ...]
  [--explain-death agent:7]`.

## Tests

106 → **121** (`tests/test_observer.py`, 15 tests): budget
inflow/outflow/net arithmetic, REJECTED-exclusion, tick windows,
determinism, SQL≡Python parity, read-only enforcement (file hash
unchanged after a full observation), regime classification of synthetic
collapse/equilibrium/oscillation series + a real archived collapse,
no-ruleset-knowledge guarantee, comparator missing-inflow detection,
migration entropy extremes, template + LLM-hook compression.

## What the observer is NOT

No significance filtering yet (that is display-level and comes with the
query engine), no LLM, no cross-seed statistics, no write capability.
The observer cannot change what it observes — the four layers above only
rearrange what the journal already contains.
