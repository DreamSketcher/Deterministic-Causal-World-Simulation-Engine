# Causal survival experiment — seed 7

Kernel **v0.1 (frozen)**, ruleset **0.3.1-ctrl** — the laws
differ from the baseline by proposal only; the kernel, the purposes
and the addressable draw stream are unchanged.

> Control: default v0.1 laws, disease system removed entirely. Isolates the abiotic (food/soil) dynamics.

## Run

| parameter | value |
|---|---|
| seed | 7 |
| ruleset | 0.3.1-ctrl |
| regions | 10 |
| agents | 1000 |
| ticks | 10000 |
| wall time | 698s |
| archive | `runs/survival_seed7_no_disease.db` |
| survivors | 0 / 1000 |
| deaths | 1000 |
| last death | tick 573 |

## Lifespan distribution (all agents died: no censoring)

| pct | ticks |
|---|---|
| p0 | 83 |
| p10 | 185 |
| p25 | 253 |
| p50 | 407 |
| p75 | 425 |
| p90 | 573 |
| p100 | 573 |

mean lifespan: **369** ticks

## Statistical regularity: correlations with lifespan

| observable | pearson | spearman |
|---|---|---|
| initial_health | -0.018 | -0.018 |
| initial_immunity | -0.032 | -0.033 |
| risk_tolerance | -0.007 | +0.020 |
| migration_count | -0.001 | +0.033 |
| infection_count | +nan | +nan |
| avg_food_access | +0.698 | +0.746 |
| avg_social_density | +0.643 | +0.594 |

## Individual causality: death mechanisms (from traces)

| mechanism | deaths | share |
|---|---|---|
| starvation | 1000 | 100.0% |

> **Interpretation caveat.** `migration_count`, `infection_count` and
> the sampled food/density aggregates are *time-at-risk* variables:
> agents that die early simply have fewer ticks in which to migrate
> or meet pathogens. A positive correlation of such a variable with
> lifespan is therefore expected even when the variable is harmful.
> The group tables below exist precisely to confront those numbers
> with per-death causal mechanisms.

## Statistical regularity vs individual causality

### Migration — same observable, different mechanisms?

| group | n | mean lifespan | starvation |
|---|---|---|---|
| stayers (0 migrations) | 40 | 259 | 40 |
| migrants (>=1 migration) | 960 | 373 | 960 |

### Risk tolerance quartiles

| group | n | mean lifespan | starvation |
|---|---|---|---|
| risk Q1 (lowest) | 250 | 357 | 250 |
| risk Q2 | 250 | 396 | 250 |
| risk Q3 | 250 | 364 | 250 |
| risk Q4 (highest) | 250 | 358 | 250 |

## Example mechanical explanations

### agent:0 — starvation (died tick 177, T348851)

