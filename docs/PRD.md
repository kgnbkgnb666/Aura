# 语音 Agent Prompt 编译器 PRD

版本：v0.1  
日期：2026-07-07  
当前代号：AgentVoice / PromptVoice / VoiceBridge，正式名称待定  
目标平台：MVP 优先 Windows，本地技术验证已在 `voice/voice_test.py` 跑通  

## 1. 一句话定义

一个面向 AI coding agent 和桌面 AI 工具的本地优先语音输入工具：用户按快捷键唤起小浮窗，长按空格说出模糊想法，工具实时转录原始语音，再用 LLM 将其编译成结构清晰、可直接粘贴给 Codex、Claude Code、Cursor、ChatGPT 等 agent 的高质量提示词，并默认复制到剪贴板。

它不是泛用听写工具，而是“语音需求到 agent 指令”的编译层。

## 2. 背景与问题

### 2.1 用户观察

Codex、Claude Code、Cursor、ChatGPT、各类 CLI agent 的核心输入仍然是文本。对于复杂开发任务，用户经常需要描述背景、目标、约束、验收标准、已有思路和风险。打字输入很慢，尤其是：

- 想法还在形成中，需要边说边组织。
- 中文用户经常需要中英混杂表达技术名词。
- 需求不是一句命令，而是一段上下文。
- 用户希望 agent 执行前先理解“真正意图”，而不是照着口语逐字执行。

移动端或系统级语音输入能解决“输入速度”，但不能解决“表达质量”。普通听写把口语变成文字，AI agent 需要的是结构化、消歧义、带边界的任务说明。

### 2.2 核心痛点

1. 打字慢：开发者和知识工作者大量时间消耗在向 AI 描述任务。
2. 口语乱：用户自然说话包含停顿、改口、重复、顺序混乱、省略上下文。
3. agent 风险高：模糊需求可能被 agent 理解成错误操作，尤其是代码修改、文件操作、终端命令。
4. 泛用听写不懂 agent：竞品大多优化邮件、聊天、文档，不专注“把模糊需求编译成可执行但受控的 agent prompt”。
5. 上下文连续修改困难：用户常常第一遍说完后发现不完整，需要补充“刚才那个需求再加一点”，普通听写工具无法理解这是对上一版 prompt 的修订。
6. 隐私和可控性：开发需求可能包含公司代码、路径、内部 API、错误日志，用户更愿意本地优先。

## 3. 市场与竞品调研

### 3.1 结论

同类方向已经存在很多“AI dictation / AI voice typing”产品，所以单纯做语音转文字没有意义。项目有意义的前提是明确收窄为：

- 面向 AI agent 的 prompt 编译器。
- 原始转录和 AI 编译结果双轨显示，用户可追溯。
- 支持会话内增量修订，而不是每次生成孤立文本。
- 默认不直接执行 agent 动作，只复制或粘贴清晰 prompt，降低误操作风险。
- 本地优先、开源、可扩展 skill / mode / model provider。

### 3.2 典型竞品

| 产品 / 项目                       | 形态                             | 主要能力                                                          | 对我们的启发                         | 我们应避免重复                                                            |
| ----------------------------- | ------------------------------ | ------------------------------------------------------------- | ------------------------------ | ------------------------------------------------------------------ |
| Typeless                      | 跨平台 AI 语音键盘 / dictation        | 自然说话变成润色文本；支持跨应用、填充词移除、重复移除、自动格式化、个性化词典、不同 app 语气             | 小而全的“到处能写”体验很强；自动编辑口语是标配       | 不要做泛用“写邮件、聊天、文档”的同质化产品                                             |
| Wispr Flow                    | 跨应用语音输入                        | AI auto edits、个人词典、snippet library、团队能力、多端                    | 口语整理和词典已经是成熟方向；“4x faster”叙事清晰 | 不要只强调速度，要强调 agent 安全和任务质量                                          |
| Superwhisper                  | macOS/Windows/iOS AI dictation | 离线、预设模式、词汇表、自动粘贴、push-to-talk、快捷键                             | 预设模式、自动粘贴、快捷键是用户预期             | 不要把模式只做成 tone/format，要做 agent target 和任务类型                         |
| VoiceInk                      | 开源 macOS 语音转文字                 | 本地模型、隐私优先、全局快捷键、push-to-talk、模式、上下文感知、个人词典                    | 开源项目已证明这个赛道有社区关注；本地优先是强卖点      | 它是 macOS native dictation，我们要避开纯 macOS 和泛用听写定位                     |
| Whispering                    | 开源、本地优先 dictation              | local/cloud provider、透明数据流、可链式 transform                      | “transform pipeline”很接近我们的思路   | 我们要把 transform 做成 agent prompt compiler，而非通用文本变换                   |
| OpenWhispr                    | 开源跨平台语音助手                      | Windows/macOS/Linux、离线模型、dictation、AI agent hotkey、会议、MCP/API | 跨平台、开源增长和 agent 入口值得重点参考       | 它已经很接近“语音到 AI action”，我们的差异必须是可审阅、可修订、带安全边界的 agent prompt compiler |
| faster-whisper-dictation 等小项目 | CLI/桌面工具                       | 本地离线实时听写、hold-to-talk                                         | 技术实现可参考                        | 缺少产品化和 agent 场景差异                                                  |

