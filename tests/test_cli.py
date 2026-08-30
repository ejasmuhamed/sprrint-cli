from typer.testing import CliRunner

from sprrint.cli import app
from sprrint.config import Settings, save


runner = CliRunner()


def test_help():
    result = runner.invoke(app, ['--help'])
    assert result.exit_code == 0
    assert 'now' in result.stdout
    assert 'tasks' in result.stdout
    assert 'blackhole' in result.stdout
    assert 'mcp' in result.stdout


def test_whoami_json(monkeypatch, tmp_path, httpx_mock):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    save(Settings(api_url='http://localhost:8000', api_key='spr_live_ok', project='BR'))
    httpx_mock.add_response(
        url='http://localhost:8000/api/v1/me',
        json={'ok': True, 'data': {
            'user': {'username': 'ejas', 'display_name': 'Ejas', 'email': 'ejas@acme.test'},
            'workspace': {'name': 'Acme', 'slug': 'acme', 'role': 'owner'},
        }},
    )
    result = runner.invoke(app, ['whoami', '--json', '--plain'])
    assert result.exit_code == 0
    assert 'ejas' in result.stdout


def test_tasks_create(monkeypatch, tmp_path, httpx_mock):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    save(Settings(api_url='http://localhost:8000', api_key='spr_live_ok', project='BR'))
    httpx_mock.add_response(
        method='POST',
        url='http://localhost:8000/api/v1/projects/BR/tasks/create',
        json={'ok': True, 'data': {'key': 'BR-12', 'title': 'From CLI'}},
    )
    result = runner.invoke(app, ['tasks', 'create', '--title', 'From CLI', '--plain', '--json'])
    assert result.exit_code == 0
    assert 'BR-12' in result.stdout


def test_blackhole_pull(monkeypatch, tmp_path, httpx_mock):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    save(Settings(api_url='http://localhost:8000', api_key='spr_live_ok', project='BR'))
    httpx_mock.add_response(
        method='POST',
        url='http://localhost:8000/api/v1/projects/BR/blackhole/BR-9/pull',
        json={'ok': True, 'data': {'key': 'BR-9', 'sprint': {'name': 'Launch Week'}}},
    )
    result = runner.invoke(app, ['blackhole', 'pull', 'BR-9', '--plain'])
    assert result.exit_code == 0
    assert 'Launch Week' in result.stdout


def test_error_exit(monkeypatch, tmp_path, httpx_mock):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    save(Settings(api_url='http://localhost:8000', api_key='spr_live_ok', project='BR'))
    httpx_mock.add_response(
        url='http://localhost:8000/api/v1/me',
        status_code=401,
        json={'ok': False, 'error': 'That API key is not valid.', 'code': 'unauthorized'},
    )
    result = runner.invoke(app, ['whoami', '--plain'])
    assert result.exit_code == 1
    assert 'not valid' in result.stdout or 'not valid' in result.stderr
