import json
import os
from pydantic import BaseModel, Field
from typing import List

SETTINGS_FILE = "settings.json"

class VisualizerSettings(BaseModel):
    bar_count: int = Field(default=25, description="Number of visualizer bars per side")
    bar_color: str = Field(default="#c7eaff", description="Hex color code for the bars")
    transparency_radius: float = Field(default=600.0, description="Radius in pixels for mouse proximity transparency, default is 150")
    max_transparency: float = Field(default=0.9, description="Maximum transparency level (0-1) at the center of the mouse")
    refresh_rate: int = Field(default=120, description="Target FPS for the visualizer")
    bar_width: int = Field(default=20, description="Thickness of each bar in pixels")
    bar_spacing: int = Field(default=8, description="Spacing between bars in pixels")
    max_width: int = Field(default=200, description="Maximum length of the bars in pixels")
    audio_device_index: int = Field(default=18, description="Index of the PyAudio device to use. Leave as -1 to use the default system loopback.")
    smoothing_factor: float = Field(default=0.4, description="Controls bar smoothness (0.0 to 0.99). Higher is smoother but slower.")
    default_transparency: float = Field(default=0.7, description="Default opacity of the bars when the mouse is away (0.0=invisible to 1.0=solid).")
    bar_roundness: float = Field(default=0.5, description="Roundness of the bars. 1.0 = Square, 0.0 = Fully rounded.")
    target_screen: str = Field(default="all", description="Target screen index to display on ('all', '0', '1', etc).")
    frequency_scale: str = Field(default="mel_a_weight", description="Frequency scaling method ('log' for standard, 'mel' for vocal spread, 'mel_a_weight' for A-weighted).")

class SettingsManager:
    def __init__(self, filename: str = SETTINGS_FILE):
        self.filename = filename
        self.settings = self.load()

    def load(self) -> VisualizerSettings:
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                return VisualizerSettings(**data)
            except Exception as e:
                print(f"Error loading settings: {e}. Using defaults.")
        return VisualizerSettings()

    def save(self):
        try:
            with open(self.filename, 'w') as f:
                f.write(self.settings.model_dump_json(indent=4))
        except Exception as e:
            print(f"Error saving settings: {e}")
