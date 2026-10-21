import base64

import httpx

from sprrint.mcp_server import _decode_upload, mcp, sprrint_files_upload, sprrint_tasks_get


def test_mcp_server_loads():
    assert mcp.name == 'sprrint'
    tools = getattr(mcp, '_tool_manager').list_tools()
    names = {tool.name for tool in tools}
    assert 'sprrint_now' in names
    assert 'sprrint_tasks_create' in names
    assert 'sprrint_files_upload' in names
    assert 'sprrint_blackhole_pull' in names
    assert 'sprrint_workspace_invite' in names
    assert 'sprrint_releases_list' in names
    assert 'sprrint_releases_create' in names
    assert 'sprrint_releases_get' in names
    assert 'sprrint_releases_update' in names
    assert len(names) >= 30


def test_decode_upload_rejects_bad_input():
    try:
        _decode_upload('../shot.png', base64.b64encode(b'abc').decode())
        assert False
    except Exception as exc:
        assert getattr(exc, 'code', None) == 'invalid'
    try:
        _decode_upload('shot.png', '!!!')
        assert False
    except Exception as exc:
        assert 'base64' in str(exc)


def test_files_upload_failure_does_not_call_the_api(monkeypatch, tmp_path):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    monkeypatch.setenv('SPRRINT_API_KEY', 'spr_live_ok')
    called = {'n': 0}

    def boom(self, *args, **kwargs):
        called['n'] += 1
        raise AssertionError('upload should not run')

    monkeypatch.setattr('sprrint.client.Client.upload_bytes', boom)
    result = sprrint_files_upload(filename='shot.png', content_base64='!!!', project='BR')
    assert result['ok'] is False
    assert result['code'] == 'invalid'
    assert called['n'] == 0


def test_tasks_get_resolves_inline_files_when_api_omits_them(monkeypatch, tmp_path, httpx_mock):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    monkeypatch.setenv('SPRRINT_API_KEY', 'spr_live_ok')
    file_id = '11111111-1111-1111-1111-111111111111'
    httpx_mock.add_response(
        url='https://sprrint.run/api/v1/projects/BR/tasks/BR-1',
        json={'ok': True, 'data': {
            'key': 'BR-1',
            'description': f'Steps\n\n![shot.png](media:{file_id})\n\nAfter\n\n[brief.pdf](media:22222222-2222-2222-2222-222222222222)',
        }},
    )
    httpx_mock.add_response(
        url=f'https://sprrint.run/api/v1/projects/BR/files/resolve?ids={file_id},22222222-2222-2222-2222-222222222222',
        json={'ok': True, 'data': {
            file_id: {
                'id': file_id,
                'name': 'shot.png',
                'content_type': 'image/png',
                'kind': 'image',
                'size': 8,
                'url': 'https://files.example/shot.png',
            },
        }},
    )
    task = sprrint_tasks_get('BR-1', project='BR')
    assert task['description'].index('Steps') < task['description'].index(file_id)
    assert task['description'].index(file_id) < task['description'].index('After')
    assert task['description_files'][0]['role'] == 'image'
    assert task['description_files'][0]['markdown'] == f'![shot.png](media:{file_id})'
    assert task['description_files'][0]['content_type'] == 'image/png'
    assert task['description_files'][1]['missing'] is True
    assert '22222222-2222-2222-2222-222222222222' in task['description']


def test_files_upload_returns_markdown(monkeypatch, tmp_path, httpx_mock):
    monkeypatch.setenv('SPRRINT_HOME', str(tmp_path))
    monkeypatch.setenv('SPRRINT_API_KEY', 'spr_live_ok')

    def responder(request):
        assert request.headers['content-type'].startswith('multipart/form-data')
        assert b'shot.png' in request.content
        return httpx.Response(201, json={'ok': True, 'data': {
            'id': '33333333-3333-3333-3333-333333333333',
            'name': 'shot.png',
            'content_type': 'image/png',
            'kind': 'image',
            'size': 4,
            'url': 'https://files.example/shot.png',
        }})

    httpx_mock.add_callback(responder, method='POST', url='https://sprrint.run/api/v1/projects/BR/files')
    uploaded = sprrint_files_upload(
        filename='shot.png',
        content_base64=base64.b64encode(b'\x89PNG').decode(),
        content_type='image/png',
        project='BR',
    )
    assert uploaded['markdown'] == '![shot.png](media:33333333-3333-3333-3333-333333333333)'
    assert uploaded['role'] == 'image'
