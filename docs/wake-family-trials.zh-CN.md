# 家庭唤醒测试

[English](wake-family-trials.md) | 简体中文

更新于 2026-11-03。这些工具为后续验收做准备，本次没有进行家庭测试。当前冻结候选
尚未完成全新独立 TEST 和 ESP32 运行验收；家庭参与继续按用户要求稍后安排。

`tools/wake-trials.py` 复用本项目已注册的 USB 监测进程，不另开串口、不录音、不训练、
不烧录、不改音量、不注入模拟唤醒。正式测试使用自然连读的 **Hi, Pikoo**，接受
piku／piko；历史中文提示仅保留在显式诊断模式中。

## 正式测试前

先完成封存的六组独立 TEST。正式入口要求 150 条完整报告及已完成的消耗标记、冻结
模型与策略，以及实际安装校验清单。清单须明确包含 `offline_qualified: true`、
`firmware_version`、`app_sha256`、`model_sha256` 和 `policy_sha256`。
编译镜像不能代替安装校验。报告须满足六组各 20 条、每组至少 18 次命中、零误触发／
提前触发及 800ms 延迟门槛；成人子集、部分报告会在访问 USB 前被拒绝。

固件在原有诊断记录中增加模型及策略文件摘要。测试全程核对这些摘要与版本；不带
身份字段的旧镜像不能产生正式验证结果。

真人明确准备好后，逐人、逐场运行。以下变量须指向本机私密文件：

```sh
python3 tools/wake-trials.py \
  --port "$PORT" --socket "$MONITOR_SOCKET" --status-file "$STATUS_FILE" \
  --firmware-manifest "$PRIVATE/verified-install.json" \
  --wake-model "$PRIVATE/hi_pikoo.tflite" --wake-policy "$PRIVATE/wake-policy.json" \
  --sealed-test-report "$PRIVATE/independent-test-report.json" \
  --tester child --tester-id child-1 --session-index 1 --trials 20 \
  --output "$PRIVATE/child-1-session-1.json"
```

私密目录放在仓库外。不传 `--ready` 时保留交互式准备提示；阅读说明不会自动倒计时
或采音。四人分别使用 `adult-1`、`adult-2`、`child-1`、`child-2`，场次为 1 或 2。
成人／儿童身份由用户指定，不根据声音猜测。

## 结果如何确认

电脑讲解期间设备静音，开启离线测试隔离后才恢复本地唤醒。开始信号是终端绿色文字，
不播放可能误触发的提示音；提示之前的命中不能算目标词成功。身份变化、隔离失效、
重启、上传计数增长、推理错误或丢帧都不能产生通过结果。中断清理先静音，再解除
隔离；静音失败就保留隔离。显式 `--diagnostic` 短测永不认定正式通过，结束保持静音。

即使机器计数达到 18/20，也先标为**待人工确认**。观察者须事后确认每次独立完整
喊一遍、没有成人跟读或重复呼叫、距离一米。私密观察 JSON 包含：

```json
{
  "report_sha256": "原始测试JSON文件的SHA256",
  "tester_id": "child-1",
  "session_index": 1,
  "observed_at_unix": 0,
  "human_statement": "填写本轮结束后实际观察到的情况。",
  "all20_independent_complete_targets_once": true,
  "no_adult_follow_or_repeated_calls": true,
  "distance_m": 1
}
```

摘要及时间填写真实值，观察时间须晚于测试结束；不能确定的项目不要填写肯定值。
`confirm` 另存带人工确认的文件，不改原始逐次结果：

```sh
python3 tools/wake-trials.py confirm \
  --report "$PRIVATE/child-1-session-1.json" \
  --observation "$PRIVATE/child-1-session-1-observation.json" \
  --output "$PRIVATE/child-1-session-1-confirmed.json"
```

最后以 `family --run 文件` 重复八次，再指定 `--output 文件` 汇总。要求四人两场、
八份独立且不重叠的测试，同一校验过的模型／策略／程序，每场至少 18/20。
家庭两场通过不代表另外的八小时误唤醒及 ESP32 资源验收已通过。
`confirm` 和 `family` 仅处理文件，不使用 USB 或音频。
