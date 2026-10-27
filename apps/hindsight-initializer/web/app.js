'use strict';
const $ = (id) => document.getElementById(id);
const names = { codex: 'Codex', claude: 'Claude Code', hermes: 'Hermes', document: '文档' };
const statusNames = { pending:'待提取', ready:'待处理', active:'活跃', skipped:'跳过', duplicate:'重复', error:'解析失败', approved:'已核验', review_required:'待复核', no_gain:'无收益' };
const jobNames = {idle:'待命', running:'执行中', completed:'完成', failed:'失败', cancelled:'已取消'};
let key = location.hash.slice(1);
if (key) {sessionStorage.setItem('setup-key',key);history.replaceState(null,'',location.pathname);}
else key = sessionStorage.getItem('setup-key') || '';
let state, selected=new Set(), uploadSelected=new Set(), consentScope='', detailProduct, sourcePage=0, discoveryMode='all', loaded=false, lastInventory='',lastProducts='',tab='sources', toastTimer, browseTarget, folderParent, busy=false;
let selectionTouched=false;
const fmt = (n) => Number(n || 0).toLocaleString('zh-CN');
const fileSize = (n) => n>=1048576?(n/1048576).toFixed(1)+' MB':n>=1024?(n/1024).toFixed(1)+' KB':fmt(n)+' B';
const icon = (name) => {
  const i=document.createElement('i'); i.dataset.lucide=name; return i;
};
function icons(){ if(window.lucide) lucide.createIcons(); }
function toast(message){
  $('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>$('toast').hidden=true,5000);
}
async function api(path, data){
  const opts={headers:{'X-Setup-Token':key}};
  if(data!==undefined){opts.method='POST';opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(data);}
  const res=await fetch('/api/'+path,opts);
  const value=await res.json();
  if(!res.ok)throw new Error(value.error || '请求失败');
  return value;
}
async function guarded(fn){try{await fn();}catch(err){toast(err.message);}}
function step(id){
  document.querySelectorAll('.view').forEach(e=>e.hidden=e.id!==id);
  document.querySelectorAll('.step').forEach(e=>e.classList.toggle('active',e.dataset.step===id));
  $(id).querySelector('.section-heading').after($('task-progress'));
}
document.querySelectorAll('.step').forEach(e=>e.onclick=()=>step(e.dataset.step));
function button(name,title,fn){
  const b=document.createElement('button');b.type='button';b.className='icon';b.title=title;b.setAttribute('aria-label',title);b.append(icon(name));b.onclick=fn;return b;
}
function addRoot(value=''){
  const row=document.createElement('div');row.className='root-item';
  const input=document.createElement('input');input.value=value;input.placeholder='项目或文档目录的绝对路径';input.setAttribute('aria-label','文档目录');
  row.append(input,button('folder-open','选择文档目录',()=>browse(input)),button('x','移除此目录',()=>{row.remove();$('roots-empty').hidden=$('roots').children.length>0;}));
  $('roots').append(row);$('roots-empty').hidden=true;icons();return input;
}
function buildConfig(c){
  const form=$('connection-form');
  ['api_url','bank_id','model_url','model'].forEach(name=>form.elements[name].value=c[name] || '');
  form.elements.model_key.placeholder=c.has_model_key?'已保存，留空保持不变':'本地模型可留空';
  $('idle-hours').value=c.idle_hours;$('max-size').value=c.max_file_mb;
  $('agent-list').replaceChildren();
  ['codex','claude','hermes'].forEach(name=>{
    const a=c.agents[name] || {};
    const row=document.createElement('div');row.className='agent';row.dataset.agent=name;
    const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=!!a.enabled;
    label.append(check,icon(name==='codex'?'terminal':name==='claude'?'message-square':'bot'),document.createTextNode(names[name]));
    const input=document.createElement('input');input.type='text';input.value=a.path || '';input.setAttribute('aria-label',names[name]+' 数据目录');
    row.append(label,input,button('folder-open','选择 '+names[name]+' 数据目录',()=>browse(input)));
    $('agent-list').append(row);
  });
  $('roots').replaceChildren();(c.document_roots || []).forEach(addRoot);
  $('roots-empty').hidden=$('roots').children.length>0;
  icons();
}
function configDraft(){
  const f=$('connection-form'),agents={};
  document.querySelectorAll('.agent').forEach(row=>agents[row.dataset.agent]={enabled:row.querySelector('[type=checkbox]').checked,path:row.querySelector('[type=text]').value.trim()});
  return {
    api_url:f.elements.api_url.value.trim().replace(/\/+$/,''),
    bank_id:f.elements.bank_id.value.trim(),
    model_url:f.elements.model_url.value.trim().replace(/\/+$/,''),
    model:f.elements.model.value.trim(),model_key:f.elements.model_key.value,
    agents,document_roots:Array.from($('roots').querySelectorAll('input')).map(e=>e.value.trim()).filter(Boolean),
    idle_hours:Number($('idle-hours').value),max_file_mb:Number($('max-size').value)
  };
}
async function save(){
  const result=await api('config',configDraft());
  state.config=result.config;
  $('connection-form').elements.model_url.value=result.config.model_url || '';
  $('connection-form').elements.model_key.value='';
  $('connection-form').elements.model_key.placeholder=result.config.has_model_key?'已保存，留空保持不变':'本地模型可留空';
  renderClients();
  renderProductSelection();
}
function badge(status){
  const e=document.createElement('span');e.className='badge';
  if(['ready','approved','completed'].includes(status))e.classList.add('good');
  if(['error','review_required','failed'].includes(status))e.classList.add('bad');
  if(status==='running')e.classList.add('running');
  e.textContent=statusNames[status] || jobNames[status] || status;return e;
}
function renderSources(){
  const inv=state.inventory || {sources:[]},filter=$('filter').value.toLowerCase(),rows=$('source-rows');
  rows.replaceChildren();
  const available=(inv.sources || []).filter(s=>!['error','unsupported','skipped'].includes(s.status));
  const sources=available.filter(s=>(s.title+' '+s.path+' '+s.project).toLowerCase().includes(filter));
  sourcePage=Math.min(sourcePage,Math.max(0,Math.ceil(sources.length/100)-1));
  $('source-pagination').hidden=sources.length<=100;
  $('source-page-info').textContent=fmt(sourcePage*100+1)+'–'+fmt(Math.min(sources.length,(sourcePage+1)*100))+' / '+fmt(sources.length);
  $('source-prev').disabled=sourcePage===0;$('source-next').disabled=(sourcePage+1)*100>=sources.length;
  for(const s of sources.slice(sourcePage*100,(sourcePage+1)*100)){
    const tr=document.createElement('tr'),tds=Array.from({length:6},()=>document.createElement('td'));tr.dataset.sourceId=s.id;
    const check=document.createElement('input');check.type='checkbox';check.disabled=busy || !['pending','ready'].includes(s.status);check.checked=selected.has(s.id);check.setAttribute('aria-label','选择 '+s.title);
    check.onchange=()=>{selectionTouched=true;if(check.checked)selected.add(s.id);else selected.delete(s.id);renderSelection();};
    tds[0].append(check);
    const title=document.createElement('b');title.textContent=s.title;
    const sub=document.createElement('small');sub.textContent=s.project;sub.title=s.path;
    tds[1].append(title,sub);tds[2].textContent=names[s.agent] || s.agent;tds[3].textContent=s.sha256?fmt(s.chars):s.size_bytes!==undefined?fileSize(s.size_bytes):fmt(s.chars);
    const st=badge(s.status);st.title=s.reason || '';tds[4].append(st);
    if(s.sha256)tds[5].append(button('file-text','预览脱敏正文',()=>preview(s.id,'source',s.title)));
    tds.forEach(e=>tr.append(e));rows.append(tr);
  }
  $('source-empty').hidden=sources.length>0;
  $('source-empty').querySelector('span').textContent=filter?'没有匹配的来源':'尚无扫描结果';
  $('source-count').textContent=fmt(available.length);
  $('metric-ready').textContent=fmt((inv.ready || 0)+(inv.pending || 0));$('metric-chars').textContent=fmt(inv.chars);
  renderSelection();icons();
}
function renderSelection(){
  const chosen=(state.inventory.sources || []).filter(s=>selected.has(s.id));
  const pending=chosen.filter(s=>s.status==='pending').length, readyChosen=chosen.filter(s=>s.status==='ready').length;
  $('selection-count').textContent='已选 '+fmt(selected.size)+' 篇'+(pending?' · '+fmt(pending)+' 篇待提取':'');
  const eligible=(state.inventory.sources || []).filter(s=>['pending','ready'].includes(s.status));
  $('select-all').checked=eligible.length>0 && eligible.every(s=>selected.has(s.id));
  $('select-all').indeterminate=selected.size>0 && !$('select-all').checked;
  $('select-all').disabled=busy;
  $('extract').textContent=pending?'提取所选 '+fmt(pending)+' 篇':state.inventory.pending>0?'提取待处理正文':'正文已提取';
  $('extract').disabled=busy || (!(state.inventory.pending>0) && !pending);
  $('extract').hidden=false;
  const modelReady=!!state.config.model_url?.trim() && !!state.config.model?.trim();
  $('compact').disabled=busy || readyChosen===0 || pending>0 || !modelReady;
  $('compact').title=pending?'所选文档还未提取正文，请先提取':modelReady?'压缩所选来源':'请先配置压缩模型接口地址和模型名称';
  $('source-action-note').textContent=busy?jobStatus(state.job)+'，可在上方查看进度；完成或取消后可继续选择文件。':pending?'已选文档需要先提取正文，完成后即可压缩。提取不联网；压缩调用模型，上传需单独确认。':'提取仅在本机读取正文；压缩会调用所配置的模型。上传需在成品列表单独确认。';
  $('configure-model').hidden=modelReady;
  $('configure-model').disabled=busy;
}
function renderProducts(){
  const products=state.products || [],filter=$('filter').value.toLowerCase();
  $('product-rows').replaceChildren();
  const visible=products.filter(p=>(p.title+' '+(p.reason || '')).toLowerCase().includes(filter));
  for(const p of visible){
    const tr=document.createElement('tr'),tds=Array.from({length:5},()=>document.createElement('td'));
    tr.dataset.productId=p.id;
    const check=document.createElement('input');check.type='checkbox';check.checked=uploadSelected.has(p.id);check.disabled=busy || p.status!=='approved' || !p.sha256;check.setAttribute('aria-label','选择上传 '+(p.title || '未通过核验的归档组'));
    check.onchange=()=>{if(check.checked)uploadSelected.add(p.id);else uploadSelected.delete(p.id);renderProductSelection();};tds[0].append(check);
    const title=document.createElement('b');title.textContent=p.title || '未通过核验的归档组';
    const sub=document.createElement('small');sub.textContent=p.reason || fmt((p.source_ids || []).length)+' 个来源';tds[1].append(title,sub);
    tds[2].textContent=fmt(p.input_chars)+' → '+fmt(p.chars);tds[3].append(badge(p.status));
    tds[4].append(button('file-text','查看提炼明细',()=>productDetails(p.id)));
    tds.forEach(e=>tr.append(e));$('product-rows').append(tr);
  }
  const approved=products.filter(p=>p.status==='approved');
  $('product-count').textContent=fmt(products.length);$('metric-approved').textContent=fmt(approved.length);
  $('metric-output').textContent=fmt(approved.reduce((n,p)=>n+p.chars,0));$('product-empty').hidden=visible.length>0;
  renderProductSelection();
  icons();
}
function renderProductSelection(){
  const approved=(state.products || []).filter(p=>p.status==='approved' && p.sha256);
  const valid=new Set(approved.map(p=>p.id));
  uploadSelected=new Set([...uploadSelected].filter(id=>valid.has(id)));
  const scope=JSON.stringify([state.config.api_url,state.config.bank_id,approved.filter(p=>uploadSelected.has(p.id)).map(p=>[p.id,p.sha256])]);
  if(scope!==consentScope){consentScope=scope;$('confirm-upload').checked=false;}
  $('product-selection-count').textContent='已选 '+fmt(uploadSelected.size)+' 篇';
  $('select-all-products').checked=approved.length>0 && approved.every(p=>uploadSelected.has(p.id));
  $('select-all-products').indeterminate=uploadSelected.size>0 && !$('select-all-products').checked;
  $('select-all-products').disabled=busy || !approved.length;
  $('confirm-upload').disabled=busy || !uploadSelected.size;
  $('upload').disabled=busy || !uploadSelected.size || !$('confirm-upload').checked;
  if(detailProduct){
    const current=approved.find(p=>p.id===detailProduct.id && p.sha256===detailProduct.sha256);
    $('detail-select').disabled=busy || !current;
    $('detail-select').checked=!!current && uploadSelected.has(current.id);
  }
}
function switchTab(which){
  tab=which;$('source-panel').hidden=which!=='sources';$('product-panel').hidden=which!=='products';
  ['sources','products'].forEach(t=>{$('tab-'+t).classList.toggle('active',which===t);$('tab-'+t).setAttribute('aria-selected',String(which===t));});
}
function renderClients(){
  $('client-summary').replaceChildren();
  ['codex','claude','hermes'].forEach(name=>{
    const a=state.config.agents[name] || {};
    const row=document.createElement('div');row.className='client-row';
    const info=document.createElement('div'),b=document.createElement('strong'),small=document.createElement('small');
    b.textContent=names[name];small.textContent=a.path || '未配置目录';info.append(b,small);
    const tag=document.createElement('span');tag.className='badge'+(a.enabled?' good':'');tag.textContent=a.enabled?'已选择':'未选择';
    row.append(icon(name==='codex'?'terminal':name==='claude'?'message-square':'bot'),info,tag);$('client-summary').append(row);
  });
  $('target-bank').textContent=state.config.bank_id;
  $('state-root').textContent=state.data_dir || '';
  icons();
}
let jobVersion='';
function duration(seconds){
  const value=Math.max(0,Math.floor(seconds || 0));
  return value<60?value+' 秒':value<3600?Math.floor(value/60)+' 分 '+value%60+' 秒':Math.floor(value/3600)+' 小时 '+Math.floor(value%3600/60)+' 分';
}
function renderProgress(){
  if(!state)return;
  const j=state.job || {},p=j.progress || {},running=j.status==='running',known=p.total>0;
  $('task-progress').hidden=!j.kind;
  $('task-progress').setAttribute('aria-busy',String(running));
  $('task-progress').dataset.status=j.status || '';
  $('progress-stage').textContent=(j.kind==='discover'?'已发现 '+fmt(p.completed)+' 个文档':(p.stage || '任务'))+' · '+jobStatus(j);
  const done=Math.min(p.completed || 0,p.total || Infinity);
  $('progress-count').textContent=known?fmt(done)+' / '+fmt(p.total)+' '+(p.unit || '')+' · '+Math.floor(done/p.total*100)+'%':(p.completed?('已处理 '+fmt(p.completed)+' '+(p.unit || '')+' · '):'')+(running?'总量未确定':(jobNames[j.status] || ''));
  const bar=$('progress-bar');
  if(known){bar.max=p.total;bar.value=done;}else if(running){bar.removeAttribute('value');}else{bar.max=1;bar.value=j.status==='completed'?1:0;}
  $('progress-detail').textContent=(p.detail || (running?(known?'逐项处理，完成结果会保存到本机':'统计范围或等待处理，暂无法估算剩余时间'):'本地结果已保留'))+(p.waiting?' · '+p.waiting:'');
  const now=j.finished_at?Date.parse(j.finished_at):Date.now(),start=Date.parse(j.started_at || '');
  const elapsed=Number.isFinite(start)?Math.max(0,(now-start)/1000):0;
  let estimate='';
  if(running && known && done>=3 && done<p.total){
    const phaseStart=Date.parse(p.phase_started_at || j.started_at),phaseElapsed=(Date.now()-phaseStart)/1000;
    if(phaseElapsed>=2)estimate=' · 预计剩余 '+duration(phaseElapsed/done*(p.total-done));
  }
  $('progress-time').textContent='已用 '+duration(elapsed)+(running?(estimate || ' · 剩余时间估算中'):'');
  $('progress-current').textContent=p.current || '';$('progress-current').title=p.current || '';
}
function jobStatus(j){
  const active={discover:'扫描中',catalog:'扫描中',scan:'提取中',compact:'压缩中',upload:'上传中',test:'连接测试中',install:'配置中',restore:'恢复中'};
  return j.status==='running'?(active[j.kind] || '处理中'):(jobNames[j.status] || j.status || '待命');
}
function renderJob(){
  const j=state.job;busy=j.status==='running';
  const next=badge(j.status);next.textContent=jobStatus(j);next.id='job-badge';$('job-badge').replaceWith(next);
  $('cancel').hidden=!busy;
  $('job-error').hidden=!j.error;$('job-error').textContent=j.error || '';
  const version=JSON.stringify(j.log);
  if(version!==jobVersion){
    jobVersion=version;$('logs').replaceChildren();
    for(const line of j.log || []){const p=document.createElement('p');p.textContent=line;$('logs').append(p);}
    if(!(j.log || []).length){const p=document.createElement('p');p.className='log-placeholder';p.textContent=busy?'任务启动中…':'暂无执行记录';$('logs').append(p);}
    $('logs').scrollTop=$('logs').scrollHeight;
  }
  ['scan','rescan','extract','discover','start-discovery','test-model','test-remote','install','restore','save-sources'].forEach(id=>$(id).disabled=busy);
  $('connection-form').querySelector('[type=submit]').disabled=busy;
  const activeButtons={scan:['scan','extract'],compact:['compact'],upload:['upload'],discover:['discover'],catalog:['rescan'],install:['install'],restore:['restore'],test:['test-model','test-remote']};
  document.querySelectorAll('button[data-running]').forEach(b=>b.removeAttribute('data-running'));
  if(busy)for(const id of activeButtons[j.kind] || [])$(id).dataset.running='true';
  const sourceStatus=new Map((state.inventory.sources || []).map(s=>[s.id,s.status]));
  document.querySelectorAll('#source-rows input').forEach(input=>{input.disabled=busy || !['pending','ready'].includes(sourceStatus.get(input.closest('tr').dataset.sourceId));});
  renderProgress();renderSelection();renderProducts();
}
async function refresh(){
  const previous=state && state.job;
  const next=await api('state');state=next;
  if(!loaded){
    buildConfig(state.config);$('platform').textContent=state.os==='windows'?'Windows':'Linux / Web';
    $('credential-note').textContent=state.os==='windows'?'模型密钥由 Windows DPAPI 加密保存在本机':'模型密钥保存在本机，文件权限 0600';
    loaded=true;renderClients();
    if((state.inventory.sources || []).length || (state.products || []).length){step('archive');if((state.products || []).length)switchTab('products');}
  }
  const inv=JSON.stringify(state.inventory);
  if(inv!==lastInventory){
    lastInventory=inv;
    if(!selectionTouched)selected=new Set((state.inventory.sources || []).filter(s=>s.status==='ready').map(s=>s.id));
    else {const valid=new Set((state.inventory.sources || []).filter(s=>['pending','ready'].includes(s.status)).map(s=>s.id));selected=new Set([...selected].filter(id=>valid.has(id)));}
    renderSources();
  }
  const ps=JSON.stringify(state.products);
  if(ps!==lastProducts){lastProducts=ps;uploadSelected.clear();$('confirm-upload').checked=false;renderProducts();}
  renderJob();
  if(previous && previous.status==='running' && next.job.status!=='running'){
    if(next.job.status==='completed'){
      if(next.job.kind==='compact'){switchTab('products');step('archive');}
      if(['scan','catalog','discover'].includes(next.job.kind)){switchTab('sources');step('archive');}
      toast(next.job.kind==='compact'?'提炼完成，结果已保存在本地':next.job.kind==='catalog'?'文档清单已更新':'任务完成');
    } else if(next.job.status==='failed')toast(next.job.error || '任务失败');
    if(next.job.kind==='discover'){
      $('roots').replaceChildren();(next.config.document_roots || []).forEach(addRoot);
      $('roots-empty').hidden=$('roots').children.length>0;
    }
  }
}
async function start(path,data={}){
  const previous=state.job;
  state.job={kind:path,status:'running',log:[]};renderJob();
  try{await api(path,data);await refresh();}
  catch(err){state.job=previous;renderJob();throw err;}
}
async function scan(fromCatalog=false){
  await save();step('archive');switchTab('sources');
  const hasPending=(state.inventory.sources || []).some(s=>s.status==='pending' && selected.has(s.id));
  const ids=fromCatalog && hasPending?[...selected]:[];
  if(!ids.length)selectionTouched=false;
  await start('scan',fromCatalog?(ids.length?{ids}:{}):{scope:true});
}
async function preview(id,kind,title){
  await guarded(async()=>{
    const result=await api('preview?id='+encodeURIComponent(id)+'&kind='+kind);
    $('preview-title').textContent=title;$('preview-text').textContent=result.text;
    $('preview-note').textContent=result.truncated?'仅预览前 12,000 字，完整正文保存在本机归档目录。':'';
    $('preview-dialog').showModal();
  });
}
function detailTab(which){
  ['text','sources'].forEach(t=>{
    $('detail-'+t+'-panel').hidden=t!==which;
    $('detail-tab-'+t).classList.toggle('active',t===which);
    $('detail-tab-'+t).setAttribute('aria-selected',String(t===which));
  });
}
async function productDetails(id){
  await guarded(async()=>{
    const result=await api('preview?kind=product&id='+encodeURIComponent(id)),p=result.product;
    detailProduct=p;
    $('product-title').textContent=p.title || '未通过核验的归档组';
    $('product-detail-status').replaceChildren(badge(p.status));
    $('detail-input').textContent=fmt(p.input_chars);$('detail-output').textContent=fmt(p.chars);
    $('detail-ratio').textContent=p.input_chars?((p.chars || 0)/p.input_chars*100).toFixed(1)+'%':'-';
    $('product-reason').hidden=!p.reason;$('product-reason').textContent=p.reason || '';
    $('product-text').textContent=result.text || '暂无可用的提炼正文';
    let references=Object.entries(p.source_map || {});
    if(!references.length)references=(state.inventory.sources || []).filter(s=>(p.source_ids || []).includes(s.id)).map((s,i)=>['S'+(i+1),s]);
    const represented=new Set(references.map(([,s])=>s.id));
    for(const s of state.inventory.sources || []){
      if((p.source_ids || []).includes(s.id) && !represented.has(s.id))references.push(['副本',s]);
    }
    references.sort((a,b)=>a[0].localeCompare(b[0],undefined,{numeric:true}));
    $('detail-source-count').textContent=fmt(references.length);
    $('product-sources').replaceChildren();
    for(const [label,s] of references){
      const li=document.createElement('li'),info=document.createElement('div'),title=document.createElement('strong'),meta=document.createElement('small'),path=document.createElement('code');
      title.textContent=label+' · '+(s.title || s.id);
      meta.textContent=[names[s.agent] || s.agent,s.project,fmt(s.chars)+' 字',s.modified].filter(Boolean).join(' · ');
      path.textContent=s.path || '';info.append(title,meta,path);
      if(s.session_id){const session=document.createElement('small');session.textContent='会话 ID：'+s.session_id;info.append(session);}
      li.append(info);
      if((state.inventory.sources || []).some(source=>source.id===s.id && source.sha256))li.append(button('file-text','查看来源正文',()=>preview(s.id,'source',s.title)));
      $('product-sources').append(li);
    }
    if(!references.length){const li=document.createElement('li');li.textContent='暂无来源明细';$('product-sources').append(li);}
    detailTab('text');renderProductSelection();icons();$('product-dialog').showModal();
  });
}
async function browse(input){
  browseTarget=input;await guarded(async()=>{await loadFolder(input.value || state.home);$('browse-dialog').showModal();});
}
function discoveryModeTab(mode){
  discoveryMode=mode;
  $('discovery-volumes').hidden=mode!=='all';$('discovery-directory-panel').hidden=mode!=='directory';
  ['all','directory'].forEach(t=>{$('discovery-'+t).classList.toggle('active',mode===t);$('discovery-'+t).setAttribute('aria-selected',String(mode===t));});
}
async function loadFolder(path){
  const result=await api('browse?path='+encodeURIComponent(path));
  $('folder-address').value=result.path;folderParent=result.parent;$('folder-items').replaceChildren();
  for(const dir of result.directories){
    const b=document.createElement('button');b.type='button';b.append(icon('folder'),document.createTextNode(dir.replace(/\\/g,'/').split('/').pop()));
    b.onclick=()=>guarded(()=>loadFolder(dir));$('folder-items').append(b);
  }
  if(!result.directories.length){const p=document.createElement('p');p.className='muted';p.textContent='此目录没有可显示的子目录';$('folder-items').append(p);}
  icons();
}
$('connection-form').onsubmit=(e)=>{e.preventDefault();guarded(async()=>{await save();step('sources');toast('配置已保存');});};
$('save-sources').onclick=()=>guarded(async()=>{await save();await start('catalog');});
$('test-remote').onclick=()=>guarded(async()=>{await save();await start('test',{kind:'remote'});});
$('test-model').onclick=()=>guarded(async()=>{await save();await start('test',{kind:'model'});});
$('add-root').onclick=()=>{const input=addRoot();browse(input);};
$('discover').onclick=()=>guarded(async()=>{
  const result=await api('document-volumes');$('volume-list').replaceChildren();
  for(const volume of result.volumes || []){const li=document.createElement('li'),title=document.createElement('strong'),path=document.createElement('code');title.textContent=volume.name;path.textContent=volume.path;li.append(icon('hard-drive'),title,path);$('volume-list').append(li);}
  $('discovery-root').value=state.home;discoveryModeTab('all');icons();$('discovery-dialog').showModal();
});
$('discovery-all').onclick=()=>discoveryModeTab('all');$('discovery-directory').onclick=()=>discoveryModeTab('directory');
$('discovery-browse').onclick=()=>browse($('discovery-root'));
$('start-discovery').onclick=()=>guarded(async()=>{
  await save();
  await start('discover',{mode:discoveryMode,path:discoveryMode==='directory'?$('discovery-root').value.trim():''});
  $('discovery-dialog').close();switchTab('sources');step('archive');
});
$('scan').onclick=()=>guarded(()=>scan(false));$('extract').onclick=()=>guarded(()=>scan(true));$('rescan').onclick=()=>guarded(()=>start('catalog'));
$('compact').onclick=()=>guarded(async()=>{await save();await start('compact',{ids:[...selected]});});
$('configure-model').onclick=()=>{step('connection');const f=$('connection-form');(f.elements.model_url.value.trim()?f.elements.model:f.elements.model_url).focus();};
$('upload').onclick=()=>guarded(async()=>{await start('upload',{confirm:$('confirm-upload').checked,ids:[...uploadSelected]});$('confirm-upload').checked=false;renderProductSelection();});
$('confirm-upload').onchange=renderProductSelection;
$('select-all-products').onchange=()=>{uploadSelected=new Set($('select-all-products').checked?(state.products || []).filter(p=>p.status==='approved' && p.sha256).map(p=>p.id):[]);renderProducts();};
$('detail-select').onchange=()=>{if(!detailProduct)return;if($('detail-select').checked)uploadSelected.add(detailProduct.id);else uploadSelected.delete(detailProduct.id);renderProducts();};
$('detail-tab-text').onclick=()=>detailTab('text');$('detail-tab-sources').onclick=()=>detailTab('sources');
$('install').onclick=()=>guarded(async()=>{await save();await start('install');});
$('restore').onclick=()=>guarded(()=>start('restore'));
$('cancel').onclick=()=>guarded(()=>api('cancel',{}));
$('select-all').onchange=()=>{
  selectionTouched=true;
  const checked=$('select-all').checked;
  selected=new Set(checked?(state.inventory.sources || []).filter(s=>['pending','ready'].includes(s.status)).map(s=>s.id):[]);renderSources();
};
$('tab-sources').onclick=()=>switchTab('sources');$('tab-products').onclick=()=>switchTab('products');
$('filter').oninput=()=>{sourcePage=0;renderSources();renderProducts();};
$('source-prev').onclick=()=>{sourcePage--;renderSources();$('source-rows').closest('.table-wrap').scrollTop=0;};
$('source-next').onclick=()=>{sourcePage++;renderSources();$('source-rows').closest('.table-wrap').scrollTop=0;};
document.querySelectorAll('.reveal').forEach(b=>b.onclick=()=>{const input=b.parentNode.querySelector('input');input.type=input.type==='password'?'text':'password';});
document.querySelectorAll('.close-dialog').forEach(b=>b.onclick=()=>b.closest('dialog').close());
$('folder-up').onclick=()=>guarded(()=>loadFolder(folderParent));$('folder-go').onclick=()=>guarded(()=>loadFolder($('folder-address').value));
$('folder-address').onkeydown=(e)=>{if(e.key==='Enter'){e.preventDefault();guarded(()=>loadFolder(e.target.value));}};
$('folder-select').onclick=()=>{if(browseTarget)browseTarget.value=$('folder-address').value;$('browse-dialog').close();};
icons();
guarded(refresh);
setInterval(()=>refresh().catch(()=>{}),1500);
setInterval(renderProgress,1000);
