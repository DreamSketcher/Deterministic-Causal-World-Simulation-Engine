# v0.9 — сквозная ситуация: от обнаружения до нового решения

seed 7, 2 региона, 54 агентов, горизонт 600 тиков, ruleset `player_spatial`.

Это не сценарий-рассказ: все фазы прочитаны из двух архивов, и каждую строку можно проверить `query`/`trace`.

## 1. Наблюдение — мир сам называет проблему (тик 57)

- **hunger** `cell:1:1`: cell:1:1: еды мало (0.7 на человека) — запасы тают (острота 0.40, с тика 56; T9046, T9056, T9056)

## 2. Понимание — бюджет причин, а не догадка

- `cell:1:1.food_stock`: итог -165.6237; вклад: SpatialAgricultureSystem.agriculture.harvest -172.2882; SpatialAgricultureSystem.agriculture.harvest +6.6645
- `cell:1:1.soil_fertility`: итог +0.1631; вклад: SpatialAgricultureSystem.agriculture.harvest +0.1631

## 3. Вмешательство — приказы с явным ответом

| тик | приказ | цель | сила | ответ |
|---:|---|---|---:|---|
| 58 | amend | cell:1:0 | 0.15 | accepted: приказ принят: в силу с тика 58 |
| 59 | amend | cell:1:1 | 0.15 | accepted: приказ принят: в силу с тика 59 |
| 60 | amend | cell:1:2 | 0.15 | accepted: приказ принят: в силу с тика 60 |
| 61 | amend | cell:1:3 | 0.15 | accepted: приказ принят: в силу с тика 61 |
| 62 | water | cell:1:0 | 1.0 | accepted: приказ принят: в силу с тика 62 |
| 63 | water | cell:1:1 | 1.0 | accepted: приказ принят: в силу с тика 63 |
| 64 | water | cell:1:2 | 1.0 | accepted: приказ принят: в силу с тика 64 |
| 65 | water | cell:1:3 | 1.0 | accepted: приказ принят: в силу с тика 65 |

Принято 8 из 8; ни один приказ не потерян молча.

## 4. Проверка — что стало с людьми и землёй

| мир | живых | рождений | смертей | средняя почва | вымерших клеток |
|---|---:|---:|---:|---:|---:|
| base | 38 | 71 | 38 | 0.470 | 4 |
| orders | 77 | 127 | 1 | 0.536 | 0 |

Вердикты целей (мир с приказами): всего 6, решено 6, решено с ценой 0, катастроф 0, переехало 0, проверяется 0, идёт 0.

- **resolved** · feed `cell:1:0` (58–64): люди 10→11, почва 0.4389→0.5647. famine ушёл, население 10 → 11, почва 0.44 → 0.56: система цела
- **resolved** · feed `cell:1:2` (58–67): люди 10→10, почва 0.4953→0.5792. famine ушёл, население 10 → 10, почва 0.50 → 0.58: система цела
- **resolved** · feed `cell:1:1` (57–64): люди 8→11, почва 0.4314→0.5538. famine ушёл, население 8 → 11, почва 0.43 → 0.55: система цела
- **resolved** · restore_soil `cell:0:2` (0–18): люди 7→9, почва 0.2862→0.3975. thin_soil ушёл, население 7 → 9, почва 0.29 → 0.40: система цела
- **resolved** · restore_soil `cell:1:0` (0–14): люди 7→9, почва 0.3026→0.3988. thin_soil ушёл, население 7 → 9, почва 0.30 → 0.40: система цела
- **resolved** · restore_soil `cell:1:1` (0–14): люди 7→8, почва 0.302→0.3968. thin_soil ушёл, население 7 → 8, почва 0.30 → 0.40: система цела

## 5. Сравнение — тот же мир, одно отличие

Архивы расходятся на тике 58 (переход T9413): `player.act` против `player.directive`.

| поле | Δ бюджета база→приказы | структурный контур |
|---|---:|---|
| cell:1:0.food_stock | +387.3635 | no structural loop difference. |
| cell:1:0.soil_fertility | +0.1381 | no structural loop difference. |
| cell:1:1.food_stock | +378.8435 | no structural loop difference. |
| cell:1:1.soil_fertility | +0.1409 | no structural loop difference. |
| cell:1:2.food_stock | +184.3690 | no structural loop difference. |
| cell:1:2.soil_fertility | +0.1220 | regime orders has an inflow (agriculture.harvest) that no_orders lacks: the loop closes. in orders the field is in balance (net=-0.002); in no_orders it declines monotonically (net=-0.125). |
| cell:1:3.food_stock | +208.9380 | no structural loop difference. |
| cell:1:3.soil_fertility | +0.1260 | regime orders has an inflow (agriculture.harvest) that no_orders lacks: the loop closes. |

## 6. Новая проблема из результата

- **birth_stall** `cell:0:1`: cell:0:1: рождений нет уже 214 тиков — ёмкость или еда не дают (с тика 385)

Ёмкость мира: 83.0 мест, занято 77 (93%). Следующий шаг игрока — не «ещё приказ», а решение о ёмкости: новая земля или рост `pop_base` (переселение только перераспределит людей между полными клетками). Это и есть новая задача, которую создал успех.

## Проверяемость

- база: `query --db base.db`; приказы: `query --db orders.db`
- расхождение: `compare` по тем же архивам даёт тик и transition-id
- цели: `goals` читает историю полей из журнала, а не из текста отчёта

