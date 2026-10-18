# v0.13 — Godot-срез: карта и действие поверх Python-ядра

Статус: **код написан, тесты Python-стороны зелёные; Godot-проект не запускался и не собирался.**
Движок Godot в песочнице установить не удалось (прямая загрузка релиза заблокирована,
пакеты через PyPI/npm — не движок). Поэтому всё, что зависит от движка (сцена, поток
чтения, каналы, мышь, камера), **не проверено**. Сборки Windows и Linux не выполнялись.

## Архитектура

```
Godot (GDScript, клиент)                 Python (ядро, источник истины)
  game.gd  ── контроллер                   server/jsonl.py  ── stdio JSON Lines
   │  py_bridge.gd  OS.execute_with_pipe ──►   │ causal-world-jsonl/1
   │  (чтение в Thread → Mutex → очередь)  ◄── │ ready/welcome/view/frame/error
   │  dto.gd  валидация по contract/v1.json    server/dispatch.py  (transport-free)
   │                                           server/session.py   Session (look, decide, _status)
  world_map.gd  карта, камера, выбор клетки     kernel/ + systems/ (правила не менялись)
  cell_panel.gd панель: факты / связи / гипотезы
```

* Ядро — отдельный процесс. Клиент не считает состояние: разница между кадрами — два факта рядом.
* Протокол версионируется строкой `causal-world-jsonl/1`; `ready` при несовпадении версии → отказ.
* Один запрос в полёте: кнопка блокируется до ответа.
* Ответ, не прошедший проверку по `contract/v1.json`, не отображается, а ошибка пишется в лог.
* Клиентский контракт и Python-тест читают один файл `client/godot/contract/v1.json`.

## Изменения ядра (минимальные, без изменения правил)

| Файл | Что |
|---|---|
| `src/causal_world/server/dispatch.py` | новый: transport-free `Dispatcher`; логика из `ws.py` без изменения семантики; команда `look` |
| `src/causal_world/server/ws.py` | использует `Dispatcher` |
| `src/causal_world/server/jsonl.py` | новый: stdio-адаптер, ошибки `protocol_mismatch`, `malformed`, `seq_gap`, `conflict`, `unknown_type`, `not_awaiting`, `finalized`, `world_busy`; логи в stderr |
| `src/causal_world/server/session.py` | `look()` → `view` (только чтение, шага нет); общий `_status(view)` для `frame` и `view`; `_render` использует его |

Проверка, что рефакторинг `_render` не изменил кадры: golden-тесты ядра и
`tests/test_godot_determinism.py` (хеши журнала на каждом тике) проходят без изменения эталонов.

## Клиент (`client/godot/`)

| Файл | Назначение |
|---|---|
| `project.godot` | Godot 4.4, 1280×720, GL Compatibility |
| `scenes/main.tscn` | корень `Node2D` со скриптом контроллера |
| `scripts/protocol/py_bridge.gd` | запуск `python -c` (`OS.execute_with_pipe`), чтение в потоке, `store_string`, `shutdown` → `OS.kill` |
| `scripts/protocol/dto.gd` | проверка по контракту, типизированные `View`, `Cell`, `Region` |
| `scripts/game/game.gd` | протокол: ready → hello → welcome → look → view; decide → frame; журнал результата |
| `scripts/game/world_map.gd` | сетка по координатам ядра, камера (правая/средняя кнопка — сдвиг, колесо — масштаб), клик |
| `scripts/game/cell_panel.gd` | факты клетки, связи (ситуации/цели со ссылками на T-id), гипотезы (`confidence=hypothesis`) |
| `contract/v1.json` | поля и типы ответов: ready, welcome, error, view, frame, frame.you/journal/world/cell/region |
| `README.md` | запуск, поиск Python, ограничения |

Поиск Python: аргумент `--python=`, затем `CAUSAL_WORLD_PYTHON`, затем `.venv`, затем системный `python3`/`python`.

## Сценарий

`player_resettle`, seed 7, 2 региона, 54 агента, `max_ticks` 200. Игрок один раз нажимает «работать».
Эталон (`tests/golden/godot_slice_reference.json`): 46 нажатий, смерть на тике 45 (seq 46, `alive=false`),
кадр `finished` приходит вместе с кадром смерти; первый хеш журнала `3b677a75…`, последний `19a24ad1…`.

## Тесты

