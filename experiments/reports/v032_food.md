# v0.3.2 — can the world live WITH the soil clock?

Frozen **CAUSAL KERNEL v0.1** (tag `v0.1.0`). Same seed (7), same scale
(10 regions × 1000 agents × 10 000 ticks), immune memory on in all three
worlds. v0.3.1 proved the collapse clock is the unconditional soil
depletion (−0.0009/tick, floor 0.05). These three rulesets keep the clock
and ask whether a realistic food-side mechanism lets the population live
with it — no magic, no removing the degradation.

## The mechanisms

| ruleset | law change | realism |
|---|---|---|
| `fallow` (0.3.2d) | abandoned regions (population 0) recover +0.0015/tick and stop degrading; farmed regions degrade exactly as before | abandoned fields regain fertility |
| `storage` (0.3.2e) | spoilage 2 % only above 50 rations/agent of stock, → 0 for tiny stocks, 4 % for surpluses above 10 rations/agent | small stocks are eaten before rotting; big granaries rot |
| `crop_rotation` (0.3.2f) | degradation ×(1 + 0.5·(1 − cv)), cv = workforce fluctuation over a ~10-tick window: stable monoculture degrades 50 % faster, fluctuating load rests the soil | crop rotation vs monoculture |

(One transcription note: the literal fallow condition
`workers < population × 0.3` can never fire in the frozen laws — `workers`
is the census alive-count, always equal to `population` — so the law uses
the meaningful signal: presence.)

## The comparison

| measure | 0.3.0 immune | D fallow | E storage | F rotation | B stable_soil¹ |
|---|---|---|---|---|---|
| survivors | 0/1000 | 0/1000 | 0/1000 | 0/1000 | **950/1000** |
| extinction tick | 573 | **794** | 594 | **514** | — |
| mean lifespan | 335 | 340 | 353 | 302 | 3803² |
| median lifespan | 396 | 396 | 409 | 351 | 4000² |
| mechanism mix | d+s 95.4 % | d+s 95.8 % | d+s 95.6 % | d+s 95.9 % | (50 early deaths) |

¹ Reference from v0.3.1: the only world that lives — degradation removed
entirely.  ² Censored at the 4000-tick run.

Death counts per 100-tick window (out of 1000):

```
window  | fallow        storage       rotation
0-99    |   63 → 937      68 → 932      66 → 934
100-199 |  131 → 806     109 → 823     148 → 786
200-299 |  249 → 557     250 → 573     218 → 568
300-399 |   86 → 471      53 → 520     430 → 138
400-499 |  332 → 139     383 → 137      50 →  88
500-599 |  113 →  26     137 →   0      88 →   0
600-699 |   13 →  13       —              —
700-794 |   13 →   0       —              —
```

## What happened in each world

**D — fallow came closest and produced the first self-generated spatial
pattern.** The population concentrated into 2–3 regions while everything
else emptied, and the abandoned regions *did* heal — soil recovered toward
1.0 exactly as the law prescribes (region 1: 0.53 → 0.43 → 0.53 → 0.75 →
1.0). Deaths even paused between waves (only 86 deaths in ticks 300–399,
and 13 agents survived past tick 600). But the oscillation never
self-sustained: the remnant population died inside the last farmed regions
instead of recolonizing the healed ones — migration in the frozen laws is
a hunger-gated random walk to the *next* region, not a move toward fertile
land. Extinction moved from tick 573 to 794 — a delay, not a rescue.

**E — storage changed almost nothing (594 vs 573).** The collapse is not a
peak deficit (bad seasons on an empty buffer) — it is the average deficit.
Smoothing spoilage does not create food that the soil no longer produces.

**F — rotation made the collapse *faster* (514).** The negative feedback
exists on paper, but during the phase when it matters the workforce is
stable (everyone alive and farming), so cv ≈ 0 and the penalty sits at its
maximum: degradation runs 50 % faster than the frozen clock. The
fluctuation regime only arrives with the collapse itself — too late to be
useful. A behavioral feedback that activates only after the crisis is not
a stabilizer.

## The arithmetic behind the verdict

Per-capita harvest = `3.6 × temp × rain × soil × variance`; consumption =
1.1/agent/tick. The region stops feeding itself when soil falls below

* ≈ 0.38 under typical climate,
* ≈ 0.19 even under the best possible climate.

From the mean genesis soil (~0.55) the frozen clock reaches 0.38 in ~190
ticks and the absolute best-case break-even in ~400; the floor is 0.05,
deep inside the starvation zone. **While a region is farmed, net soil
change is negative in all three rulesets** — none of the mechanisms adds
fertility where agents actually farm. So no behavioral adaptation in this
family can save the population: the degradation rate is fundamentally
incompatible with 1000 agents at this consumption level.

## Verdict and next step

The decision tree of v0.3.1 lands on its last branch: *none of the three
survives → the degradation rate itself is the parameter that decides
survival*. The world needs fertility **maintenance where farming happens**
(manure/compost tied to consumption, resting farmed fields, or a slower
depletion constant) — each still a ruleset, kernel untouched. The
observer stage (v0.4) should wait for that: today's regime zoo has one
equilibrium world reached by magic, and everything else is the same
collapse in four costumes; fallow is the most interesting costume (a real
spatial oscillation attempt), which is worth keeping as a comparison
regime later.

## Reproduction

```bash
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset fallow --db runs/survival_seed7_fallow.db --report <path>
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset storage --db runs/survival_seed7_storage.db --report <path>
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset crop_rotation --db runs/survival_seed7_rotation.db --report <path>
```

Per-run reports: `survival_seed7_{fallow,storage,rotation}.md` in this
directory. Same seed + kernel v0.1.0 + same ruleset → bit-identical world,
identical traces, identical report (pinned by `tests/test_food_rulesets.py`).
