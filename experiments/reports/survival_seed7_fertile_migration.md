# Causal survival experiment — seed 7

Kernel **v0.1 (frozen)**, ruleset **0.3.3i** — the laws
differ from the baseline by proposal only; the kernel, the purposes
and the addressable draw stream are unchanged.

> Experiment I (fertile migration + fallow): migration targets the most fertile, least crowded region; abandoned soil heals.

## Run

| parameter | value |
|---|---|
| seed | 7 |
| ruleset | 0.3.3i |
| regions | 10 |
| agents | 1000 |
| ticks | 10000 |
| wall time | 698s |
| archive | `runs/survival_seed7_fertile_migration.db` |
| survivors | 0 / 1000 |
| deaths | 1000 |
| last death | tick 710 |

## Lifespan distribution (all agents died: no censoring)

| pct | ticks |
|---|---|
| p0 | 28 |
| p10 | 391 |
| p25 | 570 |
| p50 | 693 |
| p75 | 702 |
| p90 | 710 |
| p100 | 710 |

mean lifespan: **605** ticks

## Statistical regularity: correlations with lifespan

| observable | pearson | spearman |
|---|---|---|
| initial_health | +0.047 | +0.008 |
| initial_immunity | +0.068 | +0.029 |
| risk_tolerance | +0.404 | +0.322 |
| migration_count | +0.510 | +0.476 |
| infection_count | +0.495 | +0.188 |
| avg_food_access | +0.353 | +0.087 |
| avg_social_density | +0.840 | +0.404 |

## Individual causality: death mechanisms (from traces)

| mechanism | deaths | share |
|---|---|---|
| disease+starvation | 952 | 95.2% |
| acute_infection | 41 | 4.1% |
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
| stayers (0 migrations) | 61 | 220 | 4 | 5 | 52 |
| migrants (>=1 migration) | 939 | 630 | 37 | 2 | 900 |

### Risk tolerance quartiles

| group | n | mean lifespan | acute_infection | disease | disease+starvation |
|---|---|---|---|---|---|
| risk Q1 (lowest) | 250 | 477 | 10 | 2 | 238 |
| risk Q2 | 250 | 632 | 17 | 1 | 232 |
| risk Q3 | 250 | 646 | 7 | 2 | 241 |
| risk Q4 (highest) | 250 | 667 | 7 | 2 | 241 |

## Example mechanical explanations

### agent:102 — disease (died tick 83, T168222)

