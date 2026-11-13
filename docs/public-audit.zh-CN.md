# 公开仓库检查

[English](public-audit.md) | **简体中文**

原创源码与文档采用 Apache-2.0，模型权重及第三方组件另有条款。

## 技术检查

`tools/check-public-repo.py` 检查已跟踪文件、示例占位值、本地 Markdown 链接与模型校验和。CI 使用 Gitleaks 脱敏扫描历史。禁止提交凭证、设备备份、录音或用户数据；扫描通过不等于保证能识别所有可能的秘密信息。

## 模型权限

推理权重和训练检查点保存在 [models/hi-pikoo](../models/hi-pikoo/README.md)。[ChildMandarin 访问条款](https://huggingface.co/datasets/BAAI/ChildMandarin)要求研究衍生物向研究组外分发前取得书面许可，但未明确单列训练权重。目前模型分发书面许可待确认，Git 中可以下载不代表授权已满足。

[distribution-status.json](../models/hi-pikoo/distribution-status.json)将状态绑定至模型摘要。取得并记录许可依据前，公开模型与固件打包被阻止。源码 Apache-2.0 不覆盖上游限制；非商业模型条款也不属于 OSI 定义的开源许可证。保留[数据来源](../models/hi-pikoo/ATTRIBUTION.md)和依赖许可。

[工程验证](release.zh-CN.md)与分发权限分开判断。
