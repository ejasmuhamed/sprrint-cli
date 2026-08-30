from sprrint.client import Client
from sprrint.config import Settings
from sprrint.errors import AuthError, SprrintError


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
    client = Client(Settings(api_url='http://localhost:8000/', api_key='spr_live_x'))
    assert client._url('/me') == 'http://localhost:8000/api/v1/me'


def test_error_payload(httpx_mock):
    httpx_mock.add_response(
        method='GET',
        url='http://localhost:8000/api/v1/me',
        status_code=401,
        json={'ok': False, 'error': 'That API key is not valid.', 'code': 'unauthorized'},
    )
    client = Client(Settings(api_url='http://localhost:8000', api_key='spr_live_bad'))
    try:
        client.me()
        assert False
    except AuthError as exc:
        assert 'not valid' in exc.message


def test_unwraps_data(httpx_mock):
    httpx_mock.add_response(
        url='http://localhost:8000/api/v1/projects',
        json={'ok': True, 'data': [{'key': 'BR', 'name': 'Brand Refresh'}]},
    )
    client = Client(Settings(api_url='http://localhost:8000', api_key='spr_live_ok'))
    assert client.projects()[0]['key'] == 'BR'


def test_create_task_posts_json(httpx_mock):
    httpx_mock.add_response(
        method='POST',
        url='http://localhost:8000/api/v1/projects/BR/tasks/create',
        json={'ok': True, 'data': {'key': 'BR-1', 'title': 'Ship it'}},
    )
    client = Client(Settings(api_url='http://localhost:8000', api_key='spr_live_ok'))
    task = client.create_task('BR', title='Ship it')
    assert task['key'] == 'BR-1'


def test_server_error(httpx_mock):
    httpx_mock.add_response(
        url='http://localhost:8000/api/v1/projects/ZZ',
        status_code=404,
        json={'ok': False, 'error': 'Project not found.', 'code': 'not_found'},
    )
    client = Client(Settings(api_url='http://localhost:8000', api_key='spr_live_ok'))
    try:
        client.project('ZZ')
        assert False
    except SprrintError as exc:
        assert exc.status == 404
