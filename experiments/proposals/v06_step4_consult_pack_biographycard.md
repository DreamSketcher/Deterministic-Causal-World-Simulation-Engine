# Пак для консалтинга, шаг 4: BiographyCard против реального CausalQuery

Документ собран из фактического кода репозитория (ветка
`arena/8eafe912-deterministic-causal-world-sim`, HEAD `b6864db`), а не из
описаний. Цель: дать консультанту точные ограничения, в рамках которых нужно
утвердить контракт BiographyCard v1. Формат каждого раздела: что уже доказано
→ что означает для контракта → где соблазн уйти в лишнее.

## 0. Три детерминизма: честное состояние доказательств

| слой | статус | чем доказано |
|---|---|---|
| Детерминизм симуляции | ✅ замкнут | тесты идентичности state/journal хэшей (seed → мир); research-миры на pinned-хэшах; инвариант I8 (адресный RNG: добавление систем не сдвигает чужие броски) |
| Детерминизм протокола | 🟡 только правила потребления | канал: ровно одно решение на живой тик; мёртвый агент не потребляет ничего; out-of-range потребляется и записывается (реплей не разъезжается); блокирующий recv с фолбэком в idle по таймауту. НЕТ: client seq, дедупликация, реконнект — это шаг 5, риск описан в G5 |
| Причинная объяснимость | 🟡 инфраструктура есть, карточки нет | журнал хранит reads(+source-переход)/writes/draws на каждом переходе, включая ОТКЛОНЁННЫЕ; index: замыкания trace/profile/budget/timeline. BiographyCard — предмет этого пакета |

Ключевое следствие для контракта: **объяснимость уже зашита в формат данных
(каждое чтение помечено переходом-источником последнего значения), карточка
должна её извлекать, а не достраивать.**

## 1. Модель данных (ядро, заморожено с v0.1)

`kernel/transition.py` — всё, что есть в журнале на один переход:

```python
class StateRead:    entity, field, value, source_transition: int|None
class StateChange:  entity, field, old, new
class RandomDraw:   purpose, value: float, threshold: float|None,
                    outcome, entity, index
class Transition:   id, tick, system, operation,
                    reads, writes, random_draws,
                    priority, status: TransitionStatus, reject_reason
```

Гарантии, на которых можно строить карточку (все под тестами):
- `old` в write совпадает со значением на момент вычисления — «stale read»
  структурно невозможен;
- `source_transition` в read — id перехода, последний раз писавшего это
  поле. Это и есть ребро причинного графа: `writer → reader`;
- отклонённые переходы (проигравший конфликт, `reject_reason`) тоже в
  журнале — «кубик сказал нет, и почему» восстанавливаемо;
- тип draw различает слои контракта без новых полей:
  - `threshold is None` и purpose=`player.decision` → **выбор** (значение
    поставлено игроком);
  - `threshold not None` → **случай** (исход; `value` — бросок,
    `outcome = value < threshold` — попадание);
  - отсутствие draw у перехода → **закон** (детерминирован из состояния:
    ruin.age, agriculture.harvest).
  Карточка «твой выбор vs кубик» = группировка по этим трём классам, ничего
  нового в формат не просится.

## 2. Два хранилища журнала — и только одно с запросным слоем

- **In-memory** (`Journal` + `causal/index.CausalIndex`) — живёт в
  `Simulation` всегда. Тонкий API: `writer_of(entity, field)`,
  `history_of(entity, field)`, `dependents_of(tid)`, `has/get(tid)`.
  **CausalQuery поверх него не работает** — билдер фильтров построен на SQL.
- **Архив** (`simulation/archive.SqliteArchive`, режим WAL) — тот же журнал
  + тот же causality-index, один файл, **идентичные хэши** (проверено v0.4).
  Таблицы: `transitions` (payload включает random_draws — hydrate
  восстанавливает переход целиком), `latest_writer`, `history`, `dependents`.
