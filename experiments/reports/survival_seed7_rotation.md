# Causal survival experiment — seed 7

Kernel **v0.1 (frozen)**, ruleset **0.3.2f** — the laws
differ from the baseline by proposal only; the kernel, the purposes
and the addressable draw stream are unchanged.

> Experiment F (crop rotation): stable maximal labor load degrades soil 50 % faster; a fluctuating load lets it rest.

## Run

| parameter | value |
|---|---|
| seed | 7 |
| ruleset | 0.3.2f |
| regions | 10 |
| agents | 1000 |
| ticks | 10000 |
| wall time | 1145s |
| archive | `runs/survival_seed7_rotation.db` |
| survivors | 0 / 1000 |
| deaths | 1000 |
| last death | tick 514 |

## Lifespan distribution (all agents died: no censoring)

| pct | ticks |
|---|---|
| p0 | 28 |
| p10 | 148 |
| p25 | 211 |
| p50 | 351 |
| p75 | 368 |
| p90 | 497 |
| p100 | 514 |

mean lifespan: **302** ticks

## Statistical regularity: correlations with lifespan

| observable | pearson | spearman |
|---|---|---|
| initial_health | +0.003 | -0.002 |
| initial_immunity | -0.001 | -0.014 |
| risk_tolerance | +0.095 | +0.088 |
| migration_count | +0.233 | +0.257 |
| infection_count | +0.417 | +0.343 |
| avg_food_access | +0.698 | +0.760 |
| avg_social_density | +0.653 | +0.658 |

## Individual causality: death mechanisms (from traces)

| mechanism | deaths | share |
|---|---|---|
| disease+starvation | 959 | 95.9% |
| acute_infection | 34 | 3.4% |
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
| stayers (0 migrations) | 67 | 192 | 1 | 5 | 61 |
| migrants (>=1 migration) | 933 | 310 | 33 | 2 | 898 |

### Risk tolerance quartiles

| group | n | mean lifespan | acute_infection | disease | disease+starvation |
|---|---|---|---|---|---|
| risk Q1 (lowest) | 250 | 277 | 6 | 2 | 242 |
| risk Q2 | 250 | 315 | 15 | 1 | 234 |
| risk Q3 | 250 | 307 | 10 | 2 | 238 |
| risk Q4 (highest) | 250 | 310 | 3 | 2 | 245 |

## Example mechanical explanations

### agent:102 — disease (died tick 83, T167683)

