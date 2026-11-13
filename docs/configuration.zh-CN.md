# 服务配置

[English](configuration.md) | **简体中文**

把[示例](../examples/device.example.json)复制到 Git 仓库外，配置版本为 `1`。修改后先校验，再写入设备：

```sh
python tools/configure.py --config /private/pikoo.json --dry-run
python tools/device.py configure --port PORT --config /private/pikoo.json
```

`device.py configure` 经 USB 写入整份配置并重启，不重刷应用、不覆盖音量、屏幕方向或家庭数据分区。也可用 `configure.py --init /private/pikoo.json` 交互创建；密码和密钥不回显。完成的私有配置不要提交 Git。

| 配置组 | 字段 |
|---|---|
| `wifi` | `ssid`、`password`；开放网络密码可为空 |
| `agent` | `name`、`language`、`instructions`；省略时默认 Pikoo / en |
| `live` | `protocol`、完整 `url`、`api_key`、`model`、`voice`（默认 marin）、`audio_rate`（16000 或 24000） |
| `llm` | `protocol`、完整 `url`、`api_key`、`model` |
| `search` | `enabled`；启用后填协议、完整地址、密钥；Responses 另填模型；Tavily 可填 `extract_url` |
| `network` | 可选 `proxy_url`（HTTPS origin）和 `proxy_basic`（用户名:密码的 Base64） |

地址不会自动追加 API 路径。各服务密钥独立，不自动复用；使用 Bearer 鉴权，空密钥表示不发送 Authorization，适用于明确免鉴权的服务。代理使用独立 Basic 凭证。所有连接校验 TLS 证书，不提供跳过验证的开关。

## 支持的协议

- `live.protocol = openai_live`：Live 主 WebSocket、客户端委派、输入输出转写、PCM16 和 Decisions 互动分类。OpenAI 地址为 `wss://api.openai.com/v1/live/sessions`；兼容入口也必须支持这些能力。模型与音色按账号权限填写。
- `llm.protocol = openai_responses`：支持函数工具调用及完整输出的 Responses API，OpenAI 地址为 `https://api.openai.com/v1/responses`。
- `llm.protocol = openai_chat_completions`：支持函数工具、工具结果消息及非流式输出的 Chat Completions。仅接受聊天文本的接口不足以执行 Agent 工具。
- `search.protocol = tavily`：独立搜索接口，常用地址为 `https://api.tavily.com/search`。填写 `https://api.tavily.com/extract` 可启用网页提取；因复用该搜索密钥，提取地址必须与搜索同源。
- `search.protocol = openai_responses`：独立配置支持托管 `web_search` 的 Responses 地址和模型；返回可用来源引用，不开放任意网页提取工具。

示例关闭搜索，无须配置搜索密钥。修改地址表示选择兼容部署，不会改变线上协议；未知协议直接拒绝。本版未实现自定义 CA 或其他鉴权头格式。

[Live 委派协议](https://developers.openai.com/api/docs/guides/live-delegation) · [Responses 搜索](https://developers.openai.com/api/docs/guides/tools-web-search) · [Tavily API](https://docs.tavily.com/)

默认对话语言为英文（`en`）。将 `agent.language` 改为 `zh-CN` 并经 USB 更新配置即可切换中文，无须重编固件。
