import sys
from PyQt6.QtWidgets import QWidget, QMainWindow
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor

class VisualizerWidget(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.bars = [0.0] * self.settings.bar_count
        # This widget is transparent to mouse events, but the parent window will handle global cursor proximity
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_bars(self, target_bars):
        if len(self.bars) != len(target_bars):
            self.bars = list(target_bars)
        else:
            alpha = self.settings.smoothing_factor
            # Clamp alpha between 0 and 0.99 to prevent freezing
            alpha = max(0.0, min(0.99, alpha))
            
            # Exponential moving average filter
            for i in range(len(self.bars)):
                self.bars[i] = (alpha * self.bars[i]) + ((1.0 - alpha) * target_bars[i])
                
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Map global cursor to local coordinates for proximity check
        global_mouse_pos = self.cursor().pos()
        local_mouse_pos = self.mapFromGlobal(global_mouse_pos)
        
        bar_thickness = self.settings.bar_width
        bar_spacing = self.settings.bar_spacing
        # Double the total height because we are mirroring the bars
        total_height = (self.settings.bar_count * 2) * (bar_thickness + bar_spacing)
        
        # Center vertically
        start_y = (self.height() - total_height) // 2
        
        # Create a mirrored layout: High Freqs -> Low Freqs -> High Freqs
        mirrored_bars = self.bars[::-1] + self.bars

        for i, val in enumerate(mirrored_bars):
            w = max(2.0, val * self.settings.max_width) # Minimum width of 2px
            y = start_y + i * (bar_thickness + bar_spacing)
            
            # Do not render bars that are outside the visible window vertically
            if y < 0 or y + bar_thickness > self.height():
                continue
            
            # Left side grows from x=0 rightwards. Right side grows from right edge leftwards.
            if getattr(self.parent(), 'is_left', True):
                x = 0
            else:
                x = self.width() - w

            rect = QRectF(x, y, w, bar_thickness)

            # Check distance to mouse for transparency
            center_x = x + w / 2
            center_y = y + bar_thickness / 2
            dist = ((center_x - local_mouse_pos.x())**2 + (center_y - local_mouse_pos.y())**2)**0.5

            # Default alpha based on settings
            base_alpha = int(255 * self.settings.default_transparency)
            alpha = base_alpha
            
            if dist < self.settings.transparency_radius:
                t = 1.0 - (dist / self.settings.transparency_radius)
                # When mouse is over it, transition from base_alpha to max_transparency (which usually means more transparent, so a lower alpha value)
                target_hover_alpha = int(255 * (1.0 - self.settings.max_transparency))
                # Interpolate between the default base alpha and the hover alpha
                alpha = int(base_alpha - (t * (base_alpha - target_hover_alpha)))

            color = QColor(self.settings.bar_color)
            color.setAlpha(alpha)
            
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            
            # Calculate corner radius: 1.0 = 0 radius (square), 0.0 = max radius (fully rounded)
            max_radius = bar_thickness / 2.0
            radius = max_radius * (1.0 - getattr(self.settings, 'bar_roundness', 1.0))
            
            painter.drawRoundedRect(rect, radius, radius)
            
        painter.end()


class OverlayWindow(QMainWindow):
    def __init__(self, settings, is_left=True):
        super().__init__()
        self.settings = settings
        self.is_left = is_left
        
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput # Make it click-through so user can interact with apps behind
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.visualizer = VisualizerWidget(settings, self)
        self.setCentralWidget(self.visualizer)
         
    def update_bars(self, bars):
        # We can implement smoothing here if we want (e.g., exponential moving average)
        self.visualizer.set_bars(bars)