| Файл | Проверяет | Результат |
|---|---|---|
| `tests/test_godot_contract.py` | реальные welcome, view (до и после шага), frame (вся жизнь, кадр смерти), error и `out_of_range` соответствуют контракту; координаты клеток уникальны; строка запуска из `py_bridge.gd` извлекается и запускается как подпроцесс | 9 passed |
| `tests/test_jsonl_protocol.py` | реальный stdio-процесс: ready, refusal по версии, gap/conflict/malformed (ни один отказ не двигает мир), пустые строки, EOF, close → finalized, `look` только читает | 7 passed |
| `tests/test_godot_determinism.py` | stdio совпадает с in-process по хешу на каждом тике; совпадение с golden | 3 passed |
| полный `pytest` | ядро и всё остальное | exit 0, без падений |
| `gdlint` (gdtoolkit 4.5.0) | все `client/godot/scripts/**/*.gd` | без замечаний |
| `gdparse` | все `.gd` | парсятся |
| `pyflakes` | изменённые Python-файлы | чисто |

## Известные ограничения

* Godot не запускался: сцена, поток чтения, каналы, мышь и камера не проверены. Первый запуск в редакторе — обязательный шаг.
* Сборки Windows и Linux не выполнялись; поиск Python по правилам Windows не тестировался.
* Экспорт: `res://` упакован, корень репозитория из него не найти — нужно передавать `--src=` и `--python=`.
* Архив миров пишется в `user://worlds`; каждый запуск — свой мир (именованный мир после EOF даёт `world_busy`).
* Один игровой ход — «работать». Других действий, графики и анимаций в срезе нет (по требованию: минимальный работающий срез).
* Оценки «устойчивости» поселения не выводятся клиентом; панель показывает только то, что отдаёт ядро.

## Исправления после первого запуска в Godot 4.4

Первый запуск выявил три проблемы; все исправлены в коде, но проверены только тестами Python-стороны и статической проверкой GDScript.

1. **Неописанная цель и конец жизни.** В начало лога добавлено объяснение: что это, что делать, когда жизнь заканчивается. При смерти выводится тик смерти и причина из `finished.autopsy.label` (`acute_infection` → «острая инфекция», `starvation` → «голод», и т. д.). Клиент не выдумывает причину. «Начать заново» создаёт новый мир. На эталонном сценарии (`work` ×46) смерть на тике 45 вызвана `disease.infect`, то есть классификатор отнёс её к `acute_infection`.
2. **Зависание при «Выход».** Прежний код вызывал `get_as_text()` на stderr-канале в главном потоке и ждал фиксированные 1.5 с. Теперь stdout и stderr читаются построчно в двух фоновых потоках, остановка не блокирует главный поток, а выход ждёт `bridge_ended` (ядро отвечает `bye` или после таймаута убивается).
3. **Ошибка «Invalid UTF-8 leading byte».** Причина — многобайтовые символы в каналах, которые клиент декодирует по частям. Ядро теперь пишет в stdout и stderr только ASCII (`jsonl.py`: `reconfigure(encoding="ascii", errors="backslashreplace")`). Тест `test_godot_launcher_string_starts_the_core` отправляет кириллицу и проверяет, что оба канала остаются ASCII.

Также добавлен тест `test_gdscript_private_names_are_declared`: он ловит необъявленные приватные имена, которые `gdparse` не видит (как `_quit_button`).

### Autopsy и трасса на пути с пробелами и «—» (после второго запуска)

- **Autopsy:** `autopsy_error: unable to open database: …life-*.db?mode=ro`. Причина:
  `QueryIndex` подключал архив через `ATTACH 'file:<path>?mode=ro'` на соединении
  без `uri=True`, а URI строился вручную. Исправлено: `read_only_uri()` (`Path.as_uri()`),
  параметризованный `ATTACH`. На Linux ошибка не воспроизводилась (ни с «—», ни без);
  Windows-запуск не проверен.
- **Трасса на смерти:** `Cannot operate on a closed database`. Шаг трассы читает
  переходы через read-only `JournalView.since(id)`, не через закрытый журнал.
- **Объём:** по умолчанию одна сводка на решение (~4 строки, жизнь на 46 ходов ≈ 234 строки);
  построчный вывод только с `--trace-detail` (≈3000 строк на жизнь).
- **Проверка:** полный pytest зелёный (exit 0); `tests/test_core_trace.py`,
  `tests/test_readonly_paths.py` покрывают смерть на пути с «—».
  Godot в этой среде не запускался.
