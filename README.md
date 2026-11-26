<div align="center">

# ✨ Aura

### 一个优雅的语音输入工具

说话就能输入。Aura 会识别你的语音整理表达并把结果写入当前编辑器。

它可以替代 Typeless 和千问输入法成为日常工作里的轻量语音入口。

[![License](https://img.shields.io/badge/License-MIT-22C55E)](LICENSE)

</div>

## 功能

- 右 Alt 开始录音再按一次结束
- 结果自动写入当前光标或复制到剪贴板
- 自动跟随当前输入框所在屏幕显示优雅浮窗
- 语音整理与选区改写
- 去 AI 味和 Prompt 工程 Skill
- 语音翻译
- 实时麦克风波形检测
- 听写历史与个人词典

模型服务固定使用豆包流式 ASR 2.0 和 `doubao-seed-2-0-mini-260428`。我们做过速度、延迟和成本对比，选择了响应更快、延迟更低且价格更友好的组合。

## 快速开始

1. 下载并安装最新版本 Aura。
2. 打开设置进入模型服务。
3. 填入豆包 ASR API Key 和火山方舟 API Key。
4. 点击测试连接。
5. 在任意输入框按右 Alt 开始说话，再按一次右 Alt 写入。

## 申请两个 API Key

### 火山方舟 LLM Key

1. 注册并登录[火山方舟控制台](https://console.volcengine.com/ark/region:cn-beijing)。
2. 打开左侧「开通管理」，开通豆包 Seed 2.0 Mini 文本模型。
3. 打开「API Key 管理」，点击「创建 API Key」。
4. 填写备注并创建，复制生成的 Key。Key 通常只完整显示一次，请立即保存。
5. 回到 Aura 的「设置 → 模型服务」，粘贴到「火山方舟 API Key」。

方舟接口地址是 `https://ark.cn-beijing.volces.com/api/v3`。Aura 已经固定使用 `doubao-seed-2-0-mini-260428`。

### 豆包流式 ASR 2.0 Key

1. 注册并登录[豆包语音控制台](https://console.volcengine.com/speech/app)。
2. 进入「开通管理」，开通「流式语音识别 2.0」。
3. 在左侧底部打开「API Key」，点击创建或获取 API Key。
4. 复制生成的 Key，回到 Aura 的「设置 → 模型服务」。
5. 粘贴到「豆包 ASR API Key」并保存。

Aura 使用实时接口 `wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async`，资源 ID 为 `volc.seedasr.sauc.duration`。

请妥善保管两个 Key。不要把它们提交到 GitHub 或发给其他人。

## 社区

问题反馈请前往[GitHub Issues](https://github.com/kgnbkgnb666/Aura/issues)。

<div align="center">

## Star 历史

[![Star History Chart](https://api.star-history.com/svg?repos=kgnbkgnb666/Aura&type=Date)](https://star-history.com/#kgnbkgnb666/Aura&Date)

<img src="qq技术交流群.jpg" alt="QQ 技术交流群" width="360" />

</div>

## License

[MIT](LICENSE)
