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
extinction t573, trajectory identical to v0.3: determinism across months
of code growth), fertile_migration 0.3.3i (1500 ticks, extinction t710,
identical to v0.3.3), compost 0.3.3g (5000 ticks, 937/1000 alive at the
end; the 10k compost run of v0.3.3 showed the identical trajectory).
Reproducible: `python3 experiments/observer_demo.py`.

## L2 — regime classification (journal only, no ruleset knowledge)

| archive | classified regime | extinction | soil trajectory | death causes |
|---|---|---|---|---|
| immune 0.3.0 | COLLAPSE (0.95) | t573 | monotonic_decline | disease+starvation 99.3 % |
| fertile_migration 0.3.3i | COLLAPSE (0.95) | t710 | recovering | disease+starvation 99.3 % |
| compost 0.3.3g | EQUILIBRIUM (0.90) | — (pop 937) | recovering | disease+starvation 85 %, disease 15 % (60 deaths, all burn-in) |

Two things are worth pausing on:

* The classifier does not know these are three different rulesets. It
  sees three population curves and three soil curves and labels them
  correctly — including the *shape* difference between the two
  collapses: immune soil declines monotonically, while the herding
  world's soil is "recovering" (fallow heals the abandoned regions) even
  while the population dies. The compost world's soil is also labelled
  recovering: it spends the run climbing from the burn-in trough up to
  the per-region balance points.
* EQUILIBRIUM here is a statement about the final 20 % of the run
  (population CV < 5 %), not a hint from the laws: 937 agents, unchanged
  since t≈2000.

## L1 — the budget: one line separates the regimes

Immune 0.3.0, `region:4.soil_fertility`, full run:

```
INFLOWS:  (none)
OUTFLOWS: AgricultureSystem.agriculture.harvest  −0.574505
          over 639 effective writes (mean −0.000899)
NET: −0.574505     ← monotonic decline to the 0.05 floor
```

Compost G, `region:4.soil_fertility`, late equilibrium window t4000–4999:

```
INFLOWS:  CompostAgricultureSystem.agriculture.harvest  +0.000055
          over 1000 effective writes (mean +5.5e-08)
OUTFLOWS: (none)
NET: +0.000055     ← balance: four orders of magnitude below the
                     immune rate (−0.000899 per effective write)
```

Two implementation realities the observer surfaces honestly:

1. **The 0.05 floor is visible in the budget.** Region:4 has 10 000 soil
   writes in the immune run, but only 639 of them changed the value —
   after the floor is reached the remaining ~9 360 writes are clamp
   no-ops (delta 0) and contribute nothing. The observer counts *actual
   change*, not activity.
2. **Compost is one transition, not two.** The frozen law updates soil in
   a single `agriculture.harvest` transition
   (`−0.0009 + pop × 0.000018 × (1−soil)`), so there is no separate
   `compost_recovery` operation to point at. The regime difference
   therefore appears at the *system* level — which is exactly what L3
   reports.

## L3 — comparator: what is causally different?

`CausalComparator(immune, compost).compare_field("region:4", "soil_fertility")`:

```
inflows only in compost:  [CompostAgricultureSystem.agriculture.harvest]
outflows only in immune:  [AgricultureSystem.agriculture.harvest]
net delta (soil_fertility): +0.629484
loop diff: "regime compost has an inflow (agriculture.harvest) that
            immune lacks: the loop closes."
```

The comparator, knowing nothing about compost, finds the single
structural difference: in regime B there exists a writer that returns
fertility to the soil; in regime A there is none. Everything else —
climate, disease, consumption — is shared. This is "what changed between
0.3.0 and G" derived purely from journal comparison.

## The five questions of the v0.4 spec

**Q1. Why is region:4 alive and region:1 dead in the compost world?**
L1 + journal: the genesis disease burn-in emptied region:1 (last
inhabited at tick 1408, final population 0) while region:4 kept 156
agents. The budgets then show the
divergence: region:1 has **no inflow at all** — net −0.4804 to the
floor (final soil 0.05); once a region's population is gone, no agents
means no returns, and the clock keeps ticking. Region:4 sits at its
balance point (final soil 0.6795, net ≈ +0.05 over the run).
Population decides whether the loop closes.

**Q2. Why soil* = 0.679 for region:4?**
L1 balance: inflow = outflow means `pop × 0.000018 × (1−s) = 0.0009`,
hence `s = 1 − 50/pop`. With pop = 156: `1 − 50/156 = 0.6795` — the
archived final soil is **0.67948**, agreement to four decimals. The
observer can derive the formula from the budget alone.

