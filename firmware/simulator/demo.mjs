// Preview controls never access microphones, speakers or model services.
const labels={idle:'待机',connecting:'连接中',listening:'聆听',thinking:'思考',speaking:'说话',muted:'MIC OFF',offline:'离线',auth_error:'检查配置'};
for(const button of document.querySelectorAll('[data-state]'))button.onclick=()=>{
 const state=button.dataset.state;window.dispatchEvent(new CustomEvent('pikoo:state',{detail:state}));
 document.getElementById('status').textContent=labels[state]||state;
};
