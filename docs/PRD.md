# Aura PRD

## Product

Aura is a local-first desktop tool that turns spoken thoughts into agent-ready prompts.

The app is designed for Codex, Claude Code, Cursor, ChatGPT, and other agentic tools. It keeps the raw transcript visible, streams the cleaned AI result, and copies the final prompt when generation finishes.

## Current Architecture

- Desktop shell: Tauri.
- Frontend: React + TypeScript + Vite.
- Desktop integration: Rust/Tauri.
- Core voice and prompt logic: Python sidecar.
- Audio recording: PyAudio.
- STT: SenseVoice-Small through FunASR.
- LLM: OpenAI-compatible HTTP provider, with a local rule-based fallback.
- Data: local JSON settings and SQLite history.

## Core Flow

1. User opens Aura with `Ctrl+Shift+Space`.
2. User holds `Space` while the Aura window is focused.
3. Aura records audio locally.
4. On release, Aura starts a background processing job.
5. STT result is shown in the transcript panel as soon as recognition completes.
6. AI compilation streams into the result panel chunk by chunk.
7. The final AI result is copied automatically when enabled.
8. The current session keeps context for follow-up recordings.

## Shortcuts

- `Ctrl+Shift+Space`: show and focus Aura.
- `Space`: hold to record when the main window is focused.
- `Ctrl+N`: new session.
- `Esc`: hide Aura.

## UX Requirements

- The transcript panel must update before AI compilation is complete.
- The AI result panel must stream partial output.
- Auto-copy success must be visible with a green copied state.
- The close/minimize control must clearly hide the window, not quit unexpectedly.
- Settings must expose microphone, model cache, LLM configuration, history, and shortcuts.

## Performance Requirements

- The STT model should preload when the sidecar starts.
- Saving microphone-only settings must not rebuild or unload the STT model.
- Local ModelScope snapshots should be preferred when available.
- Audio temp files must be deleted after processing.

## Local Storage

```text
config.local.json
.aura-local/history.sqlite
.aura-local/modes/*.yaml (user overrides only)
models/
```

Runtime configuration, API credentials, microphone selection, skill settings, and storage paths are
saved in `config.local.json`. Session memory is saved in `.aura-local/history.sqlite`. Both locations
are project-local, ignored by Git, and excluded from package resource manifests. Aura does not use
environment variables as an API credential fallback.

Older `%APPDATA%/Aura/config.json` and history files are copied into the project-local locations on
first launch after an upgrade. Legacy `concise` and `professional` mode selections are mapped to
the unified `coding_agent` mode.

## Prompt Modes

- `coding_agent` / 标准模式: the single built-in mode. It adapts output depth to the task and
  combines clarity, execution boundaries, risk awareness, Skill matching, and verification.

## Verification

```powershell
pytest
npm run build
cargo check --manifest-path src-tauri\Cargo.toml
```
