from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from sprrint.config import Settings, load, require_key
from sprrint.errors import AuthError, SprrintError


class Client:
    def __init__(self, settings: Settings | None = None, timeout=30.0):
        self.settings = settings or load()
        self._http = httpx.Client(timeout=timeout, follow_redirects=True)

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _url(self, path: str) -> str:
        return f'{self.settings.host()}/api/v1{path}'

    def _headers(self, auth=True) -> dict[str, str]:
        headers = {'Accept': 'application/json'}
        if auth:
            require_key(self.settings)
            headers['Authorization'] = f'Bearer {self.settings.api_key}'
        return headers

    def _request(self, method: str, path: str, *, auth=True, json=None, files=None, params=None):
        headers = self._headers(auth)
        if json is not None and files is None:
            headers['Content-Type'] = 'application/json'
        response = self._http.request(
            method,
            self._url(path),
            headers=headers,
            json=json,
            files=files,
            params=params,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise SprrintError(f'Sprrint returned a non-JSON response ({response.status_code}).') from exc
        if response.status_code == 401:
            raise AuthError(payload.get('error') or 'That API key is not valid.')
        if not payload.get('ok', response.is_success):
            raise SprrintError(
                payload.get('error') or 'Request failed.',
                status=response.status_code,
                code=payload.get('code'),
            )
        if not response.is_success:
            raise SprrintError(
                payload.get('error') or f'Request failed ({response.status_code}).',
                status=response.status_code,
                code=payload.get('code'),
            )
        return payload.get('data', payload)

    def get(self, path: str, **params):
        return self._request('GET', path, params=params or None)

    def post(self, path: str, data: dict | None = None, *, auth=True):
        return self._request('POST', path, json=data or {}, auth=auth)

    def patch(self, path: str, data: dict | None = None):
        return self._request('PATCH', path, json=data or {})

    def delete(self, path: str, data: dict | None = None):
        return self._request('DELETE', path, json=data)

    def login_start(self, email: str):
        return self.post('/auth/login', {'email': email}, auth=False)

    def login_verify(self, email: str, code: str, name='CLI', source='cli'):
        return self.post('/auth/verify', {'email': email, 'code': code, 'name': name, 'source': source}, auth=False)

    def me(self):
        return self.get('/me')

    def update_me(self, **fields):
        return self.patch('/me/update', fields)

    def emails(self):
        return self.get('/me/emails')

    def add_email(self, email: str):
        return self.post('/me/emails/add', {'email': email})

    def verify_email(self, email_id: int, code: str):
        return self.post(f'/me/emails/{email_id}/verify', {'code': code})

    def primary_email(self, email_id: int):
        return self.post(f'/me/emails/{email_id}/primary')

    def resend_email(self, email_id: int):
        return self.post(f'/me/emails/{email_id}/resend')

    def remove_email(self, email_id: int):
        return self.delete(f'/me/emails/{email_id}')

    def keys(self):
        return self.get('/keys')

    def create_key(self, name: str, source='cli'):
        return self.post('/keys/create', {'name': name, 'source': source})

    def revoke_key(self, key_id: int):
        return self.delete(f'/keys/{key_id}')

    def workspace(self):
        return self.get('/workspace')

    def update_workspace(self, **fields):
        return self.post('/workspace/update', fields)

    def invite(self, email: str, role='member'):
        return self.post('/workspace/invite', {'email': email, 'role': role})

    def set_role(self, user_id: int, role: str):
        return self.post(f'/workspace/members/{user_id}', {'role': role})

    def remove_member(self, user_id: int):
        return self.delete(f'/workspace/members/{user_id}/remove')

    def leave(self):
        return self.post('/workspace/leave')

    def delete_workspace(self, confirm: str):
        return self.delete('/workspace/delete', {'confirm': confirm})

    def overview(self):
        return self.get('/overview')

    def search(self, q: str, project: str | None = None):
        params = {'q': q}
        if project:
            params['project'] = project
        return self.get('/search', **params)

    def activity(self, project: str | None = None, **params):
        if project:
            return self.get(f'/projects/{project}/activity', **params)
        return self.get('/overview/activity', **params)

    def projects(self):
        return self.get('/projects')

    def create_project(self, **fields):
        return self.post('/projects/create', fields)

    def project(self, ref: str):
        return self.get(f'/projects/{ref}')

    def update_project(self, ref: str, **fields):
        return self.post(f'/projects/{ref}/update', fields)

    def archive_project(self, ref: str):
        return self.post(f'/projects/{ref}/archive')

    def restore_project(self, project_id: int):
        return self.post(f'/projects/{project_id}/restore')

    def delete_project(self, ref: str, confirm: str):
        return self.delete(f'/projects/{ref}/delete', {'confirm': confirm})

    def add_project_member(self, ref: str, user: str, role='member'):
        return self.post(f'/projects/{ref}/members', {'user': user, 'role': role})

    def remove_project_member(self, ref: str, user_id: int):
        return self.delete(f'/projects/{ref}/members/{user_id}')

    def home(self, ref: str):
        return self.get(f'/projects/{ref}/home')

    def now(self, ref: str, **params):
        return self.get(f'/projects/{ref}/now', **params)

    def tasks(self, ref: str, **params):
        return self.get(f'/projects/{ref}/tasks', **params)

    def create_task(self, ref: str, **fields):
        return self.post(f'/projects/{ref}/tasks/create', fields)

    def task(self, ref: str, key: str):
        return self.get(f'/projects/{ref}/tasks/{key}')

    def update_task(self, ref: str, key: str, **fields):
        return self.post(f'/projects/{ref}/tasks/{key}/update', fields)

    def move_task(self, ref: str, key: str, status: str, position: float | None = None):
        data: dict[str, Any] = {'status': status}
        if position is not None:
            data['position'] = position
        return self.post(f'/projects/{ref}/tasks/{key}/move', data)

    def comment(self, ref: str, key: str, body: str, parent: int | None = None, file_ids=None):
        data: dict[str, Any] = {'body': body}
        if parent:
            data['parent'] = parent
        if file_ids:
            data['file_ids'] = file_ids
        return self.post(f'/projects/{ref}/tasks/{key}/comments', data)

    def attach(self, ref: str, key: str, path: Path):
        upload = Path(path)
        with upload.open('rb') as handle:
            return self._request(
                'POST',
                f'/projects/{ref}/tasks/{key}/files',
                files={'file': (upload.name, handle)},
            )

    def sprints(self, ref: str, status: str | None = None):
        params = {'status': status} if status else {}
        return self.get(f'/projects/{ref}/sprints', **params)

    def create_sprint(self, ref: str, **fields):
        return self.post(f'/projects/{ref}/sprints/create', fields)

    def sprint(self, ref: str, slug: str):
        return self.get(f'/projects/{ref}/sprints/{slug}')

    def update_sprint(self, ref: str, slug: str, **fields):
        return self.post(f'/projects/{ref}/sprints/{slug}/update', fields)

    def delete_sprint(self, ref: str, slug: str, move='free'):
        return self.delete(f'/projects/{ref}/sprints/{slug}/delete', {'move': move})

    def blackhole(self, ref: str):
        return self.get(f'/projects/{ref}/blackhole')

    def pull(self, ref: str, key: str):
        return self.post(f'/projects/{ref}/blackhole/{key}/pull')

    def drop(self, ref: str, key: str):
        return self.post(f'/projects/{ref}/blackhole/{key}/drop')

    def categories(self, ref: str):
        return self.get(f'/projects/{ref}/categories')

    def create_category(self, ref: str, kind: str, name: str):
        return self.post(f'/projects/{ref}/categories/create', {'kind': kind, 'name': name})

    def delete_category(self, ref: str, category_id: int):
        return self.delete(f'/projects/{ref}/categories/{category_id}')

    def upload_file(self, ref: str, path: Path):
        upload = Path(path)
        with upload.open('rb') as handle:
            return self._request(
                'POST',
                f'/projects/{ref}/files',
                files={'file': (upload.name, handle)},
            )

    def resolve_project(self, ref: str | None = None) -> str:
        if ref:
            return ref
        if self.settings.project:
            return self.settings.project
        me = self.me()
        if me.get('last_project_key'):
            return me['last_project_key']
        projects = self.projects()
        if len(projects) == 1:
            return projects[0]['slug']
        raise SprrintError('Pass --project KEY or run `sprrint config set project KEY`.')
