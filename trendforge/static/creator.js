import {configureMedia,loadMedia,videoPage,researchPage,mediaAction,mediaSubmit} from './creator-media.js?v=video-1';
const root=document.querySelector('#app');
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state={csrf:'',user:null,projects:[],workspace:null,status:{},busy:false,dirty:false,tab:'source',pid:null};
const formatName={short_script:'Short-video script',social_caption:'Social caption',marketplace_listing:'Marketplace listing'};
const languageName={id:'Bahasa Indonesia',en:'English',zh:'Mandarin'};
const labels={running:'Your agent team is working',waiting_for_workbuddy:'Waiting for WorkBuddy',awaiting_approval:'Ready for your review',approved:'Approved by you',escalated:'Your guidance is needed',cancelled:'Run cancelled',interrupted:'Run interrupted'};
const active=r=>r&&['running','waiting_for_workbuddy'].includes(r.status);
const button=(action,label,disabled=false)=>`<button type="button" class="btn" data-action="${action}" ${disabled?'disabled':''}>${label}</button>`;

async function api(path,options={}){
  const headers=new Headers(options.headers||{});if(state.csrf)headers.set('X-CSRF-Token',state.csrf);
  if(options.body){headers.set('Content-Type','application/json');options.body=JSON.stringify(options.body);}
  const response=await fetch('/api/v1'+path,{...options,headers});
  const result=response.status===204?null:await response.json();
  if(!response.ok)throw new Error(result?.error?.message||'The request could not be completed.');
  return result;
}
function notify(text,error=false){const el=document.createElement('div');el.className='toast'+(error?' error':'');el.role=error?'alert':'status';el.textContent=text;document.querySelector('#toasts').append(el);setTimeout(()=>el.remove(),6500);}
async function work(fn){if(state.busy)return;state.busy=true;document.body.dataset.busy='true';try{await fn();}catch(e){notify(e.message,true);}finally{state.busy=false;delete document.body.dataset.busy;}}
function connectionPanel(){
  const c=state.status.workbuddy_connection||{state:'unknown'},seen=c.last_seen_at?new Date(c.last_seen_at).toLocaleString():'';
  const copy={
    connected:['WorkBuddy connected recently','Your connector reached TrendForge within the last 10 minutes.'],
    not_connected:['WorkBuddy not connected','No verified connector activity for your account. Install your package from Connections, then ask WorkBuddy to run trendforge_health.'],
    inactive:['WorkBuddy connection needs a check','No connector activity recorded in the last 10 minutes. Ask WorkBuddy to run trendforge_health, then refresh this status.'],
    not_selected:['WorkBuddy not selected','This workspace is using an alternative writing provider.'],
    unknown:['WorkBuddy status unavailable','We could not check the connector. Refresh the status to try again.']
  }[c.state]||['WorkBuddy status unavailable','Refresh the status to try again.'];
  return `<div class="creator-connection" data-state="${esc(c.state)}"><div><strong><span class="creator-connection-dot" aria-hidden="true"></span>${copy[0]}</strong><p>${copy[1]}${seen?` <span>Last recorded contact: ${esc(seen)}.</span>`:''}${c.state==='connected'?' This checks recent activity, not a continuous connection.':''}</p></div><div class="creator-actions"><a href="/connections" data-nav>Connection setup</a>${button('refresh-connection','Refresh status')}</div></div>`;
}
async function refreshConnection(){
  try{state.status=await api('/creator/status');}
  catch(e){state.status={...state.status,workbuddy_connection:{state:'unknown'}};throw e;}
  finally{const el=document.querySelector('#workbuddy-status');if(el)el.innerHTML=connectionPanel();}
}
function workflowGuide(project=false){
  const run=project?state.workspace.run:null,media=project&&state.media;
  const current=!project?null:!state.workspace.source?'source':active(run)?'generate':run?.status==='awaiting_approval'?'review':run?.status==='approved'?(state.tab==='review'?'approve':media?.subtitle?.status==='approved'?'export':'video'):run?.draft?'review':state.tab==='source'?'source':'generate';
  const steps=[
    ['source','Source','Add verified product facts, brand tone, formats and languages.'],
    ['generate','Generate','Select Create & review, then copy the task into WorkBuddy.'],
    ['review','Review','Read the drafts, source quotes and fixes from the Reviewer.'],
    ['approve','Approve','Confirm the exact content yourself. Edits require another review.'],
    ['video','Video','Optional: add 3–5 clips, approve the cut and check subtitles.'],
    ['export','Export','Download approved content or the finished MP4. Upload manually.']
  ];
  return `<section class="creator-workflow" aria-labelledby="workflow-title"><h2 id="workflow-title">From source to something you can share</h2><p>Follow the steps below. You decide what is approved and ready to upload.</p><ol>${steps.map(([id,title,description],i)=>`<li ${current===id?'aria-current="step"':''}><span class="creator-step-number">${i+1}</span><div><h3>${title}${current===id?'<span class="creator-step-current">Current step</span>':''}</h3><p>${description}</p></div></li>`).join('')}</ol></section>`;
}
function shell(content){
  const name=state.user?.display_name||state.user?.username||'',connections=location.pathname==='/connections';
  root.innerHTML=`<div class="creator-shell"><header class="creator-header"><a class="creator-brand" href="/" data-nav aria-label="TrendForge home"><img src="/static/mark.svg" alt="">trendforge</a><nav class="creator-nav" aria-label="Main navigation"><a href="/" data-nav ${!connections?`aria-current="${location.pathname==='/'?'page':'location'}"`:''}>Projects</a><a href="/connections" data-nav ${connections?'aria-current="page"':''}>Connections</a></nav><div class="creator-account" role="group" aria-label="${esc('Signed in as '+name)}"><span class="creator-avatar" aria-hidden="true" title="${esc(name)}">${esc(Array.from(name)[0]?.toUpperCase()||'')}</span><span class="creator-account-name" title="${esc(name)}">${esc(name)}</span>${button('logout','Sign out')}</div></header><section id="workbuddy-status" aria-label="WorkBuddy connection" aria-live="polite">${connectionPanel()}</section><main id="main">${content}</main><footer class="creator-footer"><span>Source facts. Thoughtful review. Your final say.</span><span>Planner → Writer → Reviewer · Up to 3 review rounds</span></footer></div>`;
}
function auth(register=false){
  root.innerHTML=`<main class="creator-shell" id="main"><header class="creator-header"><span class="creator-brand"><img src="/static/mark.svg" alt="">trendforge</span></header><form class="creator-form" id="auth-form" data-register="${register}"><span class="creator-label">Your creator workspace</span><h1>${register?'Create your account':'Welcome back.'}</h1><p>Make something you feel confident sharing.</p><div class="field"><label for="username">Username</label><input id="username" name="username" autocomplete="username" required minlength="3" maxlength="32"></div><div class="field"><label for="password">Password</label><input id="password" name="password" type="password" autocomplete="${register?'new-password':'current-password'}" minlength="8" required></div><button class="btn btn-primary" type="submit">${register?'Create account':'Sign in'}</button><p class="creator-form-error" id="auth-error" role="alert"></p><button type="button" class="btn btn-quiet" data-action="${register?'show-login':'show-register'}">${register?'Already have an account? Sign in':'Create an account'}</button></form></main>`;
}
async function loadProject(pid){if(state.pid!==pid){state.pendingReferences=null;state.media=null;}state.workspace=await api(`/projects/${pid}/creator`);state.pid=pid;}
async function route(){
  const match=location.pathname.match(/^\/projects\/([^/]+)(?:\/(source|review|audit|video|research))?/);
  state.dirty=false;
  if(match){state.tab=match[2]||'source';await loadProject(match[1]);if(['video','research'].includes(state.tab))await loadMedia();renderProject();return;}
  if(location.pathname==='/connections'){state.pid=null;await renderConnections();return;}
  state.pid=null;state.projects=await api('/projects');home();
}
async function go(path){if(state.dirty&&!confirm('Leave without saving your changes?'))return;history.pushState({},'',path);await route();window.scrollTo({top:0,behavior:'instant'});}
function home(){
  document.title='TrendForge — Create with confidence';
  shell(`<section class="creator-hero"><span class="creator-label">A little more confidence</span><h1>Your story.<br>Your facts. Your final say.</h1><p>Turn one product sheet into content for different formats. A Planner shapes the idea, a Writer drafts it, and a Reviewer helps you catch unsupported claims before you share.</p></section>${workflowGuide()}<div class="creator-grid"><form class="creator-card" id="new-project"><h2>Start with your product.</h2><div class="field"><label for="project-title">Project name</label><input id="project-title" name="niche" required minlength="2" maxlength="100" placeholder="Your product launch"></div><div class="field"><label for="project-audience">Who are you creating for?</label><input id="project-audience" name="audience" required minlength="2" maxlength="200" placeholder="First-time customers, students, your community…"></div><button class="btn btn-primary" type="submit">Create project</button></form><aside class="creator-card"><h2>What happens here</h2><p>Add the facts you can stand behind. Choose your formats and languages, then let the team draft and review.</p><p>You will see every rejection, the rule behind it, and what changed. If the team cannot resolve an issue after three rounds, it stops and asks for your help.</p><p class="creator-note">Nothing is published automatically. Approved content can become a vertical MP4 with your own clips and reviewed subtitles.</p></aside></div><section class="creator-section"><h2>Your projects</h2><div class="creator-grid">${state.projects.map(p=>`<a class="creator-card creator-project" href="/projects/${p.id}/source" data-nav><h3>${esc(p.niche)}</h3><p>${esc(p.audience)}</p><span class="creator-muted">Open workspace →</span></a>`).join('')||'<p class="creator-muted">Your first project will appear here.</p>'}</div></section>`);
}
function sourceForm(){
  const {project:p,source:s,run}=state.workspace;const value=s||{};const references=state.pendingReferences||value.inspiration_video_ids||[];
  return `<div class="creator-grid"><form id="source-form" class="creator-card" data-edit><div class="creator-actions" style="justify-content:space-between"><h2>Facts first.</h2>${button('load-demo','Load fictional example',active(run))}</div><p>Paste one verified fact per line. Source instructions and testimonials are reviewed as data, not commands.</p>${references.length?`<p class="creator-note">${references.length} YouTube reference(s) selected for creative inspiration. Product claims still use your facts below.</p>`:''}${references.map(id=>`<input type="hidden" name="inspiration_video_ids" value="${esc(id)}">`).join('')}<div class="field"><label for="source-title">Source title or document reference</label><input id="source-title" name="source_title" required minlength="2" maxlength="180" value="${esc(value.source_title)}" placeholder="Product sheet — version or date"></div><div class="field"><label for="source-facts">Product facts · one per line</label><textarea class="creator-long" id="source-facts" name="facts" required placeholder="Product name\nIngredients or materials\nVerified size and price\nUsage instructions">${esc(value.facts?.join('\n'))}</textarea><small class="creator-muted">Up to 20 facts. Do not include customer contact details or private records.</small></div><div class="field"><label for="source-audience">Audience</label><input id="source-audience" name="audience" required minlength="2" maxlength="240" value="${esc(value.audience||p.audience)}"></div><div class="field"><label for="source-tone">Brand tone</label><input id="source-tone" name="tone" required minlength="3" maxlength="400" value="${esc(value.tone||'Friendly, honest and encouraging')}"></div><div class="field"><label for="source-direction">Creative direction or requested angle</label><textarea id="source-direction" name="direction" maxlength="1500" placeholder="What would you like to communicate? Rules still apply to requested claims.">${esc(value.direction)}</textarea></div><fieldset><legend>Choose at least two formats</legend><div class="creator-checks">${Object.entries(formatName).map(([k,v])=>`<label><input type="checkbox" name="formats" value="${k}" ${(value.formats||['short_script','social_caption']).includes(k)?'checked':''}>${v}</label>`).join('')}</div></fieldset><fieldset><legend>Languages</legend><div class="creator-checks">${Object.entries(languageName).map(([k,v])=>`<label><input type="checkbox" name="languages" value="${k}" ${(value.languages||['id']).includes(k)?'checked':''}>${v}</label>`).join('')}</div></fieldset><details><summary>Halal certificate evidence · only when verified</summary><p class="creator-muted">The application does not verify certification with an external authority. You must check the evidence before confirming it.</p><div class="field"><label for="cert-ref">Certificate reference</label><input id="cert-ref" name="certificate_reference" maxlength="200" value="${esc(value.certificate_reference)}"></div><div class="field"><label for="cert-issuer">Issuer</label><input id="cert-issuer" name="certificate_issuer" maxlength="120" value="${esc(value.certificate_issuer)}"></div><div class="field"><label for="cert-expiry">Valid until</label><input type="date" id="cert-expiry" name="certificate_expiry" value="${esc(value.certificate_expiry)}"></div><div class="creator-checks"><label><input type="checkbox" name="certificate_verified" ${value.certificate_verified?'checked':''}>I checked the certificate reference, issuer and validity.</label></div></details><div class="creator-actions" style="margin-top:24px"><button class="btn btn-primary" type="submit" ${active(run)?'disabled':''}>Save source</button>${button('run','Create & review',!s||active(run))}</div></form><aside><div class="creator-card"><h2>Your review rules</h2><p>These rules stay in place even when a brief asks for a prohibited claim.</p>${state.workspace.rules.map(r=>`<details class="creator-audit"><summary>${esc(r.id)}</summary><p class="small">${esc(r.text)}</p><small class="creator-muted">${esc(r.basis)}</small></details>`).join('')}</div><div class="creator-note" style="margin-top:18px">The agent uses your supplied facts only. Approved content from your own projects can guide its tone. Another creator's projects are never used.</div></aside></div>`;
}
function pipeline(run){return `<div class="creator-pipeline">${[['Planner','Chooses the angle and source facts.'],['Writer','Creates the requested formats.'],['Reviewer','Checks facts, tone and claims.']].map(([r,d],i)=>`<div class="creator-agent ${active(run)&&run.stage===r?'active':''}"><small>0${i+1} · ${run?.trace?.some(t=>t.role===r)?'Recorded':r==='Planner'&&(run?.parent_run_id||run?.trace?.[0]?.role==='Reviewer')?'Earlier revision':'Not started'}</small><h3>${r}</h3><p>${d}</p></div>`).join('')}</div>`;}
function issueCards(issues){return issues.map(i=>`<div class="creator-issue"><strong>${esc(i.rule_id)}</strong><small> · ${esc(i.line_id)}</small><blockquote>“${esc(i.quote)}”</blockquote><p>${esc(i.reason)}</p><p>Next: ${esc(i.fix)}</p></div>`).join('');}
function contentCards(run,editing=false){return run.draft.contents.map((c,ci)=>`<article class="creator-card"><div class="creator-label">${esc(languageName[c.language])}</div><h2>${esc(formatName[c.format])}</h2>${c.lines.map((l,li)=>`<div class="creator-output">${editing?`<label for="line-${ci}-${li}">Line ${li+1}</label><textarea id="line-${ci}-${li}" data-content="${ci}" data-line="${li}" required minlength="2" maxlength="800">${esc(l.text)}</textarea>`:esc(l.text)}<small class="creator-evidence">${l.evidence.length?l.evidence.map(e=>`${esc(e.fact_id)}: “${esc(e.quote)}”`).join('<br>'):'Creative line · no new factual claim permitted'}</small></div>`).join('')}</article>`).join('');}
function reviewPage(){
  const run=state.workspace.run;
  if(!run)return `<div class="creator-card"><h2>Your team is ready when you are.</h2><p>Save your source facts first, then start the agent team.</p><a class="btn btn-primary" href="/projects/${state.pid}/source" data-nav>Add source facts</a></div>`;
  const rejected=run.trace.filter(t=>t.role==='Reviewer'&&(t.enforced_issues||t.output?.issues||[]).length);
  return `${pipeline(run)}<section class="creator-status" role="status"><strong>${esc(labels[run.status]||run.status)}</strong><p>Round ${run.iteration} of 3 · ${esc(run.stage)}${run.brand_examples?.length?' · Your approved content guides the tone':''}</p><p>${esc(run.message||({running:'You can see the agent exchange in Audit. Nothing is approved or published while this runs.',waiting_for_workbuddy:'Enable the TrendForge connector in WorkBuddy, then copy the task below.',awaiting_approval:'Every requested format passed the current rules. Read the content and source evidence before approving.',approved:'You approved this exact revision. You can download your content, cover assets and audit.'}[run.status]||'Your source and previous revisions are saved.'))}</p><div class="creator-actions" style="margin-top:14px">${active(run)?button('cancel','Cancel run'):button('run','Start a new run')}${run.status==='waiting_for_workbuddy'?button('copy-workbuddy','Copy WorkBuddy task'):''}</div></section>${run.issues?.length?`<h2>These issues need attention</h2>${issueCards(run.issues)}`:''}${rejected.length?`<details class="creator-card creator-audit" style="margin-bottom:22px"><summary>${rejected.length} review rejection${rejected.length===1?'':'s'} recorded · see what changed</summary>${rejected.map(t=>`<h3>Round ${t.iteration}</h3>${issueCards(t.enforced_issues||t.output.issues)}`).join('')}</details>`:''}${run.draft?`<div class="creator-grid">${contentCards(run)}</div>`:''}${run.status==='awaiting_approval'?`<form class="creator-card" id="approve-form" style="margin-top:22px"><h2>You have the final say.</h2><p>Check the wording, facts and all language versions. AI review can miss things; your approval is required for release.</p><div class="creator-checks"><label><input type="checkbox" name="confirmation" required>I reviewed all formats and their source evidence.</label></div><button type="submit" class="btn btn-primary">Approve this content</button></form>`:''}${run.status==='approved'?`<div class="creator-card" style="margin-top:22px"><h2>Ready for your next step.</h2><p>Turn this script into a vertical MP4 in Video studio, or download the approved text, cover assets and audit as a ZIP.</p><a class="btn btn-primary" href="/projects/${state.pid}/video" data-nav>Make a video</a> <a class="btn" href="/api/v1/projects/${state.pid}/creator/runs/${run.id}/export" download>Download approved content</a></div>`:''}${run.draft&&!active(run)?`<div class="creator-actions" style="margin-top:24px">${button('edit-content','Edit copy & send back to Reviewer')}</div><div id="edit-content"></div>`:''}`;
}
function auditPage(){
  const {run,runs,rule_proposals}=state.workspace;
  return `<div class="creator-card"><h2>Every decision has a trail.</h2><p>Source snapshots, role inputs, outputs, rejections and human approval stay attached to each revision.</p>${runs.map(r=>`<details class="creator-audit" ${r.id===run?.id?'open':''}><summary>${esc(labels[r.status]||r.status)} · ${esc(r.id)} · ${esc(new Date(r.created_at).toLocaleString())}</summary><p class="creator-muted">Engine: ${esc(r.engine)} · Model: ${esc(r.model)} · Source: ${esc(r.source_id)}${r.approved_at?' · Human approval: '+esc(r.approved_at):''}</p>${r.trace.map(t=>`<details class="creator-audit"><summary>Round ${t.iteration} · ${esc(t.role)} · ${esc(t.at)}</summary><pre>${esc(JSON.stringify(t,null,2))}</pre></details>`).join('')||'<p>No agent exchange yet.</p>'}</details>`).join('')||'<p>No runs yet. Your first run will appear here.</p>'}</div>${rule_proposals.length?`<section class="creator-section"><h2>Your edits can guide future drafts.</h2><p>A proposed tone preference never changes mandatory safety rules. You must approve it first.</p>${rule_proposals.map(r=>`<div class="creator-card" style="margin-bottom:15px"><p>${esc(r.text)}</p><span class="badge">${esc(r.status)}</span>${r.status==='proposed'?button('approve-rule','Approve tone preference',false).replace('data-action="approve-rule"',`data-action="approve-rule" data-id="${r.id}"`):''}</div>`).join('')}</section>`:''}`;
}
function renderProject(){
  const {project:p}=state.workspace;
  document.title=p.niche+' — TrendForge';
  shell(`<section class="creator-hero" style="padding-bottom:8px"><span class="creator-label">Product launch workspace</span><h1 style="font-size:34px">${esc(p.niche)}</h1><p>${esc(p.audience)}</p></section>${workflowGuide(true)}<nav class="creator-tabs" aria-label="Content workflow">${[['research','Trend research'],['source','Source & rules'],['review','Create & review'],['video','Video studio'],['audit','Audit & revisions']].map(([k,v])=>`<a href="/projects/${p.id}/${k}" data-nav ${state.tab===k?'aria-current="page"':''}>${v}</a>`).join('')}</nav>${state.tab==='source'?sourceForm():state.tab==='audit'?auditPage():state.tab==='video'?videoPage():state.tab==='research'?researchPage():reviewPage()}`);
}
async function renderConnections(){
  document.title='Connections — TrendForge';
  const [status,tokens]=await Promise.all([api('/creator/status'),api('/tokens')]);state.status=status;
  shell(`<section class="creator-hero"><h1>Your connected workspace.</h1><p>Service credentials are managed in the backend. You only need your source facts to create.</p></section><div class="creator-grid"><div class="creator-card"><h2>AI writing & review</h2><p>${state.status.engine==='workbuddy'?'WorkBuddy':'Configured writing provider'}</p><p class="creator-muted">${state.status.engine==='workbuddy'?'Use the local connector and complete each agent role in WorkBuddy.':state.status.configured?'Credentials configured. Each run records actual completion or failure.':'Awaiting a key from the workspace owner.'}</p><p class="creator-muted">Model: ${esc(state.status.model||'Selected in WorkBuddy')}</p></div><div class="creator-card"><h2>Your account & database</h2><p>${esc(state.user.username)} · ${esc(state.status.database==='turso'?'Turso Cloud':'SQLite on this device')}</p><p>Only you and your personal connector can access your projects. Approval and export require your website session.</p><p class="creator-note">Download approved content and upload it yourself to your chosen platform.</p></div><div class="creator-card"><h2>WorkBuddy connector</h2><p>Create a personal connector once, then use its Planner, Writer and Reviewer tools. Keep the generated configuration private.</p><div style="display:flex;gap:8px;flex-wrap:wrap">${button('connector-package','Download WorkBuddy package')}${button('connector','Show configuration')}</div><div id="connector-result"></div><div style="margin-top:18px">${tokens.map(t=>`<p>${esc(t.label)} <button type="button" class="btn" data-action="revoke-token" data-id="${esc(t.id)}">Revoke access</button></p>`).join('')||'<p class="creator-muted">No personal connectors.</p>'}</div></div><div class="creator-card"><h2>Accountability</h2><p>Agents see supplied source facts, approved brand examples from your projects, documented rules and previous review findings. They cannot approve content, access another user's projects or publish.</p><p>The team stops after three review rounds, or after its ${Math.round((state.status.budget_seconds||180)/60*10)/10}-minute execution budget, and hands unresolved issues to you.</p></div></div>`);
}

