import pyaudiowpatch as pyaudio
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

class AudioEngine(QThread):
    audio_data_updated = pyqtSignal(np.ndarray)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.running = False
        self.chunk_size = 1024
        self.format = pyaudio.paInt16
        self.channels = 2
        self.rate = 44100

    def run(self):
        self.running = True

        try:
            if self.settings.audio_device_index >= 0:
                # Use manually selected device
                device_index = self.settings.audio_device_index
                device_info = self.p.get_device_info_by_index(device_index)
                self.channels = int(device_info.get('maxInputChannels', 2))
                rate = int(device_info.get('defaultSampleRate', 44100))
                
                # If the user selected a loopback device with 0 input channels, it might still work 
                # if we specify it as an input via WASAPI loopback, but fallback to 2 channels
                if self.channels == 0:
                    self.channels = 2
                    
                self.stream = self.p.open(format=self.format,
                                          channels=self.channels,
                                          rate=rate,
                                          input=True,
                                          input_device_index=device_index,
                                          frames_per_buffer=self.chunk_size)
            else:
                # Look for default WASAPI loopback device using pyaudiowpatch
                wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
                default_speakers = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
                
                if not default_speakers["isLoopbackDevice"]:
                    for loopback in self.p.get_loopback_device_info_generator():
                        # Try to find loopback for default speakers
                        if default_speakers["name"] in loopback["name"]:
                            default_speakers = loopback
                            break
                    else:
                        # Fallback to the first loopback device found
                        default_speakers = self.p.get_default_wasapi_loopback()
                        
                device_index = default_speakers["index"]
                self.channels = default_speakers["maxInputChannels"]
                if self.channels == 0:
                    self.channels = 2
    
                self.stream = self.p.open(format=self.format,
                                          channels=self.channels,
                                          rate=int(default_speakers["defaultSampleRate"]),
                                          input=True,
                                          input_device_index=device_index,
                                          frames_per_buffer=self.chunk_size)

            while self.running:
                try:
                    data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    
                    if self.channels == 2:
                        # Average channels
                        audio_data = audio_data.reshape(-1, 2).mean(axis=1)
                        
                    fft_data = np.fft.rfft(audio_data)
                    fft_mag = np.abs(fft_data)
                    
                    # Logarithmic binning
                    bars = self.settings.bar_count
                    binned_data = []
                    
                    if not hasattr(self, 'max_val'):
                        self.max_val = 1.0  # Dynamic scaling max

                    NOISE_FLOOR = 30.0 # Audio magnitude threshold to consider as silence

                    # Skip DC component (index 0) and high noise
                    usable_mag = fft_mag[1:len(fft_mag)//2] 
                    
                    # Compute average magnitude of the frame to check against noise floor
                    avg_mag = np.mean(usable_mag) if len(usable_mag) > 0 else 0
                    
                    if len(usable_mag) >= bars and bars > 0 and avg_mag > NOISE_FLOOR:
                        bin_size = len(usable_mag) // bars
                        for i in range(bars):
                            start = i * bin_size
                            end = start + bin_size
                            # Subtract noise floor to eliminate static
                            val = max(0.0, np.mean(usable_mag[start:end]) - NOISE_FLOOR)
                            
                            # Update dynamic max (slowly decay to adapt to quieter parts)
                            if val > self.max_val:
                                self.max_val = val
                            else:
                                self.max_val = max(200.0, self.max_val * 0.98) # Don't drop max_val too low
                                
                            normalized_val = val / self.max_val if self.max_val > 0 else 0
                            binned_data.append(min(1.0, normalized_val))
                    else:
                        # Below noise floor or empty array -> silence
                        binned_data = [0.0] * bars
                        # Keep decaying max_val even during silence
                        if hasattr(self, 'max_val'):
                            self.max_val = max(200.0, self.max_val * 0.98)
                        
                    self.audio_data_updated.emit(np.array(binned_data))
                    
                except Exception as stream_err:
                    pass # Ignore read overflows
                    
        except Exception as e:
            print(f"Audio stream initialization error: {e}")

    def stop(self):
        self.running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()
