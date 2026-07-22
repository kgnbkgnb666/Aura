<div align="center">

[English](README.md) · [简体中文](README_zh-CN.md) · [日本語](README_ja.md)

# ✨ Aura

### アイデアを声に出し、AI エージェントが実行できる明確なタスクへ

🎙️ ローカル音声認識 · 🧠 LLM によるタスク整理 · 🧩 Skill マッチング · 📋 エージェントへそのまま貼り付け

**プロンプトの型を覚える必要はありません。考えを話せば、Aura が問いを明確にします。**

役に立ったら、ぜひ ⭐ Star で応援してください。

</div>

---

## 👀 Aura を 30 秒で理解する

```text
曖昧なアイデア → Space を押して話す → ローカル STT → LLM が整理
                → 目的・制約・完了条件を補う → Agent に貼り付ける
```

Aura は単なるチャットボットではありません。人と AI エージェントの間にある「表現のレイヤー」です。散らばった発話を、明確で実行可能・検証可能なタスクに変換します。

## 🌌 Aura が存在する理由

Codex、Claude Code、Cursor を開いても、最初から目的・範囲・手順・完了条件がすべて言葉になるわけではありません。機能修正、バグ修正、まだ形になっていない思いつきでも同じです。

それは表現力の問題ではありません。**人の思考は、曖昧な状態から明確になるものです。** 話し、見直し、補足し、修正する過程でアイデアは形になります。Aura は最初の思いつきを受け止め、エージェントが理解できる形へ照らし出します。✨

```text
曖昧な考え → 話す → Aura が最初の明確な表現を作る → 修正する → Agent が実行する
```

### 🎙️ なぜ音声なのか？

考えが曖昧な時、入力は「正しい文章」を早く求めすぎて思考を止めがちです。話すなら、ためらう、補足する、考えを変えることができます。LLM はその不完全な手がかりから意図と構造を見つけます。

| あなた | Aura | Agent |
| --- | --- | --- |
| 🎤 形式を気にせず自然に話す | 🧩 目的・文脈・制約・重要点を理解する | 🤖 実行可能なタスクを受け取る |
| ✍️ 初稿を確認して修正する | 🧠 表現をより正確に整理する | 🚀 実際に仕事を進める |

### 🚀 Agent 時代の差は「どう聞くか」

反復作業を Agent が担うほど、重要なのは本当の問題を明確に伝える力です。Aura は、入力欄に合わせる方法ではなく、**目的・判断・創造**に集中できるようにします。

### 🛠️ 眠っている Skills を再び使う

インストールした Skills は必要な時に忘れがちです。Aura は Skill の説明をスキャンし、現在の意図に合う能力を生成タスクへ入れます。

```text
「この調査をプレゼンにしたい」→ プレゼン用 Skill を選択 → Agent 向けの依頼を生成
```

Skill の名前を全部覚える必要はありません。達成したいことを覚えていれば十分です。🧩

## 🌟 主な機能

- 🎙️ `Space` を押して録音、離すと文字起こしと整理を開始。
- 🔒 SenseVoice Small / Whisper Large V3 によるローカル音声認識。
- 🧠 標準の DeepSeek または OpenAI 互換 LLM エンドポイント。
- 🎯 行動・意思決定・創作の 3 モード。
- 🧩 ローカル Skills のスキャンと自動マッチング。
- 🔁 会話文脈の保持と要件の統合出力。
- 📋 Codex、Claude Code、Cursor などへ結果をコピー。

## 🚀 クイックスタート

### 必要な環境

- Windows 10 / 11、Python 3.10 または 3.11、Node.js 20.19+、Rust stable、Visual Studio C++ Build Tools

```powershell
git clone https://github.com/kgnbkgnb666/Aura.git
cd Aura
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm ci
npm run tauri:dev
```

初回起動時に選択した音声モデルを準備します。その後 `Space` を押して話してください。🚀

| ショートカット | 操作 |
| --- | --- |
| `Ctrl + Shift + Space` | Aura を前面に表示 |
| `Space` を長押し | 録音、離すと処理 |
| `Ctrl + N` | 新しいセッション |
| `Esc` | Aura を隠す |

## 🧠 なぜ DeepSeek を標準で勧めるのか？

Aura の中心は、音声の意図・目的・制約を理解し、テキストを構造化することです。毎回最高額のモデルを必要とする処理ではありません。DeepSeek はこの用途で十分以上の性能を持ちます。

- 💰 **低コスト**：日常的に何度も使いやすい。
- 🧱 **安定**：OpenAI 互換 API とストリーミングに対応。
- ⚡ **実用的に高速**：音声からタスクへの体験に適した速度。
- 🛠️ **設定が簡単**：`設定 → LLM` で API Key を入力するだけ。

標準は思考モードをオフにした `deepseek-v4-flash` です。難しいタスクでは `deepseek-v4-pro` または思考モードを選べます。

> 🔐 開発環境では Key はプロジェクト直下の `config.local.json` に保存されます。Windows のパッケージ版では `%LOCALAPPDATA%\Aura\config.local.json` に保存され、インストーラーには含まれません。いずれも平文のため共有・アップロードはしないでください。

### 🔌 カスタム LLM 接続

`設定 → LLM → 自定义接口` で OpenAI 互換の Base URL、モデル ID、必要なら API Key を入力します。Ollama や vLLM のローカルサービスは Key を空欄にできます。

| サービス | エンドポイント例 | モデル例 |
| --- | --- | --- |
| Ollama | `http://127.0.0.1:11434/v1` | `qwen3:8b` |
| vLLM | `http://127.0.0.1:8000/v1` | 起動時に指定したモデル ID |
| Gateway | `https://your-gateway.example/v1` | Gateway が提供するモデル ID |

