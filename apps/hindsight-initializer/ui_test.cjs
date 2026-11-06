// Generated fixtures and a fake remote keep the UI smoke test away from real memory.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
let testProcess, testBrowser, testMock;
async function cleanup() {
  if (testBrowser) await testBrowser.close();
  if (testMock) await new Promise(resolve => testMock.close(resolve));
  if (testProcess && testProcess.exitCode === null) {
    await new Promise(resolve => { testProcess.once('exit', resolve); testProcess.kill('SIGTERM'); });
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
  const sessions = path.join(fixture,'.codex','sessions');
  await fs.mkdir(sessions,{recursive:true});
  const transcript = path.join(sessions,'history.jsonl');
  await fs.writeFile(transcript,[
    {type:'session_meta',payload:{id:'fixture-sid',cwd:docs}},
    {type:'response_item',payload:{role:'user',content:'保留原始要求，数据库迁移尚未完成。'}},
    {type:'response_item',payload:{role:'assistant',content:'助手报告文档已交付；实际部署仍待验证。'}},
  ].map(row=>JSON.stringify(row)).join('\n'));
  await fs.utimes(transcript,old,old);
  const documents = new Map();
  let uploads = 0, preparations = 0;
  const completed = new Set();
  const mock = http.createServer(async(req,res)=>{
    const chunks=[];for await(const part of req)chunks.push(part);
    const raw=Buffer.concat(chunks);
    const body=raw.length && req.headers['content-type']?.includes('application/json')?JSON.parse(raw.toString()):{};
    res.setHeader('Content-Type','application/json');
    const json=(x)=>res.end(JSON.stringify(x));
    assert.notEqual(req.url,'/chat/completions','client must never call a model endpoint');
    if(req.url.endsWith('/capabilities')){json({model_configured:true,server_processing:true,requires_llm:true,session_preview:true});return;}
    if(req.method==='POST'&&req.url.endsWith('/sessions')){
      preparations++;
      const form=await new Request('http://fixture/sessions',{method:'POST',headers:req.headers,body:raw}).formData();
      const manifest=JSON.parse(form.get('manifest'));
      assert.equal(manifest.session_id,'fixture-sid');
      assert.equal(manifest.auto_commit,false,'history must wait for preview confirmation');
      assert.equal(uploads,0);
      assert.ok((await form.get('session').text()).includes('实际部署仍待验证'));
      json({accepted:[{job_id:'fixture-session',status:'pending',kind:'session'}],failed:[]});return;
    }
    if(req.method==='POST'&&req.url.endsWith('/archives')){
      preparations++;assert.equal(body.sources.length,1);
      assert.ok(Buffer.from(body.sources[0].data,'base64').toString().includes('数据库迁移尚未完成'));
      json({job_id:'fixture-one',status:'pending'});return;
    }
    if(req.method==='POST'&&req.url.endsWith('/commit')){
      const id=req.url.split('/jobs/')[1].split('/')[0];
      uploads++;completed.add(id);json({job_id:id,status:'retaining'});return;
    }
    if(req.url.includes('/jobs/fixture-')){
      const id=req.url.split('/jobs/')[1].split('?')[0];
      const text=id==='fixture-session'?'# 历史会话\n用户要求保留原始要求，数据库迁移尚未完成；助手报告文档已交付，实际部署仍待验证。':'# 项目历史决策与迁移待办\n历史记录中的数据库迁移尚未完成。 [S1]';
      json({job_id:id,status:completed.has(id)?'completed':'prepared',refined_text:text});return;
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
  testMock = mock;
  await new Promise(r=>mock.listen(0,'127.0.0.1',r));
  const mockURL='http://127.0.0.1:'+mock.address().port;
  let launcherPath = process.env.LAUNCHER;
  if (!launcherPath) {
    assert.ok(process.env.SETUP_BINARY, 'Set SETUP_BINARY to a test build or LAUNCHER to an isolated launcher.json');
    const state = path.join(fixture, 'app-state');
    launcherPath = path.join(state, 'launcher.json');
    testProcess = spawn(process.env.SETUP_BINARY, ['--no-browser', '--listen', '127.0.0.1:0', '--data-dir', state],
      {stdio: 'ignore', env: {...process.env, HOME: fixture, USERPROFILE: fixture}});
    let startupError;
    testProcess.on('error', error => { startupError = error; });
    const deadline = Date.now() + 15000;
    while (true) {
      if (startupError) throw startupError;
      try { await fs.access(launcherPath); break; } catch {}
      assert.ok(Date.now() < deadline && testProcess.exitCode === null, 'Test app did not start');
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }
  const launcher=JSON.parse(await fs.readFile(launcherPath,'utf8'));
  const browser=await chromium.launch({executablePath:process.env.CHROME_PATH || undefined,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
  testBrowser = browser;
  const page=await browser.newPage({viewport:{width:1380,height:960},deviceScaleFactor:1});
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  await page.goto(launcher.url);
  await page.locator('[name=bank_id]').waitFor();
  await page.waitForFunction(()=>document.querySelector('[name=bank_id]').value.length>0);
  assert.equal(await page.locator('[name=bank_id]').inputValue(),'agent-memory');
  await page.screenshot({path:path.join(output,'01-connection-desktop.png'),fullPage:true});
  await page.locator('[name=api_url]').fill(mockURL);
  await page.locator('[name=mcp_token]').fill('fixture-token');
  assert.equal(await page.locator('[name=model_url]').count(),0);
  await page.locator('#test-remote').click();
  await page.waitForFunction(()=>document.querySelector('#logs').textContent.includes('连接与认证通过'));
  await page.waitForFunction(()=>!document.querySelector('#test-model').disabled);
  await page.locator('#test-model').click();
  await page.waitForFunction(()=>document.querySelector('#logs').textContent.includes('模型已配置'));
  await page.waitForFunction(()=>!document.querySelector('#test-model').disabled);
  await page.locator('#connection-form [type=submit]').click();
  for(const agent of ['codex','claude','hermes']){
    const input=page.locator(`.agent[data-agent="${agent}"] [type=checkbox]`);
    if(agent==='codex'){await input.check();}else{await input.uncheck();}
  }
  await page.locator('#add-root').click();
  await page.locator('#browse-dialog').waitFor({state:'visible'});
  await page.locator('#folder-address').fill(docs);
  await page.locator('#folder-go').click();
  await page.waitForFunction(p=>document.querySelector('#folder-address').value===p,docs);
  await page.locator('#folder-select').click();
  await page.screenshot({path:path.join(output,'02-sources-desktop.png'),fullPage:true});
  await page.locator('#scan').click();
  await page.waitForFunction(()=>document.querySelector('#metric-ready').textContent==='2');
  await page.locator('#confirm-source-upload').check();
  await page.waitForFunction(()=>!document.querySelector('#compact').disabled);
  assert.equal(await page.locator('#source-rows tr').count(),4);
  await page.locator('#source-rows button').first().click();
  await page.locator('#preview-dialog').waitFor({state:'visible'});
  assert.ok((await page.locator('#preview-text').textContent()).includes('数据库迁移尚未完成'));
  await page.locator('#preview-dialog .close-dialog').click();
  await page.screenshot({path:path.join(output,'03-inventory-desktop.png'),fullPage:true});
  await page.locator('#compact').click();
  await page.waitForFunction(()=>document.querySelector('#metric-approved').textContent==='2');
  assert.equal(uploads,0,'neither sessions nor documents may be retained before confirmation');
  assert.equal(preparations,2);
  await page.waitForFunction(()=>!document.querySelector('#scan').disabled);
  await page.locator('#tab-products').click();
  await page.locator('#product-rows button').first().click();
  await page.locator('#preview-dialog').waitFor({state:'visible'});
  await page.screenshot({path:path.join(output,'04-product-preview.png'),fullPage:true});
  await page.locator('#preview-dialog .close-dialog').click();
  await page.locator('#confirm-upload').check();
  await page.locator('#upload').click();
  await page.waitForFunction(()=>document.querySelector('#logs').textContent.includes('成品已确认落库'));
  assert.equal(uploads,2);
  await page.waitForFunction(()=>!document.querySelector('#upload').disabled);
  await page.locator('#upload').click();
  await page.waitForFunction(()=>document.querySelector('#logs').textContent.includes('成品已确认落库'));
  assert.equal(uploads,2);
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
  console.log(JSON.stringify({passed:true,uploads,preparations,screenshots:output,fixture}));
  await cleanup();
})().catch(async err=>{console.error(err);await cleanup();process.exitCode=1;});
