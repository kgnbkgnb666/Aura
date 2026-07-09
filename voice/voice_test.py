from __future__ import annotations

import os
import logging
import threading
import time
import wave
from pathlib import Path

import numpy as np
import pyaudio
from pynput import keyboard


# ==================== 配置参数 ====================
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
WAVE_OUTPUT_FILENAME = "temp_audio.wav"

# 指定使用设备 2（Web Camera 麦克风）
INPUT_DEVICE_INDEX = 2


# ==================== FunASR 模型懒加载 ====================
for logger_name in ("modelscope", "modelscope_hub", "jieba"):
    logging.getLogger(logger_name).setLevel(logging.ERROR)
logging.getLogger().setLevel(logging.ERROR)

MODEL_CACHE_DIR = Path(
    os.environ.get("MODELSCOPE_CACHE", Path.home() / ".cache" / "modelscope")
)

ASR_CACHE_PATH = (
    MODEL_CACHE_DIR
    / "models"
    / "iic--speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    / "snapshots"
    / "v2.0.4"
)
VAD_CACHE_PATH = (
    MODEL_CACHE_DIR
    / "models"
    / "iic--speech_fsmn_vad_zh-cn-16k-common-pytorch"
    / "snapshots"
    / "master"
)
PUNC_CACHE_PATH = (
    MODEL_CACHE_DIR
    / "models"
    / "iic--punc_ct-transformer_cn-en-common-vocab471067-large"
    / "snapshots"
    / "master"
)

model = None
model_lock = threading.Lock()
model_ready = threading.Event()
model_loading = False
model_error: Exception | None = None


def _cache_path_or_alias(path: Path, alias: str) -> str:
    """优先使用本地快照目录，避免每次启动都触发 ModelScope 下载检查。"""
    if (path / "configuration.json").exists():
        return str(path)
    return alias


def _create_funasr_model():
    from funasr import AutoModel

    asr_model = _cache_path_or_alias(ASR_CACHE_PATH, "paraformer-zh")
    vad_model = _cache_path_or_alias(VAD_CACHE_PATH, "fsmn-vad")
    punc_model = _cache_path_or_alias(PUNC_CACHE_PATH, "ct-punc")

    kwargs = {
        "model": asr_model,
        "vad_model": vad_model,
        "punc_model": punc_model,
        "disable_update": True,
        "device": "cpu",
    }
    if asr_model == "paraformer-zh":
        kwargs["model_revision"] = "v2.0.4"

    return AutoModel(**kwargs)


def ensure_model(show_status: bool = True):
    """返回已加载模型；如果后台还在预热，则等待它完成。"""
    global model, model_loading, model_error

    with model_lock:
        if model is not None:
            return model

        if model_loading:
            should_wait = True
        else:
            model_loading = True
            model_error = None
            model_ready.clear()
            should_wait = False

    if should_wait:
        if show_status:
            print("\n⏳ 模型还在后台加载，正在等待就绪...")
        model_ready.wait()
        with model_lock:
            if model_error is not None:
                raise RuntimeError(f"FunASR 模型加载失败: {model_error}") from model_error
            return model

    try:
        if show_status:
            print("🔄 后台预热 FunASR 模型...")
        loaded_model = _create_funasr_model()
    except Exception as exc:
        with model_lock:
            model_error = exc
            model_loading = False
            model_ready.set()
        raise

    with model_lock:
        model = loaded_model
        model_loading = False
        model_ready.set()

    if show_status:
        print("✅ FunASR 模型已就绪")
    return loaded_model


def warm_up_model_in_background():
    """启动后立即显示界面，模型在后台加载。"""

    def warm_up():
        try:
            ensure_model(show_status=True)
        except Exception as exc:
            print(f"\n❌ FunASR 模型后台加载失败: {exc}")

    threading.Thread(target=warm_up, daemon=True).start()


# ==================== 录音相关变量 ====================
frames = []
is_recording = False
audio = None
stream = None


def get_input_device_info():
    """获取输入设备信息。"""
    p = pyaudio.PyAudio()
    try:
        if INPUT_DEVICE_INDEX is not None:
            device_info = p.get_device_info_by_index(INPUT_DEVICE_INDEX)
            print(f"🎤 使用指定设备: {device_info['name']}")
            print(f"   采样率: {int(device_info['defaultSampleRate'])}Hz")
            print(f"   输入通道: {device_info['maxInputChannels']}")
            return device_info

        device_info = p.get_default_input_device_info()
        print(f"🎤 使用默认设备: {device_info['name']}")
        return device_info
    except Exception as exc:
        print(f"❌ 获取设备信息失败: {exc}")
        return None
    finally:
        p.terminate()


