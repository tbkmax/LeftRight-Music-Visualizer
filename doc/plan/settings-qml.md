# Settings window: PyQt6 + QML implementation plan

## Goal and scope

Replace the current settings dialog with a QML settings window while keeping Python responsible for settings, device discovery, restart, and the live energy value. This stage covers the settings experience and its integration with the existing application. The window should be useful as a small QML trial before any decision about the visualizer overlay.

## Current baseline

- `src/left_right_music_visualizer/main.py` creates the settings dialog lazily from the tray menu and connects `AudioEngine.audio_data_updated` to its live energy display.
- `src/left_right_music_visualizer/settings_gui.py` builds controls from the 16 fields in `VisualizerSettings`, enumerates WASAPI loopback devices, saves changes, resets values, and restarts the app.
- `src/left_right_music_visualizer/settings.py` owns the Pydantic model and persists `settings.json` in the current working directory. The overlay and audio engine share that same settings object.
- The existing dialog says visual changes apply immediately. Screen choice, bar count, and audio device require restart; window geometry also depends on bar width, spacing, and maximum width at startup.

## Stage 1 — Prove the QML window integration

1. Add a minimal QML window under `src/left_right_music_visualizer/qml/` and load it from the existing `QApplication` when the tray's Settings action is used. Keep a Python reference to the QML engine/window so repeated tray clicks reopen the same instance.
2. Confirm the window can receive focus, raise above the overlays, close without quitting the tray app, and reopen. Check normal and high-DPI displays.
3. Choose one packaged-resource path for QML files that works in an editable install and the PyInstaller build; update `pyproject.toml` and `scripts/build.ps1` as needed.

**Exit check:** A packaged and development build can open and reopen a QML settings window from the tray without a second application event loop.

## Stage 2 — Move settings behavior behind a Python bridge

1. Create a `QObject` settings controller with explicit properties, signals, and slots for reading fields, applying a value, listing audio devices, resetting defaults, restarting, reporting save/validation errors, and publishing live energy. QML should contain presentation and input behavior; Python should own device and process operations.
2. Keep `SettingsManager` as the persistence owner and keep the shared `VisualizerSettings` instance stable so existing overlay/audio consumers see valid live updates. Validate values before applying them. Save committed text values on edit completion and numeric/toggle choices as they change.
3. Give QML typed metadata for every current field: label, description, value, control kind, limits/options, and whether a restart is pending. Use explicit choices for `frequency_scale`, `target_screen`, and loopback devices. Preserve an unavailable saved audio-device value visibly instead of silently switching it to the default.
4. Audit when each field is read. Mark startup-dependent settings clearly; at minimum inspect `bar_count`, `bar_width`, `bar_spacing`, `max_width`, `target_screen`, and `audio_device_index`. Compare current values with startup values to show a restart-needed state.
5. Preserve the live energy formula (45% SPS, 40% onsets, 15% loudness). Send only a throttled display value to QML while the window is visible; the settings display does not need every audio frame.
6. Implement reset as one controller action that covers all 16 fields, including booleans, then emits the new values and restart state. Keep the current development (`python -m left_right_music_visualizer`) and frozen-executable restart paths working.

**Exit check:** All existing settings can be edited, persisted, reset, and reloaded; invalid input is rejected visibly; the energy readout and restart action work.

## Stage 3 — Redesign the settings UI using `doc/DESIGN.md`

Translate the applicable tokens from `doc/DESIGN.md` into a compact desktop control panel. Its ClickHouse marketing examples inform visual style, not the settings window's copy or information architecture.

1. Define QML theme tokens rather than scattering literal colors and dimensions: canvas `#0a0a0a`, cards `#1a1a1a`, elevated surfaces `#242424`, hairlines `#2a2a2a`, primary yellow `#faff69`, white primary text, and muted secondary text. Keep the user's `bar_color` setting independent of the settings UI accent.
2. Use Inter where available, with a clear Windows fallback. Apply the document's compact 4/8/12/16/24/32 px spacing rhythm, 8 px input/button corners, 12 px card corners, dark inputs, and yellow focus/primary-action treatment. Avoid marketing-scale headlines and oversized 96 px section spacing in this utility window.
3. Replace the long generated form with task-oriented groups: **Appearance**, **Bars & layout**, **Audio & frequency**, and **Display & performance**. Keep field descriptions close to controls; use suitable sliders, numeric inputs, toggles, color selection, and option lists rather than generic text boxes.
4. Put live energy and audio-device status in a restrained status area. Show a persistent, specific restart notice only when startup-dependent values differ. Make Reset secondary and Restart the primary yellow action when needed.
5. Design for keyboard focus, readable labels and value units, narrow windows, scrolling, and high-DPI scaling. Check empty device lists, invalid values, save failures, and long device names as part of the visual pass.

**Exit check:** A visual review against `doc/DESIGN.md` confirms consistent tokens and hierarchy, and a settings user can find each control and understand which changes need restart.

## Stage 4 — Verify and cut over

1. Test the controller's validation, persistence, reset, and restart-pending logic. Run the repository's existing unit suite.
2. On Windows, exercise the tray flow, all settings groups, live energy, device selection, reset, restart, and relaunch persistence. Repeat with settings closed/open and on a secondary or scaled display.
3. Build the executable and verify its bundled QML and font assets load without relying on the repository directory.
4. Compare CPU and memory with the settings window closed and open against the current build. Investigate a material regression before removing the old dialog path.
5. Switch the tray action to the QML window, remove unused widget-dialog code, and update the README with the new UI/build requirements.

**Completion criteria:** The QML settings window provides full behavior parity, follows the adapted design system, works in development and packaged builds, and leaves the overlay/audio signal path functional.
