<div align="center">

[简体中文](README.md) · [English](README_EN.md) · [日本語](README_ja.md)

# ✨ Aura

### 说出想法，让 AI 帮你整理成可执行的任务

🎙️ 本地语音转文字 · 🧠 LLM 智能整理 · 🧩 Skill 自动匹配 · 📋 一键粘贴到 AI Agent

[![Tauri](https://img.shields.io/badge/Tauri-2-24C8DB?logo=tauri&logoColor=white)](https://tauri.app/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-22C55E)](LICENSE)

**不需要记住任何 Prompt 模板。想到什么说什么，Aura 帮你把它变成清晰的、可执行的 AI 任务。**

如果 Aura 对你有用，请给项目一个 ⭐ Star。

</div>

---

## 👀 30 秒了解 Aura

```text
模糊的想法 → 按住 Space 说话 → 本地语音转文字 → LLM 整理需求
           → 目标、约束、验收标准 → 粘贴到 AI Agent 执行
```

Aura 不是聊天机器人。它是你和 AI Agent 之间的**表达层**——保留你的真实意图，把零散的语音变成清晰、可执行、可验证的任务。

## 🌌 为什么需要 Aura

你打开 Codex、Claude Code 或 Cursor，光标在闪烁。你大概知道自己想要什么——修个 bug、改个功能、或者脑子里有个半成型的想法——但目标、范围、步骤和完成标准不会一下子全部浮现。

这不是沟通的失败。**人类的思维天然是从模糊到清晰的过程。** 好想法是在说出口、看见文字、反复修改、补充细节的过程中诞生的。Aura 的存在，就是为了接住你的第一个念头，然后帮你把它照亮。✨

```text
模糊的想法 → 说出来 → Aura 帮你整理成清晰的第一版 → 优化它 → AI Agent 执行
```

### 🎙️ 为什么用语音？

打字容易让人过早追求「完美的句子」。说话允许你犹豫、补充上下文、改变主意、从感觉出发——而大语言模型恰好擅长从这些不完整的线索中找出意图和结构。

| 你 | Aura | AI Agent |
| --- | --- | --- |
| 🎤 自然说话，无需格式 | 🧩 提炼目标、上下文、约束、优先级 | 🤖 收到可执行的任务 |
| ✍️ 检查和修改初稿 | 🧠 持续让需求更精确 | 🚀 执行工作 |

### 🚀 在 AI Agent 时代，会提问才是优势

当 Agent 承担越来越多的重复性工作时，区分高下的关键越来越在于：**我们能不能清楚地表达真正的问题**。Aura 让你专注于**目标、判断和创造力**，而不是学习如何讨好一个输入框。

### 🛠️ 唤醒沉睡的 Skill

Skill 容易安装、容易遗忘。Aura 会扫描 Skill 的描述，匹配当前的意图，并把相关的能力自动写入生成的任务中。

```text
「把这个研究做成演示文稿」→ 匹配到演示 Skill → 生成 Agent 可执行的任务
```

你不需要记住每个 Skill 的名字——只要记住你想完成什么。🧩

---

## 📅 更新日志

> 格式参考 [GitHub 风格](https://docs.github.com/zh/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates)

### 2026-07-25

**✨ 新增：问题清晰度**

- 每次语音转录后，AI 自动评估问题的清晰程度，以百分比环形饼状图展示在「原始转录」栏（绿/黄/红三色对应高/中/低清晰度）
- 清晰度评估结果持久化保存到 SQLite，同一段转录每次加载显示一致，不会反复变化
- 新增「补充信息」功能——AI 根据当前转录和历史对话，自动生成 2~4 个澄清性问题，附带可选答案；支持单选/多选（AI 自动判断），也可自定义输入
- 补充信息问题按转录内容缓存，同一段话重复打开显示相同问题，避免无意义变化；底部提供「刷新问题」按钮可手动换一批
- 复制按钮新增淡出动画，「已复制」状态不再突然消失

### 2026-07-22

**🔧 修复**

- 解决打包 bug
- LLM 设置新增「测试连接」按钮，输入完 API Key 可一键验证

**📝 文档**

- README 新增 QQ 技术交流群

### 2026-07-21

**🔧 修复**

- 修复 STT 模型加载失败时的自动回退：Whisper 下载失败自动切换至 SenseVoice Small 并持久化配置
- 多项打包相关 bug 修复

**📝 文档**

- 重新整理 README，更清晰地说明项目定位和使用方式

### 2026-07-20

**✨ 新增**

- 三种官方模式（行动 / 决策 / 创作），支持自定义模式和本地私人副本
- 界面主题切换（晨光 / 静夜），支持简体中文 / 繁體中文 / English / 日本語
- 语音识别模型切换更方便
- 修复 LLM API Key 保存逻辑

### 2026-07-18 ~ 07-19

**✨ 新增**

- 设置页面：语音模型选择（SenseVoice Small / Whisper Large V3）
- 界面主题美化
- Windows 安装包支持（NSIS）
- 系统托盘、开机自启动
- 程序退出流程和日志系统优化
- 预发布版本

### 2026-07-16 ~ 07-17

**✨ 新增**

- 冷启动优化：启动页展示模型加载进度条
- 编辑模式：可手动编辑转录和编译结果，修改后重新编译
- 本地 Skill 扫描和匹配
- 历史会话：加载、删除、清空

### 2026-07-10 ~ 07-12

**🎉 项目诞生**

- MVP 1.0 版本：语音录入 → 本地 STT 转录 → LLM 整理 → 复制结果
- 技能（Skill）配置页
- 手动编辑转录和编译结果的初步支持
- 初代框架搭建

---

## 🌟 功能特性

- 🎙️ 按住 `Space` 录音，松手自动转录和整理
- 🔒 本地语音识别：SenseVoice Small 或 Whisper Large V3
- 🧠 默认 DeepSeek，也支持任何 OpenAI 兼容的 LLM 接口
- 🎯 三种模式：行动 / 决策 / 创作，各有专属 Prompt 策略
- 🧩 本地 Skill 扫描匹配
- 📊 **问题清晰度**：AI 评估每次提问的清晰度，饼状图可视化
- 💡 **补充信息**：AI 生成澄清问题，选择题式引导用户补充细节
- 🔁 会话上下文保持，支持合并需求输出
- 📋 一键复制整理结果，粘贴到 Codex、Claude Code、Cursor 等 Agent

## 🚀 快速开始

### 环境要求

- Windows 10 / 11
- Python 3.10 或 3.11
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

首次启动会自动下载语音模型。之后按住 `Space`，说出你的第一个想法。🚀

| 快捷键 | 功能 |
| --- | --- |
| `Ctrl + Shift + Space` | 唤起 Aura |
| 按住 `Space` | 录音；松手自动处理 |
| `Ctrl + N` | 新建会话 |
| `Esc` | 隐藏 Aura |

## 🧠 为什么默认推荐 DeepSeek

Aura 主要做的是理解口语、提取目标和约束、重新组织文字，不需要每次都调用昂贵的前沿模型。对于这个场景，DeepSeek 绰绰有余：

- 💰 **实惠**，适合日常高频使用
- 🧱 **稳定**的 OpenAI 兼容 API 和流式工作流
- ⚡ **够快**，满足语音到任务的处理体验
- 🛠️ **简单**：在 `设置 → LLM` 中填入 DeepSeek API Key 即可

默认为 `deepseek-v4-flash`（思考模式关闭）。复杂任务可选 `deepseek-v4-pro` 或开启思考模式。

> 🔐 开发环境下 Key 存储在项目根目录的 `config.local.json`；打包后的 Windows 应用中存储在 `%LOCALAPPDATA%\Aura\config.local.json`——不会打包进安装程序。均为明文存储，请勿上传或分享。

### 🔌 使用自定义 LLM

打开 `设置 → LLM → 自定义接口`，填入 OpenAI 兼容的 Base URL、模型 ID 和 API Key（本地服务可留空）。

| 服务 | 端点示例 | 模型示例 |
| --- | --- | --- |
| Ollama | `http://127.0.0.1:11434/v1` | `qwen3:8b` |
| vLLM | `http://127.0.0.1:8000/v1` | 你部署的模型 ID |
| 网关 | `https://your-gateway.example/v1` | 网关支持的模型 ID |

任何 OpenAI Chat Completions 兼容的服务都可以接入。没有 LLM 时，Aura 会使用本地规则引擎兜底。

## 🎧 语音模型：选择、下载、扩展

| 模型 | 优势 | 代价 | 适合 |
| --- | --- | --- | --- |
| **SenseVoice Small** | ⚡ 轻量快速，中文支持好 | 多语言和噪音场景稍弱 | 日常中文语音输入 |
| **Whisper Large V3** | 🎯 精度更高，多语言支持 | 约 3 GB；CPU 上较慢 | 多语言或精度优先 |

在 `设置 → 语音` 中选择模型，使用「预加载模型」提前下载初始化。

- SenseVoice 通过 ModelScope 下载到 `models/modelscope/`
- Whisper 下载到 `models/huggingface/`
- Whisper 有完整 CUDA 12 / cuDNN 9 环境时使用 GPU，否则回退 CPU `int8`
- Whisper 下载失败时自动切换至 SenseVoice Small

### 提前下载模型

```powershell
# SenseVoice Small + VAD
$env:MODELSCOPE_CACHE = "$PWD\models\modelscope"
modelscope download --model iic/SenseVoiceSmall
modelscope download --model iic/speech_fsmn_vad_zh-cn-16k-common-pytorch

# Whisper Large V3 (faster-whisper 格式)
hf download Systran/faster-whisper-large-v3 --cache-dir models/huggingface
```

如需安装 CLI：

```powershell
python -m pip install -U modelscope huggingface_hub
```

## 🎯 模式：选择与定制

| 模式 | 适用场景 | 输出侧重 |
| --- | --- | --- |
| ⚡ **行动** | 明确要做什么：编码、文档、调试、数据 | 范围、约束、交付物、验收标准 |
| 🧭 **决策** | 需要选择：权衡、优先级、方向 | 事实 vs 假设、选项、风险、建议 |
| 🎨 **创作** | 需要探索：文案、命名、脚本、概念 | 受众、调性、创作空间、可直接使用的成果 |

一句话：**行动**用来完成任务，**决策**用来做出选择，**创作**用来产出独特内容。🤝

在 `设置 → 模式` 中可以启用、禁用、排序、添加模式。编辑官方模式会创建本地私人副本，不会覆盖仓库中的定义。

## 🏗️ 架构

![Aura 技术架构](docs/assets/aura-architecture.svg)

可编辑源文件：[docs/assets/aura-architecture.drawio](docs/assets/aura-architecture.drawio)

| 层 | 技术 / 职责 |
| --- | --- |
| 桌面 UI | Tauri 2 + React 18 + TypeScript：录音、设置、结果编辑 |
| 本地服务 | Python sidecar + 本地 HTTP API：录音、转写、会话、流式输出 |
| 语音 | PyAudio、FunASR / SenseVoice、faster-whisper / CTranslate2 |
| 编译 | 模式 + 会话上下文 + Skill 发送给 DeepSeek 或自定义 LLM |
| 本地数据 | 开发环境：项目根目录。打包应用：`%LOCALAPPDATA%\Aura`（配置、SQLite 历史、私有模式、模型缓存） |

## 📈 Star 历史

[![Star History Chart](https://api.star-history.com/svg?repos=kgnbkgnb666/Aura&type=Date)](https://star-history.com/#kgnbkgnb666/Aura&Date)

## 🛠️ 开发

> Windows 上安装更新前请关闭 Aura。安装程序也会自动关闭 `aura.exe` 和 `aura-sidecar.exe` 以释放被锁定的文件。

### 版本管理

`package.json` 是唯一的版本号来源。一行命令同步所有包的版本：

```powershell
npm run release:version -- 0.1.3
```

这会同步 `package.json`、`package-lock.json`、`src-tauri/tauri.conf.json` 和 `src-tauri/Cargo.toml`。

```powershell
npm run build
python -m pytest
npm run tauri:dev
npm run build:sidecar
```

贡献方式见 [CONTRIBUTING.md](CONTRIBUTING.md)。

<div align="center">

### 🌟 让每一个模糊的想法，都变成可执行的下一步

如果 Aura 帮助了你，请给它一个 ⭐ Star。谢谢！❤️

[反馈问题](https://github.com/kgnbkgnb666/Aura/issues) · [参与贡献](CONTRIBUTING.md) · [MIT License](LICENSE)

---

### 💬 Aura 技术交流群

欢迎加入 QQ 技术交流群，文明讨论，共同进步！

<img src="qq技术交流群.jpg" alt="QQ 技术交流群" width="360" />

</div>
