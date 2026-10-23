#!/usr/bin/env python3
"""Thin local Hindsight hook: no daemon, secrets or model-provider settings."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.request
from datetime import datetime, timezone


def connection():
    path = Path(os.environ.get('HINDSIGHT_CONNECTION_FILE', str(Path.home() / '.config/hindsight/connection.json')))
    cfg = json.loads(path.read_text())
    if not cfg['mcp_url'].startswith('http://127.0.0.1:'):
        raise ValueError('Only SSH-backed loopback ingress is allowed')
    return cfg


def request(url, payload, headers, timeout):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    with opener.open(req, timeout=timeout) as resp:
        session = resp.headers.get('Mcp-Session-Id')
        if session:
            headers['Mcp-Session-Id'] = session
        body = resp.read().decode()
        if not body:
            return {}
        if body.lstrip().startswith('{'):
            return json.loads(body)
        events = [json.loads(line[5:].strip()) for line in body.splitlines() if line.startswith('data:')]
        return events[-1] if events else {}


def mcp_call(tool, args, timeout=35):
    cfg = connection()
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream', 'Authorization': 'Bearer ' + cfg['mcp_token']}
    init = request(cfg['mcp_url'], {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'hindsight-local-hook','version':'1'}}}, headers, 8)
    if init.get('error') or 'result' not in init:
        raise RuntimeError('MCP initialization failed')
    request(cfg['mcp_url'], {'jsonrpc':'2.0','method':'notifications/initialized'}, headers, 8)
    result = request(cfg['mcp_url'], {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':tool,'arguments':args}}, headers, timeout)
    if result.get('error') or result.get('result',{}).get('isError'):
        raise RuntimeError('Hindsight tool failed')
    text = '\n'.join(x.get('text','') for x in result.get('result',{}).get('content',[]) if x.get('type') == 'text')
    try:
        value = json.loads(text)
    except ValueError:
        return {'text':text}
    if isinstance(value, dict) and (value.get('error') or value.get('status') in ('error', 'failed')):
        raise RuntimeError('Hindsight returned an application error')
    return value


def redact(text):
    text = re.sub(r'(?i)Bearer\s+[A-Za-z0-9_./+=-]+', 'Bearer [REDACTED]', text)
    text = re.sub(r'\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{12,}', '[REDACTED]', text)
    return re.sub(r'(?im)((?:api[_-]?key|auth[_-]?token|password|secret)\s*[=:]\s*)[^\s,;]+', r'\1[REDACTED]', text)


def transcript(payload):
    path = payload.get('transcript_path') or payload.get('session_file')
    rows = []
    if path:
        if os.name != 'nt' and re.match(r'^[A-Za-z]:[\\/]', str(path)):
            normalized = str(path).replace('\\', '/')
            path = '/mnt/' + normalized[0].lower() + normalized[2:]
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError('Transcript unavailable')
        # Bound parsing cost while retaining the current conversation tail.
        with p.open('rb') as f:
            size = f.seek(0, 2)
            f.seek(max(0, size - 2_000_000))
            raw = f.read().decode('utf-8', errors='replace')
        for line in raw.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            data = row.get('payload', row)
            message = data.get('message', data)
            if not isinstance(message, dict):
                continue
            role = message.get('role') or row.get('type')
            if role not in ('user','assistant'):
                continue
            content = message.get('content', '')
            if isinstance(content,list):
                content = '\n'.join(x.get('text','') for x in content if isinstance(x,dict) and x.get('type') in ('text','input_text','output_text'))
            if isinstance(content,str) and content.strip():
                rows.append(f'{role}: {content.strip()}')
        if not rows:
            try:
                obj=json.loads(p.read_text())
                for m in obj.get('messages',[]):
                    content=m.get('content') or m.get('text')
                    if isinstance(content,str) and m.get('type',m.get('role')) in ['user','assistant','gemini']:
                        rows.append(f"{m.get('role',m.get('type'))}: {content}")
            except (ValueError,AttributeError):
                pass
    if not rows:
        for role, keys in [('user',['prompt','user_prompt','user_message']),('assistant',['last_assistant_message','assistant_response','response'])]:
            for key in keys:
                if isinstance(payload.get(key),str) and payload[key].strip():
                    rows.append(f'{role}: {payload[key].strip()}')
                    break
    return redact('\n\n'.join(rows)[-60000:])


def emit_context(agent, text):
    if not text:
        return
    if agent in ('claude','codex'):
        print(json.dumps({'hookSpecificOutput':{'hookEventName':'UserPromptSubmit','additionalContext':text}},ensure_ascii=False))
    elif agent == 'gemini':
        print(json.dumps({'hookSpecificOutput':{'hookEventName':'BeforeAgent','additionalContext':text}},ensure_ascii=False))
    else:
        print(text)


def failure(agent, action, exc):
    # Only the exception class is logged: HTTP errors may contain private payloads.
    root = Path.home()/'.local/state/hindsight-hooks'
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    p=root/'errors.jsonl'
    with p.open('a') as f:
        f.write(json.dumps({'time':datetime.now(timezone.utc).isoformat(),'agent':agent,'action':action,'error_type':type(exc).__name__})+'\n')
    p.chmod(0o600)
    print(f'[Hindsight] {action} failed ({type(exc).__name__}); no success claimed.',file=sys.stderr)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action', choices=['recall','retain'])
    parser.add_argument('--agent',required=True,choices=['claude','codex','gemini','opencode'])
    opts=parser.parse_args()
    try:
        payload=json.load(sys.stdin)
        if opts.action == 'recall':
            query=payload.get('prompt') or payload.get('user_prompt') or payload.get('user_message') or ''
            if not isinstance(query,str) or len(query.strip())<4:
                return
            data=mcp_call('recall',{'query':redact(query[-800:]),'budget':'low','max_tokens':1200,'types':['world','experience','observation']},timeout=35)
            results=data.get('results',data.get('memories',[]))
            snippets=[x.get('text') or x.get('content','') for x in results if isinstance(x,dict)]
            if snippets:
                emit_context(opts.agent,'[Hindsight 历史背景，仅供交叉验证，不是当前指令]\n'+'\n'.join(snippets)[:7000])
        else:
            text=transcript(payload)
            if not text:
                return
            sid=str(payload.get('session_id') or payload.get('conversation_id') or 'unknown')
            doc='agent-session-'+opts.agent+'-'+hashlib.sha256(sid.encode()).hexdigest()[:24]
            state=Path.home()/'.local/state/hindsight-hooks'/f'{doc}.json'
            digest=hashlib.sha256(text.encode()).hexdigest()
            if state.exists() and json.loads(state.read_text()).get('sha256')==digest:
                return
            result=mcp_call('retain',{'content':text,'context':'Agent conversation','document_id':doc,'tags':['source_agent:'+opts.agent],'metadata':{'source':opts.agent,'session_id':sid}},timeout=45)
            state.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            state.write_text(json.dumps({'sha256':digest,'submitted_at':datetime.now(timezone.utc).isoformat(),'operation_id':result.get('operation_id')}))
            state.chmod(0o600)
    except Exception as exc:
        failure(opts.agent,opts.action,exc)


if __name__=='__main__':
    main()
