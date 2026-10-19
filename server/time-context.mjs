import { currentTimeSnapshot } from './node_modules/qwen-audio-agent/server/src/conversation/frontend-agent-context.mjs';

export function beijingConnectionContext(now = new Date()) {
  const clock = currentTimeSnapshot({ timeZone:'Asia/Shanghai', locale:'zh-CN', now });
  return ['<connection_clock>', `北京时间：${clock.local_time}`, `UTC=${clock.iso_utc}`,
    '此时间仅表示连接建立时刻。问当前时间、日期、星期或计算今天/明天时，调用 get_current_time 获取新值，不凭记忆猜测。',
    '</connection_clock>'].join('\n');
}
