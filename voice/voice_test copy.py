import pyaudio
import wave
import threading
import time
import os
import numpy as np
from funasr import AutoModel
from pynput import keyboard

# ==================== 配置参数 ====================
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
WAVE_OUTPUT_FILENAME = "temp_audio.wav"

# 🔥 指定使用设备2（Web Camera麦克风）
INPUT_DEVICE_INDEX = 2

# ==================== 初始化 FunASR 模型 ====================
model = AutoModel(
    model="paraformer-zh",
    model_revision="v2.0.4",
    vad_model="fsmn-vad",
    punc_model="ct-punc",
    disable_update=True,
    device="cpu",
)

# ==================== 录音相关变量 ====================
frames = []
is_recording = False
audio = None
stream = None

def get_input_device_info():
    """获取输入设备信息"""
    p = pyaudio.PyAudio()
    try:
        if INPUT_DEVICE_INDEX is not None:
            device_info = p.get_device_info_by_index(INPUT_DEVICE_INDEX)
            print(f"🎤 使用指定设备: {device_info['name']}")
            print(f"   采样率: {int(device_info['defaultSampleRate'])}Hz")
            print(f"   输入通道: {device_info['maxInputChannels']}")
            return device_info
        else:
            device_info = p.get_default_input_device_info()
            print(f"🎤 使用默认设备: {device_info['name']}")
            return device_info
    except Exception as e:
        print(f"❌ 获取设备信息失败: {e}")
        return None
    finally:
        p.terminate()

def start_recording():
    """开始录音"""
    global frames, is_recording, audio, stream
    frames = []
    is_recording = True

    audio = pyaudio.PyAudio()
    
    # 获取设备信息
    device_info = get_input_device_info()
    if device_info is None:
        print("❌ 无法获取输入设备")
        is_recording = False
        return
    
    # 打开音频流
    try:
        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=INPUT_DEVICE_INDEX,  # 指定设备2
            frames_per_buffer=CHUNK
        )
        print("\n🎤 录音中... (按住空格说话，松开识别)")
    except Exception as e:
        print(f"❌ 打开音频流失败: {e}")
        print("   请检查：")
        print("   1. 设备2是否被其他程序占用")
        print("   2. 是否有录音权限")
        is_recording = False
        return

    # 在后台线程中持续读取音频数据
    def record():
        global frames, is_recording
        try:
            silence_count = 0
            has_sound = False
            
            while is_recording:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
                
                # 实时显示音量
                audio_data = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_data).mean()
                
                # 检测是否有声音
                if volume > 100:
                    has_sound = True
                    silence_count = 0
                    # 显示音量条
                    bar_length = min(int(volume / 200), 50)
                    bar = "█" * bar_length
                    print(f"\r🔊 音量: {volume:6.0f} {bar}", end="")
                else:
                    silence_count += 1
                    if silence_count % 10 == 0:
                        print(f"\r🔇 静音中... {silence_count * CHUNK / RATE:.1f}s", end="")
                    
                    # 如果已经录到声音，且静音超过2秒，自动结束
                    if has_sound and silence_count > RATE // CHUNK * 2:
                        print("\n🔇 检测到静音，自动结束录音")
                        # 自动触发停止录音
                        threading.Thread(target=stop_recording_and_transcribe, daemon=True).start()
                        break
                        
        except Exception as e:
            print(f"\n❌ 录音线程错误: {e}")

    threading.Thread(target=record, daemon=True).start()

def stop_recording_and_transcribe():
    """停止录音并进行语音转文字"""
    global is_recording, frames, stream, audio

    if not is_recording:
        return

    is_recording = False

    # 等待录音线程结束
    time.sleep(0.2)

    if stream:
        try:
            stream.stop_stream()
            stream.close()
        except:
            pass
    if audio:
        try:
            audio.terminate()
        except:
            pass

    if not frames:
        print("\n⚠️ 没有录制到任何音频")
        return

    # 检查录音音量和时长
    all_data = np.frombuffer(b''.join(frames), dtype=np.int16)
    avg_volume = np.abs(all_data).mean()
    audio_duration = len(frames) * CHUNK / RATE
    
    print(f"\n📊 录音统计:")
    print(f"   时长: {audio_duration:.2f}秒")
    print(f"   平均音量: {avg_volume:.0f}")
    
    if avg_volume < 100:
        print("⚠️ 音量太低！请检查：")
        print("   1. 麦克风是否靠近嘴边")
        print("   2. 系统麦克风音量是否调高")
        print("   3. 设备2是否正确")
        frames = []
        return
    
    if audio_duration < 0.5:
        print("⚠️ 录音时间太短，请按住空格说话至少1秒")
        frames = []
        return

    print("⏳ 正在识别...")

    # 保存为临时 WAV 文件
    try:
        wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        # 保存一份用于调试（可选）
        # wf_debug = wave.open("debug_audio.wav", 'wb')
        # wf_debug.setnchannels(CHANNELS)
        # wf_debug.setsampwidth(audio.get_sample_size(FORMAT))
        # wf_debug.setframerate(RATE)
        # wf_debug.writeframes(b''.join(frames))
        # wf_debug.close()
        # print("💾 调试音频已保存: debug_audio.wav")
        
    except Exception as e:
        print(f"❌ 保存音频失败: {e}")
        frames = []
        return

    # 使用 FunASR 进行识别
    try:
        res = model.generate(
            input=WAVE_OUTPUT_FILENAME,
            batch_size_s=300,
        )
        if res and len(res) > 0:
            text = res[0].get("text", "").strip()
            if text:
                print(f"\n✅ 识别结果: {text}")
            else:
                print("\n⚠️ 未识别到有效语音")
                print("   请确保：")
                print("   1. 说话清晰，语速适中")
                print("   2. 尽量在安静环境下录音")
                print("   3. 录音时长至少1-2秒")
        else:
            print("\n⚠️ 未识别到有效语音")
    except Exception as e:
        print(f"❌ 识别出错: {e}")

    # 清理临时文件
    if os.path.exists(WAVE_OUTPUT_FILENAME):
        try:
            os.remove(WAVE_OUTPUT_FILENAME)
        except:
            pass

    frames = []

# ==================== 键盘监听 ====================
def on_press(key):
    """按下按键时触发"""
    global is_recording
    if key == keyboard.Key.space and not is_recording:
        start_recording()

def on_release(key):
    """释放按键时触发"""
    if key == keyboard.Key.space:
        # 在独立线程中执行识别，避免阻塞键盘监听
        threading.Thread(target=stop_recording_and_transcribe, daemon=True).start()
    elif key == keyboard.Key.esc:
        # 按 ESC 退出程序
        print("\n👋 退出程序")
        return False

# ==================== 主程序 ====================
if __name__ == "__main__":
    print("=" * 50)
    print("🎙️  按住 空格键 开始录音，松开后自动识别")
    print("   按 ESC 键退出程序")
    print("=" * 50)
    
    # 先显示设备信息
    get_input_device_info()
    print()

    # 启动键盘监听
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()