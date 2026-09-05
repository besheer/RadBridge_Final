
document.addEventListener('DOMContentLoaded',function(){
  const trigger=document.getElementById('userTrigger'), dropdown=document.getElementById('userDropdown');
  if(trigger&&dropdown){trigger.addEventListener('click',e=>{e.stopPropagation();dropdown.classList.toggle('open')});document.addEventListener('click',()=>dropdown.classList.remove('open'))}
  document.querySelectorAll('.flash-close').forEach(b=>b.addEventListener('click',()=>b.parentElement.remove()));
  const modal=document.getElementById('confirmModal'), cancel=document.getElementById('confirmCancel');
  document.querySelectorAll('.js-confirm-logout').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();modal&&modal.classList.add('open')}));
  if(cancel)cancel.addEventListener('click',()=>modal.classList.remove('open'));
  const sb=document.getElementById('sidebar'), ov=document.getElementById('sidebarOverlay'), open=document.getElementById('sidebarOpen'), close=document.getElementById('sidebarClose');
  const show=()=>{sb&&sb.classList.add('open');ov&&ov.classList.add('open')}, hide=()=>{sb&&sb.classList.remove('open');ov&&ov.classList.remove('open')};
  if(open)open.addEventListener('click',show); if(close)close.addEventListener('click',hide); if(ov)ov.addEventListener('click',hide);
});
