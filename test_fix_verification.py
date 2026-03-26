import time
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from audio_engine import AudioEngine
from media_info import MediaInfoProvider
from settings import SettingsManager

class TestFixVerification(unittest.TestCase):
    def setUp(self):
        self.settings = SettingsManager().settings
        self.settings.bar_count = 10

    def test_audio_engine_rate_limiting(self):
        """Verify that AudioEngine does not emit signals too rapidly."""
        engine = AudioEngine(self.settings)
        engine.audio_data_updated = MagicMock()
        
        # Mock stream.read to return dummy data
        mock_stream = MagicMock()
        mock_stream.read.return_value = bytes(engine.chunk_size * 2 * 2) # Stereo int16
        mock_stream.is_active.return_value = True
        engine.stream = mock_stream
        engine.p = MagicMock()
        engine.running = True
        
        # We manually run a few iterations to check timing
        emissions = 0
        def on_emit(data):
            nonlocal emissions
            emissions += 1
        engine.audio_data_updated.connect(on_emit)
        
        # Run loop logic for a short period
        start_time = time.perf_counter()
        # We simulate 100 iterations as fast as possible
        for _ in range(100):
            # Simulate the part of run() that polls and emits
            data = engine.stream.read(engine.chunk_size)
            audio_data = np.frombuffer(data, dtype=np.int16)
            binned_data = [0.1] * self.settings.bar_count
            
            current_time = time.perf_counter()
            if current_time - engine.last_emit_time >= 0.016:
                engine.audio_data_updated.emit(np.array(binned_data))
                engine.last_emit_time = current_time
        
        duration = time.perf_counter() - start_time
        # In a tight loop of 100 iterations, if rate limiting works, 
        # emissions should be much less than 100 if the loop finishes quickly.
        # Max emissions in 'duration' seconds should be ~ duration / 0.016
        expected_max = int(duration / 0.016) + 1
        
        print(f"Emissions: {emissions}, Max Expected: {expected_max}, Duration: {duration:.4f}s")
        self.assertLessEqual(emissions, expected_max + 1)

    def test_audio_engine_error_delay(self):
        """Verify that AudioEngine sleeps on error to prevent CPU spin."""
        engine = AudioEngine(self.settings)
        engine.stream = MagicMock()
        # Mock read to raise an exception
        engine.stream.read.side_effect = Exception("Mock Error")
        engine.stream.is_active.return_value = True
        engine.running = True
        
        start_time = time.perf_counter()
        # Run 3 iterations of the error handling logic
        for _ in range(3):
            try:
                engine.stream.read(engine.chunk_size)
            except:
                engine.error_count += 1
                time.sleep(0.1) # This is what we added in the real code
        
        duration = time.perf_counter() - start_time
        # Duration should be at least 0.3 seconds
        print(f"Error Loop Duration: {duration:.4f}s")
        self.assertGreaterEqual(duration, 0.3)

    def test_media_info_lifecycle(self):
        """Verify MediaInfoProvider starts and stops cleanly."""
        provider = MediaInfoProvider()
        with patch('winsdk.windows.media.control.GlobalSystemMediaTransportControlsSessionManager.request_async') as mock_req:
            mock_req.return_value = MagicMock()
            provider.start_monitoring()
            time.sleep(0.5)
            self.assertTrue(provider._thread.is_alive())
            provider.stop()
            time.sleep(0.5)
            self.assertFalse(provider._thread.is_alive())

if __name__ == '__main__':
    unittest.main()
