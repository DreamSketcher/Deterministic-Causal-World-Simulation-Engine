# v0.6 step 5 — протокол игровой сессии (контракт v0)

Статус: ратифицируемый контракт. Ядро не расширяется; Rust не начинается.
Единственная новая механика яруса персистентности: `SqliteArchive.commit()`
(публичный flush поверх существующего батч-COMMIT) — это G1, не движок.

## 0. Инварианты (наследуются, не пересматриваются)

- **Q1/Q2**: полное синхронное исполнение; соединение с сетью — не игровое
  событие. Разрыв, таймаут, garbage-in **не рождают действий** в мире.
  Idle по таймауту из `DecisionChannel` в сессии не используется: сессия
  блокируется сама, канал всегда предзаполнен ровно одним действием.
- **G1**: `persist=` активен с тика 1. Второго механизма истории нет:
  `frames` сервера — кэш отрисовки, не источник; после рестарта процесса
  всё восстанавливается из архива (`bio`, `DecisionStreamReader`-реплей).
- **G4**: журнал — единственный источник истины для реплея, AUTOPSY и
  BiographyCard. Все три читаются из архива, не из памяти сервера.
- Транспортная инвариантность (P1): один `(seed, ruleset-config, поток
  решений, tail-политика)` → идентичный `journal.hash()` и идентичный
  fingerprint карточки, локально и через WebSocket.

## 1. Порядок исполнения (точка приёмки решения)

`validate → deliver → step → persist/flush → frame`

1. Валидация сообщения (тип/поля/seq) — ошибки короткозамыкаются **до** мира.
2. `channel.deliver(action)` — ещё не мир, только очередь.
3. `sim.step()` — `player.act` попадает в журнал (отказ мира включительно:
   внедиапазонный `action` живёт здесь и остаётся в журнале verbatim).
4. `journal.commit()` — **решение принято в этот момент**: transition
   дораблемен; падение процесса после шага 4 воспроизводимо из БД.
5. Отрисовка и отправка `frame`. `world`-секция кадра читается из
   `sim.state` (view-only).

Один кадр = один шаг = одно принятое решение. Пустой вход не двигает мир.

## 2. Идемпотентность

- `decide {seq, action}`, `seq` — строгая последовательность клиента, 1-based.
- Сервер хранит `decisions[seq]` и `frames[seq]` (in-proc кэш реконнекта).
- Повтор `seq` с **тем же** `action` → тот же `frame`, шаг НЕ повторяется.
- Тот же `seq`, другой `action` → `error {code:"conflict"}`, мир не трогается.
- `seq > last+1` → `error {code:"seq_gap", resync:{last_seq}}` — клиент
  перепривязывается, ничего не отбрасывается молча.
- Решения, пришедшие не в состоянии `awaiting_decision`, → `error`
  (`dead` / `finalized`), доставка не происходит.
- Реконнект: `hello {session}` → `welcome {last_seq, tick, alive}`;
  непринятое решение клиент шлёт повторно (см. правило повтора).

## 3. Авторитет сервера

- Клиент не отправляет tick/state/результаты; только `action`.
- Параметры мира (`seed, ruleset, regions, agents, max_ticks, tail_ticks`)
  задаются в `hello` при создании и более не читаются из сокета: игнор
  конфигурации при resume — серверный авторитет, в `welcome` поле `config`.
- Мировые отказы (`applied:false`) — семантика движка, не транспорта;
  протокол их честно пересылает в `frame.reject`.

## 4. Жизненный цикл

```
created → awaiting_decision(tick T) --decide→ step → awaiting(T+1)
        → player_dead → epilogue(tail_ticks) → finished(death|tick_limit)
        → [bio/autopsy доступны] → close (finalize, journal.close())
        → finalized (bio/autopsy читаются из БД; close идемпотентен)
```

- Смерть не закрывает доступ: сессия остаётся в реестре; `bio`/`autopsy`
  отвечают в `finished` и после `finalized`. Уничтожается только процесс.
- `autopsy` до смерти → `error {code:"alive"}`.
- `autopsy` = запись смерти (tick, operation, die-кубик) +
  `DeathClassifier.classify` по journal (дизайн Q3 сохранён).

## 5. Сообщения (JSON, по одному на кадр)

client→server:
`hello {session?, seed, ruleset, regions, agents, max_ticks?, tail_ticks?}`
`decide {seq, action:int(any int; вне карточки = мир откажет)}`
`bio {agent?, md?}` | `autopsy {}` | `close {}`

server→client:
`welcome {session_id, tick, alive, last_seq, config, db_path, action_card}`
`frame {seq, tick, applied, reject?, you{hunger,health,region,last_action},
        journal{total,committed,rejected,hash}}`
`biography {fingerprint, card{...summary...}, md?}`
`autopsy {death_tick, operation, die?, label, cause_chain{depth,truncated}}`
`finished {reason, death_tick?, bio_fingerprint?}`
`error {code, msg, seq?}`; коды: `malformed unknown_type not_awaiting dead
finalized conflict seq_gap alive`

Malformed (битый JSON, не-dict, отсутствующие поля) — `error`, соединение
живёт. Только `close`/смерть процесса завершают.

## 6. Транспортная проверка (критерий приёмки шага 5)

Тесты (без сети → с сетью):
1. state-machine: повтор=тот же кадр, один шаг; conflict/garbage — мир не
   тронут; gap → resync; bio во время игры читается (после каждого commit).
2. жизнь до смерти через `Session` напрямую: finished по смерти,
   tail=0; autopsy label; bio-открыт после close.
3. WS e2e: 52 решения через сокет (тот же rng99/seed7 скрипт) →
   `journal.hash()` == локальный baseline, fingerprint карточки == локальный;
   reconnekt посередине с повторной доставкой не меняет ни хэш, ни карточку;
   мусор в сокет не ломает сессию (последующий decide проходит).

Границы v0 (зафиксировано, не болит): resume кадров — только в живом
процессе; мультиклиент на сессию — нет; сжатие/бинарные фреймы — нет.
