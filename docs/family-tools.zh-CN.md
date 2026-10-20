# 搜索、网页阅读与家庭清单

[English](family-tools.md) | **简体中文** · [整体架构](architecture.zh-CN.md)

Gemini Live 负责选择工具和语音回答，固定的 Qwen Audio 2.0.1 负责执行。保持 `AGENT_PROTOCOL=none`，不增加独立后台 Agent 或新的对话模型。

| 工具 | 实现 | 持久化与费用 |
|---|---|---|
| `web_search` | Pikoo 注入的 DeepSeek Search Provider | 调用官方原始搜索接口，按账号当前计费规则执行 |
| `fetch_url` | 上游 `SafeUrlFetcher` | 直接请求公开网页，不调用 DeepSeek Fetch |
| `notes` | 上游家庭 owner 清单存储 | 私密 `frontend-notes.json`，重启保留 |
| 记忆、话题回溯和当前时间 | 现有运行时 | 见[上下文与记忆](context-memory.zh-CN.md) |

## 配置与行为

开启 `QWEN_AUDIO_WEB_TOOLS_ENABLED=on`、`QWEN_AUDIO_NOTES_TOOL_ENABLED=on`。保留 `QWEN_AUDIO_WEB_SEARCH_PROVIDER=none`：Pikoo 显式注入适配器，不创建 360／Bing 兜底。`DEEPSEEK_API_KEY` 只进入受保护的服务器配置，不进入固件、浏览器配置或公开文件。缺少 Key 时搜索不可用，网页阅读和清单仍可使用。

搜索调用 `POST https://api.deepseek.com/v1/tools/search`，查询为 1–128 个 Unicode 字符，默认 5 条、最多 8 条，`need_content=false`。摘要、站点和日期转换为原生引用，原始响应最多 256 KiB，单次总超时 8 秒。不发送完整对话、家庭档案或本地化 IP，不自动重试、不调用 DeepSeek 语言模型。鉴权、余额不足、限流、响应异常、超时与网络错误使用不同的脱敏错误码。失败或空结果不能被表述为查到了事实。

网页阅读接受公开 HTTP／HTTPS 文本页，保留内网阻断和重定向检查，响应最多 1 MiB、正文最多返回 12,000 字符；不绕过登录、付费或浏览器验证。网页是不可信资料，不能授权修改清单或覆盖指令。输出沿用中英双语规则。Google 工具调用取消或插话后，迟到结果不再发送给模型触发语音。

清单支持添加时创建、查看、移除、清空和删除，沿用上游名称与条目歧义规则；多个匹配时询问用户。清单属于现有家庭 owner，不推断声纹身份，也不自动变成长期家庭事实。工具成功后才确认修改完成。

## 运维与验证

将 `deepseek-search.mjs`、`family-tools.mjs` 与 `host.mjs` 和现有适配器一起部署；只替换私密人设中的旧能力说明，不覆盖家庭数据。发布前备份配置与代码，清单文件随私密状态正常备份。回滚不得覆盖发布后产生的清单或记忆。

执行 `(cd server && npm test)` 与 `node --test firmware/simulator/*.test.mjs`。真实服务验收使用独立回环 Gateway 和 owner，配置、数据、状态均隔离；生成音频丢弃，不接管设备。模型验证与板端真人听感分开记录。搜索费用与 Live 费用独立：[DeepSeek 官方说明](https://api-docs.deepseek.com/zh-cn/guides/search/)。上游能力：[搜索](https://github.com/QwenAudio/qwen-audio-agent/blob/v2.0.1/docs/guides/web-search.zh.md)、[清单](https://github.com/QwenAudio/qwen-audio-agent/blob/v2.0.1/docs/guides/notes-reminders.zh.md)。

2026-10-20 验收：27 项服务端检查、23 项模拟器回归通过。分阶段真实模型验证了中英文搜索（各 5 条引用）、公开网页阅读（每页 1 条引用）、清单创建、名称歧义、Gateway 重启保留、移除／删除及搜索失败时如实回答。最终将 `web_search`、`fetch_url` 和 `notes` 的 Google 声明设为 `BLOCKING`，短工具取得结果后再回答，并以该配置重新验证了 5 个真实场景。实际网络／账号失败保留为失败记录，恢复后才确认成功。发布健康检查确认检索与清单开启、后台 Agent 关闭，家庭记忆／资料文档未改变。隔离 Gateway 已停止并移除其凭证。本轮未操作或烧录板子，板端真人听感仍待验证。
