import pyaudiowpatch as pyaudio
import numpy as np
import time
import warnings
from scipy.signal import butter, lfilter, find_peaks
from PyQt6.QtCore import QThread, pyqtSignal

warnings.filterwarnings('ignore')

def butter_bandpass(lowcut, highcut, fs, order=3):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def butter_highpass(cutoff, fs, order=2):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    return b, a

def butter_lowpass(cutoff, fs, order=3):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return b, a

class AudioEngine(QThread):
    audio_data_updated = pyqtSignal(list, float, float, float)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.p = None
        self.stream = None
        self.running = False
        self.chunk_size = 2048
        self.format = pyaudio.paInt16
        self.channels = 2
        self.rate = 44100
        self.last_emit_time = 0
        self.error_count = 0
        self.raw_audio_buffer = np.zeros(0, dtype=np.float32)
        self.last_calc_time = 0
        self.current_sps = 0.0
        self.current_onsets = 0.0

    def _setup_stream(self):
        """Initializes PyAudio and opens the audio stream."""
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
        if self.p:
            try:
                self.p.terminate()
            except:
                pass

        self.p = pyaudio.PyAudio()
        
        try:
            if self.settings.audio_device_index >= 0:
                # Use manually selected device
                device_index = self.settings.audio_device_index
                device_info = self.p.get_device_info_by_index(device_index)
                self.channels = int(device_info.get('maxInputChannels', 2))
                rate = int(device_info.get('defaultSampleRate', 44100))
                
                if self.channels == 0:
                    self.channels = 2
                    
                self.actual_rate = rate
                self.stream = self.p.open(format=self.format,
                                          channels=self.channels,
                                          rate=rate,
                                          input=True,
                                          input_device_index=device_index,
                                          frames_per_buffer=self.chunk_size)
            else:
                # Look for default WASAPI loopback device
                wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
                default_speakers = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
                
                if not default_speakers["isLoopbackDevice"]:
                    for loopback in self.p.get_loopback_device_info_generator():
                        if default_speakers["name"] in loopback["name"]:
                            default_speakers = loopback
                            break
                    else:
                        default_speakers = self.p.get_default_wasapi_loopback()
                        
                device_index = default_speakers["index"]
                self.channels = default_speakers["maxInputChannels"]
                if self.channels == 0:
                    self.channels = 2
    
                self.actual_rate = int(default_speakers["defaultSampleRate"])
                self.stream = self.p.open(format=self.format,
                                          channels=self.channels,
                                          rate=self.actual_rate,
                                          input=True,
                                          input_device_index=device_index,
                                          frames_per_buffer=self.chunk_size)
            return True
        except Exception as e:
            print(f"Failed to setup audio stream: {e}")
            return False

    def run(self):
        self.running = True
        
        if not self._setup_stream():
            self.running = False
            return
            
        # Pre-compute filter coefficients once actual_rate is known
        self.sps_bp_b, self.sps_bp_a = butter_bandpass(300.0, 3400.0, self.actual_rate, order=3)
        self.sps_lp_b, self.sps_lp_a = butter_lowpass(15.0, self.actual_rate, order=3)
        
        self.onset_hp_b, self.onset_hp_a = butter_highpass(100.0, self.actual_rate, order=2)
        self.onset_lp_b, self.onset_lp_a = butter_lowpass(30.0, self.actual_rate, order=3)
        
        self.max_samples = int(self.actual_rate * 1.0) # 1 second window
        self.last_calc_time = time.perf_counter()

        while self.running:
            try:
                if not self.stream or not self.stream.is_active():
                    if not self._setup_stream():
                        time.sleep(1.0) # Wait before retry
                        continue

                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)
                
                if self.channels == 2:
                    audio_data = audio_data.reshape(-1, 2).mean(axis=1)
                    
                # Store raw floats for SciPy filters
                float_audio_data = audio_data.astype(np.float32) / 32768.0
                self.raw_audio_buffer = np.concatenate((self.raw_audio_buffer, float_audio_data))
                if len(self.raw_audio_buffer) > self.max_samples:
                    self.raw_audio_buffer = self.raw_audio_buffer[-self.max_samples:]
                    
                # ---------------------------------------------------------
                # FIX 1: Apply Hanning Window to normalized floats for FFT
                # This prevents massive low-frequency spikes from spectral leakage
                # ---------------------------------------------------------
                window = np.hanning(self.chunk_size)
                windowed_audio = float_audio_data[-self.chunk_size:] * window
                fft_data = np.fft.rfft(windowed_audio)
                fft_mag = np.abs(fft_data) * 2.0 # Standard float magnitude
                
                bars = self.settings.bar_count
                binned_data = []
                
                if not hasattr(self, 'max_val'):
                    self.max_val = 0.01 # Start low

                # Lower noise floor because we are now using normalized floats instead of huge int16s
                NOISE_FLOOR = 0.005 
                scale_setting = getattr(self.settings, 'frequency_scale', 'log')
                use_mel = scale_setting in ['mel', 'mel_a_weight']
                use_a_weighting = scale_setting == 'mel_a_weight'
                
                if use_mel:
                    if hasattr(self, 'actual_rate'):
                        hz_per_bin = self.actual_rate / self.chunk_size
                    else:
                        hz_per_bin = 48000 / self.chunk_size
                    max_hz = 16000.0
                    max_bin = min(len(fft_mag) - 1, int(max_hz / hz_per_bin))
                    max_bin = max(max_bin, 2)
                    usable_mag = fft_mag[1:max_bin]
                else:
                    usable_mag = fft_mag[1:len(fft_mag)//2] 
                    
                avg_mag = np.mean(usable_mag) if len(usable_mag) > 0 else 0
                
                if len(usable_mag) >= bars and bars > 0 and avg_mag > NOISE_FLOOR:
                    if use_mel:
                        if not hasattr(self, '_cached_bin_edges_mel') or len(self._cached_bin_edges_mel) != bars + 1 or getattr(self, '_last_max_bin_mel', 0) != max_bin:
                            min_mel = 2595.0 * np.log10(1.0 + hz_per_bin / 700.0)
                            max_mel = 2595.0 * np.log10(1.0 + max_hz / 700.0)
                            mel_points = np.linspace(min_mel, max_mel, bars + 1)
                            hz_points = 700.0 * (10.0**(mel_points / 2595.0) - 1.0)
                            bin_edges = hz_points / hz_per_bin
                            self._cached_bin_edges_mel = bin_edges
                            self._last_max_bin_mel = max_bin
                        bin_edges = self._cached_bin_edges_mel
                    else:
                        min_freq_bin = 1
                        max_freq_bin = len(usable_mag)
                        
                        if not hasattr(self, '_cached_bin_edges_log') or len(self._cached_bin_edges_log) != bars + 1 or getattr(self, '_last_max_freq_bin_log', 0) != max_freq_bin:
                            self._cached_bin_edges_log = np.logspace(np.log10(min_freq_bin), np.log10(max_freq_bin), num=bars + 1)
                            self._last_max_freq_bin_log = max_freq_bin
                        bin_edges = self._cached_bin_edges_log
                    
                    prev_end = 0
                    raw_vals = []
                    for i in range(bars):
                        start = int(bin_edges[i]) - 1
                        end = int(bin_edges[i+1]) - 1
                        start = max(start, prev_end)
                        end = max(end, start + 1)
                        start = max(0, min(start, len(usable_mag) - 1))
                        end = max(0, min(end, len(usable_mag)))
                        prev_end = end
                        
                        if start < end:
                            mean_val = np.mean(usable_mag[start:end])
                        else:
                            mean_val = 0.0
                            
                        if use_mel:
                            if use_a_weighting:
                                center_hz = hz_per_bin * (start + end + 2) / 2.0
                                if center_hz <= 0:
                                    freq_weight = 0.0
                                else:
                                    f2 = center_hz**2
                                    num = (12194.0**2) * (f2**2)
                                    den = (f2 + 20.6**2) * np.sqrt((f2 + 107.7**2) * (f2 + 737.9**2)) * (f2 + 12194.0**2)
                                    freq_weight = (num / den) * 1.2589
                                    freq_weight *= 2.0
                            else:
                                freq_weight = 1.0 + (2.0 * (i / max(1, bars - 1)))
                                
                            val = max(0.0, (mean_val * freq_weight) - NOISE_FLOOR)
                        else:
                            val = max(0.0, mean_val - NOISE_FLOOR)
                        raw_vals.append(val)
                        
                    # ---------------------------------------------------------
                    # FIX 2: Fast Auto-Gain Decay
                    # Drops the ceiling much faster so the visualizer stays dynamic
                    # ---------------------------------------------------------
                    current_max = max(raw_vals) if raw_vals else 0.0
                    if current_max > self.max_val:
                        self.max_val = current_max
                    else:
                        self.max_val = max(0.01, self.max_val * 0.85) # 0.85 creates a great bounce!
                        
                    for val in raw_vals:
                        # Squash small values below noise floor, normalize the rest
                        val = max(0.0, val - NOISE_FLOOR)
                        normalized_val = val / self.max_val if self.max_val > 0 else 0
                        normalized_val = normalized_val ** 1.2
                        binned_data.append(min(1.0, normalized_val))
                else:
                    binned_data = [0.0] * bars
                    if hasattr(self, 'max_val'):
                        self.max_val = max(0.01, self.max_val * 0.85)
                
                # Calculate Loudness
                loudness = float(np.mean(binned_data)) if binned_data else 0.0
                
                # ---------------------------------------------------------
                # FIX 3: Instantaneous Pulses instead of Rolling Smears
                # ---------------------------------------------------------
                current_time = time.perf_counter()
                
                if len(self.raw_audio_buffer) >= self.max_samples:
                    if current_time - self.last_calc_time >= 0.05: # Update faster (20fps) for visuals
                        self.last_calc_time = current_time
                        
                        # -- SPS (Vocal Band) Instant Pulse --
                        sps_filtered = lfilter(self.sps_bp_b, self.sps_bp_a, self.raw_audio_buffer)
                        sps_env = lfilter(self.sps_lp_b, self.sps_lp_a, np.abs(sps_filtered))
                        
                        # Grab the max envelope value of ONLY the most recent chunk of audio
                        instant_sps = np.max(sps_env[-self.chunk_size:])
                        # Amplify and cap at 1.0 for a clean visual multiplier
                        self.current_sps = min(1.0, float(instant_sps * 15.0)) 
                            
                        # -- Onsets (Broadband Hits) Instant Pulse --
                        onset_filtered = lfilter(self.onset_hp_b, self.onset_hp_a, self.raw_audio_buffer)
                        onset_env = lfilter(self.onset_lp_b, self.onset_lp_a, np.abs(onset_filtered))
                        
                        # Grab the max envelope value of ONLY the most recent chunk of audio
                        instant_onset = np.max(onset_env[-self.chunk_size:])
                        self.current_onsets = min(1.0, float(instant_onset * 10.0))

                # Rate limit emission
                safe_refresh_rate = max(1, self.settings.refresh_rate)
                target_delay = 1.0 / safe_refresh_rate
                
                if current_time - self.last_emit_time >= target_delay:
                    # current_sps and current_onsets are now bouncing floats between 0.0 and 1.0!
                    self.audio_data_updated.emit(binned_data, loudness, self.current_sps, self.current_onsets)
                    self.last_emit_time = current_time
                
                self.error_count = 0 
                
            except Exception as e:
                self.error_count += 1
                time.sleep(0.1)
                if self.error_count > 10:
                    print(f"Audio error ({e}), re-initializing...")
                    self._setup_stream()
                    self.error_count = 0
                    time.sleep(0.5)

    def stop(self):
        self.running = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
        if self.p:
            try:
                self.p.terminate()
            except:
                pass
