# v0.3.1 — structural diagnosis of the collapse

Frozen **CAUSAL KERNEL v0.1** (tag `v0.1.0`). Same seed (7), same scale
(10 regions × 1000 agents × 10 000 ticks), one severed link per ruleset.
The v0.3 immune world still collapsed; the question is no longer *does*
it collapse but *which link of the spiral is the bottleneck*.

## The experiments

Each row is a separate ruleset — kernel untouched, laws-only:

| ruleset | severed link | implementation |
|---|---|---|
| `iron_health` (0.3.1a) | infection → health | no acute damage, no chronic −2.5/tick erosion while infected; memory intact |
| `stable_soil` (0.3.1b) | soil depletion | `soil_fertility` no longer depletes (the frozen law's unconditional −0.0009/tick countdown removed) |
| `no_hunger_immunity` (0.3.1c) | hunger → susceptibility | infection probability at the well-fed constant; immunity no longer erodes with hunger |
| `no_disease_control` (0.3.1-ctrl) | the pathogen itself | default v0.1 laws, disease system removed entirely |

Two architectural facts discovered while cutting:

* The literal proposal "harvest independent of workers' health" is the
  **existing law** — `harvest = f(climate, soil, workers_count)` already
  reads no health, and `workers` is a plain alive-count. The health→labor
  link the spiral diagram assumed does not exist in the frozen rules. The
  real food-side link is the soil clock, which is what experiment B tests.
* Soil depletes unconditionally (`new_soil = clamp(soil − 0.0012 +
  0.0003, 0.05, 1)` — net −0.0009/tick, floor 0.05, no restoration
  mechanism). It is a countdown built into the world.

## The comparison

| measure | 0.1.0 baseline | 0.3.0 immune | A iron_health | B stable_soil¹ | C no_hunger | control no_disease |
|---|---|---|---|---|---|---|
| survivors | 0 / 1000 | 0 / 1000 | 0 / 1000 | **950 / 1000** | 0 / 1000 | 0 / 1000 |
| extinction tick | 553 | 573 | 573 | — (alive at run end) | 573 | 573 |
| mean lifespan | 141 | 335 | 368 | 3803² | 358 | 369 |
| median lifespan | 82 | 396 | 407 | 4000² | 405 | 407 |
| dominant death mechanism | disease 51.2 % | dis+starv 95.4 % | dis+starv 100 % | dis+starv 82 % of 50 | dis+starv 98.9 % | **starvation 100 %** |
| corr(food access, life) | +0.35 | +0.72 | +0.70 | +0.24 | +0.70 | +0.70 |
| corr(density, life) | −0.90 | +0.68 | +0.64 | +0.64 | +0.67 | +0.64 |

¹ Run truncated at 4000 ticks: with 950 agents alive the full-journal
archive exceeds the 21 GB disk of the sandbox (~10 GB at tick 4000 and
growing ~2.4 GB per 1000 ticks). Survival was already unambiguous:
the last death happened at tick 83, then 3917 ticks with zero deaths.
² Censored: survivors counted at run end (4000).

## What the numbers say

1. **The collapse clock does not read the disease variables.** Four
   rulesets with radically different disease dynamics — full memory
   (immune), zero infection damage (iron_health), no hunger-susceptibility
   coupling (no_hunger), and **no pathogen at all** (control) — go extinct
   at the *same tick* (573) with nearly identical lifespan distributions
   (median 396–407, mean 335–369). Whatever the spiral does, it does not
   set the time of death; something else does, and it is shared by all
   four worlds.

2. **The control isolates it: starvation, with no disease present.**
   In `no_disease_control` every one of the 1000 deaths is classified
   `starvation` — the causal traces contain no infection anywhere — and
   they land on the same tick-573 clock. The food base, not the pathogen,
   is what runs out.

3. **Stop the soil clock and the population survives.** In `stable_soil`
   (the only law changed: no soil depletion) the population loses 50
   agents in the first 83 ticks and then **zero deaths for the remaining
   3917 ticks** — 950/1000 alive at the end. Disease is still fully
   active in this world (memory, reinfection, damage all as in 0.3.0);
   it simply stops being lethal once food keeps coming.

4. **Bottleneck verdict: the soil countdown.** The spiral
   infection→health→hunger→susceptibility is real and it shapes *how*
   agents die (the mechanism mix), but the population-level collapse is
   driven by the terminal resource: unconditional soil depletion
   (−0.0009/tick, floor 0.05, no restoration). Remove one pressure
   (any disease-side link) and nothing changes; remove the soil clock and
   the system stabilizes. This is the "most interesting" branch of the
   original hypothesis tree: the collapse is structural and abiotic.

5. **The correlations corroborate.** In every collapsing world lifespan
   correlates with food access (+0.70) and density (+0.64 — dense regions
   hold food longer) regardless of the disease laws. The −0.90 density
   correlation of the 0.1.0 baseline was a property of the *acute*
   disease regime; once deaths moved onto the food clock, the statistical
   signature moved with them.

## A note on the early deaths in stable_soil

The 50 deaths (all by tick 83) are agents caught by early acute/disease
chains before immune memory accumulates and before the food base reaches
equilibrium; after memory saturates and food stabilizes, the disease
channel stops killing. This is consistent with the v0.3 finding that
memory blunts damage below lethality — here, given food, below lethality
*permanently*.

## What this means for v0.4+

* The next experiment is no longer "break another disease link" — the
  disease side is not the bottleneck. The live question is the food side:
  is there a law change (e.g. soil restoration tied to farming behavior,
  food storage, or rationing) that lets the *unmodified* soil dynamics
  sustain the population, i.e. a realistic mechanism instead of removing
  the clock?
* The observer (roadmap v0.4) now has genuinely different regimes to
  compare: four collapse worlds with identical extinction clocks but
  different causal mechanisms of death, and one equilibrium world —
  "why did agent X live 4000 ticks in world B but its statistical twin
  died at 407 in world C?" is now a meaningful question with a causal
  answer.

## Reproduction

```bash
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset iron_health --db runs/survival_seed7_iron_health.db --report <path>
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 4000  --ruleset stable_soil --db runs/survival_seed7_stable_soil.db --report <path>
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset no_hunger_immunity --db runs/survival_seed7_no_hunger.db --report <path>
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset no_disease_control --db runs/survival_seed7_no_disease.db --report <path>
```

Per-run reports: `survival_seed7_<ruleset>.md` in this directory.
Same seed + kernel v0.1.0 + same ruleset → bit-identical world,
identical traces, identical report (pinned by `tests/`).
