#!/usr/bin/env python3
from __future__ import annotations

import argparse, base64, hashlib, hmac, ipaddress, json, os, platform, pwd, re, secrets, shutil, subprocess, tempfile, threading, time, getpass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse, urlsplit, urlunsplit
from onvif_client import Credentials, PTZ_MOVES, continuous_move, credentials_for_ptz_camera, discover, find_ptz_camera, goto_preset, get_stream_uri, identify_device, inspect_device, stop
from i18n import DEFAULT_LANG, SUPPORTED_LANGS, lang_from_cookie_header, t as i18n_t

VERSION='1.0.0'; ROOT=Path('/opt/pidecoder'); SESSIONS={}; LOCK=threading.Lock(); CPU_PREV=None

# Anti-bruteforce sur /api/login : au-delà de LOGIN_MAX_ATTEMPTS échecs pour une
# même adresse IP en LOGIN_WINDOW secondes, l'IP est bloquée LOGIN_LOCKOUT
# secondes. État en mémoire seulement (remis à zéro au redémarrage du service),
# suffisant pour une interface d'administration destinée à rester sur un réseau
# de confiance (voir l'avertissement HTTP dans docs/installation.md).
LOGIN_ATTEMPTS={}
LOGIN_MAX_ATTEMPTS=5
LOGIN_WINDOW=300
LOGIN_LOCKOUT=300

def login_blocked(ip):
    with LOCK:
        _,locked_until=LOGIN_ATTEMPTS.get(ip,([],0))
        return bool(locked_until) and locked_until>time.time()

def register_login_failure(ip):
    now=time.time()
    with LOCK:
        attempts,_=LOGIN_ATTEMPTS.get(ip,([],0))
        attempts=[t for t in attempts if now-t<LOGIN_WINDOW]
        attempts.append(now)
        locked_until=now+LOGIN_LOCKOUT if len(attempts)>=LOGIN_MAX_ATTEMPTS else 0
        LOGIN_ATTEMPTS[ip]=([] if locked_until else attempts,locked_until)

def clear_login_failures(ip):
    with LOCK:
        LOGIN_ATTEMPTS.pop(ip,None)

WEB_DIR=Path(__file__).resolve().parent/'web'
STATIC_FILES={
    '/':('index.html','text/html;charset=utf-8'),
    '/app.js':('app.js','application/javascript;charset=utf-8'),
    '/app.css':('app.css','text/css;charset=utf-8'),
    '/i18n.js':('i18n.js','application/javascript;charset=utf-8'),
}

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
        # Comme fullscreen_on_start : réglage global (pas par caméra), décoché
        # par défaut. Décide si Player démarre le son actif dès l'ouverture du
        # focus, pour les caméras qui ont la case "audio_enabled" cochée (voir
        # CameraConfig::audio_enabled côté moteur natif) — sans effet sur les
        # autres caméras.
        'focus_audio_default_on':bool(
            x.get('focus_audio_default_on',False)
        ),
        'camera_order':order,
        'placements':placements,
    }

def credentials_for_ptz_request(root, d, ptz_xaddr, profile_token):
    """Réutilise les identifiants déjà enregistrés pour une caméra PTZ
    connue de la configuration (dérivés de son URL RTSP stockée), pour
    éviter qu'ils ne transitent depuis le navigateur à chaque mouvement.
    Si la caméra n'est pas encore enregistrée (test PTZ pendant la
    configuration initiale, avant de cliquer sur "Enregistrer"), on
    retombe sur les identifiants transmis par le formulaire, seule
    source disponible à ce stade."""
    try:
        document = load(root / 'config/cameras.json', {'cameras': []})
        camera, _ = find_ptz_camera(
            document.get('cameras', []),
            ptz_xaddr,
            profile_token,
        )
        return credentials_for_ptz_camera(camera)
    except ValueError:
        return Credentials(str(d.get('username', '')), str(d.get('password', '')))

def rtsp_with_credentials(uri, username, password, lang=DEFAULT_LANG):
    parsed = urlsplit(str(uri).strip())

    if parsed.scheme.lower() != 'rtsp' or not parsed.hostname:
        raise ValueError(i18n_t('onvif.rtsp_uri_invalid', lang))

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


