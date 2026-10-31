import importlib
import json
import subprocess

import httpx
import pytest

from conftest import approve, brief, project
from trendforge import stock
from trendforge.config import Settings
from trendforge.media import ffmpeg


def video(vid=42, **extra):
    return {"id": vid, "pageURL": f"https://pixabay.com/videos/id-{vid}/", "duration": 5,
            "user": "Test Creator", "user_id": 7, "videos": {
                "large": {"url": "https://cdn.pixabay.com/video/test-large.mp4", "width": 3840,
                          "height": 2160, "size": 2000},
                "medium": {"url": "https://cdn.pixabay.com/video/test.mp4", "width": 640,
                           "height": 360, "size": 1000, "thumbnail": "https://cdn.pixabay.com/video/test.jpg"}}, **extra}


def transport(monkeypatch, handler):
    actual = httpx.AsyncClient
    monkeypatch.setattr(stock.httpx, "AsyncClient", lambda **kw: actual(transport=httpx.MockTransport(handler), **kw))


def test_configuration_missing_key_and_redaction(client, monkeypatch):
    missing = client.get('/api/v1/stock/search?query=nature')
    assert missing.status_code == 409
    assert missing.json()['error']['code'] == 'PIXABAY_NOT_CONFIGURED'
    monkeypatch.setenv('PIXABAY_API_KEY', 'private-stock-key')
    public = client.get('/api/v1/settings')
    assert public.json()['stock_provider'] == 'pixabay'
    assert public.json()['stock_configured'] and public.json()['pixabay_configured']
    assert public.json()['configuration_sources']['pixabay_api_key'] == 'environment'
    assert 'private-stock-key' not in public.text
    assert client.patch('/api/v1/settings', json={'pixabay_api_key': 'other-key'}).status_code == 409
    monkeypatch.setenv('PIXABAY_API_KEY', '')
    assert not client.get('/api/v1/settings').json()['stock_configured']


def test_search_filters_credits_cache_restart_and_expiry(client, monkeypatch):
    monkeypatch.setenv('PIXABAY_API_KEY', 'test-stock-key')
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == 'pixabay.com'
        assert request.url.params['key'] == 'test-stock-key'
        assert request.url.params['safesearch'] == 'true'
        return httpx.Response(200, json={'hits': [video(), video(43, duration=121),
            video(44, videos={'large': {'url': 'https://cdn.pixabay.com/oversize.mp4',
                'width': 640, 'height': 360, 'size': 101 * 1024 * 1024}})]})

    transport(monkeypatch, handler)
    response = client.get('/api/v1/stock/search?query=nature')
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result) == 1
    assert result[0]['provider'] == 'pixabay'
    assert result[0]['file_url'] == 'https://cdn.pixabay.com/video/test.mp4'
    assert result[0]['creator'] == 'Test Creator'
    assert result[0]['creator_url'] == 'https://pixabay.com/users/id-7/'
    assert 'test-stock-key' not in response.text
    # A recreated settings object represents a restarted server using the same data folder.
    client.app.state.settings = Settings(client.app.state.settings.directory)
    assert client.get('/api/v1/stock/search?query=NATURE').json() == result
    assert len(calls) == 1
    cache = next(client.app.state.settings.directory.glob('cache/stock/pixabay/*.json'))
    assert 'test-stock-key' not in cache.read_text()
    stored = json.loads(cache.read_text())
    stored['fetched_at'] -= 86401
    cache.write_text(json.dumps(stored))
    assert client.get('/api/v1/stock/search?query=nature').status_code == 200
    assert len(calls) == 2


@pytest.mark.parametrize('status,code', [(400, 'PIXABAY_ERROR'), (429, 'PIXABAY_QUOTA'),
                                        (500, 'PIXABAY_ERROR')])
def test_provider_failures_are_actionable(client, monkeypatch, status, code):
    monkeypatch.setenv('PIXABAY_API_KEY', 'test-stock-key')
    transport(monkeypatch, lambda _: httpx.Response(status, text='private upstream details'))
    response = client.get('/api/v1/stock/search?query=nature')
    assert response.status_code == (429 if status == 429 else 502)
    assert response.json()['error']['code'] == code
    assert 'private upstream details' not in response.text


def test_network_and_malformed_response(client, monkeypatch):
    monkeypatch.setenv('PIXABAY_API_KEY', 'test-stock-key')
    def unavailable(request):
        raise httpx.ConnectError('offline', request=request)
    transport(monkeypatch, unavailable)
    assert client.get('/api/v1/stock/search?query=nature').json()['error']['code'] == 'PIXABAY_UNAVAILABLE'


@pytest.mark.parametrize('url', ['http://cdn.pixabay.com/clip.mp4', 'https://pixabay.com.evil.example/clip.mp4',
                               'https://cdn.pixabay.com@evil.example/clip.mp4', 'https://cdn.pixabay.com:8080/clip.mp4'])