```
T167683 AgentSystem.agent.death (tick 83)
Inputs:
  agent:102.alive = true ← T6
  agent:102.health = 1.023145 ← T165757
  agent:102.hunger = 0.0 ← T166691
  agent:102.infected = true ← T161865
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
  T161865 ImmuneDiseaseSystem.disease.infect (tick 79)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 16.812727 ← T158049
    agent:102.hunger = 0.0 ← T158983
    agent:102.immune_memory = 0.7 ← T127065
    agent:102.immunity = 0.427132 ← T158983
    agent:102.infected = false ← T154164
    agent:102.region = region:2 ← T6
    region:2.disease_load = 0.206458 ← T159935
  Random:
    disease.infection@agent:102 = 0.00308 threshold=0.014449
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
    T127065 ImmuneDiseaseSystem.disease.infect (tick 61)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 55.187459 ← T123236
      agent:102.hunger = 0.0 ← T124147
      agent:102.immune_memory = 0.35 ← T78577
      agent:102.immunity = 0.429694 ← T124147
      agent:102.infected = false ← T115299
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.268315 ← T125118
    Random:
      disease.infection@agent:102 = 0.019219 threshold=0.03247
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
      T78577 ImmuneDiseaseSystem.disease.infect (tick 37)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 100.0 ← T74498
        agent:102.hunger = 0.0 ← T75433
        agent:102.immune_memory = 0.0 ← T6
        agent:102.immunity = 0.43349 ← T75433
        agent:102.infected = false ← T6
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.310494 ← T76479
      Random:
        disease.infection@agent:102 = 0.011169 threshold=0.05324
        disease.infection@agent:102 = 0.131254
      Writes:
        agent:102.health: 100.0 → 92.687459
        agent:102.immune_memory: 0.0 → 0.35
        agent:102.infected: false → true
      T115299 ImmuneDiseaseSystem.disease.recover (tick 55)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T112261
        agent:102.immune_memory = 0.35 ← T78577
        agent:102.immunity = 0.430601 ← T112261
        agent:102.infected = true ← T78577
      Random:
        disease.recovery@agent:102 = 0.118911 threshold=0.19765
      Writes:
        agent:102.infected: true → false
      T123236 AgentSystem.agent.health (tick 60)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 53.687459 ← T121273
        agent:102.hunger = 0.0 ← T122190
        agent:102.infected = false ← T115299
      Writes:
        agent:102.health: 53.687459 → 55.187459
      … 2 more parent(s)
    T154164 ImmuneDiseaseSystem.disease.recover (tick 75)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.hunger = 0.0 ← T151264
      agent:102.immune_memory = 0.7 ← T127065
      agent:102.immunity = 0.427682 ← T151264
      agent:102.infected = true ← T127065
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
      T127065 ImmuneDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T123236
        agent:102.hunger = 0.0 ← T124147
        agent:102.immune_memory = 0.35 ← T78577
        agent:102.immunity = 0.429694 ← T124147
        agent:102.infected = false ← T115299
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.268315 ← T125118
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.03247
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T151264 AgentSystem.agent.metabolism (tick 74)
      Inputs:
        agent:102.hunger = 0.0 ← T149325
        agent:102.immunity = 0.427821 ← T149325
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1355.568456 ← T150317
        region:2.population = 108 ← T150257
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.427821 → 0.427682
    T158049 AgentSystem.agent.health (tick 78)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 15.312727 ← T156119
      agent:102.hunger = 0.0 ← T157053
      agent:102.infected = false ← T154164
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
      T154164 ImmuneDiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T151264
        agent:102.immune_memory = 0.7 ← T127065
        agent:102.immunity = 0.427682 ← T151264
        agent:102.infected = true ← T127065
      Random:
        disease.recovery@agent:102 = 0.244162 threshold=0.26692
      Writes:
        agent:102.infected: true → false
      T156119 AgentSystem.agent.health (tick 77)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 13.812727 ← T154191
        agent:102.hunger = 0.0 ← T155125
        agent:102.infected = false ← T154164
      Writes:
        agent:102.health: 13.812727 → 15.312727
      T157053 AgentSystem.agent.metabolism (tick 77)
      Inputs:
        agent:102.hunger = 0.0 ← T155125
        agent:102.immunity = 0.427406 ← T155125
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1273.455074 ← T156106
        region:2.population = 108 ← T156058
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.427406 → 0.427269
    … 2 more parent(s)
  T165757 AgentSystem.agent.health (tick 82)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 3.523145 ← T163824
    agent:102.hunger = 0.0 ← T164758
    agent:102.infected = true ← T161865
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
    T161865 ImmuneDiseaseSystem.disease.infect (tick 79)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 16.812727 ← T158049
      agent:102.hunger = 0.0 ← T158983
      agent:102.immune_memory = 0.7 ← T127065
      agent:102.immunity = 0.427132 ← T158983
      agent:102.infected = false ← T154164
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.206458 ← T159935
    Random:
      disease.infection@agent:102 = 0.00308 threshold=0.014449
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
      T127065 ImmuneDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T123236
        agent:102.hunger = 0.0 ← T124147
        agent:102.immune_memory = 0.35 ← T78577
        agent:102.immunity = 0.429694 ← T124147
        agent:102.infected = false ← T115299
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.268315 ← T125118
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.03247
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T154164 ImmuneDiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T151264
        agent:102.immune_memory = 0.7 ← T127065
        agent:102.immunity = 0.427682 ← T151264
        agent:102.infected = true ← T127065
      Random:
        disease.recovery@agent:102 = 0.244162 threshold=0.26692
      Writes:
        agent:102.infected: true → false
      T158049 AgentSystem.agent.health (tick 78)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 15.312727 ← T156119
        agent:102.hunger = 0.0 ← T157053
        agent:102.infected = false ← T154164
      Writes:
        agent:102.health: 15.312727 → 16.812727
      … 2 more parent(s)
    T163824 AgentSystem.agent.health (tick 81)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 6.023145 ← T161899
      agent:102.hunger = 0.0 ← T162833
      agent:102.infected = true ← T161865
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
      T161865 ImmuneDiseaseSystem.disease.infect (tick 79)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 16.812727 ← T158049
        agent:102.hunger = 0.0 ← T158983
        agent:102.immune_memory = 0.7 ← T127065
        agent:102.immunity = 0.427132 ← T158983
        agent:102.infected = false ← T154164
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.206458 ← T159935
      Random:
        disease.infection@agent:102 = 0.00308 threshold=0.014449
        disease.infection@agent:102 = 0.829238
      Writes:
        agent:102.health: 16.812727 → 8.523145
        agent:102.immune_memory: 0.7 → 1.0
        agent:102.infected: false → true
      T161899 AgentSystem.agent.health (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 8.523145 ← T161865
        agent:102.hunger = 0.0 ← T160905
        agent:102.infected = true ← T161865
      Writes:
        agent:102.health: 8.523145 → 6.023145
      T162833 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T160905
        agent:102.immunity = 0.426997 ← T160905
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1165.460279 ← T161886
        region:2.population = 108 ← T161837
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
    T164758 AgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T162833
      agent:102.immunity = 0.426862 ← T162833
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1167.926268 ← T163811
      region:2.population = 108 ← T163765
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
      T162833 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T160905
        agent:102.immunity = 0.426997 ← T160905
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1165.460279 ← T161886
        region:2.population = 108 ← T161837
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
      T163765 AgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 220 more input(s)
      Writes:
        region:2.population: 108 → 108
        region:2.workers: 108 → 108
      T163811 RotationAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1165.460279 ← T161886
        region:2.labor_ema = 108.654188 ← T161886
        region:2.labor_ema2 = 11811.431718 ← T161886
        region:2.population = 108 ← T161837
        region:2.rainfall = 0.577858 ← T161847
        region:2.soil_fertility = 0.411214 ← T161886
        region:2.temperature = 18.934401 ← T161847
        region:2.workers = 108 ← T161837
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1165.460279 → 1167.926268
        region:2.labor_ema: 108.654188 → 108.588769
        region:2.labor_ema2: 11811.431718 → 11796.688546
        region:2.soil_fertility: 0.411214 → 0.410173
  T166691 AgentSystem.agent.metabolism (tick 82)
  Inputs:
    agent:102.hunger = 0.0 ← T164758
    agent:102.immunity = 0.426727 ← T164758
    agent:102.region = region:2 ← T6
    region:2.food_stock = 1124.509213 ← T165744
    region:2.population = 108 ← T165690
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
    T164758 AgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T162833
      agent:102.immunity = 0.426862 ← T162833
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1167.926268 ← T163811
      region:2.population = 108 ← T163765
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
      T162833 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T160905
        agent:102.immunity = 0.426997 ← T160905
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1165.460279 ← T161886
        region:2.population = 108 ← T161837
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
      T163765 AgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 220 more input(s)
      Writes:
        region:2.population: 108 → 108
        region:2.workers: 108 → 108
      T163811 RotationAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1165.460279 ← T161886
        region:2.labor_ema = 108.654188 ← T161886
        region:2.labor_ema2 = 11811.431718 ← T161886
        region:2.population = 108 ← T161837
        region:2.rainfall = 0.577858 ← T161847
        region:2.soil_fertility = 0.411214 ← T161886
        region:2.temperature = 18.934401 ← T161847
        region:2.workers = 108 ← T161837
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1165.460279 → 1167.926268
        region:2.labor_ema: 108.654188 → 108.588769
        region:2.labor_ema2: 11811.431718 → 11796.688546
        region:2.soil_fertility: 0.411214 → 0.410173
    T165690 AgentSystem.agents.census (tick 81)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.region = region:2 ← T6
      agent:112.alive = true ← T17
      agent:112.region = region:2 ← T17
      agent:12.alive = true ← T25
      agent:12.region = region:2 ← T25
      agent:122.alive = true ← T28
      agent:122.region = region:2 ← T28
      … 220 more input(s)
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
      … 124 more parent(s)
    T165744 RotationAgricultureSystem.agriculture.harvest (tick 81)
    Inputs:
      region:2.food_stock = 1167.926268 ← T163811
      region:2.labor_ema = 108.588769 ← T163811
      region:2.labor_ema2 = 11796.688546 ← T163811
      region:2.population = 108 ← T163765
      region:2.rainfall = 0.568902 ← T163775
      region:2.soil_fertility = 0.410173 ← T163811
      region:2.temperature = 19.003536 ← T163775
      region:2.workers = 108 ← T163765
    Random:
      agriculture.crop_variance@region:2 = 0.024179
    Writes:
      region:2.food_stock: 1167.926268 → 1124.509213
      region:2.labor_ema: 108.588769 → 108.529892
      region:2.labor_ema2: 11796.688546 → 11783.419691
      region:2.soil_fertility: 0.410173 → 0.409132
      T163765 AgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 220 more input(s)
      Writes:
        region:2.population: 108 → 108
        region:2.workers: 108 → 108
      T163775 ClimateSystem.climate.step (tick 80)
      Inputs:
        region:2.climate_volatility = 0.508114 ← T1003
        region:2.rainfall = 0.577858 ← T161847
        region:2.rainfall_base = 0.553388 ← T1003
        region:2.temperature = 18.934401 ← T161847
        region:2.temperature_base = 18.487763 ← T1003
      Random:
        climate.temperature_noise@region:2 = 0.642326
        climate.rain@region:2 = 0.466151
      Writes:
        region:2.rainfall: 0.577858 → 0.568902
        region:2.temperature: 18.934401 → 19.003536
      T163811 RotationAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1165.460279 ← T161886
        region:2.labor_ema = 108.654188 ← T161886
        region:2.labor_ema2 = 11811.431718 ← T161886
        region:2.population = 108 ← T161837
        region:2.rainfall = 0.577858 ← T161847
        region:2.soil_fertility = 0.411214 ← T161886
        region:2.temperature = 18.934401 ← T161847
        region:2.workers = 108 ← T161837
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1165.460279 → 1167.926268
        region:2.labor_ema: 108.654188 → 108.588769
        region:2.labor_ema2: 11811.431718 → 11796.688546
        region:2.soil_fertility: 0.411214 → 0.410173
```

