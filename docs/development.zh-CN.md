# 开发指南

[English](development.md) | **简体中文**

## 分层与扩展

`pikoo_config` 校验带版本的配置和完整地址；`LiveAgent` 实现语音协议与分类上下文；`BackendAgent` 管理有界模型与工具循环，适配器标准化 Responses、Chat Completions 与搜索结果；`HttpResponse` 增量解析有界 HTTP。ESP 网络工作线程使用校验证书的 TLS，可选 HTTPS CONNECT，把带令牌的结果交回会话线程。NVS 与板级接口不进入共享核心。

新协议显式注册，不按域名猜测；工具的结构与执行器一起增加。实时音频不等待网络，处理结果前先使已取消任务令牌失效。不记录请求头、原始 API 正文、完整配置或家庭快照。

## 静默检查

先激活 ESP-IDF，由 `IDF_PATH` 定位 cJSON。宿主需要 C++17、OpenSSL 开发库和 Python；macOS 可设置 `OPENSSL_PREFIX` 为 Homebrew OpenSSL 目录。

```sh
PIKOO_SANITIZE=1 tools/test-local-agent.sh --services
tools/test-local-agent.sh --network --cycles 100
tools/test-local-agent.sh 28800
(cd firmware/simulator && npm ci --ignore-scripts)
bash tools/check.sh
```

测试使用合成 PCM 和内存接收器，不打开音频设备。图形双眼预览与原生 Agent 模拟器分开。重编固件后，镜像及静态内存与桌面 CPU/RSS 分别报告；板上 TLS 并发、AEC 与听感须有实机证据，见[验证范围](release.zh-CN.md)。

可选 Python 训练测试使用独立训练环境。安装其 requirements 后运行 `PIKOO_CHECK_TRAINING=1 bash tools/check.sh`；固件运行时检查不依赖 TensorFlow。
