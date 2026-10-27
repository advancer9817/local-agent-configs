// Generated fixtures and a fake remote keep the UI smoke test away from real memory.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');

let app, browser, mock, releaseModel;
async function cleanup() {
  if(releaseModel)releaseModel();
  if (browser) await browser.close();
  if (app && app.pid && app.exitCode === null && app.signalCode === null) {
    const stopped = new Promise(resolve => app.once('exit', resolve));
    app.kill();
    await stopped;
  }
  if (mock && mock.listening) {
    mock.closeAllConnections();
    await new Promise(resolve => mock.close(resolve));
  }
}

(async () => {
  const fixture = await fs.mkdtemp(path.join(os.tmpdir(),'hindsight-ui-fixture-'));
  const output = process.env.UI_SCREENSHOT_DIR || path.join(os.tmpdir(),'hindsight-ui-screenshots');
  await fs.mkdir(output,{recursive:true});
  const docs = path.join(fixture,'docs');
  await fs.mkdir(docs);
  const old = new Date(Date.now()-48*3600000);
  const source = '# 项目历史\n\n用户决定保留原始会话，先压缩后上传；数据库迁移尚未完成。\n'+'历史执行过程与重复叙述。\n'.repeat(80);
  for (const name of ['项目决策.md','重复副本.md']) {
    const file=path.join(docs,name);await fs.writeFile(file,source);await fs.utimes(file,old,old);
  }
  const secondProject=path.join(docs,'另一项目');
  await fs.mkdir(secondProject);
  const secondFile=path.join(secondProject,'项目历史.md');
  await fs.writeFile(secondFile,source+'另一项目的历史记录。');
  await fs.utimes(secondFile,old,old);
  await fs.writeFile(path.join(docs,'活跃记录.md'),'仍在编辑');
  await fs.writeFile(path.join(docs,'不支持的旧文档.doc'),'not a supported format');
  const brokenDocument=path.join(docs,'损坏的文档.docx');
  await fs.writeFile(brokenDocument,'not a valid Office archive');
  await fs.utimes(brokenDocument,old,old);
  const documents = new Map();
  let uploads = 0, modelCalls = 0, holdModel=false;
  mock = http.createServer(async(req,res)=>{
    let raw='';for await(const part of req)raw+=part;
    const body=raw?JSON.parse(raw):{};
    assert.equal(req.headers.authorization,req.url==='/v1/chat/completions'?'Bearer fixture-model-key':undefined);
    res.setHeader('Content-Type','application/json');
    const json=(x)=>res.end(JSON.stringify(x));
    if(req.url==='/v1/chat/completions'){
      modelCalls++;
      if(holdModel)await new Promise(resolve=>{releaseModel=resolve;});
      await new Promise(resolve=>setTimeout(resolve,600));
      const prompt=body.messages[1].content;
      let result;
      if(prompt.includes('连接测试'))result={ok:true};
      else if(prompt.includes('独立核查'))result={safe:true,missing:[],unsupported:[],scope_issues:[]};
      else {
        const labels=[...new Set([...prompt.matchAll(/"id":"([SP]\d+)"/g)].map(m=>m[1]))];
        result={title:'项目历史决策与迁移待办',claims:[{text:'用户决定保留原始会话，先压缩后上传；历史记录中的数据库迁移尚未完成。',sources:labels}]};
      }
      json({choices:[{finish_reason:'stop',message:{content:JSON.stringify(result)}}]});return;
    }
    if(req.url.includes('/mcp/')){json({jsonrpc:'2.0',id:1,result:{protocolVersion:'2024-11-05',capabilities:{},serverInfo:{name:'fixture',version:'1'}}});return;}
    if(req.url.endsWith('/stats')){json({total_documents:documents.size});return;}
    if(req.method==='POST'&&req.url.endsWith('/memories')){
      uploads++;
      const item=body.items[0];assert.ok(item.content.length<source.length);
      documents.set(item.document_id,{original_text:item.content,memory_unit_count:1,retain_params:{metadata:item.metadata}});
      json({operation_id:body.operation_id});return;
    }
    if(req.url.includes('/operations/')){json({status:'completed',result_metadata:{extraction_errors_count:0}});return;}
    if(req.url.includes('/documents/')){
      const id=decodeURIComponent(req.url.split('/documents/')[1]);
      if(!documents.has(id)){res.statusCode=404;json({});return;}
      json(documents.get(id));return;
    }
    res.statusCode=404;json({});
  });
  await new Promise(r=>mock.listen(0,'127.0.0.1',r));
  const mockURL='http://127.0.0.1:'+mock.address().port;
  const binary=process.env.SETUP_BINARY || path.join(__dirname,'..','..','output','hindsight-initializer',
    process.platform==='win32'?'Hindsight-Setup-windows-x64.exe':'hindsight-setup-linux-x64');
  const dataDir=path.join(fixture,'initializer-state');
  app=spawn(binary,['--no-browser','--data-dir',dataDir],{
    env:{...process.env,HOME:fixture,USERPROFILE:fixture},stdio:'ignore'
  });
  let launchError;
  app.once('error',err=>{launchError=err;});
  let launcher;
  const deadline=Date.now()+30000;
  while(Date.now()<deadline) {
    if(launchError)throw launchError;
    if(app.exitCode!==null)throw new Error('Temporary initializer exited with code '+app.exitCode);
    try {launcher=JSON.parse(await fs.readFile(path.join(dataDir,'launcher.json'),'utf8'));break;}
    catch(err) {if(err.code!=='ENOENT')throw err;}
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  assert.ok(launcher,'Temporary initializer did not start');
  browser=await chromium.launch({executablePath:process.env.CHROME_PATH || undefined,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
  const page=await browser.newPage({viewport:{width:1380,height:960},deviceScaleFactor:1});
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  await page.goto(launcher.url);
  await page.locator('[name=bank_id]').waitFor();
  await page.waitForFunction(()=>document.querySelector('[name=bank_id]').value.length>0);
  assert.equal(await page.locator('.topbar button').count(),0);
  await page.screenshot({path:path.join(output,'01-connection-desktop.png'),fullPage:true});
  await page.locator('[name=api_url]').fill(mockURL);
  assert.equal(await page.locator('[name=mcp_token]').count(),0);
  await page.locator('[name=model_url]').fill(mockURL);
  await page.locator('[name=model]').fill('fixture-model');
  await page.locator('[name=model_key]').fill('fixture-model-key');
  await page.locator('#test-remote').click();
  await page.waitForFunction(()=>document.querySelector('#logs').textContent.includes('API 与 MCP 连接通过'));
  assert.equal(await page.locator('[name=model_url]').inputValue(),mockURL+'/v1');
  await page.waitForFunction(()=>!document.querySelector('#test-model').disabled);
  await page.locator('#test-model').click();
  await page.locator('#task-progress').waitFor({state:'visible'});
  assert.ok((await page.locator('#progress-time').textContent()).includes('已用'));
  await page.waitForFunction(()=>document.querySelector('#logs').textContent.includes('模型连接'));
  await page.waitForFunction(()=>!document.querySelector('#test-model').disabled);
  await page.locator('[name=model_url]').fill('');
  await page.locator('[name=model]').fill('');
  await page.locator('#connection-form [type=submit]').click();
  for(const agent of ['codex','claude','hermes']){
    await page.locator(`.agent[data-agent="${agent}"] [type=checkbox]`).uncheck();
  }
  await page.locator('#discover').click();
  await page.locator('#discovery-dialog').waitFor({state:'visible'});
  assert.ok(await page.locator('#volume-list li').count()>0);
  await page.screenshot({path:path.join(output,'02-discovery-all.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(output,'02-discovery-mobile.png'),fullPage:true});
  await page.setViewportSize({width:1380,height:960});
  await page.locator('#discovery-directory').click();
  await page.locator('#discovery-browse').click();
  await page.locator('#browse-dialog').waitFor({state:'visible'});
  await page.locator('#folder-address').fill(docs);
  await page.locator('#folder-go').click();
  await page.waitForFunction(p=>document.querySelector('#folder-address').value===p,docs);
  await page.locator('#folder-select').click();
  await page.locator('#start-discovery').click();
  await page.waitForFunction(()=>document.querySelector('#source-count').textContent==='5' && !document.querySelector('#scan').disabled);
  assert.equal(await page.locator('#metric-chars').textContent(),'0');
  assert.equal(await page.locator('#source-rows input:checked').count(),0);
  assert.ok((await page.locator('#source-rows').textContent()).includes('待提取'));
  assert.ok(!(await page.locator('#source-rows').textContent()).includes('不支持的旧文档'));
  assert.equal(modelCalls,1,'Discovery must not call the model');
  assert.equal(uploads,0);
  await page.screenshot({path:path.join(output,'02-discovered-documents.png'),fullPage:true});
  await page.locator('#source-rows input[aria-label="选择 项目决策"]').check();
  assert.ok(await page.locator('#compact').isDisabled());
  assert.ok((await page.locator('#extract').textContent()).includes('提取所选 1 篇'));
  await page.locator('#extract').click();
  await page.waitForFunction(()=>!document.querySelector('#scan').disabled && document.querySelector('#progress-count').textContent.includes('1 / 1'));
  assert.equal(await page.locator('#source-rows input:checked').count(),1);
  assert.equal(modelCalls,1,'Selected extraction must not call the model');
  assert.equal(uploads,0,'Selected extraction must not upload');
  await page.screenshot({path:path.join(output,'02-selected-extraction-progress.png'),fullPage:true});
  await page.locator('.step[data-step="sources"]').click();
  await page.screenshot({path:path.join(output,'02-sources-desktop.png'),fullPage:true});
  await page.locator('#scan').click();
  await page.waitForFunction(()=>document.querySelector('#metric-ready').textContent==='2');
  await page.waitForFunction(()=>!document.querySelector('#scan').disabled);
  await page.locator('#select-all').check();
  assert.ok(await page.locator('#compact').isDisabled());
  await page.locator('#configure-model').click();
  assert.ok(await page.locator('#connection').isVisible());
  await page.locator('[name=model_url]').fill(mockURL);
  await page.locator('[name=model_key]').fill('fixture-model-key');
  await page.locator('#connection-form [type=submit]').click();
  await page.locator('.step[data-step="archive"]').click();
  assert.ok(await page.locator('#compact').isDisabled());
  await page.locator('#configure-model').click();
  await page.locator('[name=model]').fill('fixture-model');
  await page.locator('#connection-form [type=submit]').click();
  await page.locator('.step[data-step="archive"]').click();
  await page.waitForFunction(()=>!document.querySelector('#compact').disabled);
  assert.ok(await page.locator('#configure-model').isHidden());
  assert.equal(await page.locator('#source-rows tr').count(),4);
  assert.ok(!(await page.locator('#source-rows').textContent()).includes('损坏的文档'));
  await page.locator('#source-rows button').first().click();
  await page.locator('#preview-dialog').waitFor({state:'visible'});
  assert.ok((await page.locator('#preview-text').textContent()).includes('数据库迁移尚未完成'));
  await page.locator('#preview-dialog .close-dialog').click();
  await page.screenshot({path:path.join(output,'03-inventory-desktop.png'),fullPage:true});
  holdModel=true;
  await page.locator('#compact').click();
  await page.waitForFunction(()=>document.querySelector('#progress-detail').textContent.includes('等待模型响应'));
  assert.ok((await page.locator('#progress-count').textContent()).includes('/ 2'));
  assert.ok((await page.locator('#progress-stage').textContent()).includes('压缩与核验'));
  for(const width of [1380,390]){
    await page.setViewportSize({width,height:960});
    await page.screenshot({path:path.join(output,`03-running-progress-${width}.png`),fullPage:true});
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    assert.ok(!overflow,'Progress must fit the viewport');
  }
  await page.setViewportSize({width:1380,height:960});
  holdModel=false;releaseModel();releaseModel=undefined;
  await page.waitForFunction(()=>document.querySelector('#metric-approved').textContent==='2');
  await page.waitForFunction(()=>!document.querySelector('#scan').disabled);
  assert.equal(uploads,0,'Compaction must not upload automatically');
  await page.reload();
  await page.waitForFunction(()=>document.querySelector('#metric-approved').textContent==='2');
  await page.locator('.step[data-step="archive"]').click();
  await page.locator('#tab-products').click();
  assert.ok(await page.locator('#upload').isDisabled());
  assert.equal(await page.locator('#product-rows input:checked').count(),0);
  assert.ok(!(await page.locator('#confirm-upload').isChecked()));
  await page.locator('#product-rows button').first().click();
  await page.locator('#product-dialog').waitFor({state:'visible'});
  assert.ok((await page.locator('#product-text').textContent()).includes('数据库迁移尚未完成'));
  await page.screenshot({path:path.join(output,'04-product-text.png'),fullPage:true});
  await page.locator('#detail-tab-sources').click();
  assert.ok((await page.locator('#product-sources').textContent()).includes('项目决策.md'));
  await page.locator('#product-sources button').first().click();
  await page.locator('#preview-dialog').waitFor({state:'visible'});
  assert.ok((await page.locator('#preview-text').textContent()).includes('数据库迁移尚未完成'));
  await page.locator('#preview-dialog .close-dialog').click();
  await page.locator('#detail-select').check();
  for(const size of [{width:1380,height:960},{width:390,height:844}]){
    await page.setViewportSize(size);
    const overflow=await page.locator('#product-dialog').evaluate(d=>({scroll:d.scrollWidth,width:d.clientWidth}));
    assert.ok(overflow.scroll<=overflow.width,JSON.stringify({size,overflow}));
    await page.screenshot({path:path.join(output,`04-product-details-${size.width}.png`),fullPage:true});
  }
  await page.setViewportSize({width:1380,height:960});
  await page.locator('#product-dialog .close-dialog').click();
  assert.equal(await page.locator('#product-rows input:checked').count(),1);
  const selectedProduct=await page.locator('#product-rows tr').first().getAttribute('data-product-id');
  await page.locator('#confirm-upload').check();
  await page.locator('#product-rows input').first().uncheck();
  assert.ok(!(await page.locator('#confirm-upload').isChecked()));
  assert.ok(await page.locator('#upload').isDisabled());
  await page.locator('#product-rows input').first().check();
  assert.ok(await page.locator('#upload').isDisabled());
  assert.equal(uploads,0,'Viewing and selecting results must stay local');
  await page.locator('#confirm-upload').check();
  await page.locator('#upload').click();
  await page.waitForFunction(()=>document.querySelector('#logs').textContent.includes('成品已确认落库'));
  assert.equal(uploads,1);
  assert.equal([...documents.values()][0].retain_params.metadata.bootstrap_id,selectedProduct);
  await page.waitForFunction(()=>!document.querySelector('#confirm-upload').disabled);
  assert.ok(!(await page.locator('#confirm-upload').isChecked()));
  await page.locator('#confirm-upload').check();
  await page.locator('#upload').click();
  await page.waitForFunction(()=>document.querySelector('#logs').textContent.includes('跳过已确认上传'));
  assert.equal(uploads,1);
  await page.screenshot({path:path.join(output,'05-completed-desktop.png'),fullPage:true});
  const manyDocuments=path.join(fixture,'many-documents');
  await fs.mkdir(manyDocuments);
  for(let i=0;i<205;i++)await fs.writeFile(path.join(manyDocuments,`索引文件${String(i).padStart(3,'0')}.md`),'metadata only');
  const beforeDiscoveryCalls=modelCalls;
  await page.locator('.step[data-step="sources"]').click();
  await page.locator('#discover').click();
  await page.locator('#discovery-directory').click();
  await page.locator('#discovery-root').fill(manyDocuments);
  await page.locator('#start-discovery').click();
  await page.waitForFunction(()=>document.querySelector('#source-count').textContent==='209' && !document.querySelector('#scan').disabled);
  assert.equal(await page.locator('#source-rows tr').count(),100);
  await page.locator('#source-next').click();
  assert.equal(await page.locator('#source-rows tr').count(),100);
  await page.locator('#source-next').click();
  assert.equal(await page.locator('#source-rows tr').count(),9);
  await page.locator('#filter').fill('索引文件204');
  assert.equal(await page.locator('#source-rows tr').count(),1);
  await page.locator('#filter').fill('');
  assert.equal(uploads,1,'Smart scanning must not upload');
  assert.equal(modelCalls,beforeDiscoveryCalls,'Smart scanning must not extract through a model');
  await page.reload();
  await page.waitForFunction(()=>document.querySelector('#source-count').textContent==='209');
  assert.equal(await page.locator('#metric-approved').textContent(),'2');
  for(const size of [{width:1180,height:850},{width:840,height:620},{width:390,height:844}]){
    await page.setViewportSize(size);
    for(const step of ['connection','sources','archive','clients']){
      await page.locator(`.step[data-step="${step}"]`).click();
      const overflow=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:innerWidth}));
      assert.ok(overflow.scroll<=overflow.width,JSON.stringify({size,step,overflow}));
      await page.screenshot({path:path.join(output,`${step}-${size.width}.png`),fullPage:true});
    }
  }
  assert.equal(errors.length,0,errors.join('\n'));
  console.log(JSON.stringify({passed:true,uploads,modelCalls,screenshots:output,fixture}));
})().catch(err=>{console.error(err);process.exitCode=1;}).finally(cleanup);
