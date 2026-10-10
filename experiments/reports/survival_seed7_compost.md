# Causal survival experiment — seed 7

Kernel **v0.1 (frozen)**, ruleset **0.3.3g** — the laws
differ from the baseline by proposal only; the kernel, the purposes
and the addressable draw stream are unchanged.

> Experiment G (compost): every agent returns nutrients to its region's soil; balance point ≈ soil 0.5 at genesis density.

## Run

| parameter | value |
|---|---|
| seed | 7 |
| ruleset | 0.3.3g |
| regions | 10 |
| agents | 1000 |
| ticks | 10000 |
| wall time | 2325s |
| archive | `runs/survival_seed7_compost.db` |
| survivors | 937 / 1000 |
| deaths | 63 |
| last death | tick 1531 |

## Lifespan distribution (survivors censored at run end)

| pct | ticks |
|---|---|
| p0 | 28 |
| p10 | 10000 |
| p25 | 10000 |
| p50 | 10000 |
| p75 | 10000 |
| p90 | 10000 |
| p100 | 10000 |

mean lifespan: **9388** ticks

## Statistical regularity: correlations with lifespan

| observable | pearson | spearman |
|---|---|---|
| initial_health | +0.052 | +0.049 |
| initial_immunity | +0.068 | +0.070 |
| risk_tolerance | +0.187 | +0.188 |
| migration_count | -0.103 | -0.186 |
| infection_count | +0.705 | +0.421 |
| avg_food_access | +0.288 | +0.400 |
| avg_social_density | +0.603 | +0.410 |

## Individual causality: death mechanisms (from traces)

| mechanism | deaths | share |
|---|---|---|
| disease+starvation | 51 | 81.0% |
| disease | 9 | 14.3% |
| acute_infection | 3 | 4.8% |

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
| stayers (0 migrations) | 720 | 9692 | 2 | 5 | 16 |
| migrants (>=1 migration) | 280 | 8605 | 1 | 4 | 35 |

### Risk tolerance quartiles

| group | n | mean lifespan | acute_infection | disease | disease+starvation |
|---|---|---|---|---|---|
| risk Q1 (lowest) | 250 | 8655 | 2 | 2 | 31 |
| risk Q2 | 250 | 9489 | 0 | 1 | 12 |
| risk Q3 | 250 | 9568 | 1 | 3 | 7 |
| risk Q4 (highest) | 250 | 9841 | 0 | 3 | 1 |

## Example mechanical explanations

### agent:102 — disease (died tick 83, T168433)

