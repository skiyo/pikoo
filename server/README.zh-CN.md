# Pikoo Agent 服务端

[English](README.md) | **简体中文** · [项目首页](../README.zh-CN.md)

服务端连接 Pikoo 设备与实时语音大模型，管理会话、家庭记忆和已配置的工具。它在固定的 `qwen-audio-agent@2.0.1` 运行框架上组装 Pikoo 适配，与负责生成语音的大模型分工不同。

本文面向服务端开发和运维。只想看双眼效果，先运行[离线模拟器](../docs/getting-started.zh-CN.md)。主机安装、证书、配对、备份和恢复的详细命令集中在[主机运维指南](operations.zh-CN.md)。

## 外壳打印资料

三件小猫外壳的原始 STL、打印顺序、装配图解与验收表见[外壳目录](../hardware/enclosure/README.zh-CN.md)。项目家庭已打印、装配验证并在家使用通过（2026-10-27，用户反馈）；这份硬件反馈与本模块的软件/研究检查分别记录。

## 模块分工

| 文件或目录 | 职责 |
|---|---|
| `host.mjs` | 组装运行框架和 Pikoo 适配 |
| `google-live-compat.mjs` | Gemini Live 事件和工具兼容、活动检测选项与连接时间信息 |
| `context-runtime.mjs`、`context-learning.mjs`、`memory-timeout.mjs` | 近期上下文、持久后台整理、摘要及文本调用期限 |
| `deepseek-search.mjs`、`family-tools.mjs` | 已配置的搜索、公开网页阅读和家庭清单 |
| `companion-runtime.mjs`、`silence-output.mjs` | 可选的选择性回应与原生静默标记处理 |
| `provider-check.mjs`、`time-context.mjs` | Provider 诊断与服务端生成的时间信息 |
| `deploy/`、`persona/` | 脱敏部署和人设模板 |
| `reports/` | 带日期的验证证据，不代表服务当前健康状态 |

## 安装与检查

需要 Node.js 24+，在仓库根目录执行：

```sh
(cd server && npm ci --ignore-scripts)
(cd server && npm test)
```

测试不需要 Provider 凭证。在 `server/` 内执行 `npm start` 会运行 `host.mjs`；真实服务还需要独立的私密运行配置、模型服务凭证和设备 token。对外开放网关前先按运维指南部署。

历史主机环境使用 Alibaba Cloud Linux 4 和独立 `pikoo` 用户。`/opt/pikoo/app/`、`/var/lib/pikoo/qwaudio/` 属于部署约定，不是 `npm ci` 自动创建的目录。`203.0.113.10` 等示例地址必须替换。

## 配置真实服务

1. 以 [`deploy/config.env.example`](deploy/config.env.example) 准备私密配置，通过 `QWAUDIO_CONFIG_DIR` 选择目录。`config.env` 仅允许所有者读取，家庭人设另行填写。
2. 选择兼容的实时 Provider。当前适配面向 Gemini Live，记忆提取和摘要使用文本模型。更换固定运行框架或 Provider 前先检查兼容性。
3. 按实际主机安装 systemd 和 Nginx 模板，验证证书信任、WebSocket 转发及服务用户的网络出口，再签发设备凭证。
4. 每台设备使用可单独撤销的 token，将得到的私密配置交给模拟器或板卡。

模型 Key 和家庭资料留在服务端；设备或浏览器配置只包含自身连接地址与设备凭证。代理控制端口和内部网关不向公网开放。[主机运维指南](operations.zh-CN.md)保留具体命令及恢复顺序。

## 记忆、工具与回应策略

| 问题 | 对应说明 |
|---|---|
| 当前话题恢复、长期记忆、历史回顾和重试边界 | [上下文与记忆](../docs/context-memory.zh-CN.md) |
| 搜索、公开网页阅读、家庭清单及服务配置 | [家庭工具](../docs/family-tools.zh-CN.md) |
| 何时说话、预期静默和主动开启的陪伴模式 | [安静陪伴模式](../docs/companion.zh-CN.md) |
| 结束、休眠、重连与播放取消 | [会话生命周期](../docs/conversation-lifecycle.zh-CN.md) |

部署模板保持 `AGENT_PROTOCOL=none`；Pikoo 的 AI Agent 定位不要求再开启一个独立后台 Agent。搜索使用已配置的适配器。MCP 是扩展接口，不表示天气、智能家居或 MCP OAuth 服务默认启用；新增流程前仍需复核依赖和安全边界。

当前人设策略使用普通话回答。文档中英文切换不代表语音输出也支持双语。

## 运维与验收

私密配置、记忆、历史、话题摘要和后台整理队列一起备份。先在隔离目录演练恢复，回退代码时不能覆盖更新的家庭数据。配对输出包含凭证，应保存到受保护的文件，不能贴进 Issue 或提交。

安装后的 `pikoo-admin` 通过 SSH 提供健康检查、撤销设备、重启和备份。软件测试或模型调用成功不能代替设备听感和长期运行验收，参见[验证记录](../docs/validation-summary.zh-CN.md)及[安全说明](../SECURITY.zh-CN.md)。
