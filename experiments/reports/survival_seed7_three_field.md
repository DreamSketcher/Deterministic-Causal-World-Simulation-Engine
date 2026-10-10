# Causal survival experiment — seed 7

Kernel **v0.1 (frozen)**, ruleset **0.3.3h** — the laws
differ from the baseline by proposal only; the kernel, the purposes
and the addressable draw stream are unchanged.

> Experiment H (three-field): 200 ticks of cultivation force 100 ticks of fallow (+0.003 soil/tick), cycles phase-staggered.

## Run

| parameter | value |
|---|---|
| seed | 7 |
| ruleset | 0.3.3h |
| regions | 10 |
| agents | 1000 |
| ticks | 10000 |
| wall time | 639s |
| archive | `runs/survival_seed7_three_field.db` |
| survivors | 0 / 1000 |
| deaths | 1000 |
| last death | tick 1382 |

## Lifespan distribution (all agents died: no censoring)

| pct | ticks |
|---|---|
| p0 | 28 |
| p10 | 77 |
| p25 | 108 |
| p50 | 154 |
| p75 | 174 |
| p90 | 221 |
| p100 | 1382 |

mean lifespan: **169** ticks

## Statistical regularity: correlations with lifespan

| observable | pearson | spearman |
|---|---|---|
| initial_health | +0.024 | +0.018 |
| initial_immunity | +0.043 | +0.079 |
| risk_tolerance | -0.046 | +0.069 |
| migration_count | +0.401 | +0.375 |
| infection_count | +0.649 | +0.382 |
| avg_food_access | +0.672 | +0.184 |
| avg_social_density | -0.633 | +0.286 |

## Individual causality: death mechanisms (from traces)

| mechanism | deaths | share |
|---|---|---|
| disease+starvation | 956 | 95.6% |
| acute_infection | 36 | 3.6% |
| disease | 8 | 0.8% |

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
| stayers (0 migrations) | 74 | 115 | 2 | 5 | 67 |
| migrants (>=1 migration) | 926 | 173 | 34 | 3 | 889 |

### Risk tolerance quartiles

| group | n | mean lifespan | acute_infection | disease | disease+starvation |
|---|---|---|---|---|---|
| risk Q1 (lowest) | 250 | 161 | 9 | 2 | 239 |
| risk Q2 | 250 | 199 | 11 | 1 | 238 |
| risk Q3 | 250 | 164 | 5 | 2 | 243 |
| risk Q4 (highest) | 250 | 152 | 11 | 3 | 236 |

## Example mechanical explanations

### agent:102 — disease (died tick 83, T165271)

