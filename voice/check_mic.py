import pyaudio
import numpy as np

def list_audio_devices():
    """列出所有音频设备"""
    p = pyaudio.PyAudio()
    
    print("=" * 60)
    print("🎤 音频设备列表")
    print("=" * 60)
    
    for i in range(p.get_device_count()):
        device_info = p.get_device_info_by_index(i)
        name = device_info['name']
        max_input_channels = device_info['maxInputChannels']
        max_output_channels = device_info['maxOutputChannels']
        default_sample_rate = int(device_info['defaultSampleRate'])
        
        # 标记默认设备
        is_default_input = i == p.get_default_input_device_info()['index']
        is_default_output = i == p.get_default_output_device_info()['index']
        
        device_type = []
        if max_input_channels > 0:
            device_type.append("输入")
        if max_output_channels > 0:
            device_type.append("输出")
        
        marker = ""
        if is_default_input:
            marker += " ⭐默认输入"
        if is_default_output:
            marker += " ⭐默认输出"
        
        print(f"设备 {i}: {name}")
        print(f"   类型: {'/'.join(device_type)}")
        print(f"   最大采样率: {default_sample_rate}Hz{marker}")
        print()
    
    p.terminate()

def test_microphone():
    """测试麦克风录音"""
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    RECORD_SECONDS = 3
    
    p = pyaudio.PyAudio()
    
    # 获取默认输入设备
    default_input = p.get_default_input_device_info()
    print(f"🎤 使用默认输入设备: {default_input['name']}")
    print(f"   采样率: {int(default_input['defaultSampleRate'])}Hz")
    print(f"   输入通道: {default_input['maxInputChannels']}")
    print()
    
    print("🔴 开始录音 3 秒...")
    
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=default_input['index'],  # 明确指定输入设备
        frames_per_buffer=CHUNK
    )
    
    frames = []
    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)
        # 实时显示音量
        audio_data = np.frombuffer(data, dtype=np.int16)
        volume = np.abs(audio_data).mean()
        bar = "█" * int(volume / 100)
        print(f"\r音量: {volume:6.0f} {bar}", end="")
    
    print("\n✅ 录音完成")
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # 保存测试音频
    import wave
    wf = wave.open("test_mic.wav", 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    
    # 检查音量
    all_data = np.frombuffer(b''.join(frames), dtype=np.int16)
    max_volume = np.abs(all_data).max()
    avg_volume = np.abs(all_data).mean()
    
    print(f"\n📊 音量统计:")
    print(f"   平均音量: {avg_volume:.0f}")
    print(f"   最大音量: {max_volume}")
    
    if avg_volume < 100:
        print("⚠️ 音量太低！请检查：")
        print("   1. 麦克风是否连接正常")
        print("   2. 系统麦克风音量是否调高")
        print("   3. 是否有录音权限")
        print("   4. 是否选择了正确的输入设备")
    else:
        print("✅ 麦克风工作正常")
    
    print(f"\n💾 测试音频已保存到: test_mic.wav")

if __name__ == "__main__":
    # 列出所有设备
    list_audio_devices()
    
    # 测试麦克风
    input("\n按 Enter 键开始麦克风测试...")
    test_microphone()