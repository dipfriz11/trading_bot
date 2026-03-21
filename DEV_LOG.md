# Trading Bot Development Log

Проект: Multi-exchange, multi-asset trading bot  
Стратегия: Hedge (LONG + SHORT одновременно)

Архитектура:

- binance_exchange.py
- execution_engine.py
- position_manager.py
- profit_manager.py
- webhook_server.py

---

## 2026-03-11

### Что сделали сегодня

Добавили систему:

AUTO MANUAL CLOSE DETECTION

Логика:

если

cycle_active == True  
и  
позиции на бирже больше нет  

значит позиции были закрыты вручную.

Бот должен:

1. обнаружить manual close
2. вывести REAL CYCLE RESULT
3. выполнить reset_cycle()

Изменения внесены в файл:

execution_engine.py

метод:

execute()

Добавленная проверка:

(prev_long > 0 or prev_short > 0)


---

### Проблема

Manual close detection сейчас не срабатывает.

Сценарий:

1. Бот открывает позиции
2. Позиции закрываются вручную
3. Бот не обнаруживает manual close

В логах:

позиции нет  
но блок

[AUTO SYNC] Manual close detected

не выполняется.

---

### Текущая формула прибыли цикла

cycle_profit =

realized_pnl  
+ funding  
- entry_fees  

Exit комиссии уже входят в realizedPnl (Binance).

---

### TODO

После исправления manual close detection:

1. Вынести размеры позиций в config

2. Добавить в конфиг стратегии:

start_balance  
leverage

3. Добавить в калькулятор:

used margin

и подсветку критической загрузки депозита.

4. Подготовить бота для VPS:

- автозапуск
- восстановление состояния после перезапуска
- проверка открытых позиций
- продолжение цикла

---

### Следующая задача

Исправить AUTO MANUAL CLOSE DETECTION
в

execution_engine.py → execute()

## 2026-03-12

### Stabilization after websocket / restart work

Today we fixed several critical stability issues.

#### Fixed
- Manual close detection works correctly
- WebSocket stops correctly after manual close
- No unwanted reconnect after cycle reset
- Cycle reset works correctly
- Profit monitoring works again

#### Important discovery
state.json can corrupt test results.

If state.json contains old cycle data:
- cycle numbers may be wrong
- restore logic may behave incorrectly

Temporary solution during testing:
delete state.json before running tests.

#### Current stable version
v0.6.1

#### Next tasks
1. Redesign state.json persistence logic
2. Implement safe restart recovery
3. Restore positions after restart
4. Continue architecture development for multi-exchange system

## v0.5 — Restart-safe architecture and state reconciliation

### Дата

2026-03-13

### Основные изменения

Сегодня была завершена ключевая часть архитектуры торгового бота — обеспечение корректной работы системы при рестарте сервера и при ручном закрытии позиций на бирже.

Ранее состояние цикла могло расходиться с фактическим состоянием на бирже. Это приводило к зависшим циклам или некорректному продолжению работы после рестарта.

Архитектура была дополнена механизмами синхронизации состояния между ботом и биржей.

---

### Реализовано

#### 1. BOOT SYNC — reconciliation состояния при запуске

Добавлена проверка соответствия состояния бота и состояния биржи при старте системы.

При запуске выполняется:

* чтение состояния цикла из SQLite
* получение текущих позиций с биржи
* сверка состояния

Обрабатываются следующие случаи:

**CASE 1**

```
cycle_active = True
позиции на бирже нет
```

Считается, что цикл был сломан (например, после manual close или аварийного рестарта).

Бот автоматически:

* выполняет `reset_cycle()`
* очищает `last_sizes`
* предотвращает запуск price monitor.

---

**CASE 2**

```
cycle_active = False
позиция на бирже существует
```

Фиксируется предупреждение в логах о несоответствии состояния.

Цикл автоматически не восстанавливается, чтобы избежать ошибочного продолжения торговли.

---

#### 2. Restart-safe восстановление мониторинга

Если при запуске:

```
cycle_active = True
и
позиция существует на бирже
```

бот:

* восстанавливает `last_sizes`
* запускает `price monitor`
* продолжает текущий цикл.

---

#### 3. Проверка работы manual close

Был протестирован сценарий:

1. бот открыл hedge-позицию
2. позиция была закрыта вручную на Binance
3. бот обнаружил manual close
4. цикл корректно завершился
5. после рестарта бот обнаружил отсутствие позиции
6. цикл был автоматически сброшен.

---

#### 4. Полное тестирование restart-логики

Были протестированы следующие сценарии:

* рестарт бота при открытых позициях
* рестарт бота после manual close
* восстановление price monitor
* сброс сломанного цикла
* корректное принятие нового сигнала после сброса.