### agent:131 — acute_infection (died tick 51, T107210)

```
T107210 ImmuneDiseaseSystem.disease.infect (tick 51)
Inputs:
  agent:131.alive = true ← T38
  agent:131.health = 1.48163 ← T95105
  agent:131.hunger = 0.61 ← T104192
  agent:131.immune_memory = 0.7 ← T66226
  agent:131.immunity = 0.156634 ← T104192
  agent:131.infected = false ← T80712
  agent:131.region = region:4 ← T101053
  region:4.disease_load = 0.396099 ← T105182
Random:
  disease.infection@agent:131 = 0.049286 threshold=0.0914
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
  T66226 ImmuneDiseaseSystem.disease.infect (tick 31)
  Inputs:
    agent:131.alive = true ← T38
    agent:131.health = 55.529529 ← T54305
    agent:131.hunger = 0.576015 ← T63236
    agent:131.immune_memory = 0.35 ← T4194
    agent:131.immunity = 0.301417 ← T63236
    agent:131.infected = false ← T26708
    agent:131.region = region:1 ← T38
    region:1.disease_load = 0.415123 ← T64219
  Random:
    disease.infection@agent:131 = 0.127706 threshold=0.139357
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
    T4194 ImmuneDiseaseSystem.disease.infect (tick 1)
    Inputs:
      agent:131.alive = true ← T38
      agent:131.health = 73.062638 ← T38
      agent:131.hunger = 0.321342 ← T1536
      agent:131.immune_memory = 0.0 ← T38
      agent:131.immunity = 0.332089 ← T1536
      agent:131.infected = false ← T38
      agent:131.region = region:1 ← T38
      region:1.disease_load = 0.120789 ← T2520
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
      T1536 AgentSystem.agent.metabolism (tick 0)
      Inputs:
        agent:131.hunger = 0.351342 ← T38
        agent:131.immunity = 0.334978 ← T38
        agent:131.region = region:1 ← T38
        region:1.food_stock = 1614.504597 ← T1002
        region:1.population = 100 ← T1002
      Writes:
        agent:131.hunger: 0.351342 → 0.321342
        agent:131.immunity: 0.334978 → 0.332089
      T2520 ImmuneDiseaseSystem.disease.environment (tick 0)
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
    T26708 ImmuneDiseaseSystem.disease.recover (tick 12)
    Inputs:
      agent:131.alive = true ← T38
      agent:131.hunger = 0.0 ← T23563
      agent:131.immune_memory = 0.35 ← T4194
      agent:131.immunity = 0.320642 ← T23563
      agent:131.infected = true ← T4194
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
      T4194 ImmuneDiseaseSystem.disease.infect (tick 1)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.health = 73.062638 ← T38
        agent:131.hunger = 0.321342 ← T1536
        agent:131.immune_memory = 0.0 ← T38
        agent:131.immunity = 0.332089 ← T1536
        agent:131.infected = false ← T38
        agent:131.region = region:1 ← T38
        region:1.disease_load = 0.120789 ← T2520
      Random:
        disease.infection@agent:131 = 0.014122 threshold=0.041454
        disease.infection@agent:131 = 0.503311
      Writes:
        agent:131.health: 73.062638 → 62.029529
        agent:131.immune_memory: 0.0 → 0.35
        agent:131.infected: false → true
      T23563 AgentSystem.agent.metabolism (tick 11)
      Inputs:
        agent:131.hunger = 0.021342 ← T21456
        agent:131.immunity = 0.320244 ← T21456
        agent:131.region = region:1 ← T38
        region:1.food_stock = 730.332503 ← T22517
        region:1.population = 100 ← T22420
      Writes:
        agent:131.hunger: 0.021342 → 0.0
        agent:131.immunity: 0.320244 → 0.320642
    T54305 AgentSystem.agent.health (tick 26)
    Inputs:
      agent:131.alive = true ← T38
      agent:131.health = 54.029529 ← T52175
      agent:131.hunger = 0.226015 ← T53175
      agent:131.infected = false ← T26708
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
      T26708 ImmuneDiseaseSystem.disease.recover (tick 12)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.hunger = 0.0 ← T23563
        agent:131.immune_memory = 0.35 ← T4194
        agent:131.immunity = 0.320642 ← T23563
        agent:131.infected = true ← T4194
      Random:
        disease.recovery@agent:131 = 0.126841 threshold=0.170161
      Writes:
        agent:131.infected: true → false
      T52175 AgentSystem.agent.health (tick 25)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.health = 52.529529 ← T50050
        agent:131.hunger = 0.156015 ← T51050
        agent:131.infected = false ← T26708
      Writes:
        agent:131.health: 52.529529 → 54.029529
      T53175 AgentSystem.agent.metabolism (tick 25)
      Inputs:
        agent:131.hunger = 0.156015 ← T51050
        agent:131.immunity = 0.322957 ← T51050
        agent:131.region = region:1 ← T38
        region:1.food_stock = 0.0 ← T52129
        region:1.population = 100 ← T52014
      Writes:
        agent:131.hunger: 0.156015 → 0.226015
        agent:131.immunity: 0.322957 → 0.321082
    … 2 more parent(s)
  T80712 ImmuneDiseaseSystem.disease.recover (tick 38)
  Inputs:
    agent:131.alive = true ← T38
    agent:131.hunger = 1.0 ← T77545
    agent:131.immune_memory = 0.7 ← T66226
    agent:131.immunity = 0.24635 ← T77545
    agent:131.infected = true ← T66226
  Random:
    disease.recovery@agent:131 = 0.062477 threshold=0.071587
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
    T66226 ImmuneDiseaseSystem.disease.infect (tick 31)
    Inputs:
      agent:131.alive = true ← T38
      agent:131.health = 55.529529 ← T54305
      agent:131.hunger = 0.576015 ← T63236
      agent:131.immune_memory = 0.35 ← T4194
      agent:131.immunity = 0.301417 ← T63236
      agent:131.infected = false ← T26708
      agent:131.region = region:1 ← T38
      region:1.disease_load = 0.415123 ← T64219
    Random:
      disease.infection@agent:131 = 0.127706 threshold=0.139357
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
      T4194 ImmuneDiseaseSystem.disease.infect (tick 1)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.health = 73.062638 ← T38
        agent:131.hunger = 0.321342 ← T1536
        agent:131.immune_memory = 0.0 ← T38
        agent:131.immunity = 0.332089 ← T1536
        agent:131.infected = false ← T38
        agent:131.region = region:1 ← T38
        region:1.disease_load = 0.120789 ← T2520
      Random:
        disease.infection@agent:131 = 0.014122 threshold=0.041454
        disease.infection@agent:131 = 0.503311
      Writes:
        agent:131.health: 73.062638 → 62.029529
        agent:131.immune_memory: 0.0 → 0.35
        agent:131.infected: false → true
      T26708 ImmuneDiseaseSystem.disease.recover (tick 12)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.hunger = 0.0 ← T23563
        agent:131.immune_memory = 0.35 ← T4194
        agent:131.immunity = 0.320642 ← T23563
        agent:131.infected = true ← T4194
      Random:
        disease.recovery@agent:131 = 0.126841 threshold=0.170161
      Writes:
        agent:131.infected: true → false
      T54305 AgentSystem.agent.health (tick 26)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.health = 54.029529 ← T52175
        agent:131.hunger = 0.226015 ← T53175
        agent:131.infected = false ← T26708
      Writes:
        agent:131.health: 54.029529 → 55.529529
      … 2 more parent(s)
    T77545 AgentSystem.agent.metabolism (tick 37)
    Inputs:
      agent:131.hunger = 0.996015 ← T75465
      agent:131.immunity = 0.255628 ← T75465
      agent:131.region = region:1 ← T38
      region:1.food_stock = 0.0 ← T76562
      region:1.population = 33 ← T76458
    Writes:
      agent:131.hunger: 0.996015 → 1.0
      agent:131.immunity: 0.255628 → 0.24635
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
      T75465 AgentSystem.agent.metabolism (tick 36)
      Inputs:
        agent:131.hunger = 0.926015 ← T73373
        agent:131.immunity = 0.264913 ← T73373
        agent:131.region = region:1 ← T38
        region:1.food_stock = 0.0 ← T74486
        region:1.population = 41 ← T74385
      Writes:
        agent:131.hunger: 0.926015 → 0.996015
        agent:131.immunity: 0.264913 → 0.255628
      T76458 AgentSystem.agents.census (tick 36)
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
      T76562 RotationAgricultureSystem.agriculture.harvest (tick 36)
      Inputs:
        region:1.food_stock = 0.0 ← T74486
        region:1.labor_ema = 89.085 ← T74486
        region:1.labor_ema2 = 8289.315 ← T74486
        region:1.population = 41 ← T74385
        region:1.rainfall = 0.439525 ← T74395
        region:1.soil_fertility = 0.492827 ← T74486
        region:1.temperature = 10.235594 ← T74395
        region:1.workers = 41 ← T74385
      Random:
        agriculture.crop_variance@region:1 = 0.880569
      Writes:
        region:1.food_stock: 0.0 → 0.0
        region:1.labor_ema: 89.085 → 84.2765
        region:1.labor_ema2: 8289.315 → 7628.4835
        region:1.soil_fertility: 0.492827 → 0.4919
  T95105 AgentSystem.agent.health (tick 46)
  Inputs:
    agent:131.alive = true ← T38
    agent:131.health = 3.48163 ← T93065
    agent:131.hunger = 0.76 ← T93975
    agent:131.infected = false ← T80712
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
    T80712 ImmuneDiseaseSystem.disease.recover (tick 38)
    Inputs:
      agent:131.alive = true ← T38
      agent:131.hunger = 1.0 ← T77545
      agent:131.immune_memory = 0.7 ← T66226
      agent:131.immunity = 0.24635 ← T77545
      agent:131.infected = true ← T66226
    Random:
      disease.recovery@agent:131 = 0.062477 threshold=0.071587
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
      T66226 ImmuneDiseaseSystem.disease.infect (tick 31)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.health = 55.529529 ← T54305
        agent:131.hunger = 0.576015 ← T63236
        agent:131.immune_memory = 0.35 ← T4194
        agent:131.immunity = 0.301417 ← T63236
        agent:131.infected = false ← T26708
        agent:131.region = region:1 ← T38
        region:1.disease_load = 0.415123 ← T64219
      Random:
        disease.infection@agent:131 = 0.127706 threshold=0.139357
        disease.infection@agent:131 = 0.735177
      Writes:
        agent:131.health: 55.529529 → 44.98163
        agent:131.immune_memory: 0.35 → 0.7
        agent:131.infected: false → true
      T77545 AgentSystem.agent.metabolism (tick 37)
      Inputs:
        agent:131.hunger = 0.996015 ← T75465
        agent:131.immunity = 0.255628 ← T75465
        agent:131.region = region:1 ← T38
        region:1.food_stock = 0.0 ← T76562
        region:1.population = 33 ← T76458
      Writes:
        agent:131.hunger: 0.996015 → 1.0
        agent:131.immunity: 0.255628 → 0.24635
    T93065 AgentSystem.agent.health (tick 45)
    Inputs:
      agent:131.alive = true ← T38
      agent:131.health = 5.48163 ← T91036
      agent:131.hunger = 0.79 ← T91947
      agent:131.infected = false ← T80712
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
      T80712 ImmuneDiseaseSystem.disease.recover (tick 38)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.hunger = 1.0 ← T77545
        agent:131.immune_memory = 0.7 ← T66226
        agent:131.immunity = 0.24635 ← T77545
        agent:131.infected = true ← T66226
      Random:
        disease.recovery@agent:131 = 0.062477 threshold=0.071587
      Writes:
        agent:131.infected: true → false
      T91036 AgentSystem.agent.health (tick 44)
      Inputs:
        agent:131.alive = true ← T38
        agent:131.health = 7.48163 ← T89001
        agent:131.hunger = 0.82 ← T89918
        agent:131.infected = false ← T80712
      Writes:
        agent:131.health: 7.48163 → 5.48163
      T91947 AgentSystem.agent.metabolism (tick 44)
      Inputs:
        agent:131.hunger = 0.82 ← T89918
        agent:131.immunity = 0.197895 ← T89918
        agent:131.region = region:2 ← T78507
        region:2.food_stock = 1442.42784 ← T90994
        region:2.population = 119 ← T90895
      Writes:
        agent:131.hunger: 0.82 → 0.79
        agent:131.immunity: 0.197895 → 0.191005
    T93975 AgentSystem.agent.metabolism (tick 45)
    Inputs:
      agent:131.hunger = 0.79 ← T91947
      agent:131.immunity = 0.191005 ← T91947
      agent:131.region = region:2 ← T78507
      region:2.food_stock = 1398.316049 ← T93024
      region:2.population = 118 ← T92936
    Writes:
      agent:131.hunger: 0.79 → 0.76
      agent:131.immunity: 0.191005 → 0.18445
      T78507 AgentSystem.agent.migrate (tick 37)
      Inputs:
        agent:131.hunger = 0.996015 ← T75465
        agent:131.region = region:1 ← T38
        agent:131.risk_tolerance = 0.439929 ← T38
      Random:
        agent.decision@agent:131 = 0.131854 threshold=0.219965
      Writes:
        agent:131.region: region:1 → region:2
      T91947 AgentSystem.agent.metabolism (tick 44)
      Inputs:
        agent:131.hunger = 0.82 ← T89918
        agent:131.immunity = 0.197895 ← T89918
        agent:131.region = region:2 ← T78507
        region:2.food_stock = 1442.42784 ← T90994
        region:2.population = 119 ← T90895
      Writes:
        agent:131.hunger: 0.82 → 0.79
        agent:131.immunity: 0.197895 → 0.191005
      T92936 AgentSystem.agents.census (tick 44)
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
        region:2.population: 119 → 118
        region:2.workers: 119 → 118
      T93024 RotationAgricultureSystem.agriculture.harvest (tick 44)
      Inputs:
        region:2.food_stock = 1442.42784 ← T90994
        region:2.labor_ema = 115.117584 ← T90994
        region:2.labor_ema2 = 13370.486588 ← T90994
        region:2.population = 119 ← T90895
        region:2.rainfall = 0.471985 ← T90905
        region:2.soil_fertility = 0.448239 ← T90994
        region:2.temperature = 19.301551 ← T90905
        region:2.workers = 119 ← T90895
      Random:
        agriculture.crop_variance@region:2 = 0.336574
      Writes:
        region:2.food_stock: 1442.42784 → 1398.316049
        region:2.labor_ema: 115.117584 → 115.505826
        region:2.labor_ema2: 13370.486588 → 13449.537929
        region:2.soil_fertility: 0.448239 → 0.44723
  … 3 more parent(s)
```

## Reproduction

```bash
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset crop_rotation --db runs/survival_seed7_rotation.db --report <path>
```

Same seed + kernel v0.1.0 + ruleset 0.3.2f → bit-identical world, identical traces, identical report.