def sanitize(c,lang=DEFAULT_LANG):
    name=str(c.get('name','Caméra')).strip() or 'Caméra'; g=str(c.get('grid_url','')).strip(); f=str(c.get('focus_url','')).strip() or g
    if not g: raise ValueError(i18n_t('camera.grid_url_missing',lang,name=name))
    # audio_enabled : case "cette caméra a un micro" côté config Web, décochée par
    # défaut (False) pour toute caméra nouvellement ajoutée. Voir CameraConfig::audio_enabled
    # côté moteur natif pour ce que ce réglage déclenche (réglages mosaïque assouplis +
    # affichage du bouton son en Focus).
    result={'name':name,'enabled':bool(c.get('enabled',True)),'audio_enabled':bool(c.get('audio_enabled',False)),'grid_url':g,'focus_url':f}
    if isinstance(c.get('onvif'),dict):result['onvif']=c['onvif']
    return result


def camera_rtsp_host(camera):
    if not isinstance(camera,dict):
        return ''

    for field in ('focus_url','grid_url'):
        try:
            host=urlsplit(str(camera.get(field,'')).strip()).hostname
        except (TypeError,ValueError):
            host=None

        if host:
            return str(host).strip().lower()

    return ''


def merge_existing_onvif(cameras,existing):
    if not isinstance(existing,list):
        return cameras

    for camera in cameras:
        host=camera_rtsp_host(camera)

        if not host:
            continue

        candidates=[]

        for previous in existing:
            if not isinstance(previous,dict):
                continue

            metadata=previous.get('onvif')

            if not isinstance(metadata,dict):
                continue

            previous_host=str(metadata.get('ip','')).strip().lower()

            if not previous_host:
                previous_host=camera_rtsp_host(previous)

            if previous_host==host:
                candidates.append(previous)

        if len(candidates)>1:
            name=str(camera.get('name','')).strip().casefold()
            same_name=[
                previous
                for previous in candidates
                if str(previous.get('name','')).strip().casefold()==name
            ]

            if len(same_name)==1:
                candidates=same_name

        if len(candidates)!=1:
            continue

        previous_metadata=candidates[0].get('onvif',{})
        incoming_metadata=camera.get('onvif')

        merged=json.loads(json.dumps(previous_metadata))

        if isinstance(incoming_metadata,dict):
            merged.update(incoming_metadata)

        camera['onvif']=merged

    return cameras



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

    lowered_version=VERSION.lower()

    if '-dev' in lowered_version:
        release_label='Development'
    elif '-rc' in lowered_version:
        release_label='Release Candidate'
    elif '-beta' in lowered_version:
        release_label='Beta'
    elif '-alpha' in lowered_version:
        release_label='Alpha'
    else:
        release_label='Stable'

    payload={
        'ok':True,
        'version':VERSION,
        'release':release_label,
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
            'focus_audio_default_on':bool(
                layout.get(
                    'focus_audio_default_on',
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
    def static(self,name,content_type):
        try:
            raw=(WEB_DIR/name).read_bytes()
        except OSError:
            return self.send_error(404)
        self.send_response(200)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers(); self.wfile.write(raw)
    def body(self): return json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))).decode())
    def authdoc(self): return load(self.server.auth,{})
    def token(self):
        c=SimpleCookie(); c.load(self.headers.get('Cookie','')); m=c.get('pidecoder_session'); return m.value if m else None
    def lang(self):
        return lang_from_cookie_header(self.headers.get('Cookie',''))
    def authed(self):
        t=self.token(); now=time.time()
        if not t:return False
        with LOCK:
            if SESSIONS.get(t,0)<now: SESSIONS.pop(t,None); return False
            SESSIONS[t]=now+43200
        return True
    def need(self):
        if self.authed():return True
        self.j({'ok':False,'error':i18n_t('auth.required',self.lang())},401);return False
    def do_GET(self):
        p=urlparse(self.path).path
        if p in STATIC_FILES:
            name,content_type=STATIC_FILES[p]
            return self.static(name,content_type)
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
                        'error':i18n_t(
                            'diagnostics.failed',
                            self.lang(),
                            error=str(error),
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
                ip=self.client_address[0]
                if login_blocked(ip):
                    return self.j({'ok':False,'error':i18n_t('login.too_many_attempts',self.lang())},429)
                d=self.body();a=self.authdoc()
                if not(hmac.compare_digest(str(d.get('username','')),str(a.get('username',''))) and verify(str(d.get('password','')),a)):
                    register_login_failure(ip)
                    return self.j({'ok':False,'error':i18n_t('login.invalid_password',self.lang())},401)
                clear_login_failures(ip)
                t=secrets.token_urlsafe(32)
                with LOCK:SESSIONS[t]=time.time()+43200
                return self.j({'ok':True},cookie=f'pidecoder_session={t}; HttpOnly; SameSite=Strict; Path=/')
            if p=='/api/logout':
                with LOCK:SESSIONS.pop(self.token(),None)
                return self.j({'ok':True})
            if p=='/api/language':
                d=self.body();value=str(d.get('lang','')).strip().lower()
                if value not in SUPPORTED_LANGS:value=DEFAULT_LANG
                return self.j({'ok':True,'lang':value},cookie=f'pidecoder_lang={value}; SameSite=Lax; Path=/; Max-Age=31536000')
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
                ptz_xaddr=str(d.get('ptz_xaddr','')).strip()
                ptz_profile_token=str(
                    d.get('ptz_profile_token','')
                ).strip()
                raw_ptz_presets=d.get('ptz_presets',[])
                ptz_presets=[]

                if isinstance(raw_ptz_presets,list):
                    seen_preset_tokens=set()

                    for preset in raw_ptz_presets[:64]:
                        if not isinstance(preset,dict):
                            continue

                        preset_token=str(
                            preset.get('token','')
                        ).strip()[:512]

                        if (
                            not preset_token
                            or preset_token in seen_preset_tokens
                        ):
                            continue

                        preset_name=str(
                            preset.get('name','')
                            or preset_token
                        ).strip()[:128]

                        seen_preset_tokens.add(preset_token)
                        ptz_presets.append({
                            'token':preset_token,
                            'name':preset_name or preset_token,
                        })

                ip=str(d.get('ip','')).strip()
                information=d.get('information',{}) if isinstance(d.get('information'),dict) else {}

                if not media_xaddr or not grid_token or not focus_token:
                    raise ValueError(i18n_t('onvif.media_or_profile_missing',self.lang()))

                credentials=Credentials(username,password)
                grid_uri=rtsp_with_credentials(
                    get_stream_uri(media_xaddr,grid_token,credentials),
                    username,
                    password,
                    self.lang(),
                )
                focus_uri=rtsp_with_credentials(
                    get_stream_uri(media_xaddr,focus_token,credentials),
                    username,
                    password,
                    self.lang(),
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
                    'audio_enabled':False,
                    'grid_url':grid_uri,
                    'focus_url':focus_uri,
                    'onvif':{
                        'device_xaddr':device_xaddr,
                        'media_xaddr':media_xaddr,
                        'ip':ip,
                        'grid_profile_token':grid_token,
                        'focus_profile_token':focus_token,
                        'ptz_xaddr':ptz_xaddr,
                        'ptz_profile_token':ptz_profile_token,
                        'ptz_presets':ptz_presets,
                        'manufacturer':manufacturer,
                        'model':model,
                        'serial_number':serial_number,
                        'hardware_id':hardware_id,
                    },
                }

                rotate_camera_backups(self.server.root,cp,keep=5)

                removed_duplicates=0

                lang=self.lang()

                if existing_index is None:
                    cameras.append(sanitize(camera,lang))
                    action=i18n_t('camera.manage.action_added',lang)
                else:
                    previous=cameras[existing_index]

                    if isinstance(previous,dict):
                        camera['enabled']=bool(previous.get('enabled',True))
                        camera['audio_enabled']=bool(previous.get('audio_enabled',False))

                    cameras[existing_index]=sanitize(camera,lang)

                    for duplicate_index in sorted(
                        matching_indexes[1:],
                        reverse=True,
                    ):
                        if duplicate_index == existing_index:
                            continue

                        del cameras[duplicate_index]
                        removed_duplicates += 1

                    action=i18n_t('camera.manage.action_updated',lang)

                write_json(cp,{'cameras':cameras})

                lp=self.server.root/'config/layout.json'
                write_json(
                    lp,
                    normalize_layout(load(lp,{}),len(cameras)),
                )

                return self.j({
                    'ok':True,
                    'updated':existing_index is not None,
                    'message':i18n_t(
                        'camera.manage.message',
                        lang,
                        name=name,
                        action=action,
                        duplicates=(
                            i18n_t(
                                'camera.manage.duplicates',
                                lang,
                                count=removed_duplicates,
                            )
                            if removed_duplicates
                            else ''
                        ),
                    ),
                    'removed_duplicates':removed_duplicates,
                    'camera':camera,
                })
            if p=='/api/onvif/inspect':
                d=self.body();device=inspect_device(str(d.get('xaddr','')),str(d.get('username','')),str(d.get('password','')));return self.j({'ok':True,'device':device})
            if p=='/api/onvif/ptz':
                d=self.body();action=str(d.get('action','stop'));xaddr=str(d.get('ptz_xaddr',''));token=str(d.get('profile_token',''));creds=credentials_for_ptz_request(self.server.root,d,xaddr,token)
                if action=='stop':stop(xaddr,token,creds)
                elif action in PTZ_MOVES:continuous_move(xaddr,token,creds,*PTZ_MOVES[action])
                else:raise ValueError(i18n_t('ptz.unknown_command',self.lang()))
                return self.j({'ok':True})
            if p=='/api/onvif/preset':
                d=self.body();xaddr=str(d.get('ptz_xaddr',''));token=str(d.get('profile_token',''));creds=credentials_for_ptz_request(self.server.root,d,xaddr,token);goto_preset(xaddr,token,str(d.get('preset_token','')),creds);return self.j({'ok':True})
            if p=='/api/config':
                d=self.body();cams=[sanitize(c,self.lang()) for c in d.get('cameras',[]) if isinstance(c,dict)]
                if not cams:raise ValueError(i18n_t('config.at_least_one_camera',self.lang()))
                b=self.server.root/'config/backups';b.mkdir(parents=True,exist_ok=True)
                cp=self.server.root/'config/cameras.json';lp=self.server.root/'config/layout.json'
                cams=merge_existing_onvif(cams,load(cp,{'cameras':[]}).get('cameras',[]))
                if cp.exists():shutil.copy2(cp,b/'cameras.json.previous')
                if lp.exists():shutil.copy2(lp,b/'layout.json.previous')
                write_json(cp,{'cameras':cams});write_json(lp,normalize_layout(d.get('layout',{}),len(cams)));return self.j({'ok':True})
            if p=='/api/apply':
                exists=subprocess.run(['systemctl','cat','pidecoder.service'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
                if not exists:return self.j({'ok':True,'applied':False,'message':i18n_t('apply.saved_manual_restart',self.lang())})
                r=subprocess.run(['systemctl','restart','pidecoder.service'],capture_output=True,text=True,timeout=15)
                if r.returncode:raise RuntimeError(r.stderr.strip() or i18n_t('apply.restart_failed',self.lang()))
                return self.j({'ok':True,'applied':True,'message':i18n_t('apply.applied_restarted',self.lang())})
            if p=='/api/import':
                d=self.body()
                if d.get('format')!='pidecoder-config':raise ValueError(i18n_t('import.invalid_file',self.lang()))
                cams=[sanitize(c,self.lang()) for c in d.get('cameras',[]) if isinstance(c,dict)]
                if not cams:raise ValueError(i18n_t('import.no_valid_camera',self.lang()))
                lay=normalize_layout(d.get('layout',{}),len(cams))
                b=self.server.root/'config/backups';b.mkdir(parents=True,exist_ok=True)
                stamp=time.strftime('%Y%m%d-%H%M%S')
                cp=self.server.root/'config/cameras.json';lp=self.server.root/'config/layout.json'
                if cp.exists():shutil.copy2(cp,b/f'cameras.json.before-import-{stamp}')
                if lp.exists():shutil.copy2(lp,b/f'layout.json.before-import-{stamp}')
                write_json(cp,{'cameras':cams});write_json(lp,lay)
                return self.j({'ok':True,'message':i18n_t('import.imported',self.lang())})
            if p=='/api/change-password':
                d=self.body();a=self.authdoc()
                current=str(d.get('current_password',''))
                new_password=str(d.get('new_password',''))
                confirmation=str(d.get('confirm_password',''))
                lang=self.lang()

                if not verify(current,a):
                    raise ValueError(i18n_t('password.current_incorrect',lang))

                if not new_password or not confirmation:
                    raise ValueError(
                        i18n_t('password.must_be_typed_twice',lang)
                    )

                if len(new_password)<8:
                    raise ValueError(
                        i18n_t('password.too_short',lang)
                    )

                if new_password!=confirmation:
                    raise ValueError(
                        i18n_t('password.mismatch',lang)
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
                    'message':i18n_t('password.changed',lang)
                })
            self.send_error(404)
        except ValueError as e:self.j({'ok':False,'error':str(e)},400)
        except Exception as e:self.j({'ok':False,'error':i18n_t('server.error',self.lang(),error=str(e))},500)
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