### 3.3 重要参考链接

- Typeless: https://www.typeless.com/
- Wispr Flow: https://wisprflow.ai/
- Superwhisper: https://superwhisper.com/
- VoiceInk: https://github.com/Beingpax/VoiceInk
- Whispering 原仓库：https://github.com/braden-w/whispering
- Whispering 当前入口：https://github.com/EpicenterHQ/epicenter/tree/main/apps/whispering
- OpenWhispr: https://github.com/OpenWhispr/openwhispr
- FunASR: https://github.com/modelscope/FunASR

## 4. 产品是否值得做

### 4.1 批判性判断

如果目标是“做一个开源 Typeless / Wispr Flow”，不值得。这个方向已经卷到了：

- 多端覆盖。
- 低延迟 STT。
- AI 自动润色。
- 自动粘贴。
- 个人词典。
- 模式和快捷键。

这些都不是强差异化。

但如果目标是“给 AI agent 使用者提供从语音到高质量任务说明的中间层”，值得做。原因：

1. AI coding agent 正在成为高频工作入口，但语音输入还没有形成适合 agent 的交互范式。
2. 直接把口语丢给 agent 很危险，尤其是代码修改场景。
3. agent prompt 有独特结构：目标、背景、文件范围、约束、验收、禁止事项、是否执行、是否只分析。
4. 用户不是要“好看的文字”，而是要“让 agent 更少误解、更少乱改、更快开始”的任务描述。
5. 开源社区更容易围绕模式、模板、provider、agent 集成贡献，而不是单纯贡献 UI。
6. 即使已有 OpenWhispr 这类项目开始支持 AI agent hotkey，它们更像“语音到文本/动作入口”；本项目应坚持“原始转录可见、编译结果可审阅、会话可修订、安全边界默认存在”的更窄定位。

### 4.2 项目存在意义

本项目的存在意义不是替代键盘，而是降低“人类模糊意图”和“agent 精确执行”之间的摩擦。

更准确的定位：

> A local-first voice-to-agent prompt compiler.

中文定位：

> 本地优先的语音 Agent 指令编译器。

## 5. 产品目标

### 5.1 MVP 目标

在 Windows 上提供一个可日常使用的轻量桌面工具，让用户可以：

1. 使用全局快捷键打开小浮窗。
2. 在小浮窗聚焦时长按空格录音。
3. 实时看到原始语音转录。
4. 松开空格后，LLM 流式生成整理后的 agent prompt。
5. 自动复制生成结果到剪贴板。
6. 支持继续录音，对上一版 prompt 做增量修订。
7. 支持新建会话，清空上下文从头开始。
8. 支持切换目标模式，例如 Codex、Claude Code、Cursor、ChatGPT、通用写作。
9. 支持基础配置：STT 引擎、LLM provider、快捷键、默认行为、历史记录、隐私。

### 5.2 非目标

MVP 不做：

- 真正系统输入法 IME。
- 移动端。
- 会议纪要。
- 长音频文件转录。
- AI chat 主窗口。
- 自动执行 agent 命令。
- 复杂知识库。
- 团队协作。
- 云账号体系。
- 插件市场。

这些可以作为后续版本，但 MVP 必须保持非常锋利。

## 6. 目标用户

### 6.1 核心用户

1. AI coding agent 高频用户  
   使用 Codex、Claude Code、Cursor、Cline、Roo Code、Aider、ChatGPT 的开发者。

2. 中文技术工作者  
   经常用中文描述需求，夹杂英文技术词、路径、库名、错误信息。

3. 独立开发者和开源作者  
   希望快速把想法变成 issue、PRD、任务说明、agent prompt。

4. 产品经理 / 技术负责人  
   经常对 AI 描述复杂需求，希望输出结构化任务描述。

### 6.2 早期种子用户

- 已经使用 Claude Code / Codex 的中文开发者。
- 在 GitHub、Bilibili、X、掘金、V2EX 分享 AI coding workflow 的用户。
- 对本地优先、隐私、开源敏感的 power user。

## 7. 核心使用场景

### 7.1 向 coding agent 发起任务

用户按快捷键打开浮窗，说：

