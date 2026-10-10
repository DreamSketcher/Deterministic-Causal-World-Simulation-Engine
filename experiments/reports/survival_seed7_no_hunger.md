# Causal survival experiment — seed 7

Kernel **v0.1 (frozen)**, ruleset **0.3.1c** — the laws
differ from the baseline by proposal only; the kernel, the purposes
and the addressable draw stream are unchanged.

> Experiment C: hunger no longer raises susceptibility — neither directly (infection probability) nor via immunity erosion.

## Run

| parameter | value |
|---|---|
| seed | 7 |
| ruleset | 0.3.1c |
| regions | 10 |
| agents | 1000 |
| ticks | 10000 |
| wall time | 882s |
| archive | `runs/survival_seed7_no_hunger.db` |
| survivors | 0 / 1000 |
| deaths | 1000 |
| last death | tick 573 |

## Lifespan distribution (all agents died: no censoring)

| pct | ticks |
|---|---|
| p0 | 31 |
| p10 | 177 |
| p25 | 252 |
| p50 | 405 |
| p75 | 425 |
| p90 | 573 |
| p100 | 573 |

mean lifespan: **358** ticks

## Statistical regularity: correlations with lifespan

| observable | pearson | spearman |
|---|---|---|
| initial_health | -0.023 | -0.037 |
| initial_immunity | +0.010 | +0.010 |
| risk_tolerance | +0.029 | +0.039 |
| migration_count | +0.090 | +0.118 |
| infection_count | +0.484 | +0.435 |
| avg_food_access | +0.697 | +0.732 |
| avg_social_density | +0.669 | +0.634 |

## Individual causality: death mechanisms (from traces)

| mechanism | deaths | share |
|---|---|---|
| disease+starvation | 989 | 98.9% |
| acute_infection | 7 | 0.7% |
| disease | 4 | 0.4% |

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
| stayers (0 migrations) | 49 | 237 | 1 | 2 | 46 |
| migrants (>=1 migration) | 951 | 364 | 6 | 2 | 943 |

### Risk tolerance quartiles

| group | n | mean lifespan | acute_infection | disease | disease+starvation |
|---|---|---|---|---|---|
| risk Q1 (lowest) | 250 | 340 | 2 | 1 | 247 |
| risk Q2 | 250 | 380 | 3 | 1 | 246 |
| risk Q3 | 250 | 360 | 0 | 0 | 250 |
| risk Q4 (highest) | 250 | 352 | 2 | 2 | 246 |

## Example mechanical explanations

### agent:102 — disease (died tick 83, T168860)