```
T168222 FertileMigrationAgentSystem.agent.death (tick 83)
Inputs:
  agent:102.alive = true ← T6
  agent:102.health = 1.023145 ← T166276
  agent:102.hunger = 0.0 ← T167220
  agent:102.infected = true ← T162328
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
  T162328 ImmuneDiseaseSystem.disease.infect (tick 79)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 16.812727 ← T158480
    agent:102.hunger = 0.0 ← T159424
    agent:102.immune_memory = 0.7 ← T127153
    agent:102.immunity = 0.427132 ← T159424
    agent:102.infected = false ← T154545
    agent:102.region = region:2 ← T6
    region:2.disease_load = 0.217787 ← T160375
  Random:
    disease.infection@agent:102 = 0.00308 threshold=0.015242
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
    T127153 ImmuneDiseaseSystem.disease.infect (tick 61)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 55.187459 ← T123291
      agent:102.hunger = 0.0 ← T124216
      agent:102.immune_memory = 0.35 ← T78562
      agent:102.immunity = 0.429694 ← T124216
      agent:102.infected = false ← T115302
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.254014 ← T125181
    Random:
      disease.infection@agent:102 = 0.019219 threshold=0.03074
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
        agent:102.health = 100.0 ← T74494
        agent:102.hunger = 0.0 ← T75427
        agent:102.immune_memory = 0.0 ← T6
        agent:102.immunity = 0.43349 ← T75427
        agent:102.infected = false ← T6
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.258662 ← T76462
      Random:
        disease.infection@agent:102 = 0.011169 threshold=0.044352
        disease.infection@agent:102 = 0.131254
      Writes:
        agent:102.health: 100.0 → 92.687459
        agent:102.immune_memory: 0.0 → 0.35
        agent:102.infected: false → true
      T115302 ImmuneDiseaseSystem.disease.recover (tick 55)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T112269
        agent:102.immune_memory = 0.35 ← T78562
        agent:102.immunity = 0.430601 ← T112269
        agent:102.infected = true ← T78562
      Random:
        disease.recovery@agent:102 = 0.118911 threshold=0.19765
      Writes:
        agent:102.infected: true → false
      T123291 FertileMigrationAgentSystem.agent.health (tick 60)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 53.687459 ← T121322
        agent:102.hunger = 0.0 ← T122250
        agent:102.infected = false ← T115302
      Writes:
        agent:102.health: 53.687459 → 55.187459
      … 2 more parent(s)
    T154545 ImmuneDiseaseSystem.disease.recover (tick 75)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.hunger = 0.0 ← T151628
      agent:102.immune_memory = 0.7 ← T127153
      agent:102.immunity = 0.427682 ← T151628
      agent:102.infected = true ← T127153
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
      T127153 ImmuneDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T123291
        agent:102.hunger = 0.0 ← T124216
        agent:102.immune_memory = 0.35 ← T78562
        agent:102.immunity = 0.429694 ← T124216
        agent:102.infected = false ← T115302
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.254014 ← T125181
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.03074
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T151628 FertileMigrationAgentSystem.agent.metabolism (tick 74)
      Inputs:
        agent:102.hunger = 0.0 ← T149668
        agent:102.immunity = 0.427821 ← T149668
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1364.826229 ← T148711
        region:2.population = 100 ← T150609
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.427821 → 0.427682
    T158480 FertileMigrationAgentSystem.agent.health (tick 78)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 15.312727 ← T156531
      agent:102.hunger = 0.0 ← T157475
      agent:102.infected = false ← T154545
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
      T154545 ImmuneDiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T151628
        agent:102.immune_memory = 0.7 ← T127153
        agent:102.immunity = 0.427682 ← T151628
        agent:102.infected = true ← T127153
      Random:
        disease.recovery@agent:102 = 0.244162 threshold=0.26692
      Writes:
        agent:102.infected: true → false
      T156531 FertileMigrationAgentSystem.agent.health (tick 77)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 13.812727 ← T154582
        agent:102.hunger = 0.0 ← T155526
        agent:102.infected = false ← T154545
      Writes:
        agent:102.health: 13.812727 → 15.312727
      T157475 FertileMigrationAgentSystem.agent.metabolism (tick 77)
      Inputs:
        agent:102.hunger = 0.0 ← T155526
        agent:102.immunity = 0.427406 ← T155526
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1290.072088 ← T154569
        region:2.population = 100 ← T156467
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.427406 → 0.427269
    … 2 more parent(s)
  T166276 FertileMigrationAgentSystem.agent.health (tick 82)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 3.523145 ← T164320
    agent:102.hunger = 0.0 ← T165264
    agent:102.infected = true ← T162328
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
    T162328 ImmuneDiseaseSystem.disease.infect (tick 79)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 16.812727 ← T158480
      agent:102.hunger = 0.0 ← T159424
      agent:102.immune_memory = 0.7 ← T127153
      agent:102.immunity = 0.427132 ← T159424
      agent:102.infected = false ← T154545
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.217787 ← T160375
    Random:
      disease.infection@agent:102 = 0.00308 threshold=0.015242
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
      T127153 ImmuneDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T123291
        agent:102.hunger = 0.0 ← T124216
        agent:102.immune_memory = 0.35 ← T78562
        agent:102.immunity = 0.429694 ← T124216
        agent:102.infected = false ← T115302
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.254014 ← T125181
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.03074
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T154545 ImmuneDiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T151628
        agent:102.immune_memory = 0.7 ← T127153
        agent:102.immunity = 0.427682 ← T151628
        agent:102.infected = true ← T127153
      Random:
        disease.recovery@agent:102 = 0.244162 threshold=0.26692
      Writes:
        agent:102.infected: true → false
      T158480 FertileMigrationAgentSystem.agent.health (tick 78)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 15.312727 ← T156531
        agent:102.hunger = 0.0 ← T157475
        agent:102.infected = false ← T154545
      Writes:
        agent:102.health: 15.312727 → 16.812727
      … 2 more parent(s)
    T164320 FertileMigrationAgentSystem.agent.health (tick 81)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 6.023145 ← T162375
      agent:102.hunger = 0.0 ← T163319
      agent:102.infected = true ← T162328
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
      T162328 ImmuneDiseaseSystem.disease.infect (tick 79)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 16.812727 ← T158480
        agent:102.hunger = 0.0 ← T159424
        agent:102.immune_memory = 0.7 ← T127153
        agent:102.immunity = 0.427132 ← T159424
        agent:102.infected = false ← T154545
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.217787 ← T160375
      Random:
        disease.infection@agent:102 = 0.00308 threshold=0.015242
        disease.infection@agent:102 = 0.829238
      Writes:
        agent:102.health: 16.812727 → 8.523145
        agent:102.immune_memory: 0.7 → 1.0
        agent:102.infected: false → true
      T162375 FertileMigrationAgentSystem.agent.health (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 8.523145 ← T162328
        agent:102.hunger = 0.0 ← T161369
        agent:102.infected = true ← T162328
      Writes:
        agent:102.health: 8.523145 → 6.023145
      T163319 FertileMigrationAgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161369
        agent:102.immunity = 0.426997 ← T161369
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1190.927954 ← T160412
        region:2.population = 100 ← T162310
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
    T165264 FertileMigrationAgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T163319
      agent:102.immunity = 0.426862 ← T163319
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1194.457143 ← T162362
      region:2.population = 100 ← T164260
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
      T162362 FallowAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1190.927954 ← T160412
        region:2.population = 100 ← T162310
        region:2.rainfall = 0.577858 ← T160402
        region:2.soil_fertility = 0.421909 ← T160412
        region:2.temperature = 18.934401 ← T160402
        region:2.workers = 100 ← T162310
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1190.927954 → 1194.457143
        region:2.soil_fertility: 0.421909 → 0.421009
      T163319 FertileMigrationAgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161369
        agent:102.immunity = 0.426997 ← T161369
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1190.927954 ← T160412
        region:2.population = 100 ← T162310
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
      T164260 FertileMigrationAgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 192 more input(s)
      Writes:
        region:2.population: 100 → 100
        region:2.workers: 100 → 100
  T167220 FertileMigrationAgentSystem.agent.metabolism (tick 82)
  Inputs:
    agent:102.hunger = 0.0 ← T165264
    agent:102.immunity = 0.426727 ← T165264
    agent:102.region = region:2 ← T6
    region:2.food_stock = 1154.410662 ← T164307
    region:2.population = 100 ← T166205
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
    T164307 FallowAgricultureSystem.agriculture.harvest (tick 81)
    Inputs:
      region:2.food_stock = 1194.457143 ← T162362
      region:2.population = 100 ← T164260
      region:2.rainfall = 0.568902 ← T162352
      region:2.soil_fertility = 0.421009 ← T162362
      region:2.temperature = 19.003536 ← T162352
      region:2.workers = 100 ← T164260
    Random:
      agriculture.crop_variance@region:2 = 0.024179
    Writes:
      region:2.food_stock: 1194.457143 → 1154.410662
      region:2.soil_fertility: 0.421009 → 0.420109
      T162352 ClimateSystem.climate.step (tick 80)
      Inputs:
        region:2.climate_volatility = 0.508114 ← T1003
        region:2.rainfall = 0.577858 ← T160402
        region:2.rainfall_base = 0.553388 ← T1003
        region:2.temperature = 18.934401 ← T160402
        region:2.temperature_base = 18.487763 ← T1003
      Random:
        climate.temperature_noise@region:2 = 0.642326
        climate.rain@region:2 = 0.466151
      Writes:
        region:2.rainfall: 0.577858 → 0.568902
        region:2.temperature: 18.934401 → 19.003536
      T162362 FallowAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1190.927954 ← T160412
        region:2.population = 100 ← T162310
        region:2.rainfall = 0.577858 ← T160402
        region:2.soil_fertility = 0.421909 ← T160412
        region:2.temperature = 18.934401 ← T160402
        region:2.workers = 100 ← T162310
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1190.927954 → 1194.457143
        region:2.soil_fertility: 0.421909 → 0.421009
      T164260 FertileMigrationAgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 192 more input(s)
      Writes:
        region:2.population: 100 → 100
        region:2.workers: 100 → 100
    T165264 FertileMigrationAgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T163319
      agent:102.immunity = 0.426862 ← T163319
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1194.457143 ← T162362
      region:2.population = 100 ← T164260
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
      T162362 FallowAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1190.927954 ← T160412
        region:2.population = 100 ← T162310
        region:2.rainfall = 0.577858 ← T160402
        region:2.soil_fertility = 0.421909 ← T160412
        region:2.temperature = 18.934401 ← T160402
        region:2.workers = 100 ← T162310
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1190.927954 → 1194.457143
        region:2.soil_fertility: 0.421909 → 0.421009
      T163319 FertileMigrationAgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161369
        agent:102.immunity = 0.426997 ← T161369
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1190.927954 ← T160412
        region:2.population = 100 ← T162310
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
      T164260 FertileMigrationAgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 192 more input(s)
      Writes:
        region:2.population: 100 → 100
        region:2.workers: 100 → 100
    T166205 FertileMigrationAgentSystem.agents.census (tick 81)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.region = region:2 ← T6
      agent:112.alive = true ← T17
      agent:112.region = region:2 ← T17
      agent:12.alive = true ← T25
      agent:12.region = region:2 ← T25
      agent:122.alive = true ← T28
      agent:122.region = region:2 ← T28
      … 192 more input(s)
    Writes:
      region:2.population: 100 → 100
      region:2.workers: 100 → 100
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
      … 96 more parent(s)
```

