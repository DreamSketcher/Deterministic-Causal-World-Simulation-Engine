# Causal survival experiment — seed 7

Kernel **v0.1 (frozen)**, ruleset **0.3.1a** — the laws
differ from the baseline by proposal only; the kernel, the purposes
and the addressable draw stream are unchanged.

> Experiment A: infection deals no damage (no acute health write, no chronic erosion while infected). Memory works as in 0.3.0.

## Run

| parameter | value |
|---|---|
| seed | 7 |
| ruleset | 0.3.1a |
| regions | 10 |
| agents | 1000 |
| ticks | 10000 |
| wall time | 928s |
| archive | `runs/survival_seed7_iron_health.db` |
| survivors | 0 / 1000 |
| deaths | 1000 |
| last death | tick 573 |

## Lifespan distribution (all agents died: no censoring)

| pct | ticks |
|---|---|
| p0 | 77 |
| p10 | 185 |
| p25 | 253 |
| p50 | 407 |
| p75 | 425 |
| p90 | 573 |
| p100 | 573 |

mean lifespan: **368** ticks

## Statistical regularity: correlations with lifespan

| observable | pearson | spearman |
|---|---|---|
| initial_health | -0.017 | -0.016 |
| initial_immunity | -0.030 | -0.031 |
| risk_tolerance | -0.006 | +0.022 |
| migration_count | -0.000 | +0.035 |
| infection_count | +0.315 | +0.298 |
| avg_food_access | +0.699 | +0.749 |
| avg_social_density | +0.643 | +0.592 |

## Individual causality: death mechanisms (from traces)

| mechanism | deaths | share |
|---|---|---|
| disease+starvation | 1000 | 100.0% |

> **Interpretation caveat.** `migration_count`, `infection_count` and
> the sampled food/density aggregates are *time-at-risk* variables:
> agents that die early simply have fewer ticks in which to migrate
> or meet pathogens. A positive correlation of such a variable with
> lifespan is therefore expected even when the variable is harmful.
> The group tables below exist precisely to confront those numbers
> with per-death causal mechanisms.

## Statistical regularity vs individual causality

### Migration — same observable, different mechanisms?

| group | n | mean lifespan | disease+starvation |
|---|---|---|---|
| stayers (0 migrations) | 40 | 259 | 40 |
| migrants (>=1 migration) | 960 | 373 | 960 |

### Risk tolerance quartiles

| group | n | mean lifespan | disease+starvation |
|---|---|---|---|
| risk Q1 (lowest) | 250 | 356 | 250 |
| risk Q2 | 250 | 396 | 250 |
| risk Q3 | 250 | 364 | 250 |
| risk Q4 (highest) | 250 | 358 | 250 |

## Example mechanical explanations

### agent:0 — disease+starvation (died tick 177, T347109)

