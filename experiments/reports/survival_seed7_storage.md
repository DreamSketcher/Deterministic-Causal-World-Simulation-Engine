# Causal survival experiment — seed 7

Kernel **v0.1 (frozen)**, ruleset **0.3.2e** — the laws
differ from the baseline by proposal only; the kernel, the purposes
and the addressable draw stream are unchanged.

> Experiment E (storage): spoilage depends on stock size — tiny stocks barely rot, surpluses above 10 rations/agent rot at 4 %.

## Run

| parameter | value |
|---|---|
| seed | 7 |
| ruleset | 0.3.2e |
| regions | 10 |
| agents | 1000 |
| ticks | 10000 |
| wall time | 1145s |
| archive | `runs/survival_seed7_storage.db` |
| survivors | 0 / 1000 |
| deaths | 1000 |
| last death | tick 594 |

## Lifespan distribution (all agents died: no censoring)

| pct | ticks |
|---|---|
| p0 | 28 |
| p10 | 174 |
| p25 | 274 |
| p50 | 409 |
| p75 | 432 |
| p90 | 583 |
| p100 | 594 |

mean lifespan: **353** ticks

## Statistical regularity: correlations with lifespan

| observable | pearson | spearman |
|---|---|---|
| initial_health | -0.008 | -0.018 |
| initial_immunity | +0.008 | +0.007 |
| risk_tolerance | +0.086 | +0.081 |
| migration_count | +0.199 | +0.237 |
| infection_count | +0.432 | +0.335 |
| avg_food_access | +0.675 | +0.718 |
| avg_social_density | +0.729 | +0.705 |

## Individual causality: death mechanisms (from traces)

| mechanism | deaths | share |
|---|---|---|
| disease+starvation | 956 | 95.6% |
| acute_infection | 37 | 3.7% |
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
| stayers (0 migrations) | 58 | 215 | 1 | 5 | 52 |
| migrants (>=1 migration) | 942 | 361 | 36 | 2 | 904 |

### Risk tolerance quartiles

| group | n | mean lifespan | acute_infection | disease | disease+starvation |
|---|---|---|---|---|---|
| risk Q1 (lowest) | 250 | 330 | 13 | 2 | 235 |
| risk Q2 | 250 | 359 | 10 | 1 | 239 |
| risk Q3 | 250 | 361 | 9 | 2 | 239 |
| risk Q4 (highest) | 250 | 360 | 5 | 2 | 243 |

## Example mechanical explanations

### agent:102 — disease (died tick 83, T167813)

