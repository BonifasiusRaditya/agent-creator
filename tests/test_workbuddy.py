from conftest import project


def ideas_result():
    return {"ideas": [{"id": f"idea_{i}", "title": f"Study habit {i}",
        "angle": "One practical habit for students", "hook": "Try a focused session"} for i in range(1, 4)]}


def brief_result():
    return {"title": "One focused session", "hook": "Start with one priority",
        "angle": "A practical habit for students", "script": "Choose one priority. Remove distractions. Try a focused session.",
        "cta": "Try it today", "shots": [{"visual": "Creator films a study session",
            "narration": "Choose one priority", "duration_seconds": 10} for _ in range(3)]}


def connector_headers(c):
    return {"Authorization": "Bearer " + c.app.state.settings.get("service_token")}


def test_workbuddy_request_to_review_without_another_ai_provider(client):
    p = project(client)
    base = f"/api/v1/projects/{p['id']}"
    headers = connector_headers(client)
    assert client.get('/api/v1/settings').json()['ai_engine'] == 'workbuddy'
    request = client.post(base + '/ai/ideas', json={"source_video_ids": [], "expected_project_revision": p['revision']})
    assert request.status_code == 202
    task = request.json()
    assert task['status'] == 'pending'
    assert not client.get(base).json()['ideas']
    repeated = client.post(base + '/ai/ideas', json={"source_video_ids": [], "expected_project_revision": p['revision']})
    assert repeated.json()['id'] == task['id']
    path = base + '/agent-requests/' + task['id']
    assert client.get('/api/v1/agent/requests').status_code == 403
    pending = client.get('/api/v1/agent/requests', headers=headers).json()
    assert len(pending) == 1
    context = client.get(path, headers=headers).json()
    assert context['context']['niche'] == p['niche']
    assert context['result_schema']['properties']['ideas']['minItems'] == 3
    assert 'context' not in client.get(path).json()
    assert client.post(path + '/result', json=ideas_result()).status_code == 403
    assert client.post(path + '/result', json={"ideas": []}, headers=headers).status_code == 422
    assert client.post(path + '/result', json=ideas_result(), headers=headers).json()['status'] == 'completed'
    current = client.get(base).json()
    assert len(current['ideas']) == 3
    assert current['agent_request']['status'] == 'completed'
    assert client.post(path + '/result', json=ideas_result(), headers=headers).status_code == 200
    assert client.get(base).json()['revision'] == current['revision']
    changed = ideas_result()
    changed['ideas'][0]['title'] = 'A conflicting retry'
    assert client.post(path + '/result', json=changed, headers=headers).status_code == 409
    task = client.post(base + '/ai/brief', json={"idea_id": 'idea_1', "expected_project_revision": current['revision']}).json()
    path = base + '/agent-requests/' + task['id']
    assert client.get(path, headers=headers).json()['context']['selected_idea']['id'] == 'idea_1'
    assert client.post(path + '/result', json={**brief_result(), "status": "approved"}, headers=headers).status_code == 422
    assert client.post(path + '/result', json=brief_result(), headers=headers).status_code == 200
    saved = client.get(base).json()['brief']
    assert saved['status'] == 'draft'
    assert saved['source_video_ids'] == []
    assert client.post(base + f"/briefs/{saved['id']}/approve", headers=headers,
        json={"confirmation": True, "expected_project_revision": 3}).status_code == 403
    assert client.get('/api/v1/agent/requests', headers=headers).json() == []
    assert client.get('/api/v1/settings').json()['workbuddy_last_seen']


def test_workbuddy_stale_cancelled_and_cross_project_results_are_rejected(client):
    p = project(client)
    base = f"/api/v1/projects/{p['id']}"
    task = client.post(base + '/ai/ideas', json={}).json()
    path = base + '/agent-requests/' + task['id']
    other = project(client)
    assert client.get(f"/api/v1/projects/{other['id']}/agent-requests/{task['id']}").status_code == 404
    assert client.patch(base, json={"goal": "A different direction for the story", "expected_project_revision": 1}).status_code == 200
    assert client.get(base).json()['agent_request']['status'] == 'stale'
    result = client.post(path + '/result', json=ideas_result(), headers=connector_headers(client))
    assert result.status_code == 409
    assert not client.get(base).json()['ideas']
    assert client.post(path + '/cancel').json()['status'] == 'cancelled'
    task = client.post(base + '/ai/ideas', json={}).json()
    path = base + '/agent-requests/' + task['id']
    assert client.post(path + '/cancel').json()['status'] == 'cancelled'
    assert client.post(path + '/result', json=ideas_result(), headers=connector_headers(client)).status_code == 409


def test_workbuddy_never_invents_sources_or_accepts_wrong_brief_timing(client):
    p = project(client)
    base = f"/api/v1/projects/{p['id']}"
    unknown = client.post(base + '/agent-requests', json={"task": "ideas", "source_video_ids": ['abcdefghijk'], "expected_project_revision": 1})
    assert unknown.status_code == 422
    task = client.post(base + '/ai/ideas', json={}).json()
    assert client.post(base + '/agent-requests/' + task['id'] + '/result', json=ideas_result(), headers=connector_headers(client)).status_code == 200
    task = client.post(base + '/ai/brief', json={"idea_id": "idea_1"}).json()
    bad = brief_result()
    bad['shots'][0]['duration_seconds'] = 5
    response = client.post(base + '/agent-requests/' + task['id'] + '/result', json=bad, headers=connector_headers(client))
    assert response.status_code == 422
    assert client.get(base).json()['brief'] is None
