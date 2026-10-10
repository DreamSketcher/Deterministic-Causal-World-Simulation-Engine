# Causal survival experiment — seed 7

Kernel **v0.1 (frozen)**, ruleset **0.3.3i-plain** — the laws
differ from the baseline by proposal only; the kernel, the purposes
and the addressable draw stream are unchanged.

> Experiment I control: informed migration alone, soil laws frozen (no fallow recovery).

## Run

| parameter | value |
|---|---|
| seed | 7 |
| ruleset | 0.3.3i-plain |
| regions | 10 |
| agents | 1000 |
| ticks | 10000 |
| wall time | 670s |
| archive | `runs/survival_seed7_fertile_migration_only.db` |
| survivors | 0 / 1000 |
| deaths | 1000 |
| last death | tick 572 |

## Lifespan distribution (all agents died: no censoring)

| pct | ticks |
|---|---|
| p0 | 28 |
| p10 | 387 |
| p25 | 420 |
| p50 | 553 |
| p75 | 563 |
| p90 | 571 |
| p100 | 572 |

mean lifespan: **472** ticks

## Statistical regularity: correlations with lifespan

| observable | pearson | spearman |
|---|---|---|
| initial_health | +0.081 | +0.052 |
| initial_immunity | +0.072 | +0.033 |
| risk_tolerance | +0.249 | +0.156 |
| migration_count | +0.358 | +0.288 |
| infection_count | +0.473 | +0.245 |
| avg_food_access | +0.297 | +0.057 |
| avg_social_density | +0.888 | +0.745 |

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
| migrants (>=1 migration) | 939 | 488 | 37 | 2 | 900 |

### Risk tolerance quartiles

| group | n | mean lifespan | acute_infection | disease | disease+starvation |
|---|---|---|---|---|---|
| risk Q1 (lowest) | 250 | 405 | 13 | 2 | 235 |
| risk Q2 | 250 | 493 | 7 | 1 | 242 |
| risk Q3 | 250 | 491 | 10 | 2 | 238 |
| risk Q4 (highest) | 250 | 498 | 11 | 2 | 237 |

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
        region:2.food_stock = 1364.826229 ← T148701
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
        region:2.food_stock = 1290.072088 ← T154559
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
        region:2.food_stock = 1190.927954 ← T160402
        region:2.population = 100 ← T162310
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
    T165264 FertileMigrationAgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T163319
      agent:102.immunity = 0.426862 ← T163319
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1194.457143 ← T162352
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
      T162352 AgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1190.927954 ← T160402
        region:2.population = 100 ← T162310
        region:2.rainfall = 0.577858 ← T160412
        region:2.soil_fertility = 0.421909 ← T160402
        region:2.temperature = 18.934401 ← T160412
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
        region:2.food_stock = 1190.927954 ← T160402
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
    region:2.food_stock = 1154.410662 ← T164297
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
    T164297 AgricultureSystem.agriculture.harvest (tick 81)
    Inputs:
      region:2.food_stock = 1194.457143 ← T162352
      region:2.population = 100 ← T164260
      region:2.rainfall = 0.568902 ← T162362
      region:2.soil_fertility = 0.421009 ← T162352
      region:2.temperature = 19.003536 ← T162362
      region:2.workers = 100 ← T164260
    Random:
      agriculture.crop_variance@region:2 = 0.024179
    Writes:
      region:2.food_stock: 1194.457143 → 1154.410662
      region:2.soil_fertility: 0.421009 → 0.420109
      T162352 AgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1190.927954 ← T160402
        region:2.population = 100 ← T162310
        region:2.rainfall = 0.577858 ← T160412
        region:2.soil_fertility = 0.421909 ← T160402
        region:2.temperature = 18.934401 ← T160412
        region:2.workers = 100 ← T162310
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1190.927954 → 1194.457143
        region:2.soil_fertility: 0.421909 → 0.421009
      T162362 ClimateSystem.climate.step (tick 80)
      Inputs:
        region:2.climate_volatility = 0.508114 ← T1003
        region:2.rainfall = 0.577858 ← T160412
        region:2.rainfall_base = 0.553388 ← T1003
        region:2.temperature = 18.934401 ← T160412
        region:2.temperature_base = 18.487763 ← T1003
      Random:
        climate.temperature_noise@region:2 = 0.642326
        climate.rain@region:2 = 0.466151
      Writes:
        region:2.rainfall: 0.577858 → 0.568902
        region:2.temperature: 18.934401 → 19.003536
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
      region:2.food_stock = 1194.457143 ← T162352
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
      T162352 AgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1190.927954 ← T160402
        region:2.population = 100 ← T162310
        region:2.rainfall = 0.577858 ← T160412
        region:2.soil_fertility = 0.421909 ← T160402
        region:2.temperature = 18.934401 ← T160412
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
        region:2.food_stock = 1190.927954 ← T160402
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

