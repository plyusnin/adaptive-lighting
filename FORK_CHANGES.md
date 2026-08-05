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

После мержа форк отличается от upstream **только одной функциональной фичей**
(`warm-on-low`) плюс несколькими вспомогательными файлами. Команда для актуального
списка отличий:

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
