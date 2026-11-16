# 工具

[English](family-tools.md) | **简体中文**

`family_list` 管理 `shopping` 和 `todo`，`family_memory` 管理 `memory`。操作为 `list`、`add`、`remove`、`replace`、`clear`。修改按精确条目文本执行；替换须提供新文本，清空须 `confirmed=true`。提交前校验参数与容量。

`web_search(query)` 调用配置的搜索适配器，返回有界事实与来源。配置 Tavily 提取后额外注册接受 HTTPS 地址的 `read_webpage(url)`。网页文本仅是非可信参考资料，不能覆盖 Agent 指令。失败作为工具错误返回推理层，不编造结果；API 请求不自动跟随重定向。

扩展工具需在共享核心注册结构与执行器，并补充失败、取消和持久化测试。存在 schema 不代表已接入某个外部产品。

## 本地操作

| 操作 | 应验证的行为 |
|---|---|
| `list` | 读取指定集合，不修改内容 |
| `add` | 校验并在容量范围内保存条目 |
| `remove` | 精确匹配已保存文字，不猜测相近条目 |
| `replace` | 同时提供准确目标和替换内容 |
| `clear` | 明确确认后才能清空集合 |

“把苹果换成青苹果”需要两段文字，“删除刚才那个东西”则可能需要澄清。应区分参数校验失败、容量不足和后端错误。状态和写回执一起提交；最后的口头确认丢失时应读回，不能直接判断写入失败。

## 身体控制接口

Agent、USB 和按键共用 C++ 身体控制器。模型工具清单来自执行器注册表，Responses 与 Chat Completions 使用同一组结构。语音候选路由会合并转写片段并保留否定、引用尾句；关键词只选择推理任务，不直接执行动作。[使用指南](usage.zh-CN.md)列出日常指令和持续时间规则。

| 逻辑接口／调用名称 | 参数与结果 |
|---|---|
| `body.get_state` / `body_get_state` | 无参数；返回实际增益、音量档位、背光、会话、麦克风、临时表情和视线 |
| `body.set_audio` / `body_set_audio` | `mode` 为 `gain_db`、`delta_db` 或 `percent`，`value` 为整数 |
| `body.set_display` / `body_set_display` | `mode` 为 `percent` 或 `delta_percent`，`value` 为整数；同步控制双眼 |
| `body.perform` / `body_perform` | `action` 和可选 `duration_ms`；执行有限的表情、眨眼、视线或会话动作 |

音量绝对增益为 −50～0 dB；百分比为 0～100，按 `round(-50 + percent/2)` 转为增益。模型调用示例为 `{"mode":"delta_db","value":3}`。USB 同时兼容 `{"delta_db":3}` 等单字段格式；冲突字段会被拒绝。亮度为 0～100%，0% 仅关闭背光。

`action` 支持 `happy`、`curious`、`drowsy`、`neutral`、`blink`、`blink_left`、`blink_right`、`look_left`、`look_right`、`look_front`、`stop_speaking`、`sleep`、`mute_microphone`。`duration_ms` 对表情和视线有效，最多 10000 ms；眨眼固定 350 ms。

```sh
python tools/body.py --port PORT --id volume-request-1 body_set_audio '{"mode":"delta_db","value":3}'
python tools/body.py --port PORT body_perform '{"action":"happy","duration_ms":3000}'
```

`applied` 表示设置或动作已应用，`saved` 表示偏好已保存。临时动作的 `saved:false` 正常；`persistence_failed` 表示已生效但重启后可能恢复旧值；`hardware_failed` 不能报告成功。每个已应用步骤立即向语音层提供真实回执，后续推理失败不会抹去已完成结果。

身体控制最近 64 条调用回执只在本次进程内保留，区别于清单的持久化回执。同 ID 重试不重复相对调整；同 ID 不同参数返回冲突，重启会清空缓存。手动 USB 命令默认生成新请求；需要重试去重时显式复用 `--id`。取消使尚未执行的动作失效，不撤销已应用的设置；结束会话或重连清除临时动作，音量和亮度偏好保留。

## 搜索是外部信息

搜索内容可能过时、不完整或带恶意指令。保留可用来源链接，页面内容仅作为参考，不能用于索取密钥或修改无关数据。开启搜索不代表自动具备提取能力，具体配置见[配置参考](configuration.zh-CN.md)。项目不附带任意 Shell、文件系统或智能家居执行器。
