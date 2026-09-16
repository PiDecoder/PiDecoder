let cfg={cameras:[],layout:{}},drag=null,timer=null;
const NOTIFICATION_LIMIT=5;
let notificationItems=[];
let notificationUnread=0;
const t=(key,vars)=>window.I18N.t(key,vars);

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
      `<div class="notification-empty">${esc(t('notifications.none'))}</div>`;
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
          ? t('api.unavailable')
          : t('api.invalid_response',{status:response.status})
    };

    console.error(
      'Réponse non JSON pour',
      path,
      text.slice(0,500)
    );
  }

  if(response.status===401){
    if(path==='/api/login'){
      throw Error(data.error||t('login.error_fallback'));
    }

    showLogin();
    throw Error(t('session.expired'));
  }

  if(!response.ok||data.ok===false){
    throw Error(data.error||t('api.server_error_fallback'));
  }

  return data;
}

function showLogin(){app.classList.add('hidden');login.classList.remove('hidden')}
async function showApp(){login.classList.add('hidden');app.classList.remove('hidden');
  // Vérifie tout de suite s'il y a un changement réseau en attente de
  // confirmation (ex. : on vient de se reconnecter sur la nouvelle IP
  // après un changement d'adresse) — sans ça, le plein écran de
  // confirmation restait invisible tant que l'utilisateur n'allait pas
  // cliquer manuellement sur l'onglet Réseau, et le compte à rebours
  // pouvait déjà être écoulé le temps qu'il y pense. Ne bloque pas
  // l'affichage du reste de l'appli (pas de await).
  networkRefresh();
  await loadCfg();sysInfo()}
