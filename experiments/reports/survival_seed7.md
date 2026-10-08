# Causal survival experiment — seed 7

Frozen **CAUSAL KERNEL v0.1** — no new systems, no new laws.
Scale, statistics and mechanical death traces only.

## Run

| parameter | value |
|---|---|
| seed | 7 |
| regions | 10 |
| agents | 1000 |
| ticks | 10000 |
| wall time | 2s |
| archive | `runs/survival_seed7.db` |
| survivors | 0 / 1000 |
| deaths | 1000 |
| last death | tick 553 |

## Lifespan distribution (all agents died: no censoring)

| pct | ticks |
|---|---|
| p0 | 23 |
| p10 | 44 |
| p25 | 55 |
| p50 | 82 |
| p75 | 200 |
| p90 | 355 |
| p100 | 553 |

mean lifespan: **141** ticks

## Statistical regularity: correlations with lifespan

| observable | pearson | spearman |
|---|---|---|
| initial_health | -0.004 | +0.068 |
| initial_immunity | +0.330 | +0.337 |
| risk_tolerance | +0.074 | +0.072 |
| migration_count | +0.407 | +0.321 |
| infection_count | +0.893 | +0.854 |
| avg_food_access | +0.346 | +0.340 |
| avg_social_density | -0.898 | -0.867 |

## Individual causality: death mechanisms (from traces)

| mechanism | deaths | share |
|---|---|---|
| disease | 512 | 51.2% |
| disease+starvation | 372 | 37.2% |
| acute_infection | 116 | 11.6% |

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
| stayers (0 migrations) | 599 | 106 | 99 | 443 | 57 |
| migrants (>=1 migration) | 401 | 194 | 17 | 69 | 315 |

### Risk tolerance quartiles

| group | n | mean lifespan | acute_infection | disease | disease+starvation |
|---|---|---|---|---|---|
| risk Q1 (lowest) | 250 | 124 | 31 | 117 | 102 |
| risk Q2 | 250 | 147 | 26 | 120 | 104 |
| risk Q3 | 250 | 142 | 30 | 127 | 93 |
| risk Q4 (highest) | 250 | 152 | 29 | 148 | 73 |

## Example mechanical explanations

### agent:0 — disease (died tick 73, T137372)

