# 服务器复现与运维

历史部署使用 Alibaba Cloud Linux 4、独立 `pikoo` 用户、Node 24.21.0、固定 `qwen-audio-agent@2.0.1`。仓库仅含脱敏模板，所有 `203.0.113.10` 都是示例地址，必须替换。现网的家庭资料、SSH Key、Google Key、设备凭证和代理节点不在这里。

## 目录及启动

- `/opt/pikoo/node/`：官方 Node.js 24 LTS，验证官方发布校验和后安装。
- `/opt/pikoo/app/`：本目录的程序及 `npm ci --ignore-scripts` 安装结果。
- `/var/lib/pikoo/qwaudio/`：权限受保护的配置、身份、记忆、摘要和状态。
- `/etc/mihomo/config.yaml`：私有代理资料；仅接管 `pikoo` 的实际 UID，控制端口/混合端口仅本机。

以 root 建立用户和目录，复制 `host.mjs`、`google-live-compat.mjs`、`memory-timeout.mjs`、`provider-check.mjs`、package 文件到应用目录并安装。将 `deploy/config.env.example` 填入 `QWAUDIO_CONFIG_DIR/config.env`，权限 600、归属 pikoo。家庭人设从 `persona/*.example` 另行填写，真实内容不提交。所有持久路径以固定版 `qwenaudio config` 输出和当前配置为准，不直接覆盖旧目录。

将 `deploy/` 中 systemd 模板安装到 `/etc/systemd/system/`，Nginx 配置安装到对应目录；按主机实际 UID/地址更新 mihomo 和防火墙模板。代理节点务必验证 TLS；模板默认不跳过证书校验。根用户的 SSH/系统流量不应被 TUN 全局接管。

```sh
systemctl daemon-reload
systemctl enable --now mihomo
systemctl enable --now pikoo
# 代理与 Google 调用从 pikoo 用户运行
/usr/local/sbin/pikoo-admin check
```

`pikoo-admin` 安装到 `/usr/local/sbin/`，替换示例地址。先确认控制台/安全组保持 SSH 可用，再开启防火墙。公网仅 SSH、80、443；3101、7897、9090 不对公网开放。Nginx 保留 Host、来源和 WebSocket Upgrade，Origin 使用固定 HTTPS 地址。不要把私有 `config.env` 放入 Web 根目录。

## IP HTTPS 证书

使用 Certbot ≥5.4 的 webroot/IP/shortlived 流程；先用 staging 测试，正式证书路径填入 Nginx。参考 [Let’s Encrypt 官方说明](https://letsencrypt.org/2026/03/11/shorter-certs-certbot)。示例操作参数需与已安装版本 `certbot --help all` 对照：

```sh
certbot certonly --staging --webroot -w /var/www/acme --ip-address YOUR_IP --preferred-profile shortlived
# 测试成功后对同一 IP 申请正式证书（去掉 staging，按 Certbot 提示区分证书 lineage）。
certbot renew --dry-run
```

6 天证书不能按普通 90 天证书维护。安装每 6 小时的续签 timer；在 `/etc/letsencrypt/renewal-hooks/deploy/` 安装 root 拥有的脚本，内容为 `nginx -t && systemctl reload nginx`。正式证书加载后再启用 HTTPS，验证 SAN、系统 CA 信任及外网 WSS；不使用自签证书跳过验收。

## 配对、备份与恢复

```sh
pikoo-admin pair --name living-room --endpoint https://YOUR_IP --json
pikoo-admin devices --json
pikoo-admin revoke DEVICE_ID
pikoo-admin status
pikoo-admin restart
pikoo-admin backup
```

`pair` 的输出包含私密访问凭证，保存到权限 600 的仓库外文件，禁止贴到 issue。设备撤销后实际验证 HTTP/WSS 401。管理只通过 SSH；不要开放远程管理接口。

备份命令短暂停止 Agent 后打包状态、配置、证书及适配代码，再恢复服务。备份本身含敏感信息。恢复到隔离目录检查清单和所有者，再在相同固定版本环境中停服务、还原文件、恢复权限、启动并重测；不直接把未经检查的 tar 覆盖系统。先在备用环境演练，避免覆盖活动家庭记忆。

清理测试数据时先按 session/owner 筛选，使用系统提供的记忆编辑接口删除测试事实、摘要和对应会话。不要直接清空全家 MEMORY。历史会话、审计、备份可能仍有旧内容；完整遗忘需独立处理这些存储。

## 兼容适配与故障定位

`google-live-compat.mjs` 修正 Gemini 工具 Schema、输入转写完成事件及插话事件顺序，原版包文件不改写。`memory-timeout.mjs` 在组装入口仅替换长期记忆模块的文本调用，把固定 10 秒上限改为默认 45 秒（可配置 1–60 秒）；保留原版纠错/删除后的学习边界。**会话摘要的独立调用仍沿用原版上限**。调整上限不等于长会话自动记忆已重新验收。

先区分网络超时、地区限制、凭证错误和额度不足。地区错误先检查实际运行 UID 的代理出口，不靠盲目轮换模型解决。未开通付费，不自动切换收费服务。查看日志前注意其中可能有会话内容；提交 issue 前脱敏。

2026-10-13 `npm audit` 报告上游依赖 MCP SDK 1.30.0 的 OAuth 凭证泄露风险（已修复版本 ≥1.31.0，但固定上游包未提供自动修复）。当前配置 `AGENT_PROTOCOL=none` 且未配置 MCP OAuth 客户端，不启用受影响流程。升级依赖前做适配/记忆回归，不宣称审计零告警。
