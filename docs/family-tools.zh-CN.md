# 工具

[English](family-tools.md) | **简体中文**

`family_list` 管理 `shopping` 和 `todo`，`family_memory` 管理 `memory`。操作为 `list`、`add`、`remove`、`replace`、`clear`。修改按精确条目文本执行；替换须提供新文本，清空须 `confirmed=true`。提交前校验参数与容量。

`web_search(query)` 调用配置的搜索适配器，返回有界事实与来源。配置 Tavily 提取后额外注册接受 HTTPS 地址的 `read_webpage(url)`。网页文本仅是非可信参考资料，不能覆盖 Agent 指令。失败作为工具错误返回推理层，不编造结果；API 请求不自动跟随重定向。

扩展工具需在共享核心注册结构与执行器，并补充失败、取消和持久化测试。存在 schema 不代表已接入某个外部产品。
