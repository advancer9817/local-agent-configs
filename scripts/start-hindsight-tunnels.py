#!/usr/bin/env python3
"""Start user-owned native SSH forwards. No service registration or desktop icon."""
from pathlib import Path
import argparse,json,os,shutil,socket,subprocess,sys,urllib.request

from portable_paths import windows_home, windows_path, windows_tool
p=argparse.ArgumentParser()
p.add_argument('--host',default='35.194.237.91')
p.add_argument('--user',default='root')
p.add_argument('--ssh-port',type=int,default=22)
p.add_argument('--local-port',type=int,default=18888)
p.add_argument('--remote-port',type=int,default=18888)
p.add_argument('--windows-user-home',default=None)
a=p.parse_args()
winhome=Path(a.windows_user_home).expanduser() if a.windows_user_home else windows_home()
winssh=windows_tool('System32/OpenSSH/ssh.exe')
key=windows_path(winhome/'.ssh/id_ed25519')
common=['-F','NUL','-i',key,'-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3']
forward=['-o','ExitOnForwardFailure=yes','-N','-L',f'127.0.0.1:{a.local_port}:127.0.0.1:{a.remote_port}']
remote=f'{a.user}@{a.host}'
state=Path.home()/'.local/state/hindsight-tunnels'
state.mkdir(parents=True,exist_ok=True,mode=0o700)

def health():
 try:
  o=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  with o.open(f'http://127.0.0.1:{a.local_port}/health',timeout=4) as r:return r.status==200
 except Exception:return False

# Windows health check remains native so it checks Windows loopback, not WSL's.
curl=windows_tool('System32/curl.exe')
r=subprocess.run([str(curl),'--noproxy','*','--max-time','5','-fsS',f'http://127.0.0.1:{a.local_port}/health'],capture_output=True,timeout=8)
started=[]
if r.returncode:
 log=(state/'windows-ssh.log').open('ab')
 proc=subprocess.Popen([str(winssh),*common,*forward,'-p',str(a.ssh_port),remote],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 started.append({'owner':'windows','pid':proc.pid})
if not health():
 linuxkey=Path.home()/'.ssh/id_ed25519_win'
 proxy=subprocess.list2cmdline([str(winssh),*common,'-p',str(a.ssh_port),'-W',f'127.0.0.1:{a.ssh_port}',remote])
 log=(state/'wsl-ssh.log').open('ab')
 proc=subprocess.Popen(['ssh','-F','/dev/null','-i',str(linuxkey),'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3','-o','ProxyCommand='+proxy,*forward,'-p',str(a.ssh_port),remote],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 started.append({'owner':'wsl','pid':proc.pid})
(state/'last-start.json').write_text(json.dumps(started,indent=2))
print(json.dumps({'new_processes':started,'note':'Native SSH processes only; inspect /health after startup. Rerun this script after reboot or tunnel exit.'},ensure_ascii=False))