```
T347109 IronHealthAgentSystem.agent.death (tick 177)
Inputs:
  agent:0.alive = true ← T1
  agent:0.health = 2.0 ← T345211
  agent:0.hunger = 0.93 ← T346051
  agent:0.infected = false ← T296518
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
    agent:0.immune_memory: none → 0.0
    agent:0.immunity: none → 0.691249
    agent:0.infected: none → false
    agent:0.region: none → region:0
    agent:0.risk_tolerance: none → 0.758627
  T296518 IronHealthDiseaseSystem.disease.recover (tick 150)
  Inputs:
    agent:0.alive = true ← T1
    agent:0.hunger = 0.68 ← T293465
    agent:0.immune_memory = 1.0 ← T266427
    agent:0.immunity = 0.256839 ← T293465
    agent:0.infected = true ← T266427
  Random:
    disease.recovery@agent:0 = 0.028277 threshold=0.18221
  Writes:
    agent:0.infected: true → false
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
      agent:0.immune_memory: none → 0.0
      agent:0.immunity: none → 0.691249
      agent:0.infected: none → false
      agent:0.region: none → region:0
      agent:0.risk_tolerance: none → 0.758627
    T266427 IronHealthDiseaseSystem.disease.infect (tick 135)
    Inputs:
      agent:0.alive = true ← T1
      agent:0.hunger = 1.0 ← T263353
      agent:0.immune_memory = 0.7 ← T100178
      agent:0.immunity = 0.380166 ← T263353
      agent:0.infected = false ← T106062
      agent:0.region = region:3 ← T254534
      region:3.disease_load = 0.398184 ← T264410
    Random:
      disease.infection@agent:0 = 0.05857 threshold=0.100997
    Writes:
      agent:0.immune_memory: 0.7 → 1.0
      agent:0.infected: false → true
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
        agent:0.immune_memory: none → 0.0
        agent:0.immunity: none → 0.691249
        agent:0.infected: none → false
        agent:0.region: none → region:0
        agent:0.risk_tolerance: none → 0.758627
      T100178 IronHealthDiseaseSystem.disease.infect (tick 51)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.hunger = 0.0 ← T97224
        agent:0.immune_memory = 0.35 ← T88648
        agent:0.immunity = 0.616314 ← T97224
        agent:0.infected = false ← T98279
        agent:0.region = region:0 ← T1
        region:0.disease_load = 0.250982 ← T98245
      Random:
        disease.infection@agent:0 = 0.002905 threshold=0.023463
      Writes:
        agent:0.immune_memory: 0.35 → 0.7
        agent:0.infected: false → true
      T106062 IronHealthDiseaseSystem.disease.recover (tick 54)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.hunger = 0.0 ← T103052
        agent:0.immune_memory = 0.7 ← T100178
        agent:0.immunity = 0.613086 ← T103052
        agent:0.infected = true ← T100178
      Random:
        disease.recovery@agent:0 = 0.070734 threshold=0.313271
      Writes:
        agent:0.infected: true → false
      T254534 IronHealthAgentSystem.agent.migrate (tick 129)
      Inputs:
        agent:0.hunger = 0.697173 ← T251635
        agent:0.region = region:2 ← T238871
        agent:0.risk_tolerance = 0.758627 ← T1
      Random:
        agent.decision@agent:0 = 0.013783 threshold=0.379314
      Writes:
        agent:0.region: region:2 → region:3
      … 2 more parent(s)
    T293465 IronHealthAgentSystem.agent.metabolism (tick 149)
    Inputs:
      agent:0.hunger = 0.71 ← T291465
      agent:0.immunity = 0.262954 ← T291465
      agent:0.region = region:9 ← T282524
      region:9.food_stock = 4945.823816 ← T290567
      region:9.population = 142 ← T292514
    Writes:
      agent:0.hunger: 0.71 → 0.68
      agent:0.immunity: 0.262954 → 0.256839
      T282524 IronHealthAgentSystem.agent.migrate (tick 143)
      Inputs:
        agent:0.hunger = 0.89 ← T279533
        agent:0.region = region:8 ← T278516
        agent:0.risk_tolerance = 0.758627 ← T1
      Random:
        agent.decision@agent:0 = 0.028198 threshold=0.379314
      Writes:
        agent:0.region: region:8 → region:9
      T290567 AgricultureSystem.agriculture.harvest (tick 148)
      Inputs:
        region:9.food_stock = 4923.573908 ← T288597
        region:9.population = 144 ← T290526
        region:9.rainfall = 0.742867 ← T288607
        region:9.soil_fertility = 0.419123 ← T288597
        region:9.temperature = 17.648854 ← T288607
        region:9.workers = 144 ← T290526
      Random:
        agriculture.crop_variance@region:9 = 0.74024
      Writes:
        region:9.food_stock: 4923.573908 → 4945.823816
        region:9.soil_fertility: 0.419123 → 0.418223
      T291465 IronHealthAgentSystem.agent.metabolism (tick 148)
      Inputs:
        agent:0.hunger = 0.74 ← T289490
        agent:0.immunity = 0.269401 ← T289490
        agent:0.region = region:9 ← T282524
        region:9.food_stock = 4923.573908 ← T288597
        region:9.population = 144 ← T290526
      Writes:
        agent:0.hunger: 0.74 → 0.71
        agent:0.immunity: 0.269401 → 0.262954
      T292514 IronHealthAgentSystem.agents.census (tick 148)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.region = region:9 ← T282524
        agent:109.alive = true ← T13
        agent:109.region = region:9 ← T13
        agent:110.alive = true ← T15
        agent:110.region = region:9 ← T250721
        agent:111.alive = true ← T16
        agent:111.region = region:9 ← T94361
        … 278 more input(s)
      Writes:
        region:9.population: 144 → 142
        region:9.workers: 144 → 142
  T345211 IronHealthAgentSystem.agent.health (tick 176)
  Inputs:
    agent:0.alive = true ← T1
    agent:0.health = 4.0 ← T343319
    agent:0.hunger = 0.96 ← T344155
    agent:0.infected = false ← T296518
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
      agent:0.immune_memory: none → 0.0
      agent:0.immunity: none → 0.691249
      agent:0.infected: none → false
      agent:0.region: none → region:0
      agent:0.risk_tolerance: none → 0.758627
    T296518 IronHealthDiseaseSystem.disease.recover (tick 150)
    Inputs:
      agent:0.alive = true ← T1
      agent:0.hunger = 0.68 ← T293465
      agent:0.immune_memory = 1.0 ← T266427
      agent:0.immunity = 0.256839 ← T293465
      agent:0.infected = true ← T266427
    Random:
      disease.recovery@agent:0 = 0.028277 threshold=0.18221
    Writes:
      agent:0.infected: true → false
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
        agent:0.immune_memory: none → 0.0
        agent:0.immunity: none → 0.691249
        agent:0.infected: none → false
        agent:0.region: none → region:0
        agent:0.risk_tolerance: none → 0.758627
      T266427 IronHealthDiseaseSystem.disease.infect (tick 135)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.hunger = 1.0 ← T263353
        agent:0.immune_memory = 0.7 ← T100178
        agent:0.immunity = 0.380166 ← T263353
        agent:0.infected = false ← T106062
        agent:0.region = region:3 ← T254534
        region:3.disease_load = 0.398184 ← T264410
      Random:
        disease.infection@agent:0 = 0.05857 threshold=0.100997
      Writes:
        agent:0.immune_memory: 0.7 → 1.0
        agent:0.infected: false → true
      T293465 IronHealthAgentSystem.agent.metabolism (tick 149)
      Inputs:
        agent:0.hunger = 0.71 ← T291465
        agent:0.immunity = 0.262954 ← T291465
        agent:0.region = region:9 ← T282524
        region:9.food_stock = 4945.823816 ← T290567
        region:9.population = 142 ← T292514
      Writes:
        agent:0.hunger: 0.71 → 0.68
        agent:0.immunity: 0.262954 → 0.256839
    T343319 IronHealthAgentSystem.agent.health (tick 175)
    Inputs:
      agent:0.alive = true ← T1
      agent:0.health = 6.0 ← T341403
      agent:0.hunger = 0.89 ← T342246
      agent:0.infected = false ← T296518
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
        agent:0.immune_memory: none → 0.0
        agent:0.immunity: none → 0.691249
        agent:0.infected: none → false
        agent:0.region: none → region:0
        agent:0.risk_tolerance: none → 0.758627
      T296518 IronHealthDiseaseSystem.disease.recover (tick 150)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.hunger = 0.68 ← T293465
        agent:0.immune_memory = 1.0 ← T266427
        agent:0.immunity = 0.256839 ← T293465
        agent:0.infected = true ← T266427
      Random:
        disease.recovery@agent:0 = 0.028277 threshold=0.18221
      Writes:
        agent:0.infected: true → false
      T341403 IronHealthAgentSystem.agent.health (tick 174)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.health = 8.0 ← T339499
        agent:0.hunger = 0.82 ← T340342
        agent:0.infected = false ← T296518
      Writes:
        agent:0.health: 8.0 → 6.0
      T342246 IronHealthAgentSystem.agent.metabolism (tick 174)
      Inputs:
        agent:0.hunger = 0.82 ← T340342
        agent:0.immunity = 0.063838 ← T340342
        agent:0.region = region:0 ← T341296
        region:0.food_stock = 0.0 ← T339478
        region:0.population = 13 ← T341341
      Writes:
        agent:0.hunger: 0.82 → 0.89
        agent:0.immunity: 0.063838 → 0.056618
    T344155 IronHealthAgentSystem.agent.metabolism (tick 175)
    Inputs:
      agent:0.hunger = 0.89 ← T342246
      agent:0.immunity = 0.056618 ← T342246
      agent:0.region = region:1 ← T343199
      region:1.food_stock = 0.0 ← T341379
      region:1.population = 16 ← T343248
    Writes:
      agent:0.hunger: 0.89 → 0.96
      agent:0.immunity: 0.056618 → 0.048735
      T341379 AgricultureSystem.agriculture.harvest (tick 174)
      Inputs:
        region:1.food_stock = 0.0 ← T339479
        region:1.population = 18 ← T341342
        region:1.rainfall = 0.383707 ← T339489
        region:1.soil_fertility = 0.373832 ← T339479
        region:1.temperature = 8.096762 ← T339489
        region:1.workers = 18 ← T341342
      Random:
        agriculture.crop_variance@region:1 = 0.541568
      Writes:
        region:1.food_stock: 0.0 → 0.0
        region:1.soil_fertility: 0.373832 → 0.372932
      T342246 IronHealthAgentSystem.agent.metabolism (tick 174)
      Inputs:
        agent:0.hunger = 0.82 ← T340342
        agent:0.immunity = 0.063838 ← T340342
        agent:0.region = region:0 ← T341296
        region:0.food_stock = 0.0 ← T339478
        region:0.population = 13 ← T341341
      Writes:
        agent:0.hunger: 0.82 → 0.89
        agent:0.immunity: 0.063838 → 0.056618
      T343199 IronHealthAgentSystem.agent.migrate (tick 174)
      Inputs:
        agent:0.hunger = 0.82 ← T340342
        agent:0.region = region:0 ← T341296
        agent:0.risk_tolerance = 0.758627 ← T1
      Random:
        agent.decision@agent:0 = 0.068752 threshold=0.379314
      Writes:
        agent:0.region: region:0 → region:1
      T343248 IronHealthAgentSystem.agents.census (tick 174)
      Inputs:
        agent:123.alive = true ← T29
        agent:123.region = region:1 ← T337455
        agent:181.alive = false ← T161680
        agent:181.region = region:1 ← T93
        agent:314.alive = true ← T241
        agent:314.region = region:1 ← T331560
        agent:343.alive = true ← T273
        agent:343.region = region:1 ← T341308
        … 42 more input(s)
      Writes:
        region:1.population: 18 → 16
        region:1.workers: 18 → 16
  T346051 IronHealthAgentSystem.agent.metabolism (tick 176)
  Inputs:
    agent:0.hunger = 0.96 ← T344155
    agent:0.immunity = 0.048735 ← T344155
    agent:0.region = region:2 ← T345103
    region:2.food_stock = 352.993772 ← T343296
    region:2.population = 134 ← T345146
  Writes:
    agent:0.hunger: 0.96 → 0.93
    agent:0.immunity: 0.048735 → 0.041192
    T343296 AgricultureSystem.agriculture.harvest (tick 175)
    Inputs:
      region:2.food_stock = 394.129369 ← T341380
      region:2.population = 131 ← T343249
      region:2.rainfall = 0.502979 ← T341390
      region:2.soil_fertility = 0.336409 ← T341380
      region:2.temperature = 19.641039 ← T341390
      region:2.workers = 131 ← T343249
    Random:
      agriculture.crop_variance@region:2 = 0.56508
    Writes:
      region:2.food_stock: 394.129369 → 352.993772
      region:2.soil_fertility: 0.336409 → 0.335509
      T341380 AgricultureSystem.agriculture.harvest (tick 174)
      Inputs:
        region:2.food_stock = 429.55673 ← T339480
        region:2.population = 128 ← T341343
        region:2.rainfall = 0.490727 ← T339490
        region:2.soil_fertility = 0.337309 ← T339480
        region:2.temperature = 19.197691 ← T339490
        region:2.workers = 128 ← T341343
      Random:
        agriculture.crop_variance@region:2 = 0.63005
      Writes:
        region:2.food_stock: 429.55673 → 394.129369
        region:2.soil_fertility: 0.337309 → 0.336409
      T341390 ClimateSystem.climate.step (tick 174)
      Inputs:
        region:2.climate_volatility = 0.508114 ← T1003
        region:2.rainfall = 0.490727 ← T339490
        region:2.rainfall_base = 0.553388 ← T1003
        region:2.temperature = 19.197691 ← T339490
        region:2.temperature_base = 18.487763 ← T1003
      Random:
        climate.temperature_noise@region:2 = 0.988732
        climate.rain@region:2 = 0.497661
      Writes:
        region:2.rainfall: 0.490727 → 0.502979
        region:2.temperature: 19.197691 → 19.641039
      T343249 IronHealthAgentSystem.agents.census (tick 174)
      Inputs:
        agent:10.alive = true ← T3
        agent:10.region = region:2 ← T280522
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
    T344155 IronHealthAgentSystem.agent.metabolism (tick 175)
    Inputs:
      agent:0.hunger = 0.89 ← T342246
      agent:0.immunity = 0.056618 ← T342246
      agent:0.region = region:1 ← T343199
      region:1.food_stock = 0.0 ← T341379
      region:1.population = 16 ← T343248
    Writes:
      agent:0.hunger: 0.89 → 0.96
      agent:0.immunity: 0.056618 → 0.048735
      T341379 AgricultureSystem.agriculture.harvest (tick 174)
      Inputs:
        region:1.food_stock = 0.0 ← T339479
        region:1.population = 18 ← T341342
        region:1.rainfall = 0.383707 ← T339489
        region:1.soil_fertility = 0.373832 ← T339479
        region:1.temperature = 8.096762 ← T339489
        region:1.workers = 18 ← T341342
      Random:
        agriculture.crop_variance@region:1 = 0.541568
      Writes:
        region:1.food_stock: 0.0 → 0.0
        region:1.soil_fertility: 0.373832 → 0.372932
      T342246 IronHealthAgentSystem.agent.metabolism (tick 174)
      Inputs:
        agent:0.hunger = 0.82 ← T340342
        agent:0.immunity = 0.063838 ← T340342
        agent:0.region = region:0 ← T341296
        region:0.food_stock = 0.0 ← T339478
        region:0.population = 13 ← T341341
      Writes:
        agent:0.hunger: 0.82 → 0.89
        agent:0.immunity: 0.063838 → 0.056618
      T343199 IronHealthAgentSystem.agent.migrate (tick 174)
      Inputs:
        agent:0.hunger = 0.82 ← T340342
        agent:0.region = region:0 ← T341296
        agent:0.risk_tolerance = 0.758627 ← T1
      Random:
        agent.decision@agent:0 = 0.068752 threshold=0.379314
      Writes:
        agent:0.region: region:0 → region:1
      T343248 IronHealthAgentSystem.agents.census (tick 174)
      Inputs:
        agent:123.alive = true ← T29
        agent:123.region = region:1 ← T337455
        agent:181.alive = false ← T161680
        agent:181.region = region:1 ← T93
        agent:314.alive = true ← T241
        agent:314.region = region:1 ← T331560
        agent:343.alive = true ← T273
        agent:343.region = region:1 ← T341308
        … 42 more input(s)
      Writes:
        region:1.population: 18 → 16
        region:1.workers: 18 → 16
    T345103 IronHealthAgentSystem.agent.migrate (tick 175)
    Inputs:
      agent:0.hunger = 0.89 ← T342246
      agent:0.region = region:1 ← T343199
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
        agent:0.immune_memory: none → 0.0
        agent:0.immunity: none → 0.691249
        agent:0.infected: none → false
        agent:0.region: none → region:0
        agent:0.risk_tolerance: none → 0.758627
      T342246 IronHealthAgentSystem.agent.metabolism (tick 174)
      Inputs:
        agent:0.hunger = 0.82 ← T340342
        agent:0.immunity = 0.063838 ← T340342
        agent:0.region = region:0 ← T341296
        region:0.food_stock = 0.0 ← T339478
        region:0.population = 13 ← T341341
      Writes:
        agent:0.hunger: 0.82 → 0.89
        agent:0.immunity: 0.063838 → 0.056618
      T343199 IronHealthAgentSystem.agent.migrate (tick 174)
      Inputs:
        agent:0.hunger = 0.82 ← T340342
        agent:0.region = region:0 ← T341296
        agent:0.risk_tolerance = 0.758627 ← T1
      Random:
        agent.decision@agent:0 = 0.068752 threshold=0.379314
      Writes:
        agent:0.region: region:0 → region:1
    T345146 IronHealthAgentSystem.agents.census (tick 175)
    Inputs:
      agent:10.alive = true ← T3
      agent:10.region = region:2 ← T280522
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
        agent:10.immune_memory: none → 0.0
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
        agent:102.immune_memory: none → 0.0
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
        agent:112.immune_memory: none → 0.0
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
        agent:12.immune_memory: none → 0.0
        agent:12.immunity: none → 0.318003
        agent:12.infected: none → false
        agent:12.region: none → region:2
        agent:12.risk_tolerance: none → 0.021251
      … 166 more parent(s)
```

## Reproduction

```bash
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset iron_health --db runs/survival_seed7_iron_health.db --report <path>
```

Same seed + kernel v0.1.0 + ruleset 0.3.1a → bit-identical world, identical traces, identical report.