import sys
import signal
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QTimer

from settings import SettingsManager
from media_info import MediaInfoProvider
from audio_engine import AudioEngine
from visualizer_gui import OverlayWindow

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Setup System Tray Icon
    tray_icon = QSystemTrayIcon(QIcon("icon.ico"), app)
    tray_icon.setToolTip("Music Visualizer")
    tray_menu = QMenu()
    
    settings_dialog = None
    def show_settings():
        nonlocal settings_dialog
        if settings_dialog is None:
            from settings_gui import SettingsDialog
            settings_dialog = SettingsDialog(settings_manager)
        settings_dialog.show()
        settings_dialog.raise_()
        settings_dialog.activateWindow()

    settings_action = QAction("Settings", app)
    settings_action.triggered.connect(show_settings)
    tray_menu.addAction(settings_action)

    exit_action = QAction("Exit", app)
    exit_action.triggered.connect(app.quit)
    tray_menu.addAction(exit_action)
    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()
    
    # Ensure Ctrl+C closes the application gracefully
    signal.signal(signal.SIGINT, lambda sig, frame: app.quit())
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)
    
    # Load settings
    settings_manager = SettingsManager()
    settings = settings_manager.settings

    # Initialize Media Info
    media_provider = MediaInfoProvider()
    media_provider.start_monitoring()

    # Determine target screens
    target_screens = []
    all_screens = app.screens()
    
    if settings.target_screen.lower() == "all":
        target_screens = all_screens
    else:
        try:
            screen_index = int(settings.target_screen)
            if 0 <= screen_index < len(all_screens):
                target_screens.append(all_screens[screen_index])
            else:
                print(f"Screen index {screen_index} out of range. Falling back to primary screen.")
                target_screens.append(app.primaryScreen())
        except ValueError:
            print(f"Invalid target_screen '{settings.target_screen}'. Falling back to primary screen.")
            target_screens.append(app.primaryScreen())

    # Dimension logic for horizontal bars stacked vertically
    window_width = settings.max_width + 50
    # Multiply by 2 because we are going to mirror the bars top and bottom
    total_height = (settings.bar_count * 2) * (settings.bar_width + settings.bar_spacing)

    windows = []

        # Initialize Visualizer Windows for each target screen
    for i, screen in enumerate(target_screens):
        rect = screen.availableGeometry()
        
        left_window = OverlayWindow(settings, is_left=True)
        right_window = OverlayWindow(settings, is_left=False)

        left_window.setScreen(screen)
        right_window.setScreen(screen)

        window_height = min(total_height + 20, rect.height())
        y_offset = max(0, (rect.height() - window_height) // 2)

        left_x = rect.left()
        left_y = rect.top() + y_offset
        right_x = rect.right() - window_width
        right_y = rect.top() + y_offset
        
        # Show first to create the window handle
        left_window.show()
        right_window.show()

        # Force Qt to associate these windows with the specific screen's DPI and coordinate space
        if left_window.windowHandle():
            left_window.windowHandle().setScreen(screen)
        if right_window.windowHandle():
            right_window.windowHandle().setScreen(screen)

        # Apply geometry AFTER the screen is definitively set and handles exist
        left_window.setGeometry(left_x, left_y, window_width, window_height)
        right_window.setGeometry(right_x, right_y, window_width, window_height)

        windows.extend([left_window, right_window])

    # Initialize Audio Engine
    audio_engine = AudioEngine(settings)
    
    # Connect audio updates to all windows
    for window in windows:
        audio_engine.audio_data_updated.connect(window.update_bars)
    
    # Start capturing
    audio_engine.start()

    exit_code = app.exec()
    
    # Cleanup
    audio_engine.stop()
    audio_engine.wait()
    media_provider.stop()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