“帮我把登录页那个表单校验优化一下，就是现在那个邮箱和密码错误提示太乱了，我想让它统一走 zod schema，最好别动后端，只改前端，另外加个测试。”

AI 编译结果：

```text
请在当前项目中优化登录页的前端表单校验。

目标：
- 将邮箱和密码校验统一收敛到 Zod schema。
- 统一错误提示展示，避免多个来源的错误提示互相覆盖。
- 只修改前端实现，不改后端接口或后端校验逻辑。

请先阅读现有登录页、表单组件和测试结构，再给出最小范围修改。

验收标准：
- 邮箱格式错误、密码为空、后端返回登录失败时，错误提示清晰且不重复。
- 增加或更新相关前端测试。
- 保持现有 UI 风格，不做无关重构。
```

### 7.2 会话内增量修订

第一段生成后，用户继续按住空格说：

“等等，补充一下，不要直接改，先分析一下有哪些文件会被动到，然后问我确认。”

工具不是生成一段孤立文本，而是改写上一版：

```text
请先不要修改代码。请先分析当前项目中登录页表单校验相关实现，并列出你预计需要查看或修改的文件。

我希望后续目标是：
- 将邮箱和密码校验统一收敛到 Zod schema。
- 统一错误提示展示。
- 只修改前端实现，不改后端接口或后端校验逻辑。
- 增加或更新相关前端测试。

请先输出：
1. 相关文件和作用。
2. 建议修改方案。
3. 可能风险。
4. 需要我确认的问题。

在我确认前不要进行代码修改。
```

### 7.3 将模糊想法整理成 GitHub issue

用户选择 “GitHub Issue” 模式，说出问题和想法。工具输出 title、背景、期望行为、复现步骤、验收标准。

### 7.4 将调试思路整理给 agent

用户边看报错边说，工具整理成：

- 报错摘要。
- 当前环境。
- 已尝试操作。
- 希望 agent 先定位还是直接修复。
- 禁止事项，例如不要删除 lockfile。

### 7.5 快速生成“只分析不执行”指令

用户选择 “Review / Analyze Only” 模式，工具强制输出：

- 先阅读代码。
- 不修改文件。
- 只列出问题。
- 按严重程度排序。

这个模式对降低 agent 误操作特别重要。

## 8. 产品形态

### 8.1 推荐形态

MVP 推荐：全局快捷键 + 小浮窗 + 剪贴板输出。

不推荐 MVP 做系统输入法。原因：

1. Windows/macOS/Linux IME 技术栈差异大。
2. 权限、焦点、候选框、组合输入、中文输入法共存问题复杂。
3. 开源贡献门槛高。
4. 当前产品核心不是“替代输入法”，而是“生成可审阅的 agent prompt”。

### 8.2 工作浮窗

小浮窗是主工作窗口，必须非常克制。

默认尺寸建议：

- 宽度：520-680 px，可拖拽调整。
- 高度：320-460 px，可折叠为 mini 状态。
- 位置：默认屏幕右下或居中偏下，记忆上次位置。
- 层级：默认置顶，可配置。

布局：

```text
+------------------------------------------------------+
| 模式: Codex  || 设置 |                       | 新会话 | 
+------------------------------------------------------+
| 原始转录                                             |
| 用户刚才说出来的内容，实时追加显示...                  |
+------------------------------------------------------+
| AI 编译结果                                  [已复制] |
| 请在当前项目中...                                     |
| ...                                                  |
+------------------------------------------------------+
```

### 8.3 配置窗口

配置窗口不是工作窗口，不重复浮窗功能。它负责环境、历史、模板和诊断。

建议模块：

1. 首页 / 状态
   - 麦克风权限状态。
   - 当前 STT 引擎状态。
   - 当前 LLM provider 状态。
   - 最近一次错误。
   - 快速测试录音和测试生成。

2. 快捷键
   - 打开/隐藏浮窗。
   - 开始/停止录音。
   - 新建会话。
   - 切换上一个/下一个模式。
   - 复制当前结果。
   - 粘贴到前台应用。

3. 语音转文字
   - 引擎选择：FunASR、后续扩展。
   - 输入设备选择。
   - 采样率和音量检测。
   - VAD 静音阈值。
   - 实时转录开关。
   - 标点恢复开关。
   - 热词 / 专有名词词典。

4. LLM
   - provider：本地 Ollama / LM Studio / OpenAI-compatible / Anthropic / OpenAI / 自定义 endpoint。（先使用deepseek测试）
   - 模型选择。
   - API key 管理。
   - 流式输出开关。
   - 超时和重试。
   - 默认 prompt compiler system prompt。

5. Modes / Skills
   - Codex 模式。
   - Claude Code 模式。
   - Cursor 模式。
   - GitHub Issue 模式。
   - PRD 模式。
   - Bug Report 模式。
   - Analyze Only 模式。
   - Commit Message 模式。
   - 用户自定义模式。

