import asyncio
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
        
    def start_monitoring(self):
        # Fire and forget init - running in a thread might be needed if this blocks PyQt event loop
        # We will handle async initialization safely.
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._init_session_manager())

    async def _init_session_manager(self):
        self.session_manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        if self.session_manager:
            self.session_manager.add_sessions_changed(self._on_sessions_changed)
            await self._update_media_info()

    def _on_sessions_changed(self, sender, args):
        asyncio.run_coroutine_threadsafe(self._update_media_info(), self._loop)

    async def _update_media_info(self):
        if not self.session_manager:
            return
            
        session = self.session_manager.get_current_session()
        if session:
            try:
                media_props = await session.try_get_media_properties_async()
                if media_props:
                    title = media_props.title
                    artist = media_props.artist
                    if title != self.current_title or artist != self.current_artist:
                        self.current_title = title
                        self.current_artist = artist
                        self.media_updated.emit(title, artist)
            except Exception as e:
                print(f"Error fetching media info: {e}")
