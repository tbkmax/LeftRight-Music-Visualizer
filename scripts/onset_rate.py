import time
import warnings
import numpy as np
import pyaudiowpatch as pyaudio
from scipy.signal import butter, lfilter, find_peaks

warnings.filterwarnings('ignore')

CHUNK_SIZE = 2048
DELAY_SECONDS = 1.0 # 1 second rolling window to calculate exact Onsets Per Second
UPDATE_INTERVAL = 0.2 # update 5 times a second in the console

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

class OnsetTracker:
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
        # 1. Highpass filter (>100Hz) to remove sub-bass rumble which can muddy sharp transient hits
        self.hp_b, self.hp_a = butter_highpass(100.0, self.actual_rate, order=2)
        
        # 2. Lowpass filter for envelope extraction (30Hz is fast enough to track rapid snare rolls)
        self.lp_b, self.lp_a = butter_lowpass(30.0, self.actual_rate, order=3)
        
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
        print(f"Tracking Perceptual Onset Rate (Broadband Hits per Second)...")
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
                        
                        # 1. Highpass to remove rumble
                        filtered_audio = lfilter(self.hp_b, self.hp_a, self.raw_audio_buffer)
                        
                        # 2. Rectify
                        rectified = np.abs(filtered_audio)
                        
                        # 3. Fast lowpass filter to get the broadband envelope
                        envelope = lfilter(self.lp_b, self.lp_a, rectified)
                        
                        rms = np.sqrt(np.mean(envelope**2))
                        
                        if rms < 0.005:
                            print(f"   [Silence]")
                        else:
                            # 4. Find peaks (onsets)
                            # Minimum distance: 0.03s allows up to ~33 hits per second (human drum rolls max ~20-25)
                            min_dist = int(self.actual_rate * 0.03)
                            
                            # Prominence needs to scale with RMS so we only pick distinct impacts, not noise
                            prominence_thresh = max(0.01, rms * 0.4) 
                            
                            peaks, _ = find_peaks(envelope, distance=min_dist, prominence=prominence_thresh)
                            
                            onset_rate = len(peaks)
                            
                            # Visual console bar (capped at 50 chars so it doesn't wrap)
                            bar = "█" * min(onset_rate, 50)
                            print(f"🥁 Live Onset Rate: {onset_rate:2d} hits/sec  {bar}")
                            
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
    tracker = OnsetTracker()
    tracker.start()
