#!/usr/bin/env python3
"""Render reproducible design sheets from the same native core (optional Pillow dependency)."""
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1]
output = root / 'docs/images/dualeye'
output.mkdir(parents=True, exist_ok=True)
states = [
 ('boot', '启动', '闭眼启动 · 温暖环形提示'),
 ('idle', '待机', '未唤醒闭眼 · 轻微呼吸'),
 ('connecting', '连接', '睁大眼睛 · 暖色连接提示'),
 ('listening', '倾听', '视线居中 · 响应输入音量'),
 ('thinking', '思考', '轻微向上看 · 低幅度运动'),
 ('speaking', '说话', '播放音量驱动 · 平滑变化'),
 ('muted', '静音', '闭眼静音 · 降低饱和度'),
 ('offline', '离线', '低幅度提示 · 原因见网页'),
 ('occupied', '会话占用', '侧向视线 · 等待明确接管'),
 ('auth_error', '凭证错误', '克制提示 · 需要重新配对'),
 ('happy', '开心', '弯弯笑眼 · 演示表情'),
 ('drowsy', '困倦', '低垂眼睑 · 演示表情'),
 ('curious', '疑惑', '上看侧瞥 · 演示表情'),
]
font_path = next((p for p in ['/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'] if Path(p).exists()), None)
def font(size):
 return ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
sheet = Image.new('RGB', (1280, 1100), '#f8f5ed')
d = ImageDraw.Draw(sheet)
d.text((36, 26), 'pikoo / 双眼状态设计', font=font(32), fill='#40382e')
d.text((36, 80), '240 × 240 / 眼 · RGB565 · 同一套 C++ 绘制核心 · 固定时间 1000ms / seed 42 / 音量 0.3', font=font(16), fill='#897762')
for index, (name, title, subtitle) in enumerate(states):
 ppm = root / f'firmware/build-host/{name}.ppm'
 subprocess.run([str(root / 'firmware/build-host/pikoo-eyes'), '--snapshot', str(index), '1000', str(ppm)], check=True)
 image = Image.open(ppm).copy()
 image.save(output / f'{name}.png')
 x, y = 24 + index % 4 * 310, 132 + index // 4 * 235
 d.rounded_rectangle((x, y, x+300, y+222), 18, fill='#efe9dc')
 d.text((x+16, y+13), f'{index+1:02}  {title}', font=font(17), fill='#63533f')
 # Two circular surfaces, retaining the core's unmodified full-resolution snapshots separately.
 for side in range(2):
  eye=image.crop((side*240, 0, (side+1)*240, 240)).resize((124,124), Image.Resampling.LANCZOS)
  mask=Image.new('L', (124,124));ImageDraw.Draw(mask).ellipse((0,0,123,123), fill=255)
  sheet.paste(eye, (x+17+side*141,y+49), mask)
 d.text((x+16,y+184), subtitle, font=font(12), fill='#958168')
for i, (title, lines) in enumerate([
 ('温暖的色彩', ['暖白眼白  /  琥珀虹膜', '深棕瞳孔  /  小面积高光']),
 ('自然的节奏', ['更新目标 20fps  /  过渡 220ms', '眨眼 150ms  /  间隔 3–5 秒']),
 ('清楚的边界', ['通话状态优先于演示表情', '不推断身份或对话情绪']),
]):
 index=13+i;x,y=24+index%4*310,132+index//4*235
 d.rounded_rectangle((x,y,x+300,y+222),18,fill='#eee5d4')
 d.text((x+20,y+38),title,font=font(21),fill='#756044')
 for j,line in enumerate(lines):d.text((x+20,y+92+j*33),line,font=font(14),fill='#958168')
sheet.save(output / 'states.png')
print(output / 'states.png')