```
T168860 NoHungerErosionAgentSystem.agent.death (tick 83)
Inputs:
  agent:102.alive = true ← T6
  agent:102.health = 1.023145 ← T166863
  agent:102.hunger = 0.0 ← T167828
  agent:102.infected = true ← T160849
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
  T160849 NoHungerDiseaseSystem.disease.infect (tick 79)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 16.812727 ← T158882
    agent:102.immune_memory = 0.7 ← T124696
    agent:102.immunity = 0.439469 ← T159845
    agent:102.infected = false ← T152863
    agent:102.region = region:2 ← T6
    region:2.disease_load = 0.209029 ← T158848
  Random:
    disease.infection@agent:102 = 0.00308 threshold=0.01441
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
    T124696 NoHungerDiseaseSystem.disease.infect (tick 61)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 55.187459 ← T122732
      agent:102.immune_memory = 0.35 ← T76125
      agent:102.immunity = 0.443195 ← T123670
      agent:102.infected = false ← T112639
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.24993 ← T122685
    Random:
      disease.infection@agent:102 = 0.019219 threshold=0.029748
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
      T76125 NoHungerDiseaseSystem.disease.infect (tick 37)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 100.0 ← T74136
        agent:102.immune_memory = 0.0 ← T6
        agent:102.immunity = 0.448717 ← T75058
        agent:102.infected = false ← T6
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.285683 ← T74056
      Random:
        disease.infection@agent:102 = 0.011169 threshold=0.048072
        disease.infection@agent:102 = 0.131254
      Writes:
        agent:102.health: 100.0 → 92.687459
        agent:102.immune_memory: 0.0 → 0.35
        agent:102.infected: false → true
      T112639 NoHungerDiseaseSystem.disease.recover (tick 55)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T111584
        agent:102.immune_memory = 0.35 ← T76125
        agent:102.immunity = 0.444514 ← T111584
        agent:102.infected = true ← T76125
      Random:
        disease.recovery@agent:102 = 0.118911 threshold=0.201129
      Writes:
        agent:102.infected: true → false
      T122685 NoHungerDiseaseSystem.disease.environment (tick 60)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.infected = false ← T112639
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.infected = false ← T102516
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.infected = false ← T60212
        … 348 more input(s)
      Random:
        disease.load_noise@region:2 = 0.640855
      Writes:
        region:2.disease_load: 0.252465 → 0.24993
      … 2 more parent(s)
    T152863 NoHungerDiseaseSystem.disease.recover (tick 75)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.hunger = 0.0 ← T151843
      agent:102.immune_memory = 0.7 ← T124696
      agent:102.immunity = 0.440268 ← T151843
      agent:102.infected = true ← T124696
    Random:
      disease.recovery@agent:102 = 0.244162 threshold=0.270067
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
      T124696 NoHungerDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T122732
        agent:102.immune_memory = 0.35 ← T76125
        agent:102.immunity = 0.443195 ← T123670
        agent:102.infected = false ← T112639
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.24993 ← T122685
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.029748
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T151843 NoHungerErosionAgentSystem.agent.metabolism (tick 74)
      Inputs:
        agent:102.hunger = 0.0 ← T149842
        agent:102.immunity = 0.44047 ← T149842
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1476.027925 ← T148808
        region:2.population = 114 ← T150813
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.44047 → 0.440268
    T158848 NoHungerDiseaseSystem.disease.environment (tick 78)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.infected = false ← T152863
      agent:102.region = region:2 ← T6
      agent:112.alive = true ← T17
      agent:112.infected = false ← T102516
      agent:112.region = region:2 ← T17
      agent:12.alive = true ← T25
      agent:12.infected = false ← T60212
      … 339 more input(s)
    Random:
      disease.load_noise@region:2 = 0.263997
    Writes:
      region:2.disease_load: 0.217442 → 0.209029
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
      … 239 more parent(s)
    … 2 more parent(s)
  T166863 NoHungerErosionAgentSystem.agent.health (tick 82)
  Inputs:
    agent:102.alive = true ← T6
    agent:102.health = 3.523145 ← T164866
    agent:102.hunger = 0.0 ← T165831
    agent:102.infected = true ← T160849
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
    T160849 NoHungerDiseaseSystem.disease.infect (tick 79)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 16.812727 ← T158882
      agent:102.immune_memory = 0.7 ← T124696
      agent:102.immunity = 0.439469 ← T159845
      agent:102.infected = false ← T152863
      agent:102.region = region:2 ← T6
      region:2.disease_load = 0.209029 ← T158848
    Random:
      disease.infection@agent:102 = 0.00308 threshold=0.01441
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
      T124696 NoHungerDiseaseSystem.disease.infect (tick 61)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 55.187459 ← T122732
        agent:102.immune_memory = 0.35 ← T76125
        agent:102.immunity = 0.443195 ← T123670
        agent:102.infected = false ← T112639
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.24993 ← T122685
      Random:
        disease.infection@agent:102 = 0.019219 threshold=0.029748
        disease.infection@agent:102 = 0.396801
      Writes:
        agent:102.health: 55.187459 → 47.312727
        agent:102.immune_memory: 0.35 → 0.7
        agent:102.infected: false → true
      T152863 NoHungerDiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.hunger = 0.0 ← T151843
        agent:102.immune_memory = 0.7 ← T124696
        agent:102.immunity = 0.440268 ← T151843
        agent:102.infected = true ← T124696
      Random:
        disease.recovery@agent:102 = 0.244162 threshold=0.270067
      Writes:
        agent:102.infected: true → false
      T158848 NoHungerDiseaseSystem.disease.environment (tick 78)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.infected = false ← T152863
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.infected = false ← T102516
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.infected = false ← T60212
        … 339 more input(s)
      Random:
        disease.load_noise@region:2 = 0.263997
      Writes:
        region:2.disease_load: 0.217442 → 0.209029
      … 2 more parent(s)
    T164866 NoHungerErosionAgentSystem.agent.health (tick 81)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.health = 6.023145 ← T162865
      agent:102.hunger = 0.0 ← T163829
      agent:102.infected = true ← T160849
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
      T160849 NoHungerDiseaseSystem.disease.infect (tick 79)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 16.812727 ← T158882
        agent:102.immune_memory = 0.7 ← T124696
        agent:102.immunity = 0.439469 ← T159845
        agent:102.infected = false ← T152863
        agent:102.region = region:2 ← T6
        region:2.disease_load = 0.209029 ← T158848
      Random:
        disease.infection@agent:102 = 0.00308 threshold=0.01441
        disease.infection@agent:102 = 0.829238
      Writes:
        agent:102.health: 16.812727 → 8.523145
        agent:102.immune_memory: 0.7 → 1.0
        agent:102.infected: false → true
      T162865 NoHungerErosionAgentSystem.agent.health (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.health = 8.523145 ← T160849
        agent:102.hunger = 0.0 ← T161839
        agent:102.infected = true ← T160849
      Writes:
        agent:102.health: 8.523145 → 6.023145
      T163829 NoHungerErosionAgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161839
        agent:102.immunity = 0.439271 ← T161839
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1286.986529 ← T160821
        region:2.population = 113 ← T162804
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.439271 → 0.439075
    T165831 NoHungerErosionAgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T163829
      agent:102.immunity = 0.439075 ← T163829
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1292.149754 ← T162814
      region:2.population = 113 ← T164794
    Writes:
      agent:102.hunger: 0.0 → 0.0
      agent:102.immunity: 0.439075 → 0.438879
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
      T162814 AgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1286.986529 ← T160821
        region:2.population = 113 ← T162804
        region:2.rainfall = 0.577858 ← T160831
        region:2.soil_fertility = 0.421909 ← T160821
        region:2.temperature = 18.934401 ← T160831
        region:2.workers = 113 ← T162804
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1286.986529 → 1292.149754
        region:2.soil_fertility: 0.421909 → 0.421009
      T163829 NoHungerErosionAgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161839
        agent:102.immunity = 0.439271 ← T161839
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1286.986529 ← T160821
        region:2.population = 113 ← T162804
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.439271 → 0.439075
      T164794 NoHungerErosionAgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 222 more input(s)
      Writes:
        region:2.population: 113 → 113
        region:2.workers: 113 → 113
  T167828 NoHungerErosionAgentSystem.agent.metabolism (tick 82)
  Inputs:
    agent:102.hunger = 0.0 ← T165831
    agent:102.immunity = 0.438879 ← T165831
    agent:102.region = region:2 ← T6
    region:2.food_stock = 1248.048966 ← T164804
    region:2.population = 113 ← T166796
  Writes:
    agent:102.hunger: 0.0 → 0.0
    agent:102.immunity: 0.438879 → 0.438685
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
    T164804 AgricultureSystem.agriculture.harvest (tick 81)
    Inputs:
      region:2.food_stock = 1292.149754 ← T162814
      region:2.population = 113 ← T164794
      region:2.rainfall = 0.568902 ← T162824
      region:2.soil_fertility = 0.421009 ← T162814
      region:2.temperature = 19.003536 ← T162824
      region:2.workers = 113 ← T164794
    Random:
      agriculture.crop_variance@region:2 = 0.024179
    Writes:
      region:2.food_stock: 1292.149754 → 1248.048966
      region:2.soil_fertility: 0.421009 → 0.420109
      T162814 AgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1286.986529 ← T160821
        region:2.population = 113 ← T162804
        region:2.rainfall = 0.577858 ← T160831
        region:2.soil_fertility = 0.421909 ← T160821
        region:2.temperature = 18.934401 ← T160831
        region:2.workers = 113 ← T162804
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1286.986529 → 1292.149754
        region:2.soil_fertility: 0.421909 → 0.421009
      T162824 ClimateSystem.climate.step (tick 80)
      Inputs:
        region:2.climate_volatility = 0.508114 ← T1003
        region:2.rainfall = 0.577858 ← T160831
        region:2.rainfall_base = 0.553388 ← T1003
        region:2.temperature = 18.934401 ← T160831
        region:2.temperature_base = 18.487763 ← T1003
      Random:
        climate.temperature_noise@region:2 = 0.642326
        climate.rain@region:2 = 0.466151
      Writes:
        region:2.rainfall: 0.577858 → 0.568902
        region:2.temperature: 18.934401 → 19.003536
      T164794 NoHungerErosionAgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 222 more input(s)
      Writes:
        region:2.population: 113 → 113
        region:2.workers: 113 → 113
    T165831 NoHungerErosionAgentSystem.agent.metabolism (tick 81)
    Inputs:
      agent:102.hunger = 0.0 ← T163829
      agent:102.immunity = 0.439075 ← T163829
      agent:102.region = region:2 ← T6
      region:2.food_stock = 1292.149754 ← T162814
      region:2.population = 113 ← T164794
    Writes:
      agent:102.hunger: 0.0 → 0.0
      agent:102.immunity: 0.439075 → 0.438879
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
      T162814 AgricultureSystem.agriculture.harvest (tick 80)
      Inputs:
        region:2.food_stock = 1286.986529 ← T160821
        region:2.population = 113 ← T162804
        region:2.rainfall = 0.577858 ← T160831
        region:2.soil_fertility = 0.421909 ← T160821
        region:2.temperature = 18.934401 ← T160831
        region:2.workers = 113 ← T162804
      Random:
        agriculture.crop_variance@region:2 = 0.677832
      Writes:
        region:2.food_stock: 1286.986529 → 1292.149754
        region:2.soil_fertility: 0.421909 → 0.421009
      T163829 NoHungerErosionAgentSystem.agent.metabolism (tick 80)
      Inputs:
        agent:102.hunger = 0.0 ← T161839
        agent:102.immunity = 0.439271 ← T161839
        agent:102.region = region:2 ← T6
        region:2.food_stock = 1286.986529 ← T160821
        region:2.population = 113 ← T162804
      Writes:
        agent:102.hunger: 0.0 → 0.0
        agent:102.immunity: 0.439271 → 0.439075
      T164794 NoHungerErosionAgentSystem.agents.census (tick 80)
      Inputs:
        agent:102.alive = true ← T6
        agent:102.region = region:2 ← T6
        agent:112.alive = true ← T17
        agent:112.region = region:2 ← T17
        agent:12.alive = true ← T25
        agent:12.region = region:2 ← T25
        agent:122.alive = true ← T28
        agent:122.region = region:2 ← T28
        … 222 more input(s)
      Writes:
        region:2.population: 113 → 113
        region:2.workers: 113 → 113
    T166796 NoHungerErosionAgentSystem.agents.census (tick 81)
    Inputs:
      agent:102.alive = true ← T6
      agent:102.region = region:2 ← T6
      agent:112.alive = true ← T17
      agent:112.region = region:2 ← T17
      agent:12.alive = true ← T25
      agent:12.region = region:2 ← T25
      agent:122.alive = true ← T28
      agent:122.region = region:2 ← T28
      … 222 more input(s)
    Writes:
      region:2.population: 113 → 113
      region:2.workers: 113 → 113
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
      … 126 more parent(s)
```