```
T165271 AgentSystem.agent.death (tick 83)
Inputs:
  agent:102.alive = true ← T6
  agent:102.health = 1.023145 ← T163486
  agent:102.hunger = 0.0 ← T164235
  agent:102.infected = true ← T159853
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
  T159853 ImmuneDiseaseSystem.disease.infect (tick 79)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 16.812727 ← T156389
    agent:102.hunger = 0.0 ← T157134
    agent:102.immune_memory = 0.7 ← T126723
    agent:102.immunity = 0.427132 ← T157134
    agent:102.infected = false ← T152815
    agent:102.region = region:2 ← T6
    region:2.disease_load = 0.231646 ← T158098
  Random:
    disease.infection@agent:102 = 0.00308 threshold=0.016212
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
    T126723 ImmuneDiseaseSystem.disease.infect (tick 61)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 55.187459 ← T122910
      agent:102.hunger = 0.0 ← T123787
      agent:102.immune_memory = 0.35 ← T78552
      agent:102.immunity = 0.429694 ← T123787
      agent:102.infected = false ← T114950
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.283698 ← T124782
    Random:
      disease.infection@agent:102 = 0.019219 threshold=0.034332
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
      T78552 ImmuneDiseaseSystem.disease.infect (tick 37)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 100.0 ← T74474
        agent:102.hunger = 0.0 ← T75408
        agent:102.immune_memory = 0.0 ← T6
        agent:102.immunity = 0.43349 ← T75408
        agent:102.infected = false ← T6
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.309404 ← T76454
      Random:
        disease.infection@agent:102 = 0.011169 threshold=0.053053
        disease.infection@agent:102 = 0.131254
      Writes:
        agent:102.health: 100.0 → 92.687459
        agent:102.immune_memory: 0.0 → 0.35
        agent:102.infected: false → true
      T114950 ImmuneDiseaseSystem.disease.recover (tick 55)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T111874
        agent:102.immune_memory = 0.35 ← T78552
        agent:102.immunity = 0.430601 ← T111874
        agent:102.infected = true ← T78552
      Random:
        disease.recovery@agent:102 = 0.118911 threshold=0.19765
      Writes:
        agent:102.infected: true → false
      T122910 AgentSystem.agent.health (tick 60)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 53.687459 ← T120945
        agent:102.hunger = 0.0 ← T121836
        agent:102.infected = false ← T114950
      Writes:
        agent:102.health: 53.687459 → 55.187459
      … 2 more parent(s)
    T152815 ImmuneDiseaseSystem.disease.recover (tick 75)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.hunger = 0.0 ← T150044
      agent:102.immune_memory = 0.7 ← T126723
      agent:102.immunity = 0.427682 ← T150044
      agent:102.infected = true ← T126723
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
      T126723 ImmuneDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T122910
        agent:102.hunger = 0.0 ← T123787
        agent:102.immune_memory = 0.35 ← T78552
        agent:102.immunity = 0.429694 ← T123787
        agent:102.infected = false ← T114950
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.283698 ← T124782
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.034332
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T150044 AgentSystem.agent.metabolism (tick 74)
      Inputs:
        agent:102.hunger = 0.0 ← T148144
        agent:102.immunity = 0.427821 ← T148144
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1526.390484 ← T149167
        region:2.population = 137 ← T149094
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.427821 → 0.427682
    T156389 AgentSystem.agent.health (tick 78)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 15.312727 ← T154618
      agent:102.hunger = 0.0 ← T155363
      agent:102.infected = false ← T152815
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
      T152815 ImmuneDiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T150044
        agent:102.immune_memory = 0.7 ← T126723
        agent:102.immunity = 0.427682 ← T150044
        agent:102.infected = true ← T126723
      Random:
        disease.recovery@agent:102 = 0.244162 threshold=0.26692
      Writes:
        agent:102.infected: true → false
      T154618 AgentSystem.agent.health (tick 77)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 13.812727 ← T152850
        agent:102.hunger = 0.0 ← T153609
        agent:102.infected = false ← T152815
      Writes:
        agent:102.health: 13.812727 → 15.312727
      T155363 AgentSystem.agent.metabolism (tick 77)
      Inputs:
        agent:102.hunger = 0.0 ← T153609
        agent:102.immunity = 0.427406 ← T153609
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1445.44321 ← T154603
        region:2.population = 150 ← T154544
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.427406 → 0.427269
    … 2 more parent(s)
  T163486 AgentSystem.agent.health (tick 82)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 3.523145 ← T161681
    agent:102.hunger = 0.0 ← T162428
    agent:102.infected = true ← T159853
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
    T159853 ImmuneDiseaseSystem.disease.infect (tick 79)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 16.812727 ← T156389
      agent:102.hunger = 0.0 ← T157134
      agent:102.immune_memory = 0.7 ← T126723
      agent:102.immunity = 0.427132 ← T157134
      agent:102.infected = false ← T152815
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.231646 ← T158098
    Random:
      disease.infection@agent:102 = 0.00308 threshold=0.016212
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
      T126723 ImmuneDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T122910
        agent:102.hunger = 0.0 ← T123787
        agent:102.immune_memory = 0.35 ← T78552
        agent:102.immunity = 0.429694 ← T123787
        agent:102.infected = false ← T114950
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.283698 ← T124782
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.034332
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T152815 ImmuneDiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T150044
        agent:102.immune_memory = 0.7 ← T126723
        agent:102.immunity = 0.427682 ← T150044
        agent:102.infected = true ← T126723
      Random:
        disease.recovery@agent:102 = 0.244162 threshold=0.26692
      Writes:
        agent:102.infected: true → false
      T156389 AgentSystem.agent.health (tick 78)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 15.312727 ← T154618
        agent:102.hunger = 0.0 ← T155363
        agent:102.infected = false ← T152815
      Writes:
        agent:102.health: 15.312727 → 16.812727
      … 2 more parent(s)
    T161681 AgentSystem.agent.health (tick 81)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 6.023145 ← T159898
      agent:102.hunger = 0.0 ← T160648
      agent:102.infected = true ← T159853
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
      T159853 ImmuneDiseaseSystem.disease.infect (tick 79)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 16.812727 ← T156389
        agent:102.hunger = 0.0 ← T157134
        agent:102.immune_memory = 0.7 ← T126723
        agent:102.immunity = 0.427132 ← T157134
        agent:102.infected = false ← T152815
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.231646 ← T158098
      Random:
        disease.infection@agent:102 = 0.00308 threshold=0.016212
        disease.infection@agent:102 = 0.829238
      Writes:
        agent:102.health: 16.812727 → 8.523145
        agent:102.immune_memory: 0.7 → 1.0
        agent:102.infected: false → true
      T159898 AgentSystem.agent.health (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 8.523145 ← T159853
        agent:102.hunger = 0.0 ← T158895
        agent:102.infected = true ← T159853
      Writes:
        agent:102.health: 8.523145 → 6.023145
      T160648 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T158895
        agent:102.immunity = 0.426997 ← T158895
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1326.541329 ← T159886
        region:2.population = 145 ← T159825
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
    T162428 AgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T160648
      agent:102.immunity = 0.426862 ← T160648
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1339.664737 ← T161664
      region:2.population = 144 ← T161606
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
      T160648 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T158895
        agent:102.immunity = 0.426997 ← T158895
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1326.541329 ← T159886
        region:2.population = 145 ← T159825
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
      T161606 AgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 302 more input(s)
      Writes:
        region:2.population: 145 → 144
        region:2.workers: 145 → 144
      T161664 ThreeFieldAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.cultivation_streak = 120 ← T159886
        region:2.fallow_timer = 0 ← T159886
        region:2.food_stock = 1326.541329 ← T159886
        region:2.population = 145 ← T159825
        region:2.rainfall = 0.577858 ← T159835
        region:2.soil_fertility = 0.421909 ← T159886
        region:2.temperature = 18.934401 ← T159835
        region:2.workers = 145 ← T159825
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.cultivation_streak: 120 → 121
        region:2.fallow_timer: 0 → 0
        region:2.food_stock: 1326.541329 → 1339.664737
        region:2.soil_fertility: 0.421909 → 0.421009
  T164235 AgentSystem.agent.metabolism (tick 82)
  Inputs:
    agent:102.hunger = 0.0 ← T162428
    agent:102.immunity = 0.426727 ← T162428
    agent:102.region = region:2 ← T6
    region:2.food_stock = 1289.604876 ← T163470
    region:2.population = 140 ← T163390
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
    T162428 AgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T160648
      agent:102.immunity = 0.426862 ← T160648
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1339.664737 ← T161664
      region:2.population = 144 ← T161606
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
      T160648 AgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T158895
        agent:102.immunity = 0.426997 ← T158895
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1326.541329 ← T159886
        region:2.population = 145 ← T159825
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.426997 → 0.426862
      T161606 AgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 302 more input(s)
      Writes:
        region:2.population: 145 → 144
        region:2.workers: 145 → 144
      T161664 ThreeFieldAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.cultivation_streak = 120 ← T159886
        region:2.fallow_timer = 0 ← T159886
        region:2.food_stock = 1326.541329 ← T159886
        region:2.population = 145 ← T159825
        region:2.rainfall = 0.577858 ← T159835
        region:2.soil_fertility = 0.421909 ← T159886
        region:2.temperature = 18.934401 ← T159835
        region:2.workers = 145 ← T159825
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.cultivation_streak: 120 → 121
        region:2.fallow_timer: 0 → 0
        region:2.food_stock: 1326.541329 → 1339.664737
        region:2.soil_fertility: 0.421909 → 0.421009
    T163390 AgentSystem.agents.census (tick 81)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.region = region:2 ← T6
      agent:112.alive = true ← T17
      agent:112.region = region:2 ← T17
      agent:12.alive = true ← T25
      agent:12.region = region:2 ← T25
      agent:122.alive = true ← T28
      agent:122.region = region:2 ← T28
      … 294 more input(s)
    Writes:
      region:2.population: 144 → 140
      region:2.workers: 144 → 140
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
      … 198 more parent(s)
    T163470 ThreeFieldAgricultureSystem.agriculture.harvest (tick 81)
    Inputs:
      region:2.cultivation_streak = 121 ← T161664
      region:2.fallow_timer = 0 ← T161664
      region:2.food_stock = 1339.664737 ← T161664
      region:2.population = 144 ← T161606
      region:2.rainfall = 0.568902 ← T161616
      region:2.soil_fertility = 0.421009 ← T161664
      region:2.temperature = 19.003536 ← T161616
      region:2.workers = 144 ← T161606
    Random:
      agriculture.crop_variance@region:2 = 0.024179
    Writes:
      region:2.cultivation_streak: 121 → 122
      region:2.fallow_timer: 0 → 0
      region:2.food_stock: 1339.664737 → 1289.604876
      region:2.soil_fertility: 0.421009 → 0.420109
      T161606 AgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 302 more input(s)
      Writes:
        region:2.population: 145 → 144
        region:2.workers: 145 → 144
      T161616 ClimateSystem.climate.step (tick 80)
      Inputs:
        region:2.climate_volatility = 0.508114 ← T1003
        region:2.rainfall = 0.577858 ← T159835
        region:2.rainfall_base = 0.553388 ← T1003
        region:2.temperature = 18.934401 ← T159835
        region:2.temperature_base = 18.487763 ← T1003
      Random:
        climate.temperature_noise@region:2 = 0.642326
        climate.rain@region:2 = 0.466151
      Writes:
        region:2.rainfall: 0.577858 → 0.568902
        region:2.temperature: 18.934401 → 19.003536
      T161664 ThreeFieldAgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.cultivation_streak = 120 ← T159886
        region:2.fallow_timer = 0 ← T159886
        region:2.food_stock = 1326.541329 ← T159886
        region:2.population = 145 ← T159825
        region:2.rainfall = 0.577858 ← T159835
        region:2.soil_fertility = 0.421909 ← T159886
        region:2.temperature = 18.934401 ← T159835
        region:2.workers = 145 ← T159825
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.cultivation_streak: 120 → 121
        region:2.fallow_timer: 0 → 0
        region:2.food_stock: 1326.541329 → 1339.664737
        region:2.soil_fertility: 0.421909 → 0.421009
```

