#!/usr/bin/env python3
from __future__ import annotations

import argparse, base64, hashlib, hmac, ipaddress, json, os, platform, pwd, re, secrets, shutil, subprocess, tempfile, threading, time, getpass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse, urlsplit, urlunsplit
from onvif_client import Credentials, continuous_move, discover, goto_preset, get_stream_uri, identify_device, inspect_device, stop

VERSION='0.9.9.4-rc1'; ROOT=Path('/opt/pidecoder'); SESSIONS={}; LOCK=threading.Lock(); CPU_PREV=None

def owner():
    requested=os.environ.get('PIDECODER_USER','').strip()

    for username in (requested,'admin'):
        if not username:
            continue

        try:
            account=pwd.getpwnam(username)
            return account.pw_uid,account.pw_gid
        except KeyError:
            continue

    return os.getuid(),os.getgid()

def write_json(path,data,admin_owner=True):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(data,f,indent=2,ensure_ascii=False); f.write('\n')
        os.chmod(tmp,0o600)
        if admin_owner:
            uid,gid=owner(); os.chown(tmp,uid,gid)
        os.replace(tmp,path); os.chmod(path,0o600)
        if admin_owner:
            uid,gid=owner(); os.chown(path,uid,gid)
    except Exception:
        try: os.unlink(tmp)
        except FileNotFoundError: pass
        raise

def load(path,default):
    if not path.exists(): return default
    return json.loads(path.read_text(encoding='utf-8'))

def hash_pwd(pwd):
    if len(pwd)<8: raise ValueError('Le mot de passe doit contenir au moins 8 caractères')
    salt=secrets.token_bytes(16); it=310000
    dig=hashlib.pbkdf2_hmac('sha256',pwd.encode(),salt,it)
    return {'algorithm':'pbkdf2-sha256','iterations':it,'salt':base64.b64encode(salt).decode(),'password_hash':base64.b64encode(dig).decode()}

def verify(pwd,auth):
    try:
        salt=base64.b64decode(auth['salt']); exp=base64.b64decode(auth['password_hash']); it=int(auth['iterations'])
    except Exception: return False
    got=hashlib.pbkdf2_hmac('sha256',pwd.encode(),salt,it)
    return hmac.compare_digest(got,exp)

def set_auth(path,user,pwd):
    write_json(path,{'username':user,**hash_pwd(pwd),'session_secret':secrets.token_hex(32)},admin_owner=False)
    os.chown(path,0,0); os.chmod(path,0o600)

def cpu_percent():
    global CPU_PREV
    vals=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:])); cur=(sum(vals),vals[3]+vals[4])
    prev=CPU_PREV; CPU_PREV=cur
    if not prev or cur[0]==prev[0]: return None
    return round(100*(1-(cur[1]-prev[1])/(cur[0]-prev[0])),1)

