from sprrint.client import Client
from sprrint.config import SITE_URL, Settings, load, save
from sprrint.errors import AuthError, SprrintError
import httpx


def test_requires_key(monkeypatch, tmp_path):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    monkeypatch.delenv('SPRRINT_API_KEY', raising=False)
    client = Client(Settings(api_url='http://example.test', api_key=''))
    try:
        client.me()
        assert False, 'expected AuthError'
    except AuthError:
        pass


def test_builds_api_url():
    client = Client(Settings(api_url='https://sprrint.run/', api_key='spr_live_x'))
    assert client._url('/me') == 'https://sprrint.run/api/v1/me'


def test_load_always_uses_sprrint_run(monkeypatch, tmp_path):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    monkeypatch.setenv('SPRRINT_API_URL', 'http://localhost:8000')
    (tmp_path / 'config.toml').write_text('api_url = "http://127.0.0.1:8000"\napi_key = "spr_live_ok"\n')
    settings = load()
    assert settings.api_url == SITE_URL
    save(Settings(api_url='http://localhost:9', api_key='spr_live_ok'))
    assert load().api_url == SITE_URL


def test_error_payload(httpx_mock):
    httpx_mock.add_response(
        method='GET',
        url='https://sprrint.run/api/v1/me',
        status_code=401,
        json={'ok': False, 'error': 'That API key is not valid.', 'code': 'unauthorized'},
    )
    client = Client(Settings(api_url='https://sprrint.run', api_key='spr_live_bad'))
    try:
        client.me()
        assert False
    except AuthError as exc:
        assert 'not valid' in exc.message


def test_unwraps_data(httpx_mock):
    httpx_mock.add_response(
        url='https://sprrint.run/api/v1/projects',
        json={'ok': True, 'data': [{'key': 'BR', 'name': 'Brand Refresh'}]},
    )
    client = Client(Settings(api_url='https://sprrint.run', api_key='spr_live_ok'))
    assert client.projects()[0]['key'] == 'BR'


def test_create_task_posts_json(httpx_mock):
    httpx_mock.add_response(
        method='POST',
        url='https://sprrint.run/api/v1/projects/BR/tasks/create',
        json={'ok': True, 'data': {'key': 'BR-1', 'title': 'Ship it'}},
    )
    client = Client(Settings(api_url='https://sprrint.run', api_key='spr_live_ok'))
    task = client.create_task('BR', title='Ship it')
    assert task['key'] == 'BR-1'


def test_workspace_header(httpx_mock):
    def check(request):
        assert request.headers['X-Workspace-Slug'] == 'acme'
        return httpx.Response(200, json={'ok': True, 'data': []})

    httpx_mock.add_callback(check, url='https://sprrint.run/api/v1/projects')
    client = Client(Settings(api_url='https://sprrint.run', api_key='spr_live_ok', workspace='acme'))
    assert client.projects() == []


def test_move_task_blocked_note(httpx_mock):
    seen = {}

    def responder(request):
        seen['body'] = request.content.decode()
        return httpx.Response(200, json={'ok': True, 'data': {'key': 'BR-2', 'status': 'blocked'}})

    httpx_mock.add_callback(responder, method='POST', url='https://sprrint.run/api/v1/projects/BR/tasks/BR-2/move')
    client = Client(Settings(api_url='https://sprrint.run', api_key='spr_live_ok'))
    task = client.move_task('BR', 'BR-2', 'blocked', blocked_note='Waiting on API')
    assert task['status'] == 'blocked'
    assert 'Waiting on API' in seen['body']


def test_server_error(httpx_mock):
    httpx_mock.add_response(
        url='https://sprrint.run/api/v1/projects/ZZ',
        status_code=404,
        json={'ok': False, 'error': 'Project not found.', 'code': 'not_found'},
    )
    client = Client(Settings(api_url='https://sprrint.run', api_key='spr_live_ok'))
    try:
        client.project('ZZ')
        assert False
    except SprrintError as exc:
        assert exc.status == 404
