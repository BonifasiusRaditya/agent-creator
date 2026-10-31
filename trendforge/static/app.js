const paths = {
  home:'<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
  grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  film:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h4m-4 8h4M17 8h4m-4 8h4"/>',
  download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
  upload:'<path d="M12 16V3m-5 5 5-5 5 5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
  arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
  chevron:'<path d="m9 5 7 7-7 7"/>',
  up:'<path d="m6 15 6-6 6 6"/>', down:'<path d="m6 9 6 6 6-6"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  settings:'<path d="m9 3-1 3-3 1 1 4-1 3 3 2 1 4h5l1-4 3-2-1-3 1-4-3-1-1-3z"/><circle cx="11.5" cy="11.5" r="3"/>',
  link:'<path d="m10 13 4-4m-6 7-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2-2 1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0" transform="translate(1 1)"/>',
  spark:'<path d="m12 3 2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6zM20 2v4m-2-2h4"/>',
  check:'<path d="m5 12 4 4L20 5"/>',
  circleCheck:'<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>',
  trash:'<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
  edit:'<path d="m16 3 5 5-12 12H4v-5zM13 6l5 5"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  play:'<path d="m8 4 13 8-13 8z"/>',
  copy:'<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
  external:'<path d="M14 3h7v7m0-7L10 14M10 4H4v16h16v-6"/>',
  subtitles:'<rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 11h4m4 0h4M6 15h7m3 0h2"/>',
  user:'<circle cx="12" cy="8" r="3"/><path d="M5 21v-3a7 7 0 0 1 14 0v3"/>',
  logout:'<path d="M9 4H4v16h5m6-12 4 4-4 4m-7-4h11"/>',
  menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',
  alert:'<path d="m12 3 10 18H2zM12 9v5m0 3v1"/>',
  mute:'<path d="m11 5-6 4H2v6h3l6 4zm5 4 6 6m-6 0 6-6"/>',
  folder:'<path d="M3 7V4h7l3 3h8v13H3z"/>',
  youtube:'<rect x="2" y="5" width="20" height="14" rx="4"/><path d="m10 9 5 3-5 3z"/>',
  shield:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM8 12l3 3 5-6"/>',
};
const icon = (name,size=18) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]||paths.film}</svg>`;
const esc = value => String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const brand = `<a class="brand" href="/" data-nav><img src="/static/mark.svg" alt=""><span>trend<span>forge</span></span></a>`;
const steps = ['Discover','Brief','Footage','Edit','Subtitles','Export'];
const stepPaths = ['discover','brief','footage','edit','subtitles','export'];
const phaseNames = {CONTEXT_READY:'New project',RESEARCH_READY:'Research ready',BRIEF_DRAFT:'Writing',BRIEF_APPROVED:'Brief approved',ASSETS_READY:'Footage ready',PLAN_DRAFT:'Planning',PLAN_APPROVED:'Edit approved',DRAFT_READY:'Draft ready',CAPTIONS_REVIEW:'Review subtitles',READY_TO_EXPORT:'Ready to export',EXPORT_READY:'Exported',USER_CONFIRMED_READY:'Ready to upload'};
const S = {csrf:'',projects:[],settings:{},project:null,route:'/',step:0,search:'',busy:false,selected:new Set(),uploading:false,queue:[],mobile:false,polling:false,systemJob:null};
const stockName = provider => provider === 'pixabay' ? 'Pixabay' : 'Pexels';
const stockHome = provider => provider === 'pixabay' ? 'https://pixabay.com/' : 'https://www.pexels.com/';
const app = document.querySelector('#app');
const dialog = document.querySelector('#dialog');
dialog.addEventListener('close',()=>{delete dialog.dataset.agentRequest;});
const fmtDate = value => value ? new Intl.DateTimeFormat('en',{month:'short',day:'numeric'}).format(new Date(value)) : '—';
const fmtTime = value => value ? new Intl.DateTimeFormat('en',{hour:'2-digit',minute:'2-digit'}).format(new Date(value)) : '—';
const duration = seconds => `${Math.floor(seconds/60)}:${String(Math.round(seconds%60)).padStart(2,'0')}`;
const bytes = value => value>=1024*1024 ? `${(value/1024/1024).toFixed(1)} MB` : `${Math.round(value/1024)} KB`;
const number = value => value==null?'Unavailable':new Intl.NumberFormat('en',{notation:'compact',maximumFractionDigits:1}).format(Number(value));
const badge = (text,accent=false) => `<span class="badge ${accent?'badge-accent':''}">${accent?'<span class="dot"></span>':''}${esc(text)}</span>`;
const button = (action,text,kind='primary',extra='') => `<button type="button" class="btn ${kind==='primary'?'btn-primary':kind==='quiet'?'btn-quiet':''}" data-action="${action}" ${extra}>${text}</button>`;

async function api(path, options={}) {
  const headers = new Headers(options.headers||{});
  if (S.csrf) headers.set('X-CSRF-Token', S.csrf);
  if (options.body && !(options.body instanceof FormData)) {headers.set('Content-Type','application/json');options.body=JSON.stringify(options.body);}
  const response = await fetch('/api/v1'+path,{...options,headers,credentials:'same-origin'});
  if (response.status===204) return null;
  let data;
  try { data=await response.json(); } catch { throw new Error('The service returned an unexpected response. Reload and try again.'); }
  if (!response.ok) {
    const error = new Error(data.error?.message||'This action could not be completed.');
    error.code=data.error?.code; error.details=data.error?.details;
    if (response.status===401 && path!=='/session') {S.csrf='';renderAuth(false);}
    throw error;
  }
  return data;
}

function toast(message,error=false) {
  const el=document.createElement('div');el.className='toast'+(error?' error':'');el.setAttribute('role',error?'alert':'status');
  el.innerHTML=`${icon(error?'alert':'circleCheck',18)}<span>${esc(message)}</span>`;
  document.querySelector('#toasts').append(el);setTimeout(()=>el.remove(),error?10000:5000);
}
async function busy(label,fn) {
  if (S.busy) return;
  S.busy=true;document.body.dataset.busy='true';
  const bar=document.createElement('div');bar.className='busy-indicator';bar.setAttribute('role','status');bar.setAttribute('aria-label',label);document.body.append(bar);
  try {return await fn();} catch(error) {toast(error.message,true);if(error.code==='STALE_REVISION'&&S.project&&!dirty()) await refreshProject();}
  finally {S.busy=false;delete document.body.dataset.busy;bar.remove();}
}
function dirty() {return !!document.querySelector('form[data-edit][data-dirty="true"]');}
function canLeave() {return !dirty()||confirm('Discard your unsaved changes?');}
async function navigate(path,replace=false) {
  if (!canLeave()) return;
  S.mobile=false;S.search='';
  if(replace) history.replaceState({},'',path);else history.pushState({},'',path);
  await route();window.scrollTo({top:0,behavior:'instant'});
}
async function refreshData() {
  [S.projects,S.settings]=await Promise.all([api('/projects'),api('/settings')]);
}
async function refreshProject(render=true) {
  if (!S.project) return;
  S.project=await api(`/projects/${S.project.id}`);
  S.projects=await api('/projects');
  if(render) renderShell(projectPage());
}
function footer(){return '<footer class="page-footer"><span>Made for the way you create.</span><span>Research. Write. Edit. Publish.</span></footer>';}
function sidebar() {
  const isProject=S.route.startsWith('/projects/');
  const nav=[['/','home','Overview'],['/projects','grid','All projects'],['/exports','download','Exports'],['/connections','link','Connections']];
  return `<aside class="sidebar ${S.mobile?'open':''}">${brand}<div class="sidebar-label">Workspace</div><nav aria-label="Main navigation">${nav.map(([url,ico,title])=>`<a href="${url}" class="nav-link ${(S.route===url||(url==='/projects'&&isProject))?'active':''}" data-nav>${icon(ico,17)}${title}${url==='/projects'&&S.projects.length?`<span class="count">${S.projects.length}</span>`:''}</a>`).join('')}</nav>
    <div class="sidebar-label spread">Recent projects<button class="icon-btn" aria-label="Create project" data-action="new-project">${icon('plus',13)}</button></div>
    ${S.projects.slice(0,5).map(p=>`<a class="sidebar-project ${S.project?.id===p.id&&isProject?'selected':''}" href="/projects/${p.id}/discover" data-nav><span class="project-dot"></span><span>${esc(p.niche)}</span></a>`).join('')||'<p class="small muted" style="padding:0 14px;font-size:11px">Your projects will appear here.</p>'}
    <div class="sidebar-bottom"><div class="connection-card"><h4>${S.settings.ai_engine==='workbuddy'?'Create with WorkBuddy':'Your creative tools'}</h4><p>${S.settings.ai_engine==='workbuddy'?'Your agent writes the story. Review and produce it here.':'Manage your writing, research and speech tools.'}</p><a href="/connections" data-nav>View connections${icon('arrow',13)}</a></div>
    <div class="local-user"><span class="avatar">${icon('user',15)}</span><div><p>Your workspace</p><small>On this device</small></div><button class="icon-btn" data-action="sign-out" aria-label="Sign out" style="margin-left:auto">${icon('logout',15)}</button></div></div></aside>`;
}
function renderShell(content) {
  const title=S.route==='/connections'?'Connections':S.route==='/exports'?'Exports':S.route==='/projects'?'All projects':S.route.startsWith('/projects/')?S.project?.niche||'Project':'Overview';
  app.innerHTML=`${sidebar()}<div class="side-overlay ${S.mobile?'visible':''}" data-action="toggle-sidebar"></div><div class="main-shell"><header class="topbar"><div class="row"><button class="icon-btn mobile-toggle" data-action="toggle-sidebar" aria-label="Open navigation">${icon('menu',20)}</button><div class="breadcrumbs"><span>Workspace</span>${icon('chevron',10)}<span>${esc(title.length>40?title.slice(0,37)+'…':title)}</span></div></div><div class="topbar-right"><div class="search">${icon('search',15)}<input id="global-search" aria-label="Search projects" placeholder="Search projects…" value="${esc(S.search)}"><kbd>Ctrl K</kbd></div><span class="topbar-sep"></span><a class="icon-btn" aria-label="Manage connections" href="/connections" data-nav>${icon('settings',18)}</a></div></header><main id="main" class="page" tabindex="-1">${content}</main></div>`;
  bindMedia();
}
function art(){return `<div class="hero-art" aria-hidden="true"><div class="art-grid"></div><div class="art-ring"></div><span class="art-format">9:16</span><div class="art-phone"><div class="art-land"></div><div class="art-land second"></div><div class="art-caption"><i></i><i></i></div></div><div class="art-chip first">${icon('spark',15)}An idea takes shape</div><div class="art-chip second">${icon('subtitles',16)}Every word, in place</div><span class="art-captionline">A format made for your next story.</span></div>`;}
function projectCard(p) {
  return `<a class="project-card" href="/projects/${p.id}/${stepPaths[nextStep(p)]}" data-nav><div class="project-card-art">${icon('film',47)}${badge(phaseNames[p.phase]||p.phase,p.phase==='USER_CONFIRMED_READY')}</div><div class="project-card-body"><h3>${esc(p.niche)}</h3><p class="card-type">${p.target_duration_seconds}s · ${p.platform==='both'?'Shorts & Reels':p.platform==='shorts'?'YouTube Shorts':'Instagram Reels'}</p><div class="meta"><span>${p.asset_count||0} clips · ${p.export_count||0} exports</span><span>${fmtDate(p.updated_at)}</span></div></div></a>`;
}
function nextStep(p) {return ({CONTEXT_READY:0,RESEARCH_READY:0,BRIEF_DRAFT:1,BRIEF_APPROVED:2,ASSETS_READY:3,PLAN_DRAFT:3,PLAN_APPROVED:3,DRAFT_READY:4,CAPTIONS_REVIEW:4,READY_TO_EXPORT:5,EXPORT_READY:5,USER_CONFIRMED_READY:5})[p.phase]||0;}
function projectsList(all=false) {
  const projects=S.projects.filter(p=>!S.search||[p.niche,p.audience,p.goal].join(' ').toLowerCase().includes(S.search.toLowerCase()));
  if(!projects.length) return `<div class="empty-projects"><div class="empty-icon">${icon(S.search?'search':'film',28)}</div><div><h3>${S.search?'No matching projects':'Your next story starts here'}</h3><p>${S.search?'Try a different topic or create a new project.':'Bring an idea and a few clips. We’ll help you turn them into something ready to share.'}</p>${button('new-project',`${icon('plus',15)}Create your first project`)}</div></div>`;
  return `<div class="project-grid">${(all?projects:projects.slice(0,6)).map(projectCard).join('')}</div>`;
}
function homePage(all=false) {
  const exports=S.projects.reduce((sum,p)=>sum+(p.export_count||0),0),clips=S.projects.reduce((sum,p)=>sum+(p.asset_count||0),0);
  return `${all?`<div class="spread page-actions"><div><h1 class="page-title">Your projects</h1><p class="muted" style="margin:0">Every story, from the first thought to the final frame.</p></div>${button('new-project',`${icon('plus',15)}New project`)}</div>`:`<div class="spread" style="margin-bottom:23px"><div><p class="eyebrow" style="margin-bottom:5px">Your creative workspace</p><h2 style="font-size:22px;margin:0;letter-spacing:-.04em">Let’s make something worth watching.</h2></div></div><section class="hero"><div class="hero-copy"><h1>Find your angle.<br>Draft your story.</h1><p>Find references, develop original scripts and draft posting captions. Edit in your favorite app, then return for subtitles—or try our optional editor.</p>${button('new-project',`Start creating${icon('arrow',16)}`,'primary')}</div>${art()}</section><div class="stats"><div class="stat"><span class="stat-icon">${icon('folder',19)}</span><div><div class="stat-value">${S.projects.length}</div><div class="stat-label">Projects in your workspace</div></div></div><div class="stat"><span class="stat-icon">${icon('film',19)}</span><div><div class="stat-value">${clips}</div><div class="stat-label">Clips brought to life</div></div></div><div class="stat"><span class="stat-icon">${icon('download',19)}</span><div><div class="stat-value">${exports}</div><div class="stat-label">Finished video exports</div></div></div></div>`}
  <div class="section-head"><div><h2>${all?'All projects':'Recent projects'}</h2><p>${S.projects.length?'Pick up where you left off.':'A little inspiration. A few clips. Your next creation.'}</p></div>${!all?'<a class="inline-link" href="/projects" data-nav>View all projects'+icon('arrow',14)+'</a>':''}</div><div id="project-list">${projectsList(all)}</div>
  ${!all?`<div class="guide-grid"><div class="guide"><span class="guide-number">01</span><div><h4>Find your angle</h4><p>Explore YouTube references and develop an idea that fits your audience.</p></div></div><div class="guide"><span class="guide-number">02</span><div><h4>Build your story</h4><p>Draft a script and posting caption, then edit in your favorite app.</p></div></div><div class="guide"><span class="guide-number">03</span><div><h4>Give it the finishing touch</h4><p>Upload your finished edit for subtitles, or try our optional editor.</p></div></div></div>`:''}${footer()}`;
}
function renderAuth(setup) {
  document.title=setup?'Create your workspace — TrendForge':'Welcome back — TrendForge';
  app.innerHTML=`<main class="auth-layout" id="main"><section class="auth-left">${brand}<form class="auth-form" id="auth-form" data-setup="${setup}"><span class="eyebrow">${setup?'A space for your next idea':'Your stories are waiting'}</span><h1>${setup?'Make room for<br>your next story.':'Welcome back.'}</h1><p>${setup?'Set a password to keep your workspace, connections, and creative work private on this device.':'Sign in to pick up where you left off.'}</p><div class="field"><label for="password">${setup?'Create a password':'Password'}</label><input id="password" name="password" type="password" autocomplete="${setup?'new-password':'current-password'}" minlength="8" maxlength="200" required placeholder="${setup?'At least 8 characters':'Enter your password'}"></div>${setup?'<div class="field"><label for="confirm-password">Confirm password</label><input id="confirm-password" name="confirm_password" type="password" autocomplete="new-password" minlength="8" required placeholder="Enter your password again"></div>':''}<div id="auth-error" class="form-error" role="alert"></div><button type="submit" class="btn btn-primary btn-large">${setup?'Create workspace':'Sign in'}${icon('arrow',16)}</button><div class="auth-note">Video editing runs on your device.<br>Create with WorkBuddy, then review and produce your video here.</div></form><small class="auth-note">TrendForge · A little less work. A lot more creating.</small></section><section class="auth-art" aria-hidden="true"><div class="art-grid"></div><div class="art-ring"></div><div class="art-phone"><div class="art-land"></div><div class="art-land second"></div><div class="art-caption"><i></i><i></i></div></div><h2>From a spark.<br>To a story.</h2><p>Your ideas deserve more time in the world, and less time on a to-do list.</p></section></main>`;
}
function connectionPage() {
  const s=S.settings,workbuddy=s.ai_engine==='workbuddy';
  return `<div class="spread page-actions"><div><h1 class="page-title">Your creative tools.</h1><p class="muted" style="margin:0">WorkBuddy handles the thinking. Your workspace brings it to life.</p></div>${badge('Managed for you',true)}</div>
  <div class="connection-grid"><div class="panel connection-panel agent-connection"><div class="connection-title"><div class="service-icon">${icon('spark',23)}</div><div><h3>Tencent WorkBuddy</h3><p>Ideas, research, briefs and scripts</p></div>${badge(workbuddy?'Primary AI engine':'Available connector',workbuddy)}</div><p class="small">Create with WorkBuddy using the TrendForge connector. It reads your project, researches references, and saves original ideas and scripts back here for your review.</p><ol class="setup-steps"><li>Add the TrendForge connector to WorkBuddy once.</li><li>Request ideas from a project and copy the task into WorkBuddy.</li><li>Return here to review the result, add footage, and make your video.</li></ol><div class="row wrap">${button('show-connector',`${icon('copy',14)}Copy connector configuration`,'secondary')}<a class="btn" href="/api/v1/settings/connector-package" download>Download connector</a><a class="inline-link" href="/api/v1/settings/agent-skill" download>Download agent skill${icon('download',13)}</a></div><div id="connector-code"></div><p class="hint" style="margin-top:18px">${s.workbuddy_last_seen?'Connector last contacted this workspace at '+esc(fmtTime(s.workbuddy_last_seen))+'.':'Waiting for the first connection from WorkBuddy. A configured engine does not mean the connector has been installed.'}</p></div>
  <div class="panel connection-panel"><div class="connection-title"><div class="service-icon">${icon('youtube',23)}</div><div><h3>YouTube research</h3><p>Recent references in your niche</p></div>${badge(s.youtube_configured?'Configured':'Setup needed',s.youtube_configured)}</div><p class="small">Public video metadata and source links for creative context. Service access is managed by the workspace owner; you do not need to enter an API key.</p>${button('test-youtube','Test connection','secondary',s.youtube_configured?'':'disabled')}</div>
  <div class="panel connection-panel"><div class="connection-title"><div class="service-icon">${icon('film',21)}</div><div><h3>${stockName(s.stock_provider)} footage</h3><p>Optional stock clips</p></div>${badge(s.stock_configured?'Configured':'Not enabled',s.stock_configured)}</div><p class="small">Find stock footage alongside your own clips. Service access is managed by the workspace owner. Source links and creator credits stay attached.</p>${button('test-stock','Test connection','secondary',s.stock_configured?'':'disabled')}</div>
  ${!workbuddy?`<div class="panel connection-panel"><div class="connection-title"><div class="service-icon">${icon('spark',21)}</div><div><h3>Alternative writing provider</h3><p>Enabled by the workspace owner</p></div>${badge(s.ai_connected?'Configured':'Setup needed',s.ai_connected)}</div><p class="small">The workspace is currently using an OpenAI-compatible provider for website writing requests.</p>${button('test-ai','Test connection','secondary',s.ai_connected?'':'disabled')}</div>`:''}
  <form class="panel connection-panel" id="speech-settings" data-edit><div class="connection-title"><div class="service-icon">${icon('subtitles',22)}</div><div><h3>Speech & subtitles</h3><p>Indonesian transcription on your device</p></div>${badge(s.speech_models_ready?.includes(s.speech_model)?'Downloaded':'Setup needed',s.speech_models_ready?.includes(s.speech_model))}</div><div class="field"><label for="speech-model">Multilingual speech model</label><select id="speech-model" name="speech_model" ${s.configuration_sources?.speech_model==='environment'?'disabled':''}>${['tiny','base','small'].map((m,i)=>`<option value="${m}" ${s.speech_model===m?'selected':''}>${['Tiny — fastest, lower accuracy','Base — balanced','Small — more accurate, slower'][i]}</option>`).join('')}</select><span class="hint">Download once. No speech API key is needed.</span></div><div class="spread">${button('download-model',`${icon('download',14)}Download model`,'secondary',s.active_job?'disabled':'')}${s.configuration_sources?.speech_model==='environment'?'':`<button type="submit" class="btn btn-primary">Save model</button>`}</div><div id="model-job-status">${s.active_job?.type==='model_download'?jobBanner(s.active_job,true):''}</div></form>
  <div class="panel connection-panel" style="grid-column:1/-1"><div class="connection-title" style="margin-bottom:14px"><div class="service-icon">${icon('shield',21)}</div><div><h3>Your files, your workspace</h3><p>Local video and speech processing</p></div>${badge(s.ffmpeg_available?'Video engine installed':'Video engine unavailable',s.ffmpeg_available)}</div><p class="storage-note">WorkBuddy receives project context and reference metadata through the connector. Video editing and speech processing run locally. Files follow your device’s folder-sync settings.</p><p class="storage-note" style="margin-bottom:0"><strong>Project database</strong><br>${s.database_backend==='turso'?'Turso Cloud':'SQLite on this device'}<br><br><strong>Storage folder</strong><br>${esc(s.storage_path)}<br><span class="muted">Delete a project to remove its workspace files. Separately downloaded copies stay with you.</span></p></div></div>${footer()}`;
}

function openAgentDialog(request) {
  S.agentRequest=request;
  dialog.dataset.agentRequest=request.id;
  dialog.innerHTML=`<div class="dialog-head"><div><h2 id="dialog-title">Continue in WorkBuddy</h2><p>Your ${request.task==='ideas'?'ideas':'brief and script'} will appear in this project.</p></div><button class="icon-btn" data-action="close-dialog" aria-label="Close">${icon('close',18)}</button></div><div class="dialog-body"><p class="small">Copy this task into WorkBuddy with the TrendForge connector enabled. Keep TrendForge running while the agent works.</p><label for="agent-prompt">Your WorkBuddy task</label><textarea id="agent-prompt" class="agent-prompt" readonly rows="7">${esc(request.prompt)}</textarea><p class="hint">The website is waiting for WorkBuddy to save a result. Your task is saved, so you can close this window and return later.</p><a class="inline-link" href="/connections" data-nav>Set up the connector${icon('arrow',13)}</a></div><div class="dialog-foot"><button class="btn" data-action="close-dialog">Close</button>${button('copy-agent-task',`${icon('copy',14)}Copy task`)}</div>`;
  dialog.showModal();
}
function agentRequestBanner() {
  const r=S.project.agent_request;
  if(!r||!['pending','stale'].includes(r.status))return '';
  return `<div class="callout agent-request">${icon('spark',20)}<div style="flex:1"><strong>${r.status==='pending'?'Waiting for WorkBuddy':'Writing request needs a refresh'}</strong><p>${r.status==='pending'?'Continue the saved task in WorkBuddy. Its result will appear here automatically.':esc(r.message)}</p></div><div class="row">${r.status==='pending'?button('show-agent-task','View task','secondary'):''}${button('cancel-agent-task','Dismiss','quiet',`data-id="${esc(r.id)}"`)}</div></div>`;
}

function openProjectDialog(edit=false) {
  const p=edit?S.project:{};
  dialog.innerHTML=`<form id="project-form" data-editing="${edit}"><div class="dialog-head"><div><h2 id="dialog-title">${edit?'Project details':'Start a new story.'}</h2><p>${edit?'Changing these details creates a new brief and edit flow.':'A little context goes a long way.'}</p></div><button type="button" class="icon-btn" data-action="close-dialog" aria-label="Close">${icon('close',18)}</button></div><div class="dialog-body"><div class="field"><label for="project-niche">What is your video about?</label><input id="project-niche" name="niche" minlength="2" maxlength="100" required value="${esc(p.niche)}" placeholder="e.g. Practical study habits"></div><div class="field"><label for="project-audience">Who are you creating for?</label><input id="project-audience" name="audience" minlength="2" maxlength="200" required value="${esc(p.audience)}" placeholder="e.g. University students in Indonesia"></div><div class="field"><label for="project-goal">What should your audience take away?</label><textarea id="project-goal" name="goal" minlength="5" maxlength="500" required placeholder="Describe the idea, feeling, or action you want to leave them with.">${esc(p.goal)}</textarea></div><div class="grid-3"><div class="field"><label for="project-platform">Platform</label><select id="project-platform" name="platform"><option value="both" ${p.platform==='both'?'selected':''}>Shorts & Reels</option><option value="shorts" ${p.platform==='shorts'?'selected':''}>YouTube Shorts</option><option value="reels" ${p.platform==='reels'?'selected':''}>Instagram Reels</option></select></div><div class="field"><label for="project-duration">Video length</label><select id="project-duration" name="target_duration_seconds">${[30,45,60].map(n=>`<option value="${n}" ${p.target_duration_seconds===n?'selected':''}>${n} seconds</option>`).join('')}</select></div><div class="field"><label for="project-language">Writing language</label><select id="project-language" name="language"><option value="id" ${p.language==='id'?'selected':''}>Indonesian</option><option value="en" ${p.language==='en'?'selected':''}>English</option></select></div></div></div><div class="dialog-foot"><button type="button" class="btn" data-action="close-dialog">Cancel</button><button class="btn btn-primary" type="submit">${edit?'Save project details':'Create project'}${icon('arrow',15)}</button></div></form>`;
  dialog.showModal();setTimeout(()=>document.querySelector('#project-niche')?.focus(),30);
}

function jobBanner(job,system=false) {
  if(!job||!['queued','running','cancelling'].includes(job.status))return '';
  return `<div class="job-banner"><span class="spinner"></span><div class="job-copy"><strong id="job-status-text">${esc(job.stage)}</strong><p id="job-elapsed">You can keep this page open or come back later.</p></div>${button(system?'cancel-system-job':'cancel-job','Cancel','secondary',`data-id="${job.id}"`)}</div>`;
}
function guarded(title,description,step) {return `<div class="panel empty-state">${icon('film',38)}<h3>${title}</h3><p>${description}</p>${button('goto-step',`Go to ${steps[step].toLowerCase()}${icon('arrow',14)}`,'primary',`data-step="${step}"`)}</div>`;}
function projectPage() {
  const p=S.project;
  const current=nextStep(p);
  const banner=p.active_job?jobBanner(p.active_job):p.last_job?.status==='failed'?`<div class="callout error">${icon('alert',19)}<div style="flex:1"><strong>One step needs attention.</strong><p>${esc(p.last_job.error?.message||'Try this step again.')}</p></div>${button('retry-job','Try again','secondary')}</div>`:'';
  return `<div class="spread page-actions"><div><div class="row" style="margin-bottom:11px"><a class="inline-link muted" href="/projects" data-nav>Projects</a>${icon('chevron',11)}${badge(phaseNames[p.phase]||p.phase,p.phase==='USER_CONFIRMED_READY')}</div><h1 class="page-title">${esc(p.niche)}</h1><p class="muted" style="margin:0;font-size:12px">${p.target_duration_seconds}-second video · ${p.platform==='both'?'YouTube Shorts & Instagram Reels':p.platform==='shorts'?'YouTube Shorts':'Instagram Reels'} · ${p.language==='id'?'Indonesian':'English'} writing</p></div><div class="row">${button('edit-project',`${icon('edit',13)}Details`,'secondary',p.active_job?'disabled':'')}<button class="icon-btn" data-action="delete-project" aria-label="Delete project" ${p.active_job?'disabled':''}>${icon('trash',16)}</button></div></div><nav class="stepper" aria-label="Production steps">${steps.map((text,i)=>`<button class="step ${i===S.step?'active':i<current&&!(i===3&&p.draft?.source==='external_edit')?'complete':''}" data-action="goto-step" data-step="${i}" ${i===S.step?'aria-current="step"':''}><span class="step-number">${i<current&&i!==S.step&&!(i===3&&p.draft?.source==='external_edit')?icon('check',11):String(i+1).padStart(2,'0')}</span>${text}</button>`).join('')}</nav>${banner}${agentRequestBanner()}<section class="workflow-body">${[discoverPage,briefPage,footagePage,editPage,subtitlesPage,exportPage][S.step]()}${[1,5].includes(S.step)?postingCaptionPanel():''}</section>${footer()}`;
}

function discoverPage() {
  const p=S.project,run=p.research?.at(-1),items=[...new Map((p.research||[]).flatMap(r=>r.items||[]).map(item=>[item.video_id,item])).values()];
  return `<div class="context-bar"><div><div class="context-label">Your goal</div><div class="context-value line-clamp">${esc(p.goal)}</div></div><div><div class="context-label">Audience</div><div class="context-value">${esc(p.audience)}</div></div><div><div class="context-label">Format</div><div class="context-value">9:16 vertical · ${p.target_duration_seconds} seconds</div></div></div>
  <div class="spread section-head"><div><h2>Start with a good angle.</h2><p>Explore references, then develop an idea that feels like you.</p></div>${badge('YouTube Data API')}</div>
  ${!S.settings.youtube_configured?`<div class="callout">${icon('link',19)}<div style="flex:1"><strong>YouTube research is awaiting setup.</strong><p>The workspace owner manages this service. You can continue with your own topic.</p></div><a href="/connections" data-nav class="btn btn-small">View status</a></div>`:''}
  <div class="panel research-panel"><form id="research-form" class="research-header"><div class="research-controls"><input id="research-query" name="query" aria-label="Research topic" value="${esc(run?.query||p.niche)}" minlength="2" maxlength="150" placeholder="Search your niche"><select name="period_days" aria-label="Research period">${[1,7,30].map(n=>`<option value="${n}" ${(run?.period_days||7)===n?'selected':''}>Last ${n} ${n===1?'day':'days'}</option>`).join('')}</select><select name="source_mode" aria-label="Reference source"><option value="search">Niche search</option><option value="chart" ${run?.source_mode==='chart'?'selected':''}>Popular chart</option></select><button class="btn btn-primary" type="submit" ${p.active_job?'disabled':''}>${icon('search',15)}Find references</button></div></form>
  ${run?.warnings?.length?`<div style="padding:20px 24px 0"><div class="callout warning" style="margin:0">${icon('alert',16)}<p>${run.warnings.map(esc).join(' ')}</p></div></div>`:''}
  ${items.length?`<div class="research-results">${items.map(item=>`<article class="source-card ${S.selected.has(item.video_id)?'selected':''}" data-source-card="${esc(item.video_id)}"><div class="source-image">${item.thumbnail_url?`<img src="${esc(item.thumbnail_url)}" alt="" loading="lazy" referrerpolicy="no-referrer">`:''}<input type="checkbox" data-source="${esc(item.video_id)}" aria-label="Select ${esc(item.title)}" ${S.selected.has(item.video_id)?'checked':''}></div><div class="source-info"><h4>${esc(item.title)}</h4><p>${esc(item.channel_title)}</p><div class="source-meta"><span>${number(item.view_count)}${item.view_count==null?'':' views'}</span><span>${fmtDate(item.published_at)}</span></div><a href="${esc(item.watch_url)}" target="_blank" rel="noopener noreferrer">Watch on YouTube${icon('external',10)}</a></div></article>`).join('')}</div>`:`<div class="research-empty">${icon('search',35)}<p>${run?'No references found for this topic. Try another search, or start with your own idea.':'Search for recent references in your niche. Select references from any of your searches as creative context.'}</p>${button('manual-research','Continue with my own topic','quiet')}</div>`}
  <div class="research-foot"><span>${run?`${run.data_mode==='manual'?'Your own topic':run.data_mode==='cache'?'Saved research':'YouTube references'} · ${fmtDate(run.fetched_at)} at ${fmtTime(run.fetched_at)}`:'References are creative context, not a prediction of what will go viral.'}</span><span id="selected-count">${S.selected.size} references selected</span></div></div>
  <div class="action-bar"><p>${S.settings.ai_engine==='workbuddy'?'Ask WorkBuddy for three original ideas using your topic and selected references.':S.settings.ai_connected?'Turn your topic and selected references into three original ideas.':'Writing service is awaiting setup. You can write your own brief.'}</p><div class="row">${button('goto-step','Write my own brief','secondary','data-step="1"')}${button('generate-ideas',`${icon('spark',15)}${S.settings.ai_engine==='workbuddy'?'Create with WorkBuddy':'Generate ideas'}`,'primary',S.settings.ai_engine!=='workbuddy'&&!S.settings.ai_connected||p.active_job?'disabled':'')}</div></div>
  ${p.ideas?.length?`<div class="section-head" style="margin-top:30px"><div><h2>Three ways to tell your story.</h2><p>${S.settings.ai_engine==='workbuddy'?'Ideas from WorkBuddy.':'AI suggestions.'} Choose the one you want to develop.</p></div></div><div class="ideas">${p.ideas.map((idea,i)=>`<article class="idea-card"><span class="idea-number">0${i+1}</span><h3>${esc(idea.title)}</h3><p>${esc(idea.angle)}</p><div class="idea-hook">“${esc(idea.hook)}”</div>${button('choose-idea',`Develop this idea${icon('arrow',13)}`,'secondary',`data-id="${esc(idea.id)}" ${p.active_job?'disabled':''}`)}</article>`).join('')}</div>`:''}`;
}

function briefPage() {
  const p=S.project,b=p.brief||{},approved=b.status==='approved';
  const shots=b.shots||Array.from({length:3},()=>({visual:'',narration:'',duration_seconds:p.target_duration_seconds/3}));
  return `<div class="section-head"><div><h2>Give your idea a clear shape.</h2><p>A practical brief, a strong opening, and a script that sounds like you.</p></div>${badge(approved?'Approved':'Draft',approved)}</div><form id="brief-form" data-edit><div class="editor-grid"><div class="panel"><div class="field"><label for="brief-title">Video title</label><input id="brief-title" name="title" required minlength="3" maxlength="180" value="${esc(b.title)}" placeholder="Give your story a working title"></div><div class="field"><label for="brief-hook">Opening hook</label><textarea id="brief-hook" name="hook" required minlength="3" maxlength="600" placeholder="What makes someone stop scrolling?">${esc(b.hook)}</textarea></div><div class="field"><label for="brief-angle">The angle</label><textarea id="brief-angle" name="angle" required minlength="5" maxlength="1000" placeholder="What makes this story useful or different?">${esc(b.angle)}</textarea></div><div class="field"><label for="brief-script">Script</label><textarea class="brief-script" id="brief-script" name="script" required minlength="10" maxlength="8000" placeholder="Write the spoken story, from your opening to your closing line.">${esc(b.script)}</textarea><span class="hint">This is your production guide. Subtitles will follow the actual speech in your footage.</span></div><div class="field" style="margin-bottom:0"><label for="brief-cta">Call to action</label><input id="brief-cta" name="cta" required minlength="2" maxlength="600" value="${esc(b.cta)}" placeholder="What should your audience do next?"></div></div><aside class="panel"><div class="spread" style="margin-bottom:23px"><h3 style="margin:0">Your shot list</h3><span class="badge" id="shot-total">${shots.reduce((a,s)=>a+s.duration_seconds,0)} / ${p.target_duration_seconds}s</span></div><div id="shots">${shots.map((shot,i)=>`<div class="shot" data-shot><div class="shot-head"><h4>Shot ${String(i+1).padStart(2,'0')}</h4><div class="shot-duration"><input data-duration type="number" step="0.1" min="0.1" max="60" aria-label="Shot ${i+1} duration in seconds" value="${shot.duration_seconds}" required><span>sec</span></div></div><label>Visual direction</label><textarea data-visual aria-label="Shot ${i+1} visual direction" required minlength="2" maxlength="600" placeholder="What do we see?">${esc(shot.visual)}</textarea><label>Spoken line</label><textarea data-narration aria-label="Shot ${i+1} spoken line" required maxlength="1000" placeholder="What do we hear?">${esc(shot.narration)}</textarea></div>`).join('')}</div><p class="hint" style="margin-top:18px">Plan 3–5 shots. Your shot timings should add up to ${p.target_duration_seconds} seconds.</p><div class="row">${button('add-shot',`${icon('plus',12)}Add shot`,'secondary',shots.length>=5?'disabled':'')}${button('remove-shot','Remove last','quiet',shots.length<=3?'disabled':'')}</div></aside></div><div class="action-bar"><p id="brief-save-note">${approved?'Your brief is approved. Save changes to create a new revision.':'Review the draft and approve it when you’re ready to add footage.'}</p><div class="row"><button type="submit" class="btn" ${p.active_job?'disabled':''}>Save changes</button>${approved?button('goto-step',`Add footage${icon('arrow',14)}`,'primary','data-step="2"'):button('approve-brief',`${icon('check',15)}Approve brief`,'primary',p.active_job?'disabled':'')}</div></div></form>`;
}

function footagePage() {
  const p=S.project;
  if(!p.brief||p.brief.status!=='approved') return guarded('A clear brief comes first.','Review and approve your brief before adding footage.',1);
  const selector=footageModeSelector();
  if(footageUploadMode()==='finished')return selector+finishedVideoUpload();
  return selector+`<div class="section-head"><div><h2>Upload raw footage.</h2><p>Upload 3–5 clips to trim, arrange and edit here, then continue to subtitles. You can also find stock footage below.</p></div>${badge(`${p.assets.length} / 5 clips`)}</div><div class="panel"><label class="checkbox-label" style="margin-bottom:23px"><input type="checkbox" id="rights-confirmed" ${S.rights?'checked':''}>These clips are mine, or I have permission to use them.</label><div class="dropzone" id="dropzone" role="button" tabindex="0" aria-label="Choose video files to upload"><div class="upload-icon">${icon('upload',24)}</div><h3>Drop your clips here.</h3><p>Or choose a few files from your device.</p><span class="btn">${icon('plus',14)}Browse files</span><p class="formats">MP4 or MOV · H.264 · Up to 100 MiB per clip · 3–120 seconds each</p></div><input type="file" id="clip-input" class="visually-hidden" accept="video/mp4,video/quicktime,.mp4,.mov" multiple aria-label="Select video clips"><div id="upload-queue">${uploadQueue()}</div></div>
  ${p.assets.length?`<div class="asset-grid">${p.assets.map(a=>`<article class="asset-card"><div class="asset-video"><video src="/api/v1/projects/${p.id}/assets/${a.id}/media#t=0.1" preload="metadata" controls muted playsinline aria-label="Preview ${esc(a.original_name)}"></video></div><div class="asset-info"><div class="spread"><h4 title="${esc(a.original_name)}">${esc(a.original_name)}</h4><button class="icon-btn" data-action="remove-asset" data-id="${a.id}" aria-label="Remove ${esc(a.original_name)}" ${p.active_job?'disabled':''}>${icon('trash',13)}</button></div><div class="asset-meta"><span>${duration(a.duration_seconds)}</span><span>${a.width}×${a.height}</span><span>${bytes(a.bytes)}</span></div><a class="inline-link" href="/api/v1/projects/${p.id}/assets/${a.id}/media?download=true" download="${esc(a.original_name)}">${icon('download',12)}Download clip</a>${!a.has_audio?'<span class="badge" style="margin-top:9px">No audio</span>':''}${a.provenance?`<a class="inline-link" style="font-size:9px;margin-top:8px" href="${esc(a.provenance.url)}" target="_blank" rel="noopener noreferrer">${esc(a.provenance.creator)} on ${stockName(a.provenance.provider || a.source)}${icon('external',10)}</a>`:''}</div></article>`).join('')}</div>`:''}
  <div class="action-bar"><p>${p.assets.length>=3?`${duration(p.assets.reduce((sum,a)=>sum+a.duration_seconds,0))} of footage · ${p.target_duration_seconds}s target`:'Clip assembly is optional. Bring your own finished edit for subtitles.'}</p><div class="row">${button('open-stock','Find stock footage','secondary',p.active_job?'disabled':'')}${button('goto-step',`Continue to Edit${icon('arrow',14)}`,'secondary','data-step="3"')}</div></div>`;
}
function uploadQueue() {
  return S.queue.map((file,i)=>`<div class="upload-progress"><div class="spread"><span class="small">${esc(file.name)}</span><span class="small muted">${file.error?`<span style="color:var(--red)">${esc(file.error)}</span>`:file.done?'Uploaded':file.progress===100?'Checking video…':`${file.progress}%`}</span>${!file.done&&!file.error?button('cancel-upload','Cancel','quiet'):''}</div>${!file.error&&!file.done?`<div class="progress-track"><div class="progress-fill" style="width:${file.progress}%"></div></div>`:''}</div>`).join('');
}

function postingCaptionPanel() {
  const p=S.project,c=p.posting_caption;
  if(!p.brief)return '';
  return `<form id="posting-caption-form" class="panel" data-edit style="margin-top:24px"><div class="section-head"><div><h3>Draft your posting caption.</h3><p>A hook, a caption and a CTA to go with your video. Edit before posting.</p></div></div>${c?.stale?'<p class="callout warning">Your brief changed. Review or regenerate this caption.</p>':''}<div class="field"><label for="posting-caption">Posting caption</label><textarea id="posting-caption" name="text" rows="7" maxlength="5000" placeholder="Write your caption here, or generate a draft from your saved brief.">${esc(c?.text||'')}</textarea></div><div class="row wrap">${S.settings.ai_engine==='openai_compatible'?button('generate-posting-caption','Generate caption','secondary',p.active_job?'disabled':''):'<p class="hint">Write a caption here or paste one from WorkBuddy.</p>'}<button type="submit" class="btn" ${p.active_job?'disabled':''}>Save caption</button>${button('copy-posting-caption','Copy caption','secondary')}${button('copy-script','Copy script','quiet')}</div></form>`;
}
function footageUploadMode() {
  const p=S.project;
  if(S.footageMode?.pid===p.id)return S.footageMode.mode;
  return p.draft?.source==='external_edit'||p.active_job?.type==='edited_prepare'?'finished':'raw';
}
function footageModeSelector() {
  const mode=footageUploadMode(),disabled=S.uploading||S.project.active_job;
  return `<div class="section-head"><div><h2>What would you like to upload?</h2><p>Choose raw footage to edit here, or a finished video to go straight to subtitles.</p></div></div><div class="upload-mode-switch" role="group" aria-label="Video upload type" data-mode="${mode}"><span class="upload-mode-thumb" aria-hidden="true"></span><label><input class="visually-hidden" id="upload-mode-raw" type="radio" name="upload-mode" value="raw" ${mode==='raw'?'checked':''} ${disabled?'disabled':''}>Raw footage</label><label><input class="visually-hidden" id="upload-mode-finished" type="radio" name="upload-mode" value="finished" ${mode==='finished'?'checked':''} ${disabled?'disabled':''}>Finished video</label></div>`;
}
function finishedVideoUpload() {
  const p=S.project;
  return `<div class="panel"><h3>Upload your finished video.</h3><p>Already edited your video in another app? Upload it here to prepare subtitles. You will skip the Edit phase and continue directly to Subtitles.</p><p class="hint">MP4/MOV · H.264 · 3–120 seconds · up to 100 MiB. We fit your video to 1080×1920 without cropping and keep its duration and cut sequence.</p><form id="edited-video-form"><div class="field"><label for="edited-video-file">Finished video</label><input id="edited-video-file" type="file" name="file" accept=".mp4,.mov" required ${p.active_job?'disabled':''}></div><label class="checkbox-label"><input type="checkbox" name="rights_confirmed" value="true" required>I have permission to use this video.</label><button type="submit" class="btn btn-primary" style="margin-top:16px" ${p.active_job?'disabled':''}>Upload & prepare subtitles</button></form></div>${p.draft?`<div class="callout"><p>Your current video is ready for subtitle review.</p>${button('goto-step','Review subtitles','secondary','data-step="4"')}</div>`:''}`;
}
function editPage() {
  if(S.project.brief?.status!=='approved')return guarded('Approve your brief first.','Your brief and script can be used in any editor.',1);
  return `<div class="section-head"><div><h2>Try out our new video editing feature!</h2><p>Optional: assemble 3–5 raw clips into a simple draft. Already edited your video? Upload it on Footage and go straight to subtitles.</p></div></div>`+builtInEditPage();
}

function builtInEditPage() {
  const p=S.project,plan=p.plan;
  if(p.assets.length<3) return guarded('Your footage comes first.','Add 3–5 clips to build your edit plan.',2);
  if(!plan) return `<div class="panel empty-state">${icon('film',38)}<h3>A first cut, without the busywork.</h3><p>We’ll suggest a trim for each clip, arrange the sequence, and fit it to your ${p.target_duration_seconds}-second story. You can adjust everything before processing.</p>${button('create-plan',`Create edit plan${icon('arrow',14)}`)}</div>`;
  const assets=Object.fromEntries(p.assets.map(a=>[a.id,a]));
  const segments=[...plan.segments].sort((a,b)=>a.order-b.order);
  return `<div class="section-head"><div><h2>Make the cut your own.</h2><p>Suggested trims, a simple sequence, and room for your judgment.</p></div>${badge(plan.status==='approved'?'Approved plan':'Suggested edit',plan.status==='approved')}</div><form id="plan-form" data-edit><div class="panel"><div class="spread" style="margin-bottom:6px"><h3 style="margin:0">Clip sequence</h3><div class="plan-total"><span>Video length</span><strong id="plan-total">${segments.reduce((sum,s)=>sum+s.out_seconds-s.in_seconds,0).toFixed(1)}s</strong><span class="muted">/ ${p.target_duration_seconds}s</span></div></div><div id="plan-segments">${segments.map((seg,i)=>planRow(seg,assets[seg.asset_id],i)).join('')}</div><div class="timeline">${segments.map((seg,i)=>`<div class="timeline-segment" style="flex:${seg.out_seconds-seg.in_seconds}">Clip ${i+1}</div>`).join('')}</div><div class="row" style="flex-wrap:wrap">${badge('1080 × 1920')}${badge('Fit with padding')}${badge('Fade in & out')}${badge('Original audio')}</div></div><div class="action-bar"><p>Your clips are kept in full view. No hidden crops or duplicated footage.</p><div class="row"><button type="submit" class="btn" ${p.active_job?'disabled':''}>Save plan</button>${button('prepare-video',`${icon('play',13)}${p.draft?'Create new draft':'Approve & create draft'}`,'primary',p.active_job?'disabled':'')}</div></div></form>${p.draft?`<div class="callout" style="margin-top:20px">${icon('check',18)}<div style="flex:1"><strong>Your draft is ready.</strong><p>Review its speech and subtitles before the final export.</p></div>${button('goto-step',`Review subtitles${icon('arrow',13)}`,'secondary','data-step="4"')}</div>`:''}`;
}
function planRow(seg,a,i) {
  return `<div class="clip-plan" data-plan-asset="${a.id}"><span class="small muted">${String(i+1).padStart(2,'0')}</span><video class="clip-thumb" src="/api/v1/projects/${S.project.id}/assets/${a.id}/media#t=0.1" preload="metadata" muted playsinline></video><div><div class="clip-name">${esc(a.original_name)}</div><div class="clip-meta">Source: ${duration(a.duration_seconds)}</div></div><div class="trim-field"><label>Start (sec)</label><input type="number" data-in value="${seg.in_seconds}" step="any" min="0" max="${a.duration_seconds}" required aria-label="Start of ${esc(a.original_name)}"></div><div class="trim-field"><label>End (sec)</label><input type="number" data-out value="${seg.out_seconds}" step="any" min="0.01" max="${a.duration_seconds}" required aria-label="End of ${esc(a.original_name)}"></div><div class="reorder"><button class="icon-btn" type="button" data-action="clip-up" aria-label="Move clip up">${icon('up',13)}</button><button class="icon-btn" type="button" data-action="clip-down" aria-label="Move clip down">${icon('down',13)}</button></div></div>`;
}

function subtitlesPage() {
  const p=S.project,t=p.subtitle;
  if(!p.draft&&p.active_job?.type==='edited_prepare')return `<div class="panel empty-state"><h3>Preparing your finished edit for subtitles.</h3><p>Your video is being prepared and transcribed. Your subtitles will appear here automatically.</p></div>`;
  if(!p.draft)return guarded('Bring your video.','Upload your finished edit on Footage, or try the optional editor.',2);
  return `<div class="section-head"><div><h2>Get every word right.</h2><p>Review the actual speech in your edit. Make the final words yours.</p></div>${badge(t?.status==='approved'?'Subtitles approved':t?'Automatic transcription':'Review needed',t?.status==='approved')}</div><div class="caption-layout"><div class="video-panel"><div class="portrait-preview"><video id="caption-video" src="/api/v1/projects/${p.id}/drafts/${p.draft.id}/media" controls playsinline preload="metadata" aria-label="Draft video preview"></video><div class="preview-captions" id="preview-captions"></div></div><div class="preview-meta"><span>${p.draft.duration_seconds.toFixed(1)}s · 9:16</span><span>Draft preview</span></div><p class="small muted" style="font-size:10px;line-height:1.8">Preview subtitles appear over your draft. They will be embedded in your final MP4.</p></div><form id="caption-form" class="panel" data-edit><div class="spread" style="margin-bottom:14px"><h3 style="margin:0">Subtitles</h3><span class="badge">Indonesian speech</span></div>${!t?`<div class="callout warning">${icon('alert',15)}<p>Automatic transcription is not available yet. Retry the speech step or add subtitles manually.</p></div>${button('retry-speech','Retry transcription','secondary',p.active_job?'disabled':'')}`:''}
  ${t?.speech_status==='no_speech'?`<div class="no-speech">${icon('mute',34)}<h3>No speech detected.</h3><p>We haven’t added words that aren’t in your audio. Listen to the preview, then confirm if you want to continue without subtitles.</p></div>`:''}<div class="cue-list" id="cue-list">${(t?.cues||[]).map(cueRow).join('')}</div><div class="spread" style="margin-top:17px">${button('add-cue',`${icon('plus',12)}Add subtitle`,'secondary',p.active_job?'disabled':'')}${button('split-cues','Split long subtitles','quiet',p.active_job?'disabled':'')}</div><label class="checkbox-label" style="margin-top:23px"><input type="checkbox" id="no-speech-confirm" ${t?.no_speech_confirmed_at?'checked':''}>This video has no spoken audio. Continue without subtitles.</label><p class="hint" style="margin-top:16px">Keep each subtitle to two short lines. Timings cannot overlap or extend past the video.</p><div class="row" style="justify-content:flex-end;margin-top:22px;flex-wrap:wrap"><button type="submit" class="btn" ${p.active_job?'disabled':''}>Save subtitles</button>${t?.status==='approved'?button('goto-step',`Export video${icon('arrow',14)}`,'primary','data-step="5"'):button('approve-subtitles',`${icon('check',14)}Approve subtitles`,'primary',p.active_job?'disabled':'')}</div></form></div>`;
}
function cueRow(cue,i) {
  return `<div class="cue" data-cue="${esc(cue.id)}"><button type="button" class="icon-btn cue-number" data-action="seek-cue" aria-label="Play subtitle ${i+1}">${String(i+1).padStart(2,'0')}</button><div><div class="cue-times"><input data-start type="number" min="0" max="${S.project.draft?.duration_seconds||S.project.target_duration_seconds}" step="0.001" value="${cue.start_seconds}" aria-label="Subtitle ${i+1} start time" required><span>→</span><input data-end type="number" min="0.001" max="${S.project.draft?.duration_seconds||S.project.target_duration_seconds}" step="0.001" value="${cue.end_seconds}" aria-label="Subtitle ${i+1} end time" required><span>sec</span></div><textarea data-text maxlength="500" required aria-label="Subtitle ${i+1} text">${esc(cue.text)}</textarea><div class="cue-count">${cue.text.length} characters</div></div><button type="button" class="icon-btn" data-action="remove-cue" aria-label="Remove subtitle ${i+1}">${icon('close',13)}</button></div>`;
}

function exportPage() {
  const p=S.project,current=p.exports?.find(e=>e.current);
  if(!current) {
    if(p.subtitle?.status!=='approved')return guarded('One last review.','Approve your subtitles, or confirm that there is no speech, before exporting your finished video.',4);
    return `<div class="panel empty-state">${icon('download',40)}<h3>Your story is ready for its final frame.</h3><p>Export a vertical MP4 with your approved subtitles, original audio, and finishing effects.</p><div class="row" style="justify-content:center;margin-bottom:25px">${badge('1080 × 1920')}${badge(`${p.draft?.duration_seconds||p.target_duration_seconds} seconds`)}${badge('H.264 MP4')}</div>${button('export-video',`${icon('download',16)}Export video`,'primary',p.active_job?'disabled':'')}</div>`;
  }
  return `<div class="section-head"><div><h2>Your story. Ready to share.</h2><p>Give it a final watch, then take it to your audience.</p></div>${badge(p.ready_confirmed_at?'Ready to upload':'Export complete',true)}</div><div class="export-layout"><div class="video-panel"><div class="portrait-preview"><video src="/api/v1/projects/${p.id}/exports/${current.id}/files/mp4" controls playsinline preload="metadata" aria-label="Finished video"></video></div><div class="preview-meta"><span>Final video</span><span>${duration(current.duration_seconds)}</span></div></div><div class="panel"><div class="row" style="gap:10px;margin-bottom:17px"><span style="color:var(--accent)">${icon('circleCheck',25)}</span><div><h3 style="margin:0 0 3px">The finishing touches are in.</h3><p class="small" style="margin:0">Video profile and playback checks passed.</p></div></div><div class="export-specs"><div class="export-spec"><span>Resolution</span><strong>${current.metadata.width} × ${current.metadata.height}</strong></div><div class="export-spec"><span>Duration</span><strong>${current.duration_seconds} seconds</strong></div><div class="export-spec"><span>Format</span><strong>H.264 · MP4 · 30 fps</strong></div><div class="export-spec"><span>File size</span><strong>${bytes(current.bytes)}</strong></div></div><div class="export-downloads"><a class="btn btn-primary" href="/api/v1/projects/${p.id}/exports/${current.id}/files/mp4?download=true" download>${icon('download',15)}Download MP4</a>${current.subtitle_id&&p.subtitle?.cues?.length?`<a class="btn" href="/api/v1/projects/${p.id}/exports/${current.id}/files/srt?download=true" download>${icon('subtitles',15)}Download SRT</a>`:''}</div><div class="callout">${icon('film',18)}<p>Watch the full video and check the words, timing, and framing. Upload your downloaded file to YouTube Shorts or Instagram Reels when you’re happy with it.</p></div>${p.ready_confirmed_at?`<div class="row" style="color:var(--accent);font-size:12px">${icon('check',16)}You marked this video ready to upload.</div>`:button('confirm-ready',`${icon('check',15)}I’ve reviewed it — ready to upload`,'secondary')}<hr class="rule"><div class="spread"><span class="small muted">Want a different cut?</span>${button('goto-step','Back to edit','quiet','data-step="3"')}</div></div></div>${p.exports.length>1?`<div class="panel" style="margin-top:24px"><h3>Earlier versions</h3>${p.exports.filter(e=>!e.current).map(e=>`<div class="export-item"><div class="export-info"><h3>${e.duration_seconds}-second video${badge('Earlier version')}</h3><p>${fmtDate(e.validated_at)} · ${fmtTime(e.validated_at)} · ${bytes(e.bytes)}</p></div><a class="btn btn-small" href="/api/v1/projects/${p.id}/exports/${e.id}/files/mp4?download=true" download>${icon('download',13)}Download</a></div>`).join('')}</div>`:''}`;
}

function bindMedia() {
  if(S.project?.active_job&&S.route.startsWith('/projects/')){
    document.querySelectorAll('form[data-edit] input, form[data-edit] textarea, form[data-edit] select, form[data-edit] button:not([data-action="goto-step"])').forEach(control=>control.disabled=true);
  }
  const video=document.querySelector('#caption-video');
  if(video)video.addEventListener('timeupdate',()=>{
    const cue=readCues().find(c=>c.start_seconds<=video.currentTime&&video.currentTime<c.end_seconds);
    document.querySelector('#preview-captions').textContent=cue?.text||'';
  });
  const drop=document.querySelector('#dropzone');
  if(drop){drop.addEventListener('click',()=>chooseClips());drop.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();chooseClips();}});for(const type of ['dragenter','dragover'])drop.addEventListener(type,event=>{event.preventDefault();drop.classList.add('dragging');});drop.addEventListener('dragleave',()=>drop.classList.remove('dragging'));drop.addEventListener('drop',event=>{event.preventDefault();drop.classList.remove('dragging');uploadFiles([...event.dataTransfer.files]);});}
}

async function route() {
  S.route=location.pathname;
  if(S.route==='/connections'){S.settings=await api('/settings');renderShell(connectionPage());document.title='Connections — TrendForge';return;}
  const match=S.route.match(/^\/projects\/([^/]+)(?:\/([^/]+))?$/);
  if(match){
    if(S.project?.id!==match[1]){S.selected.clear();S.queue=[];S.rights=false;}
    try {S.project=await api(`/projects/${match[1]}`);S.step=Math.max(0,stepPaths.indexOf(match[2]||'discover'));renderShell(projectPage());document.title=`${S.project.niche} — TrendForge`;}
    catch(error){renderShell(`<div class="panel empty-state">${icon('folder',35)}<h3>Project unavailable.</h3><p>${esc(error.message)}</p><a class="btn btn-primary" href="/projects" data-nav>Back to projects</a></div>`);}
    return;
  }
  S.projects=await api('/projects');
  if(S.route==='/exports'){
    const list=await Promise.all(S.projects.filter(p=>p.export_count).map(async p=>({project:p,exports:await api(`/projects/${p.id}/exports`)})));
    renderShell(`<div class="spread page-actions"><div><h1 class="page-title">The stories you’ve made.</h1><p class="muted" style="margin:0">Your finished videos, ready when you are.</p></div>${button('new-project',`${icon('plus',14)}New project`)}</div>${list.length?`<div class="panel">${list.map(({project,exports})=>exports.map(e=>`<div class="export-item"><span class="service-icon">${icon('film',21)}</span><div class="export-info"><h3><a href="/projects/${project.id}/export" data-nav>${esc(project.niche)}</a></h3><p>${e.duration_seconds}s · ${bytes(e.bytes)} · ${fmtDate(e.validated_at)} ${!e.current?'· Earlier version':''}</p></div><a class="btn btn-small" href="/api/v1/projects/${project.id}/exports/${e.id}/files/mp4?download=true" download>${icon('download',13)}Download</a></div>`).join('')).join('')}</div>`:guarded('Your finished stories will live here.','Create a project and export your first video to get started.',0)}${footer()}`);
    document.title='Exports — TrendForge';return;
  }
  renderShell(homePage(S.route==='/projects'));document.title='Your creative workspace — TrendForge';
}

function readBrief() {
  const f=document.querySelector('#brief-form'),data=Object.fromEntries(new FormData(f));
  return {title:data.title,hook:data.hook,angle:data.angle,script:data.script,cta:data.cta,
    shots:[...f.querySelectorAll('[data-shot]')].map(el=>({visual:el.querySelector('[data-visual]').value,narration:el.querySelector('[data-narration]').value,duration_seconds:Number(el.querySelector('[data-duration]').value)})),
    source_video_ids:S.project.brief?.source_video_ids||[],selected_idea_id:S.project.brief?.selected_idea_id||null,expected_project_revision:S.project.revision};
}
async function saveBrief() {
  const form=document.querySelector('#brief-form');if(!form.reportValidity())return false;
  await api(`/projects/${S.project.id}/briefs`,{method:'POST',body:readBrief()});
  await refreshProject();return true;
}
function readPlan(){return {brief_revision_id:S.project.brief_id,target_duration_seconds:S.project.target_duration_seconds,
  segments:[...document.querySelectorAll('[data-plan-asset]')].map((el,i)=>({asset_id:el.dataset.planAsset,order:i+1,in_seconds:Number(el.querySelector('[data-in]').value),out_seconds:Number(el.querySelector('[data-out]').value)})),
  framing:'fit_pad',preset:'simple_fade',audio_mode:'original',expected_project_revision:S.project.revision};}
async function savePlan(){if(!document.querySelector('#plan-form').reportValidity())return false;await api(`/projects/${S.project.id}/plans`,{method:'POST',body:readPlan()});await refreshProject();return true;}
function readCues(){return [...document.querySelectorAll('[data-cue]')].map(el=>({id:el.dataset.cue,start_seconds:Number(el.querySelector('[data-start]').value),end_seconds:Number(el.querySelector('[data-end]').value),text:el.querySelector('[data-text]').value}));}
function splitCues(cues) {
  const out=[];
  for(const cue of cues){const words=cue.text.trim().split(/\s+/),lines=[];let line='';for(const word of words){if((line+' '+word).trim().length>32&&line){lines.push(line);line=word;}else line=(line+' '+word).trim();}if(line)lines.push(line);const parts=[];for(let i=0;i<lines.length;i+=2)parts.push(lines.slice(i,i+2).join('\n'));if(!parts.length)continue;const size=parts.reduce((a,p)=>a+p.length,0);let start=cue.start_seconds;parts.forEach((text,i)=>{const end=i===parts.length-1?cue.end_seconds:start+(cue.end_seconds-cue.start_seconds)*text.length/size;out.push({id:'cue_'+crypto.randomUUID(),start_seconds:Math.round(start*1000)/1000,end_seconds:Math.round(end*1000)/1000,text});start=end;});}
  return out;
}
async function saveSubtitles() {
  const form=document.querySelector('#caption-form');if(!form.reportValidity())return false;
  const cues=splitCues(readCues());
  const noSpeech=document.querySelector('#no-speech-confirm').checked;
  await api(`/projects/${S.project.id}/subtitles`,{method:'POST',body:{draft_id:S.project.draft_id,cues,speech_status:noSpeech?'no_speech':'speech',expected_project_revision:S.project.revision}});
  await refreshProject();return true;
}
async function startJob(type,body={}) {
  await api(`/projects/${S.project.id}/${type}`,{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()},body});
  await refreshProject();toast(type==='export-jobs'?'Your final video is being exported.':'Your video is being prepared.');
}
function chooseClips(){if(S.project.active_job)return toast('Wait for processing to finish before changing your footage.',true);if(!document.querySelector('#rights-confirmed')?.checked)return toast('Confirm that you have permission to use these clips first.',true);document.querySelector('#clip-input').click();}
async function uploadFiles(files) {
  if(S.uploading)return;
  if(!document.querySelector('#rights-confirmed')?.checked)return toast('Confirm that you have permission to use these clips first.',true);
  if(S.project.active_job)return toast('Wait for processing to finish first.',true);
  if(S.project.assets.length+files.length>5)return toast('Use at most five clips in one project.',true);
  S.uploading=true;S.uploadCancelled=false;const pid=S.project.id;S.queue=[];
  for(const file of files){if(S.uploadCancelled)break;const entry={name:file.name,progress:0,done:false};S.queue.push(entry);updateQueue();
    try {if(file.size>100*1024*1024)throw new Error('Larger than 100 MiB.');await new Promise((resolve,reject)=>{
      const xhr=new XMLHttpRequest();S.uploadXHR=xhr;xhr.open('POST',`/api/v1/projects/${pid}/assets`);xhr.setRequestHeader('X-CSRF-Token',S.csrf);
      xhr.upload.onprogress=event=>{if(event.lengthComputable){entry.progress=Math.round(event.loaded/event.total*100);updateQueue();}};
      xhr.onload=()=>{let data;try{data=JSON.parse(xhr.responseText);}catch{return reject(new Error('Upload failed. Try this file again.'));}if(xhr.status>=400)reject(new Error(data.error?.message||'Upload failed.'));else resolve(data);};
      xhr.onerror=()=>reject(new Error('Connection interrupted. Try this file again.'));xhr.onabort=()=>reject(new Error('Upload cancelled.'));
      const form=new FormData();form.append('file',file);form.append('rights_confirmed','true');xhr.send(form);
    });entry.done=true;await refreshProject(S.route.startsWith(`/projects/${pid}`)&&S.step===2);}
    catch(error){entry.error=error.message;updateQueue();}
  }
  S.uploading=false;S.uploadXHR=null;if(S.project?.id===pid&&S.step===2)await refreshProject();
}
function updateQueue(){const target=document.querySelector('#upload-queue');if(target)target.innerHTML=uploadQueue();}

async function openStock() {
  S.settings=await api('/settings');
  if(!S.settings.stock_configured){toast('Stock footage is awaiting setup by the workspace owner. You can upload your own clips.',true);return;}
  dialog.innerHTML=`<div class="dialog-head"><div><h2 id="dialog-title">Find a supporting shot.</h2><p>Stock footage provided by <a href="${stockHome(S.settings.stock_provider)}" target="_blank" rel="noopener noreferrer">${stockName(S.settings.stock_provider)}</a>.</p></div><button class="icon-btn" data-action="close-dialog" aria-label="Close">${icon('close',18)}</button></div><div class="dialog-body"><form id="stock-form" class="stock-form"><input name="query" minlength="2" maxlength="100" placeholder="Search for a scene or subject" required><button class="btn btn-primary">Search</button></form><div id="stock-results"><p class="small muted">Look for a simple shot that supports your story.</p></div></div>`;dialog.showModal();
}

document.addEventListener('click',async event=>{
  const link=event.target.closest('a[data-nav]');if(link){event.preventDefault();if(S.csrf){if(dialog.contains(link))dialog.close();await navigate(link.getAttribute('href'));}return;}
  const el=event.target.closest('[data-action]');if(!el||el.disabled)return;
  const action=el.dataset.action;if(S.busy&&!['close-dialog','cancel-upload','toggle-sidebar'].includes(action))return;
  if(action==='close-dialog'){dialog.close();return;}
  if(action==='toggle-sidebar'){S.mobile=!S.mobile;document.querySelector('.sidebar')?.classList.toggle('open',S.mobile);document.querySelector('.side-overlay')?.classList.toggle('visible',S.mobile);return;}
  if(action==='new-project'){openProjectDialog();return;}
  if(action==='edit-project'){openProjectDialog(true);return;}
  if(action==='goto-step'){if(!S.project)return navigate('/projects');await navigate(`/projects/${S.project.id}/${stepPaths[Number(el.dataset.step)]}`);return;}
  if(action==='clear-secret'){const input=document.querySelector(`[name="${el.dataset.name}"]`);input.value='';input.dataset.remove='true';input.placeholder='Key will be removed when you save.';input.closest('form').dataset.dirty='true';return;}
  if(action==='cancel-upload'){S.uploadCancelled=true;S.uploadXHR?.abort();return;}
  if(action==='add-shot'||action==='remove-shot'){
    const shots=[...document.querySelectorAll('[data-shot]')];if(action==='remove-shot'&&shots.length>3)shots.at(-1).remove();
    if(action==='add-shot'&&shots.length<5){const copy=shots[0].cloneNode(true);copy.querySelector('h4').textContent=`Shot ${String(shots.length+1).padStart(2,'0')}`;copy.querySelectorAll('textarea').forEach(el=>el.value='');copy.querySelector('[data-duration]').value=1;document.querySelector('#shots').append(copy);}
    document.querySelector('#brief-form').dataset.dirty='true';updateTotals();return;
  }
  if(action==='clip-up'||action==='clip-down'){const row=el.closest('[data-plan-asset]'),parent=row.parentElement;if(action==='clip-up'&&row.previousElementSibling)parent.insertBefore(row,row.previousElementSibling);if(action==='clip-down'&&row.nextElementSibling)parent.insertBefore(row.nextElementSibling,row);[...parent.children].forEach((r,i)=>r.firstElementChild.textContent=String(i+1).padStart(2,'0'));document.querySelector('#plan-form').dataset.dirty='true';return;}
  if(action==='seek-cue'){const video=document.querySelector('#caption-video');video.currentTime=Number(el.closest('[data-cue]').querySelector('[data-start]').value);video.play().catch(()=>{});return;}
  if(action==='remove-cue'){el.closest('[data-cue]').remove();document.querySelector('#caption-form').dataset.dirty='true';return;}
  if(action==='add-cue'){
    const cues=readCues(),start=cues.length?cues.at(-1).end_seconds:0,end=Math.min(start+2,S.project.draft?.duration_seconds||S.project.target_duration_seconds);
    if(end<=start)return toast('Make room by shortening the final subtitle first.',true);
    document.querySelector('#cue-list').insertAdjacentHTML('beforeend',cueRow({id:'cue_'+crypto.randomUUID(),start_seconds:start,end_seconds:end,text:''},cues.length));document.querySelector('#no-speech-confirm').checked=false;document.querySelector('#caption-form').dataset.dirty='true';return;
  }
  if(action==='split-cues'){document.querySelector('#cue-list').innerHTML=splitCues(readCues()).map(cueRow).join('');document.querySelector('#caption-form').dataset.dirty='true';toast('Long subtitles have been split into shorter cues.');return;}
  if(action==='open-stock'){await openStock();return;}
  await busy('Working on your story',async()=>{
    const pid=S.project?.id;
    if(action==='sign-out'){if(!canLeave())return;await api('/session',{method:'DELETE'});S.csrf='';renderAuth(false);}
    else if(action==='delete-project'){if(!confirm('Delete this project and all its clips, drafts, subtitles, and exports? Your separately downloaded copies will stay with you.'))return;await api(`/projects/${pid}`,{method:'DELETE',body:{confirmation:true,expected_project_revision:S.project.revision}});S.project=null;await refreshData();await navigate('/projects');toast('Project and workspace files deleted.');}
    else if(action==='manual-research'){await api(`/projects/${pid}/research`,{method:'POST',body:{query:S.project.niche,period_days:7,source_mode:'manual',language:S.project.language,region:'ID'}});await refreshProject(false);await navigate(`/projects/${pid}/brief`);}
    else if(action==='generate-ideas'){const result=await api(`/projects/${pid}/ai/ideas`,{method:'POST',body:{source_video_ids:[...S.selected],expected_project_revision:S.project.revision}});await refreshProject();if(result.engine==='workbuddy'){openAgentDialog(result);return;}toast('Three ideas are ready for you to explore.');document.querySelector('.ideas')?.scrollIntoView({behavior:'smooth',block:'center'});}
    else if(action==='choose-idea'){const result=await api(`/projects/${pid}/ai/brief`,{method:'POST',body:{idea_id:el.dataset.id,expected_project_revision:S.project.revision}});await refreshProject(false);if(result.engine==='workbuddy'){await refreshProject();openAgentDialog(result);return;}await navigate(`/projects/${pid}/brief`);toast('Your brief and script are ready to review.');}
    else if(action==='approve-brief'){if(!S.project.brief||dirty()){if(!await saveBrief())return;}await api(`/projects/${pid}/briefs/${S.project.brief_id}/approve`,{method:'POST',body:{confirmation:true,expected_project_revision:S.project.revision}});await refreshProject();toast('Brief approved. Time to add your footage.');}
    else if(action==='remove-asset'){if(!confirm('Remove this clip? Any edit that uses it will need to be rebuilt.'))return;await api(`/projects/${pid}/assets/${el.dataset.id}`,{method:'DELETE',body:{confirmation:true,expected_project_revision:S.project.revision}});await refreshProject();}
    else if(action==='copy-script'){await navigator.clipboard.writeText(S.project.brief?.script||'');toast('Script copied.');}
    else if(action==='copy-posting-caption'){await navigator.clipboard.writeText(document.querySelector('#posting-caption').value);toast('Caption copied.');}
    else if(action==='generate-posting-caption'){if(dirty()&&!confirm('Generate a new caption? Save other unsaved changes first.'))return;await api(`/projects/${pid}/posting-caption/generate`,{method:'POST',body:{expected_project_revision:S.project.revision}});await refreshProject();toast('Posting caption drafted. Review it before posting.');}
    else if(action==='create-plan'){await api(`/projects/${pid}/plans/auto`,{method:'POST',body:{expected_project_revision:S.project.revision}});await refreshProject(false);await navigate(`/projects/${pid}/edit`);}
    else if(action==='prepare-video'){if(dirty()){if(!await savePlan())return;}if(S.project.plan.status!=='approved'){await api(`/projects/${pid}/plans/${S.project.plan_id}/approve`,{method:'POST',body:{confirmation:true,expected_project_revision:S.project.revision}});await refreshProject(false);}await startJob('prepare-jobs',{plan_id:S.project.plan_id});}
    else if(action==='retry-speech'){await startJob('transcription-jobs',{draft_id:S.project.draft_id});}
    else if(action==='approve-subtitles'){const noSpeech=document.querySelector('#no-speech-confirm').checked;if(!S.project.subtitle||dirty()){if(!await saveSubtitles())return;}await api(`/projects/${pid}/subtitles/${S.project.subtitle_id}/approve`,{method:'POST',body:{confirmation:true,expected_project_revision:S.project.revision,no_speech_decision:noSpeech}});await refreshProject();toast('Subtitles approved. Your video is ready to export.');}
    else if(action==='export-video'){await startJob('export-jobs');}
    else if(action==='confirm-ready'){await api(`/projects/${pid}/ready-confirmation`,{method:'POST',body:{export_id:S.project.export_id,confirmation:true}});await refreshProject();toast('Ready to upload. Go share your story.');}
    else if(action==='cancel-job'){await api(`/projects/${pid}/jobs/${el.dataset.id}/cancel`,{method:'POST'});await refreshProject();}
    else if(action==='cancel-system-job'){await api(`/jobs/${el.dataset.id}/cancel`,{method:'POST'});toast('Stopping the download safely.');}
    else if(action==='retry-job'){const job=S.project.last_job;if(job.type==='export')await startJob('export-jobs');else if(job.type==='edited_prepare'&&!job.output?.draft_id)await startJob('edited-video-jobs',{edited_video_id:job.edited_video_id});else if(S.project.draft)await startJob('transcription-jobs',{draft_id:S.project.draft_id});else await startJob('prepare-jobs',{plan_id:S.project.plan_id});}
    else if(['test-ai','test-youtube','test-stock'].includes(action)){const result=await api('/settings/test',{method:'POST',body:{provider:action.slice(5)}});toast(result.message);}
    else if(action==='show-agent-task'){openAgentDialog(await api(`/projects/${pid}/agent-requests/${S.project.agent_request.id}`));}
    else if(action==='copy-agent-task'){try{await navigator.clipboard.writeText(S.agentRequest.prompt);toast('Task copied. Paste it into WorkBuddy.');}catch{document.querySelector('#agent-prompt')?.select();toast('Select and copy the task above.');}}
    else if(action==='cancel-agent-task'){await api(`/projects/${pid}/agent-requests/${el.dataset.id}/cancel`,{method:'POST'});await refreshProject();}
    else if(action==='show-connector'){const config=await api('/settings/connector');const text=JSON.stringify(config,null,2);document.querySelector('#connector-code').innerHTML=`<pre tabindex="0">${esc(text)}</pre><p class="hint">No API credentials are included in this configuration.</p>`;try{await navigator.clipboard.writeText(text);toast('Connector configuration copied.');}catch{toast('Your connector configuration is shown below.');}}
    else if(action==='download-model'){const job=await api('/settings/speech-model',{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()}});S.systemJob=job.id;document.querySelector('#model-job-status').innerHTML=jobBanner(job,true);toast('Speech model download started.');}
    else if(action==='import-stock'){await api(`/projects/${pid}/stock/import`,{method:'POST',body:{query:S.stockQuery,video_id:Number(el.dataset.id),provider:el.dataset.provider}});dialog.close();await refreshProject();toast('Stock footage added.');}
  });
});

document.addEventListener('submit',async event=>{
  const f=event.target;if(!(f instanceof HTMLFormElement))return;event.preventDefault();
  if(f.id==='auth-form'){
    const values=Object.fromEntries(new FormData(f));if(f.dataset.setup==='true'&&values.password!==values.confirm_password){document.querySelector('#auth-error').textContent='The passwords do not match.';return;}
    const submit=f.querySelector('[type=submit]');submit.disabled=true;
    try{const result=await api(f.dataset.setup==='true'?'/setup':'/session',{method:'POST',body:{password:values.password}});S.csrf=result.csrf_token;await refreshData();await route();}catch(error){document.querySelector('#auth-error').textContent=error.message;}finally{submit.disabled=false;}return;
  }
  await busy('Saving your work',async()=>{
    if(f.id==='project-form'){
      const body=Object.fromEntries(new FormData(f));body.target_duration_seconds=Number(body.target_duration_seconds);
      const editing=f.dataset.editing==='true';if(editing){body.expected_project_revision=S.project.revision;}
      const p=await api(editing?`/projects/${S.project.id}`:'/projects',{method:editing?'PATCH':'POST',body});dialog.close();await refreshData();S.project=null;await navigate(`/projects/${p.id}/discover`);toast(editing?'Project details updated.':'Your new project is ready.');
    }else if(f.id==='research-form'){
      const body=Object.fromEntries(new FormData(f));body.period_days=Number(body.period_days);body.region='ID';body.language=S.project.language;
      const result=await api(`/projects/${S.project.id}/research`,{method:'POST',body});await refreshProject();toast(result.items?.length?`${result.items.length} references found.`:'No references found. Try another topic or continue with your own idea.');
    }else if(f.id==='edited-video-form'){const body=new FormData(f);await api(`/projects/${S.project.id}/edited-video`,{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()},body});await refreshProject(false);await navigate(`/projects/${S.project.id}/subtitles`);toast('Preparing your finished edit for subtitles.');
    }else if(f.id==='posting-caption-form'){await api(`/projects/${S.project.id}/posting-caption`,{method:'POST',body:{text:new FormData(f).get('text'),expected_project_revision:S.project.revision}});f.removeAttribute('data-dirty');await refreshProject();toast('Posting caption saved.');
    }else if(f.id==='brief-form'){if(await saveBrief())toast('Brief saved.');}
    else if(f.id==='plan-form'){if(await savePlan())toast('Edit plan saved.');}
    else if(f.id==='caption-form'){if(await saveSubtitles())toast('Subtitles saved.');}
    else if(f.id==='speech-settings'){
      const body=Object.fromEntries(new FormData(f));for(const input of f.querySelectorAll('[data-secret]')){if(!input.value&&!input.dataset.remove)delete body[input.name];}
      S.settings=await api('/settings',{method:'PATCH',body});S.settings=await api('/settings');renderShell(connectionPage());toast('Connection settings saved.');
    }else if(f.id==='stock-form'){
      S.stockQuery=new FormData(f).get('query');S.stockResults=await api(`/stock/search?query=${encodeURIComponent(S.stockQuery)}`);
      document.querySelector('#stock-results').innerHTML=S.stockResults.length?`<div class="stock-results">${S.stockResults.map(v=>`<article class="stock-result"><img src="${esc(v.image)}" alt="Stock footage preview"><div><p>${v.duration}s · ${esc(v.creator)}</p><a href="${esc(v.url)}" target="_blank" rel="noopener noreferrer">View on ${stockName(v.provider)}${icon('external',10)}</a>${button('import-stock','Add clip','secondary',`data-id="${v.id}" data-provider="${v.provider}"`)}</div></article>`).join('')}</div>`:'<p class="small muted">No suitable clips found. Try a different search.</p>';
    }
  });
});

function updateTotals() {
  const shots=[...document.querySelectorAll('[data-shot]')];
  if(shots.length){const sum=shots.reduce((total,el)=>total+Number(el.querySelector('[data-duration]').value),0);document.querySelector('#shot-total').textContent=`${sum.toFixed(1)} / ${S.project.target_duration_seconds}s`;const add=document.querySelector('[data-action="add-shot"]');if(add)add.disabled=shots.length>=5;const remove=document.querySelector('[data-action="remove-shot"]');if(remove)remove.disabled=shots.length<=3;}
  if(document.querySelector('#plan-total')){const sum=readPlan().segments.reduce((total,s)=>total+s.out_seconds-s.in_seconds,0);document.querySelector('#plan-total').textContent=`${sum.toFixed(1)}s`;}
}
document.addEventListener('input',event=>{
  const el=event.target;
  if(el.id==='global-search'){S.search=el.value;const target=document.querySelector('#project-list');if(target)target.innerHTML=projectsList(S.route==='/projects');else if(el.value.length>1){if(dirty()){el.setCustomValidity('Save your changes before searching projects.');el.reportValidity();return;}el.setCustomValidity('');history.replaceState({},'','/projects');S.route='/projects';renderShell(homePage(true));const input=document.querySelector('#global-search');input.focus();input.setSelectionRange(input.value.length,input.value.length);}return;}
  el.closest('form[data-edit]')?.setAttribute('data-dirty','true');
  if(el.matches('[data-secret]'))delete el.dataset.remove;
  if(el.matches('[data-duration],[data-in],[data-out]'))updateTotals();
  if(el.matches('[data-text]'))el.parentElement.querySelector('.cue-count').textContent=`${el.value.length} characters`;
});
document.addEventListener('change',event=>{
  const el=event.target;
  if(el.name==='upload-mode'){
    if(S.uploading||S.project?.active_job)return;
    S.footageMode={pid:S.project.id,mode:el.value==='finished'?'finished':'raw'};
    renderShell(projectPage());document.querySelector(`#upload-mode-${S.footageMode.mode}`)?.focus();return;
  }
  if(el.matches('[data-source]')){
    if(el.checked)S.selected.add(el.dataset.source);else S.selected.delete(el.dataset.source);el.closest('.source-card').classList.toggle('selected',el.checked);document.querySelector('#selected-count').textContent=`${S.selected.size} references selected`;
  }
  if(el.id==='rights-confirmed')S.rights=el.checked;
  if(el.id==='clip-input')uploadFiles([...el.files]);
  el.closest('form[data-edit]')?.setAttribute('data-dirty','true');
});
document.addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();document.querySelector('#global-search')?.focus();}});
window.addEventListener('popstate',()=>{if(!canLeave()){history.pushState({},'',S.route);return;}route().catch(error=>toast(error.message,true));});
window.addEventListener('beforeunload',event=>{if(dirty()||S.uploading){event.preventDefault();event.returnValue='';}});
setInterval(async()=>{
  if(!S.csrf||S.polling||S.busy)return;S.polling=true;
  try{
    if(S.systemJob||S.route==='/connections'&&S.settings.active_job?.type==='model_download'){
      const id=S.systemJob||S.settings.active_job.id;const job=await api(`/jobs/${id}`);S.systemJob=id;
      if(['succeeded','failed','cancelled'].includes(job.status)){S.systemJob=null;S.settings=await api('/settings');if(S.route==='/connections'&&!dirty())renderShell(connectionPage());toast(job.status==='succeeded'?'Speech model downloaded.':job.error?.message||'Model download cancelled.',job.status==='failed');}
      else{const label=document.querySelector('#model-job-status #job-status-text');if(label)label.textContent=job.stage;}
    }
    if(S.route.startsWith('/projects/')&&S.project&&!S.project.active_job){
      const pid=S.project.id,previous=S.project.agent_request;
      const p=await api(`/projects/${pid}`);
      if(S.project?.id!==pid)return;
      if((p.revision!==S.project.revision||p.agent_request?.status!==previous?.status)&&!dirty()&&!S.uploading){
        S.project=p;
        if(dialog.open&&dialog.dataset.agentRequest===p.agent_request?.id&&p.agent_request.status!=='pending'){dialog.close();delete dialog.dataset.agentRequest;}
        renderShell(projectPage());
        if(p.agent_request?.status==='completed'&&previous?.status==='pending'){
          toast(p.agent_request.task==='ideas'?'WorkBuddy saved your ideas. Choose one to develop.':'WorkBuddy saved your brief and script. Ready for your review.');
          if(p.agent_request.task==='brief'&&S.step===0)await navigate(`/projects/${pid}/brief`);
        }
      }
    }
    if(S.route.startsWith('/projects/')&&S.project?.active_job){
      const pid=S.project.id;const p=await api(`/projects/${pid}`);if(S.project?.id!==pid)return;
      const label=document.querySelector('#job-status-text');if(label)label.textContent=p.active_job?.stage||'Finishing up';
      const elapsed=document.querySelector('#job-elapsed');if(elapsed&&p.active_job?.started_at){const sec=Math.max(0,Math.floor((Date.now()-Date.parse(p.active_job.started_at))/1000));elapsed.textContent=`${duration(sec)} elapsed · Your clips are saved.`;}
      if(!p.active_job){S.project=p;S.projects=await api('/projects');renderShell(projectPage());if(p.last_job?.status==='succeeded'){toast(p.last_job.type==='export'?'Your final video is ready.':'Your draft and subtitles are ready to review.');if(p.last_job.type==='edited_prepare'&&[2,3].includes(S.step)||p.last_job.type==='prepare'&&S.step===3)await navigate(`/projects/${pid}/subtitles`);if(p.last_job.type==='export'&&S.step!==5)await navigate(`/projects/${pid}/export`);}}
    }
  }catch(error){if(error.code!=='UNAUTHORIZED')console.warn('Status refresh unavailable.');}finally{S.polling=false;}
},1800);

try{const session=await api('/session');S.csrf=session.csrf_token||'';if(session.authenticated){await refreshData();await route();}else renderAuth(session.setup_required);}catch(error){app.innerHTML=`<main class="boot" id="main"><div><h2>We couldn’t open your workspace.</h2><p>${esc(error.message)}</p><button class="btn btn-primary" id="reload-app">Try again</button></div></main>`;document.querySelector('#reload-app').addEventListener('click',()=>location.reload());}
