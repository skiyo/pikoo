# 身体控制

2.0.0 修复了模型参数冲突和语音转交、回报链路。身体设置的模型参数使用明确的 `mode`、`value`；USB 保留原有单字段格式。

左右方向按人面对 Pikoo 屏幕时的视角定义。板级显示映射负责对应实际屏幕接线和安装方向，单眼眨眼与水平视线使用同一约定。

## 自行进行真实语音测试

macOS 可通过电脑扬声器播放合成语音，让真实 Pikoo 麦克风接收：

```sh
python tools/generate-body-voice.py --out /tmp/pikoo-voice-fixtures
python tools/test-body-voice.py --port /dev/cu.usbmodem1101 --audio-dir /tmp/pikoo-voice-fixtures --out /绝对路径/私有目录/voice-results.json
```

需要 Tingting、Samantha 系统语音，并让 Pikoo 清楚听到电脑扬声器。通过条件包括实际结果正确、只有一次写入、回执已返回语音层。每三条会导出近期会话核对口头反馈；`*-history.private.json` 可能包含环境转写，必须保存在私有目录，不公开。

身体候选指令经过现有交流对象判断后，可由 ESP32 主动转交本地推理 Agent；关键词只用于路由，不直接执行硬件。否定、引用和含糊意图仍需判断。每个已执行步骤立即将真实回执送给语音层，同一任务可继续完成组合指令的其他步骤。最终反馈携带已执行回执，后续推理失败不能抹掉已经成功的硬件动作。

Pikoo 2.1 使用现有双眼屏、喇叭、麦克风和按键。身体工具在 ESP32 本地执行；语音理解需要已配置的 Live 与推理服务。没有摄像头、IMU、触摸或机械动作。

## 日常使用

先用“Hi, Pikoo”唤醒，再提出身体指令。可以用中文或英文。

| 指令 | 动作 |
|---|---|
| 声音大一点 / 小一点 | 增益增加 / 减少 3 dB |
| 音量调到一半 | 设置控制档位为 50%，对应 −25 dB 增益 |
| 眼睛亮一点 / 暗一点 | 双眼背光增加 / 减少 10 个百分点 |
| 眼睛亮度调到零 | 关闭背光；语音和麦克风状态独立 |
| 笑一笑 / 好奇一点 / 困一点 | 对应表情，默认 3 秒 |
| 眨一下眼 / 眨左眼 / 眨右眼 | 约 350 ms 的双眼或单眼动作 |
| 看看左边 / 看看右边 / 看着前面 | 屏幕视线变化，默认 2 秒 |
| 别说了 | 停止当前回复，仍可继续交流 |
| 休息吧 | 结束会话并回到唤醒待机 |
| 关闭麦克风 | 停止采集；长按现有按键或 USB `unmute` 恢复 |

音量档位不是声压比例，芯片增益不是耳边声压分贝。允许增益范围 −50～0 dB；0 dB 是数字增益上限。音量和背光只按明确指令修改并保存；临时动作到期后恢复会话表情。相同通道的新动作替换旧动作，指定表情或视线的持续时间最多 10 秒。麦克风关闭、连接和错误状态优先显示。

“笑一笑”默认无笑声；需要出声时明确说“笑出声”。双眼是显示器，视线变化不代表看到了物体。关闭背光后仍可唤醒并要求“把眼睛亮度调到百分之百”。

## USB 诊断

先关闭占用串口的其他监视器。Python 环境需要 `pyserial`。以下命令从仓库根目录运行，替换端口。

```sh
python tools/body.py --port /dev/cu.usbmodem1101 body_get_state
python tools/body.py --port /dev/cu.usbmodem1101 body_set_audio '{"delta_db":3}'
python tools/body.py --port /dev/cu.usbmodem1101 body_set_display '{"percent":70}'
python tools/body.py --port /dev/cu.usbmodem1101 body_perform '{"action":"happy","duration_ms":3000}'
python tools/body.py --port /dev/cu.usbmodem1101 body_perform '{"action":"blink_left"}'
```

正式接口的逻辑名称为 `body.get_state`、`body.set_audio`、`body.set_display`、`body.perform`。模型与 USB 的函数名使用下划线，如 `body_set_audio`。模型设置工具使用明确的 `mode` 与 `value`：例如 `{"mode":"delta_db","value":3}`。音量模式为 `gain_db`、`delta_db` 或 `percent`；亮度模式为 `percent` 或 `delta_percent`。USB 仍兼容单字段写法，多个冲突字段会被拒绝。百分比为整数 0～100，音量百分比按 `round(-50 + percent/2)` 转为增益。

`body_perform.action` 支持 `happy`、`curious`、`drowsy`、`neutral`、`blink`、`blink_left`、`blink_right`、`look_left`、`look_right`、`look_front`、`stop_speaking`、`sleep`、`mute_microphone`。`duration_ms` 对表情和视线有效，眨眼固定 350 ms。

回执的 `applied` 表示硬件设置或临时动作已应用，`saved` 表示偏好已保存。临时动作 `saved:false` 属于正常现象。设置返回 `persistence_failed` 时本次已生效，但重启后可能恢复旧值；`hardware_failed` 时不能声称设置成功。查询返回实际增益、亮度、会话、麦克风及临时动作状态。查询不测量声压或实际光照。

同一调用 ID 在最近 64 条进程内回执中去重；重启会清空该缓存。相同 ID 配不同参数返回冲突。USB 手动命令每次视为新请求。取消和重连清除临时动作；音量与亮度保留。

## 开发与验证

激活 ESP-IDF 5.5.5 后执行：

```sh
bash tools/test-body.sh
bash tools/test-eyes.sh
bash tools/build-body-host.sh
python tools/body-preview.py --out /tmp/pikoo-body-preview
```

打开输出目录内的 `index.html`，点击按钮检查同一套 C++ 控制器生成的动作。该预览不代表真实背光、声学或硬件延迟。`tools/test-body-semantics.py --config /绝对路径/私有配置.json --out /tmp/semantic-results.json` 可选用真实推理服务检查 30 条直接指令和 6 条否定/引用指令，会消耗模型额度，只检查工具选择，不执行身体动作。

升级前备份完整 Flash 并校验；使用 `tools/device.py upgrade` 仅更新应用分区。不要向公开目录复制私有备份或服务配置。真机验收需观察双眼、试听播放、检查回声消除和中断，并连续测试 2 小时及 8 小时。未实际完成的项目必须保持待验收状态，参见 [验收记录](body-verification.md)。
