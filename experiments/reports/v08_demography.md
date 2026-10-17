# v0.8 — демографическая диагностика живого мира

Прогон: seed 7, 2 региона, 100 агентов, 700 тиков. Каждый зонд меняет РОВНО ОДИН фактор.

## 1. Сводка

| зонд | пик населения | тик пика | вымирание | рождений | смертей | причина смерти |
|---|---|---|---|---|---|---|
| baseline (player_civic as shipped) | 100 | 0 | 248 | 1 | 451 | agent.death=96, disease.infect=355 |
| probe A: no age death | 100 | 0 | 248 | 1 | 451 | agent.death=96, disease.infect=355 |
| probe B: no disease system | 100 | 0 | 265 | 0 | 100 | agent.death=100 |
| probe C: birth rate x10 | 103 | 30 | 257 | 11 | 495 | agent.death=104, disease.infect=391 |
| control: compost research world (no age death, no heredity) | 100 | 0 | 246 | 0 | 448 | agent.death=95, disease.infect=353 |

## 2. Кривая населения (каждые 25 тиков)

| тик | baseline (player_civic as shipped) | probe A | probe B | probe C | control |
|---|---|---|---|---|---|
| 0 | 100 | 100 | 100 | 100 | 100 |
| 25 | 100 | 100 | 100 | 101 | 100 |
| 50 | 90 | 90 | 100 | 96 | 90 |
| 75 | 56 | 56 | 100 | 64 | 55 |
| 100 | 55 | 55 | 68 | 65 | 54 |
| 125 | 55 | 55 | 67 | 66 | 54 |
| 150 | 55 | 55 | 67 | 66 | 54 |
| 175 | 55 | 55 | 67 | 66 | 54 |
| 200 | 55 | 55 | 67 | 66 | 54 |
| 225 | 51 | 51 | 67 | 64 | 50 |
| 250 | 0 | 0 | 19 | 1 | 0 |
| 275 | 0 | 0 | 0 | 0 | 0 |
| 300 | 0 | 0 | 0 | 0 | 0 |
| 325 | 0 | 0 | 0 | 0 | 0 |
| 350 | 0 | 0 | 0 | 0 | 0 |
| 375 | 0 | 0 | 0 | 0 | 0 |
| 400 | 0 | 0 | 0 | 0 | 0 |
| 425 | 0 | 0 | 0 | 0 | 0 |
| 450 | 0 | 0 | 0 | 0 | 0 |
| 475 | 0 | 0 | 0 | 0 | 0 |
| 500 | 0 | 0 | 0 | 0 | 0 |
| 525 | 0 | 0 | 0 | 0 | 0 |
| 550 | 0 | 0 | 0 | 0 | 0 |
| 575 | 0 | 0 | 0 | 0 | 0 |
| 600 | 0 | 0 | 0 | 0 | 0 |
| 625 | 0 | 0 | 0 | 0 | 0 |
| 650 | 0 | 0 | 0 | 0 | 0 |
| 675 | 0 | 0 | 0 | 0 | 0 |
| 700 | 0 | 0 | 0 | 0 | 0 |

## 3. Возрастная структура (сумма по всем сэмплам)

| зонд | 0-50 | 100-150 | 150-200 | 200-250 | 50-100 | средний возраст в конце | макс. возраст |
|---|---|---|---|---|---|---|---|
| baseline (player_civic as shipped) | 202 | 110 | 109 | 104 | 147 | 0.0 | 0 |
| probe A: no age death | 202 | 110 | 109 | 104 | 147 | 0.0 | 0 |
| probe B: no disease system | 200 | 135 | 134 | 134 | 19 | 200 | 0.0 | 0 |
| probe C: birth rate x10 | 221 | 131 | 124 | 110 | 1 | 168 | 0.0 | 0 |
| control: compost research world (no age death, no heredity) | 200 | 108 | 108 | 104 | 145 | 0.0 | 0 |

## 4. Рождаемость: чем ограничена

| зонд | тиков, ограниченных ёмкостью | тиков, ограниченных едой | первое рождение |
|---|---|---|---|
| baseline (player_civic as shipped) | 0 | 2 | 54 |
| probe A: no age death | 0 | 2 | 54 |
| probe B: no disease system | 0 | 2 | — |
| probe C: birth rate x10 | 0 | 2 | 23 |
| control: compost research world (no age death, no heredity) | 2 | 2 | — |

## 5. Финальное состояние регионов (baseline)

| регион | население | ёмкость | почва | еда | еда/чел. | ограничено ёмкостью | ограничено едой |
|---|---|---|---|---|---|---|---|
| region:0 | 0 | 52 | 0.050 | 0.0 | 0.00 | нет | да |
| region:1 | 0 | 52 | 0.050 | 0.0 | 0.00 | нет | да |

## 6. Отпечатки

- **baseline (player_civic as shipped)** — state `a37d5ccc9761b465`, journal `79913a0e6305ecfd`
- **probe A: no age death** — state `a37d5ccc9761b465`, journal `79913a0e6305ecfd`
- **probe B: no disease system** — state `e18f3c55df48a927`, journal `3057de54d0c0c3e6`
- **probe C: birth rate x10** — state `a61eb1c5625ca430`, journal `33ec7abf5b2e632e`
- **control: compost research world (no age death, no heredity)** — state `bedf5cba09614227`, journal `d0803be5ed5d98d2`