def start_recording():
    """开始录音。"""
    global frames, is_recording, audio, stream
    frames = []
    is_recording = True

    audio = pyaudio.PyAudio()

    device_info = get_input_device_info()
    if device_info is None:
        print("❌ 无法获取输入设备")
        is_recording = False
        return

    try:
        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=INPUT_DEVICE_INDEX,
            frames_per_buffer=CHUNK,
        )
        print("\n🎙️ 录音中...（按住空格说话，松开识别）")
    except Exception as exc:
        print(f"❌ 打开音频流失败: {exc}")
        print("   请检查：")
        print("   1. 设备 2 是否被其他程序占用")
        print("   2. 是否有录音权限")
        is_recording = False
        return

    def record():
        global frames, is_recording
        try:
            silence_count = 0
            has_sound = False

            while is_recording:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)

                audio_data = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_data).mean()

                if volume > 100:
                    has_sound = True
                    silence_count = 0
                    bar_length = min(int(volume / 200), 50)
                    bar = "█" * bar_length
                    print(f"\r🔊 音量: {volume:6.0f} {bar}", end="")
                else:
                    silence_count += 1
                    if silence_count % 10 == 0:
                        print(
                            f"\r🔇 静音中... {silence_count * CHUNK / RATE:.1f}s",
                            end="",
                        )

                    if has_sound and silence_count > RATE // CHUNK * 2:
                        print("\n🔇 检测到静音，自动结束录音")
                        threading.Thread(
                            target=stop_recording_and_transcribe, daemon=True
                        ).start()
                        break
        except Exception as exc:
            print(f"\n❌ 录音线程错误: {exc}")

    threading.Thread(target=record, daemon=True).start()


def stop_recording_and_transcribe():
    """停止录音并进行语音转文字。"""
    global is_recording, frames, stream, audio

    if not is_recording:
        return

    is_recording = False

    time.sleep(0.2)

    if stream:
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
    if audio:
        try:
            audio.terminate()
        except Exception:
            pass

    if not frames:
        print("\n⚠️ 没有录制到任何音频")
        return

    all_data = np.frombuffer(b"".join(frames), dtype=np.int16)
    avg_volume = np.abs(all_data).mean()
    audio_duration = len(frames) * CHUNK / RATE

    print("\n📊 录音统计:")
    print(f"   时长: {audio_duration:.2f}秒")
    print(f"   平均音量: {avg_volume:.0f}")

    if avg_volume < 100:
        print("⚠️ 音量太低！请检查：")
        print("   1. 麦克风是否靠近嘴边")
        print("   2. 系统麦克风音量是否调高")
        print("   3. 设备 2 是否正确")
        frames = []
        return

    if audio_duration < 0.5:
        print("⚠️ 录音时间太短，请按住空格说话至少 1 秒")
        frames = []
        return

    try:
        with wave.open(WAVE_OUTPUT_FILENAME, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(pyaudio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b"".join(frames))
    except Exception as exc:
        print(f"❌ 保存音频失败: {exc}")
        frames = []
        return

    try:
        loaded_model = ensure_model(show_status=True)
        print("⏳ 正在识别...")
        res = loaded_model.generate(
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
                print("   3. 录音时长至少 1-2 秒")
        else:
            print("\n⚠️ 未识别到有效语音")
    except Exception as exc:
        print(f"❌ 识别出错: {exc}")
    finally:
        if os.path.exists(WAVE_OUTPUT_FILENAME):
            try:
                os.remove(WAVE_OUTPUT_FILENAME)
            except Exception:
                pass
        frames = []


# ==================== 键盘监听 ====================
def on_press(key):
    """按下按键时触发。"""
    global is_recording
    if key == keyboard.Key.space and not is_recording:
        start_recording()


def on_release(key):
    """释放按键时触发。"""
    if key == keyboard.Key.space:
        threading.Thread(target=stop_recording_and_transcribe, daemon=True).start()
    elif key == keyboard.Key.esc:
        print("\n👋 退出程序")
        return False
    return None


# ==================== 主程序 ====================
if __name__ == "__main__":
    print("=" * 50)
    print("🎙️  按住 空格键 开始录音，松开后自动识别")
    print("   按 ESC 键退出程序")
    print("=" * 50)

    get_input_device_info()
    print()

    warm_up_model_in_background()

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()
