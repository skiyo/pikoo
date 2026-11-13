# 配置参考

[English](configuration.md) | **简体中文**

配置是一份完整、有版本号的 JSON，保存在 Git 仓库外，通过 USB 写入设备。从 [device.example.json](../examples/device.example.json) 开始；示例域名和 `YOUR_...` 只是占位内容，不是可直接使用的服务。

## 配置流程

1. 复制示例，或执行 `python tools/configure.py --init /absolute/private/device.json --language zh-CN`。
2. 填写 Wi-Fi、Live 与推理配置，暂不需要搜索时保持关闭。
3. 执行 `python tools/configure.py --config /absolute/private/device.json --dry-run`。
4. 执行 `python tools/device.py configure --port PORT --config /absolute/private/device.json`。
5. 查询状态，准备好后取消静音。命令会配置并重启，不重刷应用固件。

每次更新提交完整配置，不是局部 JSON 补丁。私密保存源文件，便于轮换密钥或更换网络。校验不调用 API。设备使用可更新的普通 `agent_secret` NVS，家庭数据导出不含这些设置。

## 字段与限制

普通字符串限制按 UTF-8 字节计算，另行注明的除外；规范化后的完整文档上限 16 KiB。

| 字段 | 含义与限制 |
|---|---|
| `version` | 整数 `1` |
| `wifi.ssid` | 必填，1–32 字节，使用 2.4 GHz Wi-Fi |
| `wifi.password` | 开放网络可为空，否则 8–63 字节 |
| `agent.name` | 1–64 字节；整个 agent 段省略时默认 Pikoo |
| `agent.language` | 1–32 字节；默认 `en`，中文设为 `zh-CN` |
| `agent.instructions` | 可选角色指令，最多 2048 字节 |
| `live.protocol` | `openai_live` |
| `live.url` | 完整 WSS 地址，最多 2048 字符 |
| `live.api_key` | 该服务密钥；为空时不发送 Authorization |
| `live.model` | 必填模型 ID，最多 128 字节 |
| `live.voice` | 音色 ID，默认 `marin`，最多 64 字节 |
| `live.audio_rate` | 整数 `16000` 或 `24000`，默认 16000 |
| `llm.protocol` | `openai_responses` 或 `openai_chat_completions` |
| `llm.url`、`api_key`、`model` | 独立的完整 HTTPS 地址、密钥和模型 |
| `search.enabled` | 布尔值，默认 false |
| `search.protocol` | 开启时为 `tavily` 或 `openai_responses` |
| `search.url`、`api_key` | 搜索的完整 HTTPS 地址与独立密钥 |
| `search.model` | Responses 搜索必填 |
| `search.extract_url` | Tavily 可选提取地址，必须与搜索为同一 HTTPS 源 |
| `network.proxy_url` | 可选 HTTPS 代理源地址，不带路径或查询参数 |
| `network.proxy_basic` | 可选 username:password 的 Base64，要求同时配置代理地址 |

API 密钥和代理凭证最多 1024 个非空白可打印 ASCII 字符。URL 不能嵌入用户名、密码或 fragment，也不应在查询参数中填写密钥。不支持自定义鉴权头或自定义 CA。修改字段时建议保留示例中完整的 `agent` 配置段。

## 协议兼容要求

| 角色 | 协议 | 必须支持的行为 |
|---|---|---|
| 语音 | `openai_live` | WSS、客户端委派、输入输出转写、单声道 PCM16、Decisions 交互事件 |
| 推理 | `openai_responses` | Responses 请求、函数调用、完成输出、工具结果 |
| 推理 | `openai_chat_completions` | 非流式 Chat Completions、函数工具、工具结果消息 |
| 搜索 | `tavily` | 搜索结果；提取能力另行配置 |
| 搜索 | `openai_responses` | 支持托管 `web_search` 的 Responses 和可用引用 |

固件使用配置的**完整 endpoint**，不自动添加 `/v1`，不根据域名猜协议，也不跟随 API 重定向。文字聊天服务不能自动替代 Live。模型与音色权限应向对应服务商确认，因此公开示例不固定具体商业模型名称。

## 推理与搜索示例

以下仅为配置片段，需要替换完整私有 JSON 中对应部分，不能独立用于安装：

```json
{"llm":{"protocol":"openai_chat_completions","url":"https://llm.example.com/v1/chat/completions","api_key":"YOUR_LLM_KEY","model":"YOUR_LLM_MODEL"}}
```

```json
{"search":{"enabled":true,"protocol":"tavily","url":"https://api.tavily.com/search","extract_url":"https://api.tavily.com/extract","api_key":"YOUR_SEARCH_KEY"}}
```

```json
{"search":{"enabled":true,"protocol":"openai_responses","url":"https://search.example.com/v1/responses","api_key":"YOUR_SEARCH_KEY","model":"YOUR_SEARCH_MODEL"}}
```

Tavily 不填 `extract_url` 时只提供搜索。关闭搜索后不提供搜索工具，也无需搜索密钥。Responses 搜索不注册任意网页提取能力。

## 网络、凭证与语言

默认 `network: {}`，直接建立经过证书验证的 TLS。可选配置标准 HTTPS CONNECT 代理源地址。代理凭证只用于外层连接，服务密钥通过服务 TLS 发送，各请求独立构造鉴权。API 不跟随重定向，避免携带凭证访问其他位置。

`agent.language: zh-CN` 控制中文对话，`en` 为默认英文。设置助手的 `--language` 仅改变交互提示，与设备配置独立。修改名称不会重新训练英文唤醒词；角色指令也不能添加尚未实现的工具或协议。

[快速开始](getting-started.zh-CN.md) · [常见问题](faq.zh-CN.md) · [安全说明](../SECURITY.zh-CN.md)
