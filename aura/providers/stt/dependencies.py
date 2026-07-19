"""STT provider dependency checker."""
from __future__ import annotations


def check_faster_whisper_available() -> tuple[bool, str]:
    """
    Check if faster-whisper is available.

    Returns:
        tuple[bool, str]: (is_available, error_message)
    """
    try:
        import faster_whisper  # noqa: F401
        return True, ""
    except ImportError as exc:
        error_msg = (
            "faster-whisper 未安装。\n\n"
            "安装方法：\n"
            "1. 激活虚拟环境：.venv\\Scripts\\activate (Windows) 或 source .venv/bin/activate (Linux/Mac)\n"
            "2. 安装依赖：pip install faster-whisper\n\n"
            f"详细错误：{exc}"
        )
        return False, error_msg


def check_funasr_available() -> tuple[bool, str]:
    """
    Check if FunASR is available.

    Returns:
        tuple[bool, str]: (is_available, error_message)
    """
    try:
        import funasr  # noqa: F401
        return True, ""
    except ImportError as exc:
        error_msg = (
            "funasr 未安装。\n\n"
            "安装方法：\n"
            "1. 激活虚拟环境：.venv\\Scripts\\activate (Windows) 或 source .venv/bin/activate (Linux/Mac)\n"
            "2. 安装依赖：pip install funasr modelscope\n\n"
            f"详细错误：{exc}"
        )
        return False, error_msg


def get_available_stt_providers() -> dict[str, bool]:
    """
    Get all STT providers and their availability.

    Returns:
        dict[str, bool]: provider_name -> is_available
    """
    whisper_available, _ = check_faster_whisper_available()
    funasr_available, _ = check_funasr_available()

    return {
        "sensevoice-small": funasr_available,
        "whisper-large-v3": whisper_available,
    }


def validate_stt_provider(provider: str) -> tuple[bool, str]:
    """
    Validate if a STT provider can be used.

    Args:
        provider: Provider name (sensevoice-small or whisper-large-v3)

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    if provider == "whisper-large-v3":
        return check_faster_whisper_available()
    elif provider == "sensevoice-small":
        return check_funasr_available()
    else:
        return False, f"未知的 STT 提供商: {provider}"
