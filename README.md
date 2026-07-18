<div align="center">

# Aura

### 把零散的口述想法，变成 AI Agent 真正好用的提示词

本地语音识别 · 上下文续写 · 流式整理 · 一键复制

![Tauri](https://img.shields.io/badge/Tauri-2-24C8DB?logo=tauri&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/平台-Windows-0078D4?logo=windows)
![Status](https://img.shields.io/badge/状态-早期预览-orange)

</div>

---

Aura 是一款面向 Codex、Claude Code、Cursor、ChatGPT 等 AI 工具的桌面语音工作台。

按住空格说出需求，Aura 会在本地完成语音转写，再把口语中的重复、跳跃和模糊表达整理成结构清晰、可直接交给 AI Agent 执行的提示词。原始转写始终可见，整理结果会流式输出；开启自动复制后，说完即可粘贴使用。

> 当前版本处于早期预览阶段，优先支持 Windows，适合开发者体验与共同建设，暂不建议用于关键生产流程。

## 为什么做 Aura？

键盘适合精确编辑，语音更适合快速倾倒思路。问题在于，未经整理的口述通常充满停顿、补充和上下文跳跃，直接交给 AI 往往得不到稳定结果。

Aura 把这段流程压缩成四步：

```text
按住空格说话 → SenseVoice 本地转写 → LLM 按模式整理 → 自动复制结果
```

它不试图替代你的 AI 工具，只负责把“脑中的需求”更顺畅地送进去。

## 核心能力

- **本地语音识别**：基于 SenseVoice-Small，音频转写默认在本机完成。
- **Agent 友好的提示词整理**：去除口语冗余，并补足目标、范围、约束与验收条件。
- **上下文会话**：连续口述可以继承同一会话中的历史信息。
- **流式反馈**：先展示原始转写，再持续输出整理结果，不必盯着空白界面等待。
- **可编辑模式**：通过 YAML 定义标准、专业或自己的提示词编译模式。
- **兼容多种模型服务**：内置 DeepSeek 配置，并支持 OpenAI-compatible 接口、Ollama、vLLM 等服务。
- **无 API Key 也能体验**：自动退回本地规则整理器，方便验证完整交互流程。
- **桌面快捷操作**：全局唤起、按住说话、新建会话、切换模式与自动复制。
- **本地历史记录**：设置与会话数据保存在本机，支持清理。

## 快速开始

### 环境要求

- Windows 10/11（当前主要支持平台）
- Python 3.10 或 3.11
- Node.js 20.19+ 或 22.12+
- Rust stable 与 Visual Studio C++ Build Tools（运行 Tauri 桌面端时需要）
- 可用的麦克风

### 从源码运行

```powershell
git clone <你的仓库地址>
cd Aura

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

npm ci
npm run tauri:dev
```

首次使用时，SenseVoice 模型可能需要下载并初始化，请预留数分钟和足够磁盘空间。启动后进入“LLM 设置”，填写服务地址、模型和 API Key；不填写 API Key 时会使用本地规则整理器。

## 快捷键

| 快捷键 | 功能 |
| --- | --- |
| `Ctrl + Shift + Space` | 显示 / 隐藏 Aura |
| 按住 `Space` | 录音，松开后开始处理 |
| `Ctrl + N` | 新建会话 |
| `Ctrl + ↑` / `Ctrl + ↓` | 切换提示词模式 |
| `Esc` | 隐藏窗口 |

> `Space` 录音仅在 Aura 窗口获得焦点时生效，避免影响其他应用中的正常输入。

## 技术架构

| 层级 | 技术 | 职责 |
| --- | --- | --- |
| 桌面外壳 | Tauri 2 / Rust | 窗口、托盘、快捷键、开机启动与 sidecar 生命周期 |
| 用户界面 | React / TypeScript / Vite | 录音交互、会话、设置、状态与流式结果展示 |
| 本地服务 | Python sidecar | HTTP API、任务调度、配置与业务编排 |
| 语音识别 | SenseVoice-Small / FunASR | 本地音频转写与模型缓存 |
| 提示词整理 | Provider 抽象层 | DeepSeek / OpenAI-compatible / 本地规则回退 |
| 数据 | JSON / SQLite / YAML | 设置、历史会话与提示词模式 |

```text
React WebView
    │  带会话令牌的 localhost HTTP
    ▼
Python sidecar
    ├── AudioRecorder ──► SenseVoice-Small
    ├── PromptCompiler ─► LLM Provider
    ├── ModeRegistry  ──► YAML 模式
    └── HistoryStore  ──► SQLite
```

核心扩展点：

- `aura/providers/stt/`：新增语音识别 Provider。
- `aura/providers/llm/`：新增模型服务 Provider。
- `modes/`：新增或修改提示词整理模式。
- `aura/service.py`：业务编排入口。
- `aura/sidecar.py`：桌面端与 Python 核心之间的 API 边界。

## 本地数据与隐私

Aura 默认使用以下项目本地路径：

```text
config.local.json            # 应用设置；当前包含明文 API Key
.aura-local/history.sqlite   # 会话历史
.aura-local/modes/*.yaml     # 用户自定义模式
models/                      # 本地模型缓存
```

这些路径已经加入 `.gitignore`，不会被正常提交。录音临时文件会在处理结束后删除。sidecar 只监听 `127.0.0.1`，桌面端启动时会生成随机会话令牌，所有业务接口都需要令牌，并限制可跨域访问的 WebView 来源。

请注意：**API Key 目前仍以明文保存在 `config.local.json` 中**。文件会尽量设置为仅当前用户可读，但这不等同于系统级加密。不要上传或分享该文件；后续版本计划接入 Windows Credential Manager、macOS Keychain 和 Linux Secret Service。

云端整理模式会把转写文本发送给你配置的 LLM 服务；本地规则整理器不会发送文本。具体数据政策以对应模型服务商为准。

## 开发与验证

只启动 Python sidecar（终端会打印本次会话令牌）：

```powershell
python -m aura.sidecar --host 127.0.0.1 --port 8765
```

只启动前端：

```powershell
npm run dev
```

运行完整桌面端：

```powershell
npm run tauri:dev
```

执行项目检查：

```powershell
python -m pytest -q
npm run build
cargo check --locked --manifest-path src-tauri\Cargo.toml
npm audit
```

### 构建 Windows 安装包

```powershell
python -m pip install -r requirements-build.txt
npm ci
npm run tauri:build
```

构建过程会先将 Python sidecar 打包为独立可执行文件，再生成 NSIS 安装包。由于本地语音模型运行时依赖较多，sidecar 体积目前较大，后续仍有明显的瘦身空间。

## 路线图

- [ ] 将 `App.tsx` 拆分为独立功能模块并补齐前端测试
- [ ] 使用系统凭据库安全保存 API Key
- [ ] 优化 sidecar 与模型依赖的安装包体积
- [ ] 增加 macOS / Linux 的构建与设备兼容验证
- [ ] 提供 GitHub Releases 与自动化发布流水线
- [ ] 丰富 STT、LLM Provider 和社区提示词模式
- [ ] 完善无障碍、国际化与错误恢复体验

## 参与贡献

欢迎提交 Issue、模式配置、Provider、文档与代码改进。开始前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)；安全问题请不要公开披露，处理方式见 [SECURITY.md](SECURITY.md)。

这个项目最适合从以下方向参与：

- 分享真实语音输入场景和失败案例
- 贡献新的 `modes/*.yaml`
- 接入新的本地或云端 STT / LLM Provider
- 改进 Windows 安装体验和跨平台兼容性
- 补充自动化测试、性能基准与隐私保护

## 开源许可

仓库目前尚未添加正式许可证。首次公开发布前，维护者需要选择并提交 `LICENSE` 文件；在此之前，默认著作权规则仍然适用，其他人没有自动获得复制、修改和分发代码的许可。

---

<div align="center">

如果 Aura 让你少敲一点键盘、让 AI 更懂你的需求，欢迎 Star、试用并分享反馈。

</div>