Все сценарии отработали корректно.

---

### Результат

Бот теперь устойчив к:

* рестарту сервера
* ручному закрытию позиций
* рассинхронизации состояния между ботом и биржей.

Это ключевой этап подготовки системы к production-эксплуатации.

---

### Следующий этап разработки

Следующим шагом планируется реализация системы управления монетами (Symbol Management):

* таблица `symbols` в SQLite
* статус монеты `active / inactive`
* игнорирование webhook для неактивных монет
* возможность активации и деактивации монет без изменения кода.

Эта система подготовит архитектуру к дальнейшему расширению:

* multi-exchange
* multi-account
* управление торговыми инструментами через базу данных.


DEV LOG — 15.03.2026
Версия

v0.7

symbol registry + DB symbol control + restart-safe symbol loading

Создано:

commit: v0.7
tag: v0.7
branch: stable_v0.7
Основные изменения за день
1. Реализована multi-symbol архитектура

Добавлена полноценная система управления символами через БД.

Таблица symbols (SQLite)

Поля:

symbol
exchange
account
strategy
active
created_at

Теперь бот:

загружает активные символы из БД

создаёт manager для каждого символа

работает multi-symbol

Лог при старте:

Loading active symbols from DB
Symbol manager initialized: BTCUSDT
Symbol manager initialized: XRPUSDT
2. Добавлена двойная система проверки manual close

Manual close теперь определяется двумя механизмами:

1️⃣ webhook_server.py
has_open_position()
cycle_active

если нет позиции:

reset_cycle()
2️⃣ execution_engine.py
prev_long
prev_short
has_open_position()

если:

cycle_active
prev position > 0
no exchange position

→

handle_manual_close()
3. Реализован mark price monitor

Для каждого активного цикла запускается:

start_price_monitor(symbol)

Он:

получает mark price

считает PNL

выводит:

PROFIT DEBUG
CYCLE INFO
TARGET CHECK
4. Реализовано восстановление после рестарта

Метод:

restore_price_monitor()

Логика:

если cycle_active и позиция есть
→ восстановить monitor

если cycle_active и позиции нет
→ reset_cycle()

Это защищает от:

restart сервера
рассинхронизации состояния
5. Исправлена проблема symbol_not_in_config

Выявлено:

webhook проверял БД
build_cycle_config проверял config.py

Это приводило к конфликту.

Решение:

добавление символа в COINS

Протестировано на:

XRPUSDT
6. Проведены тесты manual close

Тест сценариев:

SELL → manual close → BUY
BUY → manual close → SELL

Результаты:

✔ новый сигнал после manual close открывает позиции

Но выявлен баг:

ложный AUTO SYNC во время старта нового цикла
Обнаруженный баг

Во время старта нового цикла иногда происходит:

Starting new cycle
start_price_monitor()
opening orders
↓
AUTO SYNC manual close detected
↓
handle_manual_close()
↓
monitor останавливается

Из-за этого:

WebSocket closed intentionally

и перестаёт обновляться:

PROFIT DEBUG
CYCLE INFO
Предварительная причина

Состояние:

execution_engine.last_sizes

не очищается при reset через webhook.

Поэтому:

prev_long / prev_short > 0

остаётся от предыдущего цикла и вызывает ложный manual close.

План исправления

Необходимо изменить:

webhook_server.py

чтобы при:

reset_cycle()

очищалось также:

execution_engine.last_sizes[symbol]
Текущее состояние проекта

Архитектура:

webhook_server
↓
symbol_registry
↓
execution_engine
↓
exchange
↓
profit_manager

Поддерживается:

multi-symbol
restart-safe
manual close detection
cycle recovery
TODO (следующий этап)

1️⃣ Исправить баг ложного AUTO SYNC

reset last_sizes при reset_cycle

2️⃣ Проверить сценарий

manual close
↓
новый сигнал
↓
start cycle
↓
monitor работает

3️⃣ Проверить continuous profit monitor

PROFIT DEBUG
CYCLE INFO

4️⃣ Подготовить архитектуру к production

Будущие задачи:

multi-account
multi-exchange
configurable strategies

TODO: broken hedge recovery

Если обнаружена ситуация:
LONG > 0 and SHORT = 0
или
SHORT > 0 and LONG = 0

рассмотреть алгоритм:

1. подтвердить состояние через несколько API checks
2. если подтверждено:
   close remaining leg
3. завершить цикл

📘 DevLog — 16.03.2026
Версия
v0.7.1
Основная задача дня

Завершение и стабилизация multi-symbol архитектуры и исправление ошибок BOOT SYNC после рестарта.

Что было реализовано
1. Multi-symbol архитектура

В проект добавлена полноценная поддержка нескольких символов.

Теперь бот может одновременно работать с несколькими инструментами:

BTCUSDT
XRPUSDT
SENTUSDT
...

Реализовано:

SymbolRegistry

отдельный PositionManager для каждого символа

отдельный price monitor для каждого символа

корректная маршрутизация сигналов через webhook

Архитектура:

ExecutionEngine
    │
    └── SymbolRegistry
            │
            ├── PositionManager (BTC)
            ├── PositionManager (XRP)
            └── PositionManager (SENT)
2. Symbol DB управление

Реализовано хранение символов в SQLite:

symbols table

поля:

symbol
exchange
account
strategy
active
created_at

Добавлено:

get_active_symbols()
create_symbol()

Теперь бот автоматически загружает активные символы при старте.

3. Restart-safe symbol loading

После рестарта бот:

1. читает активные символы из DB
2. создаёт SymbolManager для каждого
3. запускает BOOT SYNC

Это позволяет переживать:

server restart
bot crash
manual restart
4. BOOT SYNC восстановление позиций

Добавлена логика восстановления позиций после рестарта.

Алгоритм:

restore_price_monitor()

for each symbol:
    check exchange position

Cases:

CASE 1
cycle_active = True
exchange position = False
→ reset_cycle()

CASE 2
cycle_active = False
exchange position = True
→ warning

CASE 3
cycle_active = True
exchange position = True
→ restore monitor
5. Исправлен критический баг BOOT SYNC

Проблема:

После рестарта:

TARGET PROFIT = 0.000000

Причина:

ProfitManager.target_profit
не восстанавливался

так как start_cycle() не вызывался.

FIX

В restore_price_monitor() добавлено:

self.profit_manager.target_profit = manager.config.target_profit

Перед запуском монитора:

logger.info("[BOOT SYNC] Restoring price monitor")

Теперь после рестарта:

TARGET PROFIT = 0.5

восстанавливается корректно.

6. Проверен restart recovery

Проведены тесты:

тест 1
open position
restart bot

результат:

monitor restored
cycle continues
тест 2
restart
manual close

результат:

manual close detected
cycle reset
тест 3
multi symbol test
XRP
BTC
SENT

позиции восстанавливаются независимо.

Итог состояния системы

Сейчас стабильно работают:

✔ multi-symbol architecture
✔ symbol registry
✔ SQLite symbol storage
✔ restart recovery
✔ BOOT SYNC
✔ manual close detection
✔ restart-safe monitors
✔ webhook routing per symbol
Известное архитектурное ограничение

Сейчас:

ProfitManager один на весь ExecutionEngine

Поэтому:

target_profit общий

Это следующая задача архитектуры.

План на завтра

Главная задача:

ProfitManager → per symbol
Архитектура станет
ExecutionEngine
    │
    └── SymbolRegistry
            │
            └── PositionManager
                    │
                    └── ProfitManager

То есть:

ProfitManager у каждого символа свой
Это позволит

Настраивать:

BTCUSDT   target_profit = 2
XRPUSDT   target_profit = 0.5
SENTUSDT  target_profit = 1

и циклы будут полностью независимы.

📅 Devlog — 17.03.2026

Версия: v0.7.3

🚀 Основные изменения

Перевод target_profit → per-cycle

Реализовано:

Добавлено поле: PositionManager.cycle_target_profit

Фиксация значения при старте цикла (start_cycle)

Сохранение в state (SQLite)

Восстановление при BOOT SYNC

Сброс при завершении цикла (reset_cycle)

check_close_condition переведён на новый источник

Результат:

target_profit теперь фиксируется на цикл

изменения config не влияют на активный цикл

устранён рассинхрон между config и runtime

корректная работа после рестарта

Исправление бага закрытия позиций (hedge mode)

Проблемы:

Использовался open_market_position вместо close_position

Некорректный positionSide (открывалась противоположная позиция)

Использование reduceOnly вместе с positionSide (ошибка Binance)

Исправления:

execute(): open_market_position → close_position

close_position():

удалён reduceOnly=True

корректная логика:

SELL → positionSide=LONG

BUY → positionSide=SHORT

Результат:

позиции корректно закрываются

устранены ошибки Binance API

исключено открытие встречных позиций при закрытии

Удаление дублирующего источника target_profit (частично)

Убрана установка:
manager.profit_manager.target_profit = config.target_profit

Основная логика закрытия переведена на:
manager.cycle_target_profit

Примечание:

ProfitManager.target_profit временно оставлен (Этап B)

🧪 Проведённые тесты

Закрытие по target_profit
✔️ обе позиции (LONG + SHORT) закрываются
✔️ ошибки Binance отсутствуют

Финансовый расчёт
✔️ PnL, комиссии и итоговая прибыль считаются корректно