document.addEventListener('click',event=>{
  const link=event.target.closest('[data-nav]');if(link){event.preventDefault();work(()=>go(link.getAttribute('href')));return;}
  const el=event.target.closest('[data-action]');if(!el||el.disabled)return;const action=el.dataset.action;
  if(action==='show-register'){auth(true);return;}if(action==='show-login'){auth(false);return;}
  if(action==='load-demo'){
    if(state.dirty&&!confirm('Replace these unsaved fields with fictional demo facts?'))return;
    document.querySelector('#source-title').value='Fictional demo sheet — Senja Ginger Tea';
    document.querySelector('#source-facts').value='Senja Ginger Tea is a fictional ginger drink.\nIngredients: ginger and palm sugar.\nEach box contains 10 sachets.\nPrice: Rp25000 per box.\nServe one sachet with warm water.';
    document.querySelector('#source-direction').value='Introduce the product honestly to first-time customers.';state.dirty=true;return;
  }
  if(action==='edit-content'){
    document.querySelector('#edit-content').innerHTML=`<form id="content-edit-form" data-edit><p class="creator-note">Every edit is reviewed again. Evidence stays visible; unsupported changes will be rejected. A tone preference is proposed separately for your approval.</p><div class="creator-grid">${contentCards(state.workspace.run,true)}</div><button class="btn btn-primary" style="margin-top:20px" type="submit">Send edits to Reviewer</button></form>`;return;
  }
  work(async()=>{
    if(action==='refresh-connection'){await refreshConnection();notify('Connection status refreshed.');return;}
    if(await mediaAction(action,el))return;
    const r=state.workspace?.run,base=`/projects/${state.pid}/creator`;
    if(action==='logout'){await api('/session',{method:'DELETE'});state.csrf='';state.user=null;state.pid=null;auth();}
    if(action==='run'){
      if(state.dirty){notify('Save your source or edits before starting a run.',true);return;}
      await api(base+'/runs',{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()}});await go(`/projects/${state.pid}/review`);
    }
    if(action==='cancel'){await api(base+`/runs/${r.id}/cancel`,{method:'POST'});await loadProject(state.pid);renderProject();}
    if(action==='copy-workbuddy'){
      const prompt=`Use the TrendForge creator workflow for project ${state.pid}, run ${r.id}. Call creator_next_step, perform its requested Planner, Writer or Reviewer role using its exact schema, then call creator_submit_step with the returned revision. Continue until awaiting_approval or escalated. Never approve or export on my behalf.`;
      await navigator.clipboard.writeText(prompt);notify('Task copied. Paste it into WorkBuddy.');
    }
    if(action==='approve-rule'){await api(base+`/rules/${el.dataset.id}/approve`,{method:'POST',body:{confirmation:true}});await loadProject(state.pid);renderProject();notify('Tone preference approved for future runs.');}
    if(action==='revoke-token'){await api('/tokens/'+el.dataset.id,{method:'DELETE'});await renderConnections();notify('Connector access revoked.');}
    if(action==='connector-package'){
      const response=await fetch('/api/v1/settings/connector-package',{method:'POST',headers:{'X-CSRF-Token':state.csrf}});
      if(!response.ok){const r=await response.json().catch(()=>null);throw new Error(r?.error?.message||'The package could not be created.');}
      const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download='trendforge-workbuddy.zip';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
      await renderConnections();notify('Package downloaded. It contains a personal token, so keep it private.');
    }
    if(action==='connector'){
      const result=await api('/settings/connector',{method:'POST',body:{label:'TrendForge creator agent'}});
      document.querySelector('#connector-result').innerHTML=`<p class="creator-muted">This personal token is shown once. Save this configuration in WorkBuddy; do not share it.</p><pre style="white-space:pre-wrap;word-break:break-all">${esc(JSON.stringify(result.config,null,2))}</pre>`;
    }
  });
});
document.addEventListener('submit',event=>{
  event.preventDefault();const f=event.target;if(!(f instanceof HTMLFormElement))return;
  work(async()=>{
    const data=new FormData(f);
    if(await mediaSubmit(f,data))return;
    if(f.id==='auth-form'){
      try{const result=await api(f.dataset.register==='true'?'/auth/register':'/session',{method:'POST',body:Object.fromEntries(data)});state.csrf=result.csrf_token;state.user=result.user;state.status=await api('/creator/status');await route();}
      catch(e){document.querySelector('#auth-error').textContent=e.message;}return;
    }
    if(f.id==='new-project'){
      const p=await api('/projects',{method:'POST',body:{niche:data.get('niche'),audience:data.get('audience'),goal:'Create source-grounded content with documented review and human approval',platform:'both',language:'id',target_duration_seconds:30}});await go(`/projects/${p.id}/source`);return;
    }
    const base=`/projects/${state.pid}/creator`;
    if(f.id==='source-form'){
      const body=Object.fromEntries(data);body.facts=body.facts.split('\n').map(x=>x.trim()).filter(Boolean);body.inspiration_video_ids=data.getAll('inspiration_video_ids');body.formats=data.getAll('formats');body.languages=data.getAll('languages');body.certificate_verified=data.has('certificate_verified');
      await api(base+'/source',{method:'POST',body});state.dirty=false;state.pendingReferences=null;await loadProject(state.pid);renderProject();notify('Source saved. Your agent team can begin.');
    }
    if(f.id==='approve-form'){const r=state.workspace.run;await api(base+`/runs/${r.id}/approve`,{method:'POST',body:{confirmation:data.has('confirmation'),revision:r.revision}});await loadProject(state.pid);renderProject();notify('You approved the reviewed content.');}
    if(f.id==='content-edit-form'){
      const draft=structuredClone(state.workspace.run.draft);f.querySelectorAll('[data-content]').forEach(el=>draft.contents[Number(el.dataset.content)].lines[Number(el.dataset.line)].text=el.value);
      await api(base+`/runs/${state.workspace.run.id}/edit`,{method:'POST',body:draft});state.dirty=false;await loadProject(state.pid);renderProject();notify('Edits submitted for a fresh review.');
    }
  });
});
document.addEventListener('input',e=>{if(e.target.closest('[data-edit]'))state.dirty=true;});
window.addEventListener('beforeunload',e=>{if(state.dirty||state.uploading){e.preventDefault();e.returnValue='';}});
window.addEventListener('popstate',()=>work(route));
let checkingConnection=false;
setInterval(async()=>{
  if(checkingConnection||state.busy||!state.user||document.hidden)return;
  checkingConnection=true;try{await refreshConnection();}catch{}finally{checkingConnection=false;}
},15000);
let polling=false;
setInterval(async()=>{
  if(polling||state.busy||!state.pid||state.dirty||state.uploading)return;
  if(state.tab==='video'&&(state.media?.active_job||state.media?.uploads?.length)){
    polling=true;try{await loadMedia();renderProject();}catch(e){notify(e.message,true);}finally{polling=false;}return;
  }
  if(!active(state.workspace?.run))return;polling=true;
  try{const w=await api(`/projects/${state.pid}/creator`);if(w.run?.revision!==state.workspace?.run?.revision){state.workspace=w;renderProject();}}
  catch(e){notify(e.message,true);}finally{polling=false;}
},2500);
configureMedia({api,state,esc,notify,loadProject,renderProject,languageName,go});
try{const session=await api('/session');state.csrf=session.csrf_token||'';state.user=session.user;if(session.authenticated){state.status=await api('/creator/status');await route();}else auth();}
catch(e){root.innerHTML=`<main class="creator-shell" id="main"><h1>We could not open your workspace.</h1><p>${esc(e.message)}</p><a class="btn" href="/">Reload</a></main>`;}
