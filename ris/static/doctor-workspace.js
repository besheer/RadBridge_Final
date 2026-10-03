/* Personal worklist: no automatic POST retry and no unsafe HTML injection. */
(() => {
  'use strict';
  const root = document.getElementById('rbUnifiedDoctorWorkspace');
  if (!root) return;
  const ar = root.dataset.ar === 'yes';
  const say = (en, arabic) => ar ? arabic : en;
  const offers = document.getElementById('rbWorkspaceOfferRows');
  const cases = document.getElementById('rbWorkspaceCaseRows');
  const externalCases = document.getElementById('rbWorkspaceExternalCaseRows');
  const message = document.getElementById('rbWorkspaceMessage');
  const search = document.getElementById('rbWorkspaceSearch');
  const resultCount = document.getElementById('rbDoctorResultCount');
  const filters = {
    priority:document.getElementById('rbDoctorPriorityFilter'), modality:document.getElementById('rbDoctorModalityFilter'),
    exam_status:document.getElementById('rbDoctorExamFilter'), pacs_status:document.getElementById('rbDoctorPacsFilter'),
    report_status:document.getElementById('rbDoctorReportFilter'), sla_status:document.getElementById('rbDoctorSlaFilter'),
  };
  const dateFrom=document.getElementById('rbDoctorDateFrom'), dateTo=document.getElementById('rbDoctorDateTo'), clearFilters=document.getElementById('rbDoctorClearFilters');
  const patientIdFilter=document.getElementById('rbDoctorPatientIdFilter'), examCodeFilter=document.getElementById('rbDoctorExamCodeFilter');
  const searchButton=document.getElementById('rbDoctorSearchButton');
  const advancedFilters=document.getElementById('rbDoctorAdvancedFilters');
  const applyAdvancedFilters=document.getElementById('rbDoctorApplyAdvancedFilters');
  const clearAdvancedFilters=document.getElementById('rbDoctorClearAdvancedFilters');
  const activeFilters=document.getElementById('rbDoctorActiveFilters');
  const activeFilterChips=document.getElementById('rbDoctorActiveFilterChips');
  const datePresetButtons=[...document.querySelectorAll('[data-doctor-date-preset]')];
  const columnButton = document.getElementById('rbDoctorColumnsButton');
  const columnMenu = document.getElementById('rbDoctorColumnsMenu');
  const columnStorageKey = 'radbridge.doctor.column-layout.v5';
  const legacyColumnStorageKey = 'radbridge.doctor.visible-columns.v4';
  const legacyLayoutStorageKey = 'radbridge.doctor.column-layout.v1';
  const columnLayoutApi = root.dataset.columnLayoutApi;
  const columnDefinitions = [
    ['priority', say('Priority', 'الأولوية'), true],
    ['accession', say('Accession', 'رقم الفحص'), true],
    ['patient_id', say('Patient ID', 'رقم المريض'), false],
    ['patient', say('Original Name', 'الاسم الأصلي'), true],
    ['patient_worklist', say('English / Worklist Name', 'الاسم الإنجليزي / Worklist'), true],
    ['dob', say('DOB', 'تاريخ الميلاد'), false],
    ['sex', say('Sex', 'النوع'), false],
    ['procedure', say('Examination', 'الفحص'), true],
    ['modality', say('Modality', 'نوع الجهاز'), true],
    ['body_part', say('Body Part', 'جزء الجسم'), true],
    ['contrast', say('Contrast', 'صبغة'), false],
    ['branch', say('Branch', 'الفرع'), false],
    ['device', say('Device', 'الجهاز'), false],
    ['room', say('Room', 'الغرفة'), false],
    ['station_ae', say('Station AE', 'اسم الجهاز على PACS'), false],
    ['referring_doctor', say('Referring Doctor', 'الطبيب المحوّل'), true],
    ['assigned_doctor', say('Assigned Radiologist', 'طبيب الأشعة المعيّن'), false],
    ['performing_doctor', say('Performing Doctor', 'الطبيب المنفّذ'), false],
    ['clinical_indication', say('Clinical Indication', 'سبب الفحص'), true],
    ['clinical_history', say('Clinical History', 'التاريخ المرضي'), false],
    ['clinical_diagnosis', say('Diagnosis', 'التشخيص'), false],
    ['allergy_notes', say('Allergies', 'الحساسية'), false],
    ['status', say('Order Status', 'حالة الطلب'), false],
    ['exam_status', say('Exam Status', 'حالة الفحص'), false],
    ['pacs_status', say('PACS Status', 'حالة PACS'), true],
    ['images', say('Image Count', 'عدد الصور'), true],
    ['attachment_count', say('Attachments', 'المرفقات'), false],
    ['prior_count', say('Prior Studies', 'الفحوصات السابقة'), false],
    ['study_instance_uid', say('Study UID', 'معرّف الدراسة'), false],
    ['report_status', say('Report Status', 'حالة التقرير'), true],
    ['reported_by', say('Reported By', 'كاتب التقرير'), false],
    ['verified_by', say('Verified By', 'تمت المراجعة بواسطة'), true],
    ['verified_at', say('Verified At', 'وقت المراجعة'), false],
    ['second_verified_by', say('Second Verified By', 'المراجع الثاني'), false],
    ['second_verified_at', say('Second Verified At', 'وقت المراجعة الثانية'), false],
    ['finalized_by', say('Finalized By', 'تم الاعتماد بواسطة'), false],
    ['finalized_at', say('Finalized At', 'وقت الاعتماد'), false],
    ['report_updated_at', say('Report Updated At', 'آخر تحديث للتقرير'), false],
    ['report_delivered', say('Report Delivered', 'تم تسليم التقرير'), false],
    ['images_delivered', say('Images Delivered', 'تم تسليم الصور'), false],
    ['sla_status', say('SLA Status', 'حالة SLA'), true],
    ['sla_elapsed_minutes', say('SLA Elapsed', 'الوقت المستغرق'), false],
    ['sla_remaining_minutes', say('SLA Remaining', 'الوقت المتبقي'), false],
    ['scheduled_at', say('Scheduled At', 'موعد الفحص'), false],
    ['assigned_at', say('Assigned At', 'وقت التعيين'), false],
    ['exam_started_at', say('Exam Started At', 'وقت بدء الفحص'), false],
    ['exam_completed_at', say('Exam Completed At', 'وقت انتهاء الفحص'), false],
    ['pacs_last_seen_at', say('PACS Last Seen', 'آخر وصول للصور'), false],
    ['center', say('Source / Center', 'المصدر / المركز'), false],
    ['action', say('Action', 'إجراء'), true],
  ];
  const defaultColumns = ['priority','accession','patient_worklist','procedure','modality','images','pacs_status','report_status','sla_status','action'];
  const columnGroups = {
    patient:['patient_id','patient','patient_worklist','dob','sex'],
    exam:['priority','accession','procedure','modality','body_part','contrast','branch','device','room','station_ae','status','exam_status'],
    clinical:['referring_doctor','assigned_doctor','performing_doctor','clinical_indication','clinical_history','clinical_diagnosis','allergy_notes','attachment_count','prior_count'],
    pacs:['pacs_status','images','study_instance_uid','pacs_last_seen_at','images_delivered'],
    report:['report_status','reported_by','verified_by','verified_at','second_verified_by','second_verified_at','finalized_by','finalized_at','report_updated_at','report_delivered'],
    timing:['sla_status','sla_elapsed_minutes','sla_remaining_minutes','scheduled_at','assigned_at','exam_started_at','exam_completed_at','center'],
    workflow:['action'],
  };
  const columnPresets = {
    reporting:defaultColumns,
    clinical:['priority','accession','patient_worklist','procedure','modality','clinical_indication','clinical_history','clinical_diagnosis','allergy_notes'],
    pacs:['priority','accession','patient_worklist','procedure','modality','pacs_status','images','pacs_last_seen_at'],
    verification:['priority','accession','patient_worklist','procedure','report_status','reported_by','verified_by','second_verified_by','finalized_by','sla_status'],
  };
  const defaultWidths = {priority:105,accession:165,patient_id:140,patient:210,patient_worklist:230,procedure:220,modality:95,images:95,pacs_status:125,report_status:135,sla_status:115,action:390};
  const defaultLayout = () => ({version:2,order:columnDefinitions.map(([key])=>key),visible:[...defaultColumns],widths:{...defaultWidths},pinned:['accession','patient_worklist'],density:'compact'});
  let layout = defaultLayout(), layoutLoaded = false, layoutSaveTimer = null;
  let rows = [], loading = false, posting = false;
  function node(tag, text, className) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (className) el.className = className;
    return el;
  }
  function openLink(url) {
    // Backend emits relative, permission-checked URLs; never navigate to payload origins.
    const parsed = new URL(url, location.origin);
    if (parsed.origin !== location.origin || !parsed.pathname.startsWith('/doctor/cases/')) throw new Error('Invalid link');
    return parsed.href;
  }
  function safeReturnLink(url) {
    const parsed = new URL(url, location.origin);
    if (parsed.origin !== location.origin || !/^\/reports\/\d+\/return-case$/.test(parsed.pathname)) throw new Error('Invalid return link');
    return parsed.href;
  }
  function card(c) {
    const el = node('article', undefined, 'rb-case-card');
    if(c.linked_visit){el.classList.add('rb-linked-visit');el.append(node('strong',say('Linked visit · ','زيارة مرتبطة · ')+c.visit_exam_count+say(' examinations',' فحوصات')));}
    const copy = node('div', undefined, 'rb-case-copy');
    copy.append(node('strong', c.accession + ' · ' + c.patient));
    if (c.source === 'EXTERNAL') copy.append(node('small', say('External center: ', 'مركز خارجي: ') + c.center));
    copy.append(node('small', [c.modality, c.procedure, c.status, say('Images: ', 'الصور: ') + c.images].join(' · ')));
    el.append(copy);
    return el;
  }
  function normalizeLayout(value) {
    const base=defaultLayout(), allowed=new Set(base.order), candidate=value&&typeof value==='object'?value:{};
    const order=[]; (Array.isArray(candidate.order)?candidate.order:[]).forEach(key=>{if(allowed.has(key)&&!order.includes(key))order.push(key);});
    base.order.forEach(key=>{if(!order.includes(key))order.push(key);});
    const visible=[]; (Array.isArray(candidate.visible)?candidate.visible:base.visible).forEach(key=>{if(allowed.has(key)&&!visible.includes(key))visible.push(key);});
    if(candidate.version!==2&&!visible.includes('action'))visible.push('action');
    const widths={...base.widths}; Object.entries(candidate.widths||{}).forEach(([key,value])=>{if(allowed.has(key)&&Number.isFinite(Number(value)))widths[key]=Math.max(72,Math.min(520,Math.round(Number(value))));});
    const pinned=[]; (Array.isArray(candidate.pinned)?candidate.pinned:base.pinned).forEach(key=>{if(allowed.has(key)&&visible.includes(key)&&!pinned.includes(key)&&pinned.length<3)pinned.push(key);});
    return {version:2,order,visible:visible.length?visible:base.visible,widths,pinned,density:candidate.density==='comfortable'?'comfortable':'compact'};
  }
  function loadLocalLayout() {
    try {
      const value = JSON.parse(localStorage.getItem(columnStorageKey));
      if(value)return normalizeLayout(value);
      const legacy=JSON.parse(localStorage.getItem(legacyColumnStorageKey));
      const legacyLayout=JSON.parse(localStorage.getItem(legacyLayoutStorageKey));
      return normalizeLayout({
        visible:Array.isArray(legacy)?legacy:defaultColumns,
        order:legacyLayout&&Array.isArray(legacyLayout.order)?legacyLayout.order:[],
        widths:legacyLayout&&legacyLayout.widths&&typeof legacyLayout.widths==='object'?legacyLayout.widths:{},
      });
    } catch (_) { return defaultLayout(); }
  }
  function selectedColumns() { return layout.visible; }
  function orderedDefinitions() {
    const byKey=new Map(columnDefinitions.map(def=>[def[0],def]));
    return layout.order.map(key=>byKey.get(key)).filter(Boolean);
  }
  function storeLayout(saveRemote=true) {
    layout=normalizeLayout(layout);
    try { localStorage.setItem(columnStorageKey,JSON.stringify(layout)); } catch (_) {}
    if(!saveRemote||!columnLayoutApi)return;
    window.clearTimeout(layoutSaveTimer);
    layoutSaveTimer=window.setTimeout(async()=>{
      try{
        const response=await fetch(columnLayoutApi,{method:'POST',credentials:'same-origin',redirect:'error',headers:{'Content-Type':'application/json'},body:JSON.stringify(layout)});
        const data=await response.json(); if(!response.ok||!data.ok)throw new Error('save failed');
        layout=normalizeLayout(data.column_layout); try{localStorage.setItem(columnStorageKey,JSON.stringify(layout));}catch(_){}
        message.textContent=say('Column layout saved to your account.','تم حفظ ترتيب الأعمدة في حسابك.');
      }catch(_){message.textContent=say('Layout saved on this device; account sync failed.','تم الحفظ على هذا الجهاز؛ تعذرت مزامنة الحساب.');}
    },350);
  }
  function syncColumnMenu() {
    columnMenu.querySelectorAll('[data-doctor-column-toggle]').forEach(toggle=>{toggle.checked=layout.visible.includes(toggle.dataset.doctorColumnToggle);});
    columnMenu.querySelectorAll('[data-doctor-column-pin]').forEach(pin=>{const active=layout.pinned.includes(pin.dataset.doctorColumnPin);pin.classList.toggle('primary',active);pin.setAttribute('aria-pressed',String(active));});
  }
  function applyColumns(keys) {
    const allowed = new Set(columnDefinitions.map(([key]) => key));
    const selected = keys.filter(key => allowed.has(key)); layout.visible=selected.length?selected:[...defaultColumns]; layout.pinned=layout.pinned.filter(key=>layout.visible.includes(key)); storeLayout();
    syncColumnMenu();
    renderCases();
  }
  function buildColumnMenu() {
    const presets = node('div', undefined, 'rb-doctor-presets');
    const presetLabels = {reporting:say('Reporting','تقارير'),clinical:say('Clinical','سريري'),pacs:'PACS',verification:say('Verification','مراجعة')};
    Object.entries(columnPresets).forEach(([name, keys]) => {
      const button = node('button', presetLabels[name], 'btn small'); button.type = 'button'; button.addEventListener('click', () => applyColumns(keys)); presets.append(button);
    });
    columnMenu.append(presets);
    const groupLabels = {patient:say('Patient','المريض'),exam:say('Exam','الفحص'),clinical:say('Clinical','سريري'),pacs:'PACS',report:say('Report','التقرير'),timing:say('Timing & SLA','التوقيت و SLA'),workflow:say('Workflow','الإجراءات')};
    Object.entries(columnGroups).forEach(([group, keys]) => {
      const section=node('section',undefined,'rb-doctor-column-group'), title=node('b',groupLabels[group]); section.append(title);
      columnDefinitions.filter(([key]) => keys.includes(key)).forEach(([key, label]) => {
      const row = node('label'), toggle = document.createElement('input');
      toggle.type = 'checkbox'; toggle.dataset.doctorColumnToggle = key;
      toggle.checked = selectedColumns().includes(key);
      const pin=node('button',say('Pin','تثبيت'),'btn small'); pin.type='button'; pin.dataset.doctorColumnPin=key;
      const updatePin=()=>{pin.classList.toggle('primary',layout.pinned.includes(key));pin.setAttribute('aria-pressed',String(layout.pinned.includes(key)));}; updatePin();
      pin.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();if(layout.pinned.includes(key))layout.pinned=layout.pinned.filter(item=>item!==key);else if(layout.pinned.length<3&&layout.visible.includes(key))layout.pinned.push(key);updatePin();storeLayout();renderCases();});
      toggle.addEventListener('change', () => {
        const visible = [...columnMenu.querySelectorAll('[data-doctor-column-toggle]')].filter(x => x.checked).map(x => x.dataset.doctorColumnToggle);
        layout.visible=visible.length?visible:[...defaultColumns];layout.pinned=layout.pinned.filter(item=>layout.visible.includes(item));storeLayout();renderCases();updatePin();
      });
        row.append(toggle, document.createTextNode(label),pin); section.append(row);
      });
      columnMenu.append(section);
    });
    const reset = node('button', say('Reset default', 'الإعداد الافتراضي'), 'btn small');
    reset.type = 'button'; reset.addEventListener('click', () => {
      layout=defaultLayout();storeLayout();
      syncColumnMenu();
      renderCases();
    });
    const clear = node('button', say('Clear', 'إلغاء الكل'), 'btn small'); clear.type='button'; clear.addEventListener('click',()=>applyColumns([]));
    const all = node('button', say('All', 'الكل'), 'btn small'); all.type='button'; all.addEventListener('click',()=>applyColumns(columnDefinitions.map(([key])=>key)));
    const done = node('button', say('Done', 'تم'), 'btn small primary');
    done.type = 'button'; done.addEventListener('click', () => { columnMenu.hidden = true; columnButton.setAttribute('aria-expanded', 'false'); });
    const help=node('p',say('Drag a table header to move it. Drag its edge to resize. Pin up to three important columns.','اسحب عنوان العمود لنقله، واسحب الحافة لتغيير العرض، وثبّت حتى 3 أعمدة مهمة.'),'rb-doctor-layout-help');
    const density=node('div',undefined,'rb-doctor-density'), densityLabel=node('b',say('Row spacing','تباعد الصفوف')), compact=node('button',say('Compact','مضغوط'),'btn small'), comfortable=node('button',say('Comfortable','مريح'),'btn small');
    [compact,comfortable].forEach(button=>button.type='button');
    const updateDensity=()=>{compact.classList.toggle('primary',layout.density==='compact');comfortable.classList.toggle('primary',layout.density==='comfortable');};
    compact.addEventListener('click',()=>{layout.density='compact';updateDensity();storeLayout();renderCases();});comfortable.addEventListener('click',()=>{layout.density='comfortable';updateDensity();storeLayout();renderCases();});updateDensity();density.append(densityLabel,compact,comfortable);
    const actions = node('div', undefined, 'rb-doctor-column-actions'); actions.append(clear, all, reset, done); columnMenu.append(help,density,actions);
    columnButton.addEventListener('click', () => { columnMenu.hidden = !columnMenu.hidden; columnButton.setAttribute('aria-expanded', String(!columnMenu.hidden)); });
    document.addEventListener('click', event => { if (!columnMenu.hidden && !columnMenu.contains(event.target) && event.target !== columnButton) { columnMenu.hidden = true; columnButton.setAttribute('aria-expanded', 'false'); } });
  }
  function renderCaseTable(target, scoped) {
    if (!scoped.length) { target.append(node('p', say('No assigned cases match.', 'لا توجد حالات معيّنة مطابقة.'))); return; }
    const visible = selectedColumns(), definitions=orderedDefinitions().filter(([key])=>visible.includes(key)), wrap = node('div', undefined, 'rb-doctor-table-wrap'), table = node('table', undefined, `rb-doctor-table rb-density-${layout.density}`), head = document.createElement('thead'), headRow = document.createElement('tr'), body = document.createElement('tbody');
    let draggedKey=null;
    definitions.forEach(([key,label])=>{
      const th=node('th',label);th.dataset.doctorColumn=key;th.draggable=true;th.style.width=`${layout.widths[key]||160}px`;th.style.minWidth=th.style.width;th.style.maxWidth=th.style.width;
      th.addEventListener('dragstart',event=>{draggedKey=key;th.classList.add('rb-column-dragging');event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',key);});
      th.addEventListener('dragend',()=>{draggedKey=null;th.classList.remove('rb-column-dragging');headRow.querySelectorAll('.rb-column-drop').forEach(item=>item.classList.remove('rb-column-drop'));});
      th.addEventListener('dragover',event=>{if(draggedKey&&draggedKey!==key){event.preventDefault();th.classList.add('rb-column-drop');}});
      th.addEventListener('dragleave',()=>th.classList.remove('rb-column-drop'));
      th.addEventListener('drop',event=>{event.preventDefault();th.classList.remove('rb-column-drop');const from=layout.order.indexOf(draggedKey),to=layout.order.indexOf(key);if(from<0||to<0||from===to)return;layout.order.splice(from,1);layout.order.splice(to,0,draggedKey);storeLayout();renderCases();});
      const resizer=node('span',undefined,'rb-column-resizer');resizer.setAttribute('aria-hidden','true');resizer.draggable=false;
      resizer.addEventListener('pointerdown',event=>{event.preventDefault();event.stopPropagation();const startX=event.clientX,startWidth=th.getBoundingClientRect().width;resizer.setPointerCapture(event.pointerId);
        const move=moveEvent=>{layout.widths[key]=Math.max(72,Math.min(520,Math.round(startWidth+(moveEvent.clientX-startX)*(ar?-1:1))));th.style.width=`${layout.widths[key]}px`;th.style.minWidth=th.style.width;th.style.maxWidth=th.style.width;table.querySelectorAll(`[data-doctor-column="${key}"]`).forEach(cell=>{cell.style.width=th.style.width;cell.style.minWidth=th.style.width;cell.style.maxWidth=th.style.width;});applyPinnedOffsets(table);};
        const up=upEvent=>{resizer.removeEventListener('pointermove',move);resizer.removeEventListener('pointerup',up);resizer.removeEventListener('pointercancel',up);try{resizer.releasePointerCapture(upEvent.pointerId);}catch(_){}storeLayout();};resizer.addEventListener('pointermove',move);resizer.addEventListener('pointerup',up);resizer.addEventListener('pointercancel',up);});
      th.append(resizer);headRow.append(th);
    });
    head.append(headRow); table.append(head);
    scoped.forEach(c => {
      const row = document.createElement('tr');
      if(c.linked_visit){row.classList.add('rb-linked-visit');row.title=say('Linked patient visit: ','زيارة مريض مرتبطة: ')+c.visit_exam_count;}
      const minutes = value => value === null || value === undefined ? '-' : `${value}m`;
      const yesNo = value => value ? say('Yes','نعم') : say('No','لا');
      const values = {priority:c.priority,accession:c.accession,patient_id:c.patient_id,patient:c.patient,patient_worklist:c.patient_worklist||'-',dob:c.dob||'-',sex:c.sex||'-',procedure:c.procedure,modality:c.modality,body_part:c.body_part||'-',contrast:yesNo(c.contrast),branch:c.branch||'-',device:c.device||'-',room:c.room||'-',station_ae:c.station_ae||'-',referring_doctor:c.referring_doctor||'-',assigned_doctor:c.assigned_doctor||'-',performing_doctor:c.performing_doctor||'-',clinical_indication:c.clinical_indication||'-',clinical_history:c.clinical_history||'-',clinical_diagnosis:c.clinical_diagnosis||'-',allergy_notes:c.allergy_notes||'-',status:c.status,exam_status:c.exam_status||'-',pacs_status:c.pacs_status||'-',images:String(c.images),attachment_count:String(c.attachment_count??0),prior_count:String(c.prior_count??0),study_instance_uid:c.study_instance_uid||'-',report_status:c.report_status||'UNREPORTED',reported_by:c.reported_by||'-',verified_by:c.verified_by||'-',verified_at:c.verified_at||'-',second_verified_by:c.second_verified_by||'-',second_verified_at:c.second_verified_at||'-',finalized_by:c.finalized_by||'-',finalized_at:c.finalized_at||'-',report_updated_at:c.report_updated_at||'-',report_delivered:yesNo(c.report_delivered),images_delivered:yesNo(c.images_delivered),sla_status:c.sla_status||'-',sla_elapsed_minutes:minutes(c.sla_elapsed_minutes),sla_remaining_minutes:minutes(c.sla_remaining_minutes),scheduled_at:c.scheduled_at||'-',assigned_at:c.assigned_at||'-',exam_started_at:c.exam_started_at||'-',exam_completed_at:c.exam_completed_at||'-',pacs_last_seen_at:c.pacs_last_seen_at||'-',center:c.source==='EXTERNAL'?(c.center||say('External','خارجي')):say('Internal','داخلي')};
      let detailsButton=null;
      definitions.forEach(([key]) => {
        if(key==='action'){
          const cell=node('td',undefined,'rb-doctor-action'); cell.dataset.doctorColumn=key;
          const width=layout.widths[key]||390; cell.style.width=`${width}px`; cell.style.minWidth=cell.style.width; cell.style.maxWidth=cell.style.width;
          const controls=node('div',undefined,'rb-doctor-action-buttons'), details=node('button',say('Details','تفاصيل'),'btn small'), link=node('a',say('Open study','فتح الفحص'),'btn primary');
          details.type='button'; controls.append(details);
          if(c.has_linked_study){
            link.href=openLink(c.open_url);link.target='_blank';link.rel='noopener';controls.append(link);
            if(c.start_url && !['VERIFIED','FINAL','CANCELLED'].includes(c.status)){
              const startForm=document.createElement('form');startForm.method='POST';startForm.action=c.start_url;startForm.target='_blank';
              const startButton=document.createElement('button');startButton.className='btn primary';startButton.textContent=say('Start Reading','بدء القراءة');startForm.append(startButton);controls.append(startForm);
            }
          }
          else controls.append(node('span',say('No linked study','لا توجد دراسة مرتبطة'),'rb-doctor-no-study'));
          if(c.return_allowed&&c.return_url){const returned=node('a',say('Return for review','إرجاع للمراجعة'),'btn small');returned.href=safeReturnLink(c.return_url);controls.append(returned);}
          detailsButton=details; cell.append(controls); row.append(cell); return;
        }
        const badgeKeys=['priority','pacs_status','report_status','sla_status'];
        const cell=node('td',undefined,key==='patient_worklist'?'rb-doctor-worklist':(key==='patient'?'rb-doctor-original':'')); cell.dataset.doctorColumn=key;
        const width=layout.widths[key]||160;cell.style.width=`${width}px`;cell.style.minWidth=cell.style.width;cell.style.maxWidth=cell.style.width;
        const value=String(values[key]??'-'); cell.title=value;
        if(badgeKeys.includes(key)) cell.append(node('span',value,`rb-status rb-status-${value.toLowerCase().replace(/[^a-z0-9]+/g,'-')}`)); else cell.textContent=value;
        row.append(cell);
      });
      body.append(row);
      const detailRow=node('tr',undefined,'rb-doctor-detail-row'); detailRow.hidden=true; const detailCell=document.createElement('td'); detailCell.colSpan=visible.length;
      const detailItems=[[say('Clinical indication','سبب الفحص'),c.clinical_indication],[say('History','التاريخ المرضي'),c.clinical_history],[say('Diagnosis','التشخيص'),c.clinical_diagnosis],[say('Allergies','الحساسية'),c.allergy_notes],[say('Referrer','الطبيب المحوّل'),c.referring_doctor],[say('PACS','PACS'),`${c.pacs_status||'-'} · ${say('Images','الصور')}: ${c.images??0}`]];
      const grid=node('div',undefined,'rb-doctor-detail-grid'); detailItems.forEach(([label,value])=>{const item=node('div',undefined,'rb-doctor-detail-item');item.append(node('b',label),node('span',value||'-'));grid.append(item);});detailCell.append(grid);detailRow.append(detailCell);body.append(detailRow);
      if(detailsButton)detailsButton.addEventListener('click',()=>{detailRow.hidden=!detailRow.hidden;detailsButton.textContent=detailRow.hidden?say('Details','تفاصيل'):say('Hide','إخفاء');});
    });
    table.append(body);wrap.append(table);target.append(wrap);applyPinnedOffsets(table);
  }
  function applyPinnedOffsets(table) {
    table.querySelectorAll('.rb-doctor-pinned').forEach(cell=>{cell.classList.remove('rb-doctor-pinned');cell.style.insetInlineStart='';});
    let offset=0;
    layout.order.filter(key=>layout.visible.includes(key)&&layout.pinned.includes(key)).forEach(key=>{
      const cells=[...table.querySelectorAll(`[data-doctor-column="${key}"]`)];cells.forEach(cell=>{cell.classList.add('rb-doctor-pinned');cell.style.insetInlineStart=`${offset}px`;});
      offset+=layout.widths[key]||160;
    });
  }
  const filterParamKeys=['q','patient_id','accession','priority','modality','exam_status','pacs_status','report_status','sla_status','date_from','date_to'];
  const initial=new URLSearchParams(location.search);
  const appliedSearch={q:initial.get('q')||'',patient_id:initial.get('patient_id')||'',accession:initial.get('accession')||''};
  const appliedAdvanced={priority:initial.get('priority')||'',modality:initial.get('modality')||'',exam_status:initial.get('exam_status')||'',pacs_status:initial.get('pacs_status')||'',report_status:initial.get('report_status')||'',sla_status:initial.get('sla_status')||'',date_from:initial.get('date_from')||'',date_to:initial.get('date_to')||''};
  search.value=appliedSearch.q;patientIdFilter.value=appliedSearch.patient_id;examCodeFilter.value=appliedSearch.accession;dateFrom.value=appliedAdvanced.date_from;dateTo.value=appliedAdvanced.date_to;
  let initialFiltersApplied=false;
  function appliedPayload(){return {...appliedSearch,...appliedAdvanced};}
  function syncUrl(){
    const url=new URL(location.href);filterParamKeys.forEach(key=>url.searchParams.delete(key));
    Object.entries(appliedPayload()).forEach(([key,value])=>{if(value)url.searchParams.set(key,value);});
    history.replaceState(null,'',url.pathname+(url.searchParams.toString()?`?${url.searchParams.toString()}`:'')+url.hash);
  }
  function updateAdvancedOpenState(){
    if(!advancedFilters)return;
    const hasAdvanced=Object.values(appliedAdvanced).some(Boolean);
    if(hasAdvanced)advancedFilters.open=true;
  }
  const filterLabels={q:say('Search','بحث'),patient_id:say('Patient ID','رقم المريض'),accession:say('Exam / Accession','الفحص / Accession'),priority:say('Priority','الأولوية'),modality:say('Modality','نوع الجهاز'),exam_status:say('Exam status','حالة الفحص'),pacs_status:say('PACS status','حالة PACS'),report_status:say('Report status','حالة التقرير'),sla_status:say('SLA status','حالة SLA'),date_from:say('From','من'),date_to:say('To','إلى')};
  function clearAppliedKey(key){
    if(Object.prototype.hasOwnProperty.call(appliedSearch,key)){appliedSearch[key]='';if(key==='q')search.value='';if(key==='patient_id')patientIdFilter.value='';if(key==='accession')examCodeFilter.value='';}
    if(Object.prototype.hasOwnProperty.call(appliedAdvanced,key)){appliedAdvanced[key]='';if(filters[key])filters[key].value='';if(key==='date_from')dateFrom.value='';if(key==='date_to')dateTo.value='';}
    datePresetButtons.forEach(button=>button.classList.remove('is-active'));syncUrl();renderCases();
  }
  function renderActiveFilters(){
    if(!activeFilters||!activeFilterChips)return;
    activeFilterChips.replaceChildren();
    const values=Object.entries(appliedPayload()).filter(([,value])=>Boolean(value));
    activeFilters.hidden=!values.length;
    values.forEach(([key,value])=>{const chip=node('button',`${filterLabels[key]||key}: ${value} ×`,'rb-doctor-filter-chip');chip.type='button';chip.addEventListener('click',()=>clearAppliedKey(key));activeFilterChips.append(chip);});
  }
  function renderCases() {
    cases.replaceChildren();
    const term = appliedSearch.q.toLocaleLowerCase();
    externalCases.replaceChildren();
    const archivedRequested=Boolean(term||appliedSearch.patient_id||appliedSearch.accession||appliedAdvanced.report_status==='FINAL');
    const selected = rows.filter(c => {
      if(String(c.report_status||'').toUpperCase()==='FINAL'&&!archivedRequested) return false;
      const textMatch=[c.accession,c.patient_id,c.patient,c.patient_worklist,c.modality,c.procedure,c.procedure_code,c.body_part,c.branch,c.device,c.referring_doctor,c.clinical_indication,c.clinical_diagnosis,c.center,c.reported_by,c.verified_by,c.finalized_by].join(' ').toLocaleLowerCase().includes(term);
      const patientMatch=!appliedSearch.patient_id||String(c.patient_id||'').toLocaleLowerCase().includes(appliedSearch.patient_id.toLocaleLowerCase());
      const examTerm=appliedSearch.accession.toLocaleLowerCase(), examMatch=!examTerm||[c.accession,c.procedure_code,c.procedure].join(' ').toLocaleLowerCase().includes(examTerm);
      const selectMatch=Object.entries(filters).every(([key])=>!appliedAdvanced[key]||String(c[key]||'')===appliedAdvanced[key]);
      const caseDate=String(c.scheduled_at||'').slice(0,10), fromMatch=!appliedAdvanced.date_from||caseDate>=appliedAdvanced.date_from, toMatch=!appliedAdvanced.date_to||caseDate<=appliedAdvanced.date_to;
      return textMatch&&patientMatch&&examMatch&&selectMatch&&fromMatch&&toMatch;
    });
    resultCount.textContent=say(`${selected.length} of ${rows.length} cases`,`${selected.length} من ${rows.length} حالة`);
    function appendCases(target, source) { renderCaseTable(target, selected.filter(c => c.source === source)); }
    appendCases(cases, 'INTERNAL');
    appendCases(externalCases, 'EXTERNAL');
    renderActiveFilters();
  }
  function preserveRequestedOption(control,value){if(value&&![...control.options].some(option=>option.value===value))control.append(new Option(value,value));}
  function populateFilters() {
    Object.entries(filters).forEach(([key,control])=>{
      const current=control.value, values=[...new Set(rows.map(row=>String(row[key]||'')).filter(Boolean))].sort();
      control.replaceChildren(new Option(say('All','الكل'),'')); values.forEach(value=>control.append(new Option(value,value))); preserveRequestedOption(control,appliedAdvanced[key]);control.value=appliedAdvanced[key]||current||'';
    });
  }
  function clearAllFilters() {
    Object.keys(appliedSearch).forEach(key=>appliedSearch[key]='');Object.keys(appliedAdvanced).forEach(key=>appliedAdvanced[key]='');
    search.value=''; patientIdFilter.value=''; examCodeFilter.value=''; dateFrom.value=''; dateTo.value=''; Object.values(filters).forEach(control=>{control.value='';}); datePresetButtons.forEach(button=>button.classList.remove('is-active')); syncUrl();renderCases();
  }
  function clearOnlyAdvancedFilters(){Object.keys(appliedAdvanced).forEach(key=>appliedAdvanced[key]='');dateFrom.value='';dateTo.value='';Object.values(filters).forEach(control=>{control.value='';});datePresetButtons.forEach(button=>button.classList.remove('is-active'));syncUrl();renderCases();}
  function applySearchFilters(){appliedSearch.q=search.value.trim();appliedSearch.patient_id=patientIdFilter.value.trim();appliedSearch.accession=examCodeFilter.value.trim();syncUrl();renderCases();}
  function applyAdvancedFilterValues(){Object.keys(filters).forEach(key=>appliedAdvanced[key]=filters[key].value);appliedAdvanced.date_from=dateFrom.value;appliedAdvanced.date_to=dateTo.value;syncUrl();updateAdvancedOpenState();renderCases();}
  function filterPayload(){return appliedPayload();}
  function fillSavedViewForm(form){form.querySelectorAll('input[data-doctor-filter-value]').forEach(item=>item.remove());Object.entries(filterPayload()).forEach(([key,value])=>{if(!value)return;const input=document.createElement('input');input.type='hidden';input.name=key;input.value=value;input.dataset.doctorFilterValue='1';form.append(input);});}
  document.querySelectorAll('[data-doctor-saved-update],[data-doctor-saved-create]').forEach(form=>form.addEventListener('submit',()=>fillSavedViewForm(form)));
  searchButton.addEventListener('click',applySearchFilters);
  [search,patientIdFilter,examCodeFilter].forEach(control=>control.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();applySearchFilters();}}));
  if(applyAdvancedFilters)applyAdvancedFilters.addEventListener('click',applyAdvancedFilterValues);
  if(clearAdvancedFilters)clearAdvancedFilters.addEventListener('click',clearOnlyAdvancedFilters);
  clearFilters.addEventListener('click',clearAllFilters);
  function localDate(value){return new Date(value.getTime()-value.getTimezoneOffset()*60000).toISOString().slice(0,10);}
  datePresetButtons.forEach(button=>button.addEventListener('click',()=>{
    const now=new Date(), preset=button.dataset.doctorDatePreset; let from='',to='';
    if(preset==='today'){from=to=localDate(now);}
    if(preset==='yesterday'){const day=new Date(now);day.setDate(day.getDate()-1);from=to=localDate(day);}
    if(preset==='7days'){const day=new Date(now);day.setDate(day.getDate()-6);from=localDate(day);to=localDate(now);}
    if(preset==='month'){from=localDate(new Date(now.getFullYear(),now.getMonth(),1));to=localDate(now);}
    dateFrom.value=from;dateTo.value=to;appliedAdvanced.date_from=from;appliedAdvanced.date_to=to;datePresetButtons.forEach(item=>item.classList.toggle('is-active',item===button));syncUrl();renderCases();
  }));
  async function refresh() {
    if (loading || posting) return;
    loading = true;
    try {
      const r = await fetch(root.dataset.api, {credentials:'same-origin', cache:'no-store', redirect:'error'});
      if (!r.ok) throw new Error('Session or request failed');
      const data = await r.json();
      if (!data.ok || !Array.isArray(data.cases) || !Array.isArray(data.offers)) throw new Error('Invalid response');
      if(!layoutLoaded){layout=normalizeLayout(data.column_layout||loadLocalLayout());layoutLoaded=true;storeLayout(false);syncColumnMenu();}
      rows = data.cases; populateFilters();if(!initialFiltersApplied){Object.entries(filters).forEach(([key,control])=>{preserveRequestedOption(control,appliedAdvanced[key]);control.value=appliedAdvanced[key];});dateFrom.value=appliedAdvanced.date_from;dateTo.value=appliedAdvanced.date_to;initialFiltersApplied=true;updateAdvancedOpenState();syncUrl();}renderCases(); offers.replaceChildren();
      data.offers.forEach(offer => {
        const el = card(offer.case), actions = node('div', undefined, 'actions');
        el.append(node('small', say('Expires: ', 'ينتهي: ') + new Date(offer.expires_at).toLocaleTimeString()));
        ['ACCEPT','REJECT','BUSY'].forEach(action => {
          const labels = {ACCEPT:say('Accept','قبول'),REJECT:say('Reject','رفض'),BUSY:say('Busy','مشغول')};
          const button = node('button', labels[action], 'btn' + (action === 'ACCEPT' ? ' primary' : ''));
          button.type = 'button'; button.onclick = () => respond(offer, action);
          actions.append(button);
        });
        el.append(actions); offers.append(el);
      });
      if (!data.offers.length) offers.append(node('p', say('No pending offers.', 'لا توجد عروض معلّقة.')));
    } catch (_) {
      offers.replaceChildren(); cases.replaceChildren(); externalCases.replaceChildren(); rows = [];
      message.textContent = say('Update failed. Check your login, then refresh.', 'تعذر التحديث. تحقق من تسجيل الدخول ثم حدّث الصفحة.');
    } finally { loading = false; }
  }
  async function respond(offer, action) {
    if (posting || loading) return;
    if (action !== 'ACCEPT' && !window.confirm(say('Confirm response for ', 'تأكيد الرد للحالة ') + offer.case.accession + '?')) return;
    posting = true;
    root.querySelectorAll('button').forEach(b => { b.disabled = true; });
    // Open synchronously with the click, so browser popup blockers do not hide acceptance.
    let viewer = action === 'ACCEPT' ? window.open('about:blank', '_blank') : null;
    if (viewer) { viewer.opener = null; viewer.document.title = say('Accepting offer…', 'جارٍ قبول العرض…'); }
    try {
      const r = await fetch(offer.respond_url, {
        method:'POST', credentials:'same-origin', redirect:'error',
        headers:{'X-RadBridge-Workspace':'doctor'},
        body:new URLSearchParams({action})
      });
      const data = await r.json();
      if (!r.ok || !data.ok) throw new Error('Response not confirmed');
      message.textContent = say('Response saved.', 'تم حفظ الرد.');
      if (data.open_url) {
        const url = openLink(data.open_url);
        const link = node('a', say('Open images & report', 'فتح الصور والتقرير'));
        link.href = url; link.target = '_blank'; link.rel = 'noopener'; message.append(link);
        if (viewer && !viewer.closed) viewer.location.replace(url);
      }
    } catch (_) {
      if (viewer && !viewer.closed) viewer.close();
      message.textContent = say('Response not confirmed. Review the updated cases/offers before retrying.', 'لم يتأكد الرد. راجع الحالات والعروض المحدثة قبل إعادة المحاولة.');
    } finally {
      posting = false;
      root.querySelectorAll('button').forEach(b => { b.disabled = false; });
      await refresh();
    }
  }
  const heartbeat = () => { if (root.dataset.heartbeat) fetch(root.dataset.heartbeat, {method:'POST',credentials:'same-origin',redirect:'error'}).catch(() => {}); };
  document.getElementById('rbWorkspaceRefresh').onclick = refresh;
  layout=loadLocalLayout();
  buildColumnMenu();
  refresh(); heartbeat();
  window.setInterval(() => { if (!document.hidden) refresh(); }, 20000);
  window.setInterval(heartbeat, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { refresh(); heartbeat(); } });
})();
