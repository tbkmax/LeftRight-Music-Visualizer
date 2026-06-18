import time
import warnings
import numpy as np
import pyaudiowpatch as pyaudio
from scipy.signal import butter, lfilter, find_peaks

warnings.filterwarnings('ignore')

CHUNK_SIZE = 2048
DELAY_SECONDS = 1.0 # 1 second rolling window to calculate exact SPS
UPDATE_INTERVAL = 0.2 # update 5 times a second in the console

def butter_bandpass(lowcut, highcut, fs, order=3):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def butter_lowpass(cutoff, fs, order=3):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return b, a

class SPSTracker:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_speakers = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        
        if not default_speakers["isLoopbackDevice"]:
            for loopback in self.p.get_loopback_device_info_generator():
                if default_speakers["name"] in loopback["name"]:
                    self.device_info = loopback
                    break
            else:
                self.device_info = self.p.get_default_wasapi_loopback()
        else:
            self.device_info = default_speakers
            
        self.channels = self.device_info["maxInputChannels"]
        self.actual_rate = int(self.device_info["defaultSampleRate"])
        self.max_samples = int(self.actual_rate * DELAY_SECONDS)
        
        self.raw_audio_buffer = np.zeros(0, dtype=np.float32)
        self.last_calc_time = time.perf_counter()
        
        # Pre-compute filter coefficients
        # 1. Bandpass filter to isolate vocal frequencies (300Hz - 3400Hz)
        self.bp_b, self.bp_a = butter_bandpass(300.0, 3400.0, self.actual_rate, order=3)
        # 2. Lowpass filter for envelope extraction (smooths out the raw waves into distinct "humps")
        self.lp_b, self.lp_a = butter_lowpass(15.0, self.actual_rate, order=3)
        
    def start(self):
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.actual_rate,
            input=True,
            input_device_index=self.device_info["index"],
            frames_per_buffer=CHUNK_SIZE
        )
        self.running = True
        
        print(f"Listening to: {self.device_info['name']}")
        print(f"Tracking Syllables Per Second (SPS) in the 300Hz-3400Hz vocal range...")
        print("Press Ctrl+C to stop...\n")
        
        try:
            while self.running:
                data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)
                
                if self.channels == 2:
                    audio_data = audio_data.reshape(-1, 2).mean(axis=1)
                    
                float_audio_data = audio_data.astype(np.float32) / 32768.0
                
                self.raw_audio_buffer = np.concatenate((self.raw_audio_buffer, float_audio_data))
                if len(self.raw_audio_buffer) > self.max_samples:
                    self.raw_audio_buffer = self.raw_audio_buffer[-self.max_samples:]
                
                current_time = time.perf_counter()
                
                if len(self.raw_audio_buffer) >= self.max_samples:
                    if current_time - self.last_calc_time >= UPDATE_INTERVAL:
                        self.last_calc_time = current_time
                        
                        # 1. Bandpass filter to isolate vocals
                        filtered_audio = lfilter(self.bp_b, self.bp_a, self.raw_audio_buffer)
                        
                        # 2. Rectify to get positive amplitude
                        rectified = np.abs(filtered_audio)
                        
                        # 3. Lowpass filter to get the smooth volume envelope
                        envelope = lfilter(self.lp_b, self.lp_a, rectified)
                        
                        # Calculate a dynamic prominence threshold based on the current volume
                        rms = np.sqrt(np.mean(envelope**2))
                        
                        if rms < 0.005:
                            print(f"   [Silence]")
                        else:
                            # 4. Find peaks (onsets)
                            # Minimum distance between syllables (e.g. 0.08s = max 12.5 syllables per sec)
                            min_dist = int(self.actual_rate * 0.08)
                            
                            # Prominence ensures we only count distinct spikes, not minor ripples
                            prominence_thresh = max(0.01, rms * 0.5) 
                            
                            peaks, _ = find_peaks(envelope, distance=min_dist, prominence=prominence_thresh)
                            
                            sps = len(peaks)
                            
                            # Simple visual bar for the console
                            bar = "█" * sps
                            print(f"🎤 Live SPS: {sps:2d} {bar}  (Vocal RMS: {rms:.3f})")
                            
        except KeyboardInterrupt:
            self.stop()
            
    def stop(self):
        print("\nStopping tracker...")
        self.running = False
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()

if __name__ == "__main__":
    tracker = SPSTracker()
    tracker.start()
