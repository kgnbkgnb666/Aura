# Aura

Local-first voice-to-agent prompt compiler.

Aura is a small Tauri desktop app for people who use Codex, Claude Code, Cursor, ChatGPT, and other AI agents. Speak messy thoughts, see the raw transcript immediately, then watch Aura stream a cleaner agent-ready prompt and copy the result when it is done.

## Status

Implemented:

- Tauri + React desktop shell.
- Python sidecar HTTP API for audio, STT, LLM, settings, modes, sessions, and history.
- SenseVoice-Small local STT provider.
- OpenAI-compatible LLM provider, suitable for DeepSeek-compatible testing.
- Rule-based fallback compiler for local development without an API key.
- Session-aware prompt refinement.
- Local SQLite history.
- Global show/hide shortcut through Tauri.

Not yet implemented:

- Packaged Python sidecar binary for end-user Tauri release builds.
- Encrypted API key storage.
- Full cross-platform release polish.

## Quick Start

```powershell
conda activate aura
cd D:\Aura1
python -m pip install -r requirements.txt
npm install
npm run tauri:dev
```

For DeepSeek-compatible testing:

```powershell
$env:DEEPSEEK_API_KEY="your_key"
npm run tauri:dev
```

Without an API key, Aura uses a local rule-based compiler so the UI and session flow can still be tested.

## Development

Run the sidecar directly:

```powershell
conda activate aura
python -m aura sidecar --host 127.0.0.1 --port 8765
```

Run the React shell in a browser:

```powershell
npm run dev
```

Run the full desktop app:

```powershell
npm run tauri:dev
```

Useful entry points:

- [aura/sidecar.py](aura/sidecar.py): local HTTP sidecar used by Tauri.
- [src/App.tsx](src/App.tsx): Tauri/React desktop interface.
- [src-tauri/src/main.rs](src-tauri/src/main.rs): Tauri shell and Python sidecar launcher.
- [aura/recorder.py](aura/recorder.py): PyAudio recording module.
- [aura/providers/stt/sensevoice_small.py](aura/providers/stt/sensevoice_small.py): SenseVoice-Small provider.
- [aura/providers/llm/openai_compatible.py](aura/providers/llm/openai_compatible.py): OpenAI-compatible LLM provider.
- [modes](modes): prompt compiler modes.

## Shortcuts

- `Ctrl+Shift+Space`: show or hide Aura.
- `Space`: hold to record when the main window is focused.
- `Ctrl+N`: new session.
- `Ctrl+Up` / `Ctrl+Down`: switch mode.
- `Esc`: hide window.

## Configuration

Aura stores local configuration and history in:

```text
%APPDATA%/Aura/config.json
%APPDATA%/Aura/history.sqlite
```

If an older `%APPDATA%/AgentVoice/config.json` exists, Aura migrates it into the new config directory.

The default model cache remains inside the project:

```text
models/
```

## Verification

```powershell
pytest
npm run build
cargo check --manifest-path src-tauri\Cargo.toml
```
