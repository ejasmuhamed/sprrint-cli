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


def test_create_release_posts_selected_tasks(httpx_mock):
    seen = {}

    def responder(request):
        seen['body'] = request.content.decode()
        return httpx.Response(
            201,
            json={'ok': True, 'data': {'slug': '1-0', 'name': '1.0', 'selected_tasks': [{'key': 'BR-1'}]}},
        )

    httpx_mock.add_callback(
        responder,
        method='POST',
        url='https://sprrint.run/api/v1/projects/BR/releases/create',
    )
    client = Client(Settings(api_url='https://sprrint.run', api_key='spr_live_ok'))
    release = client.create_release(
        'BR',
        name='1.0',
        version='v1.0',
        selected_tasks=['BR-1'],
        selected_sprints=['launch-week'],
    )
    assert release['slug'] == '1-0'
    assert 'BR-1' in seen['body']
    assert 'launch-week' in seen['body']


def test_releases_list(httpx_mock):
    httpx_mock.add_response(
        url='https://sprrint.run/api/v1/projects/BR/releases',
        json={'ok': True, 'data': [{'slug': '1-0', 'name': '1.0', 'status': 'upcoming'}]},
    )
    client = Client(Settings(api_url='https://sprrint.run', api_key='spr_live_ok'))
    assert client.releases('BR')[0]['slug'] == '1-0'


def test_workspace_header(httpx_mock):
    def check(request):
        assert request.headers['X-Workspace-Slug'] == 'acme'
        return httpx.Response(200, json={'ok': True, 'data': []})

    httpx_mock.add_callback(check, url='https://sprrint.run/api/v1/projects')
    client = Client(Settings(api_url='https://sprrint.run', api_key='spr_live_ok', workspace='acme'))
    assert client.projects() == []


def test_workspace_override_replaces_configured_workspace(httpx_mock):
    def check(request):
        assert request.headers['X-Workspace-Slug'] == 'googerit'
        return httpx.Response(200, json={'ok': True, 'data': []})

    httpx_mock.add_callback(check, url='https://sprrint.run/api/v1/projects')
    from sprrint.client import workspace_override
    token = workspace_override.set('googerit')
    try:
        client = Client(Settings(api_url='https://sprrint.run', api_key='spr_live_ok', workspace='acme'))
        assert client.projects() == []
    finally:
        workspace_override.reset(token)


def test_projects_all_sends_all_flag(httpx_mock):
    httpx_mock.add_response(
        url='https://sprrint.run/api/v1/projects?all=1',
        json={'ok': True, 'data': []},
    )
    client = Client(Settings(api_url='https://sprrint.run', api_key='spr_live_ok', workspace='acme'))
    assert client.projects(all_workspaces=True) == []


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


def test_upload_bytes_posts_file_not_a_path(httpx_mock):
    seen = {}

    def responder(request):
        seen['type'] = request.headers['content-type']
        seen['body'] = request.content
        return httpx.Response(201, json={'ok': True, 'data': {'id': 'file-1', 'name': 'shot.png', 'kind': 'image'}})

    httpx_mock.add_callback(responder, method='POST', url='https://sprrint.run/api/v1/projects/BR/files')
    client = Client(Settings(api_url='https://sprrint.run', api_key='spr_live_ok'))
    uploaded = client.upload_bytes('BR', 'shot.png', b'\x89PNG', 'image/png')
    assert uploaded['id'] == 'file-1'
    assert seen['type'].startswith('multipart/form-data')
    assert b'shot.png' in seen['body']
    assert b'\x89PNG' in seen['body']


def test_upload_bytes_rejects_a_path():
    client = Client(Settings(api_url='https://sprrint.run', api_key='spr_live_ok'))
    try:
        client.upload_bytes('BR', '../shot.png', b'abc')
        assert False
    except SprrintError as exc:
        assert exc.code == 'invalid'