- **Индекс запросов** (`query/index.QueryIndex(view, cache_path)`) — лениво
  строит из архива отдельные таблицы в отдельном cache-файле:
  ```
  idx_writes(entity, field, tid, tick, delta, old, new)
  idx_reads (source_tid, reader_tid, entity, field)     <- сам граф
  idx_entity(entity, tid, tick, role in {writer, reader})
  qmeta: идентичность источника; рассинхрон -> StaleIndexError
  ```
  Идиома сборки (cli, v0.5):
  ```python
  with JournalView(db) as view, QueryIndex(view, cache) as idx:
      q = CausalQuery(idx)
  ```

**Прямое требование к шагу 5 (следствие, а не рекомендация):** sim-server
обязан вести партию с `persist=` с первого тика. AUTOPSY без архива
строилась бы либо на голом `CausalIndex` (нет фильтров/агрегатов), либо на
втором адаптере (развилка семантики — отвергнуто сознательно). In-memory и
архив дают одинаковые хэши, так что сервер на архиве теряет ровно ноль
свойств, а игрок-одиночка на localhost его не заметит.

## 3. Поверхность CausalQuery (все сигнатуры; ничего нового не нужно)

Иммутабельный билдер, каждый метод возвращает копию:

```python
q.system(name) / q.operation(name) / q.entity(id) / q.entity_prefix(prefix)
q.field(name) / q.writes_to(entity, field) / q.ticks(start, end)
q.committed_only() / q.status(value)
q.caused_by(tid, depth) / q.dependents_of(tid, depth)      # рёбра через
q.caused(tid, depth) / q.ancestors_of(tid, depth)          # idx_reads

q.execute() -> итератор полных Transition (ленивые страницы)
q.tids() / q.first() / q.list(limit=1000) / q.count()
q.budget(entity, field, ...)      -> inflows/outflows/net  (уже отвечал на
                                     «что держало агенту жизнь» в v0.4)
q.delta_profile(entity, field, tick_start, tick_end)       -> строки
    (system, operation, count, sum_delta, mean, min, max) — «условия»,
    отличает harvest в CompostAgricultureSystem от harvest в
    AgricultureSystem по фактическим дельтам
q.entropy(by="system", ...)
q.trace(tid, direction="backward"|"forward", depth=20,
        max_nodes=50_000) -> TraceResult(nodes, depths, truncated)
    # BFS по idx_reads; backward = замыкание last-writer-причин
q.timeline(entity_id, limit=1000)  # всё, касавшееся сущности (writer+reader)
```

`index.sql(...)` — честный escape-hatch к SQLite (через него же живут
специфичные места, например «кто писал `parent_id`»).

## 4. Как узлы типов выглядят в журнале сегодня (фактические write-сеты)

- **`player.act`** (PlayerAgentSystem, priority 45): writes `last_action`
  (каждый живой тик, включая idle=6 и reject=−1) + эффектные поля агента
  (`hunger/health/immunity/region`), **для explore — write на `ruin`
  (resource_food) на этом же переходе** (немедленное исполнение, U3). Draw:
  ровно один, `player.decision`, `value=float(action)`, `threshold=None`.
- **`agent.birth`** (BirthSystem): 12 writes на ребёнка (`alive, region,
  parent_id, generation, birth_tick, immune_memory, immunity, max_health,
  health, hunger, risk_tolerance, infected`) + 6 draws: `birth.occurrence`
  (threshold=rate), `birth.select`, `birth.parent`, `birth.mutation`×5
  (уникаются по child-сущности). read родителя → ребро «наследственность от
  X» в графе автоматически.
- **`disease.infect`** (ImmuneDiseaseSystem): writes `infected`, `health`,
  `immune_memory (+0.35)`; draw с threshold=вероятность экспозиции.
- **`agent.explore`** (NPC-путь ExplorationSystem): write hunger-облегчения
  + draw threshold∈[0.02,0.15]; истощение руины — отдельный
  агрегированный `ruin.deplete` (один на (руина,тик)).
