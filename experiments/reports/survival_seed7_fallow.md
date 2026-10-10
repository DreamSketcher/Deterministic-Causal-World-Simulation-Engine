# Causal survival experiment — seed 7

Kernel **v0.1 (frozen)**, ruleset **0.3.2d** — the laws
differ from the baseline by proposal only; the kernel, the purposes
and the addressable draw stream are unchanged.

> Experiment D (fallow): soil of abandoned regions recovers +0.0015/tick; farmed regions degrade exactly as in 0.3.0.

## Run

| parameter | value |
|---|---|
| seed | 7 |
| ruleset | 0.3.2d |
| regions | 10 |
| agents | 1000 |
| ticks | 10000 |
| wall time | 1154s |
| archive | `runs/survival_seed7_fallow.db` |
| survivors | 0 / 1000 |
| deaths | 1000 |
| last death | tick 794 |

## Lifespan distribution (all agents died: no censoring)

| pct | ticks |
|---|---|
| p0 | 28 |
| p10 | 158 |
| p25 | 230 |
| p50 | 396 |
| p75 | 418 |
| p90 | 565 |
| p100 | 794 |

mean lifespan: **340** ticks

## Statistical regularity: correlations with lifespan

| observable | pearson | spearman |
|---|---|---|
| initial_health | +0.000 | +0.006 |
| initial_immunity | -0.009 | -0.010 |
| risk_tolerance | +0.071 | +0.090 |
| migration_count | +0.213 | +0.257 |
| infection_count | +0.492 | +0.408 |
| avg_food_access | +0.679 | +0.754 |
| avg_social_density | +0.582 | +0.582 |

## Individual causality: death mechanisms (from traces)

| mechanism | deaths | share |
|---|---|---|
| disease+starvation | 958 | 95.8% |
| acute_infection | 35 | 3.5% |
| disease | 7 | 0.7% |

> **Interpretation caveat.** `migration_count`, `infection_count` and
> the sampled food/density aggregates are *time-at-risk* variables:
> agents that die early simply have fewer ticks in which to migrate
> or meet pathogens. A positive correlation of such a variable with
> lifespan is therefore expected even when the variable is harmful.
> The group tables below exist precisely to confront those numbers
> with per-death causal mechanisms.

## Statistical regularity vs individual causality

### Migration — same observable, different mechanisms?

| group | n | mean lifespan | acute_infection | disease | disease+starvation |
|---|---|---|---|---|---|
| stayers (0 migrations) | 61 | 216 | 4 | 5 | 52 |
| migrants (>=1 migration) | 939 | 348 | 31 | 2 | 906 |

### Risk tolerance quartiles

| group | n | mean lifespan | acute_infection | disease | disease+starvation |
|---|---|---|---|---|---|
| risk Q1 (lowest) | 250 | 314 | 13 | 2 | 235 |
| risk Q2 | 250 | 360 | 12 | 1 | 237 |
| risk Q3 | 250 | 344 | 5 | 2 | 243 |
| risk Q4 (highest) | 250 | 343 | 5 | 2 | 243 |

## Example mechanical explanations

### agent:102 — disease (died tick 83, T167826)

