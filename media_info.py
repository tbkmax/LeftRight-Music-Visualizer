import asyncio
import threading
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
from PyQt6.QtCore import QObject, pyqtSignal

class MediaInfoProvider(QObject):
    media_updated = pyqtSignal(str, str) # title, artist
    
    def __init__(self):
        super().__init__()
        self.session_manager = None
        self.current_title = ""
        self.current_artist = ""
        self._loop = asyncio.new_event_loop()
        self._thread = None
        
    def start_monitoring(self):
        """Starts the background thread and initializes the session manager."""
        self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._thread.start()

    def _run_event_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._init_session_manager())
        self._loop.run_forever()

    async def _init_session_manager(self):
        try:
            self.session_manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
            if self.session_manager:
                self.session_manager.add_sessions_changed(self._on_sessions_changed)
                await self._update_media_info()
        except Exception as e:
            print(f"Failed to initialize MediaInfoProvider: {e}")

    def _on_sessions_changed(self, sender, args):
        if self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._update_media_info(), self._loop)

    async def _update_media_info(self):
        if not self.session_manager:
            return
            
        try:
            session = self.session_manager.get_current_session()
            if session:
                media_props = await session.try_get_media_properties_async()
                if media_props:
                    title = media_props.title
                    artist = media_props.artist
                    if title != self.current_title or artist != self.current_artist:
                        self.current_title = title
                        self.current_artist = artist
                        self.media_updated.emit(title, artist)
        except Exception as e:
            # Common to have transient errors when sessions are changing
            pass

    def stop(self):
        """Stops the monitoring thread and cleans up resources."""
        if self.session_manager:
            try:
                # Remove listener if possible (though winsdk sometimes makes this hard)
                pass
            except:
                pass
        
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
            
        if self._thread:
            self._thread.join(timeout=1.0)
