# Causal survival experiment — seed 7

Kernel **v0.1 (frozen)**, ruleset **0.3.1b** — the laws
differ from the baseline by proposal only; the kernel, the purposes
and the addressable draw stream are unchanged.

> Experiment B: soil fertility never depletes; harvest otherwise identical. Tests whether the food clock is the bottleneck.

## Run

| parameter | value |
|---|---|
| seed | 7 |
| ruleset | 0.3.1b |
| regions | 10 |
| agents | 1000 |
| ticks | 4000 |
| wall time | 1147s |
| archive | `runs/survival_seed7_stable_soil.db` |
| survivors | 950 / 1000 |
| deaths | 50 |
| last death | tick 83 |

## Lifespan distribution (survivors censored at run end)

| pct | ticks |
|---|---|
| p0 | 28 |
| p10 | 4000 |
| p25 | 4000 |
| p50 | 4000 |
| p75 | 4000 |
| p90 | 4000 |
| p100 | 4000 |

mean lifespan: **3803** ticks

## Statistical regularity: correlations with lifespan

| observable | pearson | spearman |
|---|---|---|
| initial_health | +0.069 | +0.069 |
| initial_immunity | +0.084 | +0.087 |
| risk_tolerance | +0.158 | +0.156 |
| migration_count | -0.204 | -0.259 |
| infection_count | +0.551 | +0.378 |
| avg_food_access | +0.242 | +0.305 |
| avg_social_density | +0.640 | +0.372 |

## Individual causality: death mechanisms (from traces)

| mechanism | deaths | share |
|---|---|---|
| disease+starvation | 41 | 82.0% |
| disease | 9 | 18.0% |

> **Interpretation caveat.** `migration_count`, `infection_count` and
> the sampled food/density aggregates are *time-at-risk* variables:
> agents that die early simply have fewer ticks in which to migrate
> or meet pathogens. A positive correlation of such a variable with
> lifespan is therefore expected even when the variable is harmful.
> The group tables below exist precisely to confront those numbers
> with per-death causal mechanisms.

## Statistical regularity vs individual causality

### Migration — same observable, different mechanisms?

| group | n | mean lifespan | disease | disease+starvation |
|---|---|---|---|---|
| stayers (0 migrations) | 815 | 3913 | 5 | 13 |
| migrants (>=1 migration) | 185 | 3318 | 4 | 28 |

### Risk tolerance quartiles

| group | n | mean lifespan | disease | disease+starvation |
|---|---|---|---|---|
| risk Q1 (lowest) | 250 | 3574 | 2 | 25 |
| risk Q2 | 250 | 3811 | 1 | 11 |
| risk Q3 | 250 | 3889 | 3 | 4 |
| risk Q4 (highest) | 250 | 3937 | 3 | 1 |

## Example mechanical explanations

### agent:102 — disease (died tick 83, T168488)

