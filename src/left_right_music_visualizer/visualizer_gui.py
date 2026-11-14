import sys
from PyQt6.QtWidgets import QWidget, QMainWindow
from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import QPainter, QColor

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    HWND_TOPMOST = wintypes.HWND(-1)
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040
    SWP_NOOWNERZORDER = 0x0200

    _user32 = ctypes.windll.user32
    _user32.SetWindowPos.argtypes = (
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    )
    _user32.SetWindowPos.restype = wintypes.BOOL
else:
    _user32 = None

class VisualizerWidget(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.bars = [0.0] * self.settings.bar_count
        self.smoothed_loudness = 0.0
        self.smoothed_sps = 0.0
        self.smoothed_onsets = 0.0
        # This widget is transparent to mouse events, but the parent window will handle global cursor proximity
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_bars(self, target_bars, loudness=0.0, sps=0.0, onsets=0.0):
        if len(self.bars) != len(target_bars):
            self.bars = list(target_bars)
            self.smoothed_loudness = loudness
            self.smoothed_sps = sps
            self.smoothed_onsets = onsets
        else:
            alpha = self.settings.smoothing_factor
            # Clamp alpha between 0 and 0.99 to prevent freezing
            alpha = max(0.0, min(0.99, alpha))
            
            # Exponential moving average filter for bars
            for i in range(len(self.bars)):
                self.bars[i] = (alpha * self.bars[i]) + ((1.0 - alpha) * target_bars[i])
            
            # MIR smoothing
            mir_alpha = 0.95
            self.smoothed_sps = (mir_alpha * self.smoothed_sps) + ((1.0 - mir_alpha) * sps)
            self.smoothed_onsets = (mir_alpha * self.smoothed_onsets) + ((1.0 - mir_alpha) * onsets)
            
            # Loudness needs to be faster to show detail (pulse)
            loudness_alpha = 0.6
            self.smoothed_loudness = (loudness_alpha * self.smoothed_loudness) + ((1.0 - loudness_alpha) * loudness)
                
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
            if getattr(self.settings, 'energy_color_modulation', True):
                reactivity = getattr(self.settings, 'color_reactivity', 1.0)
                
                # Normalization (SPS and Onsets are already 0.0-1.0 floats from AudioEngine)
                norm_sps = max(0.0, min(1.0, self.smoothed_sps))
                norm_onsets = max(0.0, min(1.0, self.smoothed_onsets))
                norm_loudness = max(0.0, min(1.0, self.smoothed_loudness * 3.5))
                
                # Calculate composite energy (45% SPS, 40% Onsets, 15% Loudness)
                composite_energy = (norm_sps * 0.45) + (norm_onsets * 0.40) + (norm_loudness * 0.15)
                
                # Base hue from user's bar_color
                h, base_s, base_l, a_ = color.getHslF()
                if h < 0:
                    h = 0.5 # Default to teal if achromatic
                
                # Use composite_energy to drive the visual state
                # Low energy -> High Value (0.8), Low Saturation (0.2) -> Closer to white
                # High energy -> Normal Value (0.5), High Saturation (0.8) -> Colorful
                base_dyn_s = 0.2 + (0.6 * composite_energy)
                base_dyn_l = 0.8 - (0.3 * composite_energy)
                
                # Fast Loudness adds an instantaneous "pulse" of detail
                # This ensures the visualizer still "pops" on big drum hits even if overall energy is low
                relative_pulse = max(0.0, norm_loudness - composite_energy)
                pulse_s = relative_pulse * 0.4
                pulse_l = relative_pulse * 0.15
                
                target_s = min(1.0, base_dyn_s + pulse_s)
                target_l = min(1.0, base_dyn_l + pulse_l)
                
                # Apply reactivity as an interpolation/extrapolation factor from the base color
                final_s = max(0.0, min(1.0, base_s + ((target_s - base_s) * reactivity)))
                final_l = max(0.0, min(1.0, base_l + ((target_l - base_l) * reactivity)))
                
                color.setHslF(h, final_s, final_l, alpha / 255.0)
            else:
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
            Qt.WindowType.WindowDoesNotAcceptFocus |
            Qt.WindowType.WindowTransparentForInput # Make it click-through so user can interact with apps behind
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        self.visualizer = VisualizerWidget(settings, self)
        self.setCentralWidget(self.visualizer)

        self._topmost_timer = QTimer(self)
        self._topmost_timer.setInterval(1000)
        self._topmost_timer.timeout.connect(self.ensure_topmost)
        self._topmost_timer.start()
         
    def update_bars(self, bars, loudness=0.0, sps=0.0, onsets=0.0):
        # We can implement smoothing here if we want (e.g., exponential moving average)
        self.visualizer.set_bars(bars, loudness, sps, onsets)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.ensure_topmost)
        QTimer.singleShot(250, self.ensure_topmost)

    def ensure_topmost(self):
        if _user32 is None or not self.isVisible():
            return

        hwnd = int(self.winId())
        if not hwnd:
            return

        flags = (
            SWP_NOMOVE |
            SWP_NOSIZE |
            SWP_NOACTIVATE |
            SWP_SHOWWINDOW |
            SWP_NOOWNERZORDER
        )
        _user32.SetWindowPos(wintypes.HWND(hwnd), HWND_TOPMOST, 0, 0, 0, 0, flags)
