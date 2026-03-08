# Music Visualizer Project Plan

An "Always on Top" bar-shaped music visualizer for Windows.

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