### agent:131 — acute_infection (died tick 51, T107196)

```
T107196 ImmuneDiseaseSystem.disease.infect (tick 51)
Inputs:
  agent:131.alive = true ← T38
  agent:131.health = 1.48163 ← T95098
  agent:131.hunger = 0.61 ← T104185
  agent:131.immune_memory = 0.7 ← T66231
  agent:131.immunity = 0.157539 ← T104185
  agent:131.infected = false ← T80697
  agent:131.region = region:8 ← T101034
  region:8.disease_load = 0.356861 ← T105163
Random:
  disease.infection@agent:131 = 0.049286 threshold=0.082277
  disease.infection@agent:131 = 0.224345
Writes:
  agent:131.alive: true → false
  agent:131.health: 1.48163 → 0.0
  agent:131.immune_memory: 0.7 → 1.0
  agent:131.infected: false → true
  T38 GenesisSystem.genesis.agent (tick 0)
  Random:
    genesis.attribute@agent:131 = 0.268755
    genesis.attribute@agent:131 = 0.837806
    genesis.attribute@agent:131 = 0.154505
    genesis.attribute@agent:131 = 0.439929
  Writes:
    agent:131.alive: none → true
    agent:131.health: none → 73.062638
    agent:131.hunger: none → 0.351342
    agent:131.immune_memory: none → 0.0
    agent:131.immunity: none → 0.334978
    agent:131.infected: none → false
    agent:131.region: none → region:1
    agent:131.risk_tolerance: none → 0.439929
  T66231 ImmuneDiseaseSystem.disease.infect (tick 31)
  Inputs:
    agent:131.alive = true ← T38
    agent:131.health = 55.529529 ← T54324
    agent:131.hunger = 0.56907 ← T63252
    agent:131.immune_memory = 0.35 ← T4204
    agent:131.immunity = 0.301994 ← T63252
    agent:131.infected = false ← T26718
    agent:131.region = region:1 ← T38
    region:1.disease_load = 0.415123 ← T64225
  Random:
    disease.infection@agent:131 = 0.127706 threshold=0.138293
    disease.infection@agent:131 = 0.735177
  Writes:
    agent:131.health: 55.529529 → 44.98163
    agent:131.immune_memory: 0.35 → 0.7
    agent:131.infected: false → true
    T38 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:131 = 0.268755
      genesis.attribute@agent:131 = 0.837806
      genesis.attribute@agent:131 = 0.154505
      genesis.attribute@agent:131 = 0.439929
    Writes:
      agent:131.alive: none → true
      agent:131.health: none → 73.062638
      agent:131.hunger: none → 0.351342
      agent:131.immune_memory: none → 0.0
      agent:131.immunity: none → 0.334978
      agent:131.infected: none → false
      agent:131.region: none → region:1
      agent:131.risk_tolerance: none → 0.439929
    T4204 ImmuneDiseaseSystem.disease.infect (tick 1)
    Inputs:
      agent:131.alive = true ← T38
      agent:131.health = 73.062638 ← T38
      agent:131.hunger = 0.321342 ← T1556
      agent:131.immune_memory = 0.0 ← T38
      agent:131.immunity = 0.332089 ← T1556
      agent:131.infected = false ← T38
      agent:131.region = region:1 ← T38
      region:1.disease_load = 0.120789 ← T2530
    Random:
      disease.infection@agent:131 = 0.014122 threshold=0.041454
      disease.infection@agent:131 = 0.503311
    Writes:
      agent:131.health: 73.062638 → 62.029529
      agent:131.immune_memory: 0.0 → 0.35
      agent:131.infected: false → true
      T38 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:131 = 0.268755
        genesis.attribute@agent:131 = 0.837806
        genesis.attribute@agent:131 = 0.154505
        genesis.attribute@agent:131 = 0.439929
      Writes:
        agent:131.alive: none → true
        agent:131.health: none → 73.062638
        agent:131.hunger: none → 0.351342
        agent:131.immune_memory: none → 0.0
        agent:131.immunity: none → 0.334978
        agent:131.infected: none → false
        agent:131.region: none → region:1
        agent:131.risk_tolerance: none → 0.439929
      T1556 FertileMigrationAgentSystem.agent.metabolism (tick 0)
      Inputs:
        agent:131.hunger = 0.351342 ← T38
        agent:131.immunity = 0.334978 ← T38
        agent:131.region = region:1 ← T38
        region:1.food_stock = 1614.504597 ← T1002
        region:1.population = 100 ← T1002
      Writes:
        agent:131.hunger: 0.351342 → 0.321342
        agent:131.immunity: 0.334978 → 0.332089
      T2530 ImmuneDiseaseSystem.disease.environment (tick 0)
      Inputs:
        agent:1.alive = true ← T2
        agent:1.infected = false ← T2
        agent:1.region = region:1 ← T2
        agent:101.alive = true ← T5
        agent:101.infected = false ← T5
        agent:101.region = region:1 ← T5
        agent:11.alive = true ← T14
        agent:11.infected = false ← T14
        … 294 more input(s)
      Random:
        disease.load_noise@region:1 = 0.328191
      Writes:
        region:1.disease_load: 0.118309 → 0.120789
    T26718 ImmuneDiseaseSystem.disease.recover (tick 12)
    Inputs:
      agent:131.alive = true ← T38
      agent:131.hunger = 0.0 ← T23583
      agent:131.immune_memory = 0.35 ← T4204
      agent:131.immunity = 0.320642 ← T23583
      agent:131.infected = true ← T4204
    Random:
      disease.recovery@agent:131 = 0.126841 threshold=0.170161
    Writes:
      agent:131.infected: true → false
      T38 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:131 = 0.268755
        genesis.attribute@agent:131 = 0.837806
        genesis.attribute@agent:131 = 0.154505
        genesis.attribute@agent:131 = 0.439929
      Writes:
        agent:131.alive: none → true
        agent:131.health: none → 73.062638
        agent:131.hunger: none → 0.351342
        agent:131.immune_memory: none → 0.0
        agent:131.immunity: none → 0.334978
        agent:131.infected: none → false
        agent:131.region: none → region:1
        agent:131.risk_tolerance: none → 0.439929
      T4204 ImmuneDiseaseSystem.disease.infect (tick 1)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.health = 73.062638 ← T38
        agent:131.hunger = 0.321342 ← T1556
        agent:131.immune_memory = 0.0 ← T38
        agent:131.immunity = 0.332089 ← T1556
        agent:131.infected = false ← T38
        agent:131.region = region:1 ← T38
        region:1.disease_load = 0.120789 ← T2530
      Random:
        disease.infection@agent:131 = 0.014122 threshold=0.041454
        disease.infection@agent:131 = 0.503311
      Writes:
        agent:131.health: 73.062638 → 62.029529
        agent:131.immune_memory: 0.0 → 0.35
        agent:131.infected: false → true
      T23583 FertileMigrationAgentSystem.agent.metabolism (tick 11)
      Inputs:
        agent:131.hunger = 0.021342 ← T21476
        agent:131.immunity = 0.320244 ← T21476
        agent:131.region = region:1 ← T38
        region:1.food_stock = 731.118976 ← T20420
        region:1.population = 100 ← T22440
      Writes:
        agent:131.hunger: 0.021342 → 0.0
        agent:131.immunity: 0.320244 → 0.320642
    T54324 FertileMigrationAgentSystem.agent.health (tick 26)
    Inputs:
      agent:131.alive = true ← T38
      agent:131.health = 54.029529 ← T52195
      agent:131.hunger = 0.21907 ← T53195
      agent:131.infected = false ← T26718
    Writes:
      agent:131.health: 54.029529 → 55.529529
      T38 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:131 = 0.268755
        genesis.attribute@agent:131 = 0.837806
        genesis.attribute@agent:131 = 0.154505
        genesis.attribute@agent:131 = 0.439929
      Writes:
        agent:131.alive: none → true
        agent:131.health: none → 73.062638
        agent:131.hunger: none → 0.351342
        agent:131.immune_memory: none → 0.0
        agent:131.immunity: none → 0.334978
        agent:131.infected: none → false
        agent:131.region: none → region:1
        agent:131.risk_tolerance: none → 0.439929
      T26718 ImmuneDiseaseSystem.disease.recover (tick 12)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.hunger = 0.0 ← T23583
        agent:131.immune_memory = 0.35 ← T4204
        agent:131.immunity = 0.320642 ← T23583
        agent:131.infected = true ← T4204
      Random:
        disease.recovery@agent:131 = 0.126841 threshold=0.170161
      Writes:
        agent:131.infected: true → false
      T52195 FertileMigrationAgentSystem.agent.health (tick 25)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.health = 52.529529 ← T50070
        agent:131.hunger = 0.14907 ← T51070
        agent:131.infected = false ← T26718
      Writes:
        agent:131.health: 52.529529 → 54.029529
      T53195 FertileMigrationAgentSystem.agent.metabolism (tick 25)
      Inputs:
        agent:131.hunger = 0.14907 ← T51070
        agent:131.immunity = 0.323128 ← T51070
        agent:131.region = region:1 ← T38
        region:1.food_stock = 0.0 ← T50014
        region:1.population = 100 ← T52034
      Writes:
        agent:131.hunger: 0.14907 → 0.21907
        agent:131.immunity: 0.323128 → 0.321321
    … 2 more parent(s)
  T80697 ImmuneDiseaseSystem.disease.recover (tick 38)
  Inputs:
    agent:131.alive = true ← T38
    agent:131.hunger = 1.0 ← T77540
    agent:131.immune_memory = 0.7 ← T66231
    agent:131.immunity = 0.247316 ← T77540
    agent:131.infected = true ← T66231
  Random:
    disease.recovery@agent:131 = 0.062477 threshold=0.071829
  Writes:
    agent:131.infected: true → false
    T38 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:131 = 0.268755
      genesis.attribute@agent:131 = 0.837806
      genesis.attribute@agent:131 = 0.154505
      genesis.attribute@agent:131 = 0.439929
    Writes:
      agent:131.alive: none → true
      agent:131.health: none → 73.062638
      agent:131.hunger: none → 0.351342
      agent:131.immune_memory: none → 0.0
      agent:131.immunity: none → 0.334978
      agent:131.infected: none → false
      agent:131.region: none → region:1
      agent:131.risk_tolerance: none → 0.439929
    T66231 ImmuneDiseaseSystem.disease.infect (tick 31)
    Inputs:
      agent:131.alive = true ← T38
      agent:131.health = 55.529529 ← T54324
      agent:131.hunger = 0.56907 ← T63252
      agent:131.immune_memory = 0.35 ← T4204
      agent:131.immunity = 0.301994 ← T63252
      agent:131.infected = false ← T26718
      agent:131.region = region:1 ← T38
      region:1.disease_load = 0.415123 ← T64225
    Random:
      disease.infection@agent:131 = 0.127706 threshold=0.138293
      disease.infection@agent:131 = 0.735177
    Writes:
      agent:131.health: 55.529529 → 44.98163
      agent:131.immune_memory: 0.35 → 0.7
      agent:131.infected: false → true
      T38 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:131 = 0.268755
        genesis.attribute@agent:131 = 0.837806
        genesis.attribute@agent:131 = 0.154505
        genesis.attribute@agent:131 = 0.439929
      Writes:
        agent:131.alive: none → true
        agent:131.health: none → 73.062638
        agent:131.hunger: none → 0.351342
        agent:131.immune_memory: none → 0.0
        agent:131.immunity: none → 0.334978
        agent:131.infected: none → false
        agent:131.region: none → region:1
        agent:131.risk_tolerance: none → 0.439929
      T4204 ImmuneDiseaseSystem.disease.infect (tick 1)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.health = 73.062638 ← T38
        agent:131.hunger = 0.321342 ← T1556
        agent:131.immune_memory = 0.0 ← T38
        agent:131.immunity = 0.332089 ← T1556
        agent:131.infected = false ← T38
        agent:131.region = region:1 ← T38
        region:1.disease_load = 0.120789 ← T2530
      Random:
        disease.infection@agent:131 = 0.014122 threshold=0.041454
        disease.infection@agent:131 = 0.503311
      Writes:
        agent:131.health: 73.062638 → 62.029529
        agent:131.immune_memory: 0.0 → 0.35
        agent:131.infected: false → true
      T26718 ImmuneDiseaseSystem.disease.recover (tick 12)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.hunger = 0.0 ← T23583
        agent:131.immune_memory = 0.35 ← T4204
        agent:131.immunity = 0.320642 ← T23583
        agent:131.infected = true ← T4204
      Random:
        disease.recovery@agent:131 = 0.126841 threshold=0.170161
      Writes:
        agent:131.infected: true → false
      T54324 FertileMigrationAgentSystem.agent.health (tick 26)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.health = 54.029529 ← T52195
        agent:131.hunger = 0.21907 ← T53195
        agent:131.infected = false ← T26718
      Writes:
        agent:131.health: 54.029529 → 55.529529
      … 2 more parent(s)
    T77540 FertileMigrationAgentSystem.agent.metabolism (tick 37)
    Inputs:
      agent:131.hunger = 0.98907 ← T75459
      agent:131.immunity = 0.256599 ← T75459
      agent:131.region = region:1 ← T38
      region:1.food_stock = 0.0 ← T74472
      region:1.population = 33 ← T76451
    Writes:
      agent:131.hunger: 0.98907 → 1.0
      agent:131.immunity: 0.256599 → 0.247316
      T38 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:131 = 0.268755
        genesis.attribute@agent:131 = 0.837806
        genesis.attribute@agent:131 = 0.154505
        genesis.attribute@agent:131 = 0.439929
      Writes:
        agent:131.alive: none → true
        agent:131.health: none → 73.062638
        agent:131.hunger: none → 0.351342
        agent:131.immune_memory: none → 0.0
        agent:131.immunity: none → 0.334978
        agent:131.infected: none → false
        agent:131.region: none → region:1
        agent:131.risk_tolerance: none → 0.439929
      T74472 AgricultureSystem.agriculture.harvest (tick 36)
      Inputs:
        region:1.food_stock = 0.0 ← T72376
        region:1.population = 41 ← T74383
        region:1.rainfall = 0.439525 ← T72386
        region:1.soil_fertility = 0.498032 ← T72376
        region:1.temperature = 10.235594 ← T72386
        region:1.workers = 41 ← T74383
      Random:
        agriculture.crop_variance@region:1 = 0.880569
      Writes:
        region:1.food_stock: 0.0 → 0.0
        region:1.soil_fertility: 0.498032 → 0.497132
      T75459 FertileMigrationAgentSystem.agent.metabolism (tick 36)
      Inputs:
        agent:131.hunger = 0.91907 ← T73380
        agent:131.immunity = 0.265819 ← T73380
        agent:131.region = region:1 ← T38
        region:1.food_stock = 0.0 ← T72376
        region:1.population = 41 ← T74383
      Writes:
        agent:131.hunger: 0.91907 → 0.98907
        agent:131.immunity: 0.265819 → 0.256599
      T76451 FertileMigrationAgentSystem.agents.census (tick 36)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.region = region:1 ← T38
        agent:141.alive = true ← T49
        agent:141.region = region:1 ← T49
        agent:171.alive = true ← T82
        agent:171.region = region:1 ← T82
        agent:181.alive = true ← T93
        agent:181.region = region:1 ← T93
        … 60 more input(s)
      Writes:
        region:1.population: 41 → 33
        region:1.workers: 41 → 33
  T95098 FertileMigrationAgentSystem.agent.health (tick 46)
  Inputs:
    agent:131.alive = true ← T38
    agent:131.health = 3.48163 ← T93033
    agent:131.hunger = 0.76 ← T93962
    agent:131.infected = false ← T80697
  Writes:
    agent:131.health: 3.48163 → 1.48163
    T38 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:131 = 0.268755
      genesis.attribute@agent:131 = 0.837806
      genesis.attribute@agent:131 = 0.154505
      genesis.attribute@agent:131 = 0.439929
    Writes:
      agent:131.alive: none → true
      agent:131.health: none → 73.062638
      agent:131.hunger: none → 0.351342
      agent:131.immune_memory: none → 0.0
      agent:131.immunity: none → 0.334978
      agent:131.infected: none → false
      agent:131.region: none → region:1
      agent:131.risk_tolerance: none → 0.439929
    T80697 ImmuneDiseaseSystem.disease.recover (tick 38)
    Inputs:
      agent:131.alive = true ← T38
      agent:131.hunger = 1.0 ← T77540
      agent:131.immune_memory = 0.7 ← T66231
      agent:131.immunity = 0.247316 ← T77540
      agent:131.infected = true ← T66231
    Random:
      disease.recovery@agent:131 = 0.062477 threshold=0.071829
    Writes:
      agent:131.infected: true → false
      T38 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:131 = 0.268755
        genesis.attribute@agent:131 = 0.837806
        genesis.attribute@agent:131 = 0.154505
        genesis.attribute@agent:131 = 0.439929
      Writes:
        agent:131.alive: none → true
        agent:131.health: none → 73.062638
        agent:131.hunger: none → 0.351342
        agent:131.immune_memory: none → 0.0
        agent:131.immunity: none → 0.334978
        agent:131.infected: none → false
        agent:131.region: none → region:1
        agent:131.risk_tolerance: none → 0.439929
      T66231 ImmuneDiseaseSystem.disease.infect (tick 31)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.health = 55.529529 ← T54324
        agent:131.hunger = 0.56907 ← T63252
        agent:131.immune_memory = 0.35 ← T4204
        agent:131.immunity = 0.301994 ← T63252
        agent:131.infected = false ← T26718
        agent:131.region = region:1 ← T38
        region:1.disease_load = 0.415123 ← T64225
      Random:
        disease.infection@agent:131 = 0.127706 threshold=0.138293
        disease.infection@agent:131 = 0.735177
      Writes:
        agent:131.health: 55.529529 → 44.98163
        agent:131.immune_memory: 0.35 → 0.7
        agent:131.infected: false → true
      T77540 FertileMigrationAgentSystem.agent.metabolism (tick 37)
      Inputs:
        agent:131.hunger = 0.98907 ← T75459
        agent:131.immunity = 0.256599 ← T75459
        agent:131.region = region:1 ← T38
        region:1.food_stock = 0.0 ← T74472
        region:1.population = 33 ← T76451
      Writes:
        agent:131.hunger: 0.98907 → 1.0
        agent:131.immunity: 0.256599 → 0.247316
    T93033 FertileMigrationAgentSystem.agent.health (tick 45)
    Inputs:
      agent:131.alive = true ← T38
      agent:131.health = 5.48163 ← T91007
      agent:131.hunger = 0.79 ← T91919
      agent:131.infected = false ← T80697
    Writes:
      agent:131.health: 5.48163 → 3.48163
      T38 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:131 = 0.268755
        genesis.attribute@agent:131 = 0.837806
        genesis.attribute@agent:131 = 0.154505
        genesis.attribute@agent:131 = 0.439929
      Writes:
        agent:131.alive: none → true
        agent:131.health: none → 73.062638
        agent:131.hunger: none → 0.351342
        agent:131.immune_memory: none → 0.0
        agent:131.immunity: none → 0.334978
        agent:131.infected: none → false
        agent:131.region: none → region:1
        agent:131.risk_tolerance: none → 0.439929
      T80697 ImmuneDiseaseSystem.disease.recover (tick 38)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.hunger = 1.0 ← T77540
        agent:131.immune_memory = 0.7 ← T66231
        agent:131.immunity = 0.247316 ← T77540
        agent:131.infected = true ← T66231
      Random:
        disease.recovery@agent:131 = 0.062477 threshold=0.071829
      Writes:
        agent:131.infected: true → false
      T91007 FertileMigrationAgentSystem.agent.health (tick 44)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.health = 7.48163 ← T88977
        agent:131.hunger = 0.82 ← T89893
        agent:131.infected = false ← T80697
      Writes:
        agent:131.health: 7.48163 → 5.48163
      T91919 FertileMigrationAgentSystem.agent.metabolism (tick 44)
      Inputs:
        agent:131.hunger = 0.82 ← T89893
        agent:131.immunity = 0.198833 ← T89893
        agent:131.region = region:9 ← T78502
        region:9.food_stock = 4394.467559 ← T88934
        region:9.population = 156 ← T90876
      Writes:
        agent:131.hunger: 0.82 → 0.79
        agent:131.immunity: 0.198833 → 0.191939
    T93962 FertileMigrationAgentSystem.agent.metabolism (tick 45)
    Inputs:
      agent:131.hunger = 0.79 ← T91919
      agent:131.immunity = 0.191939 ← T91919
      agent:131.region = region:9 ← T78502
      region:9.food_stock = 4443.818387 ← T90962
      region:9.population = 156 ← T92911
    Writes:
      agent:131.hunger: 0.79 → 0.76
      agent:131.immunity: 0.191939 → 0.185379
      T78502 FertileMigrationAgentSystem.agent.migrate (tick 37)
      Inputs:
        agent:131.hunger = 0.98907 ← T75459
        agent:131.region = region:1 ← T38
        agent:131.risk_tolerance = 0.439929 ← T38
        region:0.food_stock = 1021.272437 ← T74471
        region:0.population = 100 ← T76450
        region:0.soil_fertility = 0.493321 ← T74471
        region:2.food_stock = 1635.761518 ← T74473
        region:2.population = 100 ← T76452
        … 22 more input(s)
      Random:
        agent.decision@agent:131 = 0.131854 threshold=0.219965
      Writes:
        agent:131.region: region:1 → region:9
      T90962 AgricultureSystem.agriculture.harvest (tick 44)
      Inputs:
        region:9.food_stock = 4394.467559 ← T88934
        region:9.population = 156 ← T90876
        region:9.rainfall = 0.692515 ← T88944
        region:9.soil_fertility = 0.512723 ← T88934
        region:9.temperature = 17.095207 ← T88944
        region:9.workers = 156 ← T90876
      Random:
        agriculture.crop_variance@region:9 = 0.348266
      Writes:
        region:9.food_stock: 4394.467559 → 4443.818387
        region:9.soil_fertility: 0.512723 → 0.511823
      T91919 FertileMigrationAgentSystem.agent.metabolism (tick 44)
      Inputs:
        agent:131.hunger = 0.82 ← T89893
        agent:131.immunity = 0.198833 ← T89893
        agent:131.region = region:9 ← T78502
        region:9.food_stock = 4394.467559 ← T88934
        region:9.population = 156 ← T90876
      Writes:
        agent:131.hunger: 0.82 → 0.79
        agent:131.immunity: 0.198833 → 0.191939
      T92911 FertileMigrationAgentSystem.agents.census (tick 44)
      Inputs:
        agent:1.alive = true ← T2
        agent:1.region = region:9 ← T80598
        agent:109.alive = true ← T13
        agent:109.region = region:9 ← T13
        agent:11.alive = true ← T14
        agent:11.region = region:9 ← T68180
        agent:111.alive = true ← T16
        agent:111.region = region:9 ← T88808
        … 306 more input(s)
      Writes:
        region:9.population: 156 → 156
        region:9.workers: 156 → 156
  … 3 more parent(s)
```

## Reproduction

```bash
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset fertile_migration_only --db runs/survival_seed7_fertile_migration_only.db --report <path>
```

Same seed + kernel v0.1.0 + ruleset 0.3.3i-plain → bit-identical world, identical traces, identical report.