- `ruin.activate/age/collapse/note_alive`, `agent.senescence` (draw с
  threshold=кривой смертности), `agents.census`, `agriculture.harvest`…

Важно для «одного узла на действие»: узел есть, даже когда мир ответил «нет»
(explore без найденной руины = только `last_action`; out-of-range =
`last_action=−1` + сырое значение в draw). Молчание выбора невозможно —
это же и есть лосслесс-реплей.

## 5. Контракт консультанта → что даёт код, без нового API

Требование «один узел на действие игрока» — ✅ готово (см. §4).
Остальное отображается так:

1. **Отделение выбора от исхода** — ✅ структурой draw (§1). Никакого
   нового поля не нужно.
2. **«Ссылки на события, действительно необходимые для объяснения»** —
   `trace(death_tid, "backward", depth)` — но нужно принять ограничение
   семантики: замыкание идёт по **last-writer** рёбрам. Это «непосредственно
   необходимые причины» в строгом смысле (цепочка последних значений).
   Хронические **условия** (истощение 150 тиков) last-writer цепочкой
   размазываются по каждому metabolism-тику: либо глубина ~времени жизни,
   либо — рекомендовано — условия берутся агрегатом
   `delta_profile(bio-agent) + budget(entity,"hunger")`, а trace остаётся
   для прямой цепочки смерти. Это и есть ответ на «условие vs причина»:
   данные различают их без новой индексации, но **карточка обязана вызвать
   оба**, иначе не различит.
3. **Пагинация** — `execute()/tids()` ленивые страницы, `list(limit)`,
   `timeline(limit)`, `max_nodes` у trace с честным `truncated`. ✅
4. **Персональный фильтр (AUTOPSY)** — частично: `q.entity(AGENT)` берёт
   всё касавшееся агента (writer+reader роли), `writes_to(AGENT, field)` —
   точечно. «Моё влияние на мир» (чьи дети от меня; руины, разграбленные
   мной) достижимо composition'ом: `q.operation("agent.birth")` + scan
   `parent_id` (рождений за жизнь единицы), explore-влияние видно прямо из
   write на `ruin:` внутри `player.act`. Полноценного фильтра «closure от
   множества сущностей» нет — для карточки v1 и не нужно (см. «что
   отвергнуто» §7-G2).

## 6. Gaps, которые контракт обязан учесть (честно)

- **G1 (блокнер для шага 5):** запросный слой только над архивом →
  серверная партия обязана быть с `persist=`. Дешёвое решение, но его надо
  принять сейчас, чтобы шаг 5 не «дотягивал адаптером».
- **G2 (исходящее влияние):** forward-trace от смерти по плотному миру
  взрывается (в docstring честно; `max_nodes` truncates). Для v1
  рекомендуем «наследие» собирать дёшево: `timeline(ruin, limit)` +
  `operation("agent.birth")` c фильтром по родителю, а не forward-closure.
- **G3 (глубина trace):** дефолт depth=20 ≈ 20 тиков ретро-цепочки; жизнь
  длиннее — условия через profile (см. §5.2), а не подъём depth в
  неограниченность.
- **G4 (броски не индексируются):** purpose draw'ов отсутствует в idx_*.
  Карточке это безразлично (operation ↔ purpose 1:1 в game-ruleset); если
  позже понадобится «все броски с p<0.05» по research-масштабу — таблица
  `idx_draws`, но это YAGNI до реального запроса.
- **G5 (протокольный слой, пример консультанта про двойное решение после
  реконнекта):** сегодня идентификатор тика = момент потребления сервером,
  клиент seq отсутствует как понятие. Предлагаемый контракт шага 5:
  клиент шлёт `(client_seq, action)`; сервер при доставке в канал пишет
  отображение `client_seq → tick` вне симуляции (session meta),
  дедуплицирует по seq, а **источником истины реплея остаётся журнал**
  (`player.act` уже содержит фактический тик и сырое значение —
  воспроизводимость не зависит от клиентского лога и от реконнектов).
  Реализуемо без изменения формата журнала.
