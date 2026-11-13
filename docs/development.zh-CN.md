# 开发与测试

[English](development.md) | **简体中文**

## 准备适当的环境

固件构建需要 ESP-IDF 5.5.5 和 ESP32-S3 工具链。桌面测试需要 C++17 编译器、Python、OpenSSL 开发头文件与库、Node.js 24+。激活 IDF，使 `IDF_PATH` 可以定位 cJSON。模拟器独立管理锁定的 npm 依赖：

```sh
(cd firmware/simulator && npm ci --ignore-scripts)
```

macOS 按需要将 `OPENSSL_PREFIX` 指向 OpenSSL 安装目录；Linux 安装对应开发包。训练依赖另行管理，普通运行时开发不需要 TensorFlow 或服务密钥。

## 目录职责

| 目录 | 适合修改的内容 |
|---|---|
| `firmware/components/pikoo_core` | 配置、协议标准化、会话和工具行为 |
| `firmware/main` | ESP TLS、NVS、音频、唤醒和板级驱动 |
| `firmware/simulator` | 原生测试驱动和离线双眼预览 |
| `tools` | 安装、配置、打包与检查 |
| `examples` | 只含占位值的公开配置 |
| `models/hi-pikoo` | 已审核的模型、策略及元数据 |
| `training` | 语料校验、训练与评估 |
| `hardware/enclosure` | 可打印零件和双语装配说明 |

## 执行静默检查

```sh
bash tools/check.sh
PIKOO_SANITIZE=1 bash tools/test-local-agent.sh --services
bash tools/test-local-agent.sh --network --cycles 100
bash tools/test-local-agent.sh 28800
```

`check.sh` 覆盖公开内容与链接、原生音频/会话/双眼、预览和装配指南、生成规划器、启用 sanitizer 的服务测试及 Python 工具。单独服务命令适合开发时定向验证，完整检查通过且没有修改后无需重复运行。网络夹具使用假凭证和本地 TLS。最后一条加速处理 28,800 秒合成 PCM，不代表真实耗时八小时的板上运行。这些测试不打开麦克风或扬声器。

预览双眼：执行 `bash tools/start-dualeye.sh`，访问 `http://127.0.0.1:8793/dualeye`；用 Ctrl+C 或 `bash tools/stop-dualeye.sh` 停止。预览验证渲染，不验证真实服务。

## 扩展适配器或工具

1. 定义协议或工具契约、必填字段、限制和错误行为。
2. 在共享配置层与 Python 设置校验器中显式添加协议支持。
3. 在适配器内标准化响应，不把供应商解析放入存储或音频代码。
4. 同时注册工具结构和执行器，修改数据前检查全部参数。
5. 保持任务取消、有界轮次/结果与调用 ID 去重。
6. 验证成功、畸形数据、HTTP 分片、鉴权/限流失败、取消及迟到结果；写操作还需验证存储恢复。
7. 更新配置示例和中英文文档。

不要从域名推断协议，也不要记录原始服务响应、请求头、配置或快照。检索文本只作为数据，网络工作不能阻塞实时音频任务。

## 验证固件修改

通过 `tools/build-device.sh` 构建，记录镜像大小、分区余量和静态内存。板上在语音与后端并发时测量堆低水位、最大连续块、栈余量、队列峰值和 I²S 错误，使用临时数据验证重启读回与取消。声学、断电和长稳必须有实机证据，应报告时长与负载而不是笼统写“通过”。

训练 Python 检查需要单独安装 `training/requirements.txt`，再执行 `PIKOO_CHECK_TRAINING=1 bash tools/check.sh`。服务商生成和语料采集是明确执行的独立活动，不是普通检查的副作用。

[架构](architecture.zh-CN.md) · [发布流程](release.zh-CN.md) · [贡献指南](../CONTRIBUTING.zh-CN.md)