Reset цикла
✔️ cycle_target_profit сбрасывается
✔️ новый цикл стартует корректно

Новый цикл после закрытия
✔️ применяет актуальный config.target_profit

Рестарт (частично)
✔️ позиции отсутствуют
✔️ новый цикл запускается корректно

⚠️ Известные моменты

ProfitManager.target_profit ещё не удалён (будет в Этапе B)

Возможен edge-case с quantity = 0 при закрытии (пока не критично)

📌 Следующие шаги

Этап B:

Удалить ProfitManager.target_profit

Передавать target_profit извне (из PositionManager)

Убрать дублирующую логику закрытия (pm.should_close)

Оставить единый источник истины

После:

Финальный тест

Проверка manual close

Проверка restart recovery (multipliers)

🧠 Итог

Устранён критический баг закрытия позиций

Архитектура target_profit приведена к per-cycle модели

Повышена стабильность и предсказуемость системы

Версия v0.7.3 — стабильная контрольная точка

# 📅 DEVLOG — 19.03.2026

## 🚀 Общий статус

День был посвящён проверке стабильности backend перед переходом к финальным правкам и фронту.

---

## ✅ Что реализовано и подтверждено

### 1. Target Profit — runtime изменение

* Реализовано изменение target_profit во время работы бота
* Изменение применяется **мгновенно без рестарта**
* Проверено:

  * изменение в активном цикле
  * изменение для следующих циклов

✔ Работает корректно

---

### 2. Per-symbol архитектура (ProfitManager)

Проверено через:

* анализ кода (через Claude)
* практический тест на 2 монетах (ANIMEUSDT / SENTUSDT)

Результат:

* у каждого symbol свой:

  * PositionManager
  * ProfitManager

✔ Полная изоляция состояний
✔ Нет shared state

---

### 3. Поведение при работе нескольких монет

Проверено:

* изменение target_profit у одной монеты
* вторая монета не затрагивается

✔ Работает корректно

---

### 4. Recovery после рестарта (частично)

Проверено:

* позиции восстанавливаются
* цикл продолжается
* лишние ордера не создаются

✔ Логика восстановления позиций — корректная

---

## ❗ Найденные проблемы

---

### 🔴 1. Потеря комиссий после рестарта

Симптом:

* ENTRY FEES = 0 после перезапуска
* EXIT FEES остаются
* PNL считается некорректно

Причина:

* ProfitManager не сохраняет state:

  * entry_fees
  * funding_total
  * cycle_number

Вывод:
❌ Recovery реализован не полностью (только позиции, без финансового состояния)

---

### 🟠 2. target_profit не сохраняется после рестарта

Симптом:

* после изменения значения через UI
* после рестарта возвращается значение из config.py

Причина:

* изменения живут только в runtime (памяти)
* отсутствует persistence слоя

---

## 🧠 Архитектурные выводы

---

### 1. Backend почти готов

```text
~95% готовности
```

Готово:

* мультисимвольность
* конфиги
* логика циклов
* исполнение ордеров
* runtime управление

---

### 2. Остались 2 системных слоя

```text
1. Persistence state (ProfitManager)
2. Persistence config (target_profit)
```

---

### 3. config.py больше не должен быть источником правды

Роль:

* дефолтные значения

Реальные данные:

* должны храниться отдельно (JSON / DB)

---

## 📋 План (зафиксирован)

---

### 🔴 БЛОК 1 — комиссии (в работе)

* сохранить state ProfitManager
* восстановить после рестарта

---

### 🟠 БЛОК 2 — target_profit persistence

* сохранить изменения
* загрузить при старте

---

### 🟡 БЛОК 3 — управление символами

* переход на БД как источник правды

---

### 🟢 БЛОК 4 — подготовка к frontend

---

## 🎯 Следующий шаг

```text
Начать с БЛОКА 1 — ProfitManager state
(таблица + save/load)
```

---

## 💬 Итог дня

* Архитектура подтверждена как корректная
* Основные механики работают стабильно
* Найдены 2 критичных узких места
* Зафиксирован финальный план завершения backend

Статус:
👉 Переход к финальным правкам перед фронтом


🐞 BUG: некорректный расчет после manual close (после рестарта)

Сценарий:

Бот запущен → цикл активен
Бот остановлен (позиции остаются)
Бот запущен → корректно восстанавливает цикл и комиссии ✅
Бот снова остановлен
Одна позиция закрывается вручную на бирже
Бот запускается → корректно видит, что осталась 1 сторона ✅
Закрывается последняя позиция вручную
👉 В этот момент:
❗ Проблема
POSITION DEBUG перед закрытием → корректный ✅
REALIZED PNL / TOTAL COMMISSION / CYCLE PROFIT → ❌ некорректный

👉 ошибка возникает в момент финального расчета цикла