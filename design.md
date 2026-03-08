# Design Document - Top Music Visualizer

## Overview
The Top Music Visualizer is a lightweight desktop utility for Windows that provides real-time audio visualization using system loopback audio.

## Architecture

```mermaid
graph TD
    A[Audio Stream (WASAPI)] --> B[Audio Engine]
    B -->|FFT Data| C[Visualization Manager]
    D[Winsdk API] -->|Track Metadata| E[Media Info Provider]
    E --> C
    F[Settings Manager] --> C
    C -->|Update GUI| G[Left Side Window]
    C -->|Update GUI| H[Right Side Window]
```

### 1. Audio Engine
- **Input**: WASAPI Loopback (Stereo Mix).
- **Processing**:
  - Buffer management (sliding window).
  - FFT transformation to convert time-domain audio to frequency-domain.
  - Binning logic to map thousands of frequency bins into a user-defined number of bars.
- **Signal**: Emits normalized frequency data to the UI thread.

### 2. Visualization UI (PyQt6)
- **Window Attributes**:
  - `Qt.WindowStaysOnTopHint`: Always visible.
  - `Qt.FramelessWindowHint`: Removes borders/title bars.
  - `Qt.WindowTransparentForInput`: Allows mouse events to pass through (optional, toggled by settings).
- **Graphics Pipeline**:
  - `QPainter` for high-performance 2D rendering.
  - **Circular Transparency**: A `QRadialGradient` or custom `setMask` implementation to create the proximity transparency effect.

### 3. Settings System
- **Schema**:
  - `bar_count`: (Integer) Number of bars per side.
  - `colors`: (List of Hex) Bar colors (default white).
  - `transparency_radius`: (Float) Radius in pixels where transparency is applied.
  - `max_transparency`: (Float 0-1) Maximum transparency value at the center of the mouse proximity.
  - `refresh_rate`: (Integer) Target FPS.

## Interaction Design
- **Mouse Proximity**: The visualizer will track the system-wide mouse position (global cursor). When the distance between the cursor and a bar is less than `transparency_radius`, the bar's opacity is adjusted dynamically based on its distance from the mouse.