### agent:108 — acute_infection (died tick 96, T190010)

```
T190010 ImmuneDiseaseSystem.disease.infect (tick 96)
Inputs:
  agent:108.alive = true ← T12
  agent:108.health = 2.007028 ← T186728
  agent:108.hunger = 0.97 ← T187430
  agent:108.immune_memory = 0.7 ← T139560
  agent:108.immunity = 0.269137 ← T187430
  agent:108.infected = false ← T143412
  agent:108.region = region:2 ← T186597
  region:2.disease_load = 0.206463 ← T188334
Random:
  disease.infection@agent:108 = 0.013703 threshold=0.057798
  disease.infection@agent:108 = 0.634362
Writes:
  agent:108.alive: true → false
  agent:108.health: 2.007028 → 0.0
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
  T139560 ImmuneDiseaseSystem.disease.infect (tick 68)
  Inputs:
    agent:108.alive = true ← T12
    agent:108.health = 72.429254 ← T128613
    agent:108.hunger = 0.7 ← T136731
    agent:108.immune_memory = 0.35 ← T118902
    agent:108.immunity = 0.541699 ← T136731
    agent:108.infected = false ← T130404
    agent:108.region = region:8 ← T12
    region:8.disease_load = 0.274081 ← T137730
  Random:
    disease.infection@agent:108 = 0.054451 threshold=0.077326
    disease.infection@agent:108 = 0.845851
  Writes:
    agent:108.health: 72.429254 → 61.007028
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
    T118902 ImmuneDiseaseSystem.disease.infect (tick 57)
    Inputs:
      agent:108.alive = true ← T12
      agent:108.health = 100.0 ← T115017
      agent:108.hunger = 0.0 ← T115910
      agent:108.immune_memory = 0.0 ← T12
      agent:108.immunity = 0.58981 ← T115910
      agent:108.infected = false ← T12
      agent:108.region = region:8 ← T12
      region:8.disease_load = 0.33978 ← T116925
    Random:
      disease.infection@agent:108 = 0.023595 threshold=0.047107
      disease.infection@agent:108 = 0.657075
    Writes:
      agent:108.health: 100.0 → 87.429254
      agent:108.immune_memory: 0.0 → 0.35
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
      T115017 AgentSystem.agent.health (tick 56)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.health = 100.0 ← T113010
        agent:108.hunger = 0.0 ← T113915
        agent:108.infected = false ← T12
      Writes:
        agent:108.health: 100.0 → 100.0
      T115910 AgentSystem.agent.metabolism (tick 56)
      Inputs:
        agent:108.hunger = 0.0 ← T113915
        agent:108.immunity = 0.590764 ← T113915
        agent:108.region = region:8 ← T12
        region:8.food_stock = 265.433568 ← T115000
        region:8.population = 127 ← T114907
      Writes:
        agent:108.hunger: 0.0 → 0.0
        agent:108.immunity: 0.590764 → 0.58981
      T116925 ImmuneDiseaseSystem.disease.environment (tick 56)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.infected = false ← T12
        agent:108.region = region:8 ← T12
        agent:118.alive = true ← T23
        agent:118.infected = false ← T86843
        agent:118.region = region:8 ← T23
        agent:121.alive = true ← T27
        agent:121.infected = false ← T98875
        … 384 more input(s)
      Random:
        disease.load_noise@region:8 = 0.923089
      Writes:
        region:8.disease_load: 0.336049 → 0.33978
    T128613 AgentSystem.agent.health (tick 63)
    Inputs:
      agent:108.alive = true ← T12
      agent:108.health = 74.929254 ← T126795
      agent:108.hunger = 0.35 ← T127570
      agent:108.infected = true ← T118902
    Writes:
      agent:108.health: 74.929254 → 72.429254
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
      T118902 ImmuneDiseaseSystem.disease.infect (tick 57)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.health = 100.0 ← T115017
        agent:108.hunger = 0.0 ← T115910
        agent:108.immune_memory = 0.0 ← T12
        agent:108.immunity = 0.58981 ← T115910
        agent:108.infected = false ← T12
        agent:108.region = region:8 ← T12
        region:8.disease_load = 0.33978 ← T116925
      Random:
        disease.infection@agent:108 = 0.023595 threshold=0.047107
        disease.infection@agent:108 = 0.657075
      Writes:
        agent:108.health: 100.0 → 87.429254
        agent:108.immune_memory: 0.0 → 0.35
        agent:108.infected: false → true
      T126795 AgentSystem.agent.health (tick 62)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.health = 77.429254 ← T124861
        agent:108.hunger = 0.28 ← T125735
        agent:108.infected = true ← T118902
      Writes:
        agent:108.health: 77.429254 → 74.929254
      T127570 AgentSystem.agent.metabolism (tick 62)
      Inputs:
        agent:108.hunger = 0.28 ← T125735
        agent:108.immunity = 0.578147 ← T125735
        agent:108.region = region:8 ← T12
        region:8.food_stock = 0.0 ← T126782
        region:8.population = 120 ← T126701
      Writes:
        agent:108.hunger: 0.28 → 0.35
        agent:108.immunity: 0.578147 → 0.573756
    T130404 ImmuneDiseaseSystem.disease.recover (tick 63)
    Inputs:
      agent:108.alive = true ← T12
      agent:108.hunger = 0.35 ← T127570
      agent:108.immune_memory = 0.35 ← T118902
      agent:108.immunity = 0.573756 ← T127570
      agent:108.infected = true ← T118902
    Random:
      disease.recovery@agent:108 = 0.131379 threshold=0.180939
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
      T118902 ImmuneDiseaseSystem.disease.infect (tick 57)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.health = 100.0 ← T115017
        agent:108.hunger = 0.0 ← T115910
        agent:108.immune_memory = 0.0 ← T12
        agent:108.immunity = 0.58981 ← T115910
        agent:108.infected = false ← T12
        agent:108.region = region:8 ← T12
        region:8.disease_load = 0.33978 ← T116925
      Random:
        disease.infection@agent:108 = 0.023595 threshold=0.047107
        disease.infection@agent:108 = 0.657075
      Writes:
        agent:108.health: 100.0 → 87.429254
        agent:108.immune_memory: 0.0 → 0.35
        agent:108.infected: false → true
      T127570 AgentSystem.agent.metabolism (tick 62)
      Inputs:
        agent:108.hunger = 0.28 ← T125735
        agent:108.immunity = 0.578147 ← T125735
        agent:108.region = region:8 ← T12
        region:8.food_stock = 0.0 ← T126782
        region:8.population = 120 ← T126701
      Writes:
        agent:108.hunger: 0.28 → 0.35
        agent:108.immunity: 0.578147 → 0.573756
    … 2 more parent(s)
  T143412 ImmuneDiseaseSystem.disease.recover (tick 70)
  Inputs:
    agent:108.alive = true ← T12
    agent:108.hunger = 0.84 ← T140487
    agent:108.immune_memory = 0.7 ← T139560
    agent:108.immunity = 0.524224 ← T140487
    agent:108.infected = true ← T139560
  Random:
    disease.recovery@agent:108 = 0.079415 threshold=0.165056
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
    T139560 ImmuneDiseaseSystem.disease.infect (tick 68)
    Inputs:
      agent:108.alive = true ← T12
      agent:108.health = 72.429254 ← T128613
      agent:108.hunger = 0.7 ← T136731
      agent:108.immune_memory = 0.35 ← T118902
      agent:108.immunity = 0.541699 ← T136731
      agent:108.infected = false ← T130404
      agent:108.region = region:8 ← T12
      region:8.disease_load = 0.274081 ← T137730
    Random:
      disease.infection@agent:108 = 0.054451 threshold=0.077326
      disease.infection@agent:108 = 0.845851
    Writes:
      agent:108.health: 72.429254 → 61.007028
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
      T118902 ImmuneDiseaseSystem.disease.infect (tick 57)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.health = 100.0 ← T115017
        agent:108.hunger = 0.0 ← T115910
        agent:108.immune_memory = 0.0 ← T12
        agent:108.immunity = 0.58981 ← T115910
        agent:108.infected = false ← T12
        agent:108.region = region:8 ← T12
        region:8.disease_load = 0.33978 ← T116925
      Random:
        disease.infection@agent:108 = 0.023595 threshold=0.047107
        disease.infection@agent:108 = 0.657075
      Writes:
        agent:108.health: 100.0 → 87.429254
        agent:108.immune_memory: 0.0 → 0.35
        agent:108.infected: false → true
      T128613 AgentSystem.agent.health (tick 63)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.health = 74.929254 ← T126795
        agent:108.hunger = 0.35 ← T127570
        agent:108.infected = true ← T118902
      Writes:
        agent:108.health: 74.929254 → 72.429254
      T130404 ImmuneDiseaseSystem.disease.recover (tick 63)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.hunger = 0.35 ← T127570
        agent:108.immune_memory = 0.35 ← T118902
        agent:108.immunity = 0.573756 ← T127570
        agent:108.infected = true ← T118902
      Random:
        disease.recovery@agent:108 = 0.131379 threshold=0.180939
      Writes:
        agent:108.infected: true → false
      … 2 more parent(s)
    T140487 AgentSystem.agent.metabolism (tick 69)
    Inputs:
      agent:108.hunger = 0.77 ← T138571
      agent:108.immunity = 0.533291 ← T138571
      agent:108.region = region:8 ← T12
      region:8.food_stock = 0.0 ← T139605
      region:8.population = 65 ← T139538
    Writes:
      agent:108.hunger: 0.77 → 0.84
      agent:108.immunity: 0.533291 → 0.524224
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
      T138571 AgentSystem.agent.metabolism (tick 68)
      Inputs:
        agent:108.hunger = 0.7 ← T136731
        agent:108.immunity = 0.541699 ← T136731
        agent:108.region = region:8 ← T12
        region:8.food_stock = 0.0 ← T137773
        region:8.population = 80 ← T137710
      Writes:
        agent:108.hunger: 0.7 → 0.77
        agent:108.immunity: 0.541699 → 0.533291
      T139538 AgentSystem.agents.census (tick 68)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.region = region:8 ← T12
        agent:118.alive = true ← T23
        agent:118.region = region:8 ← T23
        agent:149.alive = false ← T135939
        agent:149.region = region:8 ← T133983
        agent:155.alive = true ← T64
        agent:155.region = region:8 ← T76403
        … 130 more input(s)
      Writes:
        region:8.population: 80 → 65
        region:8.workers: 80 → 65
      T139605 ThreeFieldAgricultureSystem.agriculture.harvest (tick 68)
      Inputs:
        region:8.cultivation_streak = 0 ← T137773
        region:8.fallow_timer = 72 ← T137773
        region:8.food_stock = 0.0 ← T137773
        region:8.population = 80 ← T137710
        region:8.soil_fertility = 0.614641 ← T137773
      Writes:
        region:8.cultivation_streak: 0 → 0
        region:8.fallow_timer: 72 → 71
        region:8.food_stock: 0.0 → 0.0
        region:8.soil_fertility: 0.614641 → 0.617641
  T186597 AgentSystem.agent.migrate (tick 94)
  Inputs:
    agent:108.hunger = 1.0 ← T184074
    agent:108.region = region:1 ← T158027
    agent:108.risk_tolerance = 0.239165 ← T12
  Random:
    agent.decision@agent:108 = 0.090485 threshold=0.119583
  Writes:
    agent:108.region: region:1 → region:2
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
    T158027 AgentSystem.agent.migrate (tick 78)
    Inputs:
      agent:108.hunger = 0.91 ← T155368
      agent:108.region = region:0 ← T150946
      agent:108.risk_tolerance = 0.239165 ← T12
    Random:
      agent.decision@agent:108 = 0.076601 threshold=0.119583
    Writes:
      agent:108.region: region:0 → region:1
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
      T150946 AgentSystem.agent.migrate (tick 74)
      Inputs:
        agent:108.hunger = 1.0 ← T148149
        agent:108.region = region:9 ← T141393
        agent:108.risk_tolerance = 0.239165 ← T12
      Random:
        agent.decision@agent:108 = 0.061947 threshold=0.119583
      Writes:
        agent:108.region: region:9 → region:0
      T155368 AgentSystem.agent.metabolism (tick 77)
      Inputs:
        agent:108.hunger = 0.94 ← T153614
        agent:108.immunity = 0.452949 ← T153614
        agent:108.region = region:0 ← T150946
        region:0.food_stock = 326.162178 ← T154601
        region:0.population = 150 ← T154542
      Writes:
        agent:108.hunger: 0.94 → 0.91
        agent:108.immunity: 0.452949 → 0.443585
    T184074 AgentSystem.agent.metabolism (tick 93)
    Inputs:
      agent:108.hunger = 1.0 ← T182384
      agent:108.immunity = 0.297153 ← T182384
      agent:108.region = region:1 ← T158027
      region:1.food_stock = 0.0 ← T183348
      region:1.population = 29 ← T183287
    Writes:
      agent:108.hunger: 1.0 → 1.0
      agent:108.immunity: 0.297153 → 0.287667
      T158027 AgentSystem.agent.migrate (tick 78)
      Inputs:
        agent:108.hunger = 0.91 ← T155368
        agent:108.region = region:0 ← T150946
        agent:108.risk_tolerance = 0.239165 ← T12
      Random:
        agent.decision@agent:108 = 0.076601 threshold=0.119583
      Writes:
        agent:108.region: region:0 → region:1
      T182384 AgentSystem.agent.metabolism (tick 92)
      Inputs:
        agent:108.hunger = 1.0 ← T180680
        agent:108.immunity = 0.306686 ← T180680
        agent:108.region = region:1 ← T158027
        region:1.food_stock = 0.0 ← T181651
        region:1.population = 27 ← T181591
      Writes:
        agent:108.hunger: 1.0 → 1.0
        agent:108.immunity: 0.306686 → 0.297153
      T183287 AgentSystem.agents.census (tick 92)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.region = region:1 ← T158027
        agent:141.alive = false ← T115002
        agent:141.region = region:1 ← T49
        agent:148.alive = true ← T56
        agent:148.region = region:1 ← T181533
        agent:18.alive = true ← T91
        agent:18.region = region:1 ← T174506
        … 88 more input(s)
      Writes:
        region:1.population: 27 → 29
        region:1.workers: 27 → 29
      T183348 ThreeFieldAgricultureSystem.agriculture.harvest (tick 92)
      Inputs:
        region:1.cultivation_streak = 112 ← T181651
        region:1.fallow_timer = 0 ← T181651
        region:1.food_stock = 0.0 ← T181651
        region:1.population = 27 ← T181591
        region:1.rainfall = 0.287083 ← T181601
        region:1.soil_fertility = 0.447632 ← T181651
        region:1.temperature = 6.6908 ← T181601
        region:1.workers = 27 ← T181591
      Random:
        agriculture.crop_variance@region:1 = 0.194566
      Writes:
        region:1.cultivation_streak: 112 → 113
        region:1.fallow_timer: 0 → 0
        region:1.food_stock: 0.0 → 0.0
        region:1.soil_fertility: 0.447632 → 0.446732
  … 3 more parent(s)
```

## Reproduction

```bash
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset three_field --db runs/survival_seed7_three_field.db --report <path>
```

Same seed + kernel v0.1.0 + ruleset 0.3.3h → bit-identical world, identical traces, identical report.