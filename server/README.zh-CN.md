# Pikoo Gateway

端侧 Agent 只需要 Mihomo。本页保留旧 Gateway 的部署与回滚说明，端侧配置见[本地 Agent](../docs/local-agent.zh-CN.md)。

[English](README.md) | **简体中文**

## 环境与启动

需要 Node.js 24+、私密持久目录、HTTPS/WSS 反向代理，以及 `gpt-live-1`、`gpt-6.1-terra` 的 OpenAI API 权限。搜索可配置 DeepSeek Key。运行时固定 `qwen-audio-agent@2.0.1`。外部模型可能收费，安装依赖不会自动提供密钥。

```sh
(cd server && npm ci --ignore-scripts)
(cd server && npm test)
mkdir -p "$HOME/.config/pikoo/qwaudio"
chmod 700 "$HOME/.config/pikoo/qwaudio"
cp server/deploy/config.env.example "$HOME/.config/pikoo/qwaudio/config.env"
chmod 600 "$HOME/.config/pikoo/qwaudio/config.env"
```

编辑仓库外的私密配置：OpenAI Key、可选搜索 Key、HTTPS 来源及服务设置。家庭资料从 `server/persona/` 模板单独填写，升级不得覆盖真实家庭资料。环境变量必须在加载 `host.mjs` **之前**生效：

```sh
QWAUDIO_CONFIG_DIR="$HOME/.config/pikoo/qwaudio" \
node --env-file="$HOME/.config/pikoo/qwaudio/config.env" server/host.mjs
```

服务器部署使用独立用户和 systemd。按自己的路径修改 `server/deploy/` 模板；示例假定 server 文件直接安装在 `/opt/pikoo/app/`，并需加上指向私密配置的 `EnvironmentFile`。Nginx 把 HTTPS/WSS 转到 127.0.0.1:3101，保留 WebSocket Upgrade。限制来源，代理及管理接口不对公网开放；以实际服务用户验证 TLS 与模型出口。优先域名证书；IP 证书需维护短周期自动续签。

## 设备配对

Gateway 运行时，使用相同私密配置目录：

```sh
QWAUDIO_CONFIG_DIR="$HOME/.config/pikoo/qwaudio" \
server/node_modules/.bin/qwenaudio gateway pair --name living-room --endpoint https://YOUR_HOST --json
```

输出包含**私密设备凭证**，只能保存在受保护文件。相同运行环境下用 `gateway devices --json`、`gateway revoke DEVICE_ID` 列出和撤销。设备只填自己的 endpoint、token，不填模型 Key；管理通过 SSH。

## 模块配合

`host.mjs` 组合运行时；`openai-live.mjs`、`live-runtime.mjs` 处理原生 Live、16kHz 音频、委派和播放；`openai-terra.mjs`、`live-idle.mjs` 处理推理、互动分类和空闲；`context-runtime.mjs`、`context-learning.mjs` 负责文字续接、摘要和记忆队列；`family-tools.mjs`、`deepseek-search.mjs` 负责网页、搜索与清单；`live-usage.mjs` 保存私密用量记录。

[Live](../docs/openai-live.zh-CN.md) · [记忆](../docs/context-memory.zh-CN.md) · [工具](../docs/family-tools.zh-CN.md) · [运维](operations.zh-CN.md)

## 备份与诊断

停止 Gateway，备份完整私密配置/状态目录及部署版本，再启动。owner、设备凭证、近期文字、摘要、记忆、清单、调用去重记录、学习队列和用量应一起保存。在隔离目录演练恢复；程序回滚不得覆盖新家庭数据。

`GET /api/pikoo/live-status` 只经 SSH/本机查看，不额外对公网开放。分别检查鉴权、额度、代理/TLS、设备上行与播放缓冲；HTTP 健康不等于声音质量通过。