let currentVersion='';
function updateVersionLabel(){
  if(!currentVersion)return;
  const label=t('header.version',{version:currentVersion});
  if(loginVersion)loginVersion.textContent=label;
  if(appVersion)appVersion.textContent=label;
}
async function boot(){let s=await api('/api/session');currentVersion=s.version||'';updateVersionLabel();s.authenticated?showApp():showLogin()}
async function doLogin(e){e.preventDefault();le.textContent='';try{await api('/api/login',{method:'POST',body:JSON.stringify({username:lu.value,password:lp.value})});lp.value='';le.textContent='';showApp()}catch(x){le.textContent=x.message}}
async function logout(){await api('/api/logout',{method:'POST',body:'{}'});showLogin()}
function tab(id,b){for(let x of ['cams','layout','sys','network','sec','backup','onvif'])document.getElementById(x).classList.toggle('hidden',x!==id);document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');if(id==='sys'){refreshDiagnostics();sysInfo();updateStatusRefresh()}if(id==='layout'){sync();renderMosaic()}if(id==='sec'){tlsRefreshStatus()}if(id==='network'){networkRefresh()}}
async function loadCfg(){cfg=await api('/api/config');cols.value=cfg.layout.columns||3;rows.value=cfg.layout.rows||3;fs.checked=!!cfg.layout.fullscreen_on_start;audioDefault.checked=!!cfg.layout.focus_audio_default_on;let o=cfg.layout.camera_order||[],active=cfg.cameras.filter(c=>c.enabled!==false),ordered=[];for(let i of o)if(active[i])ordered.push(active[i]);active.forEach((c,i)=>{if(!o.includes(i))ordered.push(c)});let cursor=0;cfg.cameras=cfg.cameras.map(c=>c.enabled===false?c:ordered[cursor++]);ensurePlacements();render();renderMosaic()}
function esc(v){let d=document.createElement('div');d.textContent=v??'';return d.innerHTML}
function parse(u){let r={user:'',pwd:'',host:'',port:'554',path:'/axis-media/media.amp',w:'',h:'',fps:''};try{let x=new URL(u),res=(x.searchParams.get('resolution')||'').split('x');r={user:decodeURIComponent(x.username||''),pwd:decodeURIComponent(x.password||''),host:x.hostname,port:x.port||'554',path:x.pathname||'/',w:res[0]||'',h:res[1]||'',fps:x.searchParams.get('fps')||''}}catch{}return r}
function build(b,w,h,f,orig){if(!b.host)return orig;let a=b.user?encodeURIComponent(b.user)+(b.pwd?':'+encodeURIComponent(b.pwd):'')+'@':'',p=b.port?':'+b.port:'',path=b.path.startsWith('/')?b.path:'/'+b.path,q=new URLSearchParams();try{q=new URL(orig).searchParams}catch{}if(w&&h)q.set('resolution',w+'x'+h);else q.delete('resolution');if(f)q.set('fps',f);else q.delete('fps');return `rtsp://${a}${b.host}${p}${path}${q.toString()?'?'+q.toString():''}`}
function render(){list.innerHTML='';cfg.cameras.forEach((c,i)=>{let g=parse(c.grid_url),f=parse(c.focus_url),b=g.host?g:f,d=document.createElement('div');d.className='camera';d.innerHTML=`<div class="head"><span class="handle" draggable="true">☰</span><span class="title">${esc(c.name)}</span><label class="switch"><input class="en" type="checkbox" ${c.enabled!==false?'checked':''}><span class="track"></span>${esc(t('cams.active'))}</label><label class="switch" title="${esc(t('cams.audio_enabled_hint'))}"><input class="audio" type="checkbox" ${c.audio_enabled?'checked':''}><span class="track"></span>${esc(t('cams.audio_enabled'))}</label><button class="danger del">${esc(t('cams.delete'))}</button></div><div class="grid"><div class="s4"><label>${esc(t('cams.name'))}</label><input class="name" value="${esc(c.name)}"></div><div class="s4"><label>${esc(t('cams.ip_address'))}</label><input class="host" value="${esc(b.host)}"></div><div class="s4"><label>${esc(t('cams.rtsp_port'))}</label><input class="port" type="number" value="${esc(b.port)}"></div><div class="s4"><label>${esc(t('common.username'))}</label><input class="user" value="${esc(b.user)}"></div><div class="s4"><label>${esc(t('common.password'))}</label><div class="pass"><input class="pwd" type="password" value="${esc(b.pwd)}"><button class="secondary eye" type="button">👁</button></div></div><div class="s4"><label>${esc(t('cams.rtsp_path'))}</label><input class="path" value="${esc(b.path)}"></div><div class="s6"><label>${esc(t('cams.grid_resolution'))}</label><div class="pair"><input class="gw" type="number" value="${esc(g.w)}" placeholder="640"><span>×</span><input class="gh" type="number" value="${esc(g.h)}" placeholder="360"></div></div><div class="s3"><label>${esc(t('cams.grid_fps'))}</label><input class="gf" type="number" value="${esc(g.fps)}" placeholder="12"></div><div class="s3"><label>&nbsp;</label><button class="secondary def">${esc(t('cams.default_values'))}</button></div><div class="s6"><label>${esc(t('cams.focus_resolution'))}</label><div class="pair"><input class="fw" type="number" value="${esc(f.w)}" placeholder="1920"><span>×</span><input class="fh" type="number" value="${esc(f.h)}" placeholder="1080"></div></div><div class="s3"><label>${esc(t('cams.focus_fps'))}</label><input class="ff" type="number" value="${esc(f.fps)}" placeholder="25"></div><div class="s12"><details><summary>${esc(t('cams.advanced_summary'))}</summary><div class="field"><label>${esc(t('cams.grid_url_label'))}</label><input class="gu" value="${esc(c.grid_url)}"></div><div class="field"><label>${esc(t('cams.focus_url_label'))}</label><input class="fu" value="${esc(c.focus_url)}"></div><div class="muted">${esc(t('cams.manual_url_hint'))}</div></details></div></div>`;
let h=d.querySelector('.handle');h.ondragstart=e=>{sync();drag=i;e.dataTransfer.effectAllowed='move';d.style.opacity='.45'};h.ondragend=()=>{drag=null;d.style.opacity='1'};d.ondragover=e=>{if(drag!==null)e.preventDefault()};d.ondrop=e=>{if(drag===null)return;e.preventDefault();let m=cfg.cameras.splice(drag,1)[0];cfg.cameras.splice(i,0,m);drag=null;render()};d.querySelector('.del').onclick=()=>{sync();cfg.cameras.splice(i,1);render();renderMosaic()};d.querySelector('.eye').onclick=()=>{let x=d.querySelector('.pwd');x.type=x.type==='password'?'text':'password'};d.querySelector('.def').onclick=()=>{d.querySelector('.gw').value=640;d.querySelector('.gh').value=360;d.querySelector('.gf').value=12;d.querySelector('.fw').value=1920;d.querySelector('.fh').value=1080;d.querySelector('.ff').value=25};list.appendChild(d)})}
function read(d,i){let b={user:d.querySelector('.user').value.trim(),pwd:d.querySelector('.pwd').value,host:d.querySelector('.host').value.trim(),port:d.querySelector('.port').value.trim(),path:d.querySelector('.path').value.trim()},result={name:d.querySelector('.name').value.trim()||t('cams.default_name'),enabled:d.querySelector('.en').checked,audio_enabled:d.querySelector('.audio').checked,grid_url:build(b,d.querySelector('.gw').value,d.querySelector('.gh').value,d.querySelector('.gf').value,d.querySelector('.gu').value.trim()),focus_url:build(b,d.querySelector('.fw').value,d.querySelector('.fh').value,d.querySelector('.ff').value,d.querySelector('.fu').value.trim())},previous=cfg.cameras[i];if(previous&&previous.onvif&&typeof previous.onvif==='object')result.onvif=previous.onvif;return result}
function sync(){cfg.cameras=[...document.querySelectorAll('.camera')].map((d,i)=>read(d,i))}
function addCam(){sync();cfg.cameras.push({name:t('cams.new_camera_prefix')+' '+(cfg.cameras.length+1),enabled:true,audio_enabled:false,grid_url:'rtsp://root:@192.168.1.100:554/axis-media/media.amp?videocodec=h264&resolution=640x360&fps=12',focus_url:'rtsp://root:@192.168.1.100:554/axis-media/media.amp?videocodec=h264&resolution=1920x1080&fps=25'});render();renderMosaic()}
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
    toast(t('mosaic.too_small_for_placement'),true);
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
    toast(t('mosaic.not_enough_space_resize'),true);
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
  return parsed.host||t('mosaic.unknown_address');
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
      `<div class="mosaic-warning">⚠ ${esc(t('mosaic.too_small_for_placement'))}</div>`;
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
        <div class="mosaic-name">${esc(entry.camera.name||t('cams.default_name'))}</div>
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
          <span class="muted">${esc(t('mosaic.drag_hint'))}</span>
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
      `<div class="mosaic-empty">${esc(t('mosaic.no_active_camera'))}</div>`;
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
    toast(t('mosaic.too_small_for_template'),true);
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
  mosaicSaved.textContent=t('mosaic.saving');

  mosaicSaveTimer=setTimeout(
    async()=>{
      try{
        await save(false);
        mosaicSaved.textContent=t('mosaic.saved');
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

function collect(){sync();const activeCount=cfg.cameras.filter(c=>c.enabled!==false).length;ensurePlacements();cfg.layout={columns:+cols.value||3,rows:+rows.value||3,fullscreen_on_start:fs.checked,focus_audio_default_on:audioDefault.checked,camera_order:Array.from({length:activeCount},(_,i)=>i),placements:cfg.layout.placements};return cfg}
async function save(show=true){await api('/api/config',{method:'POST',body:JSON.stringify(collect())});if(show)toast(t('save.done'))}
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
    return t('sys.uptime.dhm',{days,hours,minutes});
  }

  if(hours){
    return t('sys.uptime.hm',{hours,minutes});
  }

  return t('sys.uptime.m',{minutes});
}

function throttlingHealth(raw,label=''){
  const value=String(raw??'').trim().toLowerCase();

  if(!value || value==='—' || value==='indisponible'){
    return {
      value:t('sys.unavailable'),
      sub:label||t('sys.vcgencmd_unavailable'),
      state:''
    };
  }

  const bits=Number.parseInt(value,16);

  if(!Number.isFinite(bits)){
    return {
      value,
      sub:label||t('sys.value_not_recognized'),
      state:'warn'
    };
  }

  if((bits&0x000f)!==0){
    return {
      value:t('sys.throttling_active'),
      sub:value,
      state:'bad'
    };
  }

  if((bits&0xf0000)!==0){
    return {
      value:t('sys.throttling_past'),
      sub:value,
      state:'warn'
    };
  }

  return {
    value:t('sys.throttling_none'),
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
        ? t('sys.card.memory_units',{used:system.memory_used_mb,total:system.memory_total_mb})
        : ''
    );

  const cards=[
    [
      t('sys.card.temperature'),
      temperature!=null?`${temperature} °C`:t('sys.unavailable'),
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
      system.cpu_count?t('sys.card.cores',{count:system.cpu_count}):'',
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
    passwordStatus.textContent=t('password.current_required');
    return false;
  }

  if(!first || !second){
    passwordStatus.className='password-status-error';
    passwordStatus.textContent=t('password.twice_required');
    return false;
  }

  if(first.length<8){
    newp.classList.add('password-invalid');
    confirmp.classList.add('password-invalid');
    passwordStatus.className='password-status-error';
    passwordStatus.textContent=t('password.min_length');
    return false;
  }

  if(first!==second){
    newp.classList.add('password-invalid');
    confirmp.classList.add('password-invalid');
    passwordStatus.className='password-status-error';
    passwordStatus.textContent=t('password.mismatch_client');
    return false;
  }

  newp.classList.add('password-valid');
  confirmp.classList.add('password-valid');
  passwordStatus.className='password-status-ok';
  passwordStatus.textContent=t('password.match_ok');
  changePwdButton.disabled=false;
  return true;
}

async function changePwd(){
  if(!validatePasswordChange()){
    return;
  }

  const button=changePwdButton;
  button.disabled=true;
  button.innerHTML=`<span class="spinner"></span>${esc(t('password.changing'))}`;

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
    toast(t('password.changed_toast'));
    setTimeout(showLogin,1200);

  }catch(error){
    toast(error.message,true);

  }finally{
    button.textContent=t('sec.change_button');
    validatePasswordChange();
  }
}

function renderTlsStatus(r){
  const active=!!r.https_active;
  tlsToggleButton.textContent=active?t('sec.tls_disable_button'):t('sec.tls_enable_button');
  tlsToggleButton.dataset.action=active?'disable':'enable';
  // Toujours réactivé ici plutôt que dans tlsToggle()/httpToggle() : le cas
  // "redémarrage sans redirection" (le port par lequel on est déjà
  // connecté n'est pas affecté) relit l'état via ce même rendu au lieu de
  // recharger la page — sans ça le bouton resterait désactivé pour de bon.
  tlsToggleButton.disabled=false;
  tlsImportButton.disabled=!active;
  tlsImportHint.classList.toggle('hidden',active);
  tlsToggleWarning.classList.remove('hidden');
  let html=`<strong>${esc(active?t('sec.tls_status_active',{port:r.https_port}):t('sec.tls_status_inactive'))}</strong>`;
  if(active && r.cert){
    html+=`<br>${esc(t('sec.tls_subject'))} : ${esc(r.cert.subject||'?')}`;
    html+=`<br>${esc(t('sec.tls_expires'))} : ${esc(r.cert.not_after||'?')}`;
    html+=`<br>${esc(t('sec.tls_san'))} : ${esc((r.cert.san||[]).join(', ')||'—')}`;
  }else if(!active && r.disabled_present){
    html+=`<br>${esc(t('sec.tls_disabled_present'))}`;
  }
  tlsStatus.innerHTML=html;
}

function renderHttpStatus(r){
  const active=!!r.http_active;
  httpToggleButton.textContent=active?t('sec.http_disable_button'):t('sec.http_enable_button');
  httpToggleButton.dataset.action=active?'disable':'enable';
  httpToggleButton.disabled=false;
  httpToggleWarning.classList.remove('hidden');
  httpStatus.innerHTML=`<strong>${esc(active?t('sec.http_status_active',{port:r.http_port}):t('sec.http_status_inactive'))}</strong>`;
}

async function tlsRefreshStatus(){
  // Une seule requête : /api/tls/status renvoie l'état des deux ports
  // (HTTP et HTTPS écoutent en parallèle, voir config-web.py) — pas besoin
  // de deux allers-retours pour peupler les deux panneaux de l'onglet
  // Sécurité.
  try{
    const r=await api('/api/tls/status');
    renderTlsStatus(r);
    renderHttpStatus(r);
    renderPortsStatus(r);
  }catch(e){
    tlsStatus.textContent=e.message;
  }
}

function renderPortsStatus(r){
  // Ne jamais écraser une valeur en cours de frappe : cette fonction est
  // aussi appelée par les rafraîchissements automatiques après un toggle
  // HTTP/HTTPS, pas seulement à l'ouverture de l'onglet.
  if(document.activeElement!==portsHttpInput){portsHttpInput.value=r.http_port}
  if(document.activeElement!==portsHttpsInput){portsHttpsInput.value=r.https_port}
}

async function portsApply(){
  const httpPort=parseInt(portsHttpInput.value,10);
  const httpsPort=parseInt(portsHttpsInput.value,10);
  if(!Number.isInteger(httpPort)||httpPort<1||httpPort>65535||!Number.isInteger(httpsPort)||httpsPort<1||httpsPort>65535){
    toast(t('sec.ports_invalid'),true);
    return;
  }
  if(httpPort===httpsPort){
    toast(t('sec.ports_must_differ'),true);
    return;
  }
  portsApplyButton.disabled=true;
  try{
    const r=await api('/api/tls/set-ports',{method:'POST',body:JSON.stringify({http_port:httpPort,https_port:httpsPort})});
    toast(t('sec.ports_restarting'));
    tlsRestartCountdown(r.redirect_url,t('sec.ports_restart_overlay_title'));
  }catch(e){
    toast(e.message,true);
    portsApplyButton.disabled=false;
  }
}

async function tlsToggle(){
  const action=tlsToggleButton.dataset.action;
  tlsToggleButton.disabled=true;
  try{
    const r=await api(`/api/tls/${action}`,{method:'POST',body:'{}'});
    if(r.restarting){
      toast(t('sec.tls_restarting'));
      if(r.redirect_url){
        tlsRestartCountdown(r.redirect_url,t('sec.tls_restart_overlay_title'));
      }else{
        // Le port par lequel on est déjà connecté n'est pas affecté (HTTP
        // et HTTPS tournent en parallèle sur des ports distincts) : pas de
        // redirection nécessaire, juste attendre la fin du redémarrage et
        // relire l'état.
        tlsStatus.innerHTML=`<strong>${esc(t('sec.tls_restarting'))}</strong>`;
        setTimeout(tlsRefreshStatus,4000);
      }
    }else{
      tlsRefreshStatus();
      tlsToggleButton.disabled=false;
    }
  }catch(e){
    toast(e.message,true);
    tlsToggleButton.disabled=false;
  }
}

async function httpToggle(){
  const action=httpToggleButton.dataset.action;
  httpToggleButton.disabled=true;
  try{
    const r=await api(`/api/http/${action}`,{method:'POST',body:'{}'});
    if(r.restarting){
      toast(t('sec.http_restarting'));
      if(r.redirect_url){
        tlsRestartCountdown(r.redirect_url,t('sec.http_restart_overlay_title'));
      }else{
        httpStatus.innerHTML=`<strong>${esc(t('sec.http_restarting'))}</strong>`;
        setTimeout(tlsRefreshStatus,4000);
      }
    }else{
      tlsRefreshStatus();
      httpToggleButton.disabled=false;
    }
  }catch(e){
    toast(e.message,true);
    httpToggleButton.disabled=false;
  }
}

function tlsRestartCountdown(url,title){
  // Rediriger tout de suite (ou après un délai court fixe) tombe souvent
  // sur une page inaccessible : redémarrer pidecoder-config.service prend
  // quelques secondes (arrêt de l'ancien processus, rechargement du
  // certificat, nouvelle écoute), pendant lesquelles la nouvelle URL ne
  // répond pas encore. On affiche donc un compte à rebours généreux (30s,
  // largement suffisant en pratique) en plein écran — impossible à
  // manquer ou à fermer par erreur — avec le message d'avertissement sur
  // les cookies déjà visible dedans, puis on redirige une seule fois à la
  // fin plutôt que de laisser le navigateur afficher une erreur de
  // connexion pendant l'attente.
  let remaining=30;

  tlsRestartOverlay.classList.remove('hidden');
  if(title){tlsRestartOverlayTitle.textContent=title}

  const render=()=>{
    tlsRestartCountdownValue.textContent=remaining;
    tlsStatus.innerHTML=
      `<strong>${esc(t('sec.tls_restarting'))}</strong>`+
      `<br>${esc(t('sec.tls_restart_countdown',{seconds:remaining}))}`;
  };

  render();

  const iv=setInterval(()=>{
    remaining-=1;
    if(remaining<=0){
      clearInterval(iv);
      window.location.href=url;
      return;
    }
    render();
  },1000);
}

async function tlsGenerate(){
  tlsGenerateButton.disabled=true;
  try{
    const r=await api('/api/tls/generate',{method:'POST',body:JSON.stringify({force:true})});
    toast(r.reloaded?t('sec.tls_generated_active'):t('sec.tls_generated_staged'));
    tlsRefreshStatus();
  }catch(e){
    toast(e.message,true);
  }finally{
    tlsGenerateButton.disabled=false;
  }
}

function readFileAsText(input){
  return new Promise((resolve,reject)=>{
    const file=input.files && input.files[0];
    if(!file){reject(new Error(t('sec.tls_import_missing_file')));return}
    const reader=new FileReader();
    reader.onload=()=>resolve(String(reader.result||''));
    reader.onerror=()=>reject(new Error(t('sec.tls_import_missing_file')));
    reader.readAsText(file);
  });
}

async function tlsImport(){
  tlsImportButton.disabled=true;
  try{
    const [cert,key]=await Promise.all([readFileAsText(tlsCertFile),readFileAsText(tlsKeyFile)]);
    const r=await api('/api/tls/import',{method:'POST',body:JSON.stringify({cert,key})});
    toast(r.reloaded?t('sec.tls_imported_active'):t('sec.tls_generated_staged'));
    tlsCertFile.value='';
    tlsKeyFile.value='';
    await tlsRefreshStatus();
  }catch(e){
    toast(e.message,true);
    tlsImportButton.disabled=false;
  }
}

async function serviceStatus(){
  if(app.classList.contains('hidden'))return;
  try{
    let s=await api('/api/service-status');
    engine.className='engine '+(s.active?'running':'stopped');
    engineText.textContent=s.active?t('engine.running'):t('engine.stopped');
  }catch{}
}
async function exportConfig(){
  try{
    let r=await fetch('/api/export');
    if(r.status===401){showLogin();throw Error(t('session.expired'))}
    if(!r.ok)throw Error(t('export.failed'));
    let blob=await r.blob(),a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download='pidecoder-config-'+new Date().toISOString().slice(0,10)+'.json';
    document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(a.href);
    toast(t('export.done'));
  }catch(e){toast(e.message,true)}
}
async function importConfig(){
  let f=importFile.files[0];
  if(!f){toast(t('import.select_file'),true);return}
  try{
    let data=JSON.parse(await f.text());
    await api('/api/import',{method:'POST',body:JSON.stringify(data)});
    toast(t('import.done_toast'));
    await loadCfg();
  }catch(e){toast(e.message,true)}
}

let onvifDevices=[];
async function discoverOnvif(){
  onvifStatus.textContent=t('onvif.discovering');
  onvifResults.innerHTML='';onvifDiagnostics.style.display='none';onvifDiagnostics.innerHTML='';
  try{
    let r=await api('/api/onvif/discover',{method:'POST',body:JSON.stringify({timeout:5})});
    onvifDevices=r.devices||[];let d=r.diagnostics||{};
    onvifStatus.textContent=t('onvif.devices_found',{count:onvifDevices.length});
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
    toast(t('onvif.invalid_ipv4'),true);
    return;
  }

  if(!Number.isInteger(port)||port<1||port>65535){
    toast(t('onvif.invalid_port'),true);
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
      name:t('onvif.manual_camera_name',{ip}),
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
    toast(t('onvif.card_not_found'),true);
    return;
  }

  rememberManualOnvif();

  button.disabled=true;
  button.innerHTML=`<span class="spinner"></span>${esc(t('onvif.identifying'))}`;

  try{
    await identifyOnvif(index,box);
  }finally{
    button.disabled=false;
    button.textContent=t('onvif.identify_button');
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
  const codec=profile.encoding||t('onvif.codec_unknown');
  const resolution=profile.width&&profile.height
    ? `${profile.width} × ${profile.height}`
    : t('onvif.resolution_unknown');
  const fps=profile.fps ? `${profile.fps} fps` : t('onvif.fps_unknown');

  return `<option value="${esc(profile.token||'')}">${esc(profile.name||profile.token||t('onvif.profile_fallback'))} · ${esc(codec)} · ${esc(resolution)} · ${esc(fps)}</option>`;
}

let activePtzStop=null;

function stopActivePtz(){
  const stop=activePtzStop;
  activePtzStop=null;

  if(stop){
    stop();
  }
}

document.addEventListener('pointerup',stopActivePtz);
document.addEventListener('pointercancel',stopActivePtz);
window.addEventListener('blur',stopActivePtz);
document.addEventListener('visibilitychange',()=>{
  if(document.hidden){
    stopActivePtz();
  }
});

function ptzPayload(index,profileToken,action){
  const device=onvifDevices[index];
  const identification=device?.identification||{};

  return {
    ptz_xaddr:identification.ptz_xaddr||'',
    profile_token:profileToken,
    username:onvifUser.value,
    password:onvifPassword.value,
    action
  };
}

function bindPtzControls(index,box,profile,presets){
  const profileToken=String(profile?.token||'');
  const moveButtons=[
    ...box.querySelectorAll('[data-ptz-action]')
  ].filter(button=>button.dataset.ptzAction!=='stop');

  const stopButton=box.querySelector('[data-ptz-action="stop"]');
  const allButtons=[
    ...moveButtons,
    stopButton
  ].filter(Boolean);

  const clearActive=()=>{
    allButtons.forEach(button=>
      button.classList.remove('ptz-active')
    );
  };

  const send=action=>api('/api/onvif/ptz',{
    method:'POST',
    body:JSON.stringify(
      ptzPayload(index,profileToken,action)
    )
  });

  moveButtons.forEach(button=>{
    const action=button.dataset.ptzAction;

    button.addEventListener('contextmenu',event=>
      event.preventDefault()
    );

    button.addEventListener('pointerdown',event=>{
      if(event.pointerType==='mouse' && event.button!==0){
        return;
      }

      event.preventDefault();
      stopActivePtz();
      clearActive();
      button.classList.add('ptz-active');

      let stopped=false;
      const movePromise=send(action);

      const stop=async()=>{
        if(stopped){
          return;
        }

        stopped=true;
        clearActive();

        try{
          await movePromise;
        }catch(error){
          toast(error.message,true);
          return;
        }

        try{
          await send('stop');
        }catch(error){
          toast(error.message,true);
        }
      };

      activePtzStop=stop;

      movePromise.catch(error=>{
        if(activePtzStop===stop){
          activePtzStop=null;
        }

        clearActive();
        toast(error.message,true);
      });
    });

    button.addEventListener('pointerleave',()=>{
      if(activePtzStop){
        stopActivePtz();
      }
    });

    button.addEventListener('lostpointercapture',()=>{
      if(activePtzStop){
        stopActivePtz();
      }
    });
  });

  if(stopButton){
    stopButton.onclick=async()=>{
      stopActivePtz();
      clearActive();

      try{
        await send('stop');
      }catch(error){
        toast(error.message,true);
      }
    };
  }

  const presetSelect=box.querySelector('.ptz-preset');
  const presetButton=box.querySelector('.ptz-goto');

  if(presetSelect && presetButton){
    presetButton.onclick=async()=>{
      const presetToken=presetSelect.value;

      if(!presetToken){
        toast(t('ptz.no_preset_selected'),true);
        return;
      }

      stopActivePtz();
      presetButton.disabled=true;
      presetButton.innerHTML=
        `<span class="spinner"></span>${esc(t('ptz.moving'))}`;

      try{
        const device=onvifDevices[index];
        const identification=device?.identification||{};

        await api('/api/onvif/preset',{
          method:'POST',
          body:JSON.stringify({
            ptz_xaddr:identification.ptz_xaddr||'',
            profile_token:profileToken,
            preset_token:presetToken,
            username:onvifUser.value,
            password:onvifPassword.value
          })
        });

        toast(t('ptz.preset_called'));

      }catch(error){
        toast(error.message,true);

      }finally{
        presetButton.disabled=!(presets||[]).length;
        presetButton.textContent=t('ptz.goto_preset');
      }
    };
  }
}

function renderOnvifDiscovery(){
  onvifResults.innerHTML='';

  if(!onvifDevices.length){
    onvifResults.innerHTML=`<div class="onvif-card"><div class="muted">${esc(t('onvif.no_device_found'))}</div></div>`;
    return;
  }

  onvifDevices.forEach((device,index)=>{
    const box=document.createElement('div');
    box.className='onvif-card';

    const identification=device.identification||null;
    const info=identification?.information||{};
    const profiles=usableProfiles(identification?.profiles||[]);
    const existing=existingCameraFor(device);
    const ptzProfiles=(identification?.profiles||[])
      .filter(profile=>profile.ptz && profile.token);
    const preferredPtzToken=
      existing?.onvif?.focus_profile_token ||
      existing?.onvif?.grid_profile_token ||
      '';
    const ptzProfile=
      ptzProfiles.find(profile=>profile.token===preferredPtzToken) ||
      ptzProfiles[0] ||
      null;
    const ptzPresets=ptzProfile
      ? (identification?.presets?.[ptzProfile.token]||[])
      : [];
    const ptzAvailable=Boolean(
      identification?.ptz_supported &&
      identification?.ptz_xaddr &&
      ptzProfile
    );

    const defaultName=existing?.name ||
      [info.Manufacturer,info.Model].filter(Boolean).join(' ') ||
      device.name || device.hardware || t('onvif.manual_camera_name',{ip:device.ip||''});

    const options=profiles.map(profileOption).join('');
    const existingGrid=existing?.onvif?.grid_profile_token||existing?.onvif?.profile_token||'';
    const existingFocus=existing?.onvif?.focus_profile_token||existing?.onvif?.profile_token||'';

    const xaddrs=(device.xaddrs||[device.xaddr])
      .filter(Boolean)
      .map(value=>`<li>${esc(value)}</li>`)
      .join('');

    const ptzPresetOptions=ptzPresets
      .map(preset=>
        `<option value="${esc(preset.token||'')}">`+
        `${esc(preset.name||preset.token||t('ptz.preset_label'))}</option>`
      )
      .join('');

    const ptzPanel=ptzAvailable?`
      <div class="backupbox ptz-panel">
        <div class="ptz-panel-title">
          <strong>${esc(t('ptz.command_title'))}</strong>
          <span class="badge ptz">${esc(ptzProfile.name||ptzProfile.token)}</span>
        </div>

        <div class="ptzpad" aria-label="${esc(t('ptz.pad_aria'))}">
          <div class="ptz-empty"></div>
          <button type="button" class="secondary" data-ptz-action="up" title="${esc(t('ptz.up'))}">▲</button>
          <div class="ptz-empty"></div>

          <button type="button" class="secondary" data-ptz-action="left" title="${esc(t('ptz.left'))}">◀</button>
          <button type="button" class="secondary" data-ptz-action="stop" title="${esc(t('ptz.stop'))}">■</button>
          <button type="button" class="secondary" data-ptz-action="right" title="${esc(t('ptz.right'))}">▶</button>

          <div class="ptz-empty"></div>
          <button type="button" class="secondary" data-ptz-action="down" title="${esc(t('ptz.down'))}">▼</button>
          <div class="ptz-empty"></div>
        </div>

        <div class="ptz-zoom">
          <button type="button" class="secondary" data-ptz-action="zoomin">${esc(t('ptz.zoom_in'))}</button>
          <button type="button" class="secondary" data-ptz-action="zoomout">${esc(t('ptz.zoom_out'))}</button>
        </div>

        ${ptzPresets.length?`
          <div class="ptz-presets">
            <div>
              <label>${esc(t('ptz.preset_label'))}</label>
              <select class="ptz-preset">${ptzPresetOptions}</select>
            </div>
            <button type="button" class="secondary ptz-goto">${esc(t('ptz.goto_preset'))}</button>
          </div>
        `:`
          <div class="muted ptz-help">${esc(t('ptz.no_preset'))}</div>
        `}

        <div class="muted ptz-help">
          ${esc(t('ptz.hold_hint'))}
        </div>
      </div>
    `:'';

    box.innerHTML=`
      <div class="row" style="justify-content:space-between">
        <div>
          <div class="onvif-title">${esc([info.Manufacturer,info.Model].filter(Boolean).join(' ')||device.name||device.hardware||t('onvif.device_fallback'))}</div>
          <div style="margin-top:7px">
            <span class="badge">ONVIF</span>
            <span class="badge">${esc(device.ip||t('onvif.ip_unknown'))}</span>
            ${identification?`<span class="badge ptz">${esc(t('onvif.identified_badge'))}</span>`:''}
            ${ptzAvailable?'<span class="badge ptz">PTZ</span>':''}
            ${existing?`<span class="badge badge-configured">${esc(t('onvif.already_configured'))}</span>`:`<span class="badge">${esc(t('onvif.new_badge'))}</span>`}
          </div>
        </div>
        <button class="primary identify-onvif btn-fixed">${identification?esc(t('onvif.reidentify_button')):esc(t('onvif.identify_button'))}</button>
      </div>

      <div class="onvif-identification" style="margin-top:12px">
        ${identification?`
          <div class="grid">
            <div class="s4"><label>${esc(t('onvif.manufacturer'))}</label><div>${esc(info.Manufacturer||'—')}</div></div>
            <div class="s4"><label>${esc(t('onvif.model'))}</label><div>${esc(info.Model||'—')}</div></div>
            <div class="s4"><label>Firmware</label><div>${esc(info.FirmwareVersion||'—')}</div></div>
            <div class="s6"><label>${esc(t('onvif.serial_number'))}</label><div>${esc(info.SerialNumber||'—')}</div></div>
            <div class="s6"><label>Hardware ID</label><div>${esc(info.HardwareId||'—')}</div></div>
          </div>

          <div class="backupbox" style="margin-top:12px">
            <div class="grid">
              <div class="s12">
                <label>${esc(t('onvif.name_in_pidecoder'))}</label>
                <input class="manager-name" value="${esc(defaultName)}">
              </div>
              <div class="s6">
                <label>${esc(t('onvif.grid_profile'))}</label>
                <select class="manager-grid-profile">${options}</select>
              </div>
              <div class="s6">
                <label>${esc(t('onvif.focus_profile'))}</label>
                <select class="manager-focus-profile">${options}</select>
              </div>
            </div>

            <div class="row" style="margin-top:12px;justify-content:space-between">
              <div class="muted">${profiles.length?esc(t('onvif.usable_profiles_count',{count:profiles.length})):esc(t('onvif.no_usable_profile'))}</div>
              <button class="${existing?'primary':'success'} manager-save btn-fixed" ${profiles.length?'':'disabled'}>
                ${existing?esc(t('onvif.update_button')):esc(t('onvif.add_button'))}
              </button>
            </div>
          </div>

          ${ptzPanel}

          <details style="margin-top:12px">
            <summary>${esc(t('onvif.all_profiles_summary'))}</summary>
            ${(identification.profiles||[]).map(profile=>`
              <div class="backupbox" style="padding:10px;margin-top:8px">
                <strong>${esc(profile.name||profile.token||t('onvif.profile_fallback'))}</strong>
                <div class="muted">${esc(profile.encoding||t('onvif.codec_unknown'))} · ${profile.width&&profile.height?esc(profile.width+' × '+profile.height):esc(t('onvif.resolution_unknown'))} · ${profile.fps?esc(profile.fps)+' fps':esc(t('onvif.fps_unknown'))}</div>
                <div class="muted">${esc(t('onvif.token_label'))}${esc(profile.token||'—')}</div>
              </div>`).join('')}
          </details>
        `:`
          <div class="muted">${esc(t('onvif.hardware_announced'))}${esc(device.hardware||'—')}</div>
          <div class="muted">${esc(t('onvif.location_label'))}${esc(device.location||'—')}</div>
        `}
      </div>

      <details style="margin-top:12px">
        <summary>${esc(t('onvif.discovered_addresses'))}</summary>
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

    if(ptzAvailable){
      bindPtzControls(
        index,
        box,
        ptzProfile,
        ptzPresets
      );
    }

    onvifResults.appendChild(box);
  });
}

async function saveManagedCamera(index,box){
  const device=onvifDevices[index];
  const identification=device.identification;

  if(!identification){
    toast(t('onvif.identify_first'),true);
    return;
  }

  const button=box.querySelector('.manager-save');
  const gridProfileToken=
    box.querySelector('.manager-grid-profile').value;
  const focusProfileToken=
    box.querySelector('.manager-focus-profile').value;
  const ptzProfiles=(identification.profiles||[])
    .filter(profile=>profile.ptz && profile.token);
  const ptzProfile=
    ptzProfiles.find(profile=>profile.token===focusProfileToken) ||
    ptzProfiles.find(profile=>profile.token===gridProfileToken) ||
    ptzProfiles[0] ||
    null;

  button.disabled=true;
  button.textContent=t('onvif.saving');

  try{
    const result=await api('/api/onvif/manage-camera',{
      method:'POST',
      body:JSON.stringify({
        device_xaddr:device.xaddr,
        media_xaddr:identification.media_xaddr,
        grid_profile_token:gridProfileToken,
        focus_profile_token:focusProfileToken,
        ptz_xaddr:identification.ptz_xaddr||'',
        ptz_profile_token:ptzProfile?.token||'',
        ptz_presets:ptzProfile
          ? (identification.presets?.[ptzProfile.token]||[])
          : [],
        name:box.querySelector('.manager-name').value,
        username:onvifUser.value,
        password:onvifPassword.value,
        ip:device.ip,
        information:identification.information||{}
      })
    });

    await loadCfg();
    renderOnvifDiscovery();
    toast('✔ '+(result.message||t('onvif.camera_saved_fallback')));

  }catch(error){
    button.disabled=false;
    button.textContent=existingCameraFor(device)?t('onvif.update_button'):t('onvif.add_button');
    toast(error.message,true);
  }
}

async function identifyOnvif(index,box){
  let device=onvifDevices[index];
  let button=box.querySelector('.identify-onvif');
  let area=box.querySelector('.onvif-identification');

  button.disabled=true;
  button.innerHTML=`<span class="spinner"></span>${esc(t('onvif.identifying'))}`;
  area.innerHTML=`<div class="muted">${esc(t('onvif.connecting'))}</div>`;

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
    toast(t('onvif.identified_toast'));

  }catch(error){
    button.disabled=false;
    button.textContent=t('onvif.identify_button');
    area.innerHTML=
      '<div style="color:#ff7f89">'+
      esc(error.message)+
      '</div>'+
      '<div class="backupbox" style="margin-top:10px">'+
      `<strong>${esc(t('onvif.log_to_send'))}</strong>`+
      '<pre style="white-space:pre-wrap">sudo cat /tmp/pidecoder-onvif.log</pre>'+
      '</div>';
  }
}

function renderOnvifDiagnostics(d){
  onvifDiagnostics.style.display='block';
  let interfaces=(d.interfaces||[]).map(x=>`${esc(x.name)} (${esc(x.address)})`).join(', ')||t('common.none_f');
  let errors=(d.socket_errors||[]).map(x=>`<li>${esc(x)}</li>`).join('');
  let events=(d.events||[]).map(x=>`<li>${esc(x)}</li>`).join('');
  let types=Object.entries(d.message_types||{}).map(([n,c])=>`${esc(n)}: ${c}`).join(' · ')||t('common.none');
  let samples=(d.unknown_xml_samples||[]).map(s=>`<details style="margin-top:8px"><summary>${t('diag.sample_from',{type:esc(s.message_type||'Unknown'),ip:esc(s.source_ip||'?')})}</summary><pre style="white-space:pre-wrap;word-break:break-word">${esc((s.lines||[]).join('\n'))}</pre></details>`).join('');
  onvifDiagnostics.innerHTML=`<h3 style="margin-top:0">${esc(t('diag.discovery_title'))}</h3><div><strong>${esc(t('diag.interfaces'))}</strong> ${interfaces}</div><div><strong>${esc(t('diag.probes_sent'))}</strong> ${d.probes_sent||0}</div><div><strong>${esc(t('diag.packets_received'))}</strong> ${d.packets_received||0}</div><div><strong>${esc(t('diag.xml_packets'))}</strong> ${d.xml_packets||0}</div><div><strong>${esc(t('diag.message_types'))}</strong> ${types}</div><div><strong>${esc(t('diag.probe_matches'))}</strong> ${d.probe_matches||0}</div><div><strong>${esc(t('diag.xml_errors'))}</strong> ${d.parse_errors||0}</div>${errors?`<h4>${esc(t('diag.socket_errors'))}</h4><ul>${errors}</ul>`:''}${samples?`<h4>${esc(t('diag.unknown_xml_samples'))}</h4>${samples}`:''}<details style="margin-top:12px"><summary>${esc(t('diag.detailed_log'))}</summary><ul style="padding-left:20px">${events}</ul></details>`;
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
    diagRow('Release',data.release==='Release Candidate'?t('diag.release_candidate'):(data.release==='Stable'?t('diag.release_stable'):(data.release||'—')))+
    diagRow('Architecture',system.architecture||'—')+
    diagRow('Kernel',system.kernel||'—')+
    diagRow('PID',process.pid??'—')+
    diagRow(t('diag.fd_open'),process.fd_count??'—')+
    diagRow(t('diag.hardware_decode'),system.hardware_decode||'—');

  cameraInfo.innerHTML=
    diagRow(t('diag.configured'),cameras.total??0)+
    diagRow(t('diag.active'),cameras.enabled??0)+
    diagRow(t('diag.disabled'),cameras.disabled??0)+
    diagRow(t('diag.onvif_cameras'),cameras.onvif??0)+
    diagRow(t('diag.rtsp_streams'),cameras.configured_streams??0);

  const serviceItems=[
    ['PiDecoder',services.pidecoder||'inconnu'],
    [t('diag.web_admin'),services.web||'inconnu'],
    [t('diag.hardware_decode'),system.hardware_decode||'inconnu'],
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

  diagnosticsLogs.textContent=data.logs||t('diag.no_logs');
  diagnosticsLastReport=data.report||'';
  updateGlobalHealth(data);
}

function updateGlobalHealth(data){
  const system=data.system||{};
  const services=data.services||{};
  const cameras=data.cameras||{};

  let state=t('diag.state_stable');
  let className='ok';

  if(services.pidecoder!=='active'||services.web!=='active'){
    state=t('diag.state_error');
    className='error';
  }else if(
    system.throttled_hex!=='0x0' ||
    (system.temperature_c!=null && system.temperature_c>=80) ||
    (cameras.enabled??0)<(cameras.total??0)
  ){
    state=t('diag.state_warning');
    className='warn';
  }

  engineText.textContent=state;
  globalHealthDot.className='dot '+className;
}

async function refreshDiagnostics(){
  diagnosticsLogs.textContent=t('diag.loading');

  try{
    const lines=Number(diagnosticLogLines?.value||50);const data=await api(`/api/diagnostics?lines=${lines}`);
    renderDiagnostics(data);
    toast(t('diag.refreshed_toast'));
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
    toast(t('diag.report_copied'));
  }catch(_){
    diagnosticsCopyBuffer.classList.remove('hidden');
    diagnosticsCopyBuffer.value=diagnosticsLastReport;
    diagnosticsCopyBuffer.select();
    document.execCommand('copy');
    diagnosticsCopyBuffer.classList.add('hidden');
    toast(t('diag.report_copied'));
  }
}

oldp.addEventListener('input',validatePasswordChange);
newp.addEventListener('input',validatePasswordChange);
confirmp.addEventListener('input',validatePasswordChange);

cols.addEventListener('input',mosaicSettingsChanged);
rows.addEventListener('input',mosaicSettingsChanged);
fs.addEventListener('change',scheduleMosaicSave);
audioDefault.addEventListener('change',scheduleMosaicSave);

manualOnvifIp.addEventListener('input',setIpv4Validation);
manualOnvifPort.addEventListener('change',rememberManualOnvif);
manualOnvifPath.addEventListener('change',rememberManualOnvif);
restoreManualOnvif();

// --------------------------------------------------------------------------
// Mise à jour logicielle (onglet Système)
// --------------------------------------------------------------------------

async function updateStatusRefresh(){
  try{
    const s=await api('/api/update/status');
    if(s.state!=='idle'){
      renderUpdateStatus(s);
      if(s.state==='running'){
        updateDoneOrError=false;
        pollUpdateStatus();
      }
    }
  }catch(e){/* silencieux : ne pas gêner l'ouverture de l'onglet */}
}

async function updateCheck(){
  updateCheckButton.disabled=true;
  updateActions.classList.add('hidden');
  updateStatus.textContent=t('update.checking');
  try{
    renderUpdateCheck(await api('/api/update/check'));
  }catch(e){
    updateStatus.textContent=e.message;
  }finally{
    updateCheckButton.disabled=false;
  }
}

function renderUpdateCheck(r){
  if(!r.supported){
    updateStatus.textContent=
      r.reason==='not_a_git_repo'
        ?t('update.not_a_repo')+(r.error?' ('+r.error+')':'')
        :t('update.no_repo_path');
    return;
  }
  if(r.available===null){
    updateStatus.textContent=t('update.check_failed',{error:r.error||''});
    return;
  }
  if(r.error==='no_upstream'){
    updateStatus.textContent=t('update.no_upstream');
    return;
  }
  if(r.available){
    updateStatus.innerHTML=
      `<strong>${esc(t('update.available',{count:r.commits_behind??'?'}))}</strong>`+
      (r.latest_summary?`<br>${esc(r.latest_summary)}`:'');
    updateActions.classList.remove('hidden');
  }else{
    updateStatus.textContent=t('update.up_to_date');
  }
}

let updatePollTimer=null;

async function updateStart(){
  updateStartButton.disabled=true;
  try{
    await api('/api/update/start',{method:'POST',body:'{}'});
    updateDoneOrError=false;
    updateProgress.classList.remove('hidden');
    updateActions.classList.add('hidden');
    updateProgressText.textContent=t('update.step_git_pull');
    pollUpdateStatus();
  }catch(e){
    toast(e.message,true);
    updateStartButton.disabled=false;
  }
}

async function pollUpdateStatus(){
  clearTimeout(updatePollTimer);
  try{
    renderUpdateStatus(await api('/api/update/status'));
  }catch(e){
    // pidecoder-config.service redémarre en fin d'installation : la requête
    // échoue brièvement pendant la bascule, on continue simplement d'essayer.
  }
  if(!updateDoneOrError)updatePollTimer=setTimeout(pollUpdateStatus,2000);
}

let updateDoneOrError=false;

function renderUpdateStatus(s){
  if(s.state==='idle')return;
  updateProgress.classList.remove('hidden');
  const stepLabel=s.step==='git_pull'?t('update.step_git_pull'):s.step==='install'?t('update.step_install'):'';
  updateDoneOrError=(s.state==='done'||s.state==='error');
  if(s.state==='running'){
    updateProgressText.textContent=stepLabel;
  }else if(s.state==='done'){
    updateProgressText.textContent=t('update.done');
    updateStartButton.disabled=false;
    toast(t('update.done'));
  }else if(s.state==='error'){
    updateProgressText.textContent=t('update.failed',{step:stepLabel});
    updateStartButton.disabled=false;
    updateActions.classList.remove('hidden');
    toast(t('update.failed',{step:stepLabel}),true);
  }
  updateLog.textContent=s.log_tail||'';
  updateLog.scrollTop=updateLog.scrollHeight;
}

// --------------------------------------------------------------------------
// Réseau (onglet Réseau) : nom d'hôte, adresse IP, NTP, fuseau horaire
// --------------------------------------------------------------------------

let networkConnections=[];

async function networkRefresh(){
  try{
    renderNetworkStatus(await api('/api/network/status'));
  }catch(e){
    networkStatus.textContent=e.message;
  }
}

function renderNetworkStatus(s){
  networkStatus.textContent=s.nmcli_available?'':t('network.nmcli_unavailable');
  networkHostnameInput.value=s.hostname||'';

  networkConnections=s.connections||[];
  const previousSelection=networkConnectionSelect.value;
  networkConnectionSelect.innerHTML=networkConnections.map(c=>
    `<option value="${esc(c.name)}">${esc(c.name)}${c.active?' ✓':''}</option>`
  ).join('');
  const hasConnections=networkConnections.length>0;
  networkConnectionSelect.disabled=!s.nmcli_available||!hasConnections;
  networkMethodSelect.disabled=networkConnectionSelect.disabled;
  networkIpButton.disabled=networkConnectionSelect.disabled;

  if(hasConnections){
    const toSelect=networkConnections.find(c=>c.name===previousSelection)?previousSelection:networkConnections[0].name;
    networkConnectionSelect.value=toSelect;
    networkLoadConnectionFields(toSelect);
  }

  networkNtpEnabled.checked=!!(s.ntp&&s.ntp.enabled);
  networkNtpServersInput.value=((s.ntp&&s.ntp.servers)||[]).join(', ');

  if(!networkTimezoneSelect.dataset.loaded){
    networkLoadTimezones(s.timezone);
  }else if(s.timezone){
    networkTimezoneSelect.value=s.timezone;
  }

  renderNetworkPending(s.pending);
}

function networkLoadConnectionFields(name){
  const conn=networkConnections.find(c=>c.name===name);
  if(!conn)return;
  networkMethodSelect.value=conn.method;
  networkAddressInput.value=conn.address||'';
  networkGatewayInput.value=conn.gateway||'';
  networkDnsInput.value=(conn.dns||[]).join(', ');
  networkManualFields.classList.toggle('hidden',conn.method!=='manual');
}

function networkConnectionChanged(){
  networkLoadConnectionFields(networkConnectionSelect.value);
}

function networkMethodChanged(){
  networkManualFields.classList.toggle('hidden',networkMethodSelect.value!=='manual');
}

async function networkLoadTimezones(current){
  try{
    const r=await api('/api/network/timezones');
    networkTimezoneSelect.innerHTML=(r.timezones||[]).map(z=>
      `<option value="${esc(z)}">${esc(z)}</option>`
    ).join('');
    networkTimezoneSelect.dataset.loaded='1';
    if(current)networkTimezoneSelect.value=current;
  }catch(e){
    toast(e.message,true);
  }
}

async function networkChangeHostname(){
  const hostname=networkHostnameInput.value.trim();
  networkHostnameButton.disabled=true;
  try{
    const r=await api('/api/network/hostname',{method:'POST',body:JSON.stringify({hostname})});
    // On affiche tout de suite le plein écran à partir de la réponse de la
    // requête plutôt que d'attendre un prochain /api/network/status : le
    // script détaché a un délai de grâce de 2s avant de faire basculer son
    // fichier de statut de "pending" à "applied" (le temps que cette
    // réponse HTTP parte), pendant lequel /api/network/status ne
    // renverrait encore rien — inutile d'attendre pour prévenir l'utilisateur.
    renderNetworkPending({
      kind:'hostname',token:r.token,delay_seconds:r.delay_seconds,
      started_at:Date.now()/1000,new_value:hostname,
    });
  }catch(e){
    toast(e.message,true);
  }finally{
    networkHostnameButton.disabled=false;
  }
}

async function networkChangeIp(){
  networkIpButton.disabled=true;
  networkIpStatus.textContent='';
  try{
    const manual=networkMethodSelect.value==='manual';
    const body={
      connection:networkConnectionSelect.value,
      method:networkMethodSelect.value,
      address:manual?networkAddressInput.value.trim():'',
      gateway:manual?networkGatewayInput.value.trim():'',
      dns:manual?networkDnsInput.value.split(',').map(x=>x.trim()).filter(Boolean):[],
    };
    const r=await api('/api/network/ip',{method:'POST',body:JSON.stringify(body)});
    renderNetworkPending({
      kind:'ip',token:r.token,delay_seconds:r.delay_seconds,
      started_at:Date.now()/1000,
      new_value:{method:body.method,address:body.address,gateway:body.gateway,dns:body.dns},
    });
  }catch(e){
    networkIpStatus.textContent=e.message;
  }finally{
    networkIpButton.disabled=false;
  }
}

// --------------------------------------------------------------------------
// Changement réseau en attente : simple popup à cliquer (« Confirmer ») +
// lien de bascule vers la nouvelle adresse. Pas de compte à rebours affiché
// — le changement (nmcli/hostnamectl) est en pratique instantané, un timer
// qui défile n'apportait rien et donnait l'impression trompeuse qu'il
// fallait attendre. Le rétablissement automatique en cas de non-confirmation
// reste actif en arrière-plan (filet de sécurité), juste sans affichage
// seconde par seconde.
// --------------------------------------------------------------------------

let networkPendingToken=null;
let networkPendingDeadline=0;
let networkPendingSetAt=0;
let networkPendingRevertTimer=null;

function stopNetworkPendingUI(){
  clearTimeout(networkPendingRevertTimer);
  networkPendingRevertTimer=null;
  networkPendingToken=null;
  networkPendingOverlay.classList.add('hidden');
}

function renderNetworkPending(pending){
  if(!pending){
    // Ignore un "rien en attente" qui arriverait dans les toutes premières
    // secondes suivant une soumission côté client : le script détaché n'a
    // pas encore eu le temps de faire passer son fichier de statut de
    // "pending" à "applied" (délai de grâce de 2s), et /api/network/status
    // ne verrait donc rien pendant cette fenêtre — un changement d'onglet
    // rapide ne doit pas faire disparaître le popup qu'on vient tout juste
    // d'afficher.
    if(networkPendingToken&&Date.now()-networkPendingSetAt<5000)return;
    stopNetworkPendingUI();
    return;
  }

  const isNewChange=pending.token!==networkPendingToken;
  networkPendingToken=pending.token;
  networkPendingSetAt=Date.now();
  const anchor=pending.applied_at||pending.started_at||(Date.now()/1000);
  networkPendingDeadline=(anchor+pending.delay_seconds)*1000;

  if(!isNewChange){
    // Déjà affiché pour ce changement (ex. : nouvel appel à networkRefresh
    // pendant qu'il est toujours en attente) — juste se resynchroniser sur
    // la nouvelle échéance sans rien réafficher, et réarmer le filet de
    // sécurité sur la bonne échéance.
    scheduleNetworkPendingRevertCheck();
    return;
  }

  const kindLabel=pending.kind==='hostname'?t('network.pending_kind_hostname'):t('network.pending_kind_ip');
  networkPendingOverlayTitle.textContent=t('network.pending_title',{kind:kindLabel});
  networkPendingOverlayHint.textContent=t('network.pending_hint');
  networkPendingOverlay.classList.remove('hidden');
  renderNetworkPendingRedirectHint(pending);

  scheduleNetworkPendingRevertCheck();
}

function scheduleNetworkPendingRevertCheck(){
  clearTimeout(networkPendingRevertTimer);
  const resolvedToken=networkPendingToken;
  // Pas de compte à rebours visible : un seul minuteur silencieux, armé sur
  // l'échéance réelle (calculée côté serveur), avec une marge pour laisser
  // le script détaché finir sa propre boucle de rétablissement.
  const delay=Math.max(0,networkPendingDeadline-Date.now())+3000;
  networkPendingRevertTimer=setTimeout(()=>{
    if(networkPendingToken!==resolvedToken)return; // déjà confirmé entre-temps
    stopNetworkPendingUI();
    toast(t('network.pending_auto_reverted'),true);
    networkRefresh();
  },delay);
}

function buildSameOriginUrl(host){
  return `${location.protocol}//${host}${location.port?':'+location.port:''}${location.pathname}`;
}

function renderNetworkPendingRedirectHint(pending){
  let url=null,label='';
  if(pending.kind==='ip'&&pending.new_value&&pending.new_value.method==='manual'&&pending.new_value.address){
    const host=pending.new_value.address.split('/')[0];
    url=buildSameOriginUrl(host);
    label=t('network.pending_try_ip',{address:host});
  }else if(pending.kind==='hostname'&&pending.new_value){
    const host=pending.new_value+'.local';
    url=buildSameOriginUrl(host);
    label=t('network.pending_try_hostname',{hostname:host});
  }
  if(url){
    networkPendingRedirectHint.innerHTML=`<a href="${esc(url)}">${esc(label)}</a>`;
    networkPendingRedirectHint.classList.remove('hidden');
  }else{
    networkPendingRedirectHint.classList.add('hidden');
    networkPendingRedirectHint.innerHTML='';
  }
}

async function networkConfirmPending(){
  if(!networkPendingToken)return;
  const token=networkPendingToken;
  networkPendingConfirmButton.disabled=true;
  try{
    await api('/api/network/confirm',{method:'POST',body:JSON.stringify({token})});
    toast(t('network.pending_confirmed'));
    stopNetworkPendingUI();
    networkRefresh();
  }catch(e){
    toast(e.message,true);
  }finally{
    networkPendingConfirmButton.disabled=false;
  }
}

async function networkApplyNtp(){
  networkNtpButton.disabled=true;
  networkNtpStatus.textContent='';
  try{
    const servers=networkNtpServersInput.value.split(',').map(x=>x.trim()).filter(Boolean);
    await api('/api/network/ntp',{method:'POST',body:JSON.stringify({enabled:networkNtpEnabled.checked,servers})});
    toast(t('network.ntp_applied'));
    networkRefresh();
  }catch(e){
    networkNtpStatus.textContent=e.message;
  }finally{
    networkNtpButton.disabled=false;
  }
}

async function networkApplyTimezone(){
  networkTimezoneButton.disabled=true;
  try{
    await api('/api/network/timezone',{method:'POST',body:JSON.stringify({timezone:networkTimezoneSelect.value})});
    toast(t('network.timezone_applied'));
  }catch(e){
    toast(e.message,true);
  }finally{
    networkTimezoneButton.disabled=false;
  }
}

setInterval(serviceStatus,3000);serviceStatus();
setInterval(sysInfo,3000);boot().catch(e=>{toast(e.message,true);showLogin()});

// Ré-applique les traductions statiques (index.html) au chargement, et
// ré-exécute les rendus dynamiques concernés quand la langue change (le
// contenu de ces fonctions est généré en JS, donc data-i18n seul ne suffit
// pas à les traduire).
window.I18N.applyTranslations();

window.onLanguageChange=function(){
  window.I18N.applyTranslations();
  updateVersionLabel();

  if(!app.classList.contains('hidden')){
    render();
    renderMosaic();

    if(!document.getElementById('onvif').classList.contains('hidden')){
      renderOnvifDiscovery();
    }

    sysInfo();
    serviceStatus();
  }

  renderNotificationHistory();
};
