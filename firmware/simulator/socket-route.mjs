export function socketRoute(target,origin){
 try{
  if(typeof target!=='string'||target.length>256)return null;
  const url=new URL(target,origin);if(url.origin!==origin||!['/device','/eyes','/wake'].includes(url.pathname))return null;
  const params=[...url.searchParams];
  if(url.pathname!=='/device')return params.length?null:{path:url.pathname};
  if(!params.length)return {path:'/device'};
  if(params.length!==1||params[0][0]!=='conversationId'||!/^[A-Za-z0-9_-]{8,80}$/.test(params[0][1]))return null;
  return {path:'/device',conversationId:params[0][1]};
 }catch{return null;}
}
