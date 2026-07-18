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

On first launch, open **LLM Settings** in Aura and enter the endpoint, model, and API Key.
Aura does not read API credentials from process or system environment variables. Without an API
Key, Aura uses a local rule-based compiler so the UI and session flow can still be tested.

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

Aura stores local configuration and history under the current project directory (or next to the
installed sidecar executable in a packaged build):

```text
config.local.json
.aura-local/history.sqlite
.aura-local/modes/*.yaml (only after built-in modes are customized)
```

These paths are explicitly ignored by Git. They are runtime-created files and are not listed in the
Tauri, PyInstaller, or NSIS bundle resources. `config.local.json` contains the API Key in plain text;
do not copy or share it. The application applies owner-only file permissions where the filesystem
supports them. For stronger protection in a future release, store secrets in Windows Credential
Manager/macOS Keychain/Linux Secret Service and keep only a credential reference in this file.

On the first launch after upgrading, Aura copies `%APPDATA%/Aura/config.json` and its history database
to these project-local paths. The old files are retained as a rollback copy.

Configuration trade-offs:

- Project-local files are easy to inspect, back up, and isolate between development checkouts.
- Separate checkouts/build installations have separate settings, which is useful for development,
  testing, and production isolation but requires configuring each one once.
- Plain-text local files can still be read by malware or another account with filesystem access;
  `.gitignore` prevents accidental commits but is not encryption.
- Uninstalling or replacing the entire installation directory can remove packaged-build settings;
  back up `config.local.json` and `.aura-local` before a clean reinstall.

The default model cache remains inside the project:

```text
models/
```

## Prompt modes

Aura ships with two modes:

- **标准模式** (`coding_agent`): combines the former concise and standard modes. It keeps simple
  requests short and direct, while adding structure only when a task is complex enough to need it.
- **专业模式** (`professional`): adds scope, boundaries, risk, execution, and verification detail for
  complex work. It is the default for new configurations.

Existing `concise` settings and history are mapped to `coding_agent`. Existing users who selected
standard or professional mode keep that selection after migration.

## LLM configuration

Aura defaults to DeepSeek `deepseek-v4-flash` with thinking mode explicitly disabled. Enter a
DeepSeek API Key in the LLM settings page to enable cloud compilation; without a key Aura keeps the
local rule-based fallback.

Users who prefer another service can choose **自定义接口** and enter an OpenAI-compatible endpoint,
model ID, and optional API Key. Self-hosted Ollama and vLLM endpoints can be used without a key.

## Verification

```powershell
pytest
npm run build
cargo check --manifest-path src-tauri\Cargo.toml
```
