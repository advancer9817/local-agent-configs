#!/usr/bin/env python3
"""Finish native client settings, install hooks and sync sanitized copies."""
from pathlib import Path
import base64, json, shutil, subprocess, os, re
import yaml
from portable_paths import REPO, portable_text, windows_home, windows_path, windows_tool
HOME=Path.home()
WIN=windows_home()
B=Path((HOME/'.local/state/hindsight-migration/latest').read_text())
manifest=json.loads((B/'manifest.json').read_text())
known={x['original'] for x in manifest}

def backup(p):
    if str(p) in known:return
    if p.exists():
        dest=B/'finish'/str(p).lstrip('/')
        dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        shutil.copy2(p,dest)
        dest.chmod(0o600)
        manifest.append({'original':str(p),'backup':str(dest)})
    else:manifest.append({'original':str(p),'created':True})
    known.add(str(p))
    (B/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))

queue=[]
def put(p,obj,secret=False):
    backup(p)
    text=json.dumps(obj,ensure_ascii=True,indent=2)+'\n' if not isinstance(obj,str) else obj
    if p == WIN or WIN in p.parents:
        path=windows_path(p)
        queue.append({'path':path,'content':text,'secret':secret})
    else:
        p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        p.write_text(text)
        if secret:p.chmod(0o600)

hook=HOME/'.local/lib/hindsight/hindsight-hook.py'
for name in ('hindsight-hook.py', 'session_documents.py', 'ingest_safety.py'):
    put(hook.parent/name,(REPO/'apps/hindsight-session-ingest'/name).read_text())
conn=json.loads((HOME/'.config/hindsight/connection.json').read_text())
put(WIN/'.config/hindsight/connection.json',conn,True)
settings=json.loads((HOME/'.hermes/hindsight/config.json').read_text())
for root in [WIN/'.hermes',WIN/'AppData/Local/hermes']:
    put(root/'hindsight/config.json',settings,True)

for home in [HOME,WIN]:
    windows=home==WIN
    def cmd(action,agent):
        prefix='wsl.exe -d Ubuntu --exec /bin/python3 ' if windows else '/bin/python3 '
        return prefix+str(hook)+' '+action+' --agent '+agent
    def entry(command,timeout):return {'hooks':[{'type':'command','command':command,'timeout':timeout}]}
    for rel,agent in [('.claude/settings.json','claude'),('.codex/hooks.json','codex'),('.gemini/settings.json','gemini')]:
        p=home/rel
        d=json.loads(p.read_text()) if p.exists() else {}
        hooks=d.setdefault('hooks',{})
        # Remove only our previous integration on re-run; preserve other consumers.
        for event in list(hooks):
            hooks[event]=[e for e in hooks[event] if 'hindsight-hook.py' not in json.dumps(e)]
            if not hooks[event]:del hooks[event]
        if agent=='gemini':
            hooks.setdefault('BeforeAgent',[]).append(entry(cmd('recall',agent),45000))
            hooks.setdefault('AfterAgent',[]).append(entry(cmd('retain',agent),60000))
        else:
            hooks.setdefault('UserPromptSubmit',[]).append(entry(cmd('recall',agent),45))
            hooks.setdefault('Stop',[]).append(entry(cmd('retain',agent),60))
        put(p,d,True)
    # OpenCode's active JSON schema has no generic hooks setting; MCP + rules are used.
    p=home/'.config/opencode/opencode.json'
    if p.exists():
        d=json.loads(p.read_text())
        if d.get('hooks')=={}:d.pop('hooks',None)
        put(p,d,True)

# Windows-side writes use native APIs with UTF-8 and single-user credential ACLs.
ps='''$ErrorActionPreference="Stop"
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
$items=([Console]::In.ReadToEnd() | ConvertFrom-Json)
$utf8=New-Object System.Text.UTF8Encoding($false)
foreach($item in $items) {
 [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($item.path)) | Out-Null
 [IO.File]::WriteAllText($item.path,[string]$item.content,$utf8)
 if($item.secret){
  $who=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
  & icacls.exe $item.path /inheritance:r /grant:r ($who+":(F)") | Out-Null
  if($LASTEXITCODE -ne 0){throw "ACL failure"}
 }
}
Write-Output ("NATIVE_WINDOWS_WRITES="+$items.Count)
'''
r=subprocess.run([str(windows_tool('System32/WindowsPowerShell/v1.0/powershell.exe')),'-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(ps.encode('utf-16le')).decode()],input=json.dumps(queue),capture_output=True,text=True,errors='replace',timeout=60)
if r.returncode:print(r.stderr[-2500:]);raise SystemExit(1)
print(r.stdout.strip())

# Native Windows provider validation is performed independently from config sync.

# Sanitize runtime exports; no credentials or private runtime state enters Git.
def sanitize(v,key=''):
    if re.search(r'key|token|password|secret|credential|authorization|trusted_hash',key,re.I):return '[REDACTED]'
    if isinstance(v,dict):return {k:sanitize(x,k) for k,x in v.items()}
    if isinstance(v,list):return [sanitize(x) for x in v]
    return v
for src,dest in [(HOME/'.hermes/config.yaml',REPO/'hermes/config.yaml'),(HOME/'.hermes/SOUL.md',REPO/'hermes/SOUL.md'),(HOME/'.claude/settings.json',REPO/'claude/settings.json'),(HOME/'.claude/settings.local.json',REPO/'claude/settings.local.json'),(HOME/'.claude/CLAUDE.md',REPO/'claude/CLAUDE.md'),(HOME/'.codex/config.toml',REPO/'codex/config.toml'),(HOME/'.codex/instructions.md',REPO/'codex/instructions.md'),(HOME/'.codex/hooks.json',REPO/'codex/hooks.json')]:
    t=src.read_text()
    if src.suffix=='.yaml':t=yaml.safe_dump(sanitize(yaml.safe_load(t)),allow_unicode=True,sort_keys=False)
    elif src.suffix=='.json':t=json.dumps(sanitize(json.loads(t)),ensure_ascii=False,indent=2)+'\n'
    elif src.suffix=='.toml':t=re.sub(r'Bearer [^"\n]+','Bearer [REDACTED]',t)
    put(dest,portable_text(t,HOME,WIN))
put(REPO/'hermes/hindsight/config.json',settings)
for hh in (HOME/'.hermes/profiles').iterdir():
    if (hh/'config.yaml').exists():
        put(REPO/'hermes/profiles'/hh.name/'config.yaml',yaml.safe_dump(sanitize(yaml.safe_load((hh/'config.yaml').read_text())),sort_keys=False,allow_unicode=True))
        put(REPO/'hermes/profiles'/hh.name/'hindsight/config.json',json.loads((hh/'hindsight/config.json').read_text()))
for rel in ['scripts/mcore-context.sh','scripts/mcore-ingest.py','scripts/lmmcp-query']:
    p=REPO/rel
    if p.exists():
        backup(p)
        dest=B/'retired-repo'/p.name
        dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        shutil.move(p,dest)
print('FINISH_CONFIGURATION_COMPLETE')