OpenAI Chat Completions 互換なら、クラウド、自前ホスト、ローカルのサービスを利用できます。LLM が未設定の場合は、ローカルのルールベース整理器にフォールバックします。

## 🎧 STT モデル：選択・ダウンロード・拡張

| モデル | 長所 | 注意点 | おすすめ |
| --- | --- | --- | --- |
| **SenseVoice Small** | ⚡ 軽量・高速・中国語に強い | 多言語・騒音下では精度上限が低い | 日常的な中国語音声入力 |
| **Whisper Large V3** | 🎯 高精度・多言語対応 | 約 3 GB、CPU では遅い | 多言語・精度優先 |

`設定 → 語音` で選択し、「モデルを事前読み込み」で先にダウンロードできます。キャッシュの親フォルダーも同じ画面で変更できます。

- SenseVoice は ModelScope 経由で `models/modelscope/` に保存されます。
- Whisper は `models/huggingface/` に保存されます。
- CUDA 12 / cuDNN 9 が完全なら NVIDIA GPU、そうでなければ CPU `int8` を使用します。
- Whisper のダウンロードがネットワークエラーで失敗すると SenseVoice Small に切り替わります。

### 事前ダウンロード

```powershell
$env:MODELSCOPE_CACHE = "$PWD\models\modelscope"
modelscope download --model iic/SenseVoiceSmall
modelscope download --model iic/speech_fsmn_vad_zh-cn-16k-common-pytorch
hf download Systran/faster-whisper-large-v3 --cache-dir models/huggingface
```

必要な CLI は次で導入できます。

```powershell
python -m pip install -U modelscope huggingface_hub
```

### 独自 STT Provider を追加する

UI には現在 2 Provider があり、任意のモデルファイルを自動で読み込む機能はありません。追加する場合は次を実装します。

1. `aura/providers/stt/` に `name`、`load_model()`、`transcribe()`、状態プロパティを持つ Provider を追加。
2. `aura/providers/stt/__init__.py`、`aura/config.py`、`AuraService._build_transcriber()` に登録。
3. `src/App.tsx` と `src/i18n.ts` に選択肢と説明を追加。

`SenseVoiceSmallTranscriber` と `WhisperLargeV3Transcriber` を参照してください。

## 🎯 モードの選び方と編集

| モード | 選ぶ場面 | 出力の重点 |
| --- | --- | --- |
| ⚡ **行動** | コード、文書、調査、デバッグを完了したい | 範囲、制約、成果物、受け入れ条件 |
| 🧭 **意思決定** | 方向性、優先順位、トレードオフを選びたい | 事実と仮定、選択肢、リスク、推奨 |
| 🎨 **創作** | コピー、命名、脚本、コンセプトを考えたい | 読者、表現、創作の余地、成果物 |

「終わらせる」なら行動、「正しく選ぶ」なら意思決定、「新しく作る」なら創作を選びます。`設定 → モード` で有効化、並び替え、追加、編集が可能です。公式モードを編集するとローカルのプライベートコピーが作られます。

公式モードは `modes/official/*.yaml`、自作モードと状態は `.aura-local/modes/` に保存されます。少なくとも 1 つのモードを有効にしてください。

## 🏗️ 技術アーキテクチャ

![Aura technical architecture](docs/assets/aura-architecture.svg)

編集可能な元ファイル：[docs/assets/aura-architecture.drawio](docs/assets/aura-architecture.drawio)

| レイヤー | 技術 / 役割 |
| --- | --- |
| デスクトップ UI | Tauri 2 + React 18 + TypeScript：録音、設定、結果編集 |
| ローカルサービス | Python Sidecar + Local HTTP API：録音、STT、セッション、ストリーム処理 |
| 音声 | PyAudio、FunASR / SenseVoice、faster-whisper / CTranslate2 |
| コンパイラ | モード、会話文脈、Skills を DeepSeek / カスタム LLM へ渡す |
| ローカルデータ | 開発時はプロジェクト直下、Windows パッケージ版では `%LOCALAPPDATA%\Aura` に設定、SQLite、プライベートモード、モデルキャッシュを保存 |

## 📈 Star の推移

[![Star History Chart](https://api.star-history.com/svg?repos=kgnbkgnb666/Aura&type=Date)](https://star-history.com/#kgnbkgnb666/Aura&Date)

## 🛠️ 開発

> Windows で更新をインストールする前に Aura を終了してください。インストーラーも `aura.exe` と `aura-sidecar.exe` を自動終了し、使用中のファイルを解放します。

### バージョン管理

`package.json` を唯一のバージョンソースとして、次の 1 コマンドで全ファイルを同期できます。

```powershell
npm run release:version -- 0.1.3
```

`package.json`、`package-lock.json`、`src-tauri/tauri.conf.json`、`src-tauri/Cargo.toml` を更新します。`npm run tauri:build` 実行時にも Tauri と Cargo のバージョンを自動同期します。

```powershell
npm run build
python -m pytest
npm run tauri:dev
npm run build:sidecar
```

[CONTRIBUTING.md](CONTRIBUTING.md) を確認し、モード、STT Provider、LLM 互換性、Skills、体験改善に参加してください。

<div align="center">

### 🌟 曖昧な考えを、実行できる次の一歩へ

Aura が役に立ったら、⭐ Star をお願いします。ありがとうございます！❤️

---

### 💬 Aura 技術交流グループ（QQ）

QQ 技術交流グループへようこそ。礼儀正しい議論で共に成長しましょう！

<img src="qq技术交流群.jpg" alt="QQ 技術交流グループ" width="360" />

</div>
