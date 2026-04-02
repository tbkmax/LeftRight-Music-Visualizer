from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QSpinBox, QDoubleSpinBox, 
    QLineEdit, QLabel, QScrollArea, QWidget, QPushButton
)
from PyQt6.QtCore import Qt

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
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        form_layout = QFormLayout(scroll_content)
        
        self.widgets = {}
        
        # Manually iterate to create appropriate inputs and connect their signals 
        for field_name, field_info in self.settings.model_fields.items():
            current_value = getattr(self.settings, field_name)
            
            if isinstance(current_value, bool):
                # Pass bools for now as there are none
                pass
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

    def _make_updater(self, field_name):
        def updater(value):
            setattr(self.settings, field_name, value)
            self.settings_manager.save()
        return updater
