import os
import subprocess
import sys

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QSpinBox, QDoubleSpinBox,
    QLineEdit, QLabel, QScrollArea, QWidget, QPushButton, QComboBox, QApplication
)
from PyQt6.QtCore import Qt

import pyaudiowpatch as pyaudio

class SettingsDialog(QDialog):
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.settings = settings_manager.settings
        
        self.setWindowTitle("Visualizer Settings")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(400)
        self.setMinimumHeight(600)
        
        layout = QVBoxLayout(self)
        
        info_label = QLabel("Visual settings apply instantly as you change them.\nStructural changes (e.g., Target Screen, Bar Count, Audio Device Index) require restarting the app.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        self.energy_label = QLabel("Live Energy (45/40/15): --")
        self.energy_label.setStyleSheet("font-weight: bold; color: #cc55cc; margin-bottom: 10px;")
        layout.addWidget(self.energy_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        form_layout = QFormLayout(scroll_content)
        
        self.widgets = {}
        
        # Manually iterate to create appropriate inputs and connect their signals 
        for field_name, field_info in self.settings.model_fields.items():
            current_value = getattr(self.settings, field_name)

            if field_name == "audio_device_index":
                widget = QComboBox()
                self._populate_audio_devices(widget)
                self._select_audio_device(widget, int(current_value))
                widget.currentIndexChanged.connect(
                    self._make_combo_updater(field_name, widget)
                )
            elif isinstance(current_value, bool):
                from PyQt6.QtWidgets import QCheckBox
                widget = QCheckBox()
                widget.setChecked(current_value)
                widget.toggled.connect(self._make_updater(field_name))
            elif isinstance(current_value, int):
                widget = QSpinBox()
                widget.setRange(-10, 10000)
                widget.setValue(current_value)
                widget.valueChanged.connect(self._make_updater(field_name))
            elif isinstance(current_value, float):
                widget = QDoubleSpinBox()
                widget.setRange(-1000.0, 10000.0)
                widget.setDecimals(2)
                widget.setSingleStep(0.05)
                widget.setValue(current_value)
                widget.valueChanged.connect(self._make_updater(field_name))
            else:
                widget = QLineEdit()
                widget.setText(str(current_value))
                widget.textChanged.connect(self._make_updater(field_name))
                
            tooltip = field_info.description or field_name
            widget.setToolTip(tooltip)
            
            # Create a nice label format
            label_name = field_name.replace('_', ' ').title()
            form_layout.addRow(label_name, widget)
            self.widgets[field_name] = widget
            
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        reset_btn = QPushButton("Reset to Default Settings")
        reset_btn.setStyleSheet("padding: 5px; color: #ff5555; font-weight: bold;")
        reset_btn.clicked.connect(self.reset_to_defaults)
        layout.addWidget(reset_btn)

        restart_btn = QPushButton("Restart App")
        restart_btn.setStyleSheet("padding: 5px; color: #55cc55; font-weight: bold;")
        restart_btn.clicked.connect(self.restart_app)
        layout.addWidget(restart_btn)

    def update_energy_display(self, bars, loudness, sps, onsets):
        norm_sps = max(0.0, min(1.0, sps))
        norm_onsets = max(0.0, min(1.0, onsets))
        norm_loudness = max(0.0, min(1.0, loudness * 3.5))
        composite_energy = (norm_sps * 0.45) + (norm_onsets * 0.40) + (norm_loudness * 0.15)
        self.energy_label.setText(f"Live Energy (45/40/15): {composite_energy * 100:.1f}%")

    def reset_to_defaults(self):
        from settings import VisualizerSettings
        default_settings = VisualizerSettings()
        for field_name in self.settings.model_fields.keys():
            default_val = getattr(default_settings, field_name)
            widget = self.widgets.get(field_name)
            if widget:
                # Modifying the widget automatically fires valueChanged which saves to disk
                if isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
                    widget.setValue(default_val)
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(default_val))
                elif isinstance(widget, QComboBox):
                    self._select_audio_device(widget, int(default_val))

    def restart_app(self):
        self.settings_manager.save()

        if getattr(sys, "frozen", False):
            cmd = [sys.executable]
        else:
            cmd = [sys.executable, os.path.abspath(sys.argv[0])]

        cmd.extend(sys.argv[1:])
        cwd = os.path.dirname(os.path.abspath(sys.argv[0]))

        try:
            subprocess.Popen(cmd, cwd=cwd)
        except Exception as exc:
            print(f"Failed to restart application: {exc}")
            return

        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _make_updater(self, field_name):
        def updater(value):
            setattr(self.settings, field_name, value)
            self.settings_manager.save()
        return updater

    def _make_combo_updater(self, field_name, combo_box):
        def updater(_index):
            data = combo_box.currentData()
            if data is None:
                return
            setattr(self.settings, field_name, int(data))
            self.settings_manager.save()
        return updater

    def _populate_audio_devices(self, combo_box):
        combo_box.clear()
        combo_box.addItem("Default system loopback (-1)", -1)

        try:
            p = pyaudio.PyAudio()
        except Exception:
            combo_box.addItem("(Could not load audio devices)", -1)
            return

        try:
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if not dev.get("isLoopbackDevice", False):
                    continue
                name = dev.get("name", "Unknown Device")
                channels = dev.get("maxInputChannels", 0)
                if channels == 0:
                    channels_text = "2 (Virtual)"
                else:
                    channels_text = str(int(channels))
                label = f"{i} | {channels_text} ch | {name}"
                combo_box.addItem(label, int(i))
        finally:
            p.terminate()

    def _select_audio_device(self, combo_box, device_index):
        for i in range(combo_box.count()):
            if combo_box.itemData(i) == device_index:
                combo_box.setCurrentIndex(i)
                return
        combo_box.setCurrentIndex(0)
