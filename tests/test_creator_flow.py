import json
import subprocess
import time

import httpx
import pytest

from conftest import approve, brief, project, upload_video
from trendforge import integrations
from trendforge.media import ffmpeg, probe


def wait(client, base, job):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        current = client.get(base + '/jobs/' + job['id']).json()
        if current['status'] in {'succeeded', 'failed', 'cancelled'}:
            assert current['status'] == 'succeeded', current
            return current
        time.sleep(.15)
    pytest.fail('Job did not finish')


def test_finished_edit_without_assets_or_plan_exports_actual_duration(client, tmp_path):
    p = project(client, 30)
    base = f"/api/v1/projects/{p['id']}"
    b = brief(client, p)
    approve(client, p['id'], 'briefs', b['id'])
    clip = tmp_path / 'finished.mp4'
    subprocess.run([ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi',
        '-i', 'color=c=blue:s=640x360:r=24', '-t', '4', '-c:v', 'libx264', '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p', str(clip)], check=True, capture_output=True)
    missing_rights = client.post(base + '/uploads', json={'filename': 'finished.mp4', 'size': 10, 'purpose': 'finished_edit'})
    assert missing_rights.status_code == 422
    upload = upload_video(client, p['id'], clip, 'finished.mp4', purpose='finished_edit')
    assert upload['edited_video_id'] and upload['job_id']
    wait(client, base, {'id': upload['job_id']})
    current = client.get(base).json()
    assert current['assets'] == [] and current['plan'] is None
    assert current['draft']['source'] == 'external_edit'
    assert abs(current['draft']['duration_seconds'] - 4) < .1
    assert current['subtitle']['speech_status'] == 'no_speech'
    rejected = client.post(base + '/export-jobs', headers={'Idempotency-Key': 'reject-unapproved'}, json={})
    assert rejected.status_code == 409
    approve(client, p['id'], 'subtitles', current['subtitle_id'], no_speech_decision=True)
    exported = client.post(base + '/export-jobs', headers={'Idempotency-Key': 'export-external'}, json={})
    assert exported.status_code == 202, exported.text
    result = wait(client, base, exported.json())
    content = client.get(base + f"/exports/{result['output']['export_id']}/files/mp4?download=true")
    output = tmp_path / 'output.mp4'
    output.write_bytes(content.content)
    metadata = probe(output)
    assert (metadata['width'], metadata['height']) == (1080, 1920)
    assert abs(metadata['duration_seconds'] - 4) < .12
    assert client.get(base).json()['exports'][0]['plan_id'] is None


def test_edited_upload_approval_file_validation_and_scope(client):
    p = project(client)
    base = f"/api/v1/projects/{p['id']}"
    request = {'filename': 'bad.mp4', 'size': 9, 'purpose': 'finished_edit', 'rights_confirmed': True}
    assert client.post(base + '/uploads', json=request).status_code == 409  # Brief not approved yet.
    b = brief(client, p)
    approve(client, p['id'], 'briefs', b['id'])
    assert client.post(base + '/uploads', json={**request, 'filename': 'notes.txt'}).status_code == 422
    assert client.post(base + '/uploads', json={**request, 'size': 101 * 1024 * 1024}).status_code == 413
    rejected = upload_video(client, p['id'], b'not-video', 'bad.mp4', purpose='finished_edit', expect='rejected')
    assert rejected['error']['code'] == 'INVALID_MEDIA'
    assert client.app.state.db.docs(p['id'], 'edited_video') == []
    assert client.post(base + '/edited-video-jobs', headers={'Idempotency-Key': 'wrong-id'},
                       json={'edited_video_id': 'other-project'}).status_code == 404


def test_posting_caption_generate_save_stale_and_conflict(client, monkeypatch):
    monkeypatch.setenv('TRENDFORGE_AI_ENGINE', 'openai_compatible')
    client.patch('/api/v1/settings', json={'ai_base_url': 'https://test.example/v1', 'ai_model': 'test'})
    p = project(client)
    base = f"/api/v1/projects/{p['id']}"
    assert client.post(base + '/posting-caption/generate', json={}).status_code == 409
    b = brief(client, p)
    calls = []
    def provider(request):
        body = json.loads(request.content)
        calls.append(body)
        assert 'not subtitles' in body['messages'][0]['content']
        context = json.loads(body['messages'][1]['content'])
        assert context['brief']['script'] == b['script']
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({'text': 'One focused session. Try it today! #Study'})}}]})
    actual = httpx.AsyncClient
    monkeypatch.setattr(integrations.httpx, 'AsyncClient', lambda **kw: actual(transport=httpx.MockTransport(provider), **kw))
    current = client.get(base).json()
    generated = client.post(base + '/posting-caption/generate', json={'expected_project_revision': current['revision']})
    assert generated.status_code == 200, generated.text
    assert generated.json()['source'] == 'ai'
    current = client.get(base).json()
    assert current['posting_caption']['text'].startswith('One focused')
    assert not current['posting_caption']['stale']
    assert current['subtitle'] is None
    saved = client.post(base + '/posting-caption', json={'text': 'My reviewed caption', 'expected_project_revision': current['revision']})
    assert saved.status_code == 200
    assert client.post(base + '/posting-caption', json={'text': 'overwrite', 'expected_project_revision': current['revision']}).status_code == 409
    brief(client, client.get(base).json())
    assert client.get(base).json()['posting_caption']['stale']


@pytest.mark.parametrize('engine', ['workbuddy', 'openai_compatible'])
def test_up_to_ten_selected_references_reach_writer(client, monkeypatch, engine):
    monkeypatch.setenv('TRENDFORGE_AI_ENGINE', engine)
    p = project(client)
    refs = [{'video_id': f'ref_{i:07d}', 'title': f'Source {i}'} for i in range(35)]
    client.app.state.db.add_doc(p['id'], 'research', {'items': refs})
    rejected = client.post(f"/api/v1/projects/{p['id']}/ai/ideas", json={'source_video_ids': [x['video_id'] for x in refs], 'expected_project_revision': p['revision']})
    assert rejected.status_code == 422 and rejected.json()['error']['code'] == 'TOO_MANY_REFERENCES'
    ids = [item['video_id'] for item in refs[:10]]
    if engine == 'openai_compatible':
        client.patch('/api/v1/settings', json={'ai_base_url': 'https://test.example/v1', 'ai_model': 'test'})
        def provider(request):
            context = json.loads(json.loads(request.content)['messages'][1]['content'])
            assert len(context['selected_reference_titles']) == 10
            return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({'ideas': [
                {'id': f'idea_{i}', 'title': f'Idea {i}', 'angle': 'A practical angle.', 'hook': 'Try this habit.'} for i in range(3)]})}}]})
        actual = httpx.AsyncClient
        monkeypatch.setattr(integrations.httpx, 'AsyncClient', lambda **kw: actual(transport=httpx.MockTransport(provider), **kw))
    response = client.post(f"/api/v1/projects/{p['id']}/ai/ideas", json={'source_video_ids': ids, 'expected_project_revision': p['revision']})
    assert response.status_code == (202 if engine == 'workbuddy' else 200), response.text
    if engine == 'workbuddy': assert response.json()['source_video_ids'] == ids
    else: assert client.get(f"/api/v1/projects/{p['id']}").json()['idea_source_video_ids'] == ids