```
T168433 AgentSystem.agent.death (tick 83)
Inputs:
  agent:102.alive = true ← T6
  agent:102.health = 1.023145 ← T166478
  agent:102.hunger = 0.0 ← T167426
  agent:102.infected = true ← T162536
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
  T162536 ImmuneDiseaseSystem.disease.infect (tick 79)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 16.812727 ← T158653
    agent:102.hunger = 0.0 ← T159600
    agent:102.immune_memory = 0.7 ← T127183
    agent:102.immunity = 0.427132 ← T159600
    agent:102.infected = false ← T154720
    agent:102.region = region:2 ← T6
    region:2.disease_load = 0.203751 ← T160577
  Random:
    disease.infection@agent:102 = 0.00308 threshold=0.01426
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
    T127183 ImmuneDiseaseSystem.disease.infect (tick 61)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 55.187459 ← T123276
      agent:102.hunger = 0.0 ← T124203
      agent:102.immune_memory = 0.35 ← T78543
      agent:102.immunity = 0.429694 ← T124203
      agent:102.infected = false ← T115269
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.262153 ← T125199
    Random:
      disease.infection@agent:102 = 0.019219 threshold=0.031725
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
      T78543 ImmuneDiseaseSystem.disease.infect (tick 37)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 100.0 ← T74457
        agent:102.hunger = 0.0 ← T75394
        agent:102.immune_memory = 0.0 ← T6
        agent:102.immunity = 0.43349 ← T75394
        agent:102.infected = false ← T6
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.307879 ← T76456
      Random:
        disease.infection@agent:102 = 0.011169 threshold=0.052791
        disease.infection@agent:102 = 0.131254
      Writes:
        agent:102.health: 100.0 → 92.687459
        agent:102.immune_memory: 0.0 → 0.35
        agent:102.infected: false → true
      T115269 ImmuneDiseaseSystem.disease.recover (tick 55)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T112204
        agent:102.immune_memory = 0.35 ← T78543
        agent:102.immunity = 0.430601 ← T112204
        agent:102.infected = true ← T78543
      Random:
        disease.recovery@agent:102 = 0.118911 threshold=0.19765
      Writes:
        agent:102.infected: true → false
      T123276 AgentSystem.agent.health (tick 60)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 53.687459 ← T121292
        agent:102.hunger = 0.0 ← T122219
        agent:102.infected = false ← T115269
      Writes:
        agent:102.health: 53.687459 → 55.187459
      … 2 more parent(s)
    T154720 ImmuneDiseaseSystem.disease.recover (tick 75)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.hunger = 0.0 ← T151768
      agent:102.immune_memory = 0.7 ← T127183
      agent:102.immunity = 0.427682 ← T151768
      agent:102.infected = true ← T127183
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
      T127183 ImmuneDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T123276
        agent:102.hunger = 0.0 ← T124203
        agent:102.immune_memory = 0.35 ← T78543
        agent:102.immunity = 0.429694 ← T124203
        agent:102.infected = false ← T115269
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.262153 ← T125199
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.031725
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T151768 AgentSystem.agent.metabolism (tick 74)
      Inputs:
        agent:102.hunger = 0.0 ← T149801
        agent:102.immunity = 0.427821 ← T149801
        agent:102.region = region:2 ← T6
        region:2.food_stock = 2017.443906 ← T150768
        region:2.population = 109 ← T150748
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.427821 → 0.427682
    T158653 AgentSystem.agent.health (tick 78)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 15.312727 ← T156695
      agent:102.hunger = 0.0 ← T157642
      agent:102.infected = false ← T154720
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
      T154720 ImmuneDiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T151768
        agent:102.immune_memory = 0.7 ← T127183
        agent:102.immunity = 0.427682 ← T151768
        agent:102.infected = true ← T127183
      Random:
        disease.recovery@agent:102 = 0.244162 threshold=0.26692
      Writes:
        agent:102.infected: true → false
      T156695 AgentSystem.agent.health (tick 77)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 13.812727 ← T154737
        agent:102.hunger = 0.0 ← T155684
        agent:102.infected = false ← T154720
      Writes:
        agent:102.health: 13.812727 → 15.312727
      T157642 AgentSystem.agent.metabolism (tick 77)
      Inputs:
        agent:102.hunger = 0.0 ← T155684
        agent:102.immunity = 0.427406 ← T155684
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1966.980687 ← T156652
        region:2.population = 109 ← T156632
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.427406 → 0.427269
    … 2 more parent(s)
  T166478 AgentSystem.agent.health (tick 82)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 3.523145 ← T164515
    agent:102.hunger = 0.0 ← T165463
    agent:102.infected = true ← T162536
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
    T162536 ImmuneDiseaseSystem.disease.infect (tick 79)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 16.812727 ← T158653
      agent:102.hunger = 0.0 ← T159600
      agent:102.immune_memory = 0.7 ← T127183
      agent:102.immunity = 0.427132 ← T159600
      agent:102.infected = false ← T154720
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.203751 ← T160577
    Random:
      disease.infection@agent:102 = 0.00308 threshold=0.01426
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
      T127183 ImmuneDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T123276
        agent:102.hunger = 0.0 ← T124203
        agent:102.immune_memory = 0.35 ← T78543
        agent:102.immunity = 0.429694 ← T124203
        agent:102.infected = false ← T115269
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.262153 ← T125199
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.031725
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T154720 ImmuneDiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T151768
        agent:102.immune_memory = 0.7 ← T127183
        agent:102.immunity = 0.427682 ← T151768
        agent:102.infected = true ← T127183
      Random:
        disease.recovery@agent:102 = 0.244162 threshold=0.26692
      Writes:
        agent:102.infected: true → false
      T158653 AgentSystem.agent.health (tick 78)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 15.312727 ← T156695
        agent:102.hunger = 0.0 ← T157642
        agent:102.infected = false ← T154720
      Writes:
        agent:102.health: 15.312727 → 16.812727
      … 2 more parent(s)
    T164515 AgentSystem.agent.health (tick 81)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 6.023145 ← T162561
      agent:102.hunger = 0.0 ← T163509
      agent:102.infected = true ← T162536
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
      T162536 ImmuneDiseaseSystem.disease.infect (tick 79)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 16.812727 ← T158653
        agent:102.hunger = 0.0 ← T159600
        agent:102.immune_memory = 0.7 ← T127183
        agent:102.immunity = 0.427132 ← T159600
        agent:102.infected = false ← T154720
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.203751 ← T160577
      Random:
        disease.infection@agent:102 = 0.00308 threshold=0.01426
        disease.infection@agent:102 = 0.829238
      Writes:
        agent:102.health: 16.812727 → 8.523145
        agent:102.immune_memory: 0.7 → 1.0
        agent:102.infected: false → true
      T162561 AgentSystem.agent.health (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 8.523145 ← T162536
        agent:102.hunger = 0.0 ← T161552
        agent:102.infected = true ← T162536
      Writes:
        agent:102.health: 8.523145 → 6.023145
      T163509 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161552
        agent:102.immunity = 0.426997 ← T161552
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1885.191095 ← T162518
        region:2.population = 109 ← T162498
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
    T165463 AgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T163509
      agent:102.immunity = 0.426862 ← T163509
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1905.23379 ← T164476
      region:2.population = 109 ← T164456
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
      T163509 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161552
        agent:102.immunity = 0.426997 ← T161552
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1885.191095 ← T162518
        region:2.population = 109 ← T162498
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
      T164456 AgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:11.alive = true ← T14
        agent:11.region = region:2 ← T68252
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        … 226 more input(s)
      Writes:
        region:2.population: 109 → 109
        region:2.workers: 109 → 109
      T164476 CompostAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1885.191095 ← T162518
        region:2.population = 109 ← T162498
        region:2.rainfall = 0.577858 ← T162508
        region:2.soil_fertility = 0.500643 ← T162518
        region:2.temperature = 18.934401 ← T162508
        region:2.workers = 109 ← T162498
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1885.191095 → 1905.23379
        region:2.soil_fertility: 0.500643 → 0.500722
  T167426 AgentSystem.agent.metabolism (tick 82)
  Inputs:
    agent:102.hunger = 0.0 ← T165463
    agent:102.immunity = 0.426727 ← T165463
    agent:102.region = region:2 ← T6
    region:2.food_stock = 1868.884698 ← T166429
    region:2.population = 110 ← T166409
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
    T165463 AgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T163509
      agent:102.immunity = 0.426862 ← T163509
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1905.23379 ← T164476
      region:2.population = 109 ← T164456
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
      T163509 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161552
        agent:102.immunity = 0.426997 ← T161552
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1885.191095 ← T162518
        region:2.population = 109 ← T162498
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
      T164456 AgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:11.alive = true ← T14
        agent:11.region = region:2 ← T68252
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        … 226 more input(s)
      Writes:
        region:2.population: 109 → 109
        region:2.workers: 109 → 109
      T164476 CompostAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1885.191095 ← T162518
        region:2.population = 109 ← T162498
        region:2.rainfall = 0.577858 ← T162508
        region:2.soil_fertility = 0.500643 ← T162518
        region:2.temperature = 18.934401 ← T162508
        region:2.workers = 109 ← T162498
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1885.191095 → 1905.23379
        region:2.soil_fertility: 0.500643 → 0.500722
    T166409 AgentSystem.agents.census (tick 81)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.region = region:2 ← T6
      agent:11.alive = true ← T14
      agent:11.region = region:2 ← T68252
      agent:112.alive = true ← T17
      agent:112.region = region:2 ← T17
      agent:12.alive = true ← T25
      agent:12.region = region:2 ← T25
      … 228 more input(s)
    Writes:
      region:2.population: 109 → 110
      region:2.workers: 109 → 110
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
      … 132 more parent(s)
    T166429 CompostAgricultureSystem.agriculture.harvest (tick 81)
    Inputs:
      region:2.food_stock = 1905.23379 ← T164476
      region:2.population = 109 ← T164456
      region:2.rainfall = 0.568902 ← T164466
      region:2.soil_fertility = 0.500722 ← T164476
      region:2.temperature = 19.003536 ← T164466
      region:2.workers = 109 ← T164456
    Random:
      agriculture.crop_variance@region:2 = 0.024179
    Writes:
      region:2.food_stock: 1905.23379 → 1868.884698
      region:2.soil_fertility: 0.500722 → 0.500802
      T164456 AgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:11.alive = true ← T14
        agent:11.region = region:2 ← T68252
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        … 226 more input(s)
      Writes:
        region:2.population: 109 → 109
        region:2.workers: 109 → 109
      T164466 ClimateSystem.climate.step (tick 80)
      Inputs:
        region:2.climate_volatility = 0.508114 ← T1003
        region:2.rainfall = 0.577858 ← T162508
        region:2.rainfall_base = 0.553388 ← T1003
        region:2.temperature = 18.934401 ← T162508
        region:2.temperature_base = 18.487763 ← T1003
      Random:
        climate.temperature_noise@region:2 = 0.642326
        climate.rain@region:2 = 0.466151
      Writes:
        region:2.rainfall: 0.577858 → 0.568902
        region:2.temperature: 18.934401 → 19.003536
      T164476 CompostAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1885.191095 ← T162518
        region:2.population = 109 ← T162498
        region:2.rainfall = 0.577858 ← T162508
        region:2.soil_fertility = 0.500643 ← T162518
        region:2.temperature = 18.934401 ← T162508
        region:2.workers = 109 ← T162498
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1885.191095 → 1905.23379
        region:2.soil_fertility: 0.500643 → 0.500722
```

