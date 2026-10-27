import io
import json
import zipfile

from trendforge.config import Settings, load_environment


def test_dotenv_precedence_empty_values_and_secret_redaction(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    env_file.write_text('YOUTUBE_API_KEY="file-youtube-key"\nPEXELS_API_KEY=\nAI_API_KEY="literal-${NOT_A_VARIABLE}"\n', encoding='utf-8')
    monkeypatch.setenv('YOUTUBE_API_KEY', 'process-youtube-key')
    load_environment(env_file)
    settings = Settings(tmp_path / 'data')
    settings.update({'youtube_api_key': 'legacy-key', 'pexels_api_key': 'legacy-pexels-key'})
    assert settings.get('youtube_api_key') == 'process-youtube-key'
    assert settings.get('pexels_api_key') == ''
    assert settings.get('ai_api_key') == 'literal-${NOT_A_VARIABLE}'
    assert settings.public()['configuration_sources']['youtube_api_key'] == 'environment'
    assert not settings.public()['pexels_configured']
    assert 'process-youtube-key' not in str(settings.public())
    assert 'literal-${NOT_A_VARIABLE}' not in str(settings.public())
    assert 'process-youtube-key' not in settings.cipher.decrypt(settings.path.read_bytes()).decode()
    monkeypatch.delenv('YOUTUBE_API_KEY')
    load_environment(env_file)
    assert settings.get('youtube_api_key') == 'file-youtube-key'


def test_environment_managed_settings_cannot_be_silently_overridden(client, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'owner-secret-key')
    response = client.get('/api/v1/settings')
    assert response.json()['youtube_configured']
    assert 'owner-secret-key' not in response.text
    refused = client.patch('/api/v1/settings', json={'youtube_api_key': 'browser-secret-key'})
    assert refused.status_code == 409
    assert refused.json()['error']['code'] == 'ENV_MANAGED'
    assert client.app.state.settings.get('youtube_api_key') == 'owner-secret-key'
    connector = client.get('/api/v1/settings/connector')
    assert 'owner-secret-key' not in connector.text
    assert connector.json()['mcpServers']['trendforge']['cwd']
    package = client.get('/api/v1/settings/connector-package')
    assert package.status_code == 200
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        assert set(archive.namelist()) == {'connector-meta.json', 'mcp.json', 'icon.svg', 'skills/trendforge/SKILL.md'}
        configuration = json.loads(archive.read('mcp.json'))
        assert configuration == connector.json()
        assert all(b'owner-secret-key' not in archive.read(name) for name in archive.namelist())