**Q3. Why does disease not kill the compost world?**
Journal counts per 1000-tick window:

| window | infections | recoveries | deaths |
|---|---|---|---|
| t0–999 | 6921 | 6866 | 51 |
| t1000–1999 | 4287 | 4284 | 9 |
| t2000–2999 | 4139 | 4141 | 0 |
| t3000–3999 | 4141 | 4141 | 0 |
| t4000–4999 | 4166 | 4166 | 0 |

The endemic pool stabilizes at ~4 200 infection events per 1000 ticks,
recoveries match them one-for-one, deaths stop. Disease is present at
every tick of the equilibrium and kills nobody — immunity keeps it under
the lethal threshold.

**Q4. What changed between 0.3.0 and G?**
One line in the budget: the fertility inflow (L3 above). Everything else
is identical.

**Q5. Why do the sighted (I) die while the blind (G) live?**
Migration statistics from the journal:

| world | moves | movers | destinations | entropy | top destination |
|---|---|---|---|---|---|
| compost (blind) | 1 140 | 280 | 10 | **3.105 bits** | region:6 (18.3 %) |
| fertile_migration (informed) | 18 772 | 939 | 5 | **1.699 bits** | region:0 (43.7 %) |

The numbers invert the naive intuition. Blind migration — hunger-gated
random walks during the burn-in — is *diffusion*: nearly uniform over
all ten regions, entropy 3.10 bits against the 3.32-bit maximum.
Informed migration is *herding*: nearly half of 18 772 moves target one
region, entropy 1.70 bits. Perfect information synchronizes the herd
onto the best region, concentrates the load exactly where load
concentration kills (v0.3.2), and strips it. The blind world's moves
also peter out once the loop closes (the hunger gate shuts); the sighted
world never stops shuffling toward whichever region looks best this
tick. Information moves agents; only a closed nutrient cycle keeps them
alive.

## L4 — narrative compression (template mode)

The first death of the immune world — and, tick-for-tick, of the compost
world too (agent:769, same draws, same chain; determinism made visible):

```
t0 GenesisSystem.genesis.agent -> region:None->region:9,
   health:None->68.44, hunger:None->0.318, infected:None->False
   [genesis.attribute 0.103]
...
t27 AgentSystem.agent.metabolism -> hunger:0.0->0.0,
   immunity:0.3416->0.3419 (reads hunger=0.0, region=region:9)
t28 AgentSystem.agent.death -> alive:True->False,
   health:0.874->0.0 (reads infected=True, hunger=0.0)
```

Death at hunger 0.0 — the agent was not starving; it died infected during
the genesis burn-in. No LLM is involved; the structured trace above is
exactly what a pluggable LLM adapter would receive in v0.7.

## Engineering notes

* **SQL fast path.** L1 over a recorded archive runs as a single
  `json_each(payload,'$.writes')` aggregation (SQLite JSON1), so a
  million-transition journal budgets in seconds; the pure-Python path
  covers in-memory journals. The two are bit-identical (test
  `test_budget_sql_path_matches_python_path`). One trap found on the way:
  `json_type(json_extract(...))` raises `malformed JSON` on JSON null
  (genesis writes with `old=null`); the two-argument
  `json_type(value, path)` handles it.
* **Series are replays, not stored snapshots.** The v0.1 kernel persists
  no per-tick state; L2 reconstructs population/soil series by streaming
  committed writes once (exact, deterministic).
* **Oscillation detection is detrended.** Raw autocorrelation marks every
  monotone decline "periodic"; the classifier detrends first and rejects
  one-directional series.
* **L4 follows the freshest provenance** (highest source id among the
  deceased's reads), so a death narrative tracks the last health updates
  rather than the genesis write of `alive`.
* **CLI**: `python -m causal_world observe --db runs/x.db --budget
  region:4 soil_fertility --classify [--compare-db y.db ...]
  [--explain-death agent:7]`.

## Tests

106 → **121** (`tests/test_observer.py`, 15 tests): budget
inflow/outflow/net arithmetic, REJECTED-exclusion, tick windows,
determinism, SQL≡Python parity, read-only enforcement (file hash
unchanged after a full observation pass), regime classification of
synthetic collapse/equilibrium/oscillation series + a real archived
collapse, no-ruleset-knowledge guarantee, comparator missing-inflow
detection, migration entropy extremes, template + LLM-hook compression.

## What the observer is NOT

No significance filtering yet (that is display-level and comes with the
query engine), no LLM, no cross-seed statistics, no write capability.
The observer cannot change what it observes — the four layers above only
rearrange what the journal already contains.
