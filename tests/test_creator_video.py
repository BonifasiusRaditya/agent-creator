"""The approved three-agent workflow must reach a real, validated MP4."""
import json
import subprocess
from pathlib import Path

from conftest import another_user, upload_video, approve
from test_creator_agents import automate, setup, wait
from test_video_e2e import wait_job
from test_workbuddy import connector_headers
from trendforge.media import ffmpeg, probe


def approved_script(c, monkeypatch):
    automate(c, monkeypatch)
    pid, base, _ = setup(c)
    c.post(base+'/runs',headers={'Idempotency-Key':'video-content'})
    run=wait(c,base)
    result=c.post(base+f"/runs/{run['id']}/approve",json={'confirmation':True,'revision':run['revision']})
    assert result.status_code==200,result.text
    return pid,base,result.json()


def bind(c,pid,run):
    p=c.get(f'/api/v1/projects/{pid}').json()
    result=c.post(f'/api/v1/projects/{pid}/creator/video-brief',json={'run_revision':run['revision'],
        'expected_project_revision':p['revision'],'language':'id','duration':30,'confirmation':True})
    assert result.status_code==201,result.text
    return result.json()


def test_video_bridge_scope_approval_and_staleness(client,monkeypatch):
    pid,base,run=approved_script(client,monkeypatch)
    headers=connector_headers(client)
    body={'run_revision':run['revision'],'language':'id','duration':30,'confirmation':True}
    assert client.post(base+'/video-brief',headers=headers,json=body).status_code==403
    assert another_user(client).post(base+'/video-brief',json=body).status_code==404
    assert client.post(base+'/video-brief',json={**body,'run_revision':1}).status_code==409
    assert client.post(base+'/video-brief',json={**body,'language':'zh'}).status_code==409
    b=bind(client,pid,run)
    assert b['script']=='Senja is a ginger drink.'
    assert bind(client,pid,run)['id']==b['id']
    client.post(base+'/runs',headers={'Idempotency-Key':'changed-content'})
    assert client.get(f'/api/v1/projects/{pid}').json()['brief_id'] is None
    assert client.post(f'/api/v1/projects/{pid}/prepare-jobs',json={}).status_code==409


def test_reviewed_content_to_real_mp4_and_source_invalidation(client,monkeypatch,tmp_path):
    pid,creator,run=approved_script(client,monkeypatch)
    bind(client,pid,run)
    base=f'/api/v1/projects/{pid}'
    for i,color in enumerate(['orange','gray','black']):
        clip=tmp_path/f'owned-{i}.mp4'
        subprocess.run([ffmpeg(),'-hide_banner','-loglevel','error','-y','-f','lavfi','-i',
            f'color=c={color}:s=360x640:r=24','-t','11','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',str(clip)],check=True,capture_output=True)
        upload_video(client,pid,clip,clip.name)
    p=client.get(base).json()
    plan=client.post(base+'/plans/auto',json={'expected_project_revision':p['revision']})
    assert plan.status_code==201,plan.text
    approve(client,pid,'plans',plan.json()['id'])
    j=client.post(base+'/prepare-jobs',headers={'Idempotency-Key':'creator-prepare'},json={'plan_id':plan.json()['id']})
    assert j.status_code==202,j.text
    assert client.post(creator+'/runs',headers={'Idempotency-Key':'not-during-render'}).status_code==409
    wait_job(client,pid,j.json()['id'])
    p=client.get(base).json()
    assert p['subtitle']['speech_status']=='no_speech'
    assert client.post(base+'/export-jobs',headers={'Idempotency-Key':'premature'},json={}).status_code==409
    approve(client,pid,'subtitles',p['subtitle_id'],no_speech_decision=True)
    # Manual subtitles are explicitly reviewed text, never represented as ASR output.
    p=client.get(base).json()
    sub=client.post(base+'/subtitles',json={'draft_id':p['draft_id'],'expected_project_revision':p['revision'],
        'speech_status':'speech','cues':[{'id':'reviewed-text','start_seconds':1,'end_seconds':5,'text':'Senja: jahe dan gula aren.'}]})
    assert sub.status_code==201,sub.text
    approve(client,pid,'subtitles',sub.json()['id'])
    r=client.post(base+'/export-jobs',headers={'Idempotency-Key':'creator-export'},json={})
    assert r.status_code==202,r.text
    job=wait_job(client,pid,r.json()['id'])
    eid=job['output']['export_id']
    response=client.get(base+f'/exports/{eid}/files/mp4?download=true')
    assert response.status_code==200,response.text
    output=Path('test-results/complete-video/automated-final.mp4');output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(response.content)
    meta=probe(output)
    assert (meta['width'],meta['height'],meta['fps'],meta['video_codec'],meta['audio_codec'])==(1080,1920,30,'h264','aac')
    assert abs(meta['duration_seconds']-30)<.12
    assert 'Senja:' in client.get(base+f'/exports/{eid}/files/srt').text
    assert client.post(base+'/ready-confirmation',json={'export_id':eid,'confirmation':True}).status_code==200
    assert client.get(base+f'/exports/{eid}/files/mp4',headers=connector_headers(client)).status_code==403
    source=client.get(creator).json()['source']
    source={k:v for k,v in source.items() if k not in {'id','project_id','created_at','fact_map','inspiration_references'}}
    assert client.post(creator+'/source',json=source).status_code==201
    assert client.get(base+f'/exports/{eid}/files/mp4').status_code==409
    (output.parent/'automated-report.json').write_text(json.dumps({'metadata':meta,'bytes':len(response.content),'source_change_revokes_release':True},indent=2))
