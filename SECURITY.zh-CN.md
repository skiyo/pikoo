# 安全说明

[English](SECURITY.md) | **简体中文**

敏感漏洞请使用 [GitHub 私密漏洞报告](https://github.com/skiyo/pikoo/security/advisories/new)，不要在公开 Issue 放家庭部署攻击信息或凭证。说明版本、影响与最小脱敏复现。

禁止公开模型 Key、配对片段、设备凭证、NVS、家庭记忆和源录音。泄露凭证须在所属服务撤销。使用可信 HTTPS/WSS、独立可撤销设备凭证、来源白名单、本机管理与代理接口。

开发固件未启用安全启动或 Flash/NVS 加密，物理访问可能读取设备凭证。待机唤醒在本地处理；在线音频通过 Gateway 发给配置的外部 Provider。官网本地眼睛动画不访问麦克风。
