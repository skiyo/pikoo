# 部署与运维

[English](README.md) | **简体中文**

按 [服务端说明](README.zh-CN.md)安装依赖、私密配置并签发设备凭证。生产使用独立 `pikoo` 用户；程序、Node 与持久目录权限分离。

## systemd 与网络

模板位于 `deploy/`。修改可执行文件和目录，添加 `EnvironmentFile=/var/lib/pikoo/qwaudio/config.env`，确认 `QWAUDIO_CONFIG_DIR` 一致。程序目录只读，私密持久目录可写。没有使用 mihomo 时移除对应服务依赖；如需代理，应覆盖实际服务用户的 HTTP 和 WebSocket 请求，并只在本机监听。

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now pikoo
sudo systemctl status pikoo --no-pager
curl -fsS http://127.0.0.1:3101/api/health
```

Nginx 配置中替换示例地址，设置可信证书和 WSS Upgrade，核对来源白名单。开放 SSH、HTTPS 及证书验证需要的 HTTP；3101 和代理端口不开放。确认 SSH 可用后再修改防火墙。凭证、日志和 NVS 不进入 Web 目录。

## 备份、升级和回滚

停止服务后备份完整配置/状态目录、当前 server 源码、锁文件和部署模板。升级在新目录运行 `npm ci --ignore-scripts` 与软件回归，再切换程序路径；保留旧目录以便回滚。不要用旧备份覆盖升级后新产生的记忆和清单。恢复先在隔离端口测试。

`pikoo-admin` 是可选模板，安装前修改地址和路径；其备份路径具有部署假设，不能盲目套用。手工备份应包含整个当前 server 发布目录，而不是只挑个别适配器。

## 问题定位

- CONNECTING：查看 Gateway、上游 Live/Terra 鉴权、额度和 TLS/代理错误。
- 卡音：对照上游分片间隔、设备缓冲、Wi-Fi 和播放状态，不能只凭动画判断。
- 不记得：核实家庭 owner、会话标识、持久目录与学习队列失败状态。
- 不告别：检查转写、互动分类和播放排空回报。
- 证书：验证信任和自动续签，不能关闭客户端证书校验。

[安全说明](../SECURITY.zh-CN.md) · [发布检查](../docs/release.zh-CN.md)
