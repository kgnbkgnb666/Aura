# AgentVoice

Local-first voice-to-agent prompt compiler.

Speak messy thoughts. Send clear prompts.

AgentVoice is not a general dictation app. It is a small floating desktop tool for people who use Codex, Claude Code, Cursor, ChatGPT, and other AI agents. It keeps the raw transcript visible, compiles it into a safer structured prompt, supports session-aware refinements, and copies the final prompt to your clipboard instead of executing anything automatically.

## Current Status

This repository is in early MVP development.

Implemented:

- Python-first project skeleton.
- Small PySide6 floating window.
- Focused push-to-talk with Space.
- SenseVoice-Small STT provider wrapper.
- OpenAI-compatible LLM provider, suitable for DeepSeek-compatible testing.
- Rule-based fallback compiler for local development without an API key.
- Session-aware refinement.
- Local SQLite history.
- Built-in modes for Codex, Claude Code, Cursor, Analyze Only, GitHub Issue, Bug Fix, PRD, and general cleanup.

Not yet implemented:

- Real-time streaming STT while speaking.
- Packaged Windows installer.
- Encrypted API key storage.
- Full cross-platform polish.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For DeepSeek-compatible testing:

```powershell
$env:DEEPSEEK_API_KEY="your_key"
python -m agentvoice app
```

Without an API key, AgentVoice uses a local rule-based compiler so the UI and session flow can still be tested.

On this development machine, you can also double-click:

```text
start_agentvoice.bat
```

## CLI Smoke Test

```powershell
python -m agentvoice compile "帮我把登录页表单校验统一走 zod，不要改后端，先分析一下风险" --mode codex
```

Transcribe a wav file with the configured STT provider:

```powershell
python -m agentvoice transcribe .\voice\test_mic.wav
```

## Product Shape

The MVP follows the PRD in [docs/PRD.md](docs/PRD.md):

- `Ctrl+Shift+Space` opens or hides the floating window.
- When the floating window is focused, hold `Space` to record.
- Release `Space` to transcribe and compile.
- The top area shows raw transcript.
- The bottom area shows the compiled agent prompt.
- The compiled result is copied to the clipboard by default.
- Keep recording in the same session to revise the previous prompt.
- Start a new session to ignore previous context.

## Speech Debugging

The default speech model is `SenseVoice-Small`, a lighter local model that is much more practical than Whisper large-v3 for desktop and internal enterprise deployment. It still downloads the first time it is used, but it is far smaller and starts faster than Whisper large-v3.

The model cache is stored in the project folder by default:

```text
models/
```

This keeps model files off the C drive and out of the conda environment. The `models/` folder is ignored by Git.

Whisper large-v3 remains available as an optional fallback in settings, but it requires extra dependencies:

```powershell
pip install transformers accelerate safetensors
```

Recommended debugging order:

1. Open `设置 -> 语音转录`.
2. Select the real microphone device, not `立体声混音`.
3. Click `测试麦克风 3 秒` and check average/max volume.
4. Click `预加载转录模型`.
5. Click `测试转录`.
6. Return to the floating window and hold `Space`.

## Configuration

The default config path on Windows is:

```text
%APPDATA%/AgentVoice/config.json
```

History is stored locally:

```text
%APPDATA%/AgentVoice/history.sqlite
```

Audio files are temporary and deleted after transcription by the UI flow.

## Development

```powershell
pip install -r requirements-dev.txt
pytest
```

Useful entry points:

- [agentvoice/ui/qt_app.py](agentvoice/ui/qt_app.py): floating window and settings dialog.
- [agentvoice/recorder.py](agentvoice/recorder.py): PyAudio recording module.
- [agentvoice/providers/stt/sensevoice_small.py](agentvoice/providers/stt/sensevoice_small.py): SenseVoice-Small provider.
- [agentvoice/providers/llm/openai_compatible.py](agentvoice/providers/llm/openai_compatible.py): OpenAI-compatible LLM provider.
- [modes](modes): prompt compiler modes.

## Sharing With Others

Current easiest sharing method:

1. Send this project folder or push it to GitHub.
2. Ask the other person to create a Python 3.11 environment.
3. Ask them to run `pip install -r requirements.txt`.
4. Ask them to run `python -m agentvoice app`.

For a cleaner end-user release, build a Windows executable with PyInstaller later:

```powershell
pip install pyinstaller
pyinstaller --name AgentVoice --windowed --add-data "modes;modes" agentvoice_app.py
```

Packaging is not polished yet. The current MVP is best shared with technical users who can install Python dependencies.
