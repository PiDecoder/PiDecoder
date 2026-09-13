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
function read(d,i){let b={user:d.querySelector('.user').value.trim(),pwd:d.querySelector('.pwd').value,host:d.querySelector('.host').value.trim(),port:d.querySelector('.port').value.trim(),path:d.querySelector('.path').value.trim()},result={name:d.querySelector('.name').value.trim()||'Caméra',enabled:d.querySelector('.en').checked,grid_url:build(b,d.querySelector('.gw').value,d.querySelector('.gh').value,d.querySelector('.gf').value,d.querySelector('.gu').value.trim()),focus_url:build(b,d.querySelector('.fw').value,d.querySelector('.fh').value,d.querySelector('.ff').value,d.querySelector('.fu').value.trim())},previous=cfg.cameras[i];if(previous&&previous.onvif&&typeof previous.onvif==='object')result.onvif=previous.onvif;return result}
function sync(){cfg.cameras=[...document.querySelectorAll('.camera')].map((d,i)=>read(d,i))}
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
        toast('Aucun preset sélectionné',true);
        return;
      }

      stopActivePtz();
      presetButton.disabled=true;
      presetButton.innerHTML=
        '<span class="spinner"></span>Déplacement…';

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

        toast('✔ Preset PTZ appelé');

      }catch(error){
        toast(error.message,true);

      }finally{
        presetButton.disabled=!(presets||[]).length;
        presetButton.textContent='Aller au preset';
      }
    };
  }
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
      device.name || device.hardware || `Caméra ${device.ip||''}`;

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
        `${esc(preset.name||preset.token||'Preset')}</option>`
      )
      .join('');

    const ptzPanel=ptzAvailable?`
      <div class="backupbox ptz-panel">
        <div class="ptz-panel-title">
          <strong>Commande PTZ</strong>
          <span class="badge ptz">${esc(ptzProfile.name||ptzProfile.token)}</span>
        </div>

        <div class="ptzpad" aria-label="Commandes directionnelles PTZ">
          <div class="ptz-empty"></div>
          <button type="button" class="secondary" data-ptz-action="up" title="Monter">▲</button>
          <div class="ptz-empty"></div>

          <button type="button" class="secondary" data-ptz-action="left" title="Gauche">◀</button>
          <button type="button" class="secondary" data-ptz-action="stop" title="Arrêter">■</button>
          <button type="button" class="secondary" data-ptz-action="right" title="Droite">▶</button>

          <div class="ptz-empty"></div>
          <button type="button" class="secondary" data-ptz-action="down" title="Descendre">▼</button>
          <div class="ptz-empty"></div>
        </div>

        <div class="ptz-zoom">
          <button type="button" class="secondary" data-ptz-action="zoomin">Zoom +</button>
          <button type="button" class="secondary" data-ptz-action="zoomout">Zoom −</button>
        </div>

        ${ptzPresets.length?`
          <div class="ptz-presets">
            <div>
              <label>Preset</label>
              <select class="ptz-preset">${ptzPresetOptions}</select>
            </div>
            <button type="button" class="secondary ptz-goto">Aller au preset</button>
          </div>
        `:`
          <div class="muted ptz-help">Aucun preset ONVIF détecté pour ce profil.</div>
        `}

        <div class="muted ptz-help">
          Maintiens une commande pour déplacer la caméra. Le relâchement envoie immédiatement Stop.
        </div>
      </div>
    `:'';

    box.innerHTML=`
      <div class="row" style="justify-content:space-between">
        <div>
          <div class="onvif-title">${esc([info.Manufacturer,info.Model].filter(Boolean).join(' ')||device.name||device.hardware||'Équipement ONVIF')}</div>
          <div style="margin-top:7px">
            <span class="badge">ONVIF</span>
            <span class="badge">${esc(device.ip||'IP inconnue')}</span>
            ${identification?'<span class="badge ptz">Identifiée</span>':''}
            ${ptzAvailable?'<span class="badge ptz">PTZ</span>':''}
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

          ${ptzPanel}

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
    toast('Identifie d’abord la caméra',true);
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
  button.textContent='Enregistrement…';

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
