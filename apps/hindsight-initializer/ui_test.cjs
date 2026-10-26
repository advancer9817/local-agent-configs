// Generated fixtures and a fake remote keep the UI smoke test away from real memory.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');

let app, browser, mock;
async function cleanup() {
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
  await fs.writeFile(path.join(docs,'活跃记录.md'),'仍在编辑');
  const documents = new Map();
  let uploads = 0, modelCalls = 0;
  mock = http.createServer(async(req,res)=>{
    let raw='';for await(const part of req)raw+=part;
    const body=raw?JSON.parse(raw):{};
    res.setHeader('Content-Type','application/json');
    const json=(x)=>res.end(JSON.stringify(x));
    if(req.url==='/chat/completions'){
      modelCalls++;
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
  await page.screenshot({path:path.join(output,'01-connection-desktop.png'),fullPage:true});
  await page.locator('[name=api_url]').fill(mockURL);
  await page.locator('[name=mcp_token]').fill('fixture-token');
  await page.locator('[name=model_url]').fill(mockURL);
  await page.locator('[name=model]').fill('fixture-model');
  await page.locator('#test-remote').click();
  await page.waitForFunction(()=>document.querySelector('#logs').textContent.includes('连接与认证通过'));
  await page.waitForFunction(()=>!document.querySelector('#test-model').disabled);
  await page.locator('#test-model').click();
  await page.waitForFunction(()=>document.querySelector('#logs').textContent.includes('模型连接'));
  await page.waitForFunction(()=>!document.querySelector('#test-model').disabled);
  await page.locator('#connection-form [type=submit]').click();
  for(const agent of ['codex','claude','hermes']){
    await page.locator(`.agent[data-agent="${agent}"] [type=checkbox]`).uncheck();
  }
  await page.locator('#add-root').click();
  await page.locator('#browse-dialog').waitFor({state:'visible'});
  await page.locator('#folder-address').fill(docs);
  await page.locator('#folder-go').click();
  await page.waitForFunction(p=>document.querySelector('#folder-address').value===p,docs);
  await page.locator('#folder-select').click();
  await page.screenshot({path:path.join(output,'02-sources-desktop.png'),fullPage:true});
  await page.locator('#scan').click();
  await page.waitForFunction(()=>document.querySelector('#metric-ready').textContent==='1');
  await page.waitForFunction(()=>!document.querySelector('#compact').disabled);
  assert.equal(await page.locator('#source-rows tr').count(),3);
  await page.locator('#source-rows button').first().click();
  await page.locator('#preview-dialog').waitFor({state:'visible'});
  assert.ok((await page.locator('#preview-text').textContent()).includes('数据库迁移尚未完成'));
  await page.locator('#preview-dialog .close-dialog').click();
  await page.screenshot({path:path.join(output,'03-inventory-desktop.png'),fullPage:true});
  await page.locator('#compact').click();
  await page.waitForFunction(()=>document.querySelector('#metric-approved').textContent==='1');
  await page.waitForFunction(()=>!document.querySelector('#scan').disabled);
  await page.locator('#tab-products').click();
  await page.locator('#product-rows button').click();
  await page.locator('#preview-dialog').waitFor({state:'visible'});
  await page.screenshot({path:path.join(output,'04-product-preview.png'),fullPage:true});
  await page.locator('#preview-dialog .close-dialog').click();
  await page.locator('#confirm-upload').check();
  await page.locator('#upload').click();
  await page.waitForFunction(()=>document.querySelector('#logs').textContent.includes('成品已确认落库'));
  assert.equal(uploads,1);
  await page.waitForFunction(()=>!document.querySelector('#upload').disabled);
  await page.locator('#upload').click();
  await page.waitForFunction(()=>document.querySelector('#logs').textContent.includes('跳过已确认上传'));
  assert.equal(uploads,1);
  await page.screenshot({path:path.join(output,'05-completed-desktop.png'),fullPage:true});
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
