// Offline English/Chinese preview UI; no network translation.
const dictionary={
  "Pikoo · 双眼小伙伴": "Pikoo · Eye preview",
  "双眼预览": "Eye preview",
  "本机 C++ 绘制 · 无声演示": "Local C++ rendering · silent preview",
  "一个会听、会回应的小伙伴": "A hardware AI companion",
  "先见面，再一起长大。": "Meet Pikoo.",
  "温暖的琥珀眼睛，两块小小的圆屏。现在在电脑上试一试，板子到了再把它带到桌面。": "Explore the shared eye renderer on your computer before installing firmware.",
  "Pikoo 双眼预览": "Pikoo eye preview",
  "查看实际像素": "Actual pixels",
  "眼睛画面暂不可用，本页不运行语音。正在重试画面…": "Renderer unavailable. Retrying the silent preview…",
  "左眼，240乘240像素": "Left eye, 240 by 240 pixels",
  "右眼，240乘240像素": "Right eye, 240 by 240 pixels",
  "休息中": "Idle",
  "选择状态，查看固件共用的眼睛绘制效果": "Select a state to preview the shared firmware renderer",
  "外壳为概念预览 · 两眼均由 C++ 核心绘制 · 240 × 240 / 眼": "Concept enclosure · shared C++ renderer · 240 × 240 per eye",
  "看看它的表情": "Expressions",
  "开心": "Happy",
  "困倦": "Drowsy",
  "疑惑": "Curious",
  "恢复真实状态": "Use current state",
  "演示表情仅在休息时可用，通话状态优先。": "Expression demos are available while idle; active states take priority.",
  "本机无声预览": "Silent local preview",
  "只预览硬件状态和表情，不打开麦克风、播放声音或连接模型服务。": "Preview device states and expressions without audio capture, playback or model requests.",
  "待机": "Idle",
  "连接": "Connect",
  "聆听": "Listening",
  "思考": "Thinking",
  "说话": "Speaking",
  "静音": "Muted",
  "离线": "Offline",
  "配置错误": "Configuration error",
  "绘制信息": "Renderer",
  "连接本机 C++ 绘制进程…": "Connecting to the local C++ renderer…",
  "Agent 的协议、工具与性能测试使用独立无界面 C++ 模拟器。": "Agent protocol, tool and performance tests use the separate native C++ simulator.",
  "原生像素 · 本地唤醒 · 家庭共享对话": "Native pixels · local wake · shared conversation",
  "屏幕设计预览 / 非硬件验收": "Display preview / hardware acceptance is separate",
  "连接中": "Connecting",
  "检查配置": "Check configuration",
  "正在演示表情；点击恢复，或开始通话即可回到真实状态。": "Showing an expression demo; restore or start an active state to exit.",
  "当前由实际通话状态控制眼睛。": "The active state controls the eyes.",
  "返回宠物预览": "Enclosure preview",
  "实际像素视图 · 每眼 240 × 240 CSS 像素 · RGB565 · 20fps 目标": "Actual pixels · 240 × 240 CSS pixels per eye · RGB565 · 20 fps target",
  "画面进程暂不可用，本页不运行语音。正在重试…": "Renderer unavailable. Retrying the silent preview…"
};
export function translate(text,language='en') {
  if(language==='zh-CN') {
    for(const [zh,en] of Object.entries(dictionary))if(text===en)return zh;
    const m=text.match(/^Local C\+\+ renderer · (\d+) frames · RGB565 · 20 fps target$/);
    return m ? `本机 C++ 画面正常 · ${m[1]} 帧 · RGB565 · 20fps 目标` : text;
  }
  const m=text.match(/^本机 C\+\+ 画面正常 · (\d+) 帧 · RGB565 · 20fps 目标$/);
  return m ? `Local C++ renderer · ${m[1]} frames · RGB565 · 20 fps target` : dictionary[text]||text;
}
if(typeof document!=='undefined') {
 let language='en';try{if(localStorage.getItem('pikoo-preview-language')==='zh-CN')language='zh-CN';}catch{}
 const toggle=document.createElement('button');toggle.id='language';toggle.className='pill';document.querySelector('header').append(toggle);
 function render(){
  document.documentElement.lang=language;const label=language==='en'?'中文':'English';if(toggle.textContent!==label)toggle.textContent=label;
  const walker=document.createTreeWalker(document,NodeFilter.SHOW_TEXT);
  for(let n=walker.nextNode();n;n=walker.nextNode()){
   if(['SCRIPT','STYLE','BUTTON'].includes(n.parentElement?.tagName)&&n.parentElement===toggle)continue;
   if(['SCRIPT','STYLE'].includes(n.parentElement?.tagName))continue;
   const key=n.nodeValue.trim(),value=translate(key,language);if(value!==key)n.nodeValue=n.nodeValue.replace(key,value);
  }
  for(const n of document.querySelectorAll('[aria-label]')){const a=n.getAttribute('aria-label'),b=translate(a,language);if(a!==b)n.setAttribute('aria-label',b);}
 }
 toggle.onclick=()=>{language=language==='en'?'zh-CN':'en';try{localStorage.setItem('pikoo-preview-language',language);}catch{}render();};
 render();new MutationObserver(render).observe(document.body,{subtree:true,childList:true,characterData:true});
}