def test_unapproved_download_urls_are_rejected(client, monkeypatch, url):
    monkeypatch.setenv('PIXABAY_API_KEY', 'test-stock-key')
    bad = video(videos={'medium': {'url': url, 'width': 640, 'height': 360, 'size': 1000}})
    transport(monkeypatch, lambda _: httpx.Response(200, json={'hits': [bad]}))
    assert client.get('/api/v1/stock/search?query=nature').status_code == 422


def test_import_real_media_keeps_source_and_uses_cached_search(client, monkeypatch, tmp_path):
    monkeypatch.setenv('PIXABAY_API_KEY', 'test-stock-key')
    clip = tmp_path / 'test.mp4'
    subprocess.run([ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi',
                    '-i', 'color=c=blue:s=360x640:r=24', '-t', '3', '-c:v', 'libx264',
                    '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', str(clip)], check=True, capture_output=True)
    calls = []
    def handler(request):
        calls.append(request.url.host)
        if request.url.host == 'pixabay.com':
            return httpx.Response(200, json={'hits': [video()]})
        assert request.url.host == 'cdn.pixabay.com'
        return httpx.Response(200, content=clip.read_bytes())
    transport(monkeypatch, handler)
    p = project(client)
    b = brief(client, p)
    approve(client, p['id'], 'briefs', b['id'])
    assert client.get('/api/v1/stock/search?query=nature').status_code == 200
    base = f"/api/v1/projects/{p['id']}/stock/import"
    unknown = client.post(base, json={'query': 'nature', 'video_id': 999, 'provider': 'pixabay'})
    assert unknown.status_code == 422
    response = client.post(base, json={'query': 'nature', 'video_id': 42, 'provider': 'pixabay'})
    assert response.status_code == 201, response.text
    asset = response.json()
    assert asset['source'] == asset['provenance']['provider'] == 'pixabay'
    assert asset['original_name'] == 'pixabay-42.mp4'
    assert asset['provenance']['url'] == 'https://pixabay.com/videos/id-42/'
    assert asset['provenance']['creator'] == 'Test Creator'
    assert asset['validation_status'] == 'valid'
    assert calls == ['pixabay.com', 'cdn.pixabay.com']
    assert client.get(f"/api/v1/projects/{p['id']}/assets/{asset['id']}/media").content == clip.read_bytes()
    monkeypatch.setenv('TRENDFORGE_STOCK_PROVIDER', 'pexels')
    assert client.post(base, json={'query': 'nature', 'video_id': 42, 'provider': 'pixabay'}).status_code == 409


def test_import_blocks_redirects_and_size_limit(client, monkeypatch):
    monkeypatch.setenv('PIXABAY_API_KEY', 'test-stock-key')
    status = [302]
    def handler(request):
        if request.url.host == 'pixabay.com':
            return httpx.Response(200, json={'hits': [video()]})
        assert request.url.host == 'cdn.pixabay.com'
        return httpx.Response(status[0], headers={'Location': 'https://unapproved.example/clip.mp4'}, content=b'too large')
    transport(monkeypatch, handler)
    p = project(client)
    b = brief(client, p)
    approve(client, p['id'], 'briefs', b['id'])
    base = f"/api/v1/projects/{p['id']}"
    body = {'query': 'nature', 'video_id': 42, 'provider': 'pixabay'}
    assert client.post(base + '/stock/import', json=body).status_code == 422
    status[0] = 200
    monkeypatch.setattr(importlib.import_module('trendforge.app'), 'MAX_FILE', 2)
    assert client.post(base + '/stock/import', json=body).status_code == 413
    assert client.get(base + '/assets').json() == []


def test_pexels_switchback_and_connection_check(client, monkeypatch):
    monkeypatch.setenv('TRENDFORGE_STOCK_PROVIDER', 'pexels')
    monkeypatch.setenv('PEXELS_API_KEY', 'pexels-test-key')
    def handler(request):
        assert request.url.host == 'api.pexels.com'
        assert request.headers['Authorization'] == 'pexels-test-key'
        return httpx.Response(200, json={'videos': [{'id': 42, 'url': 'https://www.pexels.com/video/42/',
            'user': {'name': 'Pexels creator', 'url': 'https://www.pexels.com/@test/'},
            'video_files': [{'file_type': 'video/mp4', 'width': 360, 'height': 640,
                             'link': 'https://videos.pexels.com/test.mp4'}]}]})
    transport(monkeypatch, handler)
    assert client.get('/api/v1/settings').json()['stock_configured']
    result = client.get('/api/v1/stock/search?query=nature')
    assert result.status_code == 200
    assert result.json()[0]['provider'] == 'pexels'
    assert client.post('/api/v1/settings/test', json={'provider': 'stock'}).json()['ok']
