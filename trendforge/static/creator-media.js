// Reuse the existing upload, render, transcription and export contracts.
let C;
export function configureMedia(context){C=context;}
export async function loadMedia(){C.state.media=await C.api(`/projects/${C.state.pid}`);}
const path=()=>`/projects/${C.state.pid}`;
const disabled=()=>C.state.media?.active_job?'disabled':'';
const act=(name,label,attrs='')=>`<button type="button" class="btn" data-action="video-${name}" ${attrs}>${label}</button>`;
const stamp=n=>Number(n).toFixed(2);
export function researchPage(){
  const {esc,state}=C;
  const runs=state.media?.research||[],latest=[...runs].reverse().find(r=>r.items?.length);
  return `<section class="creator-card"><h2>Find an angle worth making.</h2><p>Search recent YouTube references for inspiration. Product claims still come from your verified source facts.</p><form id="video-research-form"><div class="field"><label for="trend-query">Topic or niche</label><input id="trend-query" name="query" required minlength="2" maxlength="150" value="${esc(state.workspace.project.niche)}"></div><div class="field"><label for="trend-period">Published within</label><select id="trend-period" name="period_days"><option value="7">7 days</option><option value="1">24 hours</option><option value="30">30 days</option></select></div><button class="btn btn-primary">Research YouTube</button></form></section>${latest?`<p class="creator-muted" style="margin-top:20px">Retrieved ${esc(latest.created_at)}. References are public metadata; popularity does not predict future views.</p><div class="creator-grid">${latest.items.map(r=>`<article class="creator-card"><h3><a href="${esc(r.watch_url)}" target="_blank" rel="noopener noreferrer">${esc(r.title)}</a></h3><p>${esc(r.channel_title)} · ${esc(r.published_at)}</p><p>Watch for storytelling ideas, then describe your chosen angle in Source & rules.</p>${act('use-reference','Use as creative inspiration',`data-id="${r.video_id}"`)}</article>`).join('')}</div>`:''}`;
}
function jobPanel(p){
 const {esc}=C,j=p.active_job||p.last_job;
 if(!j)return '';
 if(p.active_job)return `<section class="creator-status" role="status"><strong>${esc(j.stage)}</strong><p>Your source and uploads are saved. Processing continues if you leave this page.</p><progress max="100" value="${Number(j.progress_percent)||0}" aria-label="Video processing progress"></progress>${act('cancel-job','Cancel processing',`data-id="${j.id}"`)}</section>`;
 if(j.status==='failed'||j.status==='cancelled')return `<section class="creator-issue" role="alert"><strong>${j.status==='failed'?'Processing needs attention':'Processing cancelled'}</strong><p>${esc(j.error?.message||'Saved footage and completed checkpoints are retained.')}</p>${act('retry','Retry this step',`data-id="${j.id}"`)}</section>`;
 return '';
}
export function videoPage(){
 const {state,esc}=C,p=state.media,r=state.workspace.run;
 if(!r||r.status!=='approved')return `<section class="creator-card"><h2>Your approved script comes first.</h2><p>Create and approve the content before turning it into a video.</p><a class="btn btn-primary" href="/projects/${state.pid}/review" data-nav>Review content</a></section>`;
 const scripts=r.draft.contents.filter(c=>c.format==='short_script');
 if(!scripts.length)return `<section class="creator-card"><h2>Add a short-video script.</h2><p>Choose Short-video script in Source & rules, generate it and approve the reviewed content.</p></section>`;
 if(!p.brief||p.video_creator_run_id!==r.id)return `<section class="creator-card"><h2>Bring your script to life.</h2><p>Select an approved script and video length. Record your clips using this script; original spoken audio is preserved.</p><form id="video-bind-form"><div class="field"><label for="video-language">Script language</label><select id="video-language" name="language">${scripts.map(c=>`<option value="${c.language}">${esc(C.languageName[c.language])}</option>`).join('')}</select></div><div class="field"><label for="video-duration">Video length</label><select id="video-duration" name="duration">${[30,45,60].map(d=>`<option ${d===p.target_duration_seconds?'selected':''}>${d}</option>`).join('')}</select></div><div class="creator-checks"><label><input type="checkbox" name="confirmation" required>Use this approved content as the script for my video.</label></div><button class="btn btn-primary">Use approved script</button></form></section>`;
 const assets=p.assets||[],plan=p.plan,track=p.subtitle,current=p.exports?.find(e=>e.current);
 return `${jobPanel(p)}<details class="creator-card" style="margin-bottom:20px"><summary>Your recording script · ${p.target_duration_seconds}s</summary><p class="creator-output">${esc(p.brief.script)}</p><p>Record 3–5 clips with enough footage for ${p.target_duration_seconds} seconds. Keep spoken claims consistent with this script.</p></details>
 <div class="creator-grid"><section class="creator-card"><h2>1. Add your footage</h2><p>3–5 H.264 MP4/MOV clips, 3–120 seconds each, up to 100 MiB each. Use a short edge of at least 360px and a long edge up to 1920px.</p><form id="video-upload-form"><div class="field"><label for="video-clips">Choose clips</label><input type="file" id="video-clips" name="clips" accept="video/mp4,video/quicktime,.mp4,.mov" multiple required ${disabled()}></div><div class="creator-checks"><label><input type="checkbox" name="rights" required>I own these clips or have permission to use them.</label></div><button class="btn btn-primary" ${disabled()}>Upload clips</button><p id="video-upload-status" role="status"></p></form>${p.uploads?.length?`<p role="status">${p.uploads.length} upload(s) being checked.</p>`:''}${assets.map(a=>`<div class="video-asset"><div><strong>${esc(a.original_name)}</strong><p>${stamp(a.duration_seconds)}s · ${a.width} × ${a.height}${a.provenance?` · <a href="${esc(a.provenance.url)}" target="_blank" rel="noopener noreferrer">${esc(a.provenance.provider)} / ${esc(a.provenance.creator)}</a>`:''}</p></div>${act('remove-asset','Remove',`data-id="${a.id}" ${disabled()}`)}</div>`).join('')}<details><summary>Find stock footage instead</summary><form id="video-stock-form"><label for="stock-query">Search footage</label><input id="stock-query" name="query" minlength="2" maxlength="100" required><button class="btn" style="margin-top:12px">Find stock clips</button></form><div id="video-stock-results"></div></details></section>
 <section class="creator-card"><h2>2. Shape your cut</h2><p>Automatic trimming shares ${p.target_duration_seconds} seconds across your clips. Original framing is fitted into 9:16, with black padding, opening/closing fades and balanced audio.</p>${act('auto-plan','Create automatic cut',`${assets.length<3||p.active_job?'disabled':''}`)}${plan?`<form id="video-plan-form" style="margin-top:20px"><p class="creator-muted">Reorder clips or adjust trim points. Total length must equal ${p.target_duration_seconds} seconds.</p>${plan.segments.map((s,i)=>`<fieldset class="video-segment" data-segment="${s.asset_id}"><legend>${esc(assets.find(a=>a.id===s.asset_id)?.original_name||'Clip')}</legend><label>Order<input type="number" name="order-${i}" min="1" max="${assets.length}" value="${s.order}" required step="1"></label><label>Start (s)<input type="number" name="in-${i}" min="0" value="${stamp(s.in_seconds)}" step="0.01" required></label><label>End (s)<input type="number" name="out-${i}" min="0.01" value="${stamp(s.out_seconds)}" step="0.01" required></label></fieldset>`).join('')}<button class="btn" ${disabled()}>Save cut changes</button></form><div class="creator-actions" style="margin-top:20px">${plan.status==='approved'?act('prepare','Render draft & generate subtitles',disabled()):act('approve-plan','Approve this cut',disabled())}</div>`:''}</section></div>
 ${p.draft?`<section class="creator-section"><h2>3. Review the video and subtitles</h2><div class="creator-grid"><div class="creator-card"><video class="studio-player" src="/api/v1/projects/${p.id}/drafts/${p.draft.id}/media" controls playsinline preload="metadata" aria-label="Draft video preview"></video><p>${stamp(p.draft.duration_seconds)} seconds · 1080 × 1920</p><p>Subtitles are transcribed from actual Indonesian speech. Watch the video and check the words and claims against the approved script.</p></div><div class="creator-card">${act('transcribe','Retry automatic transcription',disabled())}<form id="video-subtitle-form" data-edit><div id="video-cues">${(track?.cues||[]).map(cueRow).join('')}</div><div class="creator-actions" style="margin:16px 0">${act('add-cue','Add subtitle',disabled())}</div><div class="creator-checks"><label><input type="checkbox" name="no_speech" ${track?.speech_status==='no_speech'?'checked':''}>I listened to the video and confirm there is no spoken audio.</label></div><button class="btn" ${disabled()}>Save subtitles</button></form>${track?`<form id="video-approve-subtitles" style="margin-top:20px"><div class="creator-checks"><label><input type="checkbox" name="confirmation" required>I checked the video, subtitle timing and spoken claims against the approved script.</label></div><button class="btn btn-primary" ${disabled()}>Approve reviewed subtitles</button></form>`:''}</div></div></section>`:''}
 ${track?.status==='approved'?`<section class="creator-card" style="margin-top:24px"><h2>4. Export your video</h2><p>Vertical 1080 × 1920, H.264 MP4, 30 fps and AAC audio. Approved subtitles are embedded in the video.</p>${act('export','Export MP4',disabled())}</section>`:''}
 ${current?`<section class="creator-card" style="margin-top:24px"><h2>Your finished video</h2><video class="studio-player" controls playsinline preload="metadata" src="/api/v1/projects/${p.id}/exports/${current.id}/files/mp4" aria-label="Finished video preview"></video><p>${current.metadata.width} × ${current.metadata.height} · ${stamp(current.duration_seconds)} seconds · ${(current.bytes/1024/1024).toFixed(1)} MiB</p><div class="creator-actions"><a class="btn btn-primary" href="/api/v1/projects/${p.id}/exports/${current.id}/files/mp4?download=true" download>Download MP4</a>${track.cues.length?`<a class="btn" href="/api/v1/projects/${p.id}/exports/${current.id}/files/srt?download=true" download>Download SRT</a>`:''}${act('copy-caption','Copy approved caption')}${act('ready',p.ready_confirmed_at?'Marked ready to upload':'I watched it — ready to upload',p.ready_confirmed_at?'disabled':'')}</div><p style="margin-top:16px">Watch the whole video before uploading it to YouTube Shorts or Instagram Reels.</p></section>`:''}`;
}
function cueRow(c){return `<fieldset class="video-cue"><label>Start (s)<input data-cue="start" type="number" min="0" step="0.01" value="${stamp(c.start_seconds)}" required></label><label>End (s)<input data-cue="end" type="number" min="0.01" step="0.01" value="${stamp(c.end_seconds)}" required></label><label class="video-cue-text">Subtitle text<textarea data-cue="text" required maxlength="500">${C.esc(c.text)}</textarea></label>${act('remove-cue','Remove subtitle')}</fieldset>`;}
async function refresh(){await C.loadProject(C.state.pid);await loadMedia();C.renderProject();}
async function startJob(type,body={}){await C.api(path()+'/'+type,{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()},body});await refresh();}
export async function mediaAction(action,el){
 if(!action.startsWith('video-'))return false;
 const {api,state,notify}=C,p=state.media,base=path();
 switch(action){
 case 'video-use-reference':state.pendingReferences=[...new Set([...(state.workspace.source?.inspiration_video_ids||[]),...(state.pendingReferences||[]),el.dataset.id])];if(state.pendingReferences.length>10){state.pendingReferences.pop();throw Error('Choose at most ten references.');}await C.go(`/projects/${state.pid}/source`);notify('Reference selected. Save your source to include it as creative inspiration.');return true;
 case 'video-auto-plan':await api(base+'/plans/auto',{method:'POST',body:{expected_project_revision:p.revision}});break;
 case 'video-approve-plan':await api(base+`/plans/${p.plan.id}/approve`,{method:'POST',body:{confirmation:true,expected_project_revision:p.revision}});break;
 case 'video-prepare':await startJob('prepare-jobs',{plan_id:p.plan.id});return true;
 case 'video-transcribe':await startJob('transcription-jobs',{draft_id:p.draft.id});return true;
 case 'video-export':await startJob('export-jobs');return true;
 case 'video-remove-asset':await api(base+'/assets/'+el.dataset.id,{method:'DELETE'});break;
 case 'video-cancel-job':await api(base+'/jobs/'+el.dataset.id+'/cancel',{method:'POST'});break;
 case 'video-retry':{const j=p.last_job;if(j.type==='export')await startJob('export-jobs');else if(p.draft)await startJob('transcription-jobs',{draft_id:p.draft.id});else await startJob('prepare-jobs',{plan_id:p.plan?.id});return true;}
 case 'video-add-cue':document.querySelector('#video-cues').insertAdjacentHTML('beforeend',cueRow({start_seconds:0,end_seconds:1,text:''}));state.dirty=true;return true;
 case 'video-remove-cue':el.closest('.video-cue').remove();state.dirty=true;return true;
 case 'video-ready':await api(base+'/ready-confirmation',{method:'POST',body:{export_id:p.export_id,confirmation:true}});break;
 case 'video-copy-caption':{const cs=state.workspace.run.draft.contents,caption=cs.find(c=>c.format==='social_caption'&&c.language===p.video_language)||cs.find(c=>c.format==='social_caption');await navigator.clipboard.writeText(caption?caption.lines.map(l=>l.text).join('\n'):'');notify(caption?'Approved caption copied.':'Select Social caption in your content formats first.',!caption);return true;}
 case 'video-import-stock':await api(base+'/stock/import',{method:'POST',body:{query:el.dataset.query,video_id:Number(el.dataset.id),provider:el.dataset.provider}});notify('Stock clip is being checked.');break;
 }
 await refresh();return true;
}
export async function mediaSubmit(f,data){
 if(!f.id.startsWith('video-'))return false;
 const {api,state,notify,esc}=C,p=state.media,base=path();
 if(f.id==='video-bind-form')await api(base+'/creator/video-brief',{method:'POST',body:{language:data.get('language'),duration:Number(data.get('duration')),confirmation:data.has('confirmation'),run_revision:state.workspace.run.revision,expected_project_revision:p.revision}});
 if(f.id==='video-upload-form'){
  const files=[...f.querySelector('[name=clips]').files];
  if(files.length+p.assets.length>5)throw Error('Use at most five clips in total.');
  if(!data.has('rights'))throw Error('Confirm permission to use these clips.');
  state.uploading=true;
  try{for(const file of files){if(file.size>100*1024*1024)throw Error('Each file must be no larger than 100 MiB.');await upload(file);}}
  finally{state.uploading=false;await refresh();}
  notify('Your clips were checked and saved.');return true;
 }
 if(f.id==='video-plan-form'){
  const segments=[...f.querySelectorAll('[data-segment]')].map((e,i)=>({asset_id:e.dataset.segment,order:Number(data.get('order-'+i)),in_seconds:Number(data.get('in-'+i)),out_seconds:Number(data.get('out-'+i))}));
  await api(base+'/plans',{method:'POST',body:{brief_revision_id:p.brief_id,target_duration_seconds:p.target_duration_seconds,segments,expected_project_revision:p.revision}});
 }
 if(f.id==='video-subtitle-form'){
  const cues=[...f.querySelectorAll('.video-cue')].map((e,i)=>({id:'cue_'+(i+1),start_seconds:Number(e.querySelector('[data-cue=start]').value),end_seconds:Number(e.querySelector('[data-cue=end]').value),text:e.querySelector('[data-cue=text]').value.trim()}));
  await api(base+'/subtitles',{method:'POST',body:{draft_id:p.draft.id,cues,speech_status:data.has('no_speech')?'no_speech':'speech',expected_project_revision:p.revision}});state.dirty=false;
 }
 if(f.id==='video-approve-subtitles'){
  if(state.dirty)throw Error('Save your subtitle edits before approving.');
  await api(base+`/subtitles/${p.subtitle.id}/approve`,{method:'POST',body:{confirmation:data.has('confirmation'),no_speech_decision:p.subtitle.speech_status==='no_speech',expected_project_revision:p.revision}});
 }
 if(f.id==='video-research-form'){
  const result=await api(base+'/research',{method:'POST',body:{query:data.get('query'),period_days:Number(data.get('period_days')),source_mode:'search',language:'id',region:'ID'}});
  if(!result.items?.length)notify('No references found. Try a different topic.');
 }
 if(f.id==='video-stock-form'){
  const q=data.get('query'),items=await api('/stock/search?query='+encodeURIComponent(q));
  document.querySelector('#video-stock-results').innerHTML=items.map(s=>`<article class="video-asset"><div><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.creator)} · ${Number(s.duration)}s</a><p>Check the source license and suitability before importing.</p></div>${act('import-stock','Import clip',`data-id="${s.id}" data-provider="${esc(s.provider)}" data-query="${esc(q)}" ${disabled()}`)}</article>`).join('')||'<p>No matching stock clips found.</p>';return true;
 }
 await refresh();notify('Saved.');return true;
}
async function upload(file){
 const {api,state}=C,base=path(),status=document.querySelector('#video-upload-status');
 const {upload,target}=await api(base+'/uploads',{method:'POST',body:{filename:file.name,size:file.size,purpose:'clip',rights_confirmed:true}});
 try{
  await new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open('POST',target.url);xhr.timeout=180000;if(target.url.startsWith('/'))xhr.setRequestHeader('X-CSRF-Token',state.csrf);xhr.upload.onprogress=e=>{status.textContent=`${file.name}: ${e.lengthComputable?Math.round(e.loaded/e.total*100):0}%`;};xhr.onload=()=>xhr.status>=200&&xhr.status<300?resolve():reject(Error('Upload failed. Please try again.'));xhr.onerror=xhr.ontimeout=()=>reject(Error('Upload connection interrupted. Please try again.'));const form=new FormData();for(const[k,v]of Object.entries(target.fields||{}))form.append(k,v);form.append('file',file);xhr.send(form);});
  await api(base+'/uploads/'+upload.id+'/complete',{method:'POST'});
  status.textContent=`Checking ${file.name}…`;
  const deadline=Date.now()+120000;
  while(Date.now()<deadline){const u=await api(base+'/uploads/'+upload.id);if(u.status==='valid')return;if(['rejected','cancelled','expired'].includes(u.status))throw Error(u.error?.message||'This clip could not be accepted.');await new Promise(r=>setTimeout(r,900));}
  throw Error('Checking took too long. Refresh to see the saved upload status.');
 }catch(e){await api(base+'/uploads/'+upload.id,{method:'DELETE'}).catch(()=>{});throw e;}
}