### agent:104 — acute_infection (died tick 699, T1219683)

```
T1219683 ImmuneDiseaseSystem.disease.infect (tick 699)
Inputs:
  agent:104.alive = true ← T8
  agent:104.health = 1.050634 ← T1217981
  agent:104.hunger = 1.0 ← T1218332
  agent:104.immune_memory = 1.0 ← T1201112
  agent:104.immunity = 0.0 ← T1218332
  agent:104.infected = false ← T1207019
  agent:104.region = region:1 ← T1218703
  region:1.disease_load = 0.272802 ← T1218813
Random:
  disease.infection@agent:104 = 0.03453 threshold=0.036828
  disease.infection@agent:104 = 0.288114
Writes:
  agent:104.alive: true → false
  agent:104.health: 1.050634 → 0.0
  agent:104.immune_memory: 1.0 → 1.0
  agent:104.infected: false → true
  T8 GenesisSystem.genesis.agent (tick 0)
  Random:
    genesis.attribute@agent:104 = 0.248748
    genesis.attribute@agent:104 = 0.758659
    genesis.attribute@agent:104 = 0.396423
    genesis.attribute@agent:104 = 0.546489
  Writes:
    agent:104.alive: none → true
    agent:104.health: none → 72.462427
    agent:104.hunger: none → 0.327598
    agent:104.immune_memory: none → 0.0
    agent:104.immunity: none → 0.468033
    agent:104.infected: none → false
    agent:104.region: none → region:4
    agent:104.risk_tolerance: none → 0.546489
  T1201112 ImmuneDiseaseSystem.disease.infect (tick 684)
  Inputs:
    agent:104.alive = true ← T8
    agent:104.health = 42.28733 ← T1198178
    agent:104.hunger = 1.0 ← T1198800
    agent:104.immune_memory = 1.0 ← T1052923
    agent:104.immunity = 0.0 ← T1198800
    agent:104.infected = false ← T1061214
    agent:104.region = region:0 ← T1190329
    region:0.disease_load = 0.318869 ← T1199602
  Random:
    disease.infection@agent:104 = 0.04061 threshold=0.043047
    disease.infection@agent:104 = 0.209174
  Writes:
    agent:104.health: 42.28733 → 39.050634
    agent:104.immune_memory: 1.0 → 1.0
    agent:104.infected: false → true
    T8 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:104 = 0.248748
      genesis.attribute@agent:104 = 0.758659
      genesis.attribute@agent:104 = 0.396423
      genesis.attribute@agent:104 = 0.546489
    Writes:
      agent:104.alive: none → true
      agent:104.health: none → 72.462427
      agent:104.hunger: none → 0.327598
      agent:104.immune_memory: none → 0.0
      agent:104.immunity: none → 0.468033
      agent:104.infected: none → false
      agent:104.region: none → region:4
      agent:104.risk_tolerance: none → 0.546489
    T1052923 ImmuneDiseaseSystem.disease.infect (tick 574)
    Inputs:
      agent:104.alive = true ← T8
      agent:104.health = 28.0 ← T1025750
      agent:104.hunger = 0.446798 ← T1050707
      agent:104.immune_memory = 1.0 ← T712970
      agent:104.immunity = 0.0 ← T1050707
      agent:104.infected = false ← T731496
      agent:104.region = region:1 ← T1047018
      region:1.disease_load = 0.240929 ← T1051501
    Random:
      disease.infection@agent:104 = 0.009405 threshold=0.01978
      disease.infection@agent:104 = 0.453167
    Writes:
      agent:104.health: 28.0 → 23.78733
      agent:104.immune_memory: 1.0 → 1.0
      agent:104.infected: false → true
      T8 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:104 = 0.248748
        genesis.attribute@agent:104 = 0.758659
        genesis.attribute@agent:104 = 0.396423
        genesis.attribute@agent:104 = 0.546489
      Writes:
        agent:104.alive: none → true
        agent:104.health: none → 72.462427
        agent:104.hunger: none → 0.327598
        agent:104.immune_memory: none → 0.0
        agent:104.immunity: none → 0.468033
        agent:104.infected: none → false
        agent:104.region: none → region:4
        agent:104.risk_tolerance: none → 0.546489
      T712970 ImmuneDiseaseSystem.disease.infect (tick 377)
      Inputs:
        agent:104.alive = true ← T8
        agent:104.health = 100.0 ← T700436
        agent:104.hunger = 0.633299 ← T710342
        agent:104.immune_memory = 1.0 ← T146719
        agent:104.immunity = 0.301543 ← T710342
        agent:104.infected = false ← T148687
        agent:104.region = region:6 ← T709631
        region:6.disease_load = 0.174405 ← T711375
      Random:
        disease.infection@agent:104 = 0.009998 threshold=0.013225
        disease.infection@agent:104 = 0.817694
      Writes:
        agent:104.health: 100.0 → 94.329223
        agent:104.immune_memory: 1.0 → 1.0
        agent:104.infected: false → true
      T731496 ImmuneDiseaseSystem.disease.recover (tick 388)
      Inputs:
        agent:104.alive = true ← T8
        agent:104.hunger = 0.303299 ← T728934
        agent:104.immune_memory = 1.0 ← T712970
        agent:104.immunity = 0.258351 ← T728934
        agent:104.infected = true ← T712970
      Random:
        disease.recovery@agent:104 = 0.016535 threshold=0.239093
      Writes:
        agent:104.infected: true → false
      T1025750 FertileMigrationAgentSystem.agent.health (tick 558)
      Inputs:
        agent:104.alive = true ← T8
        agent:104.health = 30.0 ← T1024102
        agent:104.hunger = 0.751173 ← T1024741
        agent:104.infected = false ← T731496
      Writes:
        agent:104.health: 30.0 → 28.0
      … 3 more parent(s)
    T1061214 ImmuneDiseaseSystem.disease.recover (tick 580)
    Inputs:
      agent:104.alive = true ← T8
      agent:104.hunger = 0.539284 ← T1059026
      agent:104.immune_memory = 1.0 ← T1052923
      agent:104.immunity = 0.0 ← T1059026
      agent:104.infected = true ← T1052923
    Random:
      disease.recovery@agent:104 = 0.007461 threshold=0.139107
    Writes:
      agent:104.infected: true → false
      T8 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:104 = 0.248748
        genesis.attribute@agent:104 = 0.758659
        genesis.attribute@agent:104 = 0.396423
        genesis.attribute@agent:104 = 0.546489
      Writes:
        agent:104.alive: none → true
        agent:104.health: none → 72.462427
        agent:104.hunger: none → 0.327598
        agent:104.immune_memory: none → 0.0
        agent:104.immunity: none → 0.468033
        agent:104.infected: none → false
        agent:104.region: none → region:4
        agent:104.risk_tolerance: none → 0.546489
      T1052923 ImmuneDiseaseSystem.disease.infect (tick 574)
      Inputs:
        agent:104.alive = true ← T8
        agent:104.health = 28.0 ← T1025750
        agent:104.hunger = 0.446798 ← T1050707
        agent:104.immune_memory = 1.0 ← T712970
        agent:104.immunity = 0.0 ← T1050707
        agent:104.infected = false ← T731496
        agent:104.region = region:1 ← T1047018
        region:1.disease_load = 0.240929 ← T1051501
      Random:
        disease.infection@agent:104 = 0.009405 threshold=0.01978
        disease.infection@agent:104 = 0.453167
      Writes:
        agent:104.health: 28.0 → 23.78733
        agent:104.immune_memory: 1.0 → 1.0
        agent:104.infected: false → true
      T1059026 FertileMigrationAgentSystem.agent.metabolism (tick 579)
      Inputs:
        agent:104.hunger = 0.469284 ← T1057651
        agent:104.immunity = 0.0 ← T1057651
        agent:104.region = region:1 ← T1047018
        region:1.food_stock = 0.0 ← T1057073
        region:1.population = 104 ← T1058395
      Writes:
        agent:104.hunger: 0.469284 → 0.539284
        agent:104.immunity: 0.0 → 0.0
    T1190329 FertileMigrationAgentSystem.agent.migrate (tick 677)
    Inputs:
      agent:104.hunger = 1.0 ← T1188179
      agent:104.region = region:1 ← T1184247
      agent:104.risk_tolerance = 0.546489 ← T8
      region:0.food_stock = 0.0 ← T1187525
      region:0.population = 341 ← T1188987
      region:0.soil_fertility = 0.428521 ← T1187525
      region:2.food_stock = 0.0 ← T1187527
      region:2.population = 0 ← T1188989
      … 22 more input(s)
    Random:
      agent.decision@agent:104 = 0.217518 threshold=0.273244
    Writes:
      agent:104.region: region:1 → region:0
      T8 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:104 = 0.248748
        genesis.attribute@agent:104 = 0.758659
        genesis.attribute@agent:104 = 0.396423
        genesis.attribute@agent:104 = 0.546489
      Writes:
        agent:104.alive: none → true
        agent:104.health: none → 72.462427
        agent:104.hunger: none → 0.327598
        agent:104.immune_memory: none → 0.0
        agent:104.immunity: none → 0.468033
        agent:104.infected: none → false
        agent:104.region: none → region:4
        agent:104.risk_tolerance: none → 0.546489
      T1184247 FertileMigrationAgentSystem.agent.migrate (tick 673)
      Inputs:
        agent:104.hunger = 1.0 ← T1182072
        agent:104.region = region:0 ← T1178103
        agent:104.risk_tolerance = 0.546489 ← T8
        region:1.food_stock = 0.0 ← T1181418
        region:1.population = 321 ← T1182908
        region:1.soil_fertility = 0.865 ← T1181418
        region:2.food_stock = 0.0 ← T1181419
        region:2.population = 0 ← T1182909
        … 22 more input(s)
      Random:
        agent.decision@agent:104 = 0.240958 threshold=0.273244
      Writes:
        agent:104.region: region:0 → region:1
      T1187525 FallowAgricultureSystem.agriculture.harvest (tick 676)
      Inputs:
        region:0.food_stock = 28.358015 ← T1186004
        region:0.population = 334 ← T1187469
        region:0.rainfall = 0.61067 ← T1185994
        region:0.soil_fertility = 0.429421 ← T1186004
        region:0.temperature = 10.219658 ← T1185994
        region:0.workers = 334 ← T1187469
      Random:
        agriculture.crop_variance@region:0 = 0.197151
      Writes:
        region:0.food_stock: 28.358015 → 0.0
        region:0.soil_fertility: 0.429421 → 0.428521
      T1187527 FallowAgricultureSystem.agriculture.harvest (tick 676)
      Inputs:
        region:2.food_stock = 0.0 ← T1186006
        region:2.population = 0 ← T1187471
        region:2.rainfall = 0.481044 ← T1185996
        region:2.soil_fertility = 0.915109 ← T1186006
        region:2.temperature = 18.297316 ← T1185996
        region:2.workers = 0 ← T1187471
      Random:
        agriculture.crop_variance@region:2 = 0.446857
      Writes:
        region:2.food_stock: 0.0 → 0.0
        region:2.soil_fertility: 0.915109 → 0.916609
      … 17 more parent(s)
    … 3 more parent(s)
  T1207019 ImmuneDiseaseSystem.disease.recover (tick 688)
  Inputs:
    agent:104.alive = true ← T8
    agent:104.hunger = 1.0 ← T1204766
    agent:104.immune_memory = 1.0 ← T1201112
    agent:104.immunity = 0.0 ← T1204766
    agent:104.infected = true ← T1201112
  Random:
    disease.recovery@agent:104 = 0.03878 threshold=0.07
  Writes:
    agent:104.infected: true → false
    T8 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:104 = 0.248748
      genesis.attribute@agent:104 = 0.758659
      genesis.attribute@agent:104 = 0.396423
      genesis.attribute@agent:104 = 0.546489
    Writes:
      agent:104.alive: none → true
      agent:104.health: none → 72.462427
      agent:104.hunger: none → 0.327598
      agent:104.immune_memory: none → 0.0
      agent:104.immunity: none → 0.468033
      agent:104.infected: none → false
      agent:104.region: none → region:4
      agent:104.risk_tolerance: none → 0.546489
    T1201112 ImmuneDiseaseSystem.disease.infect (tick 684)
    Inputs:
      agent:104.alive = true ← T8
      agent:104.health = 42.28733 ← T1198178
      agent:104.hunger = 1.0 ← T1198800
      agent:104.immune_memory = 1.0 ← T1052923
      agent:104.immunity = 0.0 ← T1198800
      agent:104.infected = false ← T1061214
      agent:104.region = region:0 ← T1190329
      region:0.disease_load = 0.318869 ← T1199602
    Random:
      disease.infection@agent:104 = 0.04061 threshold=0.043047
      disease.infection@agent:104 = 0.209174
    Writes:
      agent:104.health: 42.28733 → 39.050634
      agent:104.immune_memory: 1.0 → 1.0
      agent:104.infected: false → true
      T8 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:104 = 0.248748
        genesis.attribute@agent:104 = 0.758659
        genesis.attribute@agent:104 = 0.396423
        genesis.attribute@agent:104 = 0.546489
      Writes:
        agent:104.alive: none → true
        agent:104.health: none → 72.462427
        agent:104.hunger: none → 0.327598
        agent:104.immune_memory: none → 0.0
        agent:104.immunity: none → 0.468033
        agent:104.infected: none → false
        agent:104.region: none → region:4
        agent:104.risk_tolerance: none → 0.546489
      T1052923 ImmuneDiseaseSystem.disease.infect (tick 574)
      Inputs:
        agent:104.alive = true ← T8
        agent:104.health = 28.0 ← T1025750
        agent:104.hunger = 0.446798 ← T1050707
        agent:104.immune_memory = 1.0 ← T712970
        agent:104.immunity = 0.0 ← T1050707
        agent:104.infected = false ← T731496
        agent:104.region = region:1 ← T1047018
        region:1.disease_load = 0.240929 ← T1051501
      Random:
        disease.infection@agent:104 = 0.009405 threshold=0.01978
        disease.infection@agent:104 = 0.453167
      Writes:
        agent:104.health: 28.0 → 23.78733
        agent:104.immune_memory: 1.0 → 1.0
        agent:104.infected: false → true
      T1061214 ImmuneDiseaseSystem.disease.recover (tick 580)
      Inputs:
        agent:104.alive = true ← T8
        agent:104.hunger = 0.539284 ← T1059026
        agent:104.immune_memory = 1.0 ← T1052923
        agent:104.immunity = 0.0 ← T1059026
        agent:104.infected = true ← T1052923
      Random:
        disease.recovery@agent:104 = 0.007461 threshold=0.139107
      Writes:
        agent:104.infected: true → false
      T1190329 FertileMigrationAgentSystem.agent.migrate (tick 677)
      Inputs:
        agent:104.hunger = 1.0 ← T1188179
        agent:104.region = region:1 ← T1184247
        agent:104.risk_tolerance = 0.546489 ← T8
        region:0.food_stock = 0.0 ← T1187525
        region:0.population = 341 ← T1188987
        region:0.soil_fertility = 0.428521 ← T1187525
        region:2.food_stock = 0.0 ← T1187527
        region:2.population = 0 ← T1188989
        … 22 more input(s)
      Random:
        agent.decision@agent:104 = 0.217518 threshold=0.273244
      Writes:
        agent:104.region: region:1 → region:0
      … 3 more parent(s)
    T1204766 FertileMigrationAgentSystem.agent.metabolism (tick 687)
    Inputs:
      agent:104.hunger = 1.0 ← T1203296
      agent:104.immunity = 0.0 ← T1203296
      agent:104.region = region:0 ← T1203908
      region:0.food_stock = 0.0 ← T1202669
      region:0.population = 345 ← T1204078
    Writes:
      agent:104.hunger: 1.0 → 1.0
      agent:104.immunity: 0.0 → 0.0
      T1202669 FallowAgricultureSystem.agriculture.harvest (tick 686)
      Inputs:
        region:0.food_stock = 0.0 ← T1201157
        region:0.population = 331 ← T1202605
        region:0.rainfall = 0.499116 ← T1201147
        region:0.soil_fertility = 0.420421 ← T1201157
        region:0.temperature = 8.954767 ← T1201147
        region:0.workers = 331 ← T1202605
      Random:
        agriculture.crop_variance@region:0 = 0.727453
      Writes:
        region:0.food_stock: 0.0 → 0.0
        region:0.soil_fertility: 0.420421 → 0.419521
      T1203296 FertileMigrationAgentSystem.agent.metabolism (tick 686)
      Inputs:
        agent:104.hunger = 1.0 ← T1201788
        agent:104.immunity = 0.0 ← T1201788
        agent:104.region = region:1 ← T1200903
        region:1.food_stock = 0.0 ← T1201158
        region:1.population = 287 ← T1202606
      Writes:
        agent:104.hunger: 1.0 → 1.0
        agent:104.immunity: 0.0 → 0.0
      T1203908 FertileMigrationAgentSystem.agent.migrate (tick 686)
      Inputs:
        agent:104.hunger = 1.0 ← T1201788
        agent:104.region = region:1 ← T1200903
        agent:104.risk_tolerance = 0.546489 ← T8
        region:0.food_stock = 0.0 ← T1201157
        region:0.population = 331 ← T1202605
        region:0.soil_fertility = 0.420421 ← T1201157
        region:2.food_stock = 0.0 ← T1201159
        region:2.population = 0 ← T1202607
        … 22 more input(s)
      Random:
        agent.decision@agent:104 = 0.112834 threshold=0.273244
      Writes:
        agent:104.region: region:1 → region:0
      T1204078 FertileMigrationAgentSystem.agents.census (tick 686)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.region = region:0 ← T1202403
        agent:101.alive = false ← T1020799
        agent:101.region = region:0 ← T1022281
        agent:106.alive = true ← T10
        agent:106.region = region:0 ← T1199426
        agent:107.alive = true ← T11
        agent:107.region = region:0 ← T1202404
        … 928 more input(s)
      Writes:
        region:0.population: 331 → 345
        region:0.workers: 331 → 345
  T1217981 FertileMigrationAgentSystem.agent.health (tick 698)
  Inputs:
    agent:104.alive = true ← T8
    agent:104.health = 3.050634 ← T1217015
    agent:104.hunger = 1.0 ← T1217386
    agent:104.infected = false ← T1207019
  Writes:
    agent:104.health: 3.050634 → 1.050634
    T8 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:104 = 0.248748
      genesis.attribute@agent:104 = 0.758659
      genesis.attribute@agent:104 = 0.396423
      genesis.attribute@agent:104 = 0.546489
    Writes:
      agent:104.alive: none → true
      agent:104.health: none → 72.462427
      agent:104.hunger: none → 0.327598
      agent:104.immune_memory: none → 0.0
      agent:104.immunity: none → 0.468033
      agent:104.infected: none → false
      agent:104.region: none → region:4
      agent:104.risk_tolerance: none → 0.546489
    T1207019 ImmuneDiseaseSystem.disease.recover (tick 688)
    Inputs:
      agent:104.alive = true ← T8
      agent:104.hunger = 1.0 ← T1204766
      agent:104.immune_memory = 1.0 ← T1201112
      agent:104.immunity = 0.0 ← T1204766
      agent:104.infected = true ← T1201112
    Random:
      disease.recovery@agent:104 = 0.03878 threshold=0.07
    Writes:
      agent:104.infected: true → false
      T8 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:104 = 0.248748
        genesis.attribute@agent:104 = 0.758659
        genesis.attribute@agent:104 = 0.396423
        genesis.attribute@agent:104 = 0.546489
      Writes:
        agent:104.alive: none → true
        agent:104.health: none → 72.462427
        agent:104.hunger: none → 0.327598
        agent:104.immune_memory: none → 0.0
        agent:104.immunity: none → 0.468033
        agent:104.infected: none → false
        agent:104.region: none → region:4
        agent:104.risk_tolerance: none → 0.546489
      T1201112 ImmuneDiseaseSystem.disease.infect (tick 684)
      Inputs:
        agent:104.alive = true ← T8
        agent:104.health = 42.28733 ← T1198178
        agent:104.hunger = 1.0 ← T1198800
        agent:104.immune_memory = 1.0 ← T1052923
        agent:104.immunity = 0.0 ← T1198800
        agent:104.infected = false ← T1061214
        agent:104.region = region:0 ← T1190329
        region:0.disease_load = 0.318869 ← T1199602
      Random:
        disease.infection@agent:104 = 0.04061 threshold=0.043047
        disease.infection@agent:104 = 0.209174
      Writes:
        agent:104.health: 42.28733 → 39.050634
        agent:104.immune_memory: 1.0 → 1.0
        agent:104.infected: false → true
      T1204766 FertileMigrationAgentSystem.agent.metabolism (tick 687)
      Inputs:
        agent:104.hunger = 1.0 ← T1203296
        agent:104.immunity = 0.0 ← T1203296
        agent:104.region = region:0 ← T1203908
        region:0.food_stock = 0.0 ← T1202669
        region:0.population = 345 ← T1204078
      Writes:
        agent:104.hunger: 1.0 → 1.0
        agent:104.immunity: 0.0 → 0.0
    T1217015 FertileMigrationAgentSystem.agent.health (tick 697)
    Inputs:
      agent:104.alive = true ← T8
      agent:104.health = 5.050634 ← T1215997
      agent:104.hunger = 1.0 ← T1216395
      agent:104.infected = false ← T1207019
    Writes:
      agent:104.health: 5.050634 → 3.050634
      T8 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:104 = 0.248748
        genesis.attribute@agent:104 = 0.758659
        genesis.attribute@agent:104 = 0.396423
        genesis.attribute@agent:104 = 0.546489
      Writes:
        agent:104.alive: none → true
        agent:104.health: none → 72.462427
        agent:104.hunger: none → 0.327598
        agent:104.immune_memory: none → 0.0
        agent:104.immunity: none → 0.468033
        agent:104.infected: none → false
        agent:104.region: none → region:4
        agent:104.risk_tolerance: none → 0.546489
      T1207019 ImmuneDiseaseSystem.disease.recover (tick 688)
      Inputs:
        agent:104.alive = true ← T8
        agent:104.hunger = 1.0 ← T1204766
        agent:104.immune_memory = 1.0 ← T1201112
        agent:104.immunity = 0.0 ← T1204766
        agent:104.infected = true ← T1201112
      Random:
        disease.recovery@agent:104 = 0.03878 threshold=0.07
      Writes:
        agent:104.infected: true → false
      T1215997 FertileMigrationAgentSystem.agent.health (tick 696)
      Inputs:
        agent:104.alive = true ← T8
        agent:104.health = 7.050634 ← T1214893
        agent:104.hunger = 1.0 ← T1215319
        agent:104.infected = false ← T1207019
      Writes:
        agent:104.health: 7.050634 → 5.050634
      T1216395 FertileMigrationAgentSystem.agent.metabolism (tick 696)
      Inputs:
        agent:104.hunger = 1.0 ← T1215319
        agent:104.immunity = 0.0 ← T1215319
        agent:104.region = region:1 ← T1214683
        region:1.food_stock = 0.0 ← T1214859
        region:1.population = 246 ← T1215903
      Writes:
        agent:104.hunger: 1.0 → 1.0
        agent:104.immunity: 0.0 → 0.0
    T1217386 FertileMigrationAgentSystem.agent.metabolism (tick 697)
    Inputs:
      agent:104.hunger = 1.0 ← T1216395
      agent:104.immunity = 0.0 ← T1216395
      agent:104.region = region:1 ← T1214683
      region:1.food_stock = 0.0 ← T1215958
      region:1.population = 219 ← T1216933
    Writes:
      agent:104.hunger: 1.0 → 1.0
      agent:104.immunity: 0.0 → 0.0
      T1214683 FertileMigrationAgentSystem.agent.migrate (tick 694)
      Inputs:
        agent:104.hunger = 1.0 ← T1213009
        agent:104.region = region:0 ← T1210984
        agent:104.risk_tolerance = 0.546489 ← T8
        region:1.food_stock = 0.0 ← T1212492
        region:1.population = 242 ← T1213652
        region:1.soil_fertility = 0.8461 ← T1212492
        region:2.food_stock = 0.0 ← T1212493
        region:2.population = 0 ← T1213653
        … 22 more input(s)
      Random:
        agent.decision@agent:104 = 0.165401 threshold=0.273244
      Writes:
        agent:104.region: region:0 → region:1
      T1215958 FallowAgricultureSystem.agriculture.harvest (tick 696)
      Inputs:
        region:1.food_stock = 0.0 ← T1214859
        region:1.population = 246 ← T1215903
        region:1.rainfall = 0.314913 ← T1214849
        region:1.soil_fertility = 0.8443 ← T1214859
        region:1.temperature = 7.887124 ← T1214849
        region:1.workers = 246 ← T1215903
      Random:
        agriculture.crop_variance@region:1 = 0.100448
      Writes:
        region:1.food_stock: 0.0 → 0.0
        region:1.soil_fertility: 0.8443 → 0.8434
      T1216395 FertileMigrationAgentSystem.agent.metabolism (tick 696)
      Inputs:
        agent:104.hunger = 1.0 ← T1215319
        agent:104.immunity = 0.0 ← T1215319
        agent:104.region = region:1 ← T1214683
        region:1.food_stock = 0.0 ← T1214859
        region:1.population = 246 ← T1215903
      Writes:
        agent:104.hunger: 1.0 → 1.0
        agent:104.immunity: 0.0 → 0.0
      T1216933 FertileMigrationAgentSystem.agents.census (tick 696)
      Inputs:
        agent:0.alive = false ← T1212501
        agent:0.region = region:1 ← T1213511
        agent:1.alive = true ← T2
        agent:1.region = region:1 ← T1215766
        agent:103.alive = false ← T1066803
        agent:103.region = region:1 ← T1059742
        agent:104.alive = true ← T8
        agent:104.region = region:1 ← T1214683
        … 908 more input(s)
      Writes:
        region:1.population: 246 → 219
        region:1.workers: 246 → 219
  … 3 more parent(s)
```

## Reproduction

```bash
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset fertile_migration --db runs/survival_seed7_fertile_migration.db --report <path>
```

Same seed + kernel v0.1.0 + ruleset 0.3.3i → bit-identical world, identical traces, identical report.