```
T167813 AgentSystem.agent.death (tick 83)
Inputs:
  agent:102.alive = true ← T6
  agent:102.health = 1.023145 ← T165888
  agent:102.hunger = 0.0 ← T166822
  agent:102.infected = true ← T161994
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
  T161994 ImmuneDiseaseSystem.disease.infect (tick 79)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 16.812727 ← T158179
    agent:102.hunger = 0.0 ← T159112
    agent:102.immune_memory = 0.7 ← T127155
    agent:102.immunity = 0.427132 ← T159112
    agent:102.infected = false ← T154297
    agent:102.region = region:2 ← T6
    region:2.disease_load = 0.20482 ← T160063
  Random:
    disease.infection@agent:102 = 0.00308 threshold=0.014334
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
    T127155 ImmuneDiseaseSystem.disease.infect (tick 61)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 55.187459 ← T123296
      agent:102.hunger = 0.0 ← T124214
      agent:102.immune_memory = 0.35 ← T78563
      agent:102.immunity = 0.429694 ← T124214
      agent:102.infected = false ← T115334
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.279929 ← T125189
    Random:
      disease.infection@agent:102 = 0.019219 threshold=0.033876
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
      T78563 ImmuneDiseaseSystem.disease.infect (tick 37)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 100.0 ← T74509
        agent:102.hunger = 0.0 ← T75407
        agent:102.immune_memory = 0.0 ← T6
        agent:102.immunity = 0.43349 ← T75407
        agent:102.infected = false ← T6
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.318455 ← T76459
      Random:
        disease.infection@agent:102 = 0.011169 threshold=0.054604
        disease.infection@agent:102 = 0.131254
      Writes:
        agent:102.health: 100.0 → 92.687459
        agent:102.immune_memory: 0.0 → 0.35
        agent:102.infected: false → true
      T115334 ImmuneDiseaseSystem.disease.recover (tick 55)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T112292
        agent:102.immune_memory = 0.35 ← T78563
        agent:102.immunity = 0.430601 ← T112292
        agent:102.infected = true ← T78563
      Random:
        disease.recovery@agent:102 = 0.118911 threshold=0.19765
      Writes:
        agent:102.infected: true → false
      T123296 AgentSystem.agent.health (tick 60)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 53.687459 ← T121320
        agent:102.hunger = 0.0 ← T122241
        agent:102.infected = false ← T115334
      Writes:
        agent:102.health: 53.687459 → 55.187459
      … 2 more parent(s)
    T154297 ImmuneDiseaseSystem.disease.recover (tick 75)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.hunger = 0.0 ← T151397
      agent:102.immune_memory = 0.7 ← T127155
      agent:102.immunity = 0.427682 ← T151397
      agent:102.infected = true ← T127155
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
      T127155 ImmuneDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T123296
        agent:102.hunger = 0.0 ← T124214
        agent:102.immune_memory = 0.35 ← T78563
        agent:102.immunity = 0.429694 ← T124214
        agent:102.infected = false ← T115334
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.279929 ← T125189
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.033876
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T151397 AgentSystem.agent.metabolism (tick 74)
      Inputs:
        agent:102.hunger = 0.0 ← T149455
        agent:102.immunity = 0.427821 ← T149455
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1054.721069 ← T150450
        region:2.population = 108 ← T150388
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.427821 → 0.427682
    T158179 AgentSystem.agent.health (tick 78)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 15.312727 ← T156249
      agent:102.hunger = 0.0 ← T157182
      agent:102.infected = false ← T154297
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
      T154297 ImmuneDiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T151397
        agent:102.immune_memory = 0.7 ← T127155
        agent:102.immunity = 0.427682 ← T151397
        agent:102.infected = true ← T127155
      Random:
        disease.recovery@agent:102 = 0.244162 threshold=0.26692
      Writes:
        agent:102.infected: true → false
      T156249 AgentSystem.agent.health (tick 77)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 13.812727 ← T154324
        agent:102.hunger = 0.0 ← T155257
        agent:102.infected = false ← T154297
      Writes:
        agent:102.health: 13.812727 → 15.312727
      T157182 AgentSystem.agent.metabolism (tick 77)
      Inputs:
        agent:102.hunger = 0.0 ← T155257
        agent:102.immunity = 0.427406 ← T155257
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1048.122643 ← T156236
        region:2.population = 108 ← T156188
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.427406 → 0.427269
    … 2 more parent(s)
  T165888 AgentSystem.agent.health (tick 82)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 3.523145 ← T163953
    agent:102.hunger = 0.0 ← T164887
    agent:102.infected = true ← T161994
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
    T161994 ImmuneDiseaseSystem.disease.infect (tick 79)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 16.812727 ← T158179
      agent:102.hunger = 0.0 ← T159112
      agent:102.immune_memory = 0.7 ← T127155
      agent:102.immunity = 0.427132 ← T159112
      agent:102.infected = false ← T154297
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.20482 ← T160063
    Random:
      disease.infection@agent:102 = 0.00308 threshold=0.014334
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
      T127155 ImmuneDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T123296
        agent:102.hunger = 0.0 ← T124214
        agent:102.immune_memory = 0.35 ← T78563
        agent:102.immunity = 0.429694 ← T124214
        agent:102.infected = false ← T115334
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.279929 ← T125189
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.033876
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T154297 ImmuneDiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T151397
        agent:102.immune_memory = 0.7 ← T127155
        agent:102.immunity = 0.427682 ← T151397
        agent:102.infected = true ← T127155
      Random:
        disease.recovery@agent:102 = 0.244162 threshold=0.26692
      Writes:
        agent:102.infected: true → false
      T158179 AgentSystem.agent.health (tick 78)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 15.312727 ← T156249
        agent:102.hunger = 0.0 ← T157182
        agent:102.infected = false ← T154297
      Writes:
        agent:102.health: 15.312727 → 16.812727
      … 2 more parent(s)
    T163953 AgentSystem.agent.health (tick 81)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 6.023145 ← T162029
      agent:102.hunger = 0.0 ← T162962
      agent:102.infected = true ← T161994
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
      T161994 ImmuneDiseaseSystem.disease.infect (tick 79)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 16.812727 ← T158179
        agent:102.hunger = 0.0 ← T159112
        agent:102.immune_memory = 0.7 ← T127155
        agent:102.immunity = 0.427132 ← T159112
        agent:102.infected = false ← T154297
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.20482 ← T160063
      Random:
        disease.infection@agent:102 = 0.00308 threshold=0.014334
        disease.infection@agent:102 = 0.829238
      Writes:
        agent:102.health: 16.812727 → 8.523145
        agent:102.immune_memory: 0.7 → 1.0
        agent:102.infected: false → true
      T162029 AgentSystem.agent.health (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 8.523145 ← T161994
        agent:102.hunger = 0.0 ← T161035
        agent:102.infected = true ← T161994
      Writes:
        agent:102.health: 8.523145 → 6.023145
      T162962 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161035
        agent:102.immunity = 0.426997 ← T161035
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1010.739144 ← T162016
        region:2.population = 108 ← T161966
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
    T164887 AgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T162962
      agent:102.immunity = 0.426862 ← T162962
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1036.491032 ← T163940
      region:2.population = 108 ← T163893
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
      T162962 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161035
        agent:102.immunity = 0.426997 ← T161035
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1010.739144 ← T162016
        region:2.population = 108 ← T161966
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
      T163893 AgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:11.alive = true ← T14
        agent:11.region = region:2 ← T68274
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        … 224 more input(s)
      Writes:
        region:2.population: 108 → 108
        region:2.workers: 108 → 108
      T163940 StorageAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1010.739144 ← T162016
        region:2.population = 108 ← T161966
        region:2.rainfall = 0.577858 ← T161976
        region:2.soil_fertility = 0.421909 ← T162016
        region:2.temperature = 18.934401 ← T161976
        region:2.workers = 108 ← T161966
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1010.739144 → 1036.491032
        region:2.soil_fertility: 0.421909 → 0.421009
  T166822 AgentSystem.agent.metabolism (tick 82)
  Inputs:
    agent:102.hunger = 0.0 ← T164887
    agent:102.immunity = 0.426727 ← T164887
    agent:102.region = region:2 ← T6
    region:2.food_stock = 1015.062167 ← T165875
    region:2.population = 108 ← T165818
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
    T164887 AgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T162962
      agent:102.immunity = 0.426862 ← T162962
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1036.491032 ← T163940
      region:2.population = 108 ← T163893
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
      T162962 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161035
        agent:102.immunity = 0.426997 ← T161035
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1010.739144 ← T162016
        region:2.population = 108 ← T161966
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
      T163893 AgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:11.alive = true ← T14
        agent:11.region = region:2 ← T68274
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        … 224 more input(s)
      Writes:
        region:2.population: 108 → 108
        region:2.workers: 108 → 108
      T163940 StorageAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1010.739144 ← T162016
        region:2.population = 108 ← T161966
        region:2.rainfall = 0.577858 ← T161976
        region:2.soil_fertility = 0.421909 ← T162016
        region:2.temperature = 18.934401 ← T161976
        region:2.workers = 108 ← T161966
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1010.739144 → 1036.491032
        region:2.soil_fertility: 0.421909 → 0.421009
    T165818 AgentSystem.agents.census (tick 81)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.region = region:2 ← T6
      agent:11.alive = true ← T14
      agent:11.region = region:2 ← T68274
      agent:112.alive = true ← T17
      agent:112.region = region:2 ← T17
      agent:12.alive = true ← T25
      agent:12.region = region:2 ← T25
      … 224 more input(s)
    Writes:
      region:2.population: 108 → 108
      region:2.workers: 108 → 108
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
      T14 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:11 = 0.80521
        genesis.attribute@agent:11 = 0.788259
        genesis.attribute@agent:11 = 0.271182
        genesis.attribute@agent:11 = 0.380633
      Writes:
        agent:11.alive: none → true
        agent:11.health: none → 89.156314
        agent:11.hunger: none → 0.336478
        agent:11.immune_memory: none → 0.0
        agent:11.immunity: none → 0.39915
        agent:11.infected: none → false
        agent:11.region: none → region:1
        agent:11.risk_tolerance: none → 0.380633
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
      … 128 more parent(s)
    T165875 StorageAgricultureSystem.agriculture.harvest (tick 81)
    Inputs:
      region:2.food_stock = 1036.491032 ← T163940
      region:2.population = 108 ← T163893
      region:2.rainfall = 0.568902 ← T163903
      region:2.soil_fertility = 0.421009 ← T163940
      region:2.temperature = 19.003536 ← T163903
      region:2.workers = 108 ← T163893
    Random:
      agriculture.crop_variance@region:2 = 0.024179
    Writes:
      region:2.food_stock: 1036.491032 → 1015.062167
      region:2.soil_fertility: 0.421009 → 0.420109
      T163893 AgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:11.alive = true ← T14
        agent:11.region = region:2 ← T68274
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        … 224 more input(s)
      Writes:
        region:2.population: 108 → 108
        region:2.workers: 108 → 108
      T163903 ClimateSystem.climate.step (tick 80)
      Inputs:
        region:2.climate_volatility = 0.508114 ← T1003
        region:2.rainfall = 0.577858 ← T161976
        region:2.rainfall_base = 0.553388 ← T1003
        region:2.temperature = 18.934401 ← T161976
        region:2.temperature_base = 18.487763 ← T1003
      Random:
        climate.temperature_noise@region:2 = 0.642326
        climate.rain@region:2 = 0.466151
      Writes:
        region:2.rainfall: 0.577858 → 0.568902
        region:2.temperature: 18.934401 → 19.003536
      T163940 StorageAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1010.739144 ← T162016
        region:2.population = 108 ← T161966
        region:2.rainfall = 0.577858 ← T161976
        region:2.soil_fertility = 0.421909 ← T162016
        region:2.temperature = 18.934401 ← T161976
        region:2.workers = 108 ← T161966
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1010.739144 → 1036.491032
        region:2.soil_fertility: 0.421909 → 0.421009
```