```
T167826 AgentSystem.agent.death (tick 83)
Inputs:
  agent:102.alive = true ← T6
  agent:102.health = 1.023145 ← T165894
  agent:102.hunger = 0.0 ← T166831
  agent:102.infected = true ← T162000
Writes:
  agent:102.alive: true → false
  agent:102.health: 1.023145 → 0.0
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
  T162000 ImmuneDiseaseSystem.disease.infect (tick 79)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 16.812727 ← T158161
    agent:102.hunger = 0.0 ← T159098
    agent:102.immune_memory = 0.7 ← T127103
    agent:102.immunity = 0.427132 ← T159098
    agent:102.infected = false ← T154274
    agent:102.region = region:2 ← T6
    region:2.disease_load = 0.203395 ← T160063
  Random:
    disease.infection@agent:102 = 0.00308 threshold=0.014235
    disease.infection@agent:102 = 0.829238
  Writes:
    agent:102.health: 16.812727 → 8.523145
    agent:102.immune_memory: 0.7 → 1.0
    agent:102.infected: false → true
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
    T127103 ImmuneDiseaseSystem.disease.infect (tick 61)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 55.187459 ← T123252
      agent:102.hunger = 0.0 ← T124166
      agent:102.immune_memory = 0.35 ← T78562
      agent:102.immunity = 0.429694 ← T124166
      agent:102.infected = false ← T115318
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.259446 ← T125146
    Random:
      disease.infection@agent:102 = 0.019219 threshold=0.031397
      disease.infection@agent:102 = 0.396801
    Writes:
      agent:102.health: 55.187459 → 47.312727
      agent:102.immune_memory: 0.35 → 0.7
      agent:102.infected: false → true
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
      T78562 ImmuneDiseaseSystem.disease.infect (tick 37)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 100.0 ← T74474
        agent:102.hunger = 0.0 ← T75408
        agent:102.immune_memory = 0.0 ← T6
        agent:102.immunity = 0.43349 ← T75408
        agent:102.infected = false ← T6
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.309404 ← T76464
      Random:
        disease.infection@agent:102 = 0.011169 threshold=0.053053
        disease.infection@agent:102 = 0.131254
      Writes:
        agent:102.health: 100.0 → 92.687459
        agent:102.immune_memory: 0.0 → 0.35
        agent:102.infected: false → true
      T115318 ImmuneDiseaseSystem.disease.recover (tick 55)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T112267
        agent:102.immune_memory = 0.35 ← T78562
        agent:102.immunity = 0.430601 ← T112267
        agent:102.infected = true ← T78562
      Random:
        disease.recovery@agent:102 = 0.118911 threshold=0.19765
      Writes:
        agent:102.infected: true → false
      T123252 AgentSystem.agent.health (tick 60)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 53.687459 ← T121289
        agent:102.hunger = 0.0 ← T122206
        agent:102.infected = false ← T115318
      Writes:
        agent:102.health: 53.687459 → 55.187459
      … 2 more parent(s)
    T154274 ImmuneDiseaseSystem.disease.recover (tick 75)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.hunger = 0.0 ← T151356
      agent:102.immune_memory = 0.7 ← T127103
      agent:102.immunity = 0.427682 ← T151356
      agent:102.infected = true ← T127103
    Random:
      disease.recovery@agent:102 = 0.244162 threshold=0.26692
    Writes:
      agent:102.infected: true → false
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
      T127103 ImmuneDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T123252
        agent:102.hunger = 0.0 ← T124166
        agent:102.immune_memory = 0.35 ← T78562
        agent:102.immunity = 0.429694 ← T124166
        agent:102.infected = false ← T115318
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.259446 ← T125146
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.031397
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T151356 AgentSystem.agent.metabolism (tick 74)
      Inputs:
        agent:102.hunger = 0.0 ← T149410
        agent:102.immunity = 0.427821 ← T149410
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1458.048163 ← T150365
        region:2.population = 112 ← T150345
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.427821 → 0.427682
    T158161 AgentSystem.agent.health (tick 78)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 15.312727 ← T156224
      agent:102.hunger = 0.0 ← T157161
      agent:102.infected = false ← T154274
    Writes:
      agent:102.health: 15.312727 → 16.812727
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
      T154274 ImmuneDiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T151356
        agent:102.immune_memory = 0.7 ← T127103
        agent:102.immunity = 0.427682 ← T151356
        agent:102.infected = true ← T127103
      Random:
        disease.recovery@agent:102 = 0.244162 threshold=0.26692
      Writes:
        agent:102.infected: true → false
      T156224 AgentSystem.agent.health (tick 77)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 13.812727 ← T154291
        agent:102.hunger = 0.0 ← T155227
        agent:102.infected = false ← T154274
      Writes:
        agent:102.health: 13.812727 → 15.312727
      T157161 AgentSystem.agent.metabolism (tick 77)
      Inputs:
        agent:102.hunger = 0.0 ← T155227
        agent:102.immunity = 0.427406 ← T155227
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1378.472853 ← T156183
        region:2.population = 112 ← T156163
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.427406 → 0.427269
    … 2 more parent(s)
  T165894 AgentSystem.agent.health (tick 82)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 3.523145 ← T163955
    agent:102.hunger = 0.0 ← T164892
    agent:102.infected = true ← T162000
  Writes:
    agent:102.health: 3.523145 → 1.023145
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
    T162000 ImmuneDiseaseSystem.disease.infect (tick 79)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 16.812727 ← T158161
      agent:102.hunger = 0.0 ← T159098
      agent:102.immune_memory = 0.7 ← T127103
      agent:102.immunity = 0.427132 ← T159098
      agent:102.infected = false ← T154274
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.203395 ← T160063
    Random:
      disease.infection@agent:102 = 0.00308 threshold=0.014235
      disease.infection@agent:102 = 0.829238
    Writes:
      agent:102.health: 16.812727 → 8.523145
      agent:102.immune_memory: 0.7 → 1.0
      agent:102.infected: false → true
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
      T127103 ImmuneDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T123252
        agent:102.hunger = 0.0 ← T124166
        agent:102.immune_memory = 0.35 ← T78562
        agent:102.immunity = 0.429694 ← T124166
        agent:102.infected = false ← T115318
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.259446 ← T125146
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.031397
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T154274 ImmuneDiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T151356
        agent:102.immune_memory = 0.7 ← T127103
        agent:102.immunity = 0.427682 ← T151356
        agent:102.infected = true ← T127103
      Random:
        disease.recovery@agent:102 = 0.244162 threshold=0.26692
      Writes:
        agent:102.infected: true → false
      T158161 AgentSystem.agent.health (tick 78)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 15.312727 ← T156224
        agent:102.hunger = 0.0 ← T157161
        agent:102.infected = false ← T154274
      Writes:
        agent:102.health: 15.312727 → 16.812727
      … 2 more parent(s)
    T163955 AgentSystem.agent.health (tick 81)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 6.023145 ← T162024
      agent:102.hunger = 0.0 ← T162961
      agent:102.infected = true ← T162000
    Writes:
      agent:102.health: 6.023145 → 3.523145
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
      T162000 ImmuneDiseaseSystem.disease.infect (tick 79)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 16.812727 ← T158161
        agent:102.hunger = 0.0 ← T159098
        agent:102.immune_memory = 0.7 ← T127103
        agent:102.immunity = 0.427132 ← T159098
        agent:102.infected = false ← T154274
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.203395 ← T160063
      Random:
        disease.infection@agent:102 = 0.00308 threshold=0.014235
        disease.infection@agent:102 = 0.829238
      Writes:
        agent:102.health: 16.812727 → 8.523145
        agent:102.immune_memory: 0.7 → 1.0
        agent:102.infected: false → true
      T162024 AgentSystem.agent.health (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 8.523145 ← T162000
        agent:102.hunger = 0.0 ← T161027
        agent:102.infected = true ← T162000
      Writes:
        agent:102.health: 8.523145 → 6.023145
      T162961 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161027
        agent:102.immunity = 0.426997 ← T161027
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1271.336738 ← T161982
        region:2.population = 112 ← T161962
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
    T164892 AgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T162961
      agent:102.immunity = 0.426862 ← T162961
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1276.539481 ← T163916
      region:2.population = 112 ← T163896
    Writes:
      agent:102.hunger: 0.0 → 0.0
      agent:102.immunity: 0.426862 → 0.426727
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
      T162961 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161027
        agent:102.immunity = 0.426997 ← T161027
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1271.336738 ← T161982
        region:2.population = 112 ← T161962
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
      T163896 AgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 228 more input(s)
      Writes:
        region:2.population: 112 → 112
        region:2.workers: 112 → 112
      T163916 FallowAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1271.336738 ← T161982
        region:2.population = 112 ← T161962
        region:2.rainfall = 0.577858 ← T161972
        region:2.soil_fertility = 0.421909 ← T161982
        region:2.temperature = 18.934401 ← T161972
        region:2.workers = 112 ← T161962
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1271.336738 → 1276.539481
        region:2.soil_fertility: 0.421909 → 0.421009
  T166831 AgentSystem.agent.metabolism (tick 82)
  Inputs:
    agent:102.hunger = 0.0 ← T164892
    agent:102.immunity = 0.426727 ← T164892
    agent:102.region = region:2 ← T6
    region:2.food_stock = 1232.912473 ← T165847
    region:2.population = 112 ← T165827
  Writes:
    agent:102.hunger: 0.0 → 0.0
    agent:102.immunity: 0.426727 → 0.426594
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
    T164892 AgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T162961
      agent:102.immunity = 0.426862 ← T162961
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1276.539481 ← T163916
      region:2.population = 112 ← T163896
    Writes:
      agent:102.hunger: 0.0 → 0.0
      agent:102.immunity: 0.426862 → 0.426727
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
      T162961 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161027
        agent:102.immunity = 0.426997 ← T161027
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1271.336738 ← T161982
        region:2.population = 112 ← T161962
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
      T163896 AgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 228 more input(s)
      Writes:
        region:2.population: 112 → 112
        region:2.workers: 112 → 112
      T163916 FallowAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1271.336738 ← T161982
        region:2.population = 112 ← T161962
        region:2.rainfall = 0.577858 ← T161972
        region:2.soil_fertility = 0.421909 ← T161982
        region:2.temperature = 18.934401 ← T161972
        region:2.workers = 112 ← T161962
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1271.336738 → 1276.539481
        region:2.soil_fertility: 0.421909 → 0.421009
    T165827 AgentSystem.agents.census (tick 81)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.region = region:2 ← T6
      agent:112.alive = true ← T17
      agent:112.region = region:2 ← T17
      agent:12.alive = true ← T25
      agent:12.region = region:2 ← T25
      agent:122.alive = true ← T28
      agent:122.region = region:2 ← T28
      … 228 more input(s)
    Writes:
      region:2.population: 112 → 112
      region:2.workers: 112 → 112
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
      T28 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:122 = 0.666412
        genesis.attribute@agent:122 = 0.252728
        genesis.attribute@agent:122 = 0.265969
        genesis.attribute@agent:122 = 0.477795
      Writes:
        agent:122.alive: none → true
        agent:122.health: none → 84.992371
        agent:122.hunger: none → 0.175818
        agent:122.immune_memory: none → 0.0
        agent:122.immunity: none → 0.396283
        agent:122.infected: none → false
        agent:122.region: none → region:2
        agent:122.risk_tolerance: none → 0.477795
      … 132 more parent(s)
    T165847 FallowAgricultureSystem.agriculture.harvest (tick 81)
    Inputs:
      region:2.food_stock = 1276.539481 ← T163916
      region:2.population = 112 ← T163896
      region:2.rainfall = 0.568902 ← T163906
      region:2.soil_fertility = 0.421009 ← T163916
      region:2.temperature = 19.003536 ← T163906
      region:2.workers = 112 ← T163896
    Random:
      agriculture.crop_variance@region:2 = 0.024179
    Writes:
      region:2.food_stock: 1276.539481 → 1232.912473
      region:2.soil_fertility: 0.421009 → 0.420109
      T163896 AgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 228 more input(s)
      Writes:
        region:2.population: 112 → 112
        region:2.workers: 112 → 112
      T163906 ClimateSystem.climate.step (tick 80)
      Inputs:
        region:2.climate_volatility = 0.508114 ← T1003
        region:2.rainfall = 0.577858 ← T161972
        region:2.rainfall_base = 0.553388 ← T1003
        region:2.temperature = 18.934401 ← T161972
        region:2.temperature_base = 18.487763 ← T1003
      Random:
        climate.temperature_noise@region:2 = 0.642326
        climate.rain@region:2 = 0.466151
      Writes:
        region:2.rainfall: 0.577858 → 0.568902
        region:2.temperature: 18.934401 → 19.003536
      T163916 FallowAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1271.336738 ← T161982
        region:2.population = 112 ← T161962
        region:2.rainfall = 0.577858 ← T161972
        region:2.soil_fertility = 0.421909 ← T161982
        region:2.temperature = 18.934401 ← T161972
        region:2.workers = 112 ← T161962
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1271.336738 → 1276.539481
        region:2.soil_fertility: 0.421909 → 0.421009
```