```
T168488 AgentSystem.agent.death (tick 83)
Inputs:
  agent:102.alive = true ← T6
  agent:102.health = 1.023145 ← T166529
  agent:102.hunger = 0.0 ← T167479
  agent:102.infected = true ← T162575
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
  T162575 ImmuneDiseaseSystem.disease.infect (tick 79)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 16.812727 ← T158697
    agent:102.hunger = 0.0 ← T159645
    agent:102.immune_memory = 0.7 ← T127163
    agent:102.immunity = 0.427132 ← T159645
    agent:102.infected = false ← T154748
    agent:102.region = region:2 ← T6
    region:2.disease_load = 0.203751 ← T160614
  Random:
    disease.infection@agent:102 = 0.00308 threshold=0.014259
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
    T127163 ImmuneDiseaseSystem.disease.infect (tick 61)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 55.187459 ← T123268
      agent:102.hunger = 0.0 ← T124196
      agent:102.immune_memory = 0.35 ← T78533
      agent:102.immunity = 0.429694 ← T124196
      agent:102.infected = false ← T115250
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.262139 ← T125180
    Random:
      disease.infection@agent:102 = 0.019219 threshold=0.031723
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
      T78533 ImmuneDiseaseSystem.disease.infect (tick 37)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 100.0 ← T74457
        agent:102.hunger = 0.0 ← T75394
        agent:102.immune_memory = 0.0 ← T6
        agent:102.immunity = 0.43349 ← T75394
        agent:102.infected = false ← T6
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.307879 ← T76446
      Random:
        disease.infection@agent:102 = 0.011169 threshold=0.052791
        disease.infection@agent:102 = 0.131254
      Writes:
        agent:102.health: 100.0 → 92.687459
        agent:102.immune_memory: 0.0 → 0.35
        agent:102.infected: false → true
      T115250 ImmuneDiseaseSystem.disease.recover (tick 55)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T112193
        agent:102.immune_memory = 0.35 ← T78533
        agent:102.immunity = 0.430601 ← T112193
        agent:102.infected = true ← T78533
      Random:
        disease.recovery@agent:102 = 0.118911 threshold=0.19765
      Writes:
        agent:102.infected: true → false
      T123268 AgentSystem.agent.health (tick 60)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 53.687459 ← T121282
        agent:102.hunger = 0.0 ← T122209
        agent:102.infected = false ← T115250
      Writes:
        agent:102.health: 53.687459 → 55.187459
      … 2 more parent(s)
    T154748 ImmuneDiseaseSystem.disease.recover (tick 75)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.hunger = 0.0 ← T151801
      agent:102.immune_memory = 0.7 ← T127163
      agent:102.immunity = 0.427682 ← T151801
      agent:102.infected = true ← T127163
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
      T127163 ImmuneDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T123268
        agent:102.hunger = 0.0 ← T124196
        agent:102.immune_memory = 0.35 ← T78533
        agent:102.immunity = 0.429694 ← T124196
        agent:102.infected = false ← T115250
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.262139 ← T125180
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.031723
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T151801 AgentSystem.agent.metabolism (tick 74)
      Inputs:
        agent:102.hunger = 0.0 ← T149831
        agent:102.immunity = 0.427821 ← T149831
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1975.71615 ← T150840
        region:2.population = 109 ← T150780
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.427821 → 0.427682
    T158697 AgentSystem.agent.health (tick 78)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 15.312727 ← T156737
      agent:102.hunger = 0.0 ← T157685
      agent:102.infected = false ← T154748
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
      T154748 ImmuneDiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T151801
        agent:102.immune_memory = 0.7 ← T127163
        agent:102.immunity = 0.427682 ← T151801
        agent:102.infected = true ← T127163
      Random:
        disease.recovery@agent:102 = 0.244162 threshold=0.26692
      Writes:
        agent:102.infected: true → false
      T156737 AgentSystem.agent.health (tick 77)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 13.812727 ← T154775
        agent:102.hunger = 0.0 ← T155725
        agent:102.infected = false ← T154748
      Writes:
        agent:102.health: 13.812727 → 15.312727
      T157685 AgentSystem.agent.metabolism (tick 77)
      Inputs:
        agent:102.hunger = 0.0 ← T155725
        agent:102.immunity = 0.427406 ← T155725
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1922.374801 ← T156723
        region:2.population = 109 ← T156674
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.427406 → 0.427269
    … 2 more parent(s)
  T166529 AgentSystem.agent.health (tick 82)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 3.523145 ← T164564
    agent:102.hunger = 0.0 ← T165513
    agent:102.infected = true ← T162575
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
    T162575 ImmuneDiseaseSystem.disease.infect (tick 79)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 16.812727 ← T158697
      agent:102.hunger = 0.0 ← T159645
      agent:102.immune_memory = 0.7 ← T127163
      agent:102.immunity = 0.427132 ← T159645
      agent:102.infected = false ← T154748
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.203751 ← T160614
    Random:
      disease.infection@agent:102 = 0.00308 threshold=0.014259
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
      T127163 ImmuneDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T123268
        agent:102.hunger = 0.0 ← T124196
        agent:102.immune_memory = 0.35 ← T78533
        agent:102.immunity = 0.429694 ← T124196
        agent:102.infected = false ← T115250
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.262139 ← T125180
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.031723
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T154748 ImmuneDiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T151801
        agent:102.immune_memory = 0.7 ← T127163
        agent:102.immunity = 0.427682 ← T151801
        agent:102.infected = true ← T127163
      Random:
        disease.recovery@agent:102 = 0.244162 threshold=0.26692
      Writes:
        agent:102.infected: true → false
      T158697 AgentSystem.agent.health (tick 78)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 15.312727 ← T156737
        agent:102.hunger = 0.0 ← T157685
        agent:102.infected = false ← T154748
      Writes:
        agent:102.health: 15.312727 → 16.812727
      … 2 more parent(s)
    T164564 AgentSystem.agent.health (tick 81)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 6.023145 ← T162609
      agent:102.hunger = 0.0 ← T163558
      agent:102.infected = true ← T162575
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
      T162575 ImmuneDiseaseSystem.disease.infect (tick 79)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 16.812727 ← T158697
        agent:102.hunger = 0.0 ← T159645
        agent:102.immune_memory = 0.7 ← T127163
        agent:102.immunity = 0.427132 ← T159645
        agent:102.infected = false ← T154748
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.203751 ← T160614
      Random:
        disease.infection@agent:102 = 0.00308 threshold=0.014259
        disease.infection@agent:102 = 0.829238
      Writes:
        agent:102.health: 16.812727 → 8.523145
        agent:102.immune_memory: 0.7 → 1.0
        agent:102.infected: false → true
      T162609 AgentSystem.agent.health (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 8.523145 ← T162575
        agent:102.hunger = 0.0 ← T161599
        agent:102.infected = true ← T162575
      Writes:
        agent:102.health: 8.523145 → 6.023145
      T163558 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161599
        agent:102.immunity = 0.426997 ← T161599
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1838.134755 ← T162596
        region:2.population = 109 ← T162547
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
    T165513 AgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T163558
      agent:102.immunity = 0.426862 ← T163558
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1856.729364 ← T164551
      region:2.population = 109 ← T164506
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
      T163558 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161599
        agent:102.immunity = 0.426997 ← T161599
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1838.134755 ← T162596
        region:2.population = 109 ← T162547
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
      T164506 AgentSystem.agents.census (tick 80)
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
      T164551 StableSoilAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1838.134755 ← T162596
        region:2.population = 109 ← T162547
        region:2.rainfall = 0.577858 ← T162557
        region:2.soil_fertility = 0.493909 ← T1003
        region:2.temperature = 18.934401 ← T162557
        region:2.workers = 109 ← T162547
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1838.134755 → 1856.729364
  T167479 AgentSystem.agent.metabolism (tick 82)
  Inputs:
    agent:102.hunger = 0.0 ← T165513
    agent:102.immunity = 0.426727 ← T165513
    agent:102.region = region:2 ← T6
    region:2.food_stock = 1819.695071 ← T166516
    region:2.population = 109 ← T166461
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
    T165513 AgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T163558
      agent:102.immunity = 0.426862 ← T163558
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1856.729364 ← T164551
      region:2.population = 109 ← T164506
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
      T163558 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161599
        agent:102.immunity = 0.426997 ← T161599
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1838.134755 ← T162596
        region:2.population = 109 ← T162547
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
      T164506 AgentSystem.agents.census (tick 80)
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
      T164551 StableSoilAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1838.134755 ← T162596
        region:2.population = 109 ← T162547
        region:2.rainfall = 0.577858 ← T162557
        region:2.soil_fertility = 0.493909 ← T1003
        region:2.temperature = 18.934401 ← T162557
        region:2.workers = 109 ← T162547
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1838.134755 → 1856.729364
    T166461 AgentSystem.agents.census (tick 81)
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
      … 130 more parent(s)
    T166516 StableSoilAgricultureSystem.agriculture.harvest (tick 81)
    Inputs:
      region:2.food_stock = 1856.729364 ← T164551
      region:2.population = 109 ← T164506
      region:2.rainfall = 0.568902 ← T164516
      region:2.soil_fertility = 0.493909 ← T1003
      region:2.temperature = 19.003536 ← T164516
      region:2.workers = 109 ← T164506
    Random:
      agriculture.crop_variance@region:2 = 0.024179
    Writes:
      region:2.food_stock: 1856.729364 → 1819.695071
      T1003 GenesisSystem.genesis.region (tick 0)
      Random:
        genesis.attribute@region:2 = 0.749126
        genesis.attribute@region:2 = 0.451973
        genesis.attribute@region:2 = 0.097577
        genesis.attribute@region:2 = 0.008114
        genesis.attribute@region:2 = 0.665104
        genesis.attribute@region:2 = 0.64073
        genesis.attribute@region:2 = 0.077717
        genesis.attribute@region:2 = 0.71655
      Writes:
        region:2.climate_volatility: none → 0.508114
        region:2.disease_base: none → 0.165543
        region:2.disease_load: none → 0.099326
        region:2.food_stock: none → 1773.239602
        region:2.population: none → 100
        region:2.rainfall: none → 0.581534
        region:2.rainfall_base: none → 0.553388
        region:2.soil_fertility: none → 0.493909
        region:2.temperature: none → 19.148179
        region:2.temperature_base: none → 18.487763
        region:2.workers: none → 100
      T164506 AgentSystem.agents.census (tick 80)
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
      T164516 ClimateSystem.climate.step (tick 80)
      Inputs:
        region:2.climate_volatility = 0.508114 ← T1003
        region:2.rainfall = 0.577858 ← T162557
        region:2.rainfall_base = 0.553388 ← T1003
        region:2.temperature = 18.934401 ← T162557
        region:2.temperature_base = 18.487763 ← T1003
      Random:
        climate.temperature_noise@region:2 = 0.642326
        climate.rain@region:2 = 0.466151
      Writes:
        region:2.rainfall: 0.577858 → 0.568902
        region:2.temperature: 18.934401 → 19.003536
      T164551 StableSoilAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1838.134755 ← T162596
        region:2.population = 109 ← T162547
        region:2.rainfall = 0.577858 ← T162557
        region:2.soil_fertility = 0.493909 ← T1003
        region:2.temperature = 18.934401 ← T162557
        region:2.workers = 109 ← T162547
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1838.134755 → 1856.729364
```