def system_info():
    try: temp=round(int(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000,1)
    except Exception: temp=None
    mem={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        k,v=line.split(':',1); mem[k]=int(v.strip().split()[0])
    total=mem.get('MemTotal',0); used=total-mem.get('MemAvailable',0)
    try:
        out=subprocess.run(['vcgencmd','get_throttled'],capture_output=True,text=True,timeout=2).stdout.strip(); throttle=out.split('=',1)[1] if '=' in out else None
    except Exception: throttle=None
    return {'version':VERSION,'temperature_c':temp,'cpu_percent':cpu_percent(),'memory_percent':round(100*used/total,1) if total else 0,'memory_used_mb':round(used/1024,1),'memory_total_mb':round(total/1024,1),'uptime_seconds':int(float(Path('/proc/uptime').read_text().split()[0])),'load_average':list(os.getloadavg()),'throttled':throttle}

def normalize_layout(x,n):
    columns=max(1,min(9,int(x.get('columns',3))))
    rows=max(1,min(9,int(x.get('rows',3))))

    order=[]

    for value in x.get('camera_order',[]):
        try:
            value=int(value)
        except (TypeError,ValueError):
            continue

        if 0<=value<n and value not in order:
            order.append(value)

    order += [
        index
        for index in range(n)
        if index not in order
    ]

    def overlap(left,right):
        return not (
            left['x']+left['width']<=right['x']
            or right['x']+right['width']<=left['x']
            or left['y']+left['height']<=right['y']
            or right['y']+right['height']<=left['y']
        )

    def first_free(camera,occupied):
        for y in range(rows):
            for x_pos in range(columns):
                candidate={
                    'camera':camera,
                    'x':x_pos,
                    'y':y,
                    'width':1,
                    'height':1,
                }

                if not any(
                    overlap(candidate,other)
                    for other in occupied
                ):
                    return candidate

        return {
            'camera':camera,
            'x':camera%columns,
            'y':camera//columns,
            'width':1,
            'height':1,
        }

    placements=[]
    seen=set()

    for raw in x.get('placements',[]):
        if not isinstance(raw,dict):
            continue

        try:
            camera=int(raw.get('camera',0))
            x_pos=int(raw.get('x',0))
            y=int(raw.get('y',0))
            width=max(1,min(columns,int(raw.get('width',1))))
            height=max(1,min(rows,int(raw.get('height',1))))
        except (TypeError,ValueError):
            continue

        if camera<0 or camera>=n or camera in seen:
            continue

        x_pos=max(0,min(columns-width,x_pos))
        y=max(0,min(rows-height,y))

        candidate={
            'camera':camera,
            'x':x_pos,
            'y':y,
            'width':width,
            'height':height,
        }

        if any(overlap(candidate,other) for other in placements):
            candidate=first_free(camera,placements)

        placements.append(candidate)
        seen.add(camera)

    for camera in range(n):
        if camera not in seen:
            placements.append(
                first_free(camera,placements)
            )

    placements.sort(
        key=lambda item:item['camera']
    )

    return {
        'columns':columns,
        'rows':rows,
        'fullscreen_on_start':bool(
            x.get('fullscreen_on_start',False)
        ),
        'camera_order':order,
        'placements':placements,
    }

def rtsp_with_credentials(uri, username, password):
    parsed = urlsplit(str(uri).strip())

    if parsed.scheme.lower() != 'rtsp' or not parsed.hostname:
        raise ValueError('URI RTSP ONVIF invalide')

    host = parsed.hostname

    if ':' in host and not host.startswith('['):
        host = f'[{host}]'

    auth = ''

    if username:
        auth = quote(str(username), safe='')

        if password:
            auth += ':' + quote(str(password), safe='')

        auth += '@'

    port = f':{parsed.port}' if parsed.port else ''
    netloc = f'{auth}{host}{port}'

    return urlunsplit((
        parsed.scheme,
        netloc,
        parsed.path,
        parsed.query,
        parsed.fragment,
    ))


def sanitize(c):
    name=str(c.get('name','Caméra')).strip() or 'Caméra'; g=str(c.get('grid_url','')).strip(); f=str(c.get('focus_url','')).strip() or g
    if not g: raise ValueError(f'URL mosaïque absente pour {name}')
    result={'name':name,'enabled':bool(c.get('enabled',True)),'grid_url':g,'focus_url':f}
    if isinstance(c.get('onvif'),dict):result['onvif']=c['onvif']
    return result

HTML=r'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PiDecoder Admin</title>
<style>
:root{color-scheme:dark;font-family:system-ui;background:#0f1217;color:#f2f5f8;--p:#171b22;--l:#2d3440;--m:#9aa5b4;--b:#4c8dff;--g:#219b63;--r:#a93644}*{box-sizing:border-box}body{margin:0;background:#0f1217}button,input,select{font:inherit}button{border:0;border-radius:9px;padding:9px 13px;font-weight:700;cursor:pointer;transition:opacity .15s ease,transform .15s ease,background .15s ease}button:hover:not(:disabled){transform:translateY(-1px)}button:disabled{opacity:.45;cursor:not-allowed;transform:none}input,select{width:100%;padding:9px 10px;background:#0c1015;border:1px solid #353d49;border-radius:8px;color:#fff}input:focus,select:focus{outline:0;border-color:#69a5ff;box-shadow:0 0 0 3px #4c8dff30}label{display:block;color:#aab4c2;font-size:12px;margin-bottom:5px}.primary{background:var(--b);color:#fff}.success{background:var(--g);color:#fff}.secondary{background:#29313c;color:#fff}.danger{background:#51242a;color:#ffc0c6}.hidden{display:none!important}#login{min-height:100vh;display:grid;place-items:center;padding:20px}.loginbox{width:min(400px,100%);background:var(--p);border:1px solid var(--l);padding:24px;border-radius:16px}.field{margin:13px 0}header{position:sticky;top:0;z-index:20;display:flex;justify-content:space-between;align-items:center;padding:14px 20px;background:#151922;border-bottom:1px solid var(--l)}.actions{display:flex;gap:8px;flex-wrap:wrap}main{max-width:1300px;margin:auto;padding:20px}.tabs{display:flex;gap:8px;margin-bottom:16px}.tab{background:#242b35;color:#c6cfda}.tab.active{background:var(--b);color:#fff}.panel{background:var(--p);border:1px solid var(--l);border-radius:15px;padding:17px;margin-bottom:15px}.row{display:flex;gap:12px;flex-wrap:wrap;align-items:end}.grow{flex:1 1 240px}.small{width:120px}.camera{background:#12161c;border:1px solid var(--l);border-radius:13px;padding:14px;margin:11px 0}.head{display:flex;align-items:center;gap:9px;margin-bottom:12px}.handle{cursor:grab;user-select:none;padding:7px 10px;background:#252c36;border-radius:8px;font-size:20px}.title{flex:1;font-weight:800}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:11px}.s12{grid-column:span 12}.s6{grid-column:span 6}.s4{grid-column:span 4}.s3{grid-column:span 3}@media(max-width:800px){.s6,.s4,.s3{grid-column:span 12}}.pair{display:grid;grid-template-columns:1fr auto 1fr;gap:7px;align-items:center}.pass{display:grid;grid-template-columns:1fr auto;gap:6px}.muted{color:var(--m)}details{border-top:1px solid var(--l);margin-top:12px;padding-top:10px}summary{cursor:pointer;color:#9fc3ff}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:11px}.metric{background:#12161c;border:1px solid var(--l);border-radius:12px;padding:14px}.value{font-size:23px;font-weight:850;margin-top:6px}.good .value{color:#70dda2}.warn .value{color:#ffc268}.bad .value{color:#ff7f89}.toast{position:fixed;right:76px;bottom:20px;z-index:99;background:var(--g);padding:12px 15px;border-radius:11px;opacity:0;transform:translateY(10px);transition:.2s}.toast.show{opacity:1;transform:none}.toast.error{background:var(--r)}
.notification-toggle{position:fixed;right:18px;bottom:18px;z-index:25;width:42px;height:42px;border-radius:999px;padding:0;display:flex;align-items:center;justify-content:center;background:#26313e;color:#fff;box-shadow:0 10px 28px rgba(0,0,0,.35)}
.notification-count{position:absolute;top:-5px;right:-5px;min-width:19px;height:19px;padding:0 5px;border-radius:999px;display:none;align-items:center;justify-content:center;background:#4f8cff;color:#fff;font-size:11px;font-weight:800}
.notification-history{position:fixed;right:18px;bottom:70px;z-index:24;width:min(390px,calc(100vw - 36px));max-height:360px;overflow:auto;background:#151b23;border:1px solid #35404e;border-radius:13px;box-shadow:0 18px 45px rgba(0,0,0,.42);padding:12px;opacity:0;transform:translateY(8px) scale(.98);pointer-events:none;transition:opacity .16s ease,transform .16s ease}
.notification-history.show{opacity:1;transform:none;pointer-events:auto}
.notification-history-header{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:9px}
.notification-item{padding:9px 10px;border-radius:9px;background:#0f141b;border:1px solid #29323e;margin-top:7px}
.notification-item.error{border-color:#6f3038;background:#251419}
.notification-time{color:var(--m);font-size:11px;margin-top:4px}
.notification-empty{color:var(--m);text-align:center;padding:20px 8px}
.sys-section-title{margin:18px 0 10px}
.service-badges{display:flex;flex-wrap:wrap;gap:10px}
.service-badge{display:inline-flex;align-items:center;gap:8px;min-width:180px;padding:10px 12px;border-radius:10px;border:1px solid #33404e;background:#11171f}
.service-badge .status-dot{width:10px;height:10px;border-radius:999px;flex:0 0 auto}
.status-ok{background:#3ecf8e}
.status-warn{background:#f4b942}
.status-error{background:#ff6676}
.service-badge strong{display:block}
.service-badge small{color:var(--m)}
.diag-grid{
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:12px
}
.diag-card{
  padding:13px;
  border:1px solid #333e4b;
  border-radius:11px;
  background:#11171f;
  transition:border-color .2s ease,background .2s ease
}
.diag-card.good{border-color:#245f44;background:#102219}
.diag-card.warn{border-color:#7a5a22;background:#251d0f}
.diag-card.bad{border-color:#7b313a;background:#251419}
.diag-card.good .diag-value{color:#70dda2}
.diag-card.warn .diag-value{color:#ffc268}
.diag-card.bad .diag-value{color:#ff7f89}
.diag-label{
  color:var(--m);
  font-size:12px;
  margin-bottom:5px
}
.diag-value{
  font-size:20px;
  font-weight:850;
  word-break:break-word
}
.diag-sub{
  color:var(--m);
  font-size:12px;
  margin-top:5px
}
.diag-columns{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:12px;
  margin-top:12px
}
.diag-row{
  display:flex;
  justify-content:space-between;
  gap:16px;
  padding:7px 0;
  border-bottom:1px solid #28313d
}
.diag-row:last-child{border-bottom:0}
.diag-row span:first-child{color:var(--m)}
.diag-ok{color:#83dfae;font-weight:800}
.diag-warn{color:#ffd27a;font-weight:800}
.diag-error{color:#ff8b98;font-weight:800}
.diag-log{
  margin:12px 0 0;
  max-height:430px;
  overflow:auto;
  white-space:pre-wrap;
  word-break:break-word;
  padding:12px;
  border-radius:9px;
  background:#0b0f14;
  border:1px solid #28313d;
  color:#d8e0ea;
  font:12px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace
}
@media(max-width:1000px){
  .diag-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .diag-columns{grid-template-columns:1fr}
}
@media(max-width:620px){
  .diag-grid{grid-template-columns:1fr}
}

.shortcut-button{
  width:44px;
  min-width:44px;
  height:auto;
  padding:0;
  border-radius:9px;
  display:flex;
  align-items:center;
  justify-content:center;
  align-self:stretch;
  font-size:18px;
  background:#26313e;
  color:#fff;
  margin-left:0
}
.shortcut-help{
  position:fixed;
  top:66px;
  right:205px;
  z-index:30;
  width:275px;
  padding:12px;
  border:1px solid #35404e;
  border-radius:12px;
  background:#151b23;
  box-shadow:0 16px 38px rgba(0,0,0,.4);
  opacity:0;
  transform:translateY(-6px) scale(.98);
  pointer-events:none;
  transition:opacity .16s ease,transform .16s ease
}
.shortcut-help.show{
  opacity:1;
  transform:none;
  pointer-events:auto
}
.shortcut-help-title{
  font-weight:800;
  margin-bottom:9px
}
.shortcut-help>div:not(.shortcut-help-title){
  display:grid;
  grid-template-columns:auto auto 1fr;
  gap:5px;
  align-items:center;
  margin-top:7px
}
.shortcut-help span{
  color:var(--m);
  margin-left:5px
}
.shortcut-help kbd{
  min-width:28px;
  padding:3px 6px;
  border:1px solid #46515f;
  border-bottom-width:2px;
  border-radius:5px;
  background:#0f141b;
  color:#fff;
  text-align:center;
  font:inherit;
  font-size:12px
}

@media(max-width:760px){
  .shortcut-help{
    top:72px;
    right:12px;
    width:min(275px,calc(100vw - 24px))
  }
}
.engine{display:inline-flex;align-items:center;gap:7px;padding:7px 10px;border-radius:999px;background:#252c36;font-size:13px}.dot{width:9px;height:9px;border-radius:50%;background:#8b95a4}.engine.running .dot{background:#56d68b}.engine.stopped .dot{background:#ff6572}.engine.restarting .dot{background:#ffc268}.backupbox{border:1px dashed var(--l);border-radius:12px;padding:16px;margin-top:12px}.onvif-card{background:#12161c;border:1px solid var(--l);border-radius:13px;padding:14px;margin:11px 0}.onvif-title{font-weight:850;font-size:17px}.badge{display:inline-block;padding:3px 8px;border-radius:999px;background:#29313c;color:#c8d2df;font-size:12px;margin:3px}.badge.ptz{background:#244b39;color:#8ae6b3}.ptzpad{display:grid;grid-template-columns:repeat(3,52px);gap:7px;justify-content:center;margin:12px 0}.ptzpad button{height:46px;background:#29313c;color:#fff}.profile-row{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:end;margin-top:10px}
.ip-valid{border-color:#3ecf8e!important;box-shadow:0 0 0 1px rgba(62,207,142,.35)}
.ip-invalid{border-color:#ff6676!important;box-shadow:0 0 0 1px rgba(255,102,118,.35)}
.btn-fixed{min-width:170px}
.spinner{display:inline-block;width:13px;height:13px;border:2px solid rgba(255,255,255,.35);border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite;vertical-align:-2px;margin-right:7px}
@keyframes spin{to{transform:rotate(360deg)}}
.password-valid{border-color:#3ecf8e!important;box-shadow:0 0 0 1px rgba(62,207,142,.35)}
.password-invalid{border-color:#ff6676!important;box-shadow:0 0 0 1px rgba(255,102,118,.35)}
.password-status-ok{color:#83dfae}
.password-status-error{color:#ff8b98}

.manual-onvif-grid{
  display:grid;
  grid-template-columns:minmax(220px,2fr) minmax(90px,.55fr) minmax(260px,2fr) minmax(150px,.8fr);
  gap:12px;
  align-items:end
}
.manual-onvif-grid input,
.manual-onvif-grid button{
  height:42px
}
.manual-onvif-grid button{
  width:100%;
  min-width:0
}
@media(max-width:900px){
  .manual-onvif-grid{
    grid-template-columns:1fr 120px
  }
  .manual-onvif-path{
    grid-column:1/-1
  }
  .manual-onvif-action{
    grid-column:1/-1
  }
}

.badge-configured{background:#1f5e3e;color:#aaf0c8;font-weight:800}
.mosaic-toolbar{
  display:flex;
  flex-wrap:wrap;
  gap:14px;
  align-items:end;
  margin-bottom:16px
}
.mosaic-preview{
  display:grid;
  gap:8px;
  width:100%;
  min-height:260px;
  padding:10px;
  border:1px solid var(--l);
  border-radius:14px;
  background:#0b0f14
}
.mosaic-cell-layer{
  display:grid;
  gap:8px;
  position:relative
}
.mosaic-template-bar{
  display:flex;
  flex-wrap:wrap;
  gap:10px;
  margin:14px 0
}
.mosaic-template{
  min-width:150px;
  text-align:left
}
.mosaic-template strong{
  display:block;
  margin-bottom:3px
}
.mosaic-template span{
  color:var(--m);
  font-size:12px
}
.mosaic-template.active{
  border-color:#64a9ff;
  box-shadow:0 0 0 2px rgba(100,169,255,.2)
}
.mosaic-target-valid{
  background:rgba(62,207,142,.18)!important;
  border-color:#3ecf8e!important
}
.mosaic-target-invalid{
  background:rgba(255,102,118,.14)!important;
  border-color:#ff6676!important
}
.mosaic-tile{
  transition:
    grid-column-start .18s ease,
    grid-row-start .18s ease,
    grid-column-end .18s ease,
    grid-row-end .18s ease,
    transform .18s ease
}
.mosaic-size-buttons{
  display:flex;
  flex-wrap:wrap;
  gap:5px;
  margin-top:8px
}
.mosaic-size-buttons button{
  min-width:44px;
  padding:5px 7px;
  font-size:12px
}
.mosaic-tile{
  position:relative;
  min-height:105px;
  padding:12px;
  border:1px solid #384250;
  border-radius:10px;
  background:linear-gradient(145deg,#202731,#151a21);
  cursor:grab;
  user-select:none;
  display:flex;
  flex-direction:column;
  justify-content:space-between;
  overflow:hidden
}
.mosaic-tile:active{cursor:grabbing}
.mosaic-tile.dragging{
  opacity:.35;
  border-style:dashed
}
.mosaic-tile.drag-over{
  border-color:#64a9ff;
  box-shadow:0 0 0 2px rgba(100,169,255,.25)
}
.mosaic-position{
  position:absolute;
  top:8px;
  right:9px;
  min-width:25px;
  height:25px;
  padding:0 6px;
  border-radius:999px;
  display:flex;
  align-items:center;
  justify-content:center;
  background:#0b0f14;
  color:#aeb9c7;
  font-size:12px;
  font-weight:800
}
.mosaic-name{
  padding-right:32px;
  font-size:16px;
  font-weight:850;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap
}
.mosaic-address{
  color:var(--m);
  font-size:12px;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap
}
.mosaic-controls{
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:8px;
  margin-top:10px
}
.mosaic-move{
  display:flex;
  gap:5px
}
.mosaic-move button{
  min-width:35px;
  padding:6px 8px
}
.mosaic-empty{
  min-height:105px;
  border:1px dashed #2f3742;
  border-radius:10px;
  display:flex;
  align-items:center;
  justify-content:center;
  color:#5f6a78;
  font-size:13px
}
.mosaic-warning{
  padding:10px 12px;
  border-radius:9px;
  background:#4d3614;
  color:#ffd995;
  margin-bottom:12px
}
.mosaic-saved{
  color:#83dfae;
  font-size:13px;
  min-height:20px
}

select{width:100%;padding:9px 10px;background:#0c1015;border:1px solid #353d49;border-radius:8px;color:#fff}
</style></head><body>
<section id="login"><form class="loginbox" onsubmit="doLogin(event)"><h1>PiDecoder</h1><p class="muted">Administration v0.9.9.4 RC1</p><div class="field"><label>Utilisateur</label><input id="lu" value="admin"></div><div class="field"><label>Mot de passe</label><input id="lp" type="password"></div><button class="primary">Connexion</button><p id="le" class="muted"></p></form></section>
<section id="app" class="hidden"><header><div><b>PiDecoder</b><div class="muted">Administration v0.9.9.4 RC1</div></div><div class="actions"><span id="engine" class="engine"><span id="globalHealthDot" class="dot"></span><span><strong>PiDecoder</strong><br><small id="engineText">État inconnu</small></span></span><button id="shortcutButton" class="shortcut-button" type="button" title="Raccourcis clavier" onclick="toggleShortcutHelp(event)">⌨️</button><button class="secondary" onclick="save()">Sauvegarder</button><button class="success" onclick="apply()">Appliquer</button><button class="secondary" onclick="logout()">Déconnexion</button></div></header><main>
<nav class="tabs"><button class="tab active" onclick="tab('cams',this)">📹 Caméras</button><button class="tab" onclick="tab('onvif',this)">🌐 ONVIF</button><button class="tab" onclick="tab('layout',this)">🖥 Disposition</button><button class="tab" onclick="tab('sys',this)">💻 Système</button><button class="tab" onclick="tab('sec',this)">🔐 Sécurité</button><button class="tab" onclick="tab('backup',this)">💾 Sauvegarde</button></nav>
<section id="cams"><div class="panel"><div class="row" style="justify-content:space-between"><div><h2>Caméras</h2><div class="muted">Déplacement uniquement avec la poignée ☰. Les champs texte restent sélectionnables normalement.</div></div><button class="primary" onclick="addCam()">+ Ajouter</button></div><div id="list"></div></div></section>
<section id="layout" class="hidden"><div class="panel"><div class="row" style="justify-content:space-between"><div><h2>Disposition de la mosaïque</h2><div class="muted">Déplace et redimensionne les caméras actives dans la grille. Les collisions sont refusées et la disposition est sauvegardée automatiquement.</div></div><button class="secondary" onclick="resetMosaicOrder()">Réinitialiser l’ordre</button></div><div class="mosaic-toolbar"><div class="small"><label>Colonnes</label><input id="cols" type="number" min="1" max="9"></div><div class="small"><label>Lignes</label><input id="rows" type="number" min="1" max="9"></div><label><input id="fs" type="checkbox" style="width:auto"> Plein écran au démarrage</label><div id="mosaicSaved" class="mosaic-saved"></div></div><div class="mosaic-template-bar"><button class="secondary mosaic-template" onclick="applyMosaicTemplate('uniform')"><strong>Grille uniforme</strong><span>Toutes les caméras en 1×1</span></button><button class="secondary mosaic-template" onclick="applyMosaicTemplate('main')"><strong>Caméra principale</strong><span>Une grande caméra, les autres autour</span></button><button class="secondary mosaic-template" onclick="applyMosaicTemplate('dual')"><strong>Deux principales</strong><span>Deux grandes vues puis les autres</span></button><button class="secondary mosaic-template" onclick="applyMosaicTemplate('free')"><strong>Libre</strong><span>Conserver la disposition actuelle</span></button></div><div id="mosaicWarning"></div><div id="mosaicPreview" class="mosaic-preview"></div></div></section>
<section id="sys" class="hidden">
  <div class="panel">
    <div class="row" style="justify-content:space-between;align-items:center">
      <div>
        <h2>Système</h2>
        <div class="muted">État du Raspberry Pi, de PiDecoder et informations utiles au support.</div>
      </div>
      <div class="row">
        <button class="secondary" onclick="refreshDiagnostics()">Actualiser</button>
        <button class="secondary" onclick="copyDiagnostics()">Copier le rapport</button>
      </div>
    </div>

    <h3 class="sys-section-title">Santé</h3>
    <div id="systemHealthGrid" class="diag-grid"></div>

    <div class="diag-columns">
      <div class="backupbox">
        <h3>PiDecoder</h3>
        <div id="pidecoderInfo"></div>
      </div>

      <div class="backupbox">
        <h3>Caméras</h3>
        <div id="cameraInfo"></div>
      </div>
    </div>

    <div class="backupbox">
      <h3>Services</h3>
      <div id="serviceBadges" class="service-badges"></div>
    </div>

    <div class="backupbox">
      <div class="row" style="justify-content:space-between;align-items:end">
        <div>
          <h3 style="margin:0">Journaux récents</h3>
          <div class="muted">Journaux de PiDecoder et de l’administration Web.</div>
        </div>
        <div class="small">
          <label>Lignes</label>
          <select id="diagnosticLogLines" onchange="refreshDiagnostics()">
            <option value="20">20</option>
            <option value="50" selected>50</option>
            <option value="100">100</option>
          </select>
        </div>
      </div>
      <pre id="diagnosticsLogs" class="diag-log">Ouvre l’onglet Système pour charger les diagnostics.</pre>
    </div>

    <textarea id="diagnosticsCopyBuffer" class="hidden" aria-hidden="true"></textarea>
  </div>
</section>
<section id="sec" class="hidden"><div class="panel"><h2>Mot de passe administrateur</h2><div class="muted">Le mot de passe actuel est requis. Le nouveau mot de passe doit être saisi deux fois à l’identique.</div><div class="grid" style="margin-top:14px"><div class="s4"><label>Mot de passe actuel</label><input id="oldp" type="password" autocomplete="current-password"></div><div class="s4"><label>Nouveau mot de passe</label><input id="newp" type="password" autocomplete="new-password"></div><div class="s4"><label>Confirmer le nouveau mot de passe</label><input id="confirmp" type="password" autocomplete="new-password"></div></div><div id="passwordStatus" class="muted" style="margin-top:10px;min-height:20px"></div><div class="row" style="margin-top:12px"><button id="changePwdButton" class="primary" onclick="changePwd()" disabled>Modifier le mot de passe</button></div></div></section>
<section id="backup" class="hidden"><div class="panel"><h2>Sauvegarde et restauration</h2><div class="backupbox"><h3>Exporter</h3><p class="muted">Télécharge les caméras et la disposition dans un fichier JSON portable. Le mot de passe Web n'est pas exporté.</p><button class="primary" onclick="exportConfig()">📤 Exporter la configuration</button></div><div class="backupbox"><h3>Importer</h3><p class="muted">L'import crée une sauvegarde des fichiers actuels avant de les remplacer.</p><input id="importFile" type="file" accept="application/json,.json"><div style="margin-top:10px"><button class="secondary" onclick="importConfig()">📥 Importer la configuration</button></div></div></div></section>
<section id="onvif" class="hidden"><div class="panel"><div class="row" style="justify-content:space-between"><div><h2>ONVIF — Gestion des caméras</h2><div class="muted">Recherche locale ou identification manuelle par adresse IPv4. Choix séparé des profils mosaïque et plein écran.</div></div><button class="primary" onclick="discoverOnvif()">🔎 Rechercher les caméras</button></div><div class="row" style="margin-top:14px"><div class="grow"><label>Utilisateur ONVIF</label><input id="onvifUser" autocomplete="off"></div><div class="grow"><label>Mot de passe ONVIF</label><input id="onvifPassword" type="password" autocomplete="new-password"></div></div><div class="backupbox"><h3 style="margin-top:0">Ajouter manuellement par IPv4</h3><div class="muted">Pour une caméra non découverte, située sur un autre réseau routé ou dont WS-Discovery est désactivé.</div><div class="manual-onvif-grid" style="margin-top:12px"><div><label>Adresse</label><input id="manualOnvifIp" placeholder="192.168.1.100" inputmode="decimal" autocomplete="off"></div><div><label>Port ONVIF</label><input id="manualOnvifPort" type="number" min="1" max="65535" value="80"></div><div class="manual-onvif-path"><label>Chemin ONVIF</label><input id="manualOnvifPath" value="/onvif/device_service"></div><div class="manual-onvif-action"><button id="manualOnvifButton" class="secondary" onclick="identifyManualOnvif()">Identifier</button></div></div></div><div id="onvifStatus" class="muted" style="margin-top:14px"></div><div id="onvifDiagnostics" class="backupbox" style="display:none"></div><div id="onvifResults"></div></div>
</section></main></section><div id="toast" class="toast"></div><button id="notificationToggle" class="notification-toggle" type="button" title="Historique des notifications" onclick="toggleNotificationHistory(event)">🔔<span id="notificationCount" class="notification-count"></span></button><div id="shortcutHelp" class="shortcut-help">
  <div class="shortcut-help-title">Raccourcis clavier</div>
  <div><kbd>Ctrl</kbd> + <kbd>S</kbd><span>Sauvegarder</span></div>
  <div><kbd>Ctrl</kbd> + <kbd>Entrée</kbd><span>Appliquer</span></div>
  <div><kbd>Alt</kbd> + <kbd>1–6</kbd><span>Changer d’onglet</span></div>
  <div><kbd>Échap</kbd><span>Fermer les fenêtres</span></div>
</div><div id="notificationHistory" class="notification-history"><div class="notification-history-header"><strong>Notifications récentes</strong><button class="secondary" type="button" onclick="clearNotificationHistory()">Effacer</button></div><div id="notificationList"></div></div>
<script>
let cfg={cameras:[],layout:{}},drag=null,timer=null;
const NOTIFICATION_LIMIT=5;
let notificationItems=[];
let notificationUnread=0;

function notificationTime(){
  return new Intl.DateTimeFormat(
    'fr-CH',
    {hour:'2-digit',minute:'2-digit',second:'2-digit'}
  ).format(new Date());
}

function renderNotificationHistory(){
  notificationList.innerHTML='';

  if(!notificationItems.length){
    notificationList.innerHTML=
      '<div class="notification-empty">Aucune notification récente</div>';
  }else{
    notificationItems.forEach(item=>{
      const row=document.createElement('div');
      row.className='notification-item'+(item.error?' error':'');
      row.innerHTML=
        `<div>${esc(item.message)}</div>`+
        `<div class="notification-time">${esc(item.time)}</div>`;
      notificationList.appendChild(row);
    });
  }

  notificationCount.textContent=String(
    Math.min(NOTIFICATION_LIMIT,notificationUnread)
  );
  notificationCount.style.display=notificationUnread?'flex':'none';
}

function pushNotification(message,error=false){
  notificationItems.unshift({
    message:String(message),
    error:Boolean(error),
    time:notificationTime()
  });

  notificationItems=notificationItems.slice(
    0,
    NOTIFICATION_LIMIT
  );

  const history=document.getElementById('notificationHistory');

  if(!history.classList.contains('show')){
    notificationUnread=Math.min(
      NOTIFICATION_LIMIT,
      notificationUnread+1
    );
  }

  renderNotificationHistory();
}

function toggleNotificationHistory(event){
  if(event){
    event.preventDefault();
    event.stopPropagation();
  }

  const history=document.getElementById('notificationHistory');
  const help=document.getElementById('shortcutHelp');
  const opening=!history.classList.contains('show');

  help.classList.remove('show');
  history.classList.toggle('show',opening);

  if(opening){
    notificationUnread=0;
    renderNotificationHistory();
  }
}

function toggleShortcutHelp(event){
  if(event){
    event.preventDefault();
    event.stopPropagation();
  }

  const help=document.getElementById('shortcutHelp');
  const history=document.getElementById('notificationHistory');
  const opening=!help.classList.contains('show');

  history.classList.remove('show');
  help.classList.toggle('show',opening);
}

function clearNotificationHistory(){
  notificationItems=[];
  notificationUnread=0;
  renderNotificationHistory();
}

function toast(m,e=false){
  const t=document.getElementById('toast');
  t.textContent=m;
  t.className='toast show'+(e?' error':'');
  pushNotification(m,e);
  clearTimeout(timer);
  timer=setTimeout(()=>t.className='toast',3000);
}
async function api(path,opt={}){
  const response=await fetch(
    path,
    {
      ...opt,
      headers:{
        'Content-Type':'application/json',
        ...(opt.headers||{})
      }
    }
  );

  const contentType=response.headers.get('content-type')||'';
  let data;

  if(contentType.includes('application/json')){
    data=await response.json();
  }else{
    const text=await response.text();
    data={
      ok:false,
      error:
        response.status===404
          ? 'Fonction indisponible sur cette version du serveur'
          : `Réponse serveur invalide (${response.status})`
    };

    console.error(
      'Réponse non JSON pour',
      path,
      text.slice(0,500)
    );
  }

  if(response.status===401){
    if(path==='/api/login'){
      throw Error(data.error||'Mot de passe incorrect');
    }

    showLogin();
    throw Error('Session expirée');
  }

  if(!response.ok||data.ok===false){
    throw Error(data.error||'Erreur serveur');
  }

  return data;
}

function showLogin(){app.classList.add('hidden');login.classList.remove('hidden')}
async function showApp(){login.classList.add('hidden');app.classList.remove('hidden');await loadCfg();sysInfo()}
async function boot(){let s=await api('/api/session');s.authenticated?showApp():showLogin()}
async function doLogin(e){e.preventDefault();le.textContent='';try{await api('/api/login',{method:'POST',body:JSON.stringify({username:lu.value,password:lp.value})});lp.value='';le.textContent='';showApp()}catch(x){le.textContent=x.message}}
async function logout(){await api('/api/logout',{method:'POST',body:'{}'});showLogin()}
function tab(id,b){for(let x of ['cams','layout','sys','sec','backup','onvif'])document.getElementById(x).classList.toggle('hidden',x!==id);document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');if(id==='sys'){refreshDiagnostics();sysInfo()}if(id==='layout'){sync();renderMosaic()}}
async function loadCfg(){cfg=await api('/api/config');cols.value=cfg.layout.columns||3;rows.value=cfg.layout.rows||3;fs.checked=!!cfg.layout.fullscreen_on_start;let o=cfg.layout.camera_order||[],active=cfg.cameras.filter(c=>c.enabled!==false),ordered=[];for(let i of o)if(active[i])ordered.push(active[i]);active.forEach((c,i)=>{if(!o.includes(i))ordered.push(c)});let cursor=0;cfg.cameras=cfg.cameras.map(c=>c.enabled===false?c:ordered[cursor++]);ensurePlacements();render();renderMosaic()}
function esc(v){let d=document.createElement('div');d.textContent=v??'';return d.innerHTML}
function parse(u){let r={user:'',pwd:'',host:'',port:'554',path:'/axis-media/media.amp',w:'',h:'',fps:''};try{let x=new URL(u),res=(x.searchParams.get('resolution')||'').split('x');r={user:decodeURIComponent(x.username||''),pwd:decodeURIComponent(x.password||''),host:x.hostname,port:x.port||'554',path:x.pathname||'/',w:res[0]||'',h:res[1]||'',fps:x.searchParams.get('fps')||''}}catch{}return r}
function build(b,w,h,f,orig){if(!b.host)return orig;let a=b.user?encodeURIComponent(b.user)+(b.pwd?':'+encodeURIComponent(b.pwd):'')+'@':'',p=b.port?':'+b.port:'',path=b.path.startsWith('/')?b.path:'/'+b.path,q=new URLSearchParams();try{q=new URL(orig).searchParams}catch{}if(w&&h)q.set('resolution',w+'x'+h);else q.delete('resolution');if(f)q.set('fps',f);else q.delete('fps');return `rtsp://${a}${b.host}${p}${path}${q.toString()?'?'+q.toString():''}`}
function render(){list.innerHTML='';cfg.cameras.forEach((c,i)=>{let g=parse(c.grid_url),f=parse(c.focus_url),b=g.host?g:f,d=document.createElement('div');d.className='camera';d.innerHTML=`<div class="head"><span class="handle" draggable="true">☰</span><span class="title">${esc(c.name)}</span><label><input class="en" type="checkbox" style="width:auto" ${c.enabled!==false?'checked':''}> active</label><button class="danger del">Supprimer</button></div><div class="grid"><div class="s4"><label>Nom</label><input class="name" value="${esc(c.name)}"></div><div class="s4"><label>Adresse IP</label><input class="host" value="${esc(b.host)}"></div><div class="s4"><label>Port RTSP</label><input class="port" type="number" value="${esc(b.port)}"></div><div class="s4"><label>Utilisateur</label><input class="user" value="${esc(b.user)}"></div><div class="s4"><label>Mot de passe</label><div class="pass"><input class="pwd" type="password" value="${esc(b.pwd)}"><button class="secondary eye" type="button">👁</button></div></div><div class="s4"><label>Chemin RTSP</label><input class="path" value="${esc(b.path)}"></div><div class="s6"><label>Résolution mosaïque</label><div class="pair"><input class="gw" type="number" value="${esc(g.w)}" placeholder="640"><span>×</span><input class="gh" type="number" value="${esc(g.h)}" placeholder="360"></div></div><div class="s3"><label>FPS mosaïque</label><input class="gf" type="number" value="${esc(g.fps)}" placeholder="12"></div><div class="s3"><label>&nbsp;</label><button class="secondary def">Valeurs PiDecoder</button></div><div class="s6"><label>Résolution plein écran</label><div class="pair"><input class="fw" type="number" value="${esc(f.w)}" placeholder="1920"><span>×</span><input class="fh" type="number" value="${esc(f.h)}" placeholder="1080"></div></div><div class="s3"><label>FPS plein écran</label><input class="ff" type="number" value="${esc(f.fps)}" placeholder="25"></div><div class="s12"><details><summary>URL avancées / mode manuel</summary><div class="field"><label>URL mosaïque</label><input class="gu" value="${esc(c.grid_url)}"></div><div class="field"><label>URL plein écran</label><input class="fu" value="${esc(c.focus_url)}"></div><div class="muted">Adresse vide = les URL manuelles sont conservées.</div></details></div></div>`;
let h=d.querySelector('.handle');h.ondragstart=e=>{sync();drag=i;e.dataTransfer.effectAllowed='move';d.style.opacity='.45'};h.ondragend=()=>{drag=null;d.style.opacity='1'};d.ondragover=e=>{if(drag!==null)e.preventDefault()};d.ondrop=e=>{if(drag===null)return;e.preventDefault();let m=cfg.cameras.splice(drag,1)[0];cfg.cameras.splice(i,0,m);drag=null;render()};d.querySelector('.del').onclick=()=>{sync();cfg.cameras.splice(i,1);render();renderMosaic()};d.querySelector('.eye').onclick=()=>{let x=d.querySelector('.pwd');x.type=x.type==='password'?'text':'password'};d.querySelector('.def').onclick=()=>{d.querySelector('.gw').value=640;d.querySelector('.gh').value=360;d.querySelector('.gf').value=12;d.querySelector('.fw').value=1920;d.querySelector('.fh').value=1080;d.querySelector('.ff').value=25};list.appendChild(d)})}
function read(d){let b={user:d.querySelector('.user').value.trim(),pwd:d.querySelector('.pwd').value,host:d.querySelector('.host').value.trim(),port:d.querySelector('.port').value.trim(),path:d.querySelector('.path').value.trim()};return{name:d.querySelector('.name').value.trim()||'Caméra',enabled:d.querySelector('.en').checked,grid_url:build(b,d.querySelector('.gw').value,d.querySelector('.gh').value,d.querySelector('.gf').value,d.querySelector('.gu').value.trim()),focus_url:build(b,d.querySelector('.fw').value,d.querySelector('.fh').value,d.querySelector('.ff').value,d.querySelector('.fu').value.trim())}}
function sync(){cfg.cameras=[...document.querySelectorAll('.camera')].map(read)}
function addCam(){sync();cfg.cameras.push({name:'Caméra '+(cfg.cameras.length+1),enabled:true,grid_url:'rtsp://root:@192.168.1.100:554/axis-media/media.amp?videocodec=h264&resolution=640x360&fps=12',focus_url:'rtsp://root:@192.168.1.100:554/axis-media/media.amp?videocodec=h264&resolution=1920x1080&fps=25'});render();renderMosaic()}
let mosaicDragCamera=null;
let mosaicSaveTimer=null;
let mosaicCurrentTemplate='free';

function activeCameraEntries(){
  return cfg.cameras
    .map((camera,index)=>({camera,index}))
    .filter(entry=>entry.camera.enabled!==false);
}

function activeCameraCount(){
  return activeCameraEntries().length;
}

function clonePlacement(item){
  return {
    camera:Number(item.camera),
    x:Number(item.x),
    y:Number(item.y),
    width:Number(item.width)||1,
    height:Number(item.height)||1
  };
}

function placementOverlap(left,right){
  return !(
    left.x+left.width<=right.x ||
    right.x+right.width<=left.x ||
    left.y+left.height<=right.y ||
    right.y+right.height<=left.y
  );
}

function placementFits(item,columns,lines){
  return (
    item.x>=0 &&
    item.y>=0 &&
    item.width>=1 &&
    item.height>=1 &&
    item.x+item.width<=columns &&
    item.y+item.height<=lines
  );
}

function firstFreePlacement(camera,width,height,occupied,columns,lines){
  for(let y=0;y<=lines-height;y++){
    for(let x=0;x<=columns-width;x++){
      const candidate={camera,x,y,width,height};

      if(!occupied.some(other=>placementOverlap(candidate,other))){
        return candidate;
      }
    }
  }

  return null;
}

function packPlacements(preferredCamera=null,preferredPlacement=null){
  const count=activeCameraCount();
  const columns=Math.max(1,Math.min(9,Number(cols.value)||3));
  const lines=Math.max(1,Math.min(9,Number(rows.value)||3));
  const current=(cfg.layout.placements||[])
    .map(clonePlacement)
    .filter(item=>item.camera>=0&&item.camera<count);

  const byCamera=new Map(
    current.map(item=>[item.camera,item])
  );

  const packed=[];

  if(preferredCamera!==null && preferredPlacement){
    const preferred=clonePlacement(preferredPlacement);

    if(!placementFits(preferred,columns,lines)){
      return null;
    }

    packed.push(preferred);
  }

  const cameraOrder=Array.from({length:count},(_,camera)=>camera);

  for(const camera of cameraOrder){
    if(camera===preferredCamera){
      continue;
    }

    const old=byCamera.get(camera)||{
      camera,
      x:0,
      y:0,
      width:1,
      height:1
    };

    let candidate={
      ...old,
      width:Math.max(1,Math.min(columns,old.width)),
      height:Math.max(1,Math.min(lines,old.height))
    };

    if(
      !placementFits(candidate,columns,lines) ||
      packed.some(other=>placementOverlap(candidate,other))
    ){
      candidate=firstFreePlacement(
        camera,
        candidate.width,
        candidate.height,
        packed,
        columns,
        lines
      );
    }

    if(!candidate){
      candidate=firstFreePlacement(
        camera,
        1,
        1,
        packed,
        columns,
        lines
      );
    }

    if(!candidate){
      return null;
    }

    packed.push(candidate);
  }

  return packed.sort((a,b)=>a.camera-b.camera);
}

function ensurePlacements(){
  const count=activeCameraCount();
  const existing=Array.isArray(cfg.layout.placements)
    ? cfg.layout.placements
    : [];

  const seen=new Set();
  const normalized=[];

  for(const raw of existing){
    const item=clonePlacement(raw);

    if(
      !Number.isInteger(item.camera) ||
      item.camera<0 ||
      item.camera>=count ||
      seen.has(item.camera)
    ){
      continue;
    }

    normalized.push(item);
    seen.add(item.camera);
  }

  for(let camera=0;camera<count;camera++){
    if(!seen.has(camera)){
      normalized.push({
        camera,
        x:0,
        y:0,
        width:1,
        height:1
      });
    }
  }

  cfg.layout.placements=normalized;

  const packed=packPlacements();

  if(packed){
    cfg.layout.placements=packed;
  }
}

function placementFor(camera){
  ensurePlacements();

  return cfg.layout.placements.find(
    item=>item.camera===camera
  );
}

function trySmartPlacement(camera,target){
  ensurePlacements();

  const old=placementFor(camera);
  const preferred={
    ...old,
    x:target.x,
    y:target.y
  };

  const packed=packPlacements(camera,preferred);

  if(!packed){
    toast('La grille est trop petite pour cette disposition',true);
    return false;
  }

  cfg.layout.placements=packed;
  mosaicCurrentTemplate='free';
  renderMosaic();
  scheduleMosaicSave();
  return true;
}

function trySmartResize(camera,width,height){
  ensurePlacements();

  const old=placementFor(camera);
  const preferred={
    ...old,
    width,
    height
  };

  const packed=packPlacements(camera,preferred);

  if(!packed){
    toast('Pas assez de place pour agrandir cette caméra',true);
    return false;
  }

  cfg.layout.placements=packed;
  mosaicCurrentTemplate='free';
  renderMosaic();
  scheduleMosaicSave();
  return true;
}

function swapCameraPositions(sourceCamera,targetCamera){
  ensurePlacements();

  const source=placementFor(sourceCamera);
  const target=placementFor(targetCamera);

  const sourcePosition={
    x:source.x,
    y:source.y
  };

  const targetPosition={
    x:target.x,
    y:target.y
  };

  const preferred={
    ...source,
    x:targetPosition.x,
    y:targetPosition.y
  };

  const packed=packPlacements(sourceCamera,preferred);

  if(!packed){
    return false;
  }

  const movedTarget=packed.find(item=>item.camera===targetCamera);

  if(
    movedTarget &&
    source.width===target.width &&
    source.height===target.height
  ){
    movedTarget.x=sourcePosition.x;
    movedTarget.y=sourcePosition.y;

    const others=packed.filter(item=>
      item.camera!==sourceCamera &&
      item.camera!==targetCamera
    );

    if(
      placementFits(movedTarget,Number(cols.value),Number(rows.value)) &&
      !others.some(other=>placementOverlap(movedTarget,other))
    ){
      cfg.layout.placements=packed.sort((a,b)=>a.camera-b.camera);
      mosaicCurrentTemplate='free';
      renderMosaic();
      scheduleMosaicSave();
      return true;
    }
  }

  cfg.layout.placements=packed;
  mosaicCurrentTemplate='free';
  renderMosaic();
  scheduleMosaicSave();
  return true;
}

function cameraAddress(camera){
  const parsed=parse(camera.grid_url||camera.focus_url||'');
  return parsed.host||'Adresse inconnue';
}

function updateTemplateButtons(){
  document
    .querySelectorAll('.mosaic-template')
    .forEach(button=>{
      const handler=button.getAttribute('onclick')||'';
      button.classList.toggle(
        'active',
        handler.includes(`'${mosaicCurrentTemplate}'`)
      );
    });
}

function renderMosaic(){
  if(!window.mosaicPreview)return;

  sync();

  const columns=Math.max(1,Math.min(9,Number(cols.value)||3));
  const lines=Math.max(1,Math.min(9,Number(rows.value)||3));
  const active=activeCameraEntries();

  cfg.layout.columns=columns;
  cfg.layout.rows=lines;
  ensurePlacements();

  mosaicPreview.style.gridTemplateColumns=`repeat(${columns},minmax(0,1fr))`;
  mosaicPreview.style.gridTemplateRows=`repeat(${lines},minmax(105px,1fr))`;
  mosaicPreview.innerHTML='';

  const usedCells=cfg.layout.placements.reduce(
    (sum,item)=>sum+(item.width*item.height),
    0
  );

  if(usedCells>columns*lines){
    mosaicWarning.innerHTML=
      '<div class="mosaic-warning">⚠ La grille est trop petite pour cette disposition.</div>';
  }else{
    mosaicWarning.innerHTML='';
  }

  for(let y=0;y<lines;y++){
    for(let x=0;x<columns;x++){
      const empty=document.createElement('div');
      empty.className='mosaic-empty';
      empty.dataset.x=String(x);
      empty.dataset.y=String(y);
      empty.textContent=`${x+1},${y+1}`;

      empty.ondragover=event=>{
        event.preventDefault();

        if(mosaicDragCamera===null){
          return;
        }

        const source=placementFor(mosaicDragCamera);
        const candidate={
          ...source,
          x,
          y
        };

        const directValid=placementFits(
          candidate,
          columns,
          lines
        );

        empty.classList.toggle(
          'mosaic-target-valid',
          directValid
        );

        empty.classList.toggle(
          'mosaic-target-invalid',
          !directValid
        );
      };

      empty.ondragleave=()=>{
        empty.classList.remove(
          'mosaic-target-valid',
          'mosaic-target-invalid'
        );
      };

      empty.ondrop=event=>{
        event.preventDefault();

        empty.classList.remove(
          'mosaic-target-valid',
          'mosaic-target-invalid'
        );

        if(mosaicDragCamera!==null){
          trySmartPlacement(
            mosaicDragCamera,
            {x,y}
          );
        }
      };

      mosaicPreview.appendChild(empty);
    }
  }

  active.forEach((entry,camera)=>{
    const placement=placementFor(camera);
    const tile=document.createElement('div');
    tile.className='mosaic-tile';
    tile.draggable=true;
    tile.dataset.camera=String(camera);
    tile.style.gridColumn=`${placement.x+1} / span ${placement.width}`;
    tile.style.gridRow=`${placement.y+1} / span ${placement.height}`;
    tile.style.zIndex='2';

    tile.innerHTML=`
      <span class="mosaic-position">${camera+1}</span>
      <div>
        <div class="mosaic-name">${esc(entry.camera.name||'Caméra')}</div>
        <div class="mosaic-address">${esc(cameraAddress(entry.camera))}</div>
      </div>
      <div>
        <div class="mosaic-size-buttons">
          <button class="secondary size-11" type="button">1×1</button>
          <button class="secondary size-21" type="button">2×1</button>
          <button class="secondary size-12" type="button">1×2</button>
          <button class="secondary size-22" type="button">2×2</button>
        </div>
        <div class="mosaic-controls">
          <span class="badge">${placement.width}×${placement.height}</span>
          <span class="muted">Glisser pour déplacer</span>
        </div>
      </div>`;

    tile.ondragstart=event=>{
      mosaicDragCamera=camera;
      tile.classList.add('dragging');
      event.dataTransfer.effectAllowed='move';
      event.dataTransfer.setData('text/plain',String(camera));
    };

    tile.ondragover=event=>{
      event.preventDefault();

      if(
        mosaicDragCamera===null ||
        mosaicDragCamera===camera
      ){
        return;
      }

      tile.classList.add('mosaic-target-valid');
    };

    tile.ondragleave=()=>{
      tile.classList.remove('mosaic-target-valid');
    };

    tile.ondrop=event=>{
      event.preventDefault();
      tile.classList.remove('mosaic-target-valid');

      if(
        mosaicDragCamera!==null &&
        mosaicDragCamera!==camera
      ){
        swapCameraPositions(
          mosaicDragCamera,
          camera
        );
      }
    };

    tile.ondragend=()=>{
      mosaicDragCamera=null;
      document
        .querySelectorAll(
          '.mosaic-tile,.mosaic-empty'
        )
        .forEach(item=>item.classList.remove(
          'dragging',
          'mosaic-target-valid',
          'mosaic-target-invalid'
        ));
    };

    tile.querySelector('.size-11').onclick=event=>{
      event.stopPropagation();
      trySmartResize(camera,1,1);
    };

    tile.querySelector('.size-21').onclick=event=>{
      event.stopPropagation();
      trySmartResize(camera,2,1);
    };

    tile.querySelector('.size-12').onclick=event=>{
      event.stopPropagation();
      trySmartResize(camera,1,2);
    };

    tile.querySelector('.size-22').onclick=event=>{
      event.stopPropagation();
      trySmartResize(camera,2,2);
    };

    mosaicPreview.appendChild(tile);
  });

  if(!active.length){
    mosaicPreview.innerHTML=
      '<div class="mosaic-empty">Aucune caméra active</div>';
  }

  updateTemplateButtons();
}

function buildUniformTemplate(){
  const count=activeCameraCount();
  const columns=Math.max(1,Number(cols.value)||3);

  return Array.from({length:count},(_,camera)=>({
    camera,
    x:camera%columns,
    y:Math.floor(camera/columns),
    width:1,
    height:1
  }));
}

function buildMainTemplate(){
  const count=activeCameraCount();
  const columns=Math.max(3,Number(cols.value)||3);
  const lines=Math.max(3,Number(rows.value)||3);

  cols.value=columns;
  rows.value=lines;

  if(!count){
    return [];
  }

  const placements=[
    {
      camera:0,
      x:0,
      y:0,
      width:Math.min(2,columns),
      height:Math.min(2,lines)
    }
  ];

  for(let camera=1;camera<count;camera++){
    const free=firstFreePlacement(
      camera,
      1,
      1,
      placements,
      columns,
      lines
    );

    if(!free){
      return null;
    }

    placements.push(free);
  }

  return placements;
}

function buildDualTemplate(){
  const count=activeCameraCount();
  const columns=Math.max(4,Number(cols.value)||4);
  const lines=Math.max(3,Number(rows.value)||3);

  cols.value=columns;
  rows.value=lines;

  const placements=[];

  if(count>=1){
    placements.push({
      camera:0,
      x:0,
      y:0,
      width:Math.min(2,columns),
      height:Math.min(2,lines)
    });
  }

  if(count>=2){
    const second={
      camera:1,
      x:Math.min(2,columns-1),
      y:0,
      width:Math.min(2,columns-Math.min(2,columns-1)),
      height:Math.min(2,lines)
    };

    if(
      second.width<1 ||
      placements.some(other=>placementOverlap(second,other))
    ){
      const free=firstFreePlacement(
        1,
        2,
        2,
        placements,
        columns,
        lines
      );

      if(!free){
        return null;
      }

      placements.push(free);
    }else{
      placements.push(second);
    }
  }

  for(let camera=2;camera<count;camera++){
    const free=firstFreePlacement(
      camera,
      1,
      1,
      placements,
      columns,
      lines
    );

    if(!free){
      return null;
    }

    placements.push(free);
  }

  return placements;
}

function applyMosaicTemplate(name){
  let placements=null;

  if(name==='uniform'){
    placements=buildUniformTemplate();
  }else if(name==='main'){
    placements=buildMainTemplate();
  }else if(name==='dual'){
    placements=buildDualTemplate();
  }else if(name==='free'){
    mosaicCurrentTemplate='free';
    updateTemplateButtons();
    return;
  }

  if(!placements){
    toast('La grille est trop petite pour ce modèle',true);
    return;
  }

  cfg.layout.columns=Math.max(1,Number(cols.value)||3);
  cfg.layout.rows=Math.max(1,Number(rows.value)||3);
  cfg.layout.placements=placements;
  mosaicCurrentTemplate=name;

  renderMosaic();
  scheduleMosaicSave();
}

function scheduleMosaicSave(){
  clearTimeout(mosaicSaveTimer);
  mosaicSaved.textContent='Sauvegarde…';

  mosaicSaveTimer=setTimeout(
    async()=>{
      try{
        await save(false);
        mosaicSaved.textContent='✔ Disposition sauvegardée — clique sur Appliquer';
      }catch(error){
        mosaicSaved.textContent='';
        toast(error.message,true);
      }
    },
    250
  );
}

function resetMosaicOrder(){
  applyMosaicTemplate('uniform');
}

function mosaicSettingsChanged(){
  cfg.layout.columns=Math.max(1,Number(cols.value)||3);
  cfg.layout.rows=Math.max(1,Number(rows.value)||3);

  const packed=packPlacements();

  if(packed){
    cfg.layout.placements=packed;
  }else{
    cfg.layout.placements=buildUniformTemplate();
  }

  mosaicCurrentTemplate='free';
  renderMosaic();
  scheduleMosaicSave();
}

function collect(){sync();const activeCount=cfg.cameras.filter(c=>c.enabled!==false).length;ensurePlacements();cfg.layout={columns:+cols.value||3,rows:+rows.value||3,fullscreen_on_start:fs.checked,camera_order:Array.from({length:activeCount},(_,i)=>i),placements:cfg.layout.placements};return cfg}
async function save(show=true){await api('/api/config',{method:'POST',body:JSON.stringify(collect())});if(show)toast('✓ Sauvegarde effectuée')}
async function apply(){try{await save(false);let r=await api('/api/apply',{method:'POST',body:'{}'});toast(r.message,!r.applied)}catch(e){toast(e.message,true)}}
function healthState(value,warnAt,badAt){
  const number=Number(value);

  if(!Number.isFinite(number)){
    return '';
  }

  if(number>=badAt){
    return 'bad';
  }

  if(number>=warnAt){
    return 'warn';
  }

  return 'good';
}

function formatSystemUptime(seconds){
  const total=Math.max(0,Number(seconds)||0);
  const days=Math.floor(total/86400);
  const hours=Math.floor((total%86400)/3600);
  const minutes=Math.floor((total%3600)/60);

  if(days){
    return `${days} j ${hours} h ${minutes} min`;
  }

  if(hours){
    return `${hours} h ${minutes} min`;
  }

  return `${minutes} min`;
}

function throttlingHealth(raw,label=''){
  const value=String(raw??'').trim().toLowerCase();

  if(!value || value==='—' || value==='indisponible'){
    return {
      value:'Indisponible',
      sub:label||'vcgencmd indisponible',
      state:''
    };
  }

  const bits=Number.parseInt(value,16);

  if(!Number.isFinite(bits)){
    return {
      value,
      sub:label||'Valeur non reconnue',
      state:'warn'
    };
  }

  if((bits&0x000f)!==0){
    return {
      value:'Actif',
      sub:value,
      state:'bad'
    };
  }

  if((bits&0xf0000)!==0){
    return {
      value:'Historique',
      sub:value,
      state:'warn'
    };
  }

  return {
    value:'Aucun',
    sub:value,
    state:'good'
  };
}

function renderSystemHealth(system={}){
  const temperature=system.temperature_c;
  const cpu=system.cpu_percent;
  const memory=system.memory_percent;
  const throttling=throttlingHealth(
    system.throttled_hex??system.throttled,
    system.throttled_label||''
  );

  const load=Array.isArray(system.load_average)
    ? system.load_average
        .map(value=>Number(value).toFixed(2))
        .join(' / ')
    : (system.load_average||'—');

  const uptime=system.uptime_human
    || formatSystemUptime(system.uptime_seconds);

  const memorySub=system.memory_used_human
    || (
      system.memory_used_mb!=null
      && system.memory_total_mb!=null
        ? `${system.memory_used_mb} / ${system.memory_total_mb} Mo`
        : ''
    );

  const cards=[
    [
      'Température CPU',
      temperature!=null?`${temperature} °C`:'Indisponible',
      '',
      healthState(temperature,75,80)
    ],
    [
      'CPU',
      cpu!=null?`${cpu} %`:'—',
      '',
      healthState(cpu,75,90)
    ],
    [
      'RAM',
      memory!=null?`${memory} %`:'—',
      memorySub,
      healthState(memory,80,90)
    ],
    [
      'Load',
      load,
      system.cpu_count?`${system.cpu_count} cœur(s)`:'',
      ''
    ],
    [
      'Uptime',
      uptime,
      system.boot_time||'',
      ''
    ],
    [
      'Throttling',
      throttling.value,
      throttling.sub,
      throttling.state
    ],
  ];

  systemHealthGrid.innerHTML='';

  cards.forEach(([label,value,sub,state])=>{
    const card=document.createElement('div');
    card.className='diag-card'+(state?` ${state}`:'');
    card.innerHTML=
      `<div class="diag-label">${diagEsc(label)}</div>`+
      `<div class="diag-value">${diagEsc(value)}</div>`+
      `<div class="diag-sub">${diagEsc(sub)}</div>`;
    systemHealthGrid.appendChild(card);
  });
}

async function sysInfo(){
  if(
    app.classList.contains('hidden')
    || document.getElementById('sys').classList.contains('hidden')
  ){
    return;
  }

  try{
    const system=await api('/api/system');
    renderSystemHealth(system);
  }catch(_){}
}

function validatePasswordChange(){
  const current=oldp.value;
  const first=newp.value;
  const second=confirmp.value;

  newp.classList.remove('password-valid','password-invalid');
  confirmp.classList.remove('password-valid','password-invalid');
  passwordStatus.className='muted';
  passwordStatus.textContent='';
  changePwdButton.disabled=true;

  if(!current && !first && !second){
    return false;
  }

  if(!current){
    passwordStatus.className='password-status-error';
    passwordStatus.textContent='Le mot de passe actuel est obligatoire.';
    return false;
  }

  if(!first || !second){
    passwordStatus.className='password-status-error';
    passwordStatus.textContent='Le nouveau mot de passe doit être saisi deux fois.';
    return false;
  }

  if(first.length<8){
    newp.classList.add('password-invalid');
    confirmp.classList.add('password-invalid');
    passwordStatus.className='password-status-error';
    passwordStatus.textContent='Le nouveau mot de passe doit contenir au moins 8 caractères.';
    return false;
  }

  if(first!==second){
    newp.classList.add('password-invalid');
    confirmp.classList.add('password-invalid');
    passwordStatus.className='password-status-error';
    passwordStatus.textContent='Les mots de passe ne correspondent pas.';
    return false;
  }

  newp.classList.add('password-valid');
  confirmp.classList.add('password-valid');
  passwordStatus.className='password-status-ok';
  passwordStatus.textContent='✔ Les mots de passe correspondent.';
  changePwdButton.disabled=false;
  return true;
}

async function changePwd(){
  if(!validatePasswordChange()){
    return;
  }

  const button=changePwdButton;
  button.disabled=true;
  button.innerHTML='<span class="spinner"></span>Modification…';

  try{
    await api('/api/change-password',{
      method:'POST',
      body:JSON.stringify({
        current_password:oldp.value,
        new_password:newp.value,
        confirm_password:confirmp.value
      })
    });

    oldp.value='';
    newp.value='';
    confirmp.value='';
    validatePasswordChange();
    toast('✔ Mot de passe modifié');
    setTimeout(showLogin,1200);

  }catch(error){
    toast(error.message,true);

  }finally{
    button.textContent='Modifier le mot de passe';
    validatePasswordChange();
  }
}

async function serviceStatus(){
  if(app.classList.contains('hidden'))return;
  try{
    let s=await api('/api/service-status');
    engine.className='engine '+(s.active?'running':'stopped');
    engineText.textContent=s.active?'PiDecoder en cours':'PiDecoder arrêté';
  }catch{}
}
async function exportConfig(){
  try{
    let r=await fetch('/api/export');
    if(r.status===401){showLogin();throw Error('Session expirée')}
    if(!r.ok)throw Error('Export impossible');
    let blob=await r.blob(),a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download='pidecoder-config-'+new Date().toISOString().slice(0,10)+'.json';
    document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(a.href);
    toast('✓ Configuration exportée');
  }catch(e){toast(e.message,true)}
}
async function importConfig(){
  let f=importFile.files[0];
  if(!f){toast('Sélectionne un fichier JSON',true);return}
  try{
    let data=JSON.parse(await f.text());
    await api('/api/import',{method:'POST',body:JSON.stringify(data)});
    toast('✓ Configuration importée');
    await loadCfg();
  }catch(e){toast(e.message,true)}
}

let onvifDevices=[];
async function discoverOnvif(){
  onvifStatus.textContent='Recherche ONVIF en cours…';
  onvifResults.innerHTML='';onvifDiagnostics.style.display='none';onvifDiagnostics.innerHTML='';
  try{
    let r=await api('/api/onvif/discover',{method:'POST',body:JSON.stringify({timeout:5})});
    onvifDevices=r.devices||[];let d=r.diagnostics||{};
    onvifStatus.textContent=onvifDevices.length+' équipement(s) ONVIF trouvé(s).';
    renderOnvifDiscovery();renderOnvifDiagnostics(d);
  }catch(e){onvifStatus.textContent='';toast(e.message,true)}
}
function ipv4FromCameraUrl(value){
  try{
    const parsed=new URL(value);
    return parsed.hostname||'';
  }catch(_){
    return '';
  }
}

function existingCameraFor(device){
  const info=device.identification?.information||{};
  const serial=String(info.SerialNumber||'');
  const xaddr=String(device.xaddr||'');
  const ip=String(device.ip||'');

  return (cfg.cameras||[]).find(camera=>{
    const metadata=camera.onvif||{};
    const legacyIp=
      String(metadata.ip||'') ||
      ipv4FromCameraUrl(camera.grid_url||'') ||
      ipv4FromCameraUrl(camera.focus_url||'');

    return (
      (serial && String(metadata.serial_number||'')===serial) ||
      (xaddr && String(metadata.device_xaddr||'')===xaddr) ||
      (ip && legacyIp===ip)
    );
  })||null;
}

function setIpv4Validation(){
  const input=manualOnvifIp;
  const value=input.value.trim();

  input.classList.remove('ip-valid','ip-invalid');

  if(!value){
    return;
  }

  input.classList.add(
    validIpv4(value)
      ? 'ip-valid'
      : 'ip-invalid'
  );
}

function rememberManualOnvif(){
  try{
    localStorage.setItem(
      'pidecoder.onvif.last_ipv4',
      manualOnvifIp.value.trim()
    );
    localStorage.setItem(
      'pidecoder.onvif.last_port',
      manualOnvifPort.value.trim()
    );
    localStorage.setItem(
      'pidecoder.onvif.last_path',
      manualOnvifPath.value.trim()
    );
  }catch(_){}
}

function restoreManualOnvif(){
  try{
    const ip=localStorage.getItem('pidecoder.onvif.last_ipv4');
    const port=localStorage.getItem('pidecoder.onvif.last_port');
    const path=localStorage.getItem('pidecoder.onvif.last_path');

    if(ip)manualOnvifIp.value=ip;
    if(port)manualOnvifPort.value=port;
    if(path)manualOnvifPath.value=path;
  }catch(_){}

  setIpv4Validation();
}

function validIpv4(value){
  const parts=String(value||'').trim().split('.');

  return (
    parts.length===4 &&
    parts.every(part=>{
      if(!/^\d{1,3}$/.test(part))return false;
      const number=Number(part);
      return number>=0 && number<=255 && String(number)===String(Number(part));
    })
  );
}

async function identifyManualOnvif(){
  const ip=manualOnvifIp.value.trim();
  const port=Number(manualOnvifPort.value||80);
  let path=manualOnvifPath.value.trim()||'/onvif/device_service';
  const button=manualOnvifButton;

  if(!validIpv4(ip)){
    toast('Adresse IPv4 invalide',true);
    return;
  }

  if(!Number.isInteger(port)||port<1||port>65535){
    toast('Port ONVIF invalide',true);
    return;
  }

  if(!path.startsWith('/')){
    path='/'+path;
  }

  const xaddr=`http://${ip}${port===80?'':':'+port}${path}`;

  let index=onvifDevices.findIndex(device=>
    String(device.ip||'')===ip
  );

  if(index<0){
    onvifDevices.unshift({
      ip,
      xaddr,
      xaddrs:[xaddr],
      name:`Caméra ${ip}`,
      hardware:'',
      location:'',
      scopes:'',
      manual:true
    });
    index=0;
  }else{
    onvifDevices[index].xaddr=xaddr;
    onvifDevices[index].xaddrs=Array.from(
      new Set([...(onvifDevices[index].xaddrs||[]),xaddr])
    );
  }

  renderOnvifDiscovery();

  const boxes=[...onvifResults.querySelectorAll('.onvif-card')];
  const box=boxes[index];

  if(!box){
    toast('Carte ONVIF introuvable',true);
    return;
  }

  rememberManualOnvif();

  button.disabled=true;
  button.innerHTML='<span class="spinner"></span>Identification…';

  try{
    await identifyOnvif(index,box);
  }finally{
    button.disabled=false;
    button.textContent='Identifier';
  }
}

function usableProfiles(profiles){
  const h264=profiles.filter(profile=>
    String(profile.encoding||'').toUpperCase()==='H264' &&
    profile.stream_uri
  );

  return h264.length
    ? h264
    : profiles.filter(profile=>profile.stream_uri);
}

function profileOption(profile){
  const codec=profile.encoding||'Codec ?';
  const resolution=profile.width&&profile.height
    ? `${profile.width} × ${profile.height}`
    : 'résolution ?';
  const fps=profile.fps ? `${profile.fps} fps` : 'fps ?';

  return `<option value="${esc(profile.token||'')}">${esc(profile.name||profile.token||'Profil')} · ${esc(codec)} · ${esc(resolution)} · ${esc(fps)}</option>`;
}

function renderOnvifDiscovery(){
  onvifResults.innerHTML='';

  if(!onvifDevices.length){
    onvifResults.innerHTML='<div class="onvif-card"><div class="muted">Aucun équipement découvert. Consulte les diagnostics ci-dessus.</div></div>';
    return;
  }

  onvifDevices.forEach((device,index)=>{
    const box=document.createElement('div');
    box.className='onvif-card';

    const identification=device.identification||null;
    const info=identification?.information||{};
    const profiles=usableProfiles(identification?.profiles||[]);
    const existing=existingCameraFor(device);

    const defaultName=existing?.name ||
      [info.Manufacturer,info.Model].filter(Boolean).join(' ') ||
      device.name || device.hardware || `Caméra ${device.ip||''}`;

    const options=profiles.map(profileOption).join('');
    const existingGrid=existing?.onvif?.grid_profile_token||existing?.onvif?.profile_token||'';
    const existingFocus=existing?.onvif?.focus_profile_token||existing?.onvif?.profile_token||'';

    const xaddrs=(device.xaddrs||[device.xaddr])
      .filter(Boolean)
      .map(value=>`<li>${esc(value)}</li>`)
      .join('');

    box.innerHTML=`
      <div class="row" style="justify-content:space-between">
        <div>
          <div class="onvif-title">${esc([info.Manufacturer,info.Model].filter(Boolean).join(' ')||device.name||device.hardware||'Équipement ONVIF')}</div>
          <div style="margin-top:7px">
            <span class="badge">ONVIF</span>
            <span class="badge">${esc(device.ip||'IP inconnue')}</span>
            ${identification?'<span class="badge ptz">Identifiée</span>':''}
            ${existing?'<span class="badge badge-configured">Déjà configurée</span>':'<span class="badge">Nouvelle</span>'}
          </div>
        </div>
        <button class="primary identify-onvif btn-fixed">${identification?'Réidentifier':'Identifier'}</button>
      </div>

      <div class="onvif-identification" style="margin-top:12px">
        ${identification?`
          <div class="grid">
            <div class="s4"><label>Fabricant</label><div>${esc(info.Manufacturer||'—')}</div></div>
            <div class="s4"><label>Modèle</label><div>${esc(info.Model||'—')}</div></div>
            <div class="s4"><label>Firmware</label><div>${esc(info.FirmwareVersion||'—')}</div></div>
            <div class="s6"><label>Numéro de série</label><div>${esc(info.SerialNumber||'—')}</div></div>
            <div class="s6"><label>Hardware ID</label><div>${esc(info.HardwareId||'—')}</div></div>
          </div>

          <div class="backupbox" style="margin-top:12px">
            <div class="grid">
              <div class="s12">
                <label>Nom dans PiDecoder</label>
                <input class="manager-name" value="${esc(defaultName)}">
              </div>
              <div class="s6">
                <label>Profil mosaïque</label>
                <select class="manager-grid-profile">${options}</select>
              </div>
              <div class="s6">
                <label>Profil plein écran</label>
                <select class="manager-focus-profile">${options}</select>
              </div>
            </div>

            <div class="row" style="margin-top:12px;justify-content:space-between">
              <div class="muted">${profiles.length?`${profiles.length} profil(s) H264/RTSP utilisable(s)`:'Aucun profil RTSP utilisable'}</div>
              <button class="${existing?'primary':'success'} manager-save btn-fixed" ${profiles.length?'':'disabled'}>
                ${existing?'Mettre à jour':'Ajouter à PiDecoder'}
              </button>
            </div>
          </div>

          <details style="margin-top:12px">
            <summary>Tous les profils détectés</summary>
            ${(identification.profiles||[]).map(profile=>`
              <div class="backupbox" style="padding:10px;margin-top:8px">
                <strong>${esc(profile.name||profile.token||'Profil')}</strong>
                <div class="muted">${esc(profile.encoding||'Codec ?')} · ${profile.width&&profile.height?esc(profile.width+' × '+profile.height):'résolution ?'} · ${profile.fps?esc(profile.fps)+' fps':'fps ?'}</div>
                <div class="muted">Token : ${esc(profile.token||'—')}</div>
              </div>`).join('')}
          </details>
        `:`
          <div class="muted">Matériel annoncé : ${esc(device.hardware||'—')}</div>
          <div class="muted">Emplacement : ${esc(device.location||'—')}</div>
        `}
      </div>

      <details style="margin-top:12px">
        <summary>Adresses ONVIF découvertes</summary>
        <ul style="word-break:break-all">${xaddrs||'<li>—</li>'}</ul>
      </details>`;

    box.querySelector('.identify-onvif').onclick=()=>identifyOnvif(index,box);

    if(identification && profiles.length){
      const gridSelect=box.querySelector('.manager-grid-profile');
      const focusSelect=box.querySelector('.manager-focus-profile');

      gridSelect.value=profiles.some(p=>p.token===existingGrid)
        ? existingGrid
        : profiles[profiles.length-1].token;

      focusSelect.value=profiles.some(p=>p.token===existingFocus)
        ? existingFocus
        : profiles[0].token;

      box.querySelector('.manager-save').onclick=()=>saveManagedCamera(index,box);
    }

    onvifResults.appendChild(box);
  });
}

async function saveManagedCamera(index,box){
  const device=onvifDevices[index];
  const identification=device.identification;

  if(!identification){
    toast('Identifie d’abord la caméra',true);
    return;
  }

  const button=box.querySelector('.manager-save');
  button.disabled=true;
  button.textContent='Enregistrement…';

  try{
    const result=await api('/api/onvif/manage-camera',{
      method:'POST',
      body:JSON.stringify({
        device_xaddr:device.xaddr,
        media_xaddr:identification.media_xaddr,
        grid_profile_token:box.querySelector('.manager-grid-profile').value,
        focus_profile_token:box.querySelector('.manager-focus-profile').value,
        name:box.querySelector('.manager-name').value,
        username:onvifUser.value,
        password:onvifPassword.value,
        ip:device.ip,
        information:identification.information||{}
      })
    });

    await loadCfg();
    renderOnvifDiscovery();
    toast('✔ '+(result.message||'Caméra enregistrée'));

  }catch(error){
    button.disabled=false;
    button.textContent=existingCameraFor(device)?'Mettre à jour':'Ajouter à PiDecoder';
    toast(error.message,true);
  }
}

async function identifyOnvif(index,box){
  let device=onvifDevices[index];
  let button=box.querySelector('.identify-onvif');
  let area=box.querySelector('.onvif-identification');

  button.disabled=true;
  button.innerHTML='<span class="spinner"></span>Identification…';
  area.innerHTML='<div class="muted">Connexion ONVIF en cours…</div>';

  try{
    let result=await api('/api/onvif/identify',{
      method:'POST',
      body:JSON.stringify({
        xaddr:device.xaddr,
        username:onvifUser.value,
        password:onvifPassword.value
      })
    });

    device.identification=result.device;
    renderOnvifDiscovery();
    toast('✔ Caméra identifiée');

  }catch(error){
    button.disabled=false;
    button.textContent='Identifier';
    area.innerHTML=
      '<div style="color:#ff7f89">'+
      esc(error.message)+
      '</div>'+
      '<div class="backupbox" style="margin-top:10px">'+
      '<strong>Log à transmettre :</strong>'+
      '<pre style="white-space:pre-wrap">sudo cat /tmp/pidecoder-onvif.log</pre>'+
      '</div>';
  }
}

function renderOnvifDiagnostics(d){
  onvifDiagnostics.style.display='block';
  let interfaces=(d.interfaces||[]).map(x=>`${esc(x.name)} (${esc(x.address)})`).join(', ')||'Aucune';
  let errors=(d.socket_errors||[]).map(x=>`<li>${esc(x)}</li>`).join('');
  let events=(d.events||[]).map(x=>`<li>${esc(x)}</li>`).join('');
  let types=Object.entries(d.message_types||{}).map(([n,c])=>`${esc(n)}: ${c}`).join(' · ')||'Aucun';
  let samples=(d.unknown_xml_samples||[]).map(s=>`<details style="margin-top:8px"><summary>${esc(s.message_type||'Unknown')} depuis ${esc(s.source_ip||'?')}</summary><pre style="white-space:pre-wrap;word-break:break-word">${esc((s.lines||[]).join('\n'))}</pre></details>`).join('');
  onvifDiagnostics.innerHTML=`<h3 style="margin-top:0">Diagnostics de découverte</h3><div><strong>Interfaces :</strong> ${interfaces}</div><div><strong>Probes envoyés :</strong> ${d.probes_sent||0}</div><div><strong>Paquets reçus :</strong> ${d.packets_received||0}</div><div><strong>Paquets XML :</strong> ${d.xml_packets||0}</div><div><strong>Types de messages :</strong> ${types}</div><div><strong>ProbeMatch trouvés :</strong> ${d.probe_matches||0}</div><div><strong>Erreurs XML :</strong> ${d.parse_errors||0}</div>${errors?`<h4>Erreurs socket</h4><ul>${errors}</ul>`:''}${samples?`<h4>Extraits XML inconnus</h4>${samples}`:''}<details style="margin-top:12px"><summary>Journal détaillé</summary><ul style="padding-left:20px">${events}</ul></details>`;
}
document.addEventListener('keydown',event=>{
  const target=event.target;
  const typing=target && (
    target.tagName==='INPUT' ||
    target.tagName==='TEXTAREA' ||
    target.tagName==='SELECT' ||
    target.isContentEditable
  );

  const history=document.getElementById('notificationHistory');
  const help=document.getElementById('shortcutHelp');

  if(event.key==='Escape'){
    const hadOpen=
      history.classList.contains('show') ||
      help.classList.contains('show');

    history.classList.remove('show');
    help.classList.remove('show');

    if(hadOpen){
      return;
    }
  }

  if(!app.classList.contains('hidden')){
    if(event.ctrlKey && event.key.toLowerCase()==='s'){
      event.preventDefault();
      save();
      return;
    }

    if(event.ctrlKey && event.key==='Enter'){
      event.preventDefault();
      apply();
      return;
    }

    if(event.altKey && !typing && /^[1-6]$/.test(event.key)){
      event.preventDefault();
      const tabs=[...document.querySelectorAll('.tab')];
      const index=Number(event.key)-1;

      if(tabs[index]){
        tabs[index].click();
      }
    }
  }
});

document.addEventListener('click',event=>{
  const history=document.getElementById('notificationHistory');
  const notificationButton=document.getElementById('notificationToggle');
  const help=document.getElementById('shortcutHelp');
  const shortcutButton=document.getElementById('shortcutButton');

  if(
    history.classList.contains('show') &&
    !history.contains(event.target) &&
    !notificationButton.contains(event.target)
  ){
    history.classList.remove('show');
  }

  if(
    help.classList.contains('show') &&
    !help.contains(event.target) &&
    !shortcutButton.contains(event.target)
  ){
    help.classList.remove('show');
  }
});

renderNotificationHistory();


let diagnosticsLastReport='';

function diagEsc(value){
  return esc(String(value??'—'));
}

function diagStatusClass(value){
  if(value===true || value==='active' || value==='ok'){
    return 'diag-ok';
  }

  if(value===false || value==='failed' || value==='inactive'){
    return 'diag-error';
  }

  return 'diag-warn';
}

function diagRow(label,value,className=''){
  return `<div class="diag-row"><span>${diagEsc(label)}</span><strong class="${className}">${diagEsc(value)}</strong></div>`;
}

function renderDiagnostics(data){
  const system=data.system||{};
  const cameras=data.cameras||{};
  const process=data.process||{};
  const services=data.services||{};

  renderSystemHealth(system);

  pidecoderInfo.innerHTML=
    diagRow('Version',data.version||'—')+
    diagRow('Release',data.release||'—')+
    diagRow('Architecture',system.architecture||'—')+
    diagRow('Kernel',system.kernel||'—')+
    diagRow('PID',process.pid??'—')+
    diagRow('FD ouverts',process.fd_count??'—')+
    diagRow('Décodage matériel',system.hardware_decode||'—');

  cameraInfo.innerHTML=
    diagRow('Configurées',cameras.total??0)+
    diagRow('Actives',cameras.enabled??0)+
    diagRow('Désactivées',cameras.disabled??0)+
    diagRow('Caméras ONVIF',cameras.onvif??0)+
    diagRow('Flux RTSP',cameras.configured_streams??0);

  const serviceItems=[
    ['PiDecoder',services.pidecoder||'inconnu'],
    ['Administration Web',services.web||'inconnu'],
    ['Décodage matériel',system.hardware_decode||'inconnu'],
  ];

  serviceBadges.innerHTML='';

  serviceItems.forEach(([label,value])=>{
    const ok=value==='active'||value==='détecté';
    const warning=value==='indisponible'||value==='non déterminé'||value==='inconnu';
    const badge=document.createElement('div');
    badge.className='service-badge';
    badge.innerHTML=
      `<span class="status-dot ${ok?'status-ok':warning?'status-warn':'status-error'}"></span>`+
      `<span><strong>${diagEsc(label)}</strong><small>${diagEsc(value)}</small></span>`;
    serviceBadges.appendChild(badge);
  });

  diagnosticsLogs.textContent=data.logs||'Aucun journal disponible.';
  diagnosticsLastReport=data.report||'';
  updateGlobalHealth(data);
}

function updateGlobalHealth(data){
  const system=data.system||{};
  const services=data.services||{};
  const cameras=data.cameras||{};

  let state='Stable';
  let className='ok';

  if(services.pidecoder!=='active'||services.web!=='active'){
    state='Erreur';
    className='error';
  }else if(
    system.throttled_hex!=='0x0' ||
    (system.temperature_c!=null && system.temperature_c>=80) ||
    (cameras.enabled??0)<(cameras.total??0)
  ){
    state='Attention';
    className='warn';
  }

  engineText.textContent=state;
  globalHealthDot.className='dot '+className;
}

async function refreshDiagnostics(){
  diagnosticsLogs.textContent='Chargement…';

  try{
    const lines=Number(diagnosticLogLines?.value||50);const data=await api(`/api/diagnostics?lines=${lines}`);
    renderDiagnostics(data);
    toast('✔ Diagnostics actualisés');
  }catch(error){
    diagnosticsLogs.textContent=error.message;
    toast(error.message,true);
  }
}

async function copyDiagnostics(){
  if(!diagnosticsLastReport){
    await refreshDiagnostics();
  }

  try{
    await navigator.clipboard.writeText(diagnosticsLastReport);
    toast('✔ Rapport copié');
  }catch(_){
    diagnosticsCopyBuffer.classList.remove('hidden');
    diagnosticsCopyBuffer.value=diagnosticsLastReport;
    diagnosticsCopyBuffer.select();
    document.execCommand('copy');
    diagnosticsCopyBuffer.classList.add('hidden');
    toast('✔ Rapport copié');
  }
}

oldp.addEventListener('input',validatePasswordChange);
newp.addEventListener('input',validatePasswordChange);
confirmp.addEventListener('input',validatePasswordChange);

cols.addEventListener('input',mosaicSettingsChanged);
rows.addEventListener('input',mosaicSettingsChanged);
fs.addEventListener('change',scheduleMosaicSave);

manualOnvifIp.addEventListener('input',setIpv4Validation);
manualOnvifPort.addEventListener('change',rememberManualOnvif);
manualOnvifPath.addEventListener('change',rememberManualOnvif);
restoreManualOnvif();

setInterval(serviceStatus,3000);serviceStatus();
setInterval(sysInfo,3000);boot().catch(e=>{toast(e.message,true);showLogin()});
</script></body></html>'''


def rotate_camera_backups(root, source, keep=5):
    backup_dir = root / 'config' / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)

    if source.exists():
        stamp = time.strftime('%Y%m%d-%H%M%S')
        shutil.copy2(
            source,
            backup_dir / f'cameras.json.{stamp}.bak',
        )

    backups = sorted(
        backup_dir.glob('cameras.json.*.bak'),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    for old in backups[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def camera_onvif_identity(metadata):
    if not isinstance(metadata, dict):
        return ('', '', '')

    return (
        str(metadata.get('serial_number', '')).strip(),
        str(metadata.get('device_xaddr', '')).strip(),
        str(metadata.get('ip', '')).strip(),
    )


def ipv4_from_url(value):
    try:
        host = urlsplit(str(value or '')).hostname or ''
        address = ipaddress.ip_address(host)
    except (ValueError, TypeError):
        return ''

    return host if address.version == 4 else ''


def camera_known_ipv4(camera):
    if not isinstance(camera, dict):
        return ''

    metadata = camera.get('onvif', {})
    _, _, metadata_ip = camera_onvif_identity(metadata)

    try:
        if metadata_ip and ipaddress.ip_address(metadata_ip).version == 4:
            return metadata_ip
    except ValueError:
        pass

    return (
        ipv4_from_url(camera.get('grid_url', ''))
        or ipv4_from_url(camera.get('focus_url', ''))
    )


def matching_onvif_camera_indexes(
    cameras,
    serial_number,
    device_xaddr,
    ip,
    grid_uri='',
    focus_uri='',
):
    matches = []

    for index, camera in enumerate(cameras):
        if not isinstance(camera, dict):
            continue

        metadata = camera.get('onvif', {})
        current_serial, current_xaddr, _ = camera_onvif_identity(metadata)
        current_ip = camera_known_ipv4(camera)

        same_serial = bool(
            serial_number
            and current_serial
            and current_serial == serial_number
        )

        same_xaddr = bool(
            device_xaddr
            and current_xaddr
            and current_xaddr == device_xaddr
        )

        same_ip = bool(
            ip
            and current_ip
            and current_ip == ip
        )

        same_stream = bool(
            (grid_uri and camera.get('grid_url') == grid_uri)
            or (focus_uri and camera.get('focus_url') == focus_uri)
        )

        if same_serial or same_xaddr or same_ip or same_stream:
            matches.append(index)

    return matches


def find_onvif_camera(
    cameras,
    serial_number,
    device_xaddr,
    ip,
    grid_uri='',
    focus_uri='',
):
    matches = matching_onvif_camera_indexes(
        cameras,
        serial_number,
        device_xaddr,
        ip,
        grid_uri,
        focus_uri,
    )

    return matches[0] if matches else None


def read_text(path, default=''):
    try:
        return Path(path).read_text(
            encoding='utf-8',
            errors='replace'
        ).strip()
    except OSError:
        return default


def command_output(command, timeout=4):
    try:
        result=subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.stdout.strip()
    except (
        OSError,
        subprocess.TimeoutExpired,
    ) as error:
        return str(error)


def service_state(name):
    value=command_output(
        ['systemctl','is-active',name],
        timeout=3,
    ).strip()

    return value or 'inconnu'


def human_bytes(value):
    try:
        value=float(value)
    except (TypeError,ValueError):
        return '—'

    units=['B','KiB','MiB','GiB','TiB']
    index=0

    while value>=1024 and index<len(units)-1:
        value/=1024
        index+=1

    return f'{value:.1f} {units[index]}'


def system_uptime_seconds():
    try:
        return float(
            read_text('/proc/uptime','0').split()[0]
        )
    except (ValueError,IndexError):
        return 0.0


def human_duration(seconds):
    seconds=max(0,int(seconds))
    days,remainder=divmod(seconds,86400)
    hours,remainder=divmod(remainder,3600)
    minutes,_=divmod(remainder,60)

    parts=[]

    if days:
        parts.append(f'{days} j')

    if hours or days:
        parts.append(f'{hours} h')

    parts.append(f'{minutes} min')
    return ' '.join(parts)


def cpu_times():
    fields=read_text('/proc/stat','').splitlines()

    if not fields:
        return (0,0)

    parts=fields[0].split()[1:]

    try:
        values=[int(value) for value in parts]
    except ValueError:
        return (0,0)

    idle=values[3] + (values[4] if len(values)>4 else 0)
    total=sum(values)
    return (idle,total)


def cpu_percent_sample():
    idle_a,total_a=cpu_times()
    time.sleep(0.12)
    idle_b,total_b=cpu_times()

    total_delta=total_b-total_a
    idle_delta=idle_b-idle_a

    if total_delta<=0:
        return 0.0

    return round(
        max(0.0,min(100.0,100.0-(idle_delta/total_delta*100.0))),
        1,
    )


def memory_info():
    values={}

    for line in read_text('/proc/meminfo','').splitlines():
        if ':' not in line:
            continue

        key,value=line.split(':',1)
        token=value.strip().split()[0]

        try:
            values[key]=int(token)*1024
        except ValueError:
            continue

    total=values.get('MemTotal',0)
    available=values.get('MemAvailable',0)
    used=max(0,total-available)
    percent=round((used/total)*100,1) if total else 0

    return {
        'total':total,
        'used':used,
        'available':available,
        'percent':percent,
    }


def cpu_temperature():
    candidates=[
        '/sys/class/thermal/thermal_zone0/temp',
        '/sys/class/hwmon/hwmon0/temp1_input',
    ]

    for candidate in candidates:
        raw=read_text(candidate,'')

        if not raw:
            continue

        try:
            value=float(raw)

            if value>1000:
                value/=1000

            return round(value,1)
        except ValueError:
            continue

    output=command_output(
        ['vcgencmd','measure_temp'],
        timeout=2,
    )

    match=re.search(r'([0-9]+(?:\.[0-9]+)?)',output)

    return float(match.group(1)) if match else None


def throttling_info():
    output=command_output(
        ['vcgencmd','get_throttled'],
        timeout=2,
    )

    match=re.search(r'(0x[0-9a-fA-F]+)',output)
    value=match.group(1).lower() if match else 'indisponible'

    return {
        'hex':value,
        'label':(
            'aucun'
            if value=='0x0'
            else (
                'indisponible'
                if value=='indisponible'
                else f'alerte {value}'
            )
        ),
    }


def process_fd_count(pid):
    try:
        return len(
            list(
                Path(f'/proc/{pid}/fd').iterdir()
            )
        )
    except OSError:
        return None


def file_status(path):
    path=Path(path)

    if not path.exists():
        return 'absent'

    try:
        modified=time.strftime(
            '%Y-%m-%d %H:%M:%S',
            time.localtime(path.stat().st_mtime),
        )
        return f'présent · {modified}'
    except OSError:
        return 'présent'


def diagnostics_payload(root, log_lines=50):
    cameras_path=root/'config/cameras.json'
    layout_path=root/'config/layout.json'
    cameras_document=load(cameras_path,{'cameras':[]})
    layout=load(layout_path,{})
    cameras=cameras_document.get('cameras',[])

    if not isinstance(cameras,list):
        cameras=[]

    enabled=[
        camera
        for camera in cameras
        if isinstance(camera,dict)
        and camera.get('enabled',True)
    ]

    configured_streams=0
    onvif_count=0

    for camera in enabled:
        if camera.get('grid_url'):
            configured_streams+=1

        if camera.get('focus_url'):
            configured_streams+=1

        metadata=camera.get('onvif')

        if (
            isinstance(metadata,dict)
            and (
                metadata.get('device_xaddr')
                or metadata.get('media_xaddr')
                or metadata.get('serial_number')
                or metadata.get('grid_profile_token')
                or metadata.get('focus_profile_token')
                or metadata.get('profile_token')
            )
        ):
            onvif_count+=1
        elif (
            '/onvif-media/' in str(camera.get('grid_url',''))
            or '/onvif-media/' in str(camera.get('focus_url',''))
            or '/onvif/' in str(camera.get('grid_url',''))
            or '/onvif/' in str(camera.get('focus_url',''))
        ):
            onvif_count+=1

    uptime=system_uptime_seconds()
    boot_timestamp=time.time()-uptime
    memory=memory_info()
    throttled=throttling_info()
    pid=os.getpid()

    try:
        load_average=' / '.join(
            f'{value:.2f}'
            for value in os.getloadavg()
        )
    except OSError:
        load_average='indisponible'

    hardware_decode=(
        'détecté'
        if (
            Path('/dev/dri').exists()
            or Path('/dev/video10').exists()
        )
        else 'non détecté'
    )

    journal_parts=[]

    for service in (
        'pidecoder.service',
        'pidecoder-config.service',
    ):
        journal_parts.append(
            f'===== {service} ====='
        )
        journal_parts.append(
            command_output(
                [
                    'journalctl',
                    '-u',
                    service,
                    '-n',
                    str(log_lines),
                    '--no-pager',
                    '--output=short-iso',
                ],
                timeout=6,
            ) or 'Aucune ligne.'
        )

    logs='\n'.join(journal_parts)
    uptime_human=human_duration(uptime)
    temperature=cpu_temperature()

    payload={
        'ok':True,
        'version':'0.9.9.4 RC1',
        'release':'Release Candidate',
        'system':{
            'hostname':platform.node(),
            'kernel':platform.release(),
            'architecture':platform.machine(),
            'uptime_seconds':int(uptime),
            'uptime_human':uptime_human,
            'boot_time':time.strftime(
                '%Y-%m-%d %H:%M:%S',
                time.localtime(boot_timestamp),
            ),
            'temperature_c':temperature,
            'cpu_percent':cpu_percent_sample(),
            'load_average':load_average,
            'cpu_count':os.cpu_count(),
            'memory_total_human':human_bytes(memory['total']),
            'memory_used_human':human_bytes(memory['used']),
            'memory_available_human':human_bytes(memory['available']),
            'memory_percent':memory['percent'],
            'throttled_hex':throttled['hex'],
            'throttled_label':throttled['label'],
            'hardware_decode':hardware_decode,
        },
        'process':{
            'pid':pid,
            'fd_count':process_fd_count(pid),
        },
        'services':{
            'pidecoder':service_state('pidecoder.service'),
            'web':service_state('pidecoder-config.service'),
        },
        'cameras':{
            'total':len(cameras),
            'enabled':len(enabled),
            'disabled':len(cameras)-len(enabled),
            'configured_streams':configured_streams,
            'onvif':onvif_count,
        },
        'layout':{
            'columns':layout.get('columns',3),
            'rows':layout.get('rows',3),
            'fullscreen_on_start':bool(
                layout.get(
                    'fullscreen_on_start',
                    False,
                )
            ),
            'placements':len(
                layout.get('placements',[])
                if isinstance(
                    layout.get('placements',[]),
                    list,
                )
                else []
            ),
        },
        'files':{
            'cameras':file_status(cameras_path),
            'layout':file_status(layout_path),
        },
        'logs':logs,
    }

    report_lines=[
        'PiDecoder Diagnostics',
        '=====================',
        f"Version: {payload['version']}",
        f"Hôte: {payload['system']['hostname']}",
        f"Kernel: {payload['system']['kernel']}",
        f"Architecture: {payload['system']['architecture']}",
        f"Uptime: {uptime_human}",
        f"Température CPU: {temperature if temperature is not None else 'indisponible'}",
        f"Throttling: {payload['system']['throttled_label']}",
        f"Charge: {load_average}",
        f"Mémoire utilisée: {payload['system']['memory_used_human']} ({memory['percent']} %)",
        f"Service PiDecoder: {payload['services']['pidecoder']}",
        f"Service Web: {payload['services']['web']}",
        f"Caméras: {len(enabled)}/{len(cameras)} actives",
        f"Flux configurés: {configured_streams}",
        f"FD administration Web: {payload['process']['fd_count']}",
        '',
        'Journaux',
        '========',
        logs,
    ]

    payload['report']='\n'.join(report_lines)
    return payload


class Server(ThreadingHTTPServer): root:Path; auth:Path
class H(BaseHTTPRequestHandler):
    def j(self,data,status=200,cookie=None):
        raw=json.dumps(
            data,
            ensure_ascii=False,
            default=str,
        ).encode()
        self.send_response(status)
        self.send_header(
            'Content-Type',
            'application/json;charset=utf-8',
        )
        self.send_header(
            'Content-Length',
            str(len(raw)),
        )
        self.send_header(
            'Cache-Control',
            'no-store',
        )
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers(); self.wfile.write(raw)
    def html(self):
        raw=HTML.encode(); self.send_response(200); self.send_header('Content-Type','text/html;charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def body(self): return json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))).decode())
    def authdoc(self): return load(self.server.auth,{})
    def token(self):
        c=SimpleCookie(); c.load(self.headers.get('Cookie','')); m=c.get('pidecoder_session'); return m.value if m else None
    def authed(self):
        t=self.token(); now=time.time()
        if not t:return False
        with LOCK:
            if SESSIONS.get(t,0)<now: SESSIONS.pop(t,None); return False
            SESSIONS[t]=now+43200
        return True
    def need(self):
        if self.authed():return True
        self.j({'ok':False,'error':'Authentification requise'},401);return False
    def do_GET(self):
        p=urlparse(self.path).path
        if p=='/':return self.html()
        if p=='/api/session':return self.j({'authenticated':self.authed(),'version':VERSION})
        if not self.need():return
        if p=='/api/config':
            cams=load(self.server.root/'config/cameras.json',{'cameras':[]}).get('cameras',[]); lay=normalize_layout(load(self.server.root/'config/layout.json',{}),len(cams)); return self.j({'cameras':cams,'layout':lay})
        if p=='/api/diagnostics':
            try:
                query=parse_qs(
                    urlparse(self.path).query
                )

                try:
                    log_lines=int(
                        query.get('lines',['50'])[0]
                    )
                except (TypeError,ValueError):
                    log_lines=50

                log_lines=max(20,min(100,log_lines))

                payload=diagnostics_payload(
                    self.server.root,
                    log_lines,
                )
                return self.j(payload)
            except Exception as error:
                return self.j(
                    {
                        'ok':False,
                        'error':(
                            'Impossible de générer les diagnostics : '
                            + str(error)
                        ),
                    },
                    500,
                )
        if p=='/api/system':return self.j(system_info())
        if p=='/api/service-status':
            active=subprocess.run(['systemctl','is-active','--quiet','pidecoder.service'],check=False).returncode==0
            enabled=subprocess.run(['systemctl','is-enabled','--quiet','pidecoder.service'],check=False).returncode==0
            return self.j({'active':active,'enabled':enabled})
        if p=='/api/export':
            cams=load(self.server.root/'config/cameras.json',{'cameras':[]})
            lay=load(self.server.root/'config/layout.json',{})
            raw=json.dumps({'format':'pidecoder-config','version':VERSION,'exported_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'cameras':cams.get('cameras',[]),'layout':lay},indent=2,ensure_ascii=False).encode('utf-8')
            self.send_response(200);self.send_header('Content-Type','application/json;charset=utf-8');self.send_header('Content-Disposition','attachment; filename=pidecoder-config.json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        self.send_error(404)
    def do_POST(self):
        p=urlparse(self.path).path
        try:
            if p=='/api/login':
                d=self.body();a=self.authdoc()
                if not(hmac.compare_digest(str(d.get('username','')),str(a.get('username',''))) and verify(str(d.get('password','')),a)):return self.j({'ok':False,'error':'Mot de passe incorrect'},401)
                t=secrets.token_urlsafe(32)
                with LOCK:SESSIONS[t]=time.time()+43200
                return self.j({'ok':True},cookie=f'pidecoder_session={t}; HttpOnly; SameSite=Strict; Path=/')
            if p=='/api/logout':
                with LOCK:SESSIONS.pop(self.token(),None)
                return self.j({'ok':True})
            if not self.need():return
            if p=='/api/onvif/discover':
                d=self.body();result=discover(float(d.get('timeout',5)))
                return self.j({'ok':True,'devices':result.get('devices',[]),'diagnostics':result.get('diagnostics',{})})
            if p=='/api/onvif/identify':
                d=self.body()
                device=identify_device(
                    str(d.get('xaddr','')),
                    str(d.get('username','')),
                    str(d.get('password',''))
                )
                return self.j({'ok':True,'device':device})
            if p=='/api/onvif/manage-camera':
                d=self.body()
                media_xaddr=str(d.get('media_xaddr','')).strip()
                grid_token=str(d.get('grid_profile_token','')).strip()
                focus_token=str(d.get('focus_profile_token','')).strip()
                username=str(d.get('username',''))
                password=str(d.get('password',''))
                device_xaddr=str(d.get('device_xaddr','')).strip()
                ip=str(d.get('ip','')).strip()
                information=d.get('information',{}) if isinstance(d.get('information'),dict) else {}

                if not media_xaddr or not grid_token or not focus_token:
                    raise ValueError('Service Media ou profil mosaïque/plein écran absent')

                credentials=Credentials(username,password)
                grid_uri=rtsp_with_credentials(
                    get_stream_uri(media_xaddr,grid_token,credentials),
                    username,
                    password,
                )
                focus_uri=rtsp_with_credentials(
                    get_stream_uri(media_xaddr,focus_token,credentials),
                    username,
                    password,
                )

                manufacturer=str(information.get('Manufacturer','')).strip()
                model=str(information.get('Model','')).strip()
                serial_number=str(information.get('SerialNumber','')).strip()
                hardware_id=str(information.get('HardwareId','')).strip()

                requested_name=str(d.get('name','')).strip()
                fallback_name=' '.join(
                    value for value in (manufacturer,model) if value
                ).strip() or f'Caméra ONVIF {ip}'.strip()
                name=requested_name or fallback_name

                cp=self.server.root/'config/cameras.json'
                document=load(cp,{'cameras':[]})
                cameras=document.get('cameras',[])
                if not isinstance(cameras,list):
                    cameras=[]

                matching_indexes=matching_onvif_camera_indexes(
                    cameras,
                    serial_number,
                    device_xaddr,
                    ip,
                    grid_uri,
                    focus_uri,
                )
                existing_index=matching_indexes[0] if matching_indexes else None

                camera={
                    'name':name,
                    'enabled':True,
                    'grid_url':grid_uri,
                    'focus_url':focus_uri,
                    'onvif':{
                        'device_xaddr':device_xaddr,
                        'media_xaddr':media_xaddr,
                        'ip':ip,
                        'grid_profile_token':grid_token,
                        'focus_profile_token':focus_token,
                        'manufacturer':manufacturer,
                        'model':model,
                        'serial_number':serial_number,
                        'hardware_id':hardware_id,
                    },
                }

                rotate_camera_backups(self.server.root,cp,keep=5)

                removed_duplicates=0

                if existing_index is None:
                    cameras.append(sanitize(camera))
                    action='ajoutée'
                else:
                    previous=cameras[existing_index]

                    if isinstance(previous,dict):
                        camera['enabled']=bool(previous.get('enabled',True))

                    cameras[existing_index]=sanitize(camera)

                    for duplicate_index in sorted(
                        matching_indexes[1:],
                        reverse=True,
                    ):
                        if duplicate_index == existing_index:
                            continue

                        del cameras[duplicate_index]
                        removed_duplicates += 1

                    action='mise à jour'

                write_json(cp,{'cameras':cameras})

                lp=self.server.root/'config/layout.json'
                write_json(
                    lp,
                    normalize_layout(load(lp,{}),len(cameras)),
                )

                return self.j({
                    'ok':True,
                    'updated':existing_index is not None,
                    'message':(
                        f'{name} {action}. '
                        + (
                            f'{removed_duplicates} doublon(s) supprimé(s). '
                            if removed_duplicates
                            else ''
                        )
                        + 'Clique sur Appliquer pour charger les flux.'
                    ),
                    'removed_duplicates':removed_duplicates,
                    'camera':camera,
                })
            if p=='/api/onvif/inspect':
                d=self.body();device=inspect_device(str(d.get('xaddr','')),str(d.get('username','')),str(d.get('password','')));return self.j({'ok':True,'device':device})
            if p=='/api/onvif/ptz':
                d=self.body();creds=Credentials(str(d.get('username','')),str(d.get('password','')));action=str(d.get('action','stop'));xaddr=str(d.get('ptz_xaddr',''));token=str(d.get('profile_token',''));moves={'up':(0,0.5,0),'down':(0,-0.5,0),'left':(-0.5,0,0),'right':(0.5,0,0),'zoomin':(0,0,0.5),'zoomout':(0,0,-0.5)}
                if action=='stop':stop(xaddr,token,creds)
                elif action in moves:continuous_move(xaddr,token,creds,*moves[action])
                else:raise ValueError('Commande PTZ inconnue')
                return self.j({'ok':True})
            if p=='/api/onvif/preset':
                d=self.body();goto_preset(str(d.get('ptz_xaddr','')),str(d.get('profile_token','')),str(d.get('preset_token','')),Credentials(str(d.get('username','')),str(d.get('password',''))));return self.j({'ok':True})
            if p=='/api/config':
                d=self.body();cams=[sanitize(c) for c in d.get('cameras',[]) if isinstance(c,dict)]
                if not cams:raise ValueError('Au moins une caméra est nécessaire')
                b=self.server.root/'config/backups';b.mkdir(parents=True,exist_ok=True)
                cp=self.server.root/'config/cameras.json';lp=self.server.root/'config/layout.json'
                if cp.exists():shutil.copy2(cp,b/'cameras.json.previous')
                if lp.exists():shutil.copy2(lp,b/'layout.json.previous')
                write_json(cp,{'cameras':cams});write_json(lp,normalize_layout(d.get('layout',{}),len(cams)));return self.j({'ok':True})
            if p=='/api/apply':
                exists=subprocess.run(['systemctl','cat','pidecoder.service'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
                if not exists:return self.j({'ok':True,'applied':False,'message':'Configuration sauvegardée. Le moteur PiDecoder doit être redémarré manuellement.'})
                r=subprocess.run(['systemctl','restart','pidecoder.service'],capture_output=True,text=True,timeout=15)
                if r.returncode:raise RuntimeError(r.stderr.strip() or 'Échec du redémarrage')
                return self.j({'ok':True,'applied':True,'message':'Configuration appliquée. PiDecoder a redémarré.'})
            if p=='/api/import':
                d=self.body()
                if d.get('format')!='pidecoder-config':raise ValueError('Fichier PiDecoder invalide')
                cams=[sanitize(c) for c in d.get('cameras',[]) if isinstance(c,dict)]
                if not cams:raise ValueError('Le fichier ne contient aucune caméra valide')
                lay=normalize_layout(d.get('layout',{}),len(cams))
                b=self.server.root/'config/backups';b.mkdir(parents=True,exist_ok=True)
                stamp=time.strftime('%Y%m%d-%H%M%S')
                cp=self.server.root/'config/cameras.json';lp=self.server.root/'config/layout.json'
                if cp.exists():shutil.copy2(cp,b/f'cameras.json.before-import-{stamp}')
                if lp.exists():shutil.copy2(lp,b/f'layout.json.before-import-{stamp}')
                write_json(cp,{'cameras':cams});write_json(lp,lay)
                return self.j({'ok':True,'message':'Configuration importée'})
            if p=='/api/change-password':
                d=self.body();a=self.authdoc()
                current=str(d.get('current_password',''))
                new_password=str(d.get('new_password',''))
                confirmation=str(d.get('confirm_password',''))

                if not verify(current,a):
                    raise ValueError('Mot de passe actuel incorrect')

                if not new_password or not confirmation:
                    raise ValueError(
                        'Le nouveau mot de passe doit être saisi deux fois'
                    )

                if len(new_password)<8:
                    raise ValueError(
                        'Le nouveau mot de passe doit contenir au moins 8 caractères'
                    )

                if new_password!=confirmation:
                    raise ValueError(
                        'Les mots de passe ne correspondent pas'
                    )

                set_auth(
                    self.server.auth,
                    str(a.get('username','admin')),
                    new_password
                )

                with LOCK:
                    SESSIONS.clear()

                return self.j({
                    'ok':True,
                    'message':'Mot de passe modifié'
                })
            self.send_error(404)
        except ValueError as e:self.j({'ok':False,'error':str(e)},400)
        except Exception as e:self.j({'ok':False,'error':'Erreur serveur : '+str(e)},500)
    def log_message(self,fmt,*args):print('[config-web] '+fmt%args)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',default=str(ROOT));ap.add_argument('--bind',default='0.0.0.0');ap.add_argument('--port',type=int,default=8080);ap.add_argument('--set-password',action='store_true');ap.add_argument('--username',default='admin');a=ap.parse_args();root=Path(a.root);auth=root/'config/web-auth.json'
    if a.set_password:
        p=getpass.getpass('Nouveau mot de passe : ');q=getpass.getpass('Confirmation : ')
        if p!=q:raise SystemExit('Les mots de passe ne correspondent pas')
        set_auth(auth,a.username,p);print('Identifiants Web mis à jour.');return
    if not auth.exists():raise SystemExit('Authentification non initialisée. Utiliser --set-password.')
    s=Server((a.bind,a.port),H);s.root=root;s.auth=auth;print(f'PiDecoder Config v{VERSION} : http://{a.bind}:{a.port}')
    try:s.serve_forever()
    except KeyboardInterrupt:pass

if __name__=='__main__':main()