### agent:160 — acute_infection (died tick 158, T315787)

```
T315787 NoHungerDiseaseSystem.disease.infect (tick 158)
Inputs:
  agent:160.alive = true ← T70
  agent:160.health = 4.210075 ← T314031
  agent:160.immune_memory = 1.0 ← T255961
  agent:160.immunity = 0.446097 ← T314811
  agent:160.infected = false ← T259750
  agent:160.region = region:5 ← T313893
  region:5.disease_load = 0.173918 ← T313957
Random:
  disease.infection@agent:160 = 0.003682 threshold=0.004404
  disease.infection@agent:160 = 0.642881
Writes:
  agent:160.alive: true → false
  agent:160.health: 4.210075 → 0.0
  agent:160.immune_memory: 1.0 → 1.0
  agent:160.infected: false → true
  T70 GenesisSystem.genesis.agent (tick 0)
  Random:
    genesis.attribute@agent:160 = 0.437939
    genesis.attribute@agent:160 = 0.237077
    genesis.attribute@agent:160 = 0.457767
    genesis.attribute@agent:160 = 0.840669
  Writes:
    agent:160.alive: none → true
    agent:160.health: none → 78.138164
    agent:160.hunger: none → 0.171123
    agent:160.immune_memory: none → 0.0
    agent:160.immunity: none → 0.501772
    agent:160.infected: none → false
    agent:160.region: none → region:0
    agent:160.risk_tolerance: none → 0.840669
  T255961 NoHungerDiseaseSystem.disease.infect (tick 127)
  Inputs:
    agent:160.alive = true ← T70
    agent:160.health = 74.518213 ← T254050
    agent:160.immune_memory = 1.0 ← T226739
    agent:160.immunity = 0.453847 ← T254996
    agent:160.infected = false ← T228747
    agent:160.region = region:3 ← T251907
    region:3.disease_load = 0.294503 ← T253961
  Random:
    disease.infection@agent:160 = 0.002945 threshold=0.007386
    disease.infection@agent:160 = 0.727035
  Writes:
    agent:160.health: 74.518213 → 69.210075
    agent:160.immune_memory: 1.0 → 1.0
    agent:160.infected: false → true
    T70 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:160 = 0.437939
      genesis.attribute@agent:160 = 0.237077
      genesis.attribute@agent:160 = 0.457767
      genesis.attribute@agent:160 = 0.840669
    Writes:
      agent:160.alive: none → true
      agent:160.health: none → 78.138164
      agent:160.hunger: none → 0.171123
      agent:160.immune_memory: none → 0.0
      agent:160.immunity: none → 0.501772
      agent:160.infected: none → false
      agent:160.region: none → region:0
      agent:160.risk_tolerance: none → 0.840669
    T226739 NoHungerDiseaseSystem.disease.infect (tick 112)
    Inputs:
      agent:160.alive = true ← T70
      agent:160.health = 100.0 ← T224828
      agent:160.immune_memory = 0.7 ← T204802
      agent:160.immunity = 0.458051 ← T225795
      agent:160.infected = false ← T206812
      agent:160.region = region:0 ← T70
      region:0.disease_load = 0.132297 ← T224738
    Random:
      disease.infection@agent:160 = 0.005339 threshold=0.008911
      disease.infection@agent:160 = 0.948584
    Writes:
      agent:160.health: 100.0 → 91.018213
      agent:160.immune_memory: 0.7 → 1.0
      agent:160.infected: false → true
      T70 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:160 = 0.437939
        genesis.attribute@agent:160 = 0.237077
        genesis.attribute@agent:160 = 0.457767
        genesis.attribute@agent:160 = 0.840669
      Writes:
        agent:160.alive: none → true
        agent:160.health: none → 78.138164
        agent:160.hunger: none → 0.171123
        agent:160.immune_memory: none → 0.0
        agent:160.immunity: none → 0.501772
        agent:160.infected: none → false
        agent:160.region: none → region:0
        agent:160.risk_tolerance: none → 0.840669
      T204802 NoHungerDiseaseSystem.disease.infect (tick 101)
      Inputs:
        agent:160.alive = true ← T70
        agent:160.health = 100.0 ← T202892
        agent:160.immune_memory = 0.35 ← T80262
        agent:160.immunity = 0.461342 ← T203859
        agent:160.infected = false ← T94442
        agent:160.region = region:0 ← T70
        region:0.disease_load = 0.139256 ← T202798
      Random:
        disease.infection@agent:160 = 0.014127 threshold=0.016202
        disease.infection@agent:160 = 0.672774
      Writes:
        agent:160.health: 100.0 → 89.945085
        agent:160.immune_memory: 0.35 → 0.7
        agent:160.infected: false → true
      T206812 NoHungerDiseaseSystem.disease.recover (tick 102)
      Inputs:
        agent:160.alive = true ← T70
        agent:160.hunger = 0.0 ← T205854
        agent:160.immune_memory = 0.7 ← T204802
        agent:160.immunity = 0.461035 ← T205854
        agent:160.infected = true ← T204802
      Random:
        disease.recovery@agent:160 = 0.192084 threshold=0.275259
      Writes:
        agent:160.infected: true → false
      T224738 NoHungerDiseaseSystem.disease.environment (tick 111)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.infected = false ← T110625
        agent:0.region = region:0 ← T1
        agent:10.alive = true ← T3
        agent:10.infected = false ← T140796
        agent:10.region = region:0 ← T3
        agent:100.alive = true ← T4
        agent:100.infected = false ← T194818
        … 345 more input(s)
      Random:
        disease.load_noise@region:0 = 0.61875
      Writes:
        region:0.disease_load: 0.128223 → 0.132297
      … 2 more parent(s)
    T228747 NoHungerDiseaseSystem.disease.recover (tick 113)
    Inputs:
      agent:160.alive = true ← T70
      agent:160.hunger = 0.277278 ← T227790
      agent:160.immune_memory = 1.0 ← T226739
      agent:160.immunity = 0.457761 ← T227790
      agent:160.infected = true ← T226739
    Random:
      disease.recovery@agent:160 = 0.107829 threshold=0.292849
    Writes:
      agent:160.infected: true → false
      T70 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:160 = 0.437939
        genesis.attribute@agent:160 = 0.237077
        genesis.attribute@agent:160 = 0.457767
        genesis.attribute@agent:160 = 0.840669
      Writes:
        agent:160.alive: none → true
        agent:160.health: none → 78.138164
        agent:160.hunger: none → 0.171123
        agent:160.immune_memory: none → 0.0
        agent:160.immunity: none → 0.501772
        agent:160.infected: none → false
        agent:160.region: none → region:0
        agent:160.risk_tolerance: none → 0.840669
      T226739 NoHungerDiseaseSystem.disease.infect (tick 112)
      Inputs:
        agent:160.alive = true ← T70
        agent:160.health = 100.0 ← T224828
        agent:160.immune_memory = 0.7 ← T204802
        agent:160.immunity = 0.458051 ← T225795
        agent:160.infected = false ← T206812
        agent:160.region = region:0 ← T70
        region:0.disease_load = 0.132297 ← T224738
      Random:
        disease.infection@agent:160 = 0.005339 threshold=0.008911
        disease.infection@agent:160 = 0.948584
      Writes:
        agent:160.health: 100.0 → 91.018213
        agent:160.immune_memory: 0.7 → 1.0
        agent:160.infected: false → true
      T227790 NoHungerErosionAgentSystem.agent.metabolism (tick 112)
      Inputs:
        agent:160.hunger = 0.207278 ← T225795
        agent:160.immunity = 0.458051 ← T225795
        agent:160.region = region:0 ← T70
        region:0.food_stock = 0.0 ← T224718
        region:0.population = 117 ← T226698
      Writes:
        agent:160.hunger: 0.207278 → 0.277278
        agent:160.immunity: 0.458051 → 0.457761
    T251907 NoHungerErosionAgentSystem.agent.migrate (tick 124)
    Inputs:
      agent:160.hunger = 0.947278 ← T249004
      agent:160.region = region:2 ← T247918
      agent:160.risk_tolerance = 0.840669 ← T70
    Random:
      agent.decision@agent:160 = 0.349753 threshold=0.420334
    Writes:
      agent:160.region: region:2 → region:3
      T70 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:160 = 0.437939
        genesis.attribute@agent:160 = 0.237077
        genesis.attribute@agent:160 = 0.457767
        genesis.attribute@agent:160 = 0.840669
      Writes:
        agent:160.alive: none → true
        agent:160.health: none → 78.138164
        agent:160.hunger: none → 0.171123
        agent:160.immune_memory: none → 0.0
        agent:160.immunity: none → 0.501772
        agent:160.infected: none → false
        agent:160.region: none → region:0
        agent:160.risk_tolerance: none → 0.840669
      T247918 NoHungerErosionAgentSystem.agent.migrate (tick 122)
      Inputs:
        agent:160.hunger = 0.907278 ← T245007
        agent:160.region = region:1 ← T245917
        agent:160.risk_tolerance = 0.840669 ← T70
      Random:
        agent.decision@agent:160 = 0.179654 threshold=0.420334
      Writes:
        agent:160.region: region:1 → region:2
      T249004 NoHungerErosionAgentSystem.agent.metabolism (tick 123)
      Inputs:
        agent:160.hunger = 0.977278 ← T247012
        agent:160.immunity = 0.454937 ← T247012
        agent:160.region = region:2 ← T247918
        region:2.food_stock = 953.037501 ← T245957
        region:2.population = 131 ← T247940
      Writes:
        agent:160.hunger: 0.977278 → 0.947278
        agent:160.immunity: 0.454937 → 0.454663
    … 3 more parent(s)
  T259750 NoHungerDiseaseSystem.disease.recover (tick 129)
  Inputs:
    agent:160.alive = true ← T70
    agent:160.hunger = 1.0 ← T258767
    agent:160.immune_memory = 1.0 ← T255961
    agent:160.immunity = 0.45331 ← T258767
    agent:160.infected = true ← T255961
  Random:
    disease.recovery@agent:160 = 0.133577 threshold=0.183327
  Writes:
    agent:160.infected: true → false
    T70 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:160 = 0.437939
      genesis.attribute@agent:160 = 0.237077
      genesis.attribute@agent:160 = 0.457767
      genesis.attribute@agent:160 = 0.840669
    Writes:
      agent:160.alive: none → true
      agent:160.health: none → 78.138164
      agent:160.hunger: none → 0.171123
      agent:160.immune_memory: none → 0.0
      agent:160.immunity: none → 0.501772
      agent:160.infected: none → false
      agent:160.region: none → region:0
      agent:160.risk_tolerance: none → 0.840669
    T255961 NoHungerDiseaseSystem.disease.infect (tick 127)
    Inputs:
      agent:160.alive = true ← T70
      agent:160.health = 74.518213 ← T254050
      agent:160.immune_memory = 1.0 ← T226739
      agent:160.immunity = 0.453847 ← T254996
      agent:160.infected = false ← T228747
      agent:160.region = region:3 ← T251907
      region:3.disease_load = 0.294503 ← T253961
    Random:
      disease.infection@agent:160 = 0.002945 threshold=0.007386
      disease.infection@agent:160 = 0.727035
    Writes:
      agent:160.health: 74.518213 → 69.210075
      agent:160.immune_memory: 1.0 → 1.0
      agent:160.infected: false → true
      T70 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:160 = 0.437939
        genesis.attribute@agent:160 = 0.237077
        genesis.attribute@agent:160 = 0.457767
        genesis.attribute@agent:160 = 0.840669
      Writes:
        agent:160.alive: none → true
        agent:160.health: none → 78.138164
        agent:160.hunger: none → 0.171123
        agent:160.immune_memory: none → 0.0
        agent:160.immunity: none → 0.501772
        agent:160.infected: none → false
        agent:160.region: none → region:0
        agent:160.risk_tolerance: none → 0.840669
      T226739 NoHungerDiseaseSystem.disease.infect (tick 112)
      Inputs:
        agent:160.alive = true ← T70
        agent:160.health = 100.0 ← T224828
        agent:160.immune_memory = 0.7 ← T204802
        agent:160.immunity = 0.458051 ← T225795
        agent:160.infected = false ← T206812
        agent:160.region = region:0 ← T70
        region:0.disease_load = 0.132297 ← T224738
      Random:
        disease.infection@agent:160 = 0.005339 threshold=0.008911
        disease.infection@agent:160 = 0.948584
      Writes:
        agent:160.health: 100.0 → 91.018213
        agent:160.immune_memory: 0.7 → 1.0
        agent:160.infected: false → true
      T228747 NoHungerDiseaseSystem.disease.recover (tick 113)
      Inputs:
        agent:160.alive = true ← T70
        agent:160.hunger = 0.277278 ← T227790
        agent:160.immune_memory = 1.0 ← T226739
        agent:160.immunity = 0.457761 ← T227790
        agent:160.infected = true ← T226739
      Random:
        disease.recovery@agent:160 = 0.107829 threshold=0.292849
      Writes:
        agent:160.infected: true → false
      T251907 NoHungerErosionAgentSystem.agent.migrate (tick 124)
      Inputs:
        agent:160.hunger = 0.947278 ← T249004
        agent:160.region = region:2 ← T247918
        agent:160.risk_tolerance = 0.840669 ← T70
      Random:
        agent.decision@agent:160 = 0.349753 threshold=0.420334
      Writes:
        agent:160.region: region:2 → region:3
      … 3 more parent(s)
    T258767 NoHungerErosionAgentSystem.agent.metabolism (tick 128)
    Inputs:
      agent:160.hunger = 1.0 ← T256876
      agent:160.immunity = 0.453577 ← T256876
      agent:160.region = region:3 ← T251907
      region:3.food_stock = 0.0 ← T255934
      region:3.population = 152 ← T257814
    Writes:
      agent:160.hunger: 1.0 → 1.0
      agent:160.immunity: 0.453577 → 0.45331
      T251907 NoHungerErosionAgentSystem.agent.migrate (tick 124)
      Inputs:
        agent:160.hunger = 0.947278 ← T249004
        agent:160.region = region:2 ← T247918
        agent:160.risk_tolerance = 0.840669 ← T70
      Random:
        agent.decision@agent:160 = 0.349753 threshold=0.420334
      Writes:
        agent:160.region: region:2 → region:3
      T255934 AgricultureSystem.agriculture.harvest (tick 127)
      Inputs:
        region:3.food_stock = 0.0 ← T253941
        region:3.population = 155 ← T255924
        region:3.rainfall = 0.499045 ← T253951
        region:3.soil_fertility = 0.513294 ← T253941
        region:3.temperature = 7.286221 ← T253951
        region:3.workers = 155 ← T255924
      Random:
        agriculture.crop_variance@region:3 = 0.462867
      Writes:
        region:3.food_stock: 0.0 → 0.0
        region:3.soil_fertility: 0.513294 → 0.512394
      T256876 NoHungerErosionAgentSystem.agent.metabolism (tick 127)
      Inputs:
        agent:160.hunger = 1.0 ← T254996
        agent:160.immunity = 0.453847 ← T254996
        agent:160.region = region:3 ← T251907
        region:3.food_stock = 0.0 ← T253941
        region:3.population = 155 ← T255924
      Writes:
        agent:160.hunger: 1.0 → 1.0
        agent:160.immunity: 0.453847 → 0.453577
      T257814 NoHungerErosionAgentSystem.agents.census (tick 127)
      Inputs:
        agent:103.alive = true ← T7
        agent:103.region = region:3 ← T7
        agent:11.alive = true ← T14
        agent:11.region = region:3 ← T67903
        agent:113.alive = true ← T18
        agent:113.region = region:3 ← T18
        agent:123.alive = true ← T29
        agent:123.region = region:3 ← T29
        … 308 more input(s)
      Writes:
        region:3.population: 155 → 152
        region:3.workers: 155 → 152
  T313893 NoHungerErosionAgentSystem.agent.migrate (tick 156)
  Inputs:
    agent:160.hunger = 1.0 ← T311188
    agent:160.region = region:4 ← T310275
    agent:160.risk_tolerance = 0.840669 ← T70
  Random:
    agent.decision@agent:160 = 0.205796 threshold=0.420334
  Writes:
    agent:160.region: region:4 → region:5
    T70 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:160 = 0.437939
      genesis.attribute@agent:160 = 0.237077
      genesis.attribute@agent:160 = 0.457767
      genesis.attribute@agent:160 = 0.840669
    Writes:
      agent:160.alive: none → true
      agent:160.health: none → 78.138164
      agent:160.hunger: none → 0.171123
      agent:160.immune_memory: none → 0.0
      agent:160.immunity: none → 0.501772
      agent:160.infected: none → false
      agent:160.region: none → region:0
      agent:160.risk_tolerance: none → 0.840669
    T310275 NoHungerErosionAgentSystem.agent.migrate (tick 154)
    Inputs:
      agent:160.hunger = 1.0 ← T307556
      agent:160.region = region:3 ← T290939
      agent:160.risk_tolerance = 0.840669 ← T70
    Random:
      agent.decision@agent:160 = 0.267922 threshold=0.420334
    Writes:
      agent:160.region: region:3 → region:4
      T70 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:160 = 0.437939
        genesis.attribute@agent:160 = 0.237077
        genesis.attribute@agent:160 = 0.457767
        genesis.attribute@agent:160 = 0.840669
      Writes:
        agent:160.alive: none → true
        agent:160.health: none → 78.138164
        agent:160.hunger: none → 0.171123
        agent:160.immune_memory: none → 0.0
        agent:160.immunity: none → 0.501772
        agent:160.infected: none → false
        agent:160.region: none → region:0
        agent:160.risk_tolerance: none → 0.840669
      T290939 NoHungerErosionAgentSystem.agent.migrate (tick 144)
      Inputs:
        agent:160.hunger = 0.93 ← T288066
        agent:160.region = region:2 ← T288973
        agent:160.risk_tolerance = 0.840669 ← T70
      Random:
        agent.decision@agent:160 = 0.118285 threshold=0.420334
      Writes:
        agent:160.region: region:2 → region:3
      T307556 NoHungerErosionAgentSystem.agent.metabolism (tick 153)
      Inputs:
        agent:160.hunger = 1.0 ← T305616
        agent:160.immunity = 0.447267 ← T305616
        agent:160.region = region:3 ← T290939
        region:3.food_stock = 0.0 ← T304621
        region:3.population = 21 ← T306554
      Writes:
        agent:160.hunger: 1.0 → 1.0
        agent:160.immunity: 0.447267 → 0.447031
    T311188 NoHungerErosionAgentSystem.agent.metabolism (tick 155)
    Inputs:
      agent:160.hunger = 1.0 ← T309374
      agent:160.immunity = 0.446796 ← T309374
      agent:160.region = region:4 ← T310275
      region:4.food_stock = 41.045203 ← T308507
      region:4.population = 161 ← T310307
    Writes:
      agent:160.hunger: 1.0 → 1.0
      agent:160.immunity: 0.446796 → 0.446562
      T308507 AgricultureSystem.agriculture.harvest (tick 154)
      Inputs:
        region:4.food_stock = 19.550866 ← T306565
        region:4.population = 158 ← T308497
        region:4.rainfall = 0.598203 ← T306575
        region:4.soil_fertility = 0.485905 ← T306565
        region:4.temperature = 22.623573 ← T306575
        region:4.workers = 158 ← T308497
      Random:
        agriculture.crop_variance@region:4 = 0.971002
      Writes:
        region:4.food_stock: 19.550866 → 41.045203
        region:4.soil_fertility: 0.485905 → 0.485005
      T309374 NoHungerErosionAgentSystem.agent.metabolism (tick 154)
      Inputs:
        agent:160.hunger = 1.0 ← T307556
        agent:160.immunity = 0.447031 ← T307556
        agent:160.region = region:3 ← T290939
        region:3.food_stock = 0.0 ← T306564
        region:3.population = 23 ← T308496
      Writes:
        agent:160.hunger: 1.0 → 1.0
        agent:160.immunity: 0.447031 → 0.446796
      T310275 NoHungerErosionAgentSystem.agent.migrate (tick 154)
      Inputs:
        agent:160.hunger = 1.0 ← T307556
        agent:160.region = region:3 ← T290939
        agent:160.risk_tolerance = 0.840669 ← T70
      Random:
        agent.decision@agent:160 = 0.267922 threshold=0.420334
      Writes:
        agent:160.region: region:3 → region:4
      T310307 NoHungerErosionAgentSystem.agents.census (tick 154)
      Inputs:
        agent:101.alive = true ← T5
        agent:101.region = region:4 ← T69864
        agent:104.alive = true ← T8
        agent:104.region = region:4 ← T8
        agent:114.alive = true ← T19
        agent:114.region = region:4 ← T19
        agent:124.alive = true ← T30
        agent:124.region = region:4 ← T30
        … 320 more input(s)
      Writes:
        region:4.population: 158 → 161
        region:4.workers: 158 → 161
  … 3 more parent(s)
```

## Reproduction

```bash
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --ruleset no_hunger_immunity --db runs/survival_seed7_no_hunger.db --report <path>
```

Same seed + kernel v0.1.0 + ruleset 0.3.1c → bit-identical world, identical traces, identical report.