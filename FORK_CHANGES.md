# Описание изменений форка (plyusnin/adaptive-lighting)

Этот документ описывает изменения форка относительно оригинального репозитория
[basnijholt/adaptive-lighting](https://github.com/basnijholt/adaptive-lighting).
Он нужен, чтобы при подтягивании обновлений из upstream было понятно, какие наши
правки сохранять и где возможны конфликты.

## Текущее состояние

- **Ветка форка:** `warm-on-low`
- **Remotes:**
  - `origin` → https://github.com/plyusnin/adaptive-lighting
  - `upstream` → https://github.com/basnijholt/adaptive-lighting
- Ветка **смержена с `upstream/main`** (merge-коммит «Merge upstream/main: adopt
  enum-based individual manual control (#1356)»).

После мержа форк отличается от upstream **двумя функциональными фичами**
(`warm-on-low` и разгорание из нуля в `adaptive_lighting.apply`), одним багфиксом
(`adaptive_lighting.apply` и transition) плюс несколькими вспомогательными
файлами. Команда для актуального списка отличий:

```powershell
git diff upstream/main HEAD -- custom_components/adaptive_lighting/switch.py
```

## Единственная уникальная фича: warm-on-low

Цветовая температура делается **теплее при низкой яркости** (имитация диммирования
ламп накаливания). В upstream этого нет. Весь код — в
[`switch.py`](custom_components/adaptive_lighting/switch.py), ~190 строк, точечно.

Что добавлено:

1. **Параметр `brightness_override: int | None`** в `prepare_adaptation_data` —
   абсолютная яркость (0-255), к которой реально придёт лампа.
2. **Интерполяция цветовой температуры** в блоке расчёта `color_temp`:
   `ct = 2000 + (target - 2000) * (brightness_pct / 100)`.
   То есть 0% яркости → 2000K, 100% → штатная адаптивная цель.
   Порог 2000K **намеренно захардкожен** (не `min_color_temp`) — это важно для
   корректной работы плагина.
3. **Приоритет источника яркости** для расчёта цвета:
   `brightness_override` → адаптивная цель (`brightness_pct` из настроек) → текущая
   яркость лампы (`state.state == STATE_ON`).
4. **Уважение `brightness_override`:** при заданном override адаптивная яркость не
   выставляется (`brightness_override is None` в условии), чтобы не перезаписать
   запрошенную пользователем яркость; цвет подбирается под неё.
5. **Извлечение `brightness_override` в перехватчике `turn_on`**
   (`_service_interceptor_turn_on_single_light_handler`): из
   `ATTR_BRIGHTNESS` / `ATTR_BRIGHTNESS_PCT` / `ATTR_BRIGHTNESS_STEP` /
   `ATTR_BRIGHTNESS_STEP_PCT` (последние два — относительно текущего состояния).
6. **Импорты:** `ATTR_BRIGHTNESS_PCT/STEP/STEP_PCT` из `homeassistant.components.light`
   и `BRIGHTNESS_ATTRS` из `.adaptation_utils`.
7. **Немедленная реакция на ручное диммирование** — новый метод
   `_respond_to_on_to_on_event` + ветка `elif old_on and new_on:` в
   `state_changed_event_listener`. Это **единственный** сигнал, который HA получает,
   когда лампой управляют напрямую на уровне устройства (например, **диммер,
   привязанный к лампе через Zigbee Binding**): такие изменения не проходят через
   `light.turn_on` и не перехватываются. При внешнем изменении яркости она помечается
   manual (`LightControlAttributes.BRIGHTNESS`), и, если цвет ещё адаптируется, цвет
   немедленно переадаптируется под новую яркость (`force=True, transition=0`).
   Изменение яркости считается относительно **baseline** (последняя яркость, которую
   выставил сам AL, из `last_service_data`) — чтобы плавное диммирование мелкими
   шагами накапливалось и пересекало порог. Одновременное изменение цвета при
   изменении яркости трактуется как побочный эффект диммирования (не ручной
   контроль цвета), иначе цвет «замораживался» бы. Защиты: `is_our_context`,
   grace-period 5с после включения, распознавание отложенного репорта нашей
   адаптации (сравнение с `last_service_data`). **Требует** `take_over_control`
   (событийный обработчик; `detect_non_ha_changes` НЕ требуется — он про
   опрос-детекцию).

Как работает с ручным контролем upstream: когда яркость под ручным контролем, а цвет
адаптируется (`LightControlAttributes.COLOR`), на следующем цикле адаптации
`prepare_adaptation_data` берёт текущую яркость лампы и подбирает под неё тёплый цвет.
Метод из п.7 делает это **мгновенно**, не дожидаясь цикла.

## Багфикс: `adaptive_lighting.apply` и transition

`handle_apply` при `turn_on_lights: true` включает погашенную лампу напрямую через
`_adapt_light`, но (в upstream) не регистрирует эту адаптацию как **проактивную**.
Из-за этого возникающее событие `off` → `on` считается внешним `light.turn_on`:
выполняется `reset()` (отменяющий текущую адаптацию) и вторая адаптация с
`initial_transition`, которая перетирает transition из вызова сервиса.

Исправление в `handle_apply` (симметрично перехватчику `light.turn_on`):

1. Сначала собираются все пары «switch → лампа» и запоминаются лампы, которые
   **на момент вызова были выключены** (`is_on` проверяется один раз, до адаптаций).
2. Для каждой такой лампы **один раз** вызываются `clear_proactively_adapting` и
   `reset(reset_manual_control=False)` — **до** любых новых регистраций, иначе
   второй switch, владеющий той же лампой, стёр бы контекст, только что
   зарегистрированный первым.
3. Затем для каждой пары создаётся контекст `"service"`, и если лампа была
   выключена — он регистрируется через `set_proactively_adapting` перед вызовом
   `_adapt_light`.

Набор выполняемой работы не меняется: условие `turn_on_lights or is_on` просто
вычисляется один раз заранее (в фазе 1 нет `await`, поэтому снимок консистентен).
Поведение для `turn_on_lights: false`, уже включённых ламп и групп прежнее.

**Что меняется намеренно.** `_proactively_adapting_contexts` живёт в общем
(одном на `hass`) менеджере, а проверка проактивности стоит в *глобальном*
обработчике `state_changed_event_listener` до цикла по switch'ам. Поэтому
зарегистрированный контекст подавляет обработку события `off` → `on` **для всех**
switch'ей, владеющих лампой, — в том числе для тех, которые в вызов сервиса не
передавались. Раньше такой «непричастный» switch тоже адаптировал лампу с
`initial_transition`. Теперь лампу адаптируют только switch'и из вызова.

Это ровно та же семантика, что и у перехваченного `light.turn_on`
(`_service_interceptor_turn_on_single_light_handler`): там контекст регистрируется
так же и событие `off` → `on` так же подавляется для всех владельцев. То есть
изменение восстанавливает симметрию двух путей включения, а не вводит новое
правило. Побочный эффект: для ламп, включённых через `apply`, пропускается и
защита `just_turned_off` от быстрой последовательности `off` → `on` → `off` —
в пути перехвата она пропускается точно так же.

Тесты: `test_apply_turn_on_keeps_requested_transition` (включая пропуск лампы при
`turn_on_lights: false`), `test_apply_two_switches_sharing_an_off_light` (третий
switch-владелец, не переданный в вызов, лампу не адаптирует).

**Известное ограничение (осознанное).** Если `_adapt_light` выйдет, не включив
лампу (занят `turn_off_lock` или `prepare_adaptation_data` вернул `None`),
зарегистрированный контекст останется в `_proactively_adapting_contexts`. Это
безвредно: id контекстов уникальны, поэтому «повиснувшая» запись никогда не
совпадёт с чужим событием, а число таких записей на лампу ограничено числом
switch'ей — каждый следующий вызов (и перехваченный `light.turn_on`) начинается
с `clear_proactively_adapting`. Чистить запись по факту «лампа всё ещё выключена»
нельзя: адаптация асинхронная, и это вернуло бы исходную гонку. В пути перехвата
ровно то же поведение.

## Фича: `adaptive_lighting.apply` разгорается из нуля

**Проблема.** `adaptive_lighting.apply(turn_on_lights: true, transition: 8)` для
погашенной лампы отправляет один `light.turn_on` с целевой яркостью и transition.
На уровне интеграции у выключенной лампы яркость 0, но реальная лампа включается
**со своей запомненной яркости** (`CurrentLevel` в Zigbee). Например, IKEA
KAJPLATS вспыхивает на прежнем уровне и уже оттуда «доезжает» до цели — плавного
разгорания из нуля нет. Живая проверка на KAJPLATS: плавный разгор получается,
только если сначала включить лампу на яркости 1 с `transition: 0`, а следом
отправить адаптивную цель с нужным transition.

**Решение** (без новых параметров сервиса — это просто корректная реализация
«разгорания», а не опция): в `handle_apply`, перед основным циклом адаптаций,
каждая лампа из `off_lights` включается на `FADE_IN_BRIGHTNESS = 1` с
`transition: 0` — функция `_async_fade_in_from_zero` в
[`switch.py`](custom_components/adaptive_lighting/switch.py).

Разгорание выполняется **только** когда оно имеет смысл:

- `turn_on_lights: true` — иначе `off_lights` пуст и лампа вообще не трогается;
- `transition > 0` — без transition разгорать нечего, включение на 1 дало бы
  только лишнюю вспышку;
- `adapt_brightness: true` — иначе адаптация не выставит яркость и лампа так и
  осталась бы на яркости 1;
- лампа поддерживает и `brightness`, и `transition` (проверка по
  `_supported_features`, то же условие, по которому `prepare_adaptation_data`
  кладёт `ATTR_BRIGHTNESS` и `ATTR_TRANSITION` в service data);
- лампа была выключена на момент вызова — уже включённые лампы не трогаются и
  **не замедляются**: для них не выполняется ни лишнего вызова, ни ожидания.

**Разгорание — свойство лампы, а не switch'а**, поэтому выполняется один раз на
лампу, даже если её делят несколько switch'ей (цикл идёт по `off_lights`, а не по
`work_items`).

**Детерминированная последовательность.** После `light.turn_on` функция ждёт не
фиксированное время, а **фактическое состояние лампы**: подписка через
`async_track_state_change_event` ставится до вызова, и ожидание завершается, как
только лампа отчиталась `on`. У ламп, которые пишут состояние синхронно внутри
вызова сервиса, ожидания не происходит вовсе (`is_on` проверяется первым).
`FADE_IN_STATE_TIMEOUT = 5` — не задержка, а верхняя граница: она нужна только
чтобы лампа, которая никогда не отчитается, не подвесила вызов сервиса навсегда.

Это же ожидание гарантирует, что к моменту адаптации менеджер уже обработал
событие `off` → `on` разгорания, то есть адаптация — это заведомо последующее
изменение `on` → `on`, а не гонка с включением.

**Почему разгорание не считается «ручным управлением».** Контекст разгорания
создаётся менеджером (`create_context("fade_in")`) и регистрируется через
`set_proactively_adapting` **до** вызова сервиса. Дальше срабатывают ровно те же
защиты, что и у перехваченного `light.turn_on`:

- `state_changed_event_listener`, ветка `off` → `on`: `is_proactively_adapting`
  → выход, второй адаптации с `initial_transition` не будет;
- `turn_on_off_event_listener` → `update_manually_controlled_from_event`: выход
  и по `is_proactively_adapting`, и по `is_our_context` (двойная защита — вторая
  работает даже если контекст был снят из-за ошибки);
- `_respond_to_on_to_on_event`: выход по `is_our_context`, а самоотчёты лампы под
  чужим контекстом отсекаются окном в 5 с после `off_to_on_event`, которое
  проставляется как раз событием разгорания.

`last_service_data` для разгорания намеренно **не** пишется: непосредственно
перед этим `reset(reset_manual_control=False)` его очищает, а следом адаптация
записывает реальную цель. Промежуток закрыт окном `off_to_on_event`.

**Ошибки локализованы по лампам.** Если `light.turn_on` разгорания упал или лампа
не отчиталась за `FADE_IN_STATE_TIMEOUT`, контекст снимается
(`clear_proactively_adapting`), пишется предупреждение, и лампа адаптируется
обычным образом (просто без разгорания). Остальные лампы вызова не затрагиваются.

Тесты: `test_apply_fades_in_off_light_from_zero` (две команды — `(1, transition 0)`,
затем адаптивная цель с transition вызова; отсутствие третьей команды с
`initial_transition`; уже включённая лампа не разгорается),
`test_apply_fade_in_is_sequenced_and_stays_adaptive` (лампа, отчитывающаяся о
состоянии только после возврата из вызова сервиса: адаптация уходит уже после
`on`; при этом ни события `manual_control`, ни пометок ручного управления —
проверяется с включёнными `intercept` и `take_over_control`),
`test_apply_does_not_fade_in_when_there_is_nothing_to_fade` (`transition: 0` и
`adapt_brightness: false`). Существующие `test_apply_turn_on_keeps_requested_transition`
и `test_apply_two_switches_sharing_an_off_light` обновлены на новую
последовательность команд.

## Вспомогательные файлы (не код компонента)

- **`.github/copilot-instructions.md`** — инструкции для AI-ассистентов.
- **`adaptive-lighting.code-workspace`** — VS Code workspace.
- **`FORK_CHANGES.md`** — этот файл.

## История: что было до мержа (контекст)

Изначально форк содержал **собственную реализацию раздельного ручного контроля
яркости и цвета** (на `dict[str, dict[str, bool]]`). Позже выяснилось, что upstream
реализовал ту же фичу основательнее — через enum-битмаску **`LightControlAttributes`**,
с сервисом `adaptive_lighting.set_manual_control`, тестами и документацией (PR #1356).

При мерже принято решение: **взять реализацию upstream как канон** (`switch.py` целиком
из upstream), а нашу dict-версию отбросить. Поверх осталась только уникальная
`warm-on-low`. Это убирает постоянные конфликты по одной и той же фиче в будущих мержах.

## Памятка по подтягиванию изменений из upstream

```powershell
git fetch upstream
git merge upstream/main
```

Конфликты возможны **только в `switch.py`**, в местах врезки warm-on-low:

1. **`prepare_adaptation_data`** — сигнатура (доп. параметр `brightness_override`) и
   блок расчёта `color_temp_kelvin` (интерполяция перед `clamp`).
2. **Условие установки яркости** — `... and brightness_override is None`.
3. **`_service_interceptor_turn_on_single_light_handler`** — извлечение
   `brightness_override` и передача его в `prepare_adaptation_data`.
4. **Импорты** — `ATTR_BRIGHTNESS_*`, `BRIGHTNESS_ATTRS`.
5. **`state_changed_event_listener`** — ветка `elif old_on and new_on:` и новый
   метод `_respond_to_on_to_on_event` (немедленная реакция на ручное диммирование).
   Зависит от upstream-API: `add_manual_control_attributes`,
   `get_manual_control_attributes`, `fire_manual_control_event`,
   `LightControlAttributes`, `_adapt_light(adapt_brightness=, adapt_color=)`.
6. **`handle_apply`** — двухфазная схема (сбор работы + снимок выключенных ламп,
   затем `clear_proactively_adapting`/`reset` и регистрация проактивных контекстов).
   Зависит от upstream-API: `set_proactively_adapting`, `clear_proactively_adapting`.

Если upstream сильно переработает `prepare_adaptation_data`, перехватчик или
`state_changed_event_listener` — перенести эти врезки заново (они изолированы;
п.5 — единственная, что завязана на upstream-структуру manual_control).

> ⚠️ Каталог `core/` — отдельный checkout Home Assistant Core (в `.gitignore` upstream),
> к форку отношения не имеет.

## Полезные команды

```powershell
# актуальный diff форка по switch.py
git diff upstream/main HEAD -- custom_components/adaptive_lighting/switch.py

# все файлы, отличающиеся от upstream
git diff --name-only upstream/main HEAD
```
