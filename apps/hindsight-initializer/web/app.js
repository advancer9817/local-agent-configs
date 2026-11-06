'use strict';
const $ = (id) => document.getElementById(id);
const names = { codex: 'Codex', claude: 'Claude Code', hermes: 'Hermes', document: '文档' };
const statusNames = { discovered:'待提取', ready:'待处理', active:'活跃', skipped:'跳过', duplicate:'重复', error:'解析失败', approved:'已核验', review_required:'待复核', no_gain:'无收益' };
const jobNames = {idle:'待命', running:'执行中', completed:'完成', failed:'失败', cancelled:'已取消'};
let key = location.hash.slice(1);
if (key) {sessionStorage.setItem('setup-key',key);history.replaceState(null,'',location.pathname);}
else key = sessionStorage.getItem('setup-key') || '';
let state, selected=new Set(), loaded=false, lastInventory='',lastProducts='',tab='sources', toastTimer, browseTarget, folderParent, busy=false;
let sourcePage=0;
const pageSize=100;
const selectable=(s)=>s.status==='ready' || s.status==='discovered';
const fmt = (n) => Number(n || 0).toLocaleString('zh-CN');
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
  ['api_url','bank_id'].forEach(name=>form.elements[name].value=c[name] || '');
  form.elements.mcp_token.placeholder=c.has_token?'已保存，留空保持不变':'输入 Bearer Token';
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
    bank_id:f.elements.bank_id.value.trim(),mcp_token:f.elements.mcp_token.value,
    agents,document_roots:Array.from($('roots').querySelectorAll('input')).map(e=>e.value.trim()).filter(Boolean),
    idle_hours:Number($('idle-hours').value),max_file_mb:Number($('max-size').value)
  };
}
async function save(){
  const result=await api('config',configDraft());
  state.config=result.config;
  $('connection-form').elements.mcp_token.value='';
  $('connection-form').elements.mcp_token.placeholder=result.config.has_token?'已保存，留空保持不变':'输入 Bearer Token';
  renderClients();
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
  const sources=(inv.sources || []).filter(s=>(s.title+' '+s.path+' '+s.project).toLowerCase().includes(filter));
  const pages=Math.max(1,Math.ceil(sources.length/pageSize));
  sourcePage=Math.max(0,Math.min(sourcePage,pages-1));
  for(const s of sources.slice(sourcePage*pageSize,(sourcePage+1)*pageSize)){
    const tr=document.createElement('tr'),tds=Array.from({length:6},()=>document.createElement('td'));
    const check=document.createElement('input');check.type='checkbox';check.disabled=busy || !selectable(s);check.checked=selected.has(s.id);check.setAttribute('aria-label','选择 '+s.title);
    check.onchange=()=>{if(check.checked)selected.add(s.id);else selected.delete(s.id);renderSelection();};
    tds[0].append(check);
    const title=document.createElement('b');title.textContent=s.title;
    const sub=document.createElement('small');sub.textContent=s.path;sub.title=s.project;
    tds[1].append(title,sub);tds[2].textContent=names[s.agent] || s.agent;tds[3].textContent=s.status==='discovered'?'—':fmt(s.chars);
    const st=badge(s.status);st.title=s.reason || '';tds[4].append(st);
    if(s.sha256 && !['.docx','.pptx','.xlsx'].some(ext=>s.path.toLowerCase().endsWith(ext)))tds[5].append(button('file-text','预览上传来源',()=>preview(s.id,'source',s.title)));
    tds.forEach(e=>tr.append(e));rows.append(tr);
  }
  $('source-empty').hidden=sources.length>0;
  $('source-empty').querySelector('span').textContent=filter?'没有匹配的来源':'尚无扫描结果';
  $('source-count').textContent=fmt((inv.sources || []).length);
  $('source-pager').hidden=sources.length<=pageSize;
  $('source-page-count').textContent='共 '+fmt(sources.length)+' 篇';
  $('source-page').textContent=(sourcePage+1)+' / '+pages;
  $('source-prev').disabled=sourcePage===0;$('source-next').disabled=sourcePage===pages-1;
  $('metric-ready').textContent=fmt(inv.ready);$('metric-chars').textContent=fmt(inv.chars);
  renderSelection();icons();
}
function renderSelection(){
  $('selection-count').textContent='已选 '+fmt(selected.size)+' 篇';
  const ready=(state.inventory.sources || []).filter(selectable);
  $('select-all').checked=ready.length>0 && ready.every(s=>selected.has(s.id));
  $('select-all').indeterminate=selected.size>0 && !$('select-all').checked;
  const picked=(state.inventory.sources || []).filter(s=>selected.has(s.id));
  $('extract').disabled=busy || !picked.some(s=>s.status==='discovered');
  $('select-all').disabled=busy || ready.length===0;
  $('compact').disabled=busy || !picked.some(s=>s.status==='ready') || picked.some(s=>s.status==='discovered') || !$('confirm-source-upload').checked;
}
function renderProducts(){
  const products=state.products || [],filter=$('filter').value.toLowerCase();
  $('product-rows').replaceChildren();
  const visible=products.filter(p=>(p.title+' '+(p.reason || '')).toLowerCase().includes(filter));
  for(const p of visible){
    const tr=document.createElement('tr'),tds=Array.from({length:4},()=>document.createElement('td'));
    const title=document.createElement('b');title.textContent=p.title || '未通过核验的归档组';
    const sub=document.createElement('small');sub.textContent=p.reason || fmt(p.source_ids.length)+' 个来源';tds[0].append(title,sub);
    tds[1].textContent=fmt(p.input_chars)+' → '+fmt(p.chars);tds[2].append(badge(p.status));
    if(p.sha256)tds[3].append(button('file-text','预览精简成品',()=>preview(p.id,'product',p.title)));
    tds.forEach(e=>tr.append(e));$('product-rows').append(tr);
  }
  const approved=products.filter(p=>p.status==='approved');
  $('product-count').textContent=fmt(products.length);$('metric-approved').textContent=fmt(approved.length);
  $('metric-output').textContent=fmt(approved.reduce((n,p)=>n+p.chars,0));$('product-empty').hidden=visible.length>0;
  $('upload').disabled=busy || !approved.length || !$('confirm-upload').checked;
  icons();
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
function renderJob(){
  const j=state.job,wasBusy=busy;busy=j.status==='running';
  const next=badge(j.status);next.id='job-badge';$('job-badge').replaceWith(next);
  $('cancel').hidden=!busy;
  $('job-error').hidden=!j.error;$('job-error').textContent=j.error || '';
  const version=JSON.stringify(j.log);
  if(version!==jobVersion){
    jobVersion=version;$('logs').replaceChildren();
    for(const line of j.log || []){const p=document.createElement('p');p.textContent=line;$('logs').append(p);}
    if(!(j.log || []).length){const p=document.createElement('p');p.className='log-placeholder';p.textContent=busy?'任务启动中…':'暂无执行记录';$('logs').append(p);}
    $('logs').scrollTop=$('logs').scrollHeight;
  }
  ['scan','rescan','discover','test-model','test-remote','install','restore','save-sources'].forEach(id=>$(id).disabled=busy);
  const p=state.discovery || {},show=['discover','extract'].includes(j.kind);
  $('discovery-progress').hidden=!show;
  if(show){
    $('discovery-stage').textContent=j.kind==='discover'?'发现本地来源':'提取本地正文';
    $('scan-visited').textContent=(j.kind==='discover'?'已遍历 ':'总来源 ')+fmt(p.visited);
    $('scan-found').textContent=(j.kind==='discover'?'已发现 ':'已提取 ')+fmt(p.files);
    $('scan-current').textContent=p.current || '';
    $('scan-current').title=p.current || '';
    const bar=$('scan-progress');
    if(j.kind==='discover' && busy){bar.removeAttribute('value');}
    else{bar.max=j.kind==='extract'?Math.max(1,p.visited || 1):1;bar.value=j.kind==='extract'?(p.files || 0):1;}
  }
  $('connection-form').querySelector('[type=submit]').disabled=busy;
  if(wasBusy!==busy)renderSources();
  renderSelection();renderProducts();
}
async function refresh(){
  const previous=state && state.job;
  const next=await api('state');state=next;
  if(!loaded){
    buildConfig(state.config);$('platform').textContent=state.os==='windows'?'Windows':'Linux / Web';
    $('credential-note').textContent=state.os==='windows'?'凭据由 Windows DPAPI 加密保存在本机':'凭据保存在本机，文件权限 0600';
    loaded=true;renderClients();
    api('document-volumes').then(result=>{
      $('discovery-volumes').textContent=(result.volumes || []).map(v=>v.name+' '+v.path).join(' · ');
    }).catch(()=>{});
  }
  const inv=JSON.stringify(state.inventory);
  if(inv!==lastInventory){
    const newCatalog=(previous && previous.kind!==next.job.kind && next.job.kind==='discover') || !lastInventory;
    const available=(state.inventory.sources || []).filter(selectable);
    const oldIDs=new Set(JSON.parse(lastInventory || '{"sources":[]}').sources.map(s=>s.id));
    lastInventory=inv;
    selected=new Set(available.filter(s=>newCatalog || selected.has(s.id) || !oldIDs.has(s.id)).map(s=>s.id));
    $('confirm-source-upload').checked=false;$('confirm-upload').checked=false;
    renderSources();
  }
  const ps=JSON.stringify(state.products);
  if(ps!==lastProducts){lastProducts=ps;renderProducts();}
  renderJob();
  if(previous && previous.status==='running' && next.job.status!=='running'){
    if(next.job.status==='completed'){
      if(next.job.kind==='compact'){switchTab('products');step('archive');}
      if(['scan','discover','extract'].includes(next.job.kind)){switchTab('sources');step('archive');}
      toast('任务完成');
    } else if(next.job.status==='failed')toast(next.job.error || '任务失败');
  }
}
async function start(path,data={}){
  await api(path,data);await refresh();
}
async function scan(){await save();step('archive');switchTab('sources');await start('scan');}
async function preview(id,kind,title){
  await guarded(async()=>{
    const result=await api('preview?id='+encodeURIComponent(id)+'&kind='+kind);
    $('preview-title').textContent=title;$('preview-text').textContent=result.text;
    $('preview-note').textContent=result.truncated?'仅预览前 12,000 字，完整正文保存在本机归档目录。':'';
    $('preview-dialog').showModal();
  });
}
async function browse(input){
  browseTarget=input;await guarded(async()=>{await loadFolder(input.value || state.home);$('browse-dialog').showModal();});
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
$('save-sources').onclick=()=>guarded(async()=>{await save();toast('提取范围已保存');});
$('test-remote').onclick=()=>guarded(async()=>{await save();await start('test',{kind:'remote'});});
$('test-model').onclick=()=>guarded(async()=>{await save();await start('test',{kind:'model'});});
$('add-root').onclick=()=>{const input=addRoot();browse(input);};
$('scan').onclick=()=>guarded(scan);$('rescan').onclick=()=>guarded(scan);
$('discover').onclick=()=>guarded(async()=>{
  await save();sourcePage=0;step('archive');switchTab('sources');
  await start('discover',{mode:document.querySelector('[name=discovery-mode]:checked').value,path:$('discovery-path').value.trim()});
});
$('extract').onclick=()=>guarded(()=>start('extract',{ids:(state.inventory.sources || []).filter(s=>s.status==='discovered' && selected.has(s.id)).map(s=>s.id)}));
$('browse-discovery').onclick=()=>browse($('discovery-path'));
document.querySelectorAll('[name=discovery-mode]').forEach(input=>input.onchange=()=>{
  $('discovery-directory').hidden=document.querySelector('[name=discovery-mode]:checked').value!=='directory';
});
$('compact').onclick=()=>guarded(async()=>{await save();await start('compact',{ids:(state.inventory.sources || []).filter(s=>s.status==='ready' && selected.has(s.id)).map(s=>s.id),confirm_source_upload:$('confirm-source-upload').checked});});
$('confirm-source-upload').onchange=renderSelection;
$('upload').onclick=()=>guarded(()=>start('upload',{confirm:$('confirm-upload').checked}));
$('confirm-upload').onchange=renderProducts;
$('install').onclick=()=>guarded(async()=>{await save();await start('install');});
$('restore').onclick=()=>guarded(()=>start('restore'));
$('cancel').onclick=()=>guarded(()=>api('cancel',{}));
$('browser').onclick=()=>guarded(()=>api('open-browser',{}));
$('exit').onclick=()=>guarded(async()=>{await api('shutdown',{});toast('本地服务已退出，可以关闭窗口');});
$('select-all').onchange=()=>{
  const checked=$('select-all').checked;
  selected=new Set(checked?(state.inventory.sources || []).filter(selectable).map(s=>s.id):[]);renderSources();
};
$('tab-sources').onclick=()=>switchTab('sources');$('tab-products').onclick=()=>switchTab('products');
$('filter').oninput=()=>{sourcePage=0;renderSources();renderProducts();};
$('source-prev').onclick=()=>{sourcePage--;renderSources();};
$('source-next').onclick=()=>{sourcePage++;renderSources();};
document.querySelectorAll('.reveal').forEach(b=>b.onclick=()=>{const input=b.parentNode.querySelector('input');input.type=input.type==='password'?'text':'password';});
document.querySelectorAll('.close-dialog').forEach(b=>b.onclick=()=>b.closest('dialog').close());
$('folder-up').onclick=()=>guarded(()=>loadFolder(folderParent));$('folder-go').onclick=()=>guarded(()=>loadFolder($('folder-address').value));
$('folder-address').onkeydown=(e)=>{if(e.key==='Enter'){e.preventDefault();guarded(()=>loadFolder(e.target.value));}};
$('folder-select').onclick=()=>{if(browseTarget)browseTarget.value=$('folder-address').value;$('browse-dialog').close();};
icons();
guarded(refresh);
setInterval(()=>refresh().catch(()=>{}),1500);
