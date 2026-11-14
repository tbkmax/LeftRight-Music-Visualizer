# LeftRight Music Visualizer

An always-on-top, bar-shaped music visualizer for Windows. It captures system
audio through WASAPI loopback and displays bars at both edges of the screen.

## Install and run

From the project root in PowerShell, using Python 3.11 or newer:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m left_right_music_visualizer
```

The editable install also provides a `left-right-music-visualizer` command.
Settings are saved to `settings.json` in the current working directory. Run
from the project root to keep using an existing project-root settings file.

To run the unit tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

To build a standalone Windows executable, install the build extra and run the
PowerShell build script:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[build]'
.\scripts\build.ps1
```

The executable is written to `dist/`. The audio diagnostic scripts in
`scripts/` can be run directly with the virtual environment's Python.

## Project layout

```text
src/left_right_music_visualizer/  Application package and bundled tray icon
tests/                            Unit tests
scripts/                          Audio diagnostics and Windows build script
doc/                              Design notes and decisions
pyproject.toml                    Package metadata, dependencies, entry point
```

## Key Features
- **Always on Top**: Resides on top of all windows (ideal for desktop personalization).
- **Dual Visualization**: Left and right side bar displays dynamically reactive to system audio.
- **Audio Sensitivity**: Real-time response to high/low pitches and frequencies using WASAPI.
- **Proximity Transparency**: Circular transparency mask centered on the mouse cursor for non-intrusive UI.
- **Customizable Layout**: Configurable bar count and positioning via a persistent Settings system.

## Technical Stack
- **Audio Capture**: `PyAudio` (WASAPI Loopback mode).
- **GUI Framework**: `PyQt6` (Frameless, transparent windows).
- **Track Info**: `winsdk` (Windows Media Control integration).
- **Signal Processing**: `numpy` (FFT-based frequency analysis).

## Core Components
1. **AudioEngine**: Manages loopback audio capture and FFT calculations.
2. **VisualizerWindow**: PyQt6 implementation for rendering bars and handling transparency masks.
3. **MediaInfoProvider**: Monitors Windows Media Sessions for current track metadata.
4. **SettingsManager**: Handles JSON-based configuration for appearance and behavior.
