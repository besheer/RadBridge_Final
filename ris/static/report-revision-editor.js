(() => {
  const host=document.getElementById('revisionWorkspace');
  if (!host) return;
  const base=host.dataset.base, ar=host.dataset.ar==='yes';
  const message=document.getElementById('revisionMessage');
  const buttons=[...host.querySelectorAll('button[data-action]')];
  let lease='',version=Number(host.dataset.version),dirty=false,editor=null,pendingCommit=null,heartbeat=null;
  const errors={
    DOCUMENT:['الوثيقة غير متاحة أو لا تطابق بيانات الحالة.','The document is unavailable or does not match the case.'],
    CORRECTION_CONTENT_REQUIRED:['أضف التصحيح الطبي قبل المراجعة والاعتماد.','Enter the clinical correction before verification and finalization.'],
    SAVE_CORRECTION_DRAFT_FIRST:['احفظ مسودة التصحيح أولًا ثم راجعها.','Save the correction draft before verification.'],
    PACS_IDENTITY_NOT_VERIFIED:['لم تُؤكد مطابقة صور PACS لهوية المريض.','PACS patient identity has not been confirmed.'],
    ADDENDUM_ORIGINAL_CONTENT_CHANGED:['الإضافة لا تسمح بتعديل نص التقرير الأصلي.','An addendum cannot change the original report text.'],
    REVISION_EDIT_LOCKED:['التصحيح مفتوح للتحرير في جلسة أخرى.','Another session is editing this correction.'],
    REVISION_LEASE_EXPIRED:['انتهت جلسة التحرير؛ أعد فتح الصفحة.','The edit session expired; reopen the page.'],
    STALE:['تغير التقرير المرجعي؛ أعد مراجعة الطلب.','The reference report changed; review the request again.'],
    IDEMPOTENT_CONTENT_CHANGED:['تغير المحتوى أثناء إعادة الحفظ؛ راجع النسخة ثم احفظ مجددًا.','Content changed during a retry; review and save again.']
  };
  function errorText(error){const pair=errors[error.message];return pair?pair[ar?0:1]:(ar?'تعذر تنفيذ الإجراء. رمز التفاصيل: ':'The action could not complete. Detail code: ')+error.message;}
  function say(a,e){message.textContent=ar?a:e;}
  function busy(value){buttons.forEach(button=>button.disabled=value);}
  async function call(path,data){
    const options={credentials:'same-origin',headers:{'X-RadBridge-Revision-Lease':lease,'X-Report-Revision-CSRF':host.dataset.csrf}};
    if(data!==undefined){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(data);}
    const r=await fetch(base+path,options),d=await r.json();
    if(!r.ok||d.ok===false)throw new Error(d.error||`HTTP ${r.status}`);
    return d;
  }
  async function renew(){const d=await call('/lease',{token:lease});lease=d.token;}
  const writable=host.dataset.edit==='yes'&&['DRAFT','VERIFIED'].includes(host.dataset.status);
  async function open(){
    try{
      busy(true);
      if(writable)await renew();
      const d=await call('/config');version=d.version_no;
      const script=document.createElement('script');script.src='/onlyoffice/web-apps/apps/api/documents/api.js';
      await new Promise((resolve,reject)=>{script.onload=resolve;script.onerror=reject;document.head.append(script);});
      d.config.events={onDocumentStateChange:event=>{dirty=Boolean(event.data);},onError:()=>say('تعذر تشغيل المحرر؛ أعد المحاولة.','The editor could not start; retry.')};
      editor=new window.DocsAPI.DocEditor('revisionEditor',d.config);
      if(writable)heartbeat=setInterval(()=>renew().catch(()=>{busy(true);say('انتهى قفل التحرير؛ أعد فتح الصفحة قبل الحفظ.','The edit lease expired; reopen before saving.');}),40000);
      busy(false);
    }catch(e){message.textContent=errorText(e);busy(true);}
  }
  buttons.forEach(button=>button.addEventListener('click',async()=>{
    const action=button.dataset.action;
    if(action!=='draft'&&!window.confirm(ar?'تأكيد مراجعة/اعتماد النسخة المحفوظة؟':'Confirm verification/finalization of the saved version?'))return;
    busy(true);
    try{
      await renew();
      if(host.dataset.status==='DRAFT')await call('/forcesave',{dirty});
      if(action==='draft'&&!pendingCommit)pendingCommit=window.crypto.randomUUID();
      const d=await call('/commit',{action,base_version_no:version,commit_id:pendingCommit});
      version=d.version_no;
      if(action==='draft'){
        pendingCommit=null;dirty=false;
        say('حُفظت مسودة التصحيح؛ التقرير الأصلي لم يتغير.','Correction draft saved; the original report is unchanged.');
      }else window.location.reload();
    }catch(e){
      if(e.message==='IDEMPOTENT_CONTENT_CHANGED'||e.message==='REPORT_VERSION_CONFLICT'){
        try{const d=await call('/state');version=d.version_no;pendingCommit=null;}catch(_){}
      }
      message.textContent=errorText(e);
    }
    finally{busy(false);}
  }));
  if(['DRAFT','VERIFIED','FINAL'].includes(host.dataset.status))open();
  window.addEventListener('pagehide',()=>{if(heartbeat)clearInterval(heartbeat);if(editor)editor.destroyEditor();});
})();
