import pytest
from fastapi.testclient import TestClient
from trendforge.app import create_app
from test_creator_agents import automate, setup
from conftest import project


def test_vercel_registered_hostname_and_spoofed_hostname(tmp_path,monkeypatch):
    monkeypatch.setenv('VERCEL_URL','preview-team.vercel.app')
    app=create_app(tmp_path)
    c=TestClient(app,base_url='https://preview-team.vercel.app')
    assert c.get('/').status_code==200
    assert c.get('/',headers={'host':'untrusted.example'}).status_code==400


def test_vercel_refuses_ephemeral_sqlite(tmp_path,monkeypatch):
    monkeypatch.setenv('VERCEL','1')
    monkeypatch.setenv('TRENDFORGE_DATABASE_BACKEND','sqlite')
    with pytest.raises(RuntimeError,match='TURSO_DATABASE_URL'):
        with TestClient(create_app(tmp_path)):
            pass


def test_vercel_ai_finishes_in_request_lifetime(client,monkeypatch):
    automate(client,monkeypatch,bad_first=True)
    _,base,_=setup(client)
    monkeypatch.setenv('VERCEL','1')
    response=client.post(base+'/runs',headers={'Idempotency-Key':'serverless-run'})
    assert response.status_code==202,response.text
    result=client.get(base).json()['run']
    assert result['status']=='awaiting_approval'
    assert [t['role'] for t in result['trace']]==['Planner','Writer','Reviewer','Writer','Reviewer']


def test_vercel_rejects_ephemeral_local_video_upload(client,monkeypatch):
    pid=project(client)['id']
    monkeypatch.setenv('VERCEL','1')
    response=client.post(f'/api/v1/projects/{pid}/uploads',json={'filename':'clip.mp4','size':100,'purpose':'clip','rights_confirmed':True})
    assert response.status_code==409,response.text
    assert response.json()['error']['code']=='SHARED_STORAGE_REQUIRED'
