# v0.10 — чувствительность вердикта к окну наблюдения

Один записанный мир: seed 7, 54 агента, 600 тиков, протокол v0.8 (`amend 0.15` тики 20–23, `water 1.0` тики 24–27). Окна: 20, 50, 100 тиков.

## Сколько целей меняют вердикт

Всего целей, восстановленных из архива: 21. Меняют вердикт хотя бы в одном окне: 8.

| окно | вердикты |
|---:|---|
| 20 | active: 2, resolved: 10, resolved_with_cost: 8, settling: 1 |
| 50 | active: 2, resolved: 9, resolved_with_cost: 5, settling: 5 |
| 100 | active: 2, resolved: 10, resolved_with_cost: 3, settling: 6 |

## Цели, зависящие от окна

| цель | открыта | окно 20 | окно 50 | окно 100 |
|---|---:|---|---|---|
| renew `cell:0:0` | 373 | resolved | resolved_with_cost | settling |
| renew `cell:0:1` | 45 | resolved_with_cost | resolved | resolved |
| renew `cell:0:1` | 384 | resolved | settling | settling |
| renew `cell:1:1` | 55 | resolved_with_cost | resolved | resolved |
| renew `cell:1:1` | 374 | resolved_with_cost | settling | settling |
| renew `cell:1:2` | 396 | resolved | settling | settling |
| renew `cell:1:3` | 65 | resolved_with_cost | resolved_with_cost | resolved |
| renew `cell:1:3` | 400 | resolved_with_cost | settling | settling |

## Как читать это

- Более широкое окно может только ЗАДЕРЖАТЬ вердикт (`settling`), но задержка иногда полезна: за 100 тиков успевают проявиться смерти, и `resolved` превращается в `resolved_with_cost` или `collapsed`.
- Если вердикт меняется, интерфейс не должен показывать его как установленный факт без окна: рядом с вердиктом обязано стоять, на каком горизонте он получен.
- Это НЕ доказательство, что 20 (или 100) — правильный горизонт. Это измерение зависимости; выбор горизонта остаётся решением игрока или сценария.

## Ограничения

- Один мир, один протокол: чувствительность к окну может быть иной в других режимах, и это следующий вопрос, а не текущий ответ.
- Цели, открытые у самого конца записи, физически не могут набрать большое окно — для них `settling` ожидаем.