```
T137372 AgentSystem.agent.death (tick 73)
Inputs:
  agent:0.alive = true ← T1
  agent:0.health = 1.558395 ← T136126
  agent:0.hunger = 0.0 ← T136698
  agent:0.infected = true ← T128135
Writes:
  agent:0.alive: true → false
  agent:0.health: 1.558395 → 0.0
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
    agent:0.immunity: none → 0.691249
    agent:0.infected: none → false
    agent:0.region: none → region:0
    agent:0.risk_tolerance: none → 0.758627
  T128135 DiseaseSystem.disease.infect (tick 65)
  Inputs:
    agent:0.alive = true ← T1
    agent:0.health = 30.23936 ← T125418
    agent:0.hunger = 0.0 ← T126059
    agent:0.immunity = 0.601655 ← T126059
    agent:0.infected = false ← T123949
    agent:0.region = region:0 ← T1
    region:0.disease_load = 0.439082 ← T126735
  Random:
    disease.infection@agent:0 = 0.052457 threshold=0.059782
    disease.infection@agent:0 = 0.518096
  Writes:
    agent:0.health: 30.23936 → 19.058395
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
      agent:0.immunity: none → 0.691249
      agent:0.infected: none → false
      agent:0.region: none → region:0
      agent:0.risk_tolerance: none → 0.758627
    T123949 DiseaseSystem.disease.recover (tick 62)
    Inputs:
      agent:0.alive = true ← T1
      agent:0.hunger = 0.0 ← T121729
      agent:0.immunity = 0.60471 ← T121729
      agent:0.infected = true ← T113156
    Random:
      disease.recovery@agent:0 = 0.040889 threshold=0.171178
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
        agent:0.immunity: none → 0.691249
        agent:0.infected: none → false
        agent:0.region: none → region:0
        agent:0.risk_tolerance: none → 0.758627
      T113156 DiseaseSystem.disease.infect (tick 55)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.health = 57.902345 ← T109896
        agent:0.hunger = 0.0 ← T110658
        agent:0.immunity = 0.61202 ← T110658
        agent:0.infected = false ← T111539
        agent:0.region = region:0 ← T1
        region:0.disease_load = 0.56885 ← T111473
      Random:
        disease.infection@agent:0 = 0.035586 threshold=0.076212
        disease.infection@agent:0 = 0.716298
      Writes:
        agent:0.health: 57.902345 → 44.73936
        agent:0.infected: false → true
      T121729 AgentSystem.agent.metabolism (tick 61)
      Inputs:
        agent:0.hunger = 0.0 ← T120235
        agent:0.immunity = 0.605739 ← T120235
        agent:0.region = region:0 ← T1
        region:0.food_stock = 617.414278 ← T120937
        region:0.population = 91 ← T120927
      Writes:
        agent:0.hunger: 0.0 → 0.0
        agent:0.immunity: 0.605739 → 0.60471
    T125418 AgentSystem.agent.health (tick 64)
    Inputs:
      agent:0.alive = true ← T1
      agent:0.health = 28.73936 ← T123995
      agent:0.hunger = 0.0 ← T124645
      agent:0.infected = false ← T123949
    Writes:
      agent:0.health: 28.73936 → 30.23936
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
        agent:0.immunity: none → 0.691249
        agent:0.infected: none → false
        agent:0.region: none → region:0
        agent:0.risk_tolerance: none → 0.758627
      T123949 DiseaseSystem.disease.recover (tick 62)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.hunger = 0.0 ← T121729
        agent:0.immunity = 0.60471 ← T121729
        agent:0.infected = true ← T113156
      Random:
        disease.recovery@agent:0 = 0.040889 threshold=0.171178
      Writes:
        agent:0.infected: true → false
      T123995 AgentSystem.agent.health (tick 63)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.health = 27.23936 ← T122550
        agent:0.hunger = 0.0 ← T123208
        agent:0.infected = false ← T123949
      Writes:
        agent:0.health: 27.23936 → 28.73936
      T124645 AgentSystem.agent.metabolism (tick 63)
      Inputs:
        agent:0.hunger = 0.0 ← T123208
        agent:0.immunity = 0.603687 ← T123208
        agent:0.region = region:0 ← T1
        region:0.food_stock = 578.433079 ← T123887
        region:0.population = 89 ← T123877
      Writes:
        agent:0.hunger: 0.0 → 0.0
        agent:0.immunity: 0.603687 → 0.602668
    T126059 AgentSystem.agent.metabolism (tick 64)
    Inputs:
      agent:0.hunger = 0.0 ← T124645
      agent:0.immunity = 0.602668 ← T124645
      agent:0.region = region:0 ← T1
      region:0.food_stock = 566.055474 ← T125311
      region:0.population = 87 ← T125301
    Writes:
      agent:0.hunger: 0.0 → 0.0
      agent:0.immunity: 0.602668 → 0.601655
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
        agent:0.immunity: none → 0.691249
        agent:0.infected: none → false
        agent:0.region: none → region:0
        agent:0.risk_tolerance: none → 0.758627
      T124645 AgentSystem.agent.metabolism (tick 63)
      Inputs:
        agent:0.hunger = 0.0 ← T123208
        agent:0.immunity = 0.603687 ← T123208
        agent:0.region = region:0 ← T1
        region:0.food_stock = 578.433079 ← T123887
        region:0.population = 89 ← T123877
      Writes:
        agent:0.hunger: 0.0 → 0.0
        agent:0.immunity: 0.603687 → 0.602668
      T125301 AgentSystem.agents.census (tick 63)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.region = region:0 ← T1
        agent:10.alive = true ← T3
        agent:10.region = region:0 ← T3
        agent:100.alive = true ← T4
        agent:100.region = region:0 ← T4
        agent:110.alive = false ← T83437
        agent:110.region = region:0 ← T15
        … 212 more input(s)
      Writes:
        region:0.population: 89 → 87
        region:0.workers: 89 → 87
      T125311 AgricultureSystem.agriculture.harvest (tick 63)
      Inputs:
        region:0.food_stock = 578.433079 ← T123887
        region:0.population = 89 ← T123877
        region:0.rainfall = 0.610538 ← T123897
        region:0.soil_fertility = 0.469921 ← T123887
        region:0.temperature = 9.448002 ← T123897
        region:0.workers = 89 ← T123877
      Random:
        agriculture.crop_variance@region:0 = 0.683883
      Writes:
        region:0.food_stock: 578.433079 → 566.055474
        region:0.soil_fertility: 0.469921 → 0.469021
    … 1 more parent(s)
  T136126 AgentSystem.agent.health (tick 72)
  Inputs:
    agent:0.alive = true ← T1
    agent:0.health = 4.058395 ← T134848
    agent:0.hunger = 0.0 ← T135432
    agent:0.infected = true ← T128135
  Writes:
    agent:0.health: 4.058395 → 1.558395
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
      agent:0.immunity: none → 0.691249
      agent:0.infected: none → false
      agent:0.region: none → region:0
      agent:0.risk_tolerance: none → 0.758627
    T128135 DiseaseSystem.disease.infect (tick 65)
    Inputs:
      agent:0.alive = true ← T1
      agent:0.health = 30.23936 ← T125418
      agent:0.hunger = 0.0 ← T126059
      agent:0.immunity = 0.601655 ← T126059
      agent:0.infected = false ← T123949
      agent:0.region = region:0 ← T1
      region:0.disease_load = 0.439082 ← T126735
    Random:
      disease.infection@agent:0 = 0.052457 threshold=0.059782
      disease.infection@agent:0 = 0.518096
    Writes:
      agent:0.health: 30.23936 → 19.058395
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
        agent:0.immunity: none → 0.691249
        agent:0.infected: none → false
        agent:0.region: none → region:0
        agent:0.risk_tolerance: none → 0.758627
      T123949 DiseaseSystem.disease.recover (tick 62)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.hunger = 0.0 ← T121729
        agent:0.immunity = 0.60471 ← T121729
        agent:0.infected = true ← T113156
      Random:
        disease.recovery@agent:0 = 0.040889 threshold=0.171178
      Writes:
        agent:0.infected: true → false
      T125418 AgentSystem.agent.health (tick 64)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.health = 28.73936 ← T123995
        agent:0.hunger = 0.0 ← T124645
        agent:0.infected = false ← T123949
      Writes:
        agent:0.health: 28.73936 → 30.23936
      T126059 AgentSystem.agent.metabolism (tick 64)
      Inputs:
        agent:0.hunger = 0.0 ← T124645
        agent:0.immunity = 0.602668 ← T124645
        agent:0.region = region:0 ← T1
        region:0.food_stock = 566.055474 ← T125311
        region:0.population = 87 ← T125301
      Writes:
        agent:0.hunger: 0.0 → 0.0
        agent:0.immunity: 0.602668 → 0.601655
      … 1 more parent(s)
    T134848 AgentSystem.agent.health (tick 71)
    Inputs:
      agent:0.alive = true ← T1
      agent:0.health = 6.558395 ← T133551
      agent:0.hunger = 0.0 ← T134147
      agent:0.infected = true ← T128135
    Writes:
      agent:0.health: 6.558395 → 4.058395
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
        agent:0.immunity: none → 0.691249
        agent:0.infected: none → false
        agent:0.region: none → region:0
        agent:0.risk_tolerance: none → 0.758627
      T128135 DiseaseSystem.disease.infect (tick 65)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.health = 30.23936 ← T125418
        agent:0.hunger = 0.0 ← T126059
        agent:0.immunity = 0.601655 ← T126059
        agent:0.infected = false ← T123949
        agent:0.region = region:0 ← T1
        region:0.disease_load = 0.439082 ← T126735
      Random:
        disease.infection@agent:0 = 0.052457 threshold=0.059782
        disease.infection@agent:0 = 0.518096
      Writes:
        agent:0.health: 30.23936 → 19.058395
        agent:0.infected: false → true
      T133551 AgentSystem.agent.health (tick 70)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.health = 9.058395 ← T132234
        agent:0.hunger = 0.0 ← T132835
        agent:0.infected = true ← T128135
      Writes:
        agent:0.health: 9.058395 → 6.558395
      T134147 AgentSystem.agent.metabolism (tick 70)
      Inputs:
        agent:0.hunger = 0.0 ← T132835
        agent:0.immunity = 0.596664 ← T132835
        agent:0.region = region:0 ← T1
        region:0.food_stock = 460.166083 ← T133453
        region:0.population = 81 ← T133443
      Writes:
        agent:0.hunger: 0.0 → 0.0
        agent:0.immunity: 0.596664 → 0.59568
    T135432 AgentSystem.agent.metabolism (tick 71)
    Inputs:
      agent:0.hunger = 0.0 ← T134147
      agent:0.immunity = 0.59568 ← T134147
      agent:0.region = region:0 ← T1
      region:0.food_stock = 435.764899 ← T134756
      region:0.population = 80 ← T134746
    Writes:
      agent:0.hunger: 0.0 → 0.0
      agent:0.immunity: 0.59568 → 0.594702
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
        agent:0.immunity: none → 0.691249
        agent:0.infected: none → false
        agent:0.region: none → region:0
        agent:0.risk_tolerance: none → 0.758627
      T134147 AgentSystem.agent.metabolism (tick 70)
      Inputs:
        agent:0.hunger = 0.0 ← T132835
        agent:0.immunity = 0.596664 ← T132835
        agent:0.region = region:0 ← T1
        region:0.food_stock = 460.166083 ← T133453
        region:0.population = 81 ← T133443
      Writes:
        agent:0.hunger: 0.0 → 0.0
        agent:0.immunity: 0.596664 → 0.59568
      T134746 AgentSystem.agents.census (tick 70)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.region = region:0 ← T1
        agent:10.alive = true ← T3
        agent:10.region = region:0 ← T3
        agent:100.alive = true ← T4
        agent:100.region = region:0 ← T4
        agent:110.alive = false ← T83437
        agent:110.region = region:0 ← T15
        … 212 more input(s)
      Writes:
        region:0.population: 81 → 80
        region:0.workers: 81 → 80
      T134756 AgricultureSystem.agriculture.harvest (tick 70)
      Inputs:
        region:0.food_stock = 460.166083 ← T133453
        region:0.population = 81 ← T133443
        region:0.rainfall = 0.559938 ← T133463
        region:0.soil_fertility = 0.463621 ← T133453
        region:0.temperature = 9.916328 ← T133463
        region:0.workers = 81 ← T133443
      Random:
        agriculture.crop_variance@region:0 = 0.399167
      Writes:
        region:0.food_stock: 460.166083 → 435.764899
        region:0.soil_fertility: 0.463621 → 0.462721
  T136698 AgentSystem.agent.metabolism (tick 72)
  Inputs:
    agent:0.hunger = 0.0 ← T135432
    agent:0.immunity = 0.594702 ← T135432
    agent:0.region = region:0 ← T1
    region:0.food_stock = 418.210328 ← T136037
    region:0.population = 80 ← T136027
  Writes:
    agent:0.hunger: 0.0 → 0.0
    agent:0.immunity: 0.594702 → 0.593728
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
      agent:0.immunity: none → 0.691249
      agent:0.infected: none → false
      agent:0.region: none → region:0
      agent:0.risk_tolerance: none → 0.758627
    T135432 AgentSystem.agent.metabolism (tick 71)
    Inputs:
      agent:0.hunger = 0.0 ← T134147
      agent:0.immunity = 0.59568 ← T134147
      agent:0.region = region:0 ← T1
      region:0.food_stock = 435.764899 ← T134756
      region:0.population = 80 ← T134746
    Writes:
      agent:0.hunger: 0.0 → 0.0
      agent:0.immunity: 0.59568 → 0.594702
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
        agent:0.immunity: none → 0.691249
        agent:0.infected: none → false
        agent:0.region: none → region:0
        agent:0.risk_tolerance: none → 0.758627
      T134147 AgentSystem.agent.metabolism (tick 70)
      Inputs:
        agent:0.hunger = 0.0 ← T132835
        agent:0.immunity = 0.596664 ← T132835
        agent:0.region = region:0 ← T1
        region:0.food_stock = 460.166083 ← T133453
        region:0.population = 81 ← T133443
      Writes:
        agent:0.hunger: 0.0 → 0.0
        agent:0.immunity: 0.596664 → 0.59568
      T134746 AgentSystem.agents.census (tick 70)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.region = region:0 ← T1
        agent:10.alive = true ← T3
        agent:10.region = region:0 ← T3
        agent:100.alive = true ← T4
        agent:100.region = region:0 ← T4
        agent:110.alive = false ← T83437
        agent:110.region = region:0 ← T15
        … 212 more input(s)
      Writes:
        region:0.population: 81 → 80
        region:0.workers: 81 → 80
      T134756 AgricultureSystem.agriculture.harvest (tick 70)
      Inputs:
        region:0.food_stock = 460.166083 ← T133453
        region:0.population = 81 ← T133443
        region:0.rainfall = 0.559938 ← T133463
        region:0.soil_fertility = 0.463621 ← T133453
        region:0.temperature = 9.916328 ← T133463
        region:0.workers = 81 ← T133443
      Random:
        agriculture.crop_variance@region:0 = 0.399167
      Writes:
        region:0.food_stock: 460.166083 → 435.764899
        region:0.soil_fertility: 0.463621 → 0.462721
    T136027 AgentSystem.agents.census (tick 71)
    Inputs:
      agent:0.alive = true ← T1
      agent:0.region = region:0 ← T1
      agent:10.alive = true ← T3
      agent:10.region = region:0 ← T3
      agent:100.alive = true ← T4
      agent:100.region = region:0 ← T4
      agent:110.alive = false ← T83437
      agent:110.region = region:0 ← T15
      … 212 more input(s)
    Writes:
      region:0.population: 80 → 80
      region:0.workers: 80 → 80
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
        agent:0.immunity: none → 0.691249
        agent:0.infected: none → false
        agent:0.region: none → region:0
        agent:0.risk_tolerance: none → 0.758627
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
        agent:10.immunity: none → 0.699493
        agent:10.infected: none → false
        agent:10.region: none → region:0
        agent:10.risk_tolerance: none → 0.381925
      T4 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:100 = 0.217458
        genesis.attribute@agent:100 = 0.295026
        genesis.attribute@agent:100 = 0.140563
        genesis.attribute@agent:100 = 0.461993
      Writes:
        agent:100.alive: none → true
        agent:100.health: none → 71.523727
        agent:100.hunger: none → 0.188508
        agent:100.immunity: none → 0.32731
        agent:100.infected: none → false
        agent:100.region: none → region:0
        agent:100.risk_tolerance: none → 0.461993
      T15 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:110 = 0.218631
        genesis.attribute@agent:110 = 0.661931
        genesis.attribute@agent:110 = 0.013539
        genesis.attribute@agent:110 = 0.890081
      Writes:
        agent:110.alive: none → true
        agent:110.health: none → 71.558933
        agent:110.hunger: none → 0.298579
        agent:110.immunity: none → 0.257446
        agent:110.infected: none → false
        agent:110.region: none → region:0
        agent:110.risk_tolerance: none → 0.890081
      … 137 more parent(s)
    T136037 AgricultureSystem.agriculture.harvest (tick 71)
    Inputs:
      region:0.food_stock = 435.764899 ← T134756
      region:0.population = 80 ← T134746
      region:0.rainfall = 0.614709 ← T134766
      region:0.soil_fertility = 0.462721 ← T134756
      region:0.temperature = 9.268187 ← T134766
      region:0.workers = 80 ← T134746
    Random:
      agriculture.crop_variance@region:0 = 0.547495
    Writes:
      region:0.food_stock: 435.764899 → 418.210328
      region:0.soil_fertility: 0.462721 → 0.461821
      T134746 AgentSystem.agents.census (tick 70)
      Inputs:
        agent:0.alive = true ← T1
        agent:0.region = region:0 ← T1
        agent:10.alive = true ← T3
        agent:10.region = region:0 ← T3
        agent:100.alive = true ← T4
        agent:100.region = region:0 ← T4
        agent:110.alive = false ← T83437
        agent:110.region = region:0 ← T15
        … 212 more input(s)
      Writes:
        region:0.population: 81 → 80
        region:0.workers: 81 → 80
      T134756 AgricultureSystem.agriculture.harvest (tick 70)
      Inputs:
        region:0.food_stock = 460.166083 ← T133453
        region:0.population = 81 ← T133443
        region:0.rainfall = 0.559938 ← T133463
        region:0.soil_fertility = 0.463621 ← T133453
        region:0.temperature = 9.916328 ← T133463
        region:0.workers = 81 ← T133443
      Random:
        agriculture.crop_variance@region:0 = 0.399167
      Writes:
        region:0.food_stock: 460.166083 → 435.764899
        region:0.soil_fertility: 0.463621 → 0.462721
      T134766 ClimateSystem.climate.step (tick 70)
      Inputs:
        region:0.climate_volatility = 0.527532 ← T1001
        region:0.rainfall = 0.559938 ← T133463
        region:0.rainfall_base = 0.623943 ← T1001
        region:0.temperature = 9.916328 ← T133463
        region:0.temperature_base = 9.866103 ← T1001
      Random:
        climate.temperature_noise@region:0 = 0.01807
        climate.rain@region:0 = 0.84975
      Writes:
        region:0.rainfall: 0.559938 → 0.614709
        region:0.temperature: 9.916328 → 9.268187
```