### agent:393 — acute_infection (died tick 1519, T2957481)

```
T2957481 ImmuneDiseaseSystem.disease.infect (tick 1519)
Inputs:
  agent:393.alive = true ← T328
  agent:393.health = 1.627381 ← T2953942
  agent:393.hunger = 1.0 ← T2954880
  agent:393.immune_memory = 1.0 ← T2943980
  agent:393.immunity = 0.0 ← T2954880
  agent:393.infected = false ← T2951706
  agent:393.region = region:3 ← T328
  region:3.disease_load = 0.403679 ← T2955546
Random:
  disease.infection@agent:393 = 0.00871 threshold=0.054497
  disease.infection@agent:393 = 0.801835
Writes:
  agent:393.alive: true → false
  agent:393.health: 1.627381 → 0.0
  agent:393.immune_memory: 1.0 → 1.0
  agent:393.infected: false → true
  T328 GenesisSystem.genesis.agent (tick 0)
  Random:
    genesis.attribute@agent:393 = 0.476931
    genesis.attribute@agent:393 = 0.229352
    genesis.attribute@agent:393 = 0.572215
    genesis.attribute@agent:393 = 0.130878
  Writes:
    agent:393.alive: none → true
    agent:393.health: none → 79.307936
    agent:393.hunger: none → 0.168806
    agent:393.immune_memory: none → 0.0
    agent:393.immunity: none → 0.564718
    agent:393.infected: none → false
    agent:393.region: none → region:3
    agent:393.risk_tolerance: none → 0.130878
  T2943980 ImmuneDiseaseSystem.disease.infect (tick 1512)
  Inputs:
    agent:393.alive = true ← T328
    agent:393.health = 29.205083 ← T2940434
    agent:393.hunger = 1.0 ← T2941374
    agent:393.immune_memory = 1.0 ← T2926573
    agent:393.immunity = 0.0 ← T2941374
    agent:393.infected = false ← T2932392
    agent:393.region = region:3 ← T328
    region:3.disease_load = 0.436864 ← T2942042
  Random:
    disease.infection@agent:393 = 0.011655 threshold=0.058977
    disease.infection@agent:393 = 0.794426
  Writes:
    agent:393.health: 29.205083 → 23.627381
    agent:393.immune_memory: 1.0 → 1.0
    agent:393.infected: false → true
    T328 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:393 = 0.476931
      genesis.attribute@agent:393 = 0.229352
      genesis.attribute@agent:393 = 0.572215
      genesis.attribute@agent:393 = 0.130878
    Writes:
      agent:393.alive: none → true
      agent:393.health: none → 79.307936
      agent:393.hunger: none → 0.168806
      agent:393.immune_memory: none → 0.0
      agent:393.immunity: none → 0.564718
      agent:393.infected: none → false
      agent:393.region: none → region:3
      agent:393.risk_tolerance: none → 0.130878
    T2926573 ImmuneDiseaseSystem.disease.infect (tick 1503)
    Inputs:
      agent:393.alive = true ← T328
      agent:393.health = 58.0 ← T2923012
      agent:393.hunger = 1.0 ← T2923956
      agent:393.immune_memory = 1.0 ← T2632162
      agent:393.immunity = 0.067763 ← T2923956
      agent:393.infected = false ← T2634001
      agent:393.region = region:3 ← T328
      region:3.disease_load = 0.455571 ← T2924625
    Random:
      disease.infection@agent:393 = 0.026203 threshold=0.058168
      disease.infection@agent:393 = 0.723729
    Writes:
      agent:393.health: 58.0 → 52.705083
      agent:393.immune_memory: 1.0 → 1.0
      agent:393.infected: false → true
      T328 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:393 = 0.476931
        genesis.attribute@agent:393 = 0.229352
        genesis.attribute@agent:393 = 0.572215
        genesis.attribute@agent:393 = 0.130878
      Writes:
        agent:393.alive: none → true
        agent:393.health: none → 79.307936
        agent:393.hunger: none → 0.168806
        agent:393.immune_memory: none → 0.0
        agent:393.immunity: none → 0.564718
        agent:393.infected: none → false
        agent:393.region: none → region:3
        agent:393.risk_tolerance: none → 0.130878
      T2632162 ImmuneDiseaseSystem.disease.infect (tick 1350)
      Inputs:
        agent:393.alive = true ← T328
        agent:393.health = 100.0 ← T2615890
        agent:393.hunger = 0.331674 ← T2629648
        agent:393.immune_memory = 1.0 ← T2355212
        agent:393.immunity = 0.36887 ← T2629648
        agent:393.infected = false ← T2359105
        agent:393.region = region:3 ← T328
        region:3.disease_load = 0.277047 ← T2630317
      Random:
        disease.infection@agent:393 = 0.005188 threshold=0.013884
        disease.infection@agent:393 = 0.429991
      Writes:
        agent:393.health: 100.0 → 95.880035
        agent:393.immune_memory: 1.0 → 1.0
        agent:393.infected: false → true
      T2634001 ImmuneDiseaseSystem.disease.recover (tick 1351)
      Inputs:
        agent:393.alive = true ← T328
        agent:393.hunger = 0.344875 ← T2631486
        agent:393.immune_memory = 1.0 ← T2632162
        agent:393.immunity = 0.365577 ← T2631486
        agent:393.infected = true ← T2632162
      Random:
        disease.recovery@agent:393 = 0.11028 threshold=0.259663
      Writes:
        agent:393.infected: true → false
      T2923012 AgentSystem.agent.health (tick 1502)
      Inputs:
        agent:393.alive = true ← T328
        agent:393.health = 60.0 ← T2921077
        agent:393.hunger = 1.0 ← T2922021
        agent:393.infected = false ← T2634001
      Writes:
        agent:393.health: 60.0 → 58.0
      … 2 more parent(s)
    T2932392 ImmuneDiseaseSystem.disease.recover (tick 1506)
    Inputs:
      agent:393.alive = true ← T328
      agent:393.hunger = 1.0 ← T2929771
      agent:393.immune_memory = 1.0 ← T2926573
      agent:393.immunity = 0.042871 ← T2929771
      agent:393.infected = true ← T2926573
    Random:
      disease.recovery@agent:393 = 0.077267 threshold=0.080718
    Writes:
      agent:393.infected: true → false
      T328 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:393 = 0.476931
        genesis.attribute@agent:393 = 0.229352
        genesis.attribute@agent:393 = 0.572215
        genesis.attribute@agent:393 = 0.130878
      Writes:
        agent:393.alive: none → true
        agent:393.health: none → 79.307936
        agent:393.hunger: none → 0.168806
        agent:393.immune_memory: none → 0.0
        agent:393.immunity: none → 0.564718
        agent:393.infected: none → false
        agent:393.region: none → region:3
        agent:393.risk_tolerance: none → 0.130878
      T2926573 ImmuneDiseaseSystem.disease.infect (tick 1503)
      Inputs:
        agent:393.alive = true ← T328
        agent:393.health = 58.0 ← T2923012
        agent:393.hunger = 1.0 ← T2923956
        agent:393.immune_memory = 1.0 ← T2632162
        agent:393.immunity = 0.067763 ← T2923956
        agent:393.infected = false ← T2634001
        agent:393.region = region:3 ← T328
        region:3.disease_load = 0.455571 ← T2924625
      Random:
        disease.infection@agent:393 = 0.026203 threshold=0.058168
        disease.infection@agent:393 = 0.723729
      Writes:
        agent:393.health: 58.0 → 52.705083
        agent:393.immune_memory: 1.0 → 1.0
        agent:393.infected: false → true
      T2929771 AgentSystem.agent.metabolism (tick 1505)
      Inputs:
        agent:393.hunger = 1.0 ← T2927837
        agent:393.immunity = 0.051127 ← T2927837
        agent:393.region = region:3 ← T328
        region:3.food_stock = 2.639763 ← T2928497
        region:3.population = 6 ← T2928477
      Writes:
        agent:393.hunger: 1.0 → 1.0
        agent:393.immunity: 0.051127 → 0.042871
    T2940434 AgentSystem.agent.health (tick 1511)
    Inputs:
      agent:393.alive = true ← T328
      agent:393.health = 31.205083 ← T2938501
      agent:393.hunger = 1.0 ← T2939441
      agent:393.infected = false ← T2932392
    Writes:
      agent:393.health: 31.205083 → 29.205083
      T328 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:393 = 0.476931
        genesis.attribute@agent:393 = 0.229352
        genesis.attribute@agent:393 = 0.572215
        genesis.attribute@agent:393 = 0.130878
      Writes:
        agent:393.alive: none → true
        agent:393.health: none → 79.307936
        agent:393.hunger: none → 0.168806
        agent:393.immune_memory: none → 0.0
        agent:393.immunity: none → 0.564718
        agent:393.infected: none → false
        agent:393.region: none → region:3
        agent:393.risk_tolerance: none → 0.130878
      T2932392 ImmuneDiseaseSystem.disease.recover (tick 1506)
      Inputs:
        agent:393.alive = true ← T328
        agent:393.hunger = 1.0 ← T2929771
        agent:393.immune_memory = 1.0 ← T2926573
        agent:393.immunity = 0.042871 ← T2929771
        agent:393.infected = true ← T2926573
      Random:
        disease.recovery@agent:393 = 0.077267 threshold=0.080718
      Writes:
        agent:393.infected: true → false
      T2938501 AgentSystem.agent.health (tick 1510)
      Inputs:
        agent:393.alive = true ← T328
        agent:393.health = 33.205083 ← T2936570
        agent:393.hunger = 1.0 ← T2937510
        agent:393.infected = false ← T2932392
      Writes:
        agent:393.health: 33.205083 → 31.205083
      T2939441 AgentSystem.agent.metabolism (tick 1510)
      Inputs:
        agent:393.hunger = 1.0 ← T2937510
        agent:393.immunity = 0.010259 ← T2937510
        agent:393.region = region:3 ← T328
        region:3.food_stock = 0.0 ← T2938167
        region:3.population = 6 ← T2938147
      Writes:
        agent:393.hunger: 1.0 → 1.0
        agent:393.immunity: 0.010259 → 0.002208
    … 2 more parent(s)
  T2951706 ImmuneDiseaseSystem.disease.recover (tick 1516)
  Inputs:
    agent:393.alive = true ← T328
    agent:393.hunger = 1.0 ← T2949101
    agent:393.immune_memory = 1.0 ← T2943980
    agent:393.immunity = 0.0 ← T2949101
    agent:393.infected = true ← T2943980
  Random:
    disease.recovery@agent:393 = 0.064229 threshold=0.07
  Writes:
    agent:393.infected: true → false
    T328 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:393 = 0.476931
      genesis.attribute@agent:393 = 0.229352
      genesis.attribute@agent:393 = 0.572215
      genesis.attribute@agent:393 = 0.130878
    Writes:
      agent:393.alive: none → true
      agent:393.health: none → 79.307936
      agent:393.hunger: none → 0.168806
      agent:393.immune_memory: none → 0.0
      agent:393.immunity: none → 0.564718
      agent:393.infected: none → false
      agent:393.region: none → region:3
      agent:393.risk_tolerance: none → 0.130878
    T2943980 ImmuneDiseaseSystem.disease.infect (tick 1512)
    Inputs:
      agent:393.alive = true ← T328
      agent:393.health = 29.205083 ← T2940434
      agent:393.hunger = 1.0 ← T2941374
      agent:393.immune_memory = 1.0 ← T2926573
      agent:393.immunity = 0.0 ← T2941374
      agent:393.infected = false ← T2932392
      agent:393.region = region:3 ← T328
      region:3.disease_load = 0.436864 ← T2942042
    Random:
      disease.infection@agent:393 = 0.011655 threshold=0.058977
      disease.infection@agent:393 = 0.794426
    Writes:
      agent:393.health: 29.205083 → 23.627381
      agent:393.immune_memory: 1.0 → 1.0
      agent:393.infected: false → true
      T328 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:393 = 0.476931
        genesis.attribute@agent:393 = 0.229352
        genesis.attribute@agent:393 = 0.572215
        genesis.attribute@agent:393 = 0.130878
      Writes:
        agent:393.alive: none → true
        agent:393.health: none → 79.307936
        agent:393.hunger: none → 0.168806
        agent:393.immune_memory: none → 0.0
        agent:393.immunity: none → 0.564718
        agent:393.infected: none → false
        agent:393.region: none → region:3
        agent:393.risk_tolerance: none → 0.130878
      T2926573 ImmuneDiseaseSystem.disease.infect (tick 1503)
      Inputs:
        agent:393.alive = true ← T328
        agent:393.health = 58.0 ← T2923012
        agent:393.hunger = 1.0 ← T2923956
        agent:393.immune_memory = 1.0 ← T2632162
        agent:393.immunity = 0.067763 ← T2923956
        agent:393.infected = false ← T2634001
        agent:393.region = region:3 ← T328
        region:3.disease_load = 0.455571 ← T2924625
      Random:
        disease.infection@agent:393 = 0.026203 threshold=0.058168
        disease.infection@agent:393 = 0.723729
      Writes:
        agent:393.health: 58.0 → 52.705083
        agent:393.immune_memory: 1.0 → 1.0
        agent:393.infected: false → true
      T2932392 ImmuneDiseaseSystem.disease.recover (tick 1506)
      Inputs:
        agent:393.alive = true ← T328
        agent:393.hunger = 1.0 ← T2929771
        agent:393.immune_memory = 1.0 ← T2926573
        agent:393.immunity = 0.042871 ← T2929771
        agent:393.infected = true ← T2926573
      Random:
        disease.recovery@agent:393 = 0.077267 threshold=0.080718
      Writes:
        agent:393.infected: true → false
      T2940434 AgentSystem.agent.health (tick 1511)
      Inputs:
        agent:393.alive = true ← T328
        agent:393.health = 31.205083 ← T2938501
        agent:393.hunger = 1.0 ← T2939441
        agent:393.infected = false ← T2932392
      Writes:
        agent:393.health: 31.205083 → 29.205083
      … 2 more parent(s)
    T2949101 AgentSystem.agent.metabolism (tick 1515)
    Inputs:
      agent:393.hunger = 1.0 ← T2947170
      agent:393.immunity = 0.0 ← T2947170
      agent:393.region = region:3 ← T328
      region:3.food_stock = 0.0 ← T2947826
      region:3.population = 5 ← T2947806
    Writes:
      agent:393.hunger: 1.0 → 1.0
      agent:393.immunity: 0.0 → 0.0
      T328 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:393 = 0.476931
        genesis.attribute@agent:393 = 0.229352
        genesis.attribute@agent:393 = 0.572215
        genesis.attribute@agent:393 = 0.130878
      Writes:
        agent:393.alive: none → true
        agent:393.health: none → 79.307936
        agent:393.hunger: none → 0.168806
        agent:393.immune_memory: none → 0.0
        agent:393.immunity: none → 0.564718
        agent:393.infected: none → false
        agent:393.region: none → region:3
        agent:393.risk_tolerance: none → 0.130878
      T2947170 AgentSystem.agent.metabolism (tick 1514)
      Inputs:
        agent:393.hunger = 1.0 ← T2945238
        agent:393.immunity = 0.0 ← T2945238
        agent:393.region = region:3 ← T328
        region:3.food_stock = 0.0 ← T2945894
        region:3.population = 5 ← T2945874
      Writes:
        agent:393.hunger: 1.0 → 1.0
        agent:393.immunity: 0.0 → 0.0
      T2947806 AgentSystem.agents.census (tick 1514)
      Inputs:
        agent:171.alive = false ← T103184
        agent:171.region = region:3 ← T101025
        agent:191.alive = false ← T117302
        agent:191.region = region:3 ← T115204
        agent:193.alive = true ← T106
        agent:193.region = region:3 ← T106
        agent:3.alive = true ← T224
        agent:3.region = region:3 ← T224
        … 18 more input(s)
      Writes:
        region:3.population: 5 → 5
        region:3.workers: 5 → 5
      T2947826 CompostAgricultureSystem.agriculture.harvest (tick 1514)
      Inputs:
        region:3.food_stock = 0.0 ← T2945894
        region:3.population = 5 ← T2945874
        region:3.rainfall = 0.460467 ← T2945884
        region:3.soil_fertility = 0.464781 ← T2945894
        region:3.temperature = 11.89475 ← T2945884
        region:3.workers = 5 ← T2945874
      Random:
        agriculture.crop_variance@region:3 = 0.663517
      Writes:
        region:3.food_stock: 0.0 → 0.0
        region:3.soil_fertility: 0.464781 → 0.463929
  T2953942 AgentSystem.agent.health (tick 1518)
  Inputs:
    agent:393.alive = true ← T328
    agent:393.health = 3.627381 ← T2952014
    agent:393.hunger = 1.0 ← T2952953
    agent:393.infected = false ← T2951706
  Writes:
    agent:393.health: 3.627381 → 1.627381
    T328 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:393 = 0.476931
      genesis.attribute@agent:393 = 0.229352
      genesis.attribute@agent:393 = 0.572215
      genesis.attribute@agent:393 = 0.130878
    Writes:
      agent:393.alive: none → true
      agent:393.health: none → 79.307936
      agent:393.hunger: none → 0.168806
      agent:393.immune_memory: none → 0.0
      agent:393.immunity: none → 0.564718
      agent:393.infected: none → false
      agent:393.region: none → region:3
      agent:393.risk_tolerance: none → 0.130878
    T2951706 ImmuneDiseaseSystem.disease.recover (tick 1516)
    Inputs:
      agent:393.alive = true ← T328
      agent:393.hunger = 1.0 ← T2949101
      agent:393.immune_memory = 1.0 ← T2943980
      agent:393.immunity = 0.0 ← T2949101
      agent:393.infected = true ← T2943980
    Random:
      disease.recovery@agent:393 = 0.064229 threshold=0.07
    Writes:
      agent:393.infected: true → false
      T328 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:393 = 0.476931
        genesis.attribute@agent:393 = 0.229352
        genesis.attribute@agent:393 = 0.572215
        genesis.attribute@agent:393 = 0.130878
      Writes:
        agent:393.alive: none → true
        agent:393.health: none → 79.307936
        agent:393.hunger: none → 0.168806
        agent:393.immune_memory: none → 0.0
        agent:393.immunity: none → 0.564718
        agent:393.infected: none → false
        agent:393.region: none → region:3
        agent:393.risk_tolerance: none → 0.130878
      T2943980 ImmuneDiseaseSystem.disease.infect (tick 1512)
      Inputs:
        agent:393.alive = true ← T328
        agent:393.health = 29.205083 ← T2940434
        agent:393.hunger = 1.0 ← T2941374
        agent:393.immune_memory = 1.0 ← T2926573
        agent:393.immunity = 0.0 ← T2941374
        agent:393.infected = false ← T2932392
        agent:393.region = region:3 ← T328
        region:3.disease_load = 0.436864 ← T2942042
      Random:
        disease.infection@agent:393 = 0.011655 threshold=0.058977
        disease.infection@agent:393 = 0.794426
      Writes:
        agent:393.health: 29.205083 → 23.627381
        agent:393.immune_memory: 1.0 → 1.0
        agent:393.infected: false → true
      T2949101 AgentSystem.agent.metabolism (tick 1515)
      Inputs:
        agent:393.hunger = 1.0 ← T2947170
        agent:393.immunity = 0.0 ← T2947170
        agent:393.region = region:3 ← T328
        region:3.food_stock = 0.0 ← T2947826
        region:3.population = 5 ← T2947806
      Writes:
        agent:393.hunger: 1.0 → 1.0
        agent:393.immunity: 0.0 → 0.0
    T2952014 AgentSystem.agent.health (tick 1517)
    Inputs:
      agent:393.alive = true ← T328
      agent:393.health = 5.627381 ← T2950092
      agent:393.hunger = 1.0 ← T2951031
      agent:393.infected = false ← T2951706
    Writes:
      agent:393.health: 5.627381 → 3.627381
      T328 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:393 = 0.476931
        genesis.attribute@agent:393 = 0.229352
        genesis.attribute@agent:393 = 0.572215
        genesis.attribute@agent:393 = 0.130878
      Writes:
        agent:393.alive: none → true
        agent:393.health: none → 79.307936
        agent:393.hunger: none → 0.168806
        agent:393.immune_memory: none → 0.0
        agent:393.immunity: none → 0.564718
        agent:393.infected: none → false
        agent:393.region: none → region:3
        agent:393.risk_tolerance: none → 0.130878
      T2950092 AgentSystem.agent.health (tick 1516)
      Inputs:
        agent:393.alive = true ← T328
        agent:393.health = 10.127381 ← T2948163
        agent:393.hunger = 1.0 ← T2949101
        agent:393.infected = true ← T2943980
      Writes:
        agent:393.health: 10.127381 → 5.627381
      T2951031 AgentSystem.agent.metabolism (tick 1516)
      Inputs:
        agent:393.hunger = 1.0 ← T2949101
        agent:393.immunity = 0.0 ← T2949101
        agent:393.region = region:3 ← T328
        region:3.food_stock = 0.0 ← T2949758
        region:3.population = 5 ← T2949738
      Writes:
        agent:393.hunger: 1.0 → 1.0
        agent:393.immunity: 0.0 → 0.0
      T2951706 ImmuneDiseaseSystem.disease.recover (tick 1516)
      Inputs:
        agent:393.alive = true ← T328
        agent:393.hunger = 1.0 ← T2949101
        agent:393.immune_memory = 1.0 ← T2943980
        agent:393.immunity = 0.0 ← T2949101
        agent:393.infected = true ← T2943980
      Random:
        disease.recovery@agent:393 = 0.064229 threshold=0.07
      Writes:
        agent:393.infected: true → false
    T2952953 AgentSystem.agent.metabolism (tick 1517)
    Inputs:
      agent:393.hunger = 1.0 ← T2951031
      agent:393.immunity = 0.0 ← T2951031
      agent:393.region = region:3 ← T328
      region:3.food_stock = 0.0 ← T2951687
      region:3.population = 4 ← T2951667
    Writes:
      agent:393.hunger: 1.0 → 1.0
      agent:393.immunity: 0.0 → 0.0
      T328 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:393 = 0.476931
        genesis.attribute@agent:393 = 0.229352
        genesis.attribute@agent:393 = 0.572215
        genesis.attribute@agent:393 = 0.130878
      Writes:
        agent:393.alive: none → true
        agent:393.health: none → 79.307936
        agent:393.hunger: none → 0.168806
        agent:393.immune_memory: none → 0.0
        agent:393.immunity: none → 0.564718
        agent:393.infected: none → false
        agent:393.region: none → region:3
        agent:393.risk_tolerance: none → 0.130878
      T2951031 AgentSystem.agent.metabolism (tick 1516)
      Inputs:
        agent:393.hunger = 1.0 ← T2949101
        agent:393.immunity = 0.0 ← T2949101
        agent:393.region = region:3 ← T328
        region:3.food_stock = 0.0 ← T2949758
        region:3.population = 5 ← T2949738
      Writes:
        agent:393.hunger: 1.0 → 1.0
        agent:393.immunity: 0.0 → 0.0
      T2951667 AgentSystem.agents.census (tick 1516)
      Inputs:
        agent:171.alive = false ← T103184
        agent:171.region = region:3 ← T101025
        agent:191.alive = false ← T117302
        agent:191.region = region:3 ← T115204
        agent:193.alive = true ← T106
        agent:193.region = region:3 ← T106
        agent:3.alive = true ← T224
        agent:3.region = region:3 ← T224
        … 16 more input(s)
      Writes:
        region:3.population: 5 → 4
        region:3.workers: 5 → 4
      T2951687 CompostAgricultureSystem.agriculture.harvest (tick 1516)
      Inputs:
        region:3.food_stock = 0.0 ← T2949758
        region:3.population = 5 ← T2949738
        region:3.rainfall = 0.454812 ← T2949748
        region:3.soil_fertility = 0.463077 ← T2949758
        region:3.temperature = 9.656099 ← T2949748
        region:3.workers = 5 ← T2949738
      Random:
        agriculture.crop_variance@region:3 = 0.343237
      Writes:
        region:3.food_stock: 0.0 → 0.0
        region:3.soil_fertility: 0.463077 → 0.462225
  … 2 more parent(s)
```

## Reproduction

```bash
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset compost --db runs/survival_seed7_compost.db --report <path>
```

Same seed + kernel v0.1.0 + ruleset 0.3.3g → bit-identical world, identical traces, identical report.