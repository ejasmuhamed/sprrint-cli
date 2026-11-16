from typer.testing import CliRunner

import httpx

from sprrint.cli import app
from sprrint.config import Settings, save


runner = CliRunner()


def test_help():
    result = runner.invoke(app, ['--help'])
    assert result.exit_code == 0
    assert 'now' in result.stdout
    assert 'tasks' in result.stdout
    assert 'blackhole' in result.stdout
    assert 'workspaces' in result.stdout
    assert 'releases' in result.stdout
    assert 'mcp' in result.stdout


def test_whoami_json(monkeypatch, tmp_path, httpx_mock):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    save(Settings(api_url='https://sprrint.run', api_key='spr_live_ok', project='BR'))
    httpx_mock.add_response(
        url='https://sprrint.run/api/v1/me',
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
    save(Settings(api_url='https://sprrint.run', api_key='spr_live_ok', project='BR'))
    httpx_mock.add_response(
        method='POST',
        url='https://sprrint.run/api/v1/projects/BR/tasks/create',
        json={'ok': True, 'data': {'key': 'BR-12', 'title': 'From CLI'}},
    )
    result = runner.invoke(app, ['tasks', 'create', '--title', 'From CLI', '--plain', '--json'])
    assert result.exit_code == 0
    assert 'BR-12' in result.stdout


def test_releases_create(monkeypatch, tmp_path, httpx_mock):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    save(Settings(api_url='https://sprrint.run', api_key='spr_live_ok', project='BR'))
    seen = {}

    def responder(request):
        seen['body'] = request.content.decode()
        return httpx.Response(
            201,
            json={'ok': True, 'data': {'slug': '1-0', 'name': '1.0', 'status': 'upcoming'}},
        )

    httpx_mock.add_callback(
        responder,
        method='POST',
        url='https://sprrint.run/api/v1/projects/BR/releases/create',
    )
    result = runner.invoke(
        app,
        [
            'releases', 'create',
            '--name', '1.0',
            '--version', 'v1.0',
            '--task', 'BR-12',
            '--sprint', 'launch-week',
            '--plain',
            '--json',
        ],
    )
    assert result.exit_code == 0
    assert '1-0' in result.stdout
    assert 'BR-12' in seen['body']
    assert 'launch-week' in seen['body']


def test_blackhole_pull(monkeypatch, tmp_path, httpx_mock):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    save(Settings(api_url='https://sprrint.run', api_key='spr_live_ok', project='BR'))
    httpx_mock.add_response(
        method='POST',
        url='https://sprrint.run/api/v1/projects/BR/blackhole/BR-9/pull',
        json={'ok': True, 'data': {'key': 'BR-9', 'sprint': {'name': 'Launch Week'}}},
    )
    result = runner.invoke(app, ['blackhole', 'pull', 'BR-9', '--plain'])
    assert result.exit_code == 0
    assert 'Launch Week' in result.stdout


def test_error_exit(monkeypatch, tmp_path, httpx_mock):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    save(Settings(api_url='https://sprrint.run', api_key='spr_live_ok', project='BR'))
    httpx_mock.add_response(
        url='https://sprrint.run/api/v1/me',
        status_code=401,
        json={'ok': False, 'error': 'That API key is not valid.', 'code': 'unauthorized'},
    )
    result = runner.invoke(app, ['whoami', '--plain'])
    assert result.exit_code == 1
    assert 'not valid' in result.stdout or 'not valid' in result.stderr


def test_config_set_rejects_api_url(monkeypatch, tmp_path):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    result = runner.invoke(app, ['config', 'set', 'api_url', 'http://localhost:8000'])
    assert result.exit_code != 0
    assert 'sprrint.run' in result.stdout or 'sprrint.run' in result.stderr


def test_workspaces_use(monkeypatch, tmp_path):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    result = runner.invoke(app, ['workspaces', 'use', 'acme', '--plain'])
    assert result.exit_code == 0
    assert 'acme' in result.stdout


def test_tasks_move_blocked_note(monkeypatch, tmp_path, httpx_mock):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    save(Settings(api_url='https://sprrint.run', api_key='spr_live_ok', project='BR'))
    httpx_mock.add_response(
        method='POST',
        url='https://sprrint.run/api/v1/projects/BR/tasks/BR-12/move',
        status_code=409,
        json={
            'ok': False,
            'needs_block_note': True,
            'key': 'BR-12',
            'title': 'Blocked task',
            'blocked_note': '',
        },
    )
    result = runner.invoke(app, ['tasks', 'move', 'BR-12', 'blocked', '--plain'])
    assert result.exit_code == 1
    assert 'blocked note' in result.stdout.lower() or 'blocked note' in result.stderr.lower()


def test_qa_fix_command_preserves_finding_and_note(monkeypatch, tmp_path, httpx_mock):
    import json
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    save(Settings(api_url='https://sprrint.run', api_key='spr_live_ok', project='BR'))
    httpx_mock.add_response(method='POST', url='https://sprrint.run/api/v1/projects/BR/tasks/BR-12/qa',
                            json={'ok': True, 'data': {'key': 'BR-12', 'status': 'progress', 'qa_round_number': 2}})
    result = runner.invoke(app, ['tasks', 'qa', 'BR-12', 'fix', '--finding', '8', '--body', 'Fixed the password error', '--file-ids', 'file-a,file-b', '--plain', '--json'])
    assert result.exit_code == 0, result.output
    payload = json.loads(httpx_mock.get_request().content)
    assert payload == {'action': 'fix', 'body': 'Fixed the password error', 'finding_id': 8,
                       'owner_id': None, 'file_ids': ['file-a', 'file-b']}
    assert 'qa_round_number' in result.stdout


def test_qa_failed_verdict_returns_api_error(monkeypatch, tmp_path, httpx_mock):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    save(Settings(api_url='https://sprrint.run', api_key='spr_live_ok', project='BR'))
    httpx_mock.add_response(method='POST', url='https://sprrint.run/api/v1/projects/BR/tasks/BR-12/qa', status_code=400,
                            json={'ok': False, 'error': 'Only the assigned QA owner can perform this action.', 'code': 'invalid'})
    result = runner.invoke(app, ['tasks', 'qa', 'BR-12', 'pass', '--body', 'Passed', '--plain'])
    assert result.exit_code == 1
    assert 'QA owner' in result.output
