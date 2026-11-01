"""Opt-in real Gemini check on isolated SQLite data; no application records touched.

Run once after configuring GEMINI_API_KEY. Artifacts contain fictional test data.
This is provider evidence, not an official organizer case or WorkBuddy evidence.
"""
import copy
import json
import os
import time
from pathlib import Path

from trendforge import config
from fastapi.testclient import TestClient
from trendforge.app import create_app


DIRECTORY = config.ROOT / "test-results" / "creator-live"


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    os.environ.update(TRENDFORGE_AI_ENGINE="gemini", TRENDFORGE_DATABASE_BACKEND="sqlite",
        TRENDFORGE_STORAGE_BACKEND="local", TRENDFORGE_WORKER="external",
        TRENDFORGE_INVITE_CODE="creator-local-test-invite", TRENDFORGE_ADMIN_USERNAMES="creator-tester")
    report = {"provider": "Gemini", "model": config.Settings().get("gemini_model"),
              "dataset": "Fictional synthetic source, not the official organizer dataset", "checks": []}
    with TestClient(create_app(DIRECTORY / "data")) as c:
        credentials = {"username": "creator-tester", "password": "CreatorLocalTest!2026"}
        r = c.post('/api/v1/session', json=credentials)
        if r.status_code != 200:
            r = c.post('/api/v1/auth/register', json={**credentials, "invite_code": "creator-local-test-invite"})
        assert r.status_code in (200, 201), r.text
        c.headers['X-CSRF-Token'] = r.json()['csrf_token']
        p = c.post('/api/v1/projects', json={"niche": "Fictional Senja product launch", "audience": "First-time ginger drink customers",
            "goal": "Introduce a fictional product honestly", "platform": "both", "language": "id", "target_duration_seconds": 30}).json()
        base = f"/api/v1/projects/{p['id']}/creator"
        src = {"source_title": "Fictional demo product sheet: Senja",
            "facts": ["Senja is a fictional ginger drink.", "Ingredients: ginger and palm sugar.",
                      "Each box contains 10 sachets.", "Price: Rp25000 per box.", "Serve one sachet with warm water."],
            "audience": "First-time customers", "direction": "Introduce Senja to new customers. Do not invent benefits.",
            "tone": "Friendly, warm, honest and encouraging. Avoid pressure.",
            "formats": ["short_script", "social_caption"], "languages": ["id", "en", "zh"]}
        assert c.post(base+'/source', json=src).status_code == 201
        report['project_id'] = p['id']
        def wait():
            for _ in range(180):
                run = c.get(base).json()['run']
                if run['status'] != 'running': return run
                time.sleep(.5)
            raise AssertionError('Run exceeded its bounded execution time')
        start = time.monotonic()
        r = c.post(base+'/runs', headers={'Idempotency-Key': 'live-'+str(time.time_ns())})
        assert r.status_code == 202, r.text
        run = wait()
        report['generation_seconds'] = round(time.monotonic()-start, 2)
        report['generation_status'] = run['status']
        report['checks'].append({'check': 'Real Planner, Writer and Reviewer completed', 'passed': run['status'] == 'awaiting_approval'})
        (DIRECTORY/'generation.json').write_text(json.dumps(run,ensure_ascii=False,indent=2),encoding='utf-8')
        if run['status'] == 'awaiting_approval':
            # A synthetic operator edit forces a real rejection/remediation example.
            edited = copy.deepcopy(run['draft'])
            edited['contents'][0]['lines'][0]['text'] = 'Senja cures gastritis.'
            response = c.post(base+f"/runs/{run['id']}/edit", json=edited)
            assert response.status_code == 202, response.text
            start = time.monotonic()
            revised = wait()
            report['revision_seconds'] = round(time.monotonic()-start,2)
            report['revision_status'] = revised['status']
            rejected = any(t.get('enforced_issues') for t in revised['trace'] if t['role']=='Reviewer')
            report['checks'].append({'check':'Real Reviewer rejected injected medical claim', 'passed':rejected})
            report['checks'].append({'check':'Real Writer repaired claim and Reviewer passed it', 'passed':revised['status']=='awaiting_approval' and revised['iteration']>1})
            assert c.get(base+f"/runs/{revised['id']}/export").status_code == 409
            report['checks'].append({'check':'Export blocked pending human approval', 'passed':True})
            (DIRECTORY/'revision.json').write_text(json.dumps(revised,ensure_ascii=False,indent=2),encoding='utf-8')
        (DIRECTORY/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
        print('Local test sign-in: creator-tester / CreatorLocalTest!2026 (isolated data only)')
        if not all(check['passed'] for check in report['checks']):
            raise SystemExit(1)


if __name__ == '__main__':
    main()
