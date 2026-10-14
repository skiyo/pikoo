// Only an opaque conversation identifier is cached, never credentials or transcripts.
export const key='pikoo.conversation.v1';
export function loadConversation(storage,now=Date.now()){
 try{const row=JSON.parse(storage?.getItem(key)||'null');if(row&&typeof row.id==='string'&&/^[A-Za-z0-9_-]{8,80}$/.test(row.id)&&Number.isFinite(row.at)&&now-row.at>=0&&now-row.at<24*60*60*1000)return row.id;}catch{}
 return null;
}
export function saveConversation(storage,id,now=Date.now()){
 try{if(id)storage?.setItem(key,JSON.stringify({id,at:now}));else storage?.removeItem(key);}catch{}
}