- **G6 (genesis):** генезис-переходы — обычные строки с writer-ролями,
  trace до них доходит корректно; спец-обработки «начала жизни» не нужно,
  но у карточки поле `birth_tick`/`genesis` — естественная левая граница
  окна (все запросы с `q.ticks(birth_tick, death_tick)`).

## 7. Предлагаемый контракт BiographyCard v1 (к обсуждению)

Секции (каждая = ≤1 запрос, hydrate по мере надобности, бюджет ~6 запросов
на карточку):

0. **Идентичность партии**: seed, ruleset/rng версии, `initial_state_hash`,
   финальный `journal.hash()` (ручка для P1-проверки «транспорт не меняет
   результат»: клиент получает hash карточки = hash журнала).
1. **Смерть**: tid = `q.writes_to(AGENT,"alive").committed_only()` →
   последний; узел-причина (operation, его draw с threshold = «насколько
   это был кубик»).
2. **Цепочка причины**: `trace(death_tid, backward, depth≈24)` — узлы,
   отфильтрованные до касающихся агента/его региона/его руин → «что именно
   его убило» минимально необходимым.
3. **Условия жизни**: `delta_profile(AGENT)` по всем полям-потокам +
   `budget(AGENT,"hunger")`/`("health")` → «что его держало и что точило»
   (агрегаты по (system,operation) — выбор «heal/rest дали +X здоровья
   против эрозии −Y» прямо из строк).
4. **Лента выборов**: `q.writes_to(AGENT,"last_action").ticks(birth,death)`
   → hydrate → [(tick, action, сырое значение draw)]; группировка
   подряд идущих одинаковых (в т.ч. idle-простыней) — чисто слой карточки,
   журнал остаётся полным.
5. **Наследие**: дети = `q.operation("agent.birth")` c `parent_id==AGENT`
   (полное имя родителя есть в write); разграбленные руины = writes на
   `ruin:` из `player.act` (+ `ruin.deplete`, чьи writes затронули её
   руины).
6. **(опционально) Автопсийный хвост**: «миру после тебя» —
   `q.ticks(death+1, end).entity(его регион)` компактно; только если есть
   посмертный мир (после шага 5 сервер это умеет trivially).

Отвергнуто намеренно: новый CausalQuery-API под карточку; forward-closure
из смерти; отдельная таблица draw-индексов; серверный реплей по клиентскому
логу (G5: журнал — единственный источник истины); перфекционизм нарратива
(первая версия — доказательство ценности существующих данных, по установке
консультанта).

## 8. Минимальная проверка результата (для accept'а контракта)

1. Детерминированный сценарий из §шаг-3 E2E (seed 7, 2×30, скрипт
   решений, ~200 тиков) — прогон с `persist=`;
2. карточка, собранная шестью запросами, golden-файлом;
3. ассерты, которые ловят ровно три слоя:
   - карточка воспроизводится из того же архива побитово (объяснимость);
   - тот же seed+stream через «серверную» доставку → та же карточка
     (протокол; пока на уровне consume-правил);
   - `delta_profile`-суммы сходятся с ручным пересчётом журнала (данные,
     не предположения).

Вопросы консультанту по существу контракта: (а) достаточно ли секций 0–5
для «убедительного объяснения» или нужна 6-я «контрфактика» (trace из
смерти с заменой одного узла — дорого, но uniquely наше); (б) где проходит
граница «необходимой причинности» при depth-лимите trace (24 — моё
предположение, не вывод); (в) приемлемо ли группировать idling'и в
карточке, оставляя журнал полным, или UX требует явного «ничегонеделание
тоже решение» — тогда группировка с счётчиком, не сжатием.