### agent:108 — acute_infection (died tick 427, T682296)

```
T682296 ImmuneDiseaseSystem.disease.infect (tick 427)
Inputs:
  agent:108.alive = true ← T12
  agent:108.health = 2.0 ← T680831
  agent:108.hunger = 1.0 ← T681154
  agent:108.immune_memory = 1.0 ← T236999
  agent:108.immunity = 0.0 ← T681154
  agent:108.infected = false ← T246613
  agent:108.region = region:5 ← T669077
  region:5.disease_load = 0.174491 ← T681560
Random:
  disease.infection@agent:108 = 0.020597 threshold=0.023556
  disease.infection@agent:108 = 0.445427
Writes:
  agent:108.alive: true → false
  agent:108.health: 2.0 → 0.0
  agent:108.immune_memory: 1.0 → 1.0
  agent:108.infected: false → true
  T12 GenesisSystem.genesis.agent (tick 0)
  Random:
    genesis.attribute@agent:108 = 0.948869
    genesis.attribute@agent:108 = 0.621539
    genesis.attribute@agent:108 = 0.754699
    genesis.attribute@agent:108 = 0.239165
  Writes:
    agent:108.alive: none → true
    agent:108.health: none → 93.466071
    agent:108.hunger: none → 0.286462
    agent:108.immune_memory: none → 0.0
    agent:108.immunity: none → 0.665084
    agent:108.infected: none → false
    agent:108.region: none → region:8
    agent:108.risk_tolerance: none → 0.239165
  T236999 ImmuneDiseaseSystem.disease.infect (tick 118)
  Inputs:
    agent:108.alive = true ← T12
    agent:108.health = 100.0 ← T233199
    agent:108.hunger = 0.0 ← T234131
    agent:108.immune_memory = 0.7 ← T194745
    agent:108.immunity = 0.539806 ← T234131
    agent:108.infected = false ← T196675
    agent:108.region = region:8 ← T12
    region:8.disease_load = 0.186556 ← T235082
  Random:
    disease.infection@agent:108 = 0.008563 threshold=0.011268
    disease.infection@agent:108 = 0.55132
  Writes:
    agent:108.health: 100.0 → 93.322341
    agent:108.immune_memory: 0.7 → 1.0
    agent:108.infected: false → true
    T12 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:108 = 0.948869
      genesis.attribute@agent:108 = 0.621539
      genesis.attribute@agent:108 = 0.754699
      genesis.attribute@agent:108 = 0.239165
    Writes:
      agent:108.alive: none → true
      agent:108.health: none → 93.466071
      agent:108.hunger: none → 0.286462
      agent:108.immune_memory: none → 0.0
      agent:108.immunity: none → 0.665084
      agent:108.infected: none → false
      agent:108.region: none → region:8
      agent:108.risk_tolerance: none → 0.239165
    T194745 ImmuneDiseaseSystem.disease.infect (tick 96)
    Inputs:
      agent:108.alive = true ← T12
      agent:108.health = 100.0 ← T190937
      agent:108.hunger = 0.0 ← T191869
      agent:108.immune_memory = 0.35 ← T119288
      agent:108.immunity = 0.556106 ← T191869
      agent:108.infected = false ← T131069
      agent:108.region = region:8 ← T12
      region:8.disease_load = 0.187508 ← T192820
    Random:
      disease.infection@agent:108 = 0.013703 threshold=0.019195
      disease.infection@agent:108 = 0.634362
    Writes:
      agent:108.health: 100.0 → 90.248541
      agent:108.immune_memory: 0.35 → 0.7
      agent:108.infected: false → true
      T12 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:108 = 0.948869
        genesis.attribute@agent:108 = 0.621539
        genesis.attribute@agent:108 = 0.754699
        genesis.attribute@agent:108 = 0.239165
      Writes:
        agent:108.alive: none → true
        agent:108.health: none → 93.466071
        agent:108.hunger: none → 0.286462
        agent:108.immune_memory: none → 0.0
        agent:108.immunity: none → 0.665084
        agent:108.infected: none → false
        agent:108.region: none → region:8
        agent:108.risk_tolerance: none → 0.239165
      T119288 ImmuneDiseaseSystem.disease.infect (tick 57)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.health = 100.0 ← T115396
        agent:108.hunger = 0.0 ← T116313
        agent:108.immune_memory = 0.0 ← T12
        agent:108.immunity = 0.58981 ← T116313
        agent:108.infected = false ← T12
        agent:108.region = region:8 ← T12
        region:8.disease_load = 0.322588 ← T117311
      Random:
        disease.infection@agent:108 = 0.023595 threshold=0.044724
        disease.infection@agent:108 = 0.657075
      Writes:
        agent:108.health: 100.0 → 87.429254
        agent:108.immune_memory: 0.0 → 0.35
        agent:108.infected: false → true
      T131069 ImmuneDiseaseSystem.disease.recover (tick 63)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.hunger = 0.0 ← T128141
        agent:108.immune_memory = 0.35 ← T119288
        agent:108.immunity = 0.584186 ← T128141
        agent:108.infected = true ← T119288
      Random:
        disease.recovery@agent:108 = 0.131379 threshold=0.236047
      Writes:
        agent:108.infected: true → false
      T190937 AgentSystem.agent.health (tick 95)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.health = 100.0 ← T189018
        agent:108.hunger = 0.0 ← T189950
        agent:108.infected = false ← T131069
      Writes:
        agent:108.health: 100.0 → 100.0
      … 2 more parent(s)
    T196675 ImmuneDiseaseSystem.disease.recover (tick 97)
    Inputs:
      agent:108.alive = true ← T12
      agent:108.hunger = 0.0 ← T193792
      agent:108.immune_memory = 0.7 ← T194745
      agent:108.immunity = 0.555325 ← T193792
      agent:108.infected = true ← T194745
    Random:
      disease.recovery@agent:108 = 0.027547 threshold=0.298831
    Writes:
      agent:108.infected: true → false
      T12 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:108 = 0.948869
        genesis.attribute@agent:108 = 0.621539
        genesis.attribute@agent:108 = 0.754699
        genesis.attribute@agent:108 = 0.239165
      Writes:
        agent:108.alive: none → true
        agent:108.health: none → 93.466071
        agent:108.hunger: none → 0.286462
        agent:108.immune_memory: none → 0.0
        agent:108.immunity: none → 0.665084
        agent:108.infected: none → false
        agent:108.region: none → region:8
        agent:108.risk_tolerance: none → 0.239165
      T193792 AgentSystem.agent.metabolism (tick 96)
      Inputs:
        agent:108.hunger = 0.0 ← T191869
        agent:108.immunity = 0.556106 ← T191869
        agent:108.region = region:8 ← T12
        region:8.food_stock = 2196.336572 ← T192849
        region:8.population = 131 ← T192800
      Writes:
        agent:108.hunger: 0.0 → 0.0
        agent:108.immunity: 0.556106 → 0.555325
      T194745 ImmuneDiseaseSystem.disease.infect (tick 96)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.health = 100.0 ← T190937
        agent:108.hunger = 0.0 ← T191869
        agent:108.immune_memory = 0.35 ← T119288
        agent:108.immunity = 0.556106 ← T191869
        agent:108.infected = false ← T131069
        agent:108.region = region:8 ← T12
        region:8.disease_load = 0.187508 ← T192820
      Random:
        disease.infection@agent:108 = 0.013703 threshold=0.019195
        disease.infection@agent:108 = 0.634362
      Writes:
        agent:108.health: 100.0 → 90.248541
        agent:108.immune_memory: 0.35 → 0.7
        agent:108.infected: false → true
    T233199 AgentSystem.agent.health (tick 117)
    Inputs:
      agent:108.alive = true ← T12
      agent:108.health = 100.0 ← T231281
      agent:108.hunger = 0.0 ← T232213
      agent:108.infected = false ← T196675
    Writes:
      agent:108.health: 100.0 → 100.0
      T12 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:108 = 0.948869
        genesis.attribute@agent:108 = 0.621539
        genesis.attribute@agent:108 = 0.754699
        genesis.attribute@agent:108 = 0.239165
      Writes:
        agent:108.alive: none → true
        agent:108.health: none → 93.466071
        agent:108.hunger: none → 0.286462
        agent:108.immune_memory: none → 0.0
        agent:108.immunity: none → 0.665084
        agent:108.infected: none → false
        agent:108.region: none → region:8
        agent:108.risk_tolerance: none → 0.239165
      T196675 ImmuneDiseaseSystem.disease.recover (tick 97)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.hunger = 0.0 ← T193792
        agent:108.immune_memory = 0.7 ← T194745
        agent:108.immunity = 0.555325 ← T193792
        agent:108.infected = true ← T194745
      Random:
        disease.recovery@agent:108 = 0.027547 threshold=0.298831
      Writes:
        agent:108.infected: true → false
      T231281 AgentSystem.agent.health (tick 116)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.health = 100.0 ← T229361
        agent:108.hunger = 0.0 ← T230293
        agent:108.infected = false ← T196675
      Writes:
        agent:108.health: 100.0 → 100.0
      T232213 AgentSystem.agent.metabolism (tick 116)
      Inputs:
        agent:108.hunger = 0.0 ← T230293
        agent:108.immunity = 0.541215 ← T230293
        agent:108.region = region:8 ← T12
        region:8.food_stock = 2359.659432 ← T231270
        region:8.population = 131 ← T231224
      Writes:
        agent:108.hunger: 0.0 → 0.0
        agent:108.immunity: 0.541215 → 0.540509
    … 2 more parent(s)
  T246613 ImmuneDiseaseSystem.disease.recover (tick 123)
  Inputs:
    agent:108.alive = true ← T12
    agent:108.hunger = 0.0 ← T243732
    agent:108.immune_memory = 1.0 ← T236999
    agent:108.immunity = 0.536346 ← T243732
    agent:108.infected = true ← T236999
  Random:
    disease.recovery@agent:108 = 0.224597 threshold=0.354086
  Writes:
    agent:108.infected: true → false
    T12 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:108 = 0.948869
      genesis.attribute@agent:108 = 0.621539
      genesis.attribute@agent:108 = 0.754699
      genesis.attribute@agent:108 = 0.239165
    Writes:
      agent:108.alive: none → true
      agent:108.health: none → 93.466071
      agent:108.hunger: none → 0.286462
      agent:108.immune_memory: none → 0.0
      agent:108.immunity: none → 0.665084
      agent:108.infected: none → false
      agent:108.region: none → region:8
      agent:108.risk_tolerance: none → 0.239165
    T236999 ImmuneDiseaseSystem.disease.infect (tick 118)
    Inputs:
      agent:108.alive = true ← T12
      agent:108.health = 100.0 ← T233199
      agent:108.hunger = 0.0 ← T234131
      agent:108.immune_memory = 0.7 ← T194745
      agent:108.immunity = 0.539806 ← T234131
      agent:108.infected = false ← T196675
      agent:108.region = region:8 ← T12
      region:8.disease_load = 0.186556 ← T235082
    Random:
      disease.infection@agent:108 = 0.008563 threshold=0.011268
      disease.infection@agent:108 = 0.55132
    Writes:
      agent:108.health: 100.0 → 93.322341
      agent:108.immune_memory: 0.7 → 1.0
      agent:108.infected: false → true
      T12 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:108 = 0.948869
        genesis.attribute@agent:108 = 0.621539
        genesis.attribute@agent:108 = 0.754699
        genesis.attribute@agent:108 = 0.239165
      Writes:
        agent:108.alive: none → true
        agent:108.health: none → 93.466071
        agent:108.hunger: none → 0.286462
        agent:108.immune_memory: none → 0.0
        agent:108.immunity: none → 0.665084
        agent:108.infected: none → false
        agent:108.region: none → region:8
        agent:108.risk_tolerance: none → 0.239165
      T194745 ImmuneDiseaseSystem.disease.infect (tick 96)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.health = 100.0 ← T190937
        agent:108.hunger = 0.0 ← T191869
        agent:108.immune_memory = 0.35 ← T119288
        agent:108.immunity = 0.556106 ← T191869
        agent:108.infected = false ← T131069
        agent:108.region = region:8 ← T12
        region:8.disease_load = 0.187508 ← T192820
      Random:
        disease.infection@agent:108 = 0.013703 threshold=0.019195
        disease.infection@agent:108 = 0.634362
      Writes:
        agent:108.health: 100.0 → 90.248541
        agent:108.immune_memory: 0.35 → 0.7
        agent:108.infected: false → true
      T196675 ImmuneDiseaseSystem.disease.recover (tick 97)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.hunger = 0.0 ← T193792
        agent:108.immune_memory = 0.7 ← T194745
        agent:108.immunity = 0.555325 ← T193792
        agent:108.infected = true ← T194745
      Random:
        disease.recovery@agent:108 = 0.027547 threshold=0.298831
      Writes:
        agent:108.infected: true → false
      T233199 AgentSystem.agent.health (tick 117)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.health = 100.0 ← T231281
        agent:108.hunger = 0.0 ← T232213
        agent:108.infected = false ← T196675
      Writes:
        agent:108.health: 100.0 → 100.0
      … 2 more parent(s)
    T243732 AgentSystem.agent.metabolism (tick 122)
    Inputs:
      agent:108.hunger = 0.0 ← T241809
      agent:108.immunity = 0.537031 ← T241809
      agent:108.region = region:8 ← T12
      region:8.food_stock = 2175.807827 ← T242789
      region:8.population = 131 ← T242740
    Writes:
      agent:108.hunger: 0.0 → 0.0
      agent:108.immunity: 0.537031 → 0.536346
      T12 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:108 = 0.948869
        genesis.attribute@agent:108 = 0.621539
        genesis.attribute@agent:108 = 0.754699
        genesis.attribute@agent:108 = 0.239165
      Writes:
        agent:108.alive: none → true
        agent:108.health: none → 93.466071
        agent:108.hunger: none → 0.286462
        agent:108.immune_memory: none → 0.0
        agent:108.immunity: none → 0.665084
        agent:108.infected: none → false
        agent:108.region: none → region:8
        agent:108.risk_tolerance: none → 0.239165
      T241809 AgentSystem.agent.metabolism (tick 121)
      Inputs:
        agent:108.hunger = 0.0 ← T239889
        agent:108.immunity = 0.53772 ← T239889
        agent:108.region = region:8 ← T12
        region:8.food_stock = 2220.356179 ← T240866
        region:8.population = 131 ← T240820
      Writes:
        agent:108.hunger: 0.0 → 0.0
        agent:108.immunity: 0.53772 → 0.537031
      T242740 AgentSystem.agents.census (tick 121)
      Inputs:
        agent:105.alive = false ← T136911
        agent:105.region = region:8 ← T136841
        agent:108.alive = true ← T12
        agent:108.region = region:8 ← T12
        agent:118.alive = true ← T23
        agent:118.region = region:8 ← T23
        agent:121.alive = true ← T27
        agent:121.region = region:8 ← T111261
        … 266 more input(s)
      Writes:
        region:8.population: 131 → 131
        region:8.workers: 131 → 131
      T242789 StorageAgricultureSystem.agriculture.harvest (tick 121)
      Inputs:
        region:8.food_stock = 2220.356179 ← T240866
        region:8.population = 131 ← T240820
        region:8.rainfall = 0.701922 ← T240830
        region:8.soil_fertility = 0.453841 ← T240866
        region:8.temperature = 19.565607 ← T240830
        region:8.workers = 131 ← T240820
      Random:
        agriculture.crop_variance@region:8 = 0.3505
      Writes:
        region:8.food_stock: 2220.356179 → 2175.807827
        region:8.soil_fertility: 0.453841 → 0.452941
  T669077 AgentSystem.agent.migrate (tick 413)
  Inputs:
    agent:108.hunger = 1.0 ← T667477
    agent:108.region = region:4 ← T659952
    agent:108.risk_tolerance = 0.239165 ← T12
  Random:
    agent.decision@agent:108 = 0.02783 threshold=0.119583
  Writes:
    agent:108.region: region:4 → region:5
    T12 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:108 = 0.948869
      genesis.attribute@agent:108 = 0.621539
      genesis.attribute@agent:108 = 0.754699
      genesis.attribute@agent:108 = 0.239165
    Writes:
      agent:108.alive: none → true
      agent:108.health: none → 93.466071
      agent:108.hunger: none → 0.286462
      agent:108.immune_memory: none → 0.0
      agent:108.immunity: none → 0.665084
      agent:108.infected: none → false
      agent:108.region: none → region:8
      agent:108.risk_tolerance: none → 0.239165
    T659952 AgentSystem.agent.migrate (tick 405)
    Inputs:
      agent:108.hunger = 1.0 ← T658265
      agent:108.region = region:3 ← T658776
      agent:108.risk_tolerance = 0.239165 ← T12
    Random:
      agent.decision@agent:108 = 0.048414 threshold=0.119583
    Writes:
      agent:108.region: region:3 → region:4
      T12 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:108 = 0.948869
        genesis.attribute@agent:108 = 0.621539
        genesis.attribute@agent:108 = 0.754699
        genesis.attribute@agent:108 = 0.239165
      Writes:
        agent:108.alive: none → true
        agent:108.health: none → 93.466071
        agent:108.hunger: none → 0.286462
        agent:108.immune_memory: none → 0.0
        agent:108.immunity: none → 0.665084
        agent:108.infected: none → false
        agent:108.region: none → region:8
        agent:108.risk_tolerance: none → 0.239165
      T658265 AgentSystem.agent.metabolism (tick 404)
      Inputs:
        agent:108.hunger = 1.0 ← T657081
        agent:108.immunity = 0.1399 ← T657081
        agent:108.region = region:2 ← T656409
        region:2.food_stock = 0.0 ← T657740
        region:2.population = 57 ← T657694
      Writes:
        agent:108.hunger: 1.0 → 1.0
        agent:108.immunity: 0.1399 → 0.1312
      T658776 AgentSystem.agent.migrate (tick 404)
      Inputs:
        agent:108.hunger = 1.0 ← T657081
        agent:108.region = region:2 ← T656409
        agent:108.risk_tolerance = 0.239165 ← T12
      Random:
        agent.decision@agent:108 = 0.108456 threshold=0.119583
      Writes:
        agent:108.region: region:2 → region:3
    T667477 AgentSystem.agent.metabolism (tick 412)
    Inputs:
      agent:108.hunger = 1.0 ← T666356
      agent:108.immunity = 0.07151 ← T666356
      agent:108.region = region:4 ← T659952
      region:4.food_stock = 0.0 ← T666982
      region:4.population = 41 ← T666934
    Writes:
      agent:108.hunger: 1.0 → 1.0
      agent:108.immunity: 0.07151 → 0.063152
      T659952 AgentSystem.agent.migrate (tick 405)
      Inputs:
        agent:108.hunger = 1.0 ← T658265
        agent:108.region = region:3 ← T658776
        agent:108.risk_tolerance = 0.239165 ← T12
      Random:
        agent.decision@agent:108 = 0.048414 threshold=0.119583
      Writes:
        agent:108.region: region:3 → region:4
      T666356 AgentSystem.agent.metabolism (tick 411)
      Inputs:
        agent:108.hunger = 1.0 ← T665230
        agent:108.immunity = 0.079909 ← T665230
        agent:108.region = region:4 ← T659952
        region:4.food_stock = 0.0 ← T665857
        region:4.population = 39 ← T665813
      Writes:
        agent:108.hunger: 1.0 → 1.0
        agent:108.immunity: 0.079909 → 0.07151
      T666934 AgentSystem.agents.census (tick 411)
      Inputs:
        agent:10.alive = false ← T346702
        agent:10.region = region:4 ← T346609
        agent:108.alive = true ← T12
        agent:108.region = region:4 ← T659952
        agent:134.alive = false ← T499143
        agent:134.region = region:4 ← T41
        agent:138.alive = true ← T45
        agent:138.region = region:4 ← T665722
        … 182 more input(s)
      Writes:
        region:4.population: 39 → 41
        region:4.workers: 39 → 41
      T666982 StorageAgricultureSystem.agriculture.harvest (tick 411)
      Inputs:
        region:4.food_stock = 0.0 ← T665857
        region:4.population = 39 ← T665813
        region:4.rainfall = 0.55039 ← T665823
        region:4.soil_fertility = 0.254605 ← T665857
        region:4.temperature = 22.136728 ← T665823
        region:4.workers = 39 ← T665813
      Random:
        agriculture.crop_variance@region:4 = 0.578688
      Writes:
        region:4.food_stock: 0.0 → 0.0
        region:4.soil_fertility: 0.254605 → 0.253705
  … 3 more parent(s)
```

## Reproduction

```bash
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset storage --db runs/survival_seed7_storage.db --report <path>
```

Same seed + kernel v0.1.0 + ruleset 0.3.2e → bit-identical world, identical traces, identical report.