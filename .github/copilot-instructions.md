# Adaptive Lighting AI Instructions

This repository hosts the **Adaptive Lighting** custom component for Home Assistant. It adjusts the brightness and color of lights based on the sun's position.

## 🏗 Architecture & Core Concepts

- **Component Structure**: The integration logic resides in `custom_components/adaptive_lighting/`.
  - `__init__.py`: Sets up the integration and `switch` platform.
  - `switch.py`: Contains `AdaptiveSwitch`, the main control entity. It manages the adaptation loop and state.
  - `color_and_brightness.py`: `SunLightSettings` class calculates target brightness/color based on solar position.
  - `adaptation_utils.py`: Helpers for preparing service calls (`light.turn_on`) and handling attributes.
  - `config_flow.py`: Handles UI configuration via `ConfigFlow`.

- **Key Mechanisms**:
  - **Interception**: The component intercepts `light.turn_on` calls to apply adaptive settings immediately.
  - **Periodic Adaptation**: `AdaptiveSwitch` runs a loop (default 90s) to update lights.
  - **Manual Control Detection**: Monitors light state changes. If a light changes state without Adaptive Lighting's intervention, it's marked as "manually controlled" and adaptation pauses for that light.
  - **Sleep Mode**: A specific mode with lower brightness and warmer color, toggled via a separate switch.

## 🛠 Development Workflow

- **Environment Setup**:
  - The workspace includes a `core/` directory (Home Assistant Core) to provide context and dependencies.
  - `scripts/develop`: Sets up `PYTHONPATH` and runs a local Home Assistant instance with the component loaded.
  - `scripts/lint`: Runs `pre-commit` hooks (Black, Isort, Flake8).

- **Testing**:
  - Tests are in `tests/`.
  - Run tests using `pytest`.
  - **Important**: Ensure `PYTHONPATH` includes `custom_components` and `core` (if running locally without installed HA).
  - Example: `PYTHONPATH=.:core pytest tests/` (adjust paths as needed based on env).
  - `test_dependencies.py` helps identify required test dependencies from HA Core.

## 🧩 Coding Conventions & Patterns

- **Async First**: Use `async`/`await` for all I/O and HA interactions.
- **Type Hinting**: Strictly use Python type hints.
- **Configuration**:
  - Use `voluptuous` for data validation (see `CONFIG_SCHEMA` in `__init__.py`).
  - Configuration is available via both YAML and UI (Config Flow).
- **Logging**: Use `_LOGGER` for debug info.
- **State Management**:
  - Use `async_track_state_change_event` to listen for light changes.
  - Use `async_track_time_interval` for the periodic update loop.

## 🔍 Common Tasks

- **Adding a new option**:
  1. Add constant in `const.py`.
  2. Update `VALIDATION_TUPLES` in `const.py`.
  3. Update `OptionsFlowHandler` in `config_flow.py`.
  4. Update `AdaptiveSwitch` in `switch.py` to use the new option.
  5. Update `strings.json` for UI labels.

- **Debugging Adaptation Logic**:
  - Check `color_and_brightness.py` for math related to sun position.
  - Inspect `adaptation_utils.py` for how attributes are filtered/prepared for service calls.

## 📦 Dependencies

- **Home Assistant Core**: Relies heavily on HA helpers (`homeassistant.helpers`, `homeassistant.util`).
- **External**: `ulid-transform`.