### agent:105 — disease+starvation (died tick 64, T131154)

```
T131154 AgentSystem.agent.death (tick 64)
Inputs:
  agent:105.alive = true ← T9
  agent:105.health = 4.420416 ← T129182
  agent:105.hunger = 0.988691 ← T130113
  agent:105.infected = true ← T78534
Writes:
  agent:105.alive: true → false
  agent:105.health: 4.420416 → 0.0
  T9 GenesisSystem.genesis.agent (tick 0)
  Random:
    genesis.attribute@agent:105 = 0.181909
    genesis.attribute@agent:105 = 0.478079
    genesis.attribute@agent:105 = 0.098673
    genesis.attribute@agent:105 = 0.395967
  Writes:
    agent:105.alive: none → true
    agent:105.health: none → 70.457256
    agent:105.hunger: none → 0.243424
    agent:105.immune_memory: none → 0.0
    agent:105.immunity: none → 0.30427
    agent:105.infected: none → false
    agent:105.region: none → region:5
    agent:105.risk_tolerance: none → 0.395967
  T78534 ImmuneDiseaseSystem.disease.infect (tick 37)
  Inputs:
    agent:105.alive = true ← T9
    agent:105.health = 98.0 ← T74460
    agent:105.hunger = 0.860658 ← T75397
    agent:105.immune_memory = 0.0 ← T9
    agent:105.immunity = 0.256922 ← T75397
    agent:105.infected = false ← T9
    agent:105.region = region:5 ← T9
    region:5.disease_load = 0.384864 ← T76449
  Random:
    disease.infection@agent:105 = 0.240153 threshold=0.248023
    disease.infection@agent:105 = 0.657958
  Writes:
    agent:105.health: 98.0 → 85.420416
    agent:105.immune_memory: 0.0 → 0.35
    agent:105.infected: false → true
    T9 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:105 = 0.181909
      genesis.attribute@agent:105 = 0.478079
      genesis.attribute@agent:105 = 0.098673
      genesis.attribute@agent:105 = 0.395967
    Writes:
      agent:105.alive: none → true
      agent:105.health: none → 70.457256
      agent:105.hunger: none → 0.243424
      agent:105.immune_memory: none → 0.0
      agent:105.immunity: none → 0.30427
      agent:105.infected: none → false
      agent:105.region: none → region:5
      agent:105.risk_tolerance: none → 0.395967
    T74460 AgentSystem.agent.health (tick 36)
    Inputs:
      agent:105.alive = true ← T9
      agent:105.health = 100.0 ← T58523
      agent:105.hunger = 0.790658 ← T73304
      agent:105.infected = false ← T9
    Writes:
      agent:105.health: 100.0 → 98.0
      T9 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:105 = 0.181909
        genesis.attribute@agent:105 = 0.478079
        genesis.attribute@agent:105 = 0.098673
        genesis.attribute@agent:105 = 0.395967
      Writes:
        agent:105.alive: none → true
        agent:105.health: none → 70.457256
        agent:105.hunger: none → 0.243424
        agent:105.immune_memory: none → 0.0
        agent:105.immunity: none → 0.30427
        agent:105.infected: none → false
        agent:105.region: none → region:5
        agent:105.risk_tolerance: none → 0.395967
      T58523 AgentSystem.agent.health (tick 28)
      Inputs:
        agent:105.alive = true ← T9
        agent:105.health = 100.0 ← T56407
        agent:105.hunger = 0.230658 ← T57407
        agent:105.infected = false ← T9
      Writes:
        agent:105.health: 100.0 → 100.0
      T73304 AgentSystem.agent.metabolism (tick 35)
      Inputs:
        agent:105.hunger = 0.720658 ← T71256
        agent:105.immunity = 0.272121 ← T71256
        agent:105.region = region:5 ← T9
        region:5.food_stock = 0.0 ← T72396
        region:5.population = 75 ← T72303
      Writes:
        agent:105.hunger: 0.720658 → 0.790658
        agent:105.immunity: 0.272121 → 0.264853
    T75397 AgentSystem.agent.metabolism (tick 36)
    Inputs:
      agent:105.hunger = 0.790658 ← T73304
      agent:105.immunity = 0.264853 ← T73304
      agent:105.region = region:5 ← T9
      region:5.food_stock = 0.0 ← T74449
      region:5.population = 57 ← T74349
    Writes:
      agent:105.hunger: 0.790658 → 0.860658
      agent:105.immunity: 0.264853 → 0.256922
      T9 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:105 = 0.181909
        genesis.attribute@agent:105 = 0.478079
        genesis.attribute@agent:105 = 0.098673
        genesis.attribute@agent:105 = 0.395967
      Writes:
        agent:105.alive: none → true
        agent:105.health: none → 70.457256
        agent:105.hunger: none → 0.243424
        agent:105.immune_memory: none → 0.0
        agent:105.immunity: none → 0.30427
        agent:105.infected: none → false
        agent:105.region: none → region:5
        agent:105.risk_tolerance: none → 0.395967
      T73304 AgentSystem.agent.metabolism (tick 35)
      Inputs:
        agent:105.hunger = 0.720658 ← T71256
        agent:105.immunity = 0.272121 ← T71256
        agent:105.region = region:5 ← T9
        region:5.food_stock = 0.0 ← T72396
        region:5.population = 75 ← T72303
      Writes:
        agent:105.hunger: 0.720658 → 0.790658
        agent:105.immunity: 0.272121 → 0.264853
      T74349 AgentSystem.agents.census (tick 35)
      Inputs:
        agent:105.alive = true ← T9
        agent:105.region = region:5 ← T9
        agent:135.alive = true ← T42
        agent:135.region = region:5 ← T42
        agent:145.alive = true ← T53
        agent:145.region = region:5 ← T53
        agent:15.alive = true ← T58
        agent:15.region = region:5 ← T58
        … 108 more input(s)
      Writes:
        region:5.population: 75 → 57
        region:5.workers: 75 → 57
      T74449 StableSoilAgricultureSystem.agriculture.harvest (tick 35)
      Inputs:
        region:5.food_stock = 0.0 ← T72396
        region:5.population = 75 ← T72303
        region:5.rainfall = 0.523304 ← T72313
        region:5.soil_fertility = 0.476468 ← T1006
        region:5.temperature = 20.124071 ← T72313
        region:5.workers = 75 ← T72303
      Random:
        agriculture.crop_variance@region:5 = 0.348517
      Writes:
        region:5.food_stock: 0.0 → 0.0
    T76449 ImmuneDiseaseSystem.disease.environment (tick 36)
    Inputs:
      agent:105.alive = true ← T9
      agent:105.infected = false ← T9
      agent:105.region = region:5 ← T9
      agent:135.alive = true ← T42
      agent:135.infected = true ← T70322
      agent:135.region = region:5 ← T42
      agent:145.alive = true ← T53
      agent:145.infected = true ← T58431
      … 132 more input(s)
    Random:
      disease.load_noise@region:5 = 0.322495
    Writes:
      region:5.disease_load: 0.366912 → 0.384864
      T9 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:105 = 0.181909
        genesis.attribute@agent:105 = 0.478079
        genesis.attribute@agent:105 = 0.098673
        genesis.attribute@agent:105 = 0.395967
      Writes:
        agent:105.alive: none → true
        agent:105.health: none → 70.457256
        agent:105.hunger: none → 0.243424
        agent:105.immune_memory: none → 0.0
        agent:105.immunity: none → 0.30427
        agent:105.infected: none → false
        agent:105.region: none → region:5
        agent:105.risk_tolerance: none → 0.395967
      T42 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:135 = 0.065428
        genesis.attribute@agent:135 = 0.253851
        genesis.attribute@agent:135 = 0.692732
        genesis.attribute@agent:135 = 0.818441
      Writes:
        agent:135.alive: none → true
        agent:135.health: none → 66.962836
        agent:135.hunger: none → 0.176155
        agent:135.immune_memory: none → 0.0
        agent:135.immunity: none → 0.631003
        agent:135.infected: none → false
        agent:135.region: none → region:5
        agent:135.risk_tolerance: none → 0.818441
      T53 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:145 = 0.956457
        genesis.attribute@agent:145 = 0.254652
        genesis.attribute@agent:145 = 0.32803
        genesis.attribute@agent:145 = 0.349942
      Writes:
        agent:145.alive: none → true
        agent:145.health: none → 93.693711
        agent:145.hunger: none → 0.176396
        agent:145.immune_memory: none → 0.0
        agent:145.immunity: none → 0.430416
        agent:145.infected: none → false
        agent:145.region: none → region:5
        agent:145.risk_tolerance: none → 0.349942
      T58 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:15 = 0.706386
        genesis.attribute@agent:15 = 0.363331
        genesis.attribute@agent:15 = 0.540488
        genesis.attribute@agent:15 = 0.053071
      Writes:
        agent:15.alive: none → true
        agent:15.health: none → 86.191588
        agent:15.hunger: none → 0.208999
        agent:15.immune_memory: none → 0.0
        agent:15.immunity: none → 0.547268
        agent:15.infected: none → false
        agent:15.region: none → region:5
        agent:15.risk_tolerance: none → 0.053071
      … 83 more parent(s)
  T129182 AgentSystem.agent.health (tick 63)
  Inputs:
    agent:105.alive = true ← T9
    agent:105.health = 8.920416 ← T127220
    agent:105.hunger = 0.918691 ← T128151
    agent:105.infected = true ← T78534
  Writes:
    agent:105.health: 8.920416 → 4.420416
    T9 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:105 = 0.181909
      genesis.attribute@agent:105 = 0.478079
      genesis.attribute@agent:105 = 0.098673
      genesis.attribute@agent:105 = 0.395967
    Writes:
      agent:105.alive: none → true
      agent:105.health: none → 70.457256
      agent:105.hunger: none → 0.243424
      agent:105.immune_memory: none → 0.0
      agent:105.immunity: none → 0.30427
      agent:105.infected: none → false
      agent:105.region: none → region:5
      agent:105.risk_tolerance: none → 0.395967
    T78534 ImmuneDiseaseSystem.disease.infect (tick 37)
    Inputs:
      agent:105.alive = true ← T9
      agent:105.health = 98.0 ← T74460
      agent:105.hunger = 0.860658 ← T75397
      agent:105.immune_memory = 0.0 ← T9
      agent:105.immunity = 0.256922 ← T75397
      agent:105.infected = false ← T9
      agent:105.region = region:5 ← T9
      region:5.disease_load = 0.384864 ← T76449
    Random:
      disease.infection@agent:105 = 0.240153 threshold=0.248023
      disease.infection@agent:105 = 0.657958
    Writes:
      agent:105.health: 98.0 → 85.420416
      agent:105.immune_memory: 0.0 → 0.35
      agent:105.infected: false → true
      T9 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:105 = 0.181909
        genesis.attribute@agent:105 = 0.478079
        genesis.attribute@agent:105 = 0.098673
        genesis.attribute@agent:105 = 0.395967
      Writes:
        agent:105.alive: none → true
        agent:105.health: none → 70.457256
        agent:105.hunger: none → 0.243424
        agent:105.immune_memory: none → 0.0
        agent:105.immunity: none → 0.30427
        agent:105.infected: none → false
        agent:105.region: none → region:5
        agent:105.risk_tolerance: none → 0.395967
      T74460 AgentSystem.agent.health (tick 36)
      Inputs:
        agent:105.alive = true ← T9
        agent:105.health = 100.0 ← T58523
        agent:105.hunger = 0.790658 ← T73304
        agent:105.infected = false ← T9
      Writes:
        agent:105.health: 100.0 → 98.0
      T75397 AgentSystem.agent.metabolism (tick 36)
      Inputs:
        agent:105.hunger = 0.790658 ← T73304
        agent:105.immunity = 0.264853 ← T73304
        agent:105.region = region:5 ← T9
        region:5.food_stock = 0.0 ← T74449
        region:5.population = 57 ← T74349
      Writes:
        agent:105.hunger: 0.790658 → 0.860658
        agent:105.immunity: 0.264853 → 0.256922
      T76449 ImmuneDiseaseSystem.disease.environment (tick 36)
      Inputs:
        agent:105.alive = true ← T9
        agent:105.infected = false ← T9
        agent:105.region = region:5 ← T9
        agent:135.alive = true ← T42
        agent:135.infected = true ← T70322
        agent:135.region = region:5 ← T42
        agent:145.alive = true ← T53
        agent:145.infected = true ← T58431
        … 132 more input(s)
      Random:
        disease.load_noise@region:5 = 0.322495
      Writes:
        region:5.disease_load: 0.366912 → 0.384864
    T127220 AgentSystem.agent.health (tick 62)
    Inputs:
      agent:105.alive = true ← T9
      agent:105.health = 13.420416 ← T125248
      agent:105.hunger = 0.848691 ← T126175
      agent:105.infected = true ← T78534
    Writes:
      agent:105.health: 13.420416 → 8.920416
      T9 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:105 = 0.181909
        genesis.attribute@agent:105 = 0.478079
        genesis.attribute@agent:105 = 0.098673
        genesis.attribute@agent:105 = 0.395967
      Writes:
        agent:105.alive: none → true
        agent:105.health: none → 70.457256
        agent:105.hunger: none → 0.243424
        agent:105.immune_memory: none → 0.0
        agent:105.immunity: none → 0.30427
        agent:105.infected: none → false
        agent:105.region: none → region:5
        agent:105.risk_tolerance: none → 0.395967
      T78534 ImmuneDiseaseSystem.disease.infect (tick 37)
      Inputs:
        agent:105.alive = true ← T9
        agent:105.health = 98.0 ← T74460
        agent:105.hunger = 0.860658 ← T75397
        agent:105.immune_memory = 0.0 ← T9
        agent:105.immunity = 0.256922 ← T75397
        agent:105.infected = false ← T9
        agent:105.region = region:5 ← T9
        region:5.disease_load = 0.384864 ← T76449
      Random:
        disease.infection@agent:105 = 0.240153 threshold=0.248023
        disease.infection@agent:105 = 0.657958
      Writes:
        agent:105.health: 98.0 → 85.420416
        agent:105.immune_memory: 0.0 → 0.35
        agent:105.infected: false → true
      T125248 AgentSystem.agent.health (tick 61)
      Inputs:
        agent:105.alive = true ← T9
        agent:105.health = 17.920416 ← T123271
        agent:105.hunger = 0.778691 ← T124199
        agent:105.infected = true ← T78534
      Writes:
        agent:105.health: 17.920416 → 13.420416
      T126175 AgentSystem.agent.metabolism (tick 61)
      Inputs:
        agent:105.hunger = 0.778691 ← T124199
        agent:105.immunity = 0.121199 ← T124199
        agent:105.region = region:5 ← T107130
        region:5.food_stock = 0.0 ← T125233
        region:5.population = 11 ← T125163
      Writes:
        agent:105.hunger: 0.778691 → 0.848691
        agent:105.immunity: 0.121199 → 0.114106
    T128151 AgentSystem.agent.metabolism (tick 62)
    Inputs:
      agent:105.hunger = 0.848691 ← T126175
      agent:105.immunity = 0.114106 ← T126175
      agent:105.region = region:5 ← T107130
      region:5.food_stock = 0.0 ← T127207
      region:5.population = 10 ← T127138
    Writes:
      agent:105.hunger: 0.848691 → 0.918691
      agent:105.immunity: 0.114106 → 0.106349
      T107130 AgentSystem.agent.migrate (tick 51)
      Inputs:
        agent:105.hunger = 0.605911 ← T104115
        agent:105.region = region:4 ← T103053
        agent:105.risk_tolerance = 0.395967 ← T9
      Random:
        agent.decision@agent:105 = 0.170864 threshold=0.197983
      Writes:
        agent:105.region: region:4 → region:5
      T126175 AgentSystem.agent.metabolism (tick 61)
      Inputs:
        agent:105.hunger = 0.778691 ← T124199
        agent:105.immunity = 0.121199 ← T124199
        agent:105.region = region:5 ← T107130
        region:5.food_stock = 0.0 ← T125233
        region:5.population = 11 ← T125163
      Writes:
        agent:105.hunger: 0.778691 → 0.848691
        agent:105.immunity: 0.121199 → 0.114106
      T127138 AgentSystem.agents.census (tick 61)
      Inputs:
        agent:105.alive = true ← T9
        agent:105.region = region:5 ← T107130
        agent:111.alive = true ← T16
        agent:111.region = region:5 ← T88779
        agent:131.alive = false ← T111266
        agent:131.region = region:5 ← T107131
        agent:15.alive = false ← T123260
        agent:15.region = region:5 ← T58
        … 22 more input(s)
      Writes:
        region:5.population: 11 → 10
        region:5.workers: 11 → 10
      T127207 StableSoilAgricultureSystem.agriculture.harvest (tick 61)
      Inputs:
        region:5.food_stock = 0.0 ← T125233
        region:5.population = 11 ← T125163
        region:5.rainfall = 0.42674 ← T125173
        region:5.soil_fertility = 0.476468 ← T1006
        region:5.temperature = 24.070148 ← T125173
        region:5.workers = 11 ← T125163
      Random:
        agriculture.crop_variance@region:5 = 0.90235
      Writes:
        region:5.food_stock: 0.0 → 0.0
  T130113 AgentSystem.agent.metabolism (tick 63)
  Inputs:
    agent:105.hunger = 0.918691 ← T128151
    agent:105.immunity = 0.106349 ← T128151
    agent:105.region = region:5 ← T107130
    region:5.food_stock = 0.0 ← T129169
    region:5.population = 9 ← T129111
  Writes:
    agent:105.hunger: 0.918691 → 0.988691
    agent:105.immunity: 0.106349 → 0.09793
    T107130 AgentSystem.agent.migrate (tick 51)
    Inputs:
      agent:105.hunger = 0.605911 ← T104115
      agent:105.region = region:4 ← T103053
      agent:105.risk_tolerance = 0.395967 ← T9
    Random:
      agent.decision@agent:105 = 0.170864 threshold=0.197983
    Writes:
      agent:105.region: region:4 → region:5
      T9 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:105 = 0.181909
        genesis.attribute@agent:105 = 0.478079
        genesis.attribute@agent:105 = 0.098673
        genesis.attribute@agent:105 = 0.395967
      Writes:
        agent:105.alive: none → true
        agent:105.health: none → 70.457256
        agent:105.hunger: none → 0.243424
        agent:105.immune_memory: none → 0.0
        agent:105.immunity: none → 0.30427
        agent:105.infected: none → false
        agent:105.region: none → region:5
        agent:105.risk_tolerance: none → 0.395967
      T103053 AgentSystem.agent.migrate (tick 49)
      Inputs:
        agent:105.hunger = 0.665911 ← T100034
        agent:105.region = region:3 ← T101020
        agent:105.risk_tolerance = 0.395967 ← T9
      Random:
        agent.decision@agent:105 = 0.060683 threshold=0.197983
      Writes:
        agent:105.region: region:3 → region:4
      T104115 AgentSystem.agent.metabolism (tick 50)
      Inputs:
        agent:105.hunger = 0.635911 ← T102069
        agent:105.immunity = 0.172902 ← T102069
        agent:105.region = region:4 ← T103053
        region:4.food_stock = 1706.742971 ← T103172
        region:4.population = 125 ← T103070
      Writes:
        agent:105.hunger: 0.635911 → 0.605911
        agent:105.immunity: 0.172902 → 0.167979
    T128151 AgentSystem.agent.metabolism (tick 62)
    Inputs:
      agent:105.hunger = 0.848691 ← T126175
      agent:105.immunity = 0.114106 ← T126175
      agent:105.region = region:5 ← T107130
      region:5.food_stock = 0.0 ← T127207
      region:5.population = 10 ← T127138
    Writes:
      agent:105.hunger: 0.848691 → 0.918691
      agent:105.immunity: 0.114106 → 0.106349
      T107130 AgentSystem.agent.migrate (tick 51)
      Inputs:
        agent:105.hunger = 0.605911 ← T104115
        agent:105.region = region:4 ← T103053
        agent:105.risk_tolerance = 0.395967 ← T9
      Random:
        agent.decision@agent:105 = 0.170864 threshold=0.197983
      Writes:
        agent:105.region: region:4 → region:5
      T126175 AgentSystem.agent.metabolism (tick 61)
      Inputs:
        agent:105.hunger = 0.778691 ← T124199
        agent:105.immunity = 0.121199 ← T124199
        agent:105.region = region:5 ← T107130
        region:5.food_stock = 0.0 ← T125233
        region:5.population = 11 ← T125163
      Writes:
        agent:105.hunger: 0.778691 → 0.848691
        agent:105.immunity: 0.121199 → 0.114106
      T127138 AgentSystem.agents.census (tick 61)
      Inputs:
        agent:105.alive = true ← T9
        agent:105.region = region:5 ← T107130
        agent:111.alive = true ← T16
        agent:111.region = region:5 ← T88779
        agent:131.alive = false ← T111266
        agent:131.region = region:5 ← T107131
        agent:15.alive = false ← T123260
        agent:15.region = region:5 ← T58
        … 22 more input(s)
      Writes:
        region:5.population: 11 → 10
        region:5.workers: 11 → 10
      T127207 StableSoilAgricultureSystem.agriculture.harvest (tick 61)
      Inputs:
        region:5.food_stock = 0.0 ← T125233
        region:5.population = 11 ← T125163
        region:5.rainfall = 0.42674 ← T125173
        region:5.soil_fertility = 0.476468 ← T1006
        region:5.temperature = 24.070148 ← T125173
        region:5.workers = 11 ← T125163
      Random:
        agriculture.crop_variance@region:5 = 0.90235
      Writes:
        region:5.food_stock: 0.0 → 0.0
    T129111 AgentSystem.agents.census (tick 62)
    Inputs:
      agent:105.alive = true ← T9
      agent:105.region = region:5 ← T107130
      agent:111.alive = true ← T16
      agent:111.region = region:5 ← T88779
      agent:131.alive = false ← T111266
      agent:131.region = region:5 ← T107131
      agent:15.alive = false ← T123260
      agent:15.region = region:5 ← T58
      … 20 more input(s)
    Writes:
      region:5.population: 10 → 9
      region:5.workers: 10 → 9
      T9 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:105 = 0.181909
        genesis.attribute@agent:105 = 0.478079
        genesis.attribute@agent:105 = 0.098673
        genesis.attribute@agent:105 = 0.395967
      Writes:
        agent:105.alive: none → true
        agent:105.health: none → 70.457256
        agent:105.hunger: none → 0.243424
        agent:105.immune_memory: none → 0.0
        agent:105.immunity: none → 0.30427
        agent:105.infected: none → false
        agent:105.region: none → region:5
        agent:105.risk_tolerance: none → 0.395967
      T16 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:111 = 0.350696
        genesis.attribute@agent:111 = 0.098123
        genesis.attribute@agent:111 = 0.193
        genesis.attribute@agent:111 = 0.502584
      Writes:
        agent:111.alive: none → true
        agent:111.health: none → 75.520891
        agent:111.hunger: none → 0.129437
        agent:111.immune_memory: none → 0.0
        agent:111.immunity: none → 0.35615
        agent:111.infected: none → false
        agent:111.region: none → region:1
        agent:111.risk_tolerance: none → 0.502584
      T58 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:15 = 0.706386
        genesis.attribute@agent:15 = 0.363331
        genesis.attribute@agent:15 = 0.540488
        genesis.attribute@agent:15 = 0.053071
      Writes:
        agent:15.alive: none → true
        agent:15.health: none → 86.191588
        agent:15.hunger: none → 0.208999
        agent:15.immune_memory: none → 0.0
        agent:15.immunity: none → 0.547268
        agent:15.infected: none → false
        agent:15.region: none → region:5
        agent:15.risk_tolerance: none → 0.053071
      T86 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:175 = 0.035496
        genesis.attribute@agent:175 = 0.341642
        genesis.attribute@agent:175 = 0.72494
        genesis.attribute@agent:175 = 0.044676
      Writes:
        agent:175.alive: none → true
        agent:175.health: none → 66.064877
        agent:175.hunger: none → 0.202492
        agent:175.immune_memory: none → 0.0
        agent:175.immunity: none → 0.648717
        agent:175.infected: none → false
        agent:175.region: none → region:5
        agent:175.risk_tolerance: none → 0.044676
      … 19 more parent(s)
    T129169 StableSoilAgricultureSystem.agriculture.harvest (tick 62)
    Inputs:
      region:5.food_stock = 0.0 ← T127207
      region:5.population = 10 ← T127138
      region:5.rainfall = 0.415128 ← T127148
      region:5.soil_fertility = 0.476468 ← T1006
      region:5.temperature = 22.924354 ← T127148
      region:5.workers = 10 ← T127138
    Random:
      agriculture.crop_variance@region:5 = 0.261506
    Writes:
      region:5.food_stock: 0.0 → 0.0
      T1006 GenesisSystem.genesis.region (tick 0)
      Random:
        genesis.attribute@region:5 = 0.943997
        genesis.attribute@region:5 = 0.132848
        genesis.attribute@region:5 = 0.058818
        genesis.attribute@region:5 = 0.792334
        genesis.attribute@region:5 = 0.20836
        genesis.attribute@region:5 = 0.182978
        genesis.attribute@region:5 = 0.040226
        genesis.attribute@region:5 = 0.275863
      Writes:
        region:5.climate_volatility: none → 1.292334
        region:5.disease_base: none → 0.158045
        region:5.disease_load: none → 0.094827
        region:5.food_stock: none → 1420.690479
        region:5.population: none → 100
        region:5.rainfall: none → 0.346377
        region:5.rainfall_base: none → 0.409782
        region:5.soil_fertility: none → 0.476468
        region:5.temperature: none → 20.049396
        region:5.temperature_base: none → 21.215957
        region:5.workers: none → 100
      T127138 AgentSystem.agents.census (tick 61)
      Inputs:
        agent:105.alive = true ← T9
        agent:105.region = region:5 ← T107130
        agent:111.alive = true ← T16
        agent:111.region = region:5 ← T88779
        agent:131.alive = false ← T111266
        agent:131.region = region:5 ← T107131
        agent:15.alive = false ← T123260
        agent:15.region = region:5 ← T58
        … 22 more input(s)
      Writes:
        region:5.population: 11 → 10
        region:5.workers: 11 → 10
      T127148 ClimateSystem.climate.step (tick 61)
      Inputs:
        region:5.climate_volatility = 1.292334 ← T1006
        region:5.rainfall = 0.42674 ← T125173
        region:5.rainfall_base = 0.409782 ← T1006
        region:5.temperature = 24.070148 ← T125173
        region:5.temperature_base = 21.215957 ← T1006
      Random:
        climate.temperature_noise@region:5 = 0.366212
        climate.rain@region:5 = 0.431501
      Writes:
        region:5.rainfall: 0.42674 → 0.415128
        region:5.temperature: 24.070148 → 22.924354
      T127207 StableSoilAgricultureSystem.agriculture.harvest (tick 61)
      Inputs:
        region:5.food_stock = 0.0 ← T125233
        region:5.population = 11 ← T125163
        region:5.rainfall = 0.42674 ← T125173
        region:5.soil_fertility = 0.476468 ← T1006
        region:5.temperature = 24.070148 ← T125173
        region:5.workers = 11 ← T125163
      Random:
        agriculture.crop_variance@region:5 = 0.90235
      Writes:
        region:5.food_stock: 0.0 → 0.0
```

## Reproduction

```bash
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 4000 --ruleset stable_soil --db runs/survival_seed7_stable_soil.db --report <path>
```

Same seed + kernel v0.1.0 + ruleset 0.3.1b → bit-identical world, identical traces, identical report.