### agent:122 — acute_infection (died tick 255, T467985)

```
T467985 ImmuneDiseaseSystem.disease.infect (tick 255)
Inputs:
  agent:122.alive = true ← T28
  agent:122.health = 6.0 ← T465335
  agent:122.hunger = 0.88 ← T465959
  agent:122.immune_memory = 0.7 ← T119275
  agent:122.immunity = 0.0 ← T465959
  agent:122.infected = false ← T127128
  agent:122.region = region:6 ← T461075
  region:6.disease_load = 0.181343 ← T466646
Random:
  disease.infection@agent:122 = 0.034367 threshold=0.060481
  disease.infection@agent:122 = 0.974016
Writes:
  agent:122.alive: true → false
  agent:122.health: 6.0 → 0.0
  agent:122.immune_memory: 0.7 → 1.0
  agent:122.infected: false → true
  T28 GenesisSystem.genesis.agent (tick 0)
  Random:
    genesis.attribute@agent:122 = 0.666412
    genesis.attribute@agent:122 = 0.252728
    genesis.attribute@agent:122 = 0.265969
    genesis.attribute@agent:122 = 0.477795
  Writes:
    agent:122.alive: none → true
    agent:122.health: none → 84.992371
    agent:122.hunger: none → 0.175818
    agent:122.immune_memory: none → 0.0
    agent:122.immunity: none → 0.396283
    agent:122.infected: none → false
    agent:122.region: none → region:2
    agent:122.risk_tolerance: none → 0.477795
  T119275 ImmuneDiseaseSystem.disease.infect (tick 57)
  Inputs:
    agent:122.alive = true ← T28
    agent:122.health = 100.0 ← T115387
    agent:122.hunger = 0.0 ← T116313
    agent:122.immune_memory = 0.35 ← T6007
    agent:122.immunity = 0.393945 ← T116313
    agent:122.infected = false ← T18284
    agent:122.region = region:2 ← T28
    region:2.disease_load = 0.274688 ← T117295
  Random:
    disease.infection@agent:122 = 0.000829 threshold=0.03469
    disease.infection@agent:122 = 0.758234
  Writes:
    agent:122.health: 100.0 → 89.26995
    agent:122.immune_memory: 0.35 → 0.7
    agent:122.infected: false → true
    T28 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:122 = 0.666412
      genesis.attribute@agent:122 = 0.252728
      genesis.attribute@agent:122 = 0.265969
      genesis.attribute@agent:122 = 0.477795
    Writes:
      agent:122.alive: none → true
      agent:122.health: none → 84.992371
      agent:122.hunger: none → 0.175818
      agent:122.immune_memory: none → 0.0
      agent:122.immunity: none → 0.396283
      agent:122.infected: none → false
      agent:122.region: none → region:2
      agent:122.risk_tolerance: none → 0.477795
    T6007 ImmuneDiseaseSystem.disease.infect (tick 2)
    Inputs:
      agent:122.alive = true ← T28
      agent:122.health = 87.992371 ← T2581
      agent:122.hunger = 0.115818 ← T3190
      agent:122.immune_memory = 0.0 ← T28
      agent:122.immunity = 0.393711 ← T3190
      agent:122.infected = false ← T28
      agent:122.region = region:2 ← T28
      region:2.disease_load = 0.110169 ← T4195
    Random:
      disease.infection@agent:122 = 0.021716 threshold=0.025383
      disease.infection@agent:122 = 0.945311
    Writes:
      agent:122.health: 87.992371 → 72.539262
      agent:122.immune_memory: 0.0 → 0.35
      agent:122.infected: false → true
      T28 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:122 = 0.666412
        genesis.attribute@agent:122 = 0.252728
        genesis.attribute@agent:122 = 0.265969
        genesis.attribute@agent:122 = 0.477795
      Writes:
        agent:122.alive: none → true
        agent:122.health: none → 84.992371
        agent:122.hunger: none → 0.175818
        agent:122.immune_memory: none → 0.0
        agent:122.immunity: none → 0.396283
        agent:122.infected: none → false
        agent:122.region: none → region:2
        agent:122.risk_tolerance: none → 0.477795
      T2581 AgentSystem.agent.health (tick 1)
      Inputs:
        agent:122.alive = true ← T28
        agent:122.health = 86.492371 ← T1022
        agent:122.hunger = 0.145818 ← T1526
        agent:122.infected = false ← T28
      Writes:
        agent:122.health: 86.492371 → 87.992371
      T3190 AgentSystem.agent.metabolism (tick 1)
      Inputs:
        agent:122.hunger = 0.145818 ← T1526
        agent:122.immunity = 0.394843 ← T1526
        agent:122.region = region:2 ← T28
        region:2.food_stock = 1756.948086 ← T2521
        region:2.population = 100 ← T2501
      Writes:
        agent:122.hunger: 0.145818 → 0.115818
        agent:122.immunity: 0.394843 → 0.393711
      T4195 ImmuneDiseaseSystem.disease.environment (tick 1)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.infected = false ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.infected = false ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.infected = false ← T25
        … 294 more input(s)
      Random:
        disease.load_noise@region:2 = 0.122118
      Writes:
        region:2.disease_load: 0.101238 → 0.110169
    T18284 ImmuneDiseaseSystem.disease.recover (tick 8)
    Inputs:
      agent:122.alive = true ← T28
      agent:122.hunger = 0.0 ← T15143
      agent:122.immune_memory = 0.35 ← T6007
      agent:122.immunity = 0.392259 ← T15143
      agent:122.infected = true ← T6007
    Random:
      disease.recovery@agent:122 = 0.023558 threshold=0.188065
    Writes:
      agent:122.infected: true → false
      T28 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:122 = 0.666412
        genesis.attribute@agent:122 = 0.252728
        genesis.attribute@agent:122 = 0.265969
        genesis.attribute@agent:122 = 0.477795
      Writes:
        agent:122.alive: none → true
        agent:122.health: none → 84.992371
        agent:122.hunger: none → 0.175818
        agent:122.immune_memory: none → 0.0
        agent:122.immunity: none → 0.396283
        agent:122.infected: none → false
        agent:122.region: none → region:2
        agent:122.risk_tolerance: none → 0.477795
      T6007 ImmuneDiseaseSystem.disease.infect (tick 2)
      Inputs:
        agent:122.alive = true ← T28
        agent:122.health = 87.992371 ← T2581
        agent:122.hunger = 0.115818 ← T3190
        agent:122.immune_memory = 0.0 ← T28
        agent:122.immunity = 0.393711 ← T3190
        agent:122.infected = false ← T28
        agent:122.region = region:2 ← T28
        region:2.disease_load = 0.110169 ← T4195
      Random:
        disease.infection@agent:122 = 0.021716 threshold=0.025383
        disease.infection@agent:122 = 0.945311
      Writes:
        agent:122.health: 87.992371 → 72.539262
        agent:122.immune_memory: 0.0 → 0.35
        agent:122.infected: false → true
      T15143 AgentSystem.agent.metabolism (tick 7)
      Inputs:
        agent:122.hunger = 0.0 ← T13044
        agent:122.immunity = 0.39222 ← T13044
        agent:122.region = region:2 ← T28
        region:2.food_stock = 1750.521154 ← T14039
        region:2.population = 100 ← T14019
      Writes:
        agent:122.hunger: 0.0 → 0.0
        agent:122.immunity: 0.39222 → 0.392259
    T115387 AgentSystem.agent.health (tick 56)
    Inputs:
      agent:122.alive = true ← T28
      agent:122.health = 100.0 ← T113383
      agent:122.hunger = 0.0 ← T114310
      agent:122.infected = false ← T18284
    Writes:
      agent:122.health: 100.0 → 100.0
      T28 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:122 = 0.666412
        genesis.attribute@agent:122 = 0.252728
        genesis.attribute@agent:122 = 0.265969
        genesis.attribute@agent:122 = 0.477795
      Writes:
        agent:122.alive: none → true
        agent:122.health: none → 84.992371
        agent:122.hunger: none → 0.175818
        agent:122.immune_memory: none → 0.0
        agent:122.immunity: none → 0.396283
        agent:122.infected: none → false
        agent:122.region: none → region:2
        agent:122.risk_tolerance: none → 0.477795
      T18284 ImmuneDiseaseSystem.disease.recover (tick 8)
      Inputs:
        agent:122.alive = true ← T28
        agent:122.hunger = 0.0 ← T15143
        agent:122.immune_memory = 0.35 ← T6007
        agent:122.immunity = 0.392259 ← T15143
        agent:122.infected = true ← T6007
      Random:
        disease.recovery@agent:122 = 0.023558 threshold=0.188065
      Writes:
        agent:122.infected: true → false
      T113383 AgentSystem.agent.health (tick 55)
      Inputs:
        agent:122.alive = true ← T28
        agent:122.health = 100.0 ← T111357
        agent:122.hunger = 0.0 ← T112289
        agent:122.infected = false ← T18284
      Writes:
        agent:122.health: 100.0 → 100.0
      T114310 AgentSystem.agent.metabolism (tick 55)
      Inputs:
        agent:122.hunger = 0.0 ← T112289
        agent:122.immunity = 0.393884 ← T112289
        agent:122.region = region:2 ← T28
        region:2.food_stock = 1458.89925 ← T113270
        region:2.population = 113 ← T113250
      Writes:
        agent:122.hunger: 0.0 → 0.0
        agent:122.immunity: 0.393884 → 0.393914
    … 2 more parent(s)
  T127128 ImmuneDiseaseSystem.disease.recover (tick 61)
  Inputs:
    agent:122.alive = true ← T28
    agent:122.hunger = 0.0 ← T124188
    agent:122.immune_memory = 0.7 ← T119275
    agent:122.immunity = 0.394065 ← T124188
    agent:122.infected = true ← T119275
  Random:
    disease.recovery@agent:122 = 0.079443 threshold=0.258516
  Writes:
    agent:122.infected: true → false
    T28 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:122 = 0.666412
      genesis.attribute@agent:122 = 0.252728
      genesis.attribute@agent:122 = 0.265969
      genesis.attribute@agent:122 = 0.477795
    Writes:
      agent:122.alive: none → true
      agent:122.health: none → 84.992371
      agent:122.hunger: none → 0.175818
      agent:122.immune_memory: none → 0.0
      agent:122.immunity: none → 0.396283
      agent:122.infected: none → false
      agent:122.region: none → region:2
      agent:122.risk_tolerance: none → 0.477795
    T119275 ImmuneDiseaseSystem.disease.infect (tick 57)
    Inputs:
      agent:122.alive = true ← T28
      agent:122.health = 100.0 ← T115387
      agent:122.hunger = 0.0 ← T116313
      agent:122.immune_memory = 0.35 ← T6007
      agent:122.immunity = 0.393945 ← T116313
      agent:122.infected = false ← T18284
      agent:122.region = region:2 ← T28
      region:2.disease_load = 0.274688 ← T117295
    Random:
      disease.infection@agent:122 = 0.000829 threshold=0.03469
      disease.infection@agent:122 = 0.758234
    Writes:
      agent:122.health: 100.0 → 89.26995
      agent:122.immune_memory: 0.35 → 0.7
      agent:122.infected: false → true
      T28 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:122 = 0.666412
        genesis.attribute@agent:122 = 0.252728
        genesis.attribute@agent:122 = 0.265969
        genesis.attribute@agent:122 = 0.477795
      Writes:
        agent:122.alive: none → true
        agent:122.health: none → 84.992371
        agent:122.hunger: none → 0.175818
        agent:122.immune_memory: none → 0.0
        agent:122.immunity: none → 0.396283
        agent:122.infected: none → false
        agent:122.region: none → region:2
        agent:122.risk_tolerance: none → 0.477795
      T6007 ImmuneDiseaseSystem.disease.infect (tick 2)
      Inputs:
        agent:122.alive = true ← T28
        agent:122.health = 87.992371 ← T2581
        agent:122.hunger = 0.115818 ← T3190
        agent:122.immune_memory = 0.0 ← T28
        agent:122.immunity = 0.393711 ← T3190
        agent:122.infected = false ← T28
        agent:122.region = region:2 ← T28
        region:2.disease_load = 0.110169 ← T4195
      Random:
        disease.infection@agent:122 = 0.021716 threshold=0.025383
        disease.infection@agent:122 = 0.945311
      Writes:
        agent:122.health: 87.992371 → 72.539262
        agent:122.immune_memory: 0.0 → 0.35
        agent:122.infected: false → true
      T18284 ImmuneDiseaseSystem.disease.recover (tick 8)
      Inputs:
        agent:122.alive = true ← T28
        agent:122.hunger = 0.0 ← T15143
        agent:122.immune_memory = 0.35 ← T6007
        agent:122.immunity = 0.392259 ← T15143
        agent:122.infected = true ← T6007
      Random:
        disease.recovery@agent:122 = 0.023558 threshold=0.188065
      Writes:
        agent:122.infected: true → false
      T115387 AgentSystem.agent.health (tick 56)
      Inputs:
        agent:122.alive = true ← T28
        agent:122.health = 100.0 ← T113383
        agent:122.hunger = 0.0 ← T114310
        agent:122.infected = false ← T18284
      Writes:
        agent:122.health: 100.0 → 100.0
      … 2 more parent(s)
    T124188 AgentSystem.agent.metabolism (tick 60)
    Inputs:
      agent:122.hunger = 0.0 ← T122228
      agent:122.immunity = 0.394035 ← T122228
      agent:122.region = region:2 ← T28
      region:2.food_stock = 1454.129591 ← T123182
      region:2.population = 112 ← T123162
    Writes:
      agent:122.hunger: 0.0 → 0.0
      agent:122.immunity: 0.394035 → 0.394065
      T28 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:122 = 0.666412
        genesis.attribute@agent:122 = 0.252728
        genesis.attribute@agent:122 = 0.265969
        genesis.attribute@agent:122 = 0.477795
      Writes:
        agent:122.alive: none → true
        agent:122.health: none → 84.992371
        agent:122.hunger: none → 0.175818
        agent:122.immune_memory: none → 0.0
        agent:122.immunity: none → 0.396283
        agent:122.infected: none → false
        agent:122.region: none → region:2
        agent:122.risk_tolerance: none → 0.477795
      T122228 AgentSystem.agent.metabolism (tick 59)
      Inputs:
        agent:122.hunger = 0.0 ← T120266
        agent:122.immunity = 0.394005 ← T120266
        agent:122.region = region:2 ← T28
        region:2.food_stock = 1478.968242 ← T121223
        region:2.population = 112 ← T121203
      Writes:
        agent:122.hunger: 0.0 → 0.0
        agent:122.immunity: 0.394005 → 0.394035
      T123162 AgentSystem.agents.census (tick 59)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 226 more input(s)
      Writes:
        region:2.population: 112 → 112
        region:2.workers: 112 → 112
      T123182 FallowAgricultureSystem.agriculture.harvest (tick 59)
      Inputs:
        region:2.food_stock = 1478.968242 ← T121223
        region:2.population = 112 ← T121203
        region:2.rainfall = 0.553011 ← T121213
        region:2.soil_fertility = 0.440809 ← T121223
        region:2.temperature = 17.85844 ← T121213
        region:2.workers = 112 ← T121203
      Random:
        agriculture.crop_variance@region:2 = 0.151012
      Writes:
        region:2.food_stock: 1478.968242 → 1454.129591
        region:2.soil_fertility: 0.440809 → 0.439909
  T461075 AgentSystem.agent.migrate (tick 250)
  Inputs:
    agent:122.hunger = 1.0 ← T459003
    agent:122.region = region:5 ← T455360
    agent:122.risk_tolerance = 0.477795 ← T28
  Random:
    agent.decision@agent:122 = 0.036826 threshold=0.238898
  Writes:
    agent:122.region: region:5 → region:6
    T28 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:122 = 0.666412
      genesis.attribute@agent:122 = 0.252728
      genesis.attribute@agent:122 = 0.265969
      genesis.attribute@agent:122 = 0.477795
    Writes:
      agent:122.alive: none → true
      agent:122.health: none → 84.992371
      agent:122.hunger: none → 0.175818
      agent:122.immune_memory: none → 0.0
      agent:122.immunity: none → 0.396283
      agent:122.infected: none → false
      agent:122.region: none → region:2
      agent:122.risk_tolerance: none → 0.477795
    T455360 AgentSystem.agent.migrate (tick 246)
    Inputs:
      agent:122.hunger = 1.0 ← T453233
      agent:122.region = region:4 ← T447991
      agent:122.risk_tolerance = 0.477795 ← T28
    Random:
      agent.decision@agent:122 = 0.155308 threshold=0.238898
    Writes:
      agent:122.region: region:4 → region:5
      T28 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:122 = 0.666412
        genesis.attribute@agent:122 = 0.252728
        genesis.attribute@agent:122 = 0.265969
        genesis.attribute@agent:122 = 0.477795
      Writes:
        agent:122.alive: none → true
        agent:122.health: none → 84.992371
        agent:122.hunger: none → 0.175818
        agent:122.immune_memory: none → 0.0
        agent:122.immunity: none → 0.396283
        agent:122.infected: none → false
        agent:122.region: none → region:2
        agent:122.risk_tolerance: none → 0.477795
      T447991 AgentSystem.agent.migrate (tick 241)
      Inputs:
        agent:122.hunger = 1.0 ← T445787
        agent:122.region = region:3 ← T444973
        agent:122.risk_tolerance = 0.477795 ← T28
      Random:
        agent.decision@agent:122 = 0.045616 threshold=0.238898
      Writes:
        agent:122.region: region:3 → region:4
      T453233 AgentSystem.agent.metabolism (tick 245)
      Inputs:
        agent:122.hunger = 1.0 ← T451772
        agent:122.immunity = 0.013705 ← T451772
        agent:122.region = region:4 ← T447991
        region:4.food_stock = 0.0 ← T452520
        region:4.population = 17 ← T452500
      Writes:
        agent:122.hunger: 1.0 → 1.0
        agent:122.immunity: 0.013705 → 0.005636
    T459003 AgentSystem.agent.metabolism (tick 249)
    Inputs:
      agent:122.hunger = 1.0 ← T457581
      agent:122.immunity = 0.0 ← T457581
      agent:122.region = region:5 ← T455360
      region:5.food_stock = 0.0 ← T458301
      region:5.population = 12 ← T458281
    Writes:
      agent:122.hunger: 1.0 → 1.0
      agent:122.immunity: 0.0 → 0.0
      T455360 AgentSystem.agent.migrate (tick 246)
      Inputs:
        agent:122.hunger = 1.0 ← T453233
        agent:122.region = region:4 ← T447991
        agent:122.risk_tolerance = 0.477795 ← T28
      Random:
        agent.decision@agent:122 = 0.155308 threshold=0.238898
      Writes:
        agent:122.region: region:4 → region:5
      T457581 AgentSystem.agent.metabolism (tick 248)
      Inputs:
        agent:122.hunger = 1.0 ← T456137
        agent:122.immunity = 0.0 ← T456137
        agent:122.region = region:5 ← T455360
        region:5.food_stock = 0.0 ← T456879
        region:5.population = 14 ← T456859
      Writes:
        agent:122.hunger: 1.0 → 1.0
        agent:122.immunity: 0.0 → 0.0
      T458281 AgentSystem.agents.census (tick 248)
      Inputs:
        agent:10.alive = false ← T414443
        agent:10.region = region:5 ← T405255
        agent:105.alive = false ← T123243
        agent:105.region = region:5 ← T107161
        agent:122.alive = true ← T28
        agent:122.region = region:5 ← T455360
        agent:130.alive = false ← T435862
        agent:130.region = region:5 ← T423392
        … 106 more input(s)
      Writes:
        region:5.population: 14 → 12
        region:5.workers: 14 → 12
      T458301 FallowAgricultureSystem.agriculture.harvest (tick 248)
      Inputs:
        region:5.food_stock = 0.0 ← T456879
        region:5.population = 14 ← T456859
        region:5.rainfall = 0.429988 ← T456869
        region:5.soil_fertility = 0.385268 ← T456879
        region:5.temperature = 20.243985 ← T456869
        region:5.workers = 14 ← T456859
      Random:
        agriculture.crop_variance@region:5 = 0.322655
      Writes:
        region:5.food_stock: 0.0 → 0.0
        region:5.soil_fertility: 0.385268 → 0.384368
  … 3 more parent(s)
```

## Reproduction

```bash
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset fallow --db runs/survival_seed7_fallow.db --report <path>
```

Same seed + kernel v0.1.0 + ruleset 0.3.2d → bit-identical world, identical traces, identical report.