6. 记忆
   - 会话内记忆：默认开启。
   - 跨会话偏好：默认可选关闭。
   - 个人术语词典。
   - 项目偏好：例如“默认先分析再改”“不要自动执行命令”。
   - 数据清理。

7. 历史
   - 按日期和模式查看历史会话。
   - 搜索原始转录和 AI 编译结果。
   - 复制历史结果。
   - 收藏常用结果。
   - 删除单条或全部历史。

8. 隐私与数据
   - 本地数据路径。
   - 是否保存音频：默认不保存。
   - 是否保存原始转录：默认保存，可关闭。
   - 是否保存 AI 编译结果：默认保存，可关闭。
   - 云端 provider 明示提醒。
   - 一键导出和一键清除。

9. 诊断与贡献
   - 导出诊断包，不包含敏感内容。
   - 查看日志。
   - 复制环境信息。
   - 打开 GitHub issue 模板。
   - 查看当前版本和更新。

## 9. 交互设计

### 9.1 全局快捷键

默认建议：

- `Ctrl+shift+Space`：打开/隐藏浮窗。
- 浮窗聚焦时 `Space` 长按：录音。
- `Ctrl+N`：新建会话。
- `Ctrl+上下箭头`：切换模式。
- `Ctrl+C` 或点击复制：复制 AI 编译结果。
- `Enter`：复制并隐藏。
- `Esc`：隐藏浮窗。

注意：全局长按 Space 容易干扰正常打字，因此 MVP 只在浮窗聚焦时启用 Space 录音。后续可以提供全局 push-to-talk 快捷键，例如 `Right Alt` 或用户自定义组合键。

### 9.2 状态机

```text
Idle
  -> HotkeyOpen
  -> Focused
  -> Recording
  -> Transcribing
  -> Compiling
  -> Copied
  -> Idle / RecordingAgain / NewSession
```

状态说明：

- Idle：浮窗隐藏或未激活。
- Focused：浮窗可接收快捷键。
- Recording：长按空格，显示音量和实时转录。
- Transcribing：松开后补齐最终转录。
- Compiling：LLM 流式输出。
- Copied：生成完成并已复制到剪贴板。
- RecordingAgain：未新建会话时，下一段语音被视为对当前编译结果的补充或修订。
- NewSession：清空当前上下文，下一段语音生成全新 prompt。

### 9.3 会话规则

每个会话包含：

- session_id
- created_at
- active_mode
- transcript_turns
- compiled_versions
- selected_stt_provider
- selected_llm_provider
- memory_snapshot

规则：

1. 首次录音生成 v1。
2. 未点击新建会话时，后续录音作为 refinement turn。
3. refinement 不简单追加，而是根据“上一版结果 + 新转录 + 当前模式”重新生成一版完整结果。
4. 每次生成结果保存版本，可在历史中回看。
5. 用户点击新建会话后，清空会话上下文，不再参考上一会话。
6. 切换模式时保留原始转录，但重新编译需要用户确认或手动触发。

### 9.4 复制行为

默认：

- LLM 完成后自动复制 AI 编译结果。
- 复制按钮显示状态：复制、已复制、复制失败。
- 若用户在生成中点击复制，则复制当前已生成内容。
- 可配置是否自动粘贴到前台应用。MVP 默认只复制，不自动粘贴。

为什么默认复制而不是自动粘贴：

- 用户需要先审阅 prompt。
- agent 场景误粘贴成本较高。
- 复制行为更稳定，跨应用兼容性更好。

## 10. 功能需求

### 10.1 浮窗唤起

优先级：P0

需求：

- 用户可通过全局快捷键打开/隐藏浮窗。
- 浮窗打开后自动聚焦。
- 浮窗显示当前模式、STT、LLM、录音状态。
- 浮窗位置和尺寸可记忆。

验收：

- 在常见应用中按快捷键均可唤起。
- 重复按快捷键可隐藏。
- 程序重启后保持上次位置。

### 10.2 录音

优先级：P0

需求：

- 浮窗聚焦时，长按空格开始录音。
- 松开空格停止录音。
- 录音时显示音量或录音状态。
- 支持最短录音时长保护。
- 支持静音检测。
- 支持选择麦克风输入设备。

本地技术基线：

- `voice/voice_test.py` 当前使用 PyAudio。
- 采样格式：`pyaudio.paInt16`。
- 通道：mono。
- 采样率：16000 Hz。
- chunk：1024。
- 当前按住 Space 开始，松开 Space 触发转录。
- 当前使用 FunASR `AutoModel(model="paraformer-zh", vad_model="fsmn-vad", punc_model="ct-punc", device="cpu")`。

### 10.3 实时转录

优先级：P0/P1

MVP 可分两阶段：

阶段 1：

- 录音结束后显示最终转录。
- 实现简单稳定。

阶段 2：

- 录音时实时显示部分转录。
- 使用 FunASR streaming 模型或可插拔 streaming STT provider。
- 如果当前模型做不到实时zhuan

建议：

- 为了尽快发布 MVP，可先做“录音中显示音量，松开后显示转录”。

### 10.4 AI 编译

优先级：P0

输入：

- 当前原始转录。
- 当前会话历史。
- 当前模式 prompt。
- 用户记忆和术语词典。
- 可选上下文，例如前台应用名、剪贴板文本、选中文本，后续版本。

输出：

- 一个清晰、完整、可粘贴给目标 agent 的 prompt。

编译原则：

1. 保留用户真实意图，不编造需求。
2. 删除口头填充词、重复、犹豫。
3. 将乱序表达整理成结构。
4. 明确目标、约束、步骤和验收标准。
5. 对不确定内容显式标注“需要确认”。
6. 对高风险动作加入安全边界，例如“先分析，不要修改”。
7. 根据目标 agent 调整措辞。

### 10.5 模式

优先级：P0

内置模式：

1. Codex
   - 强调读取代码、最小改动、运行测试、不要改无关文件。

2. Claude Code
   - 强调先 inspect，再 plan，再 implement。
   - 对长上下文更友好。

3. Cursor
   - 适合编辑器内任务。
   - 输出更短，偏向直接可执行修改请求。

4. Analyze Only
   - 强制只分析、不改文件。

5. GitHub Issue
   - 输出 title、背景、当前行为、期望行为、验收标准。

6. Bug Fix
   - 输出复现、环境、错误、怀疑原因、修复范围、测试。

7. PRD
   - 输出背景、目标用户、功能需求、非目标、验收标准。

8. General Cleanup
   - 泛用口语整理，作为备选。

### 10.6 Skill 系统

优先级：P1

Skill 是一个可配置 prompt template，不是复杂插件。

每个 skill 包含：

```yaml
id: codex-safe-edit
name: Codex Safe Edit
target: codex
description: 编译成适合 Codex 的谨慎代码修改请求
system_prompt: |
  You convert messy spoken requirements into safe coding-agent prompts...
output_schema:
  - goal
  - context
  - constraints
  - acceptance_criteria
  - safety_instructions
defaults:
  auto_copy: true
  ask_when_uncertain: true
```

MVP 可以先用 JSON/YAML 文件管理。开源后，社区最容易贡献的就是 modes/skills。

### 10.7 记忆

优先级：P1

记忆分三层：

1. 会话内记忆
   - 默认开启。
   - 用于“刚才那个需求再补充一下”。

2. 用户偏好记忆
   - 默认可选。
   - 例如“我默认喜欢先分析再执行”“我用 pnpm”“不要自动提交 git”。

3. 项目记忆
   - P2。
   - 例如某个 repo 的技术栈、测试命令、常见路径。

MVP 先做会话内记忆。跨会话记忆容易引入隐私和错误继承，必须谨慎。

### 10.8 历史

优先级：P1

需求：

- 保存会话列表。
- 每个会话保存多轮原始转录和生成版本。
- 支持搜索。
- 支持复制历史输出。
- 支持删除。
- 支持关闭历史保存。

默认策略：

- 不保存音频。
- 保存转录和编译结果。
- 首次启动时明确告知。

### 10.9 Provider 管理

优先级：P0/P1

STT provider：

- P0：FunASR local。
- P1：faster-whisper local。
- P1：OpenAI-compatible STT。
- P2：SenseVoice / WhisperKit / platform-native。

LLM provider：

- P0：OpenAI-compatible endpoint。
- P0：Ollama。
- P1：LM Studio。
- P1：OpenAI。
- P1：Anthropic。
- P2：Gemini、Groq、自定义。

### 10.10 错误处理

优先级：P0

常见错误：

- 麦克风无权限。
- 麦克风设备不存在。
- 音量过低。
- STT 模型未下载。
- LLM provider 未配置。
- API key 错误。
- 网络超时。
- 剪贴板写入失败。

浮窗中只显示简洁状态，例如“麦克风不可用”“LLM 超时”。详细错误放配置窗口诊断页。

## 11. AI 编译器设计

### 11.1 Prompt compiler 的任务

Prompt compiler 不只是润色，它要做语义编译：

```text
messy spoken thought
  -> intent extraction
  -> risk detection
  -> missing info detection
  -> target-agent formatting
  -> final prompt
```

### 11.2 输出结构

默认 coding agent 输出结构：

```text
请完成以下任务：

目标：
- ...

背景：
- ...

约束：
- ...

执行要求：
- ...

验收标准：
- ...

如果信息不足，请先提出需要确认的问题；不要自行猜测高风险细节。
```

### 11.3 风险规则

当原始语音包含以下意图时，编译结果必须加入安全边界：

- 删除文件。
- 批量重命名。
- 修改数据库。
- 运行迁移。
- 提交或推送 git。
- 安装依赖。
- 修改认证、支付、权限、安全相关逻辑。
- 用户表达明显不确定。

示例：

```text
请先分析并列出计划。在我确认前，不要删除文件、不要运行迁移、不要提交 git。
```

### 11.4 不确定性处理

不要把不确定内容写成事实。应使用：

- “用户可能想要...，请先确认。”
- “如果当前项目中存在 X，请...；否则先说明没有找到。”
- “不要假设具体文件路径，先搜索相关实现。”

### 11.5 中英文混合

编译规则：

- 技术名词保留英文，例如 React、Zod、FastAPI、pytest。
- 用户明确说的变量名、文件名、命令保留原文。
- 中文作为主体表达。
- 如果转录里技术名词疑似错误，保留并标注可能需要确认。

## 12. 技术方案

### 12.1 推荐架构

```text
Desktop Shell
  - floating window
  - config window
  - global shortcuts
  - clipboard

Core Service
  - session manager
  - recorder
  - STT provider interface
  - LLM provider interface
  - prompt compiler
  - history store
  - settings store

Providers
  - FunASR local
  - Ollama / OpenAI-compatible LLM
  - future providers
```

### 12.2 技术栈建议

MVP 有两条可选路线：

#### 路线 A：Python-first

适合快速验证。

- UI：PySide6 / PyQt。
- 音频：PyAudio / sounddevice。
- STT：FunASR。
- 热键：pynput / keyboard。
- 配置：SQLite + JSON。
- 剪贴板：pyperclip / Qt clipboard。
- 打包：PyInstaller / Nuitka。

优点：

- 可以直接复用当前测试代码。
- 集成 FunASR 简单。
- 快速出 MVP。

缺点：

- 桌面体验和打包体积一般。
- 跨平台权限和全局热键需要更多打磨。

#### 路线 B：Tauri + Python sidecar

适合开源长期维护。

- UI：Tauri + React/Vue/Svelte。
- 核心桌面能力：Rust/Tauri。
- STT：Python sidecar 或独立本地服务。
- LLM：HTTP provider。
- 数据：SQLite。

优点：

- 桌面体验更好。
- 前端贡献者更容易参与。
- 后续跨平台更自然。

缺点：

- 初期工程复杂度更高。
- Python STT sidecar 打包要处理。

建议：

- 第一个可用版本用 Python-first。
- 当交互验证成功后，再评估 Tauri 重构。
- 不要一开始同时追求“最佳架构”和“最佳体验”，会拖慢发布。

### 12.3 本地 voice_test.py 整合计划

当前脚本可沉淀为三个模块：

1. `AudioRecorder`
   - start()
   - stop()
   - get_volume()
   - save_temp_wav()

2. `FunASRTranscriber`
   - load_model()
   - transcribe(audio_path)
   - transcribe_stream(audio_chunks)，后续

3. `HotkeyController`
   - register_open_window()
   - register_push_to_talk()
   - bind_space_when_focused()

需要改进：

- 修复源码中文注释编码问题。
- 输入设备不要硬编码 `INPUT_DEVICE_INDEX = 2`，改为配置。
- 临时音频文件使用系统 temp path 和唯一文件名。
- 模型初始化异步化，避免启动卡顿。
- 日志从 print 改为 logging。
- 错误返回结构化对象，给 UI 展示。

### 12.4 数据模型

SQLite 表建议：

```sql
sessions(
  id text primary key,
  title text,
  mode_id text,
  created_at integer,
  updated_at integer
)

turns(
  id text primary key,
  session_id text,
  turn_index integer,
  raw_transcript text,
  compiled_text text,
  stt_provider text,
  llm_provider text,
  created_at integer
)

settings(
  key text primary key,
  value text,
  updated_at integer
)

modes(
  id text primary key,
  name text,
  config_json text,
  enabled integer,
  updated_at integer
)

dictionary_entries(
  id text primary key,
  phrase text,
  replacement text,
  note text,
  created_at integer
)
```

### 12.5 配置文件

建议使用：

- `%APPDATA%/AgentVoice/config.json`
- `%APPDATA%/AgentVoice/history.sqlite`
- `%APPDATA%/AgentVoice/logs/app.log`
- `%APPDATA%/AgentVoice/modes/*.yaml`

开源项目中提供默认 `modes/` 模板。

## 13. 隐私与安全

### 13.1 默认原则

1. 音频默认不保存。
2. 历史默认本地保存，可关闭。
3. 云端 LLM/STT 必须由用户显式配置。
4. 配置页清楚显示当前数据流向。
5. API key 本地加密存储，或使用系统凭据管理器。
6. 诊断日志默认不包含原始转录和编译结果。

### 13.2 安全提示

当用户启用云端 provider 时，配置页显示：

```text
当前模式会将转录文本发送到你配置的云端 LLM provider。请确认其中不包含敏感代码、密钥、客户数据或公司内部信息。
```

### 13.3 Agent 安全

MVP 不直接调用 Codex/Claude Code 执行动作。只复制 prompt。后续即使做集成，也要保留确认步骤。

## 14. 性能指标

### 14.1 MVP 指标

- 浮窗唤起延迟：小于 200 ms。
- 开始录音反馈：小于 100 ms。
- 3-10 秒语音转录完成：目标小于 2 秒，取决于模型和硬件。
- LLM 首 token：本地小模型目标小于 2 秒，云端取决于网络。
- 复制完成提示：生成结束后小于 100 ms。
- 空闲内存：Python-first MVP 尽量小于 1.5 GB，模型加载后可接受更高但需说明。

### 14.2 质量指标

人工评估：

- Prompt 可用率：用户无需修改即可发送给 agent 的比例。
- 误解率：生成结果偏离用户意图的比例。
- 安全边界命中率：高风险需求是否加入确认/禁止执行。
- 会话修订成功率：第二轮补充是否正确整合上一版。

产品指标：

- 每日生成次数。
- 复制后是否再次手动编辑，后续可通过本地可选统计。
- 模式使用分布。
- 平均录音时长。
- 历史复用次数。

## 15. UI 文案原则

1. 浮窗不要解释功能，只显示状态。
2. 使用短标签：录音中、转录中、生成中、已复制。
3. 不用大段引导。
4. 错误文案要可行动。
5. 配置窗口再承载说明和诊断。

示例状态：

- 准备就绪
- 按住 Space 说话
- 正在录音
- 正在转录
- 正在整理
- 已复制
- 麦克风不可用
- LLM 未配置

## 16. 开源策略

### 16.1 开源定位

不要只宣传“开源听写”。建议宣传：

```text
Open-source voice-to-agent prompt compiler.
Speak messy thoughts. Send clear prompts.
```

中文：

```text
开源的语音 Agent 指令编译器。
把没想清楚的话，整理成 agent 能安全执行的 prompt。
```

### 16.2 Repo 结构建议

```text
/
  README.md
  docs/
    PRD.md
    ROADMAP.md
    ARCHITECTURE.md
    CONTRIBUTING.md
  app/
  core/
  providers/
    stt/
    llm/
  modes/
    codex.yaml
    claude-code.yaml
    cursor.yaml
    analyze-only.yaml
  voice/
    voice_test.py
  tests/
```

### 16.3 README 首屏卖点

必须第一屏讲清楚差异：

- Built for AI coding agents.
- Raw transcript + compiled prompt side by side.
- Session-aware refinements.
- Local-first STT.
- Bring your own LLM.
- Safe by default: copies prompt, does not execute.

### 16.4 适合社区贡献的模块

1. 新 STT provider。
2. 新 LLM provider。
3. 新 mode / skill。
4. 不同平台的热键和剪贴板适配。
5. UI 主题。
6. 语言优化。
7. 安装包和文档。

### 16.5 License 建议

如果希望影响力和商业可能性兼顾：

- 核心代码：Apache-2.0 或 MIT。
- 如果担心商业闭源直接拿走：AGPL-3.0，但会降低企业采用和贡献。

建议 MVP 使用 Apache-2.0。理由：

- 对开发者友好。
- 适合基础工具。
- 更利于生态扩展。

## 17. 路线图

### Phase 0：技术整理

目标：把当前脚本整理成可复用模块。

任务：

- 修复编码。
- 抽离录音模块。
- 抽离 FunASR 转录模块。
- 增加 LLM 调用原型。
- 增加简单 CLI：录音 -> 转录 -> 编译 -> 复制。

### Phase 1：可用 MVP

目标：Windows 桌面小浮窗可日常使用。

任务：

- 浮窗 UI。
- 长按空格录音。
- 转录显示。
- LLM 流式生成。
- 自动复制。
- 新建会话。
- 模式切换。
- 基础配置。
- 本地历史。

### Phase 2：开源发布

目标：GitHub 上能被快速安装和贡献。

任务：

- README。
- 安装包。
- 示例动图。
- 贡献指南。
- mode 模板文档。
- issue 模板。
- basic tests。

### Phase 3：体验增强

目标：从可用变成顺手。

任务：

- 实时转录。
- 热词词典。
- 前台 app 感知。
- 选中文本上下文。
- 自定义模式编辑器。
- Ollama/LM Studio 更好支持。
- 历史搜索。

### Phase 4：生态扩展

目标：形成 agent voice workflow 生态。

任务：

- Codex/Claude Code/Cursor 深度模式。
- MCP 或 CLI 输出。
- 项目级记忆。
- mode gallery。
- 跨平台支持。
- 可选自动粘贴。

## 18. MVP 验收标准

### 18.1 核心流程

1. 用户按快捷键打开浮窗。
2. 长按空格录音。
3. 松开空格后看到原始转录。
4. LLM 开始流式生成整理后的 prompt。
5. 生成完成后自动复制。
6. 用户继续录音，结果作为上一版 prompt 的修订。
7. 用户新建会话后，下一次生成不引用旧会话。

### 18.2 配置流程

1. 用户可以选择麦克风设备。
2. 用户可以配置 STT。
3. 用户可以配置 LLM。
4. 用户可以切换模式。
5. 用户可以查看历史。
6. 用户可以清除历史。

### 18.3 质量门槛

用 30 条真实口语样本测试：

- 至少 80% 输出可直接发给 agent。
- 至少 90% 没有明显编造关键需求。
- 高风险语句至少 90% 加入安全确认。
- 会话第二轮补充至少 80% 能正确整合上一版。

## 19. 示例 mode：Codex Safe Edit

```yaml
id: codex-safe-edit
name: Codex Safe Edit
target: codex
description: 将口语需求整理成适合 Codex 的谨慎代码修改任务
system_prompt: |
  你是一个语音需求到 coding agent prompt 的编译器。
  用户输入来自语音转录，可能包含重复、改口、口头禅和不完整想法。
  你的任务是整理为清晰、完整、可直接发送给 Codex 的中文 prompt。

  规则：
  1. 保留用户真实意图，不要编造。
  2. 删除口头填充和重复。
  3. 将需求整理为目标、背景、约束、执行要求、验收标准。
  4. 如果用户表达不确定，要求 Codex 先确认或先分析。
  5. 对文件删除、数据库、依赖安装、git 提交、权限认证等高风险操作，必须要求先分析并等待确认。
  6. 默认要求 Codex 遵循现有代码风格，保持最小改动，运行相关测试。
  7. 不要输出解释，只输出最终 prompt。
```

## 20. 最大风险

### 20.1 同质化风险

风险：用户认为这只是另一个 Wispr Flow / Typeless。

应对：

- README 和 UI 明确强调 agent prompt compiler。
- 默认模式就是 Codex / Claude Code / Cursor。
- 双栏显示原始转录和编译结果。
- 会话修订作为核心演示。

### 20.2 STT 延迟

风险：本地模型加载慢、转录慢，影响手感。

应对：

- 启动后后台预加载模型。
- 首次使用显示模型加载状态。
- 支持轻量模型。
- 支持云端 STT 作为可选。

### 20.3 LLM 编译不稳定

风险：LLM 过度改写或编造。

应对：

- prompt compiler 严格约束。
- 输出不确定项。
- 引入低温度参数。
- 加测试样本集。

### 20.4 桌面权限复杂

风险：全局快捷键、麦克风权限、剪贴板权限在不同系统表现不一致。

应对：

- MVP 优先 Windows。
- 把平台能力抽象成 adapter。
- 文档写清楚已支持平台。

### 20.5 范围膨胀

风险：想做输入法、会议、聊天、知识库、agent 集成，最终 MVP 出不来。

应对：

- Phase 1 只做浮窗、录音、转录、编译、复制、会话。
- 任何功能若不能增强“语音到 agent prompt”，暂缓。

## 21. 推荐产品决策

1. 形态：先做小浮窗，不做输入法。
2. 输出：默认复制，不默认自动粘贴。
3. 安全：默认不直接执行 agent。
4. 记忆：MVP 只做会话内记忆。
5. 技术：先 Python-first，用现有 FunASR 验证。
6. 差异化：主打 agent prompt compiler，而不是 general dictation。
7. 开源：Apache-2.0，鼓励社区贡献 modes/providers。
8. 首个演示视频：必须展示“第一段说乱了，第二段补充修订，最终生成安全清晰 Codex prompt”。

## 22. 下一步执行清单

1. 确定项目名称。
2. 整理 `voice/voice_test.py` 为 core 模块。
3. 写第一个 prompt compiler system prompt。
4. 建立 30 条真实口语样本测试集。
5. 做 Python 桌面浮窗原型。
6. 接入一个 LLM provider，优先 OpenAI-compatible 和 Ollama。
7. 实现会话内 refinement。
8. 打包一个 Windows 可运行版本。
9. 写 README 和演示 GIF。
10. 发布 v0.1 alpha。
