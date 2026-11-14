import pyaudiowpatch as pyaudio

def list_devices():
    p = pyaudio.PyAudio()
    print("=== Available Audio Input & Loopback Devices =====\n")
    
    # Get WASAPI host API info
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        print(f"Default WASAPI Output Index: {wasapi_info['defaultOutputDevice']}")
        print(f"Default WASAPI Input Index: {wasapi_info['defaultInputDevice']}\n")
    except Exception as e:
        print(f"Could not get WASAPI info: {e}\n")

    print(f"{'Index':<6} | {'Channels':<8} | {'Type':<12} | {'Name'}")
    print("-" * 75)

    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        name = dev["name"]
        channels = dev["maxInputChannels"]
        is_loopback = dev.get("isLoopbackDevice", False)
        
        # Only show loopback devices since the visualizer requires system audio capture
        if is_loopback:
            dev_type = "Loopback"
            if channels == 0:
                # Some loopback devices report 0 max channels but work fine.
                channels = "2 (Virtual)" 
                
            print(f"{i:<6} | {str(channels):<8} | {dev_type:<12} | {name}")
            
    p.terminate()
    print("\n==================================================")
    print("To use a specific device, open 'settings.json' and set 'audio_device_index' to its Index.")
    print("If you want to use the default system speakers, leave it as -1.")

if __name__ == '__main__':
    list_devices()
