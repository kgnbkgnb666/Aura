<div align="center">

[English](README.md) · [简体中文](README_zh-CN.md) · [日本語](README_ja.md)

# ✨ Aura

### Speak an idea. Turn it into a clear task your AI agent can execute.

🎙️ Local speech-to-text · 🧠 LLM-powered task shaping · 🧩 Skill matching · 📋 Ready to paste into an agent

[![Tauri](https://img.shields.io/badge/Tauri-2-24C8DB?logo=tauri&logoColor=white)](https://tauri.app/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-22C55E)](LICENSE)

**No prompt templates to memorize. Think out loud; Aura helps you ask clearly.**

If Aura is useful to you, please give the project a ⭐ Star.

</div>

---

## 👀 Aura in 30 seconds

```text
Rough idea → hold Space and speak → local STT → LLM shapes the request
          → goals, constraints, and acceptance criteria → paste into your agent
```

Aura is not another chatbot. It is an expression layer between you and an AI agent: it preserves your intent and turns scattered speech into a clear, actionable, verifiable task.

## 🌌 Why Aura exists

You open Codex, Claude Code, or Cursor. The cursor blinks. You roughly know what you need—fix a bug, change a feature, or capture a half-formed idea—but the goal, scope, steps, and definition of done do not arrive all at once.

That is not a communication failure. **Human thinking naturally moves from vague to clear.** Good ideas become real when we say them, see them, revise them, and add detail. Aura exists to catch that first thought and help illuminate it. ✨

```text
Vague thought → say it → Aura creates a first clear version → refine it → an agent can execute it
```

### 🎙️ Why voice?

Typing can make us chase the “perfect sentence” too early. Speaking lets you hesitate, add context, change your mind, and start from a feeling; language models are good at finding intent and structure in those incomplete clues.

| You | Aura | Your agent |
| --- | --- | --- |
| 🎤 Speak naturally—no format required | 🧩 Finds goals, context, constraints, and priorities | 🤖 Receives an actionable task |
| ✍️ Review and revise the first draft | 🧠 Keeps making the request more precise | 🚀 Does the work |

### 🚀 In the agent era, the advantage is asking well

As agents take on repetitive work, the differentiator is increasingly whether we can state the real problem clearly. Aura lets people focus on **goals, judgment, and creativity** instead of learning how to please an input box.

### 🛠️ Wake up dormant Skills

Skills are easy to install and easy to forget. Aura scans their descriptions, matches the current intent, and includes the relevant capability in the generated task.

```text
“Turn this research into a presentation” → match a presentation Skill → create an agent-ready brief
```

You do not need to remember every Skill name—remember what you want to accomplish. 🧩

## 🌟 What it does

- 🎙️ Hold `Space` to record; release to transcribe and organize.
- 🔒 Run speech recognition locally with SenseVoice Small or Whisper Large V3.
- 🧠 Use the default DeepSeek setup or any OpenAI-compatible LLM endpoint.
- 🎯 Choose Action, Decision, or Creative mode for task-specific prompting.
- 🧩 Scan and match local Skills.
- 🔁 Keep conversational context and optionally merge requirements across turns.
- 📋 Copy the finished brief into Codex, Claude Code, Cursor, or another agent.

## 🚀 Quick start

### Requirements

- Windows 10 / 11
- Python 3.10 or 3.11
- Node.js 20.19+
- Rust stable
- Visual Studio C++ Build Tools

```powershell
git clone https://github.com/kgnbkgnb666/Aura.git
cd Aura

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

npm ci
npm run tauri:dev
```

On first launch Aura prepares the selected local speech model. Then hold `Space` and say your first idea. 🚀

| Shortcut | Action |
| --- | --- |
| `Ctrl + Shift + Space` | Bring Aura to the front |
| Hold `Space` | Record; release to process |
| `Ctrl + N` | New session |
| `Esc` | Hide Aura |

## 🧠 Why DeepSeek is the default recommendation

Aura mainly needs to understand spoken language, extract goals and constraints, and reshape text. It does not require an expensive frontier model for every request. For this workload, DeepSeek is more than capable:

- 💰 **Affordable** for frequent everyday use.
- 🧱 **Reliable** OpenAI-compatible API and streaming workflow.
- ⚡ **Fast enough** for the responsiveness expected from voice-to-task.
- 🛠️ **Simple**: enter a DeepSeek API key in `Settings → LLM`.

The default is `deepseek-v4-flash` with thinking disabled. For harder work, choose `deepseek-v4-pro` or enable thinking mode. Available model names depend on your DeepSeek account and API.

> 🔐 Keys are stored locally in `config.local.json`. It is ignored by Git, but it is plaintext—never upload or share it.

### 🔌 Use a custom LLM endpoint

Open `Settings → LLM → Custom endpoint`, then provide an OpenAI-compatible Base URL, the actual model ID, and an API key when required. Local services may leave the key blank.

| Service | Endpoint example | Model example |
| --- | --- | --- |
| Ollama | `http://127.0.0.1:11434/v1` | `qwen3:8b` |
| vLLM | `http://127.0.0.1:8000/v1` | Your served model ID |
| Gateway | `https://your-gateway.example/v1` | A gateway-supported model ID |

Any OpenAI Chat Completions-compatible hosted, self-hosted, or local service can be used. Without an available LLM, Aura falls back to a local rule-based organizer.

## 🎧 STT models: choose, download, extend

| Model | Strength | Trade-off | Best for |
| --- | --- | --- | --- |
| **SenseVoice Small** | ⚡ Lightweight, quick, strong Chinese support | Lower ceiling for multilingual/noisy audio | Everyday Chinese voice input |
| **Whisper Large V3** | 🎯 Higher accuracy and multilingual support | About 3 GB; slower on CPU | Multilingual or accuracy-first work |

Select a model in `Settings → Speech`. Use **Preload model** to download and initialize it ahead of time; the model-cache root is configurable on the same page.

- SenseVoice downloads through ModelScope into `models/modelscope/`.
- Whisper downloads into `models/huggingface/`.
- Whisper uses an NVIDIA GPU with a complete CUDA 12 / cuDNN 9 setup, otherwise CPU `int8`.
- If Whisper cannot download because of a network error, Aura falls back to SenseVoice Small.

### Download models in advance

```powershell
# SenseVoice Small + VAD
$env:MODELSCOPE_CACHE = "$PWD\models\modelscope"
modelscope download --model iic/SenseVoiceSmall
modelscope download --model iic/speech_fsmn_vad_zh-cn-16k-common-pytorch

# Whisper Large V3, faster-whisper conversion
hf download Systran/faster-whisper-large-v3 --cache-dir models/huggingface
```

Install the CLIs if needed:

```powershell
python -m pip install -U modelscope huggingface_hub
```

### Add your own STT provider

The UI currently ships with two providers; it does **not** import arbitrary model files automatically. To add a provider:

1. Add a provider under `aura/providers/stt/` with `name`, `load_model()`, `transcribe()`, `status`, `progress`, `last_error`, and `is_ready`.
2. Export it from `aura/providers/stt/__init__.py`.
3. Register its ID in `SUPPORTED_STT_PROVIDERS` in `aura/config.py`.
4. Map the ID in `AuraService._build_transcriber()`.
5. Add its selector option and copy in `src/App.tsx` and `src/i18n.ts`.

See `SenseVoiceSmallTranscriber` and `WhisperLargeV3Transcriber` as references.

## 🎯 Modes: choose and customize

| Mode | Choose it when | Output emphasizes |
| --- | --- | --- |
| ⚡ **Action** | You know what to do: code, docs, debugging, data | Scope, constraints, deliverables, acceptance criteria |
| 🧭 **Decision** | You need to choose: trade-offs, priorities, direction | Facts vs. assumptions, options, risks, recommendation |
| 🎨 **Creative** | You need to explore: copy, naming, scripts, concepts | Audience, voice, room to create, usable output |

In short: choose **Action** to finish work, **Decision** to choose well, and **Creative** to make something original. 🤝

In `Settings → Modes`, you can enable, disable, reorder, or add modes. Editing an official mode creates a local private copy instead of overwriting its repository definition. Official modes live in `modes/official/*.yaml`; custom modes, private copies, ordering, and enabled state live in `.aura-local/modes/`. Keep at least one mode enabled.

## 🏗️ Architecture

![Aura technical architecture](docs/assets/aura-architecture.svg)

Editable source: [docs/assets/aura-architecture.drawio](docs/assets/aura-architecture.drawio)

| Layer | Technology / responsibility |
| --- | --- |
| Desktop UI | Tauri 2 + React 18 + TypeScript for recording, settings, and result editing |
| Local service | Python sidecar + local HTTP API orchestrating recording, STT, sessions, and streaming |
| Speech | PyAudio, FunASR / SenseVoice, faster-whisper / CTranslate2 |
| Compiler | Modes, session context, and Skills sent to DeepSeek or a custom LLM |
| Local data | `config.local.json`, SQLite history, `.aura-local/`, model cache |

## 📈 Star history

> 📊 Star History requires a public GitHub repository. The currently configured repository URL is not publicly accessible, so the third-party chart returns HTTP 500 instead of an image. After publishing, replace `<OWNER>/<REPO>` below with the public repository slug.

```md
[![Star History Chart](https://api.star-history.com/svg?repos=<OWNER>/<REPO>&type=Date)](https://star-history.com/#<OWNER>/<REPO>&Date)
```

## 🛠️ Development

```powershell
npm run build
python -m pytest
npm run tauri:dev
npm run build:sidecar
```

See [CONTRIBUTING.md](CONTRIBUTING.md) to contribute modes, STT providers, LLM compatibility, Skills, or product improvements.

<div align="center">

### 🌟 Turn every vague thought into an executable next step

If Aura helps you, please give it a ⭐ Star. Thank you! ❤️

[Report an issue](https://github.com/kgnbkgnb666/Aura/issues) · [Contribute](CONTRIBUTING.md) · [MIT License](LICENSE)

</div>