```
T348851 AgentSystem.agent.death (tick 177)
Inputs:
  agent:0.alive = true ← T1
  agent:0.health = 2.0 ← T346964
  agent:0.hunger = 0.93 ← T347830
  agent:0.infected = false ← T1
Writes:
  agent:0.alive: true → false
  agent:0.health: 2.0 → 0.0
  T1 GenesisSystem.genesis.agent (tick 0)
  Random:
    genesis.attribute@agent:0 = 0.167553
    genesis.attribute@agent:0 = 0.600719
    genesis.attribute@agent:0 = 0.802272
    genesis.attribute@agent:0 = 0.758627
  Writes:
    agent:0.alive: none → true
    agent:0.health: none → 70.026603
    agent:0.hunger: none → 0.280216
    agent:0.immunity: none → 0.691249
    agent:0.infected: none → false
    agent:0.region: none → region:0
    agent:0.risk_tolerance: none → 0.758627
  T346964 AgentSystem.agent.health (tick 176)
  Inputs:
    agent:0.alive = true ← T1
    agent:0.health = 4.0 ← T345084
    agent:0.hunger = 0.96 ← T345941
    agent:0.infected = false ← T1
  Writes:
    agent:0.health: 4.0 → 2.0
    T1 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:0 = 0.167553
      genesis.attribute@agent:0 = 0.600719
      genesis.attribute@agent:0 = 0.802272
      genesis.attribute@agent:0 = 0.758627
    Writes:
      agent:0.alive: none → true
      agent:0.health: none → 70.026603
      agent:0.hunger: none → 0.280216
      agent:0.immunity: none → 0.691249
      agent:0.infected: none → false
      agent:0.region: none → region:0
      agent:0.risk_tolerance: none → 0.758627
    T345084 AgentSystem.agent.health (tick 175)
    Inputs:
      agent:0.alive = true ← T1
      agent:0.health = 6.0 ← T343186
      agent:0.hunger = 0.89 ← T344049
      agent:0.infected = false ← T1
    Writes:
      agent:0.health: 6.0 → 4.0
      T1 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:0 = 0.167553
        genesis.attribute@agent:0 = 0.600719
        genesis.attribute@agent:0 = 0.802272
        genesis.attribute@agent:0 = 0.758627
      Writes:
        agent:0.alive: none → true
        agent:0.health: none → 70.026603
        agent:0.hunger: none → 0.280216
        agent:0.immunity: none → 0.691249
        agent:0.infected: none → false
        agent:0.region: none → region:0
        agent:0.risk_tolerance: none → 0.758627
      T343186 AgentSystem.agent.health (tick 174)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.health = 8.0 ← T341289
        agent:0.hunger = 0.82 ← T342152
        agent:0.infected = false ← T1
      Writes:
        agent:0.health: 8.0 → 6.0
      T344049 AgentSystem.agent.metabolism (tick 174)
      Inputs:
        agent:0.hunger = 0.82 ← T342152
        agent:0.immunity = 0.063838 ← T342152
        agent:0.region = region:0 ← T343106
        region:0.food_stock = 0.0 ← T343161
        region:0.population = 13 ← T343151
      Writes:
        agent:0.hunger: 0.82 → 0.89
        agent:0.immunity: 0.063838 → 0.056618
    T345941 AgentSystem.agent.metabolism (tick 175)
    Inputs:
      agent:0.hunger = 0.89 ← T344049
      agent:0.immunity = 0.056618 ← T344049
      agent:0.region = region:1 ← T345002
      region:1.food_stock = 0.0 ← T345061
      region:1.population = 16 ← T345051
    Writes:
      agent:0.hunger: 0.89 → 0.96
      agent:0.immunity: 0.056618 → 0.048735
      T344049 AgentSystem.agent.metabolism (tick 174)
      Inputs:
        agent:0.hunger = 0.82 ← T342152
        agent:0.immunity = 0.063838 ← T342152
        agent:0.region = region:0 ← T343106
        region:0.food_stock = 0.0 ← T343161
        region:0.population = 13 ← T343151
      Writes:
        agent:0.hunger: 0.82 → 0.89
        agent:0.immunity: 0.063838 → 0.056618
      T345002 AgentSystem.agent.migrate (tick 174)
      Inputs:
        agent:0.hunger = 0.82 ← T342152
        agent:0.region = region:0 ← T343106
        agent:0.risk_tolerance = 0.758627 ← T1
      Random:
        agent.decision@agent:0 = 0.068752 threshold=0.379314
      Writes:
        agent:0.region: region:0 → region:1
      T345051 AgentSystem.agents.census (tick 174)
      Inputs:
        agent:123.alive = true ← T29
        agent:123.region = region:1 ← T339300
        agent:181.alive = false ← T164220
        agent:181.region = region:1 ← T93
        agent:314.alive = true ← T241
        agent:314.region = region:1 ← T333485
        agent:343.alive = true ← T273
        agent:343.region = region:1 ← T343118
        … 42 more input(s)
      Writes:
        region:1.population: 18 → 16
        region:1.workers: 18 → 16
      T345061 AgricultureSystem.agriculture.harvest (tick 174)
      Inputs:
        region:1.food_stock = 0.0 ← T343162
        region:1.population = 18 ← T343152
        region:1.rainfall = 0.383707 ← T343172
        region:1.soil_fertility = 0.373832 ← T343162
        region:1.temperature = 8.096762 ← T343172
        region:1.workers = 18 ← T343152
      Random:
        agriculture.crop_variance@region:1 = 0.541568
      Writes:
        region:1.food_stock: 0.0 → 0.0
        region:1.soil_fertility: 0.373832 → 0.372932
  T347830 AgentSystem.agent.metabolism (tick 176)
  Inputs:
    agent:0.hunger = 0.96 ← T345941
    agent:0.immunity = 0.048735 ← T345941
    agent:0.region = region:2 ← T346889
    region:2.food_stock = 352.993772 ← T346942
    region:2.population = 134 ← T346932
  Writes:
    agent:0.hunger: 0.96 → 0.93
    agent:0.immunity: 0.048735 → 0.041192
    T345941 AgentSystem.agent.metabolism (tick 175)
    Inputs:
      agent:0.hunger = 0.89 ← T344049
      agent:0.immunity = 0.056618 ← T344049
      agent:0.region = region:1 ← T345002
      region:1.food_stock = 0.0 ← T345061
      region:1.population = 16 ← T345051
    Writes:
      agent:0.hunger: 0.89 → 0.96
      agent:0.immunity: 0.056618 → 0.048735
      T344049 AgentSystem.agent.metabolism (tick 174)
      Inputs:
        agent:0.hunger = 0.82 ← T342152
        agent:0.immunity = 0.063838 ← T342152
        agent:0.region = region:0 ← T343106
        region:0.food_stock = 0.0 ← T343161
        region:0.population = 13 ← T343151
      Writes:
        agent:0.hunger: 0.82 → 0.89
        agent:0.immunity: 0.063838 → 0.056618
      T345002 AgentSystem.agent.migrate (tick 174)
      Inputs:
        agent:0.hunger = 0.82 ← T342152
        agent:0.region = region:0 ← T343106
        agent:0.risk_tolerance = 0.758627 ← T1
      Random:
        agent.decision@agent:0 = 0.068752 threshold=0.379314
      Writes:
        agent:0.region: region:0 → region:1
      T345051 AgentSystem.agents.census (tick 174)
      Inputs:
        agent:123.alive = true ← T29
        agent:123.region = region:1 ← T339300
        agent:181.alive = false ← T164220
        agent:181.region = region:1 ← T93
        agent:314.alive = true ← T241
        agent:314.region = region:1 ← T333485
        agent:343.alive = true ← T273
        agent:343.region = region:1 ← T343118
        … 42 more input(s)
      Writes:
        region:1.population: 18 → 16
        region:1.workers: 18 → 16
      T345061 AgricultureSystem.agriculture.harvest (tick 174)
      Inputs:
        region:1.food_stock = 0.0 ← T343162
        region:1.population = 18 ← T343152
        region:1.rainfall = 0.383707 ← T343172
        region:1.soil_fertility = 0.373832 ← T343162
        region:1.temperature = 8.096762 ← T343172
        region:1.workers = 18 ← T343152
      Random:
        agriculture.crop_variance@region:1 = 0.541568
      Writes:
        region:1.food_stock: 0.0 → 0.0
        region:1.soil_fertility: 0.373832 → 0.372932
    T346889 AgentSystem.agent.migrate (tick 175)
    Inputs:
      agent:0.hunger = 0.89 ← T344049
      agent:0.region = region:1 ← T345002
      agent:0.risk_tolerance = 0.758627 ← T1
    Random:
      agent.decision@agent:0 = 0.135564 threshold=0.379314
    Writes:
      agent:0.region: region:1 → region:2
      T1 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:0 = 0.167553
        genesis.attribute@agent:0 = 0.600719
        genesis.attribute@agent:0 = 0.802272
        genesis.attribute@agent:0 = 0.758627
      Writes:
        agent:0.alive: none → true
        agent:0.health: none → 70.026603
        agent:0.hunger: none → 0.280216
        agent:0.immunity: none → 0.691249
        agent:0.infected: none → false
        agent:0.region: none → region:0
        agent:0.risk_tolerance: none → 0.758627
      T344049 AgentSystem.agent.metabolism (tick 174)
      Inputs:
        agent:0.hunger = 0.82 ← T342152
        agent:0.immunity = 0.063838 ← T342152
        agent:0.region = region:0 ← T343106
        region:0.food_stock = 0.0 ← T343161
        region:0.population = 13 ← T343151
      Writes:
        agent:0.hunger: 0.82 → 0.89
        agent:0.immunity: 0.063838 → 0.056618
      T345002 AgentSystem.agent.migrate (tick 174)
      Inputs:
        agent:0.hunger = 0.82 ← T342152
        agent:0.region = region:0 ← T343106
        agent:0.risk_tolerance = 0.758627 ← T1
      Random:
        agent.decision@agent:0 = 0.068752 threshold=0.379314
      Writes:
        agent:0.region: region:0 → region:1
    T346932 AgentSystem.agents.census (tick 175)
    Inputs:
      agent:10.alive = true ← T3
      agent:10.region = region:2 ← T282865
      agent:102.alive = true ← T6
      agent:102.region = region:2 ← T6
      agent:112.alive = true ← T17
      agent:112.region = region:2 ← T17
      agent:12.alive = true ← T25
      agent:12.region = region:2 ← T25
      … 262 more input(s)
    Writes:
      region:2.population: 131 → 134
      region:2.workers: 131 → 134
      T3 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:10 = 0.131275
        genesis.attribute@agent:10 = 0.977697
        genesis.attribute@agent:10 = 0.817259
        genesis.attribute@agent:10 = 0.381925
      Writes:
        agent:10.alive: none → true
        agent:10.health: none → 68.938243
        agent:10.hunger: none → 0.393309
        agent:10.immunity: none → 0.699493
        agent:10.infected: none → false
        agent:10.region: none → region:0
        agent:10.risk_tolerance: none → 0.381925
      T6 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:102 = 0.490472
        genesis.attribute@agent:102 = 0.810607
        genesis.attribute@agent:102 = 0.379354
        genesis.attribute@agent:102 = 0.439861
      Writes:
        agent:102.alive: none → true
        agent:102.health: none → 79.714166
        agent:102.hunger: none → 0.343182
        agent:102.immunity: none → 0.458645
        agent:102.infected: none → false
        agent:102.region: none → region:2
        agent:102.risk_tolerance: none → 0.439861
      T17 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:112 = 0.325946
        genesis.attribute@agent:112 = 0.993973
        genesis.attribute@agent:112 = 0.699705
        genesis.attribute@agent:112 = 0.113679
      Writes:
        agent:112.alive: none → true
        agent:112.health: none → 74.778392
        agent:112.hunger: none → 0.398192
        agent:112.immunity: none → 0.634838
        agent:112.infected: none → false
        agent:112.region: none → region:2
        agent:112.risk_tolerance: none → 0.113679
      T25 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:12 = 0.163393
        genesis.attribute@agent:12 = 0.465792
        genesis.attribute@agent:12 = 0.123643
        genesis.attribute@agent:12 = 0.021251
      Writes:
        agent:12.alive: none → true
        agent:12.health: none → 69.901801
        agent:12.hunger: none → 0.239737
        agent:12.immunity: none → 0.318003
        agent:12.infected: none → false
        agent:12.region: none → region:2
        agent:12.risk_tolerance: none → 0.021251
      … 166 more parent(s)
    T346942 AgricultureSystem.agriculture.harvest (tick 175)
    Inputs:
      region:2.food_stock = 394.129369 ← T345062
      region:2.population = 131 ← T345052
      region:2.rainfall = 0.502979 ← T345072
      region:2.soil_fertility = 0.336409 ← T345062
      region:2.temperature = 19.641039 ← T345072
      region:2.workers = 131 ← T345052
    Random:
      agriculture.crop_variance@region:2 = 0.56508
    Writes:
      region:2.food_stock: 394.129369 → 352.993772
      region:2.soil_fertility: 0.336409 → 0.335509
      T345052 AgentSystem.agents.census (tick 174)
      Inputs:
        agent:10.alive = true ← T3
        agent:10.region = region:2 ← T282865
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        … 256 more input(s)
      Writes:
        region:2.population: 128 → 131
        region:2.workers: 128 → 131
      T345062 AgricultureSystem.agriculture.harvest (tick 174)
      Inputs:
        region:2.food_stock = 429.55673 ← T343163
        region:2.population = 128 ← T343153
        region:2.rainfall = 0.490727 ← T343173
        region:2.soil_fertility = 0.337309 ← T343163
        region:2.temperature = 19.197691 ← T343173
        region:2.workers = 128 ← T343153
      Random:
        agriculture.crop_variance@region:2 = 0.63005
      Writes:
        region:2.food_stock: 429.55673 → 394.129369
        region:2.soil_fertility: 0.337309 → 0.336409
      T345072 ClimateSystem.climate.step (tick 174)
      Inputs:
        region:2.climate_volatility = 0.508114 ← T1003
        region:2.rainfall = 0.490727 ← T343173
        region:2.rainfall_base = 0.553388 ← T1003
        region:2.temperature = 19.197691 ← T343173
        region:2.temperature_base = 18.487763 ← T1003
      Random:
        climate.temperature_noise@region:2 = 0.988732
        climate.rain@region:2 = 0.497661
      Writes:
        region:2.rainfall: 0.490727 → 0.502979
        region:2.temperature: 19.197691 → 19.641039
```

## Reproduction

```bash
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset no_disease_control --db runs/survival_seed7_no_disease.db --report <path>
```

Same seed + kernel v0.1.0 + ruleset 0.3.1-ctrl → bit-identical world, identical traces, identical report.