### agent:118 — acute_infection (died tick 90, T157277)

```
T157277 DiseaseSystem.disease.infect (tick 90)
Inputs:
  agent:118.alive = true ← T23
  agent:118.health = 9.374236 ← T155298
  agent:118.hunger = 0.0 ← T155763
  agent:118.immunity = 0.334728 ← T155763
  agent:118.infected = false ← T154237
  agent:118.region = region:8 ← T23
  region:8.disease_load = 0.319599 ← T156264
Random:
  disease.infection@agent:118 = 0.0169 threshold=0.061429
  disease.infection@agent:118 = 0.512122
Writes:
  agent:118.alive: true → false
  agent:118.health: 9.374236 → 0.0
  agent:118.infected: false → true
  T23 GenesisSystem.genesis.agent (tick 0)
  Random:
    genesis.attribute@agent:118 = 0.872492
    genesis.attribute@agent:118 = 0.2112
    genesis.attribute@agent:118 = 0.093138
    genesis.attribute@agent:118 = 0.395042
  Writes:
    agent:118.alive: none → true
    agent:118.health: none → 91.17475
    agent:118.hunger: none → 0.16336
    agent:118.immunity: none → 0.301226
    agent:118.infected: none → false
    agent:118.region: none → region:8
    agent:118.risk_tolerance: none → 0.395042
  T154237 DiseaseSystem.disease.recover (tick 87)
  Inputs:
    agent:118.alive = true ← T23
    agent:118.hunger = 0.0 ← T152698
    agent:118.immunity = 0.333739 ← T152698
    agent:118.infected = true ← T148976
  Random:
    disease.recovery@agent:118 = 0.101104 threshold=0.103435
  Writes:
    agent:118.infected: true → false
    T23 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:118 = 0.872492
      genesis.attribute@agent:118 = 0.2112
      genesis.attribute@agent:118 = 0.093138
      genesis.attribute@agent:118 = 0.395042
    Writes:
      agent:118.alive: none → true
      agent:118.health: none → 91.17475
      agent:118.hunger: none → 0.16336
      agent:118.immunity: none → 0.301226
      agent:118.infected: none → false
      agent:118.region: none → region:8
      agent:118.risk_tolerance: none → 0.395042
    T148976 DiseaseSystem.disease.infect (tick 82)
    Inputs:
      agent:118.alive = true ← T23
      agent:118.health = 26.531088 ← T146827
      agent:118.hunger = 0.0 ← T147335
      agent:118.immunity = 0.332057 ← T147335
      agent:118.infected = false ← T141018
      agent:118.region = region:8 ← T23
      region:8.disease_load = 0.326972 ← T147879
    Random:
      disease.infection@agent:118 = 0.006847 threshold=0.06303
      disease.infection@agent:118 = 0.165685
    Writes:
      agent:118.health: 26.531088 → 18.874236
      agent:118.infected: false → true
      T23 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:118 = 0.872492
        genesis.attribute@agent:118 = 0.2112
        genesis.attribute@agent:118 = 0.093138
        genesis.attribute@agent:118 = 0.395042
      Writes:
        agent:118.alive: none → true
        agent:118.health: none → 91.17475
        agent:118.hunger: none → 0.16336
        agent:118.immunity: none → 0.301226
        agent:118.infected: none → false
        agent:118.region: none → region:8
        agent:118.risk_tolerance: none → 0.395042
      T141018 DiseaseSystem.disease.recover (tick 75)
      Inputs:
        agent:118.alive = true ← T23
        agent:118.hunger = 0.0 ← T139198
        agent:118.immunity = 0.329631 ← T139198
        agent:118.infected = true ← T128136
      Random:
        disease.recovery@agent:118 = 0.07052 threshold=0.102408
      Writes:
        agent:118.infected: true → false
      T146827 AgentSystem.agent.health (tick 81)
      Inputs:
        agent:118.alive = true ← T23
        agent:118.health = 25.031088 ← T145705
        agent:118.hunger = 0.0 ← T146219
        agent:118.infected = false ← T141018
      Writes:
        agent:118.health: 25.031088 → 26.531088
      T147335 AgentSystem.agent.metabolism (tick 81)
      Inputs:
        agent:118.hunger = 0.0 ← T146219
        agent:118.immunity = 0.331716 ← T146219
        agent:118.region = region:8 ← T23
        region:8.food_stock = 3019.371217 ← T146750
        region:8.population = 66 ← T146740
      Writes:
        agent:118.hunger: 0.0 → 0.0
        agent:118.immunity: 0.331716 → 0.332057
      … 1 more parent(s)
    T152698 AgentSystem.agent.metabolism (tick 86)
    Inputs:
      agent:118.hunger = 0.0 ← T151657
      agent:118.immunity = 0.333406 ← T151657
      agent:118.region = region:8 ← T23
      region:8.food_stock = 2981.463874 ← T152153
      region:8.population = 64 ← T152143
    Writes:
      agent:118.hunger: 0.0 → 0.0
      agent:118.immunity: 0.333406 → 0.333739
      T23 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:118 = 0.872492
        genesis.attribute@agent:118 = 0.2112
        genesis.attribute@agent:118 = 0.093138
        genesis.attribute@agent:118 = 0.395042
      Writes:
        agent:118.alive: none → true
        agent:118.health: none → 91.17475
        agent:118.hunger: none → 0.16336
        agent:118.immunity: none → 0.301226
        agent:118.infected: none → false
        agent:118.region: none → region:8
        agent:118.risk_tolerance: none → 0.395042
      T151657 AgentSystem.agent.metabolism (tick 85)
      Inputs:
        agent:118.hunger = 0.0 ← T150603
        agent:118.immunity = 0.333071 ← T150603
        agent:118.region = region:8 ← T23
        region:8.food_stock = 2969.563804 ← T151106
        region:8.population = 64 ← T151096
      Writes:
        agent:118.hunger: 0.0 → 0.0
        agent:118.immunity: 0.333071 → 0.333406
      T152143 AgentSystem.agents.census (tick 85)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.region = region:8 ← T12
        agent:118.alive = true ← T23
        agent:118.region = region:8 ← T23
        agent:125.alive = false ← T77113
        agent:125.region = region:8 ← T74944
        agent:128.alive = false ← T70917
        agent:128.region = region:8 ← T34
        … 242 more input(s)
      Writes:
        region:8.population: 64 → 64
        region:8.workers: 64 → 64
      T152153 AgricultureSystem.agriculture.harvest (tick 85)
      Inputs:
        region:8.food_stock = 2969.563804 ← T151106
        region:8.population = 64 ← T151096
        region:8.rainfall = 0.639027 ← T151116
        region:8.soil_fertility = 0.486241 ← T151106
        region:8.temperature = 17.79266 ← T151116
        region:8.workers = 64 ← T151096
      Random:
        agriculture.crop_variance@region:8 = 0.996832
      Writes:
        region:8.food_stock: 2969.563804 → 2981.463874
        region:8.soil_fertility: 0.486241 → 0.485341
  T155298 AgentSystem.agent.health (tick 89)
  Inputs:
    agent:118.alive = true ← T23
    agent:118.health = 7.874236 ← T154267
    agent:118.hunger = 0.0 ← T154737
    agent:118.infected = false ← T154237
  Writes:
    agent:118.health: 7.874236 → 9.374236
    T23 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:118 = 0.872492
      genesis.attribute@agent:118 = 0.2112
      genesis.attribute@agent:118 = 0.093138
      genesis.attribute@agent:118 = 0.395042
    Writes:
      agent:118.alive: none → true
      agent:118.health: none → 91.17475
      agent:118.hunger: none → 0.16336
      agent:118.immunity: none → 0.301226
      agent:118.infected: none → false
      agent:118.region: none → region:8
      agent:118.risk_tolerance: none → 0.395042
    T154237 DiseaseSystem.disease.recover (tick 87)
    Inputs:
      agent:118.alive = true ← T23
      agent:118.hunger = 0.0 ← T152698
      agent:118.immunity = 0.333739 ← T152698
      agent:118.infected = true ← T148976
    Random:
      disease.recovery@agent:118 = 0.101104 threshold=0.103435
    Writes:
      agent:118.infected: true → false
      T23 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:118 = 0.872492
        genesis.attribute@agent:118 = 0.2112
        genesis.attribute@agent:118 = 0.093138
        genesis.attribute@agent:118 = 0.395042
      Writes:
        agent:118.alive: none → true
        agent:118.health: none → 91.17475
        agent:118.hunger: none → 0.16336
        agent:118.immunity: none → 0.301226
        agent:118.infected: none → false
        agent:118.region: none → region:8
        agent:118.risk_tolerance: none → 0.395042
      T148976 DiseaseSystem.disease.infect (tick 82)
      Inputs:
        agent:118.alive = true ← T23
        agent:118.health = 26.531088 ← T146827
        agent:118.hunger = 0.0 ← T147335
        agent:118.immunity = 0.332057 ← T147335
        agent:118.infected = false ← T141018
        agent:118.region = region:8 ← T23
        region:8.disease_load = 0.326972 ← T147879
      Random:
        disease.infection@agent:118 = 0.006847 threshold=0.06303
        disease.infection@agent:118 = 0.165685
      Writes:
        agent:118.health: 26.531088 → 18.874236
        agent:118.infected: false → true
      T152698 AgentSystem.agent.metabolism (tick 86)
      Inputs:
        agent:118.hunger = 0.0 ← T151657
        agent:118.immunity = 0.333406 ← T151657
        agent:118.region = region:8 ← T23
        region:8.food_stock = 2981.463874 ← T152153
        region:8.population = 64 ← T152143
      Writes:
        agent:118.hunger: 0.0 → 0.0
        agent:118.immunity: 0.333406 → 0.333739
    T154267 AgentSystem.agent.health (tick 88)
    Inputs:
      agent:118.alive = true ← T23
      agent:118.health = 6.374236 ← T153248
      agent:118.hunger = 0.0 ← T153719
      agent:118.infected = false ← T154237
    Writes:
      agent:118.health: 6.374236 → 7.874236
      T23 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:118 = 0.872492
        genesis.attribute@agent:118 = 0.2112
        genesis.attribute@agent:118 = 0.093138
        genesis.attribute@agent:118 = 0.395042
      Writes:
        agent:118.alive: none → true
        agent:118.health: none → 91.17475
        agent:118.hunger: none → 0.16336
        agent:118.immunity: none → 0.301226
        agent:118.infected: none → false
        agent:118.region: none → region:8
        agent:118.risk_tolerance: none → 0.395042
      T153248 AgentSystem.agent.health (tick 87)
      Inputs:
        agent:118.alive = true ← T23
        agent:118.health = 8.874236 ← T152223
        agent:118.hunger = 0.0 ← T152698
        agent:118.infected = true ← T148976
      Writes:
        agent:118.health: 8.874236 → 6.374236
      T153719 AgentSystem.agent.metabolism (tick 87)
      Inputs:
        agent:118.hunger = 0.0 ← T152698
        agent:118.immunity = 0.333739 ← T152698
        agent:118.region = region:8 ← T23
        region:8.food_stock = 2936.269389 ← T153186
        region:8.population = 64 ← T153176
      Writes:
        agent:118.hunger: 0.0 → 0.0
        agent:118.immunity: 0.333739 → 0.33407
      T154237 DiseaseSystem.disease.recover (tick 87)
      Inputs:
        agent:118.alive = true ← T23
        agent:118.hunger = 0.0 ← T152698
        agent:118.immunity = 0.333739 ← T152698
        agent:118.infected = true ← T148976
      Random:
        disease.recovery@agent:118 = 0.101104 threshold=0.103435
      Writes:
        agent:118.infected: true → false
    T154737 AgentSystem.agent.metabolism (tick 88)
    Inputs:
      agent:118.hunger = 0.0 ← T153719
      agent:118.immunity = 0.33407 ← T153719
      agent:118.region = region:8 ← T23
      region:8.food_stock = 2927.634339 ← T154204
      region:8.population = 64 ← T154194
    Writes:
      agent:118.hunger: 0.0 → 0.0
      agent:118.immunity: 0.33407 → 0.3344
      T23 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:118 = 0.872492
        genesis.attribute@agent:118 = 0.2112
        genesis.attribute@agent:118 = 0.093138
        genesis.attribute@agent:118 = 0.395042
      Writes:
        agent:118.alive: none → true
        agent:118.health: none → 91.17475
        agent:118.hunger: none → 0.16336
        agent:118.immunity: none → 0.301226
        agent:118.infected: none → false
        agent:118.region: none → region:8
        agent:118.risk_tolerance: none → 0.395042
      T153719 AgentSystem.agent.metabolism (tick 87)
      Inputs:
        agent:118.hunger = 0.0 ← T152698
        agent:118.immunity = 0.333739 ← T152698
        agent:118.region = region:8 ← T23
        region:8.food_stock = 2936.269389 ← T153186
        region:8.population = 64 ← T153176
      Writes:
        agent:118.hunger: 0.0 → 0.0
        agent:118.immunity: 0.333739 → 0.33407
      T154194 AgentSystem.agents.census (tick 87)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.region = region:8 ← T12
        agent:118.alive = true ← T23
        agent:118.region = region:8 ← T23
        agent:125.alive = false ← T77113
        agent:125.region = region:8 ← T74944
        agent:128.alive = false ← T70917
        agent:128.region = region:8 ← T34
        … 242 more input(s)
      Writes:
        region:8.population: 64 → 64
        region:8.workers: 64 → 64
      T154204 AgricultureSystem.agriculture.harvest (tick 87)
      Inputs:
        region:8.food_stock = 2936.269389 ← T153186
        region:8.population = 64 ← T153176
        region:8.rainfall = 0.646824 ← T153196
        region:8.soil_fertility = 0.484441 ← T153186
        region:8.temperature = 18.906004 ← T153196
        region:8.workers = 64 ← T153176
      Random:
        agriculture.crop_variance@region:8 = 0.816728
      Writes:
        region:8.food_stock: 2936.269389 → 2927.634339
        region:8.soil_fertility: 0.484441 → 0.483541
  T155763 AgentSystem.agent.metabolism (tick 89)
  Inputs:
    agent:118.hunger = 0.0 ← T154737
    agent:118.immunity = 0.3344 ← T154737
    agent:118.region = region:8 ← T23
    region:8.food_stock = 2910.509559 ← T155219
    region:8.population = 64 ← T155209
  Writes:
    agent:118.hunger: 0.0 → 0.0
    agent:118.immunity: 0.3344 → 0.334728
    T23 GenesisSystem.genesis.agent (tick 0)
    Random:
      genesis.attribute@agent:118 = 0.872492
      genesis.attribute@agent:118 = 0.2112
      genesis.attribute@agent:118 = 0.093138
      genesis.attribute@agent:118 = 0.395042
    Writes:
      agent:118.alive: none → true
      agent:118.health: none → 91.17475
      agent:118.hunger: none → 0.16336
      agent:118.immunity: none → 0.301226
      agent:118.infected: none → false
      agent:118.region: none → region:8
      agent:118.risk_tolerance: none → 0.395042
    T154737 AgentSystem.agent.metabolism (tick 88)
    Inputs:
      agent:118.hunger = 0.0 ← T153719
      agent:118.immunity = 0.33407 ← T153719
      agent:118.region = region:8 ← T23
      region:8.food_stock = 2927.634339 ← T154204
      region:8.population = 64 ← T154194
    Writes:
      agent:118.hunger: 0.0 → 0.0
      agent:118.immunity: 0.33407 → 0.3344
      T23 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:118 = 0.872492
        genesis.attribute@agent:118 = 0.2112
        genesis.attribute@agent:118 = 0.093138
        genesis.attribute@agent:118 = 0.395042
      Writes:
        agent:118.alive: none → true
        agent:118.health: none → 91.17475
        agent:118.hunger: none → 0.16336
        agent:118.immunity: none → 0.301226
        agent:118.infected: none → false
        agent:118.region: none → region:8
        agent:118.risk_tolerance: none → 0.395042
      T153719 AgentSystem.agent.metabolism (tick 87)
      Inputs:
        agent:118.hunger = 0.0 ← T152698
        agent:118.immunity = 0.333739 ← T152698
        agent:118.region = region:8 ← T23
        region:8.food_stock = 2936.269389 ← T153186
        region:8.population = 64 ← T153176
      Writes:
        agent:118.hunger: 0.0 → 0.0
        agent:118.immunity: 0.333739 → 0.33407
      T154194 AgentSystem.agents.census (tick 87)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.region = region:8 ← T12
        agent:118.alive = true ← T23
        agent:118.region = region:8 ← T23
        agent:125.alive = false ← T77113
        agent:125.region = region:8 ← T74944
        agent:128.alive = false ← T70917
        agent:128.region = region:8 ← T34
        … 242 more input(s)
      Writes:
        region:8.population: 64 → 64
        region:8.workers: 64 → 64
      T154204 AgricultureSystem.agriculture.harvest (tick 87)
      Inputs:
        region:8.food_stock = 2936.269389 ← T153186
        region:8.population = 64 ← T153176
        region:8.rainfall = 0.646824 ← T153196
        region:8.soil_fertility = 0.484441 ← T153186
        region:8.temperature = 18.906004 ← T153196
        region:8.workers = 64 ← T153176
      Random:
        agriculture.crop_variance@region:8 = 0.816728
      Writes:
        region:8.food_stock: 2936.269389 → 2927.634339
        region:8.soil_fertility: 0.484441 → 0.483541
    T155209 AgentSystem.agents.census (tick 88)
    Inputs:
      agent:108.alive = true ← T12
      agent:108.region = region:8 ← T12
      agent:118.alive = true ← T23
      agent:118.region = region:8 ← T23
      agent:125.alive = false ← T77113
      agent:125.region = region:8 ← T74944
      agent:128.alive = false ← T70917
      agent:128.region = region:8 ← T34
      … 242 more input(s)
    Writes:
      region:8.population: 64 → 64
      region:8.workers: 64 → 64
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
        agent:108.immunity: none → 0.665084
        agent:108.infected: none → false
        agent:108.region: none → region:8
        agent:108.risk_tolerance: none → 0.239165
      T23 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:118 = 0.872492
        genesis.attribute@agent:118 = 0.2112
        genesis.attribute@agent:118 = 0.093138
        genesis.attribute@agent:118 = 0.395042
      Writes:
        agent:118.alive: none → true
        agent:118.health: none → 91.17475
        agent:118.hunger: none → 0.16336
        agent:118.immunity: none → 0.301226
        agent:118.infected: none → false
        agent:118.region: none → region:8
        agent:118.risk_tolerance: none → 0.395042
      T34 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:128 = 0.505603
        genesis.attribute@agent:128 = 0.44361
        genesis.attribute@agent:128 = 0.015974
        genesis.attribute@agent:128 = 0.980871
      Writes:
        agent:128.alive: none → true
        agent:128.health: none → 80.1681
        agent:128.hunger: none → 0.233083
        agent:128.immunity: none → 0.258786
        agent:128.infected: none → false
        agent:128.region: none → region:8
        agent:128.risk_tolerance: none → 0.980871
      T45 GenesisSystem.genesis.agent (tick 0)
      Random:
        genesis.attribute@agent:138 = 0.426973
        genesis.attribute@agent:138 = 0.894767
        genesis.attribute@agent:138 = 0.095581
        genesis.attribute@agent:138 = 0.87364
      Writes:
        agent:138.alive: none → true
        agent:138.health: none → 77.809192
        agent:138.hunger: none → 0.36843
        agent:138.immunity: none → 0.30257
        agent:138.infected: none → false
        agent:138.region: none → region:8
        agent:138.risk_tolerance: none → 0.87364
      … 183 more parent(s)
    T155219 AgricultureSystem.agriculture.harvest (tick 88)
    Inputs:
      region:8.food_stock = 2927.634339 ← T154204
      region:8.population = 64 ← T154194
      region:8.rainfall = 0.607687 ← T154214
      region:8.soil_fertility = 0.483541 ← T154204
      region:8.temperature = 19.033121 ← T154214
      region:8.workers = 64 ← T154194
    Random:
      agriculture.crop_variance@region:8 = 0.819486
    Writes:
      region:8.food_stock: 2927.634339 → 2910.509559
      region:8.soil_fertility: 0.483541 → 0.482641
      T154194 AgentSystem.agents.census (tick 87)
      Inputs:
        agent:108.alive = true ← T12
        agent:108.region = region:8 ← T12
        agent:118.alive = true ← T23
        agent:118.region = region:8 ← T23
        agent:125.alive = false ← T77113
        agent:125.region = region:8 ← T74944
        agent:128.alive = false ← T70917
        agent:128.region = region:8 ← T34
        … 242 more input(s)
      Writes:
        region:8.population: 64 → 64
        region:8.workers: 64 → 64
      T154204 AgricultureSystem.agriculture.harvest (tick 87)
      Inputs:
        region:8.food_stock = 2936.269389 ← T153186
        region:8.population = 64 ← T153176
        region:8.rainfall = 0.646824 ← T153196
        region:8.soil_fertility = 0.484441 ← T153186
        region:8.temperature = 18.906004 ← T153196
        region:8.workers = 64 ← T153176
      Random:
        agriculture.crop_variance@region:8 = 0.816728
      Writes:
        region:8.food_stock: 2936.269389 → 2927.634339
        region:8.soil_fertility: 0.484441 → 0.483541
      T154214 ClimateSystem.climate.step (tick 87)
      Inputs:
        region:8.climate_volatility = 0.556371 ← T1009
        region:8.rainfall = 0.646824 ← T153196
        region:8.rainfall_base = 0.702223 ← T1009
        region:8.temperature = 18.906004 ← T153196
        region:8.temperature_base = 18.31727 ← T1009
      Random:
        climate.temperature_noise@region:8 = 0.697207
        climate.rain@region:8 = 0.081528
      Writes:
        region:8.rainfall: 0.646824 → 0.607687
        region:8.temperature: 18.906004 → 19.033121
  … 1 more parent(s)
```

## Reproduction

```bash
python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 --ticks 10000 --db runs/survival_seed7.db --report <path>
```

Same seed + kernel v0.1.0 + ruleset 0.1.0 → bit-identical world, identical traces, identical report.