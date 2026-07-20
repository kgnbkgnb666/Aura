# 参与贡献

感谢你愿意帮助 Aura 变得更好。项目目前处于早期阶段，欢迎 Bug 修复、测试、文档、提示词模式和 Provider 扩展。

## 开始之前

1. 先搜索现有 Issue，避免重复工作。
2. 较大的功能或架构调整请先创建 Issue，说明场景、方案和兼容性影响。
3. 一个 Pull Request 尽量只解决一个问题，并保持提交内容可审查。
4. 不要提交 API Key、历史数据库、录音、模型、构建产物或个人配置。

## 本地开发

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm ci
npm run tauri:dev
```

只运行测试可安装更轻量的依赖：

```powershell
python -m pip install -r requirements-test.txt
python -m pytest -q
npm run build
cargo check --locked --manifest-path src-tauri\Cargo.toml
```

## 扩展约定

- STT Provider 放在 `aura/providers/stt/`，实现 `SpeechToTextProvider` 协议。
- LLM Provider 放在 `aura/providers/llm/`，实现 `LLMProvider` 协议。
- 官方提示词模式放在 `modes/official/`，使用带稳定 `id` 和 `icon` 的 YAML 文件。`.aura-local/modes/` 是用户私人资产，不应提交。
- 新行为需要测试；修复 Bug 时应先添加能复现问题的回归用例。
- 面向用户的错误信息尽量清楚、可操作，不记录密钥和完整敏感文本。

## Pull Request 检查清单

- [ ] 改动范围清晰，没有夹带本地文件或无关格式化
- [ ] Python 测试通过
- [ ] TypeScript 构建通过
- [ ] Rust `cargo check --locked` 通过
- [ ] 新增配置有默认值、迁移策略和文档
- [ ] 涉及隐私或网络请求的改动说明了数据边界
