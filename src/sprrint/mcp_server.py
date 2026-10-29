"""Sprrint MCP server — every product action, for agents."""

from __future__ import annotations

import base64
import binascii
import inspect
import re
from functools import wraps
from typing import Optional

from mcp.server.fastmcp import FastMCP

from sprrint.client import Client, workspace_override
from sprrint.errors import SprrintError

_MEDIA_RE = re.compile(
    r'!\[([^\]]*)\]\(media:([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\)'
    r'|(?<!!)\[([^\]]+)\]\(media:([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\)'
)
_MAX_UPLOAD = 25 * 1024 * 1024

mcp = FastMCP(
    'sprrint',
    instructions=(
        'Sprrint is a sprint, release, and task workspace. Use these tools the same way a person '
        'uses the Sprrint app: look at Now, create and move tasks, run sprints, plan releases, '
        'pull work out of the Black Hole, search, comment, and manage workspaces and projects. '
        'Set SPRRINT_WORKSPACE or config workspace to target a specific workspace. '
        'Projects live in workspaces. sprrint_projects_list with no workspace argument returns every project '
        'you can see, each with its workspace slug and name. Match by project name or key before creating a project. '
        'A channel or chat name is not a project key. Pass workspace (a workspace slug) on a tool to target that '
        'workspace for that call only. A project key that exists in only one workspace is found without workspace. '
        'If the same key exists in more than one workspace, the tool lists those projects and you must pass workspace. '
        'The active workspace is checked first. '
        'Identify projects by key (BR) or slug. Identify tasks by key (BR-12). '
        'Releases group tasks (not sprints); selected_sprints on create/update expand to tasks. '
        'Task payloads may include releases: [{id, slug, name, version, status}]. '
        'Link git work with sprrint_tasks_git_link (PR URL, branch, or commit SHA). '
        'When starting a task, move it to progress. Comment decisions and blockers. '
        'When done, link the PR and remaining commits, then move to done. '
        'Moving to blocked requires blocked_note. Completing a parent with open subtasks needs confirm_complete.'
    ),
)


def _client() -> Client:
    return Client()


def _project(project: Optional[str] = None) -> str:
    return _client().resolve_project(project)


def _call(fn):
    try:
        return fn()
    except SprrintError as exc:
        payload = {'ok': False, 'error': exc.message, 'code': exc.code}
        payload.update(exc.extra)
        return payload


def _with_workspace(fn):
    signature = inspect.signature(fn, eval_str=True)

    @wraps(fn)
    def runner(*args, **kwargs):
        workspace = None
        try:
            workspace = signature.bind_partial(*args, **kwargs).arguments.get('workspace')
        except TypeError:
            workspace = None
        token = None
        if workspace is not None and str(workspace).strip():
            token = workspace_override.set(str(workspace).strip())
        try:
            return fn(*args, **kwargs)
        finally:
            if token is not None:
                workspace_override.reset(token)

    runner.__signature__ = signature
    return runner


def tool(fn):
    wrapped = _with_workspace(fn)
    mcp.tool()(wrapped)
    return wrapped


def _markdown_for(role: str, label: str, file_id: str) -> str:
    if role == 'image':
        return f'![{label}](media:{file_id})'
    return f'[{label}](media:{file_id})'


def _description_files(api: Client, ref: str, description: str) -> list:
    refs = []
    for match in _MEDIA_RE.finditer(description or ''):
        if match.group(2):
            refs.append(('image', match.group(1), match.group(2)))
        else:
            refs.append(('file', match.group(3), match.group(4)))
    if not refs:
        return []
    resolved = api.resolve_files(ref, [uid for _, _, uid in refs]) or {}
    rows = []
    for role, label, uid in refs:
        item = resolved.get(uid) or resolved.get(str(uid))
        markdown = _markdown_for(role, label, uid)
        if not item:
            rows.append({'id': uid, 'missing': True, 'role': role, 'label': label, 'markdown': markdown})
            continue
        row = dict(item)
        row['role'] = role
        row['label'] = label
        row['markdown'] = markdown
        row.setdefault('missing', False)
        rows.append(row)
    return rows


def _with_description_files(api: Client, ref: str, data: dict) -> dict:
    if not isinstance(data, dict) or 'description_files' in data:
        return data
    if 'description' not in data:
        return data
    data = dict(data)
    data['description_files'] = _description_files(api, ref, data.get('description') or '')
    return data


def _decode_upload(filename: str, content_base64: str) -> tuple[str, bytes]:
    name = (filename or '').strip()
    if not name or name in {'.', '..'} or '/' in name or '\\' in name:
        raise SprrintError('filename is required.', code='invalid')
    if not isinstance(content_base64, str) or not content_base64.strip():
        raise SprrintError('content_base64 is required. Send the file bytes, not a local path.', code='invalid')
    compact = ''.join(content_base64.split())
    if len(compact) > ((_MAX_UPLOAD + 1) * 4 // 3) + 8:
        raise SprrintError('That file is over 25 MB.', code='invalid')
    try:
        raw = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SprrintError('content_base64 is not valid base64.', code='invalid') from exc
    if len(raw) > _MAX_UPLOAD:
        raise SprrintError('That file is over 25 MB.', code='invalid')
    return name, raw


@tool
def sprrint_whoami() -> dict:
    """Show the signed-in Sprrint user and workspace."""
    return _call(lambda: _client().me())


@tool
def sprrint_overview(workspace: Optional[str] = None) -> dict:
    """Workspace home: greeting, counts, active sprints, and tasks that need a nudge.

    workspace is an optional workspace slug for this call.
    """
    return _call(lambda: _client().overview())


@tool
def sprrint_now(
    project: Optional[str] = None,
    sprint: Optional[str] = None,
    assigned: str = 'any',
    due: str = 'any',
    q: Optional[str] = None,
    workspace: Optional[str] = None,
) -> dict:
    """Show the Now board for a project. Filter by sprint slug, assignee username, due window, or search text."""
    return _call(lambda: _client().now(_project(project), sprint=sprint or '', assigned=assigned, due=due, q=q or ''))


@tool
def sprrint_search(q: str, project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """Search tasks, sprints, and people. Optionally scope to a project key or slug.

    workspace is an optional workspace slug for this call. A project key that exists in only one workspace is found without it.
    """
    return _call(lambda: _client().search(q, project))


@tool
def sprrint_activity(
    project: Optional[str] = None,
    tab: str = 'history',
    range: str = '7',
    actor: Optional[str] = None,
    type: Optional[str] = None,
    q: Optional[str] = None,
    workspace: Optional[str] = None,
) -> dict:
    """Activity feed. tab is you|history (all still accepted as history). range is 0 (today), 7, 30, or all.

    workspace is an optional workspace slug for this call.
    """
    params = {'tab': tab, 'range': range}
    if actor:
        params['actor'] = actor
    if type:
        params['type'] = type
    if q:
        params['q'] = q
    return _call(lambda: _client().activity(project, **params))


@tool
def sprrint_workspaces_list() -> dict:
    """List workspaces you belong to."""
    return _call(lambda: _client().workspaces())


@tool
def sprrint_workspaces_create(
    name: str,
    slug: Optional[str] = None,
    description: str = '',
) -> dict:
    """Create a workspace and switch into it on the server."""
    fields = {'name': name, 'description': description}
    if slug:
        fields['slug'] = slug
    return _call(lambda: _client().create_workspace(**fields))


@tool
def sprrint_projects_list(workspace: Optional[str] = None) -> dict:
    """List projects you can see.

    Omit workspace to list every workspace. Pass a workspace slug to limit the list.
    Each project includes its workspace slug and name. Match a project here before creating one.
    A channel or chat name is not a project key.
    """
    if workspace and str(workspace).strip():
        return _call(lambda: _client().projects())
    return _call(lambda: _client().projects(all_workspaces=True))


@tool
def sprrint_projects_get(project: str, workspace: Optional[str] = None) -> dict:
    """Get one project by key or slug, including members.

    workspace is an optional workspace slug for this call. A key that exists in only one workspace is found without it.
    """
    return _call(lambda: _client().project(project))


@tool
def sprrint_projects_create(
    name: str,
    key: Optional[str] = None,
    description: str = '',
    visibility: str = 'private',
    default_view: str = 'now',
    workspace: Optional[str] = None,
) -> dict:
    """Create a project. Key is 2–4 letters, unique in the workspace, and stays fixed. visibility is private|workspace.

    Pass workspace (slug) so the project is created there. Without it, the project lands in the active workspace.
    """
    fields = {'name': name, 'description': description, 'visibility': visibility, 'default_view': default_view}
    if key:
        fields['key'] = key
    return _call(lambda: _client().create_project(**fields))


@tool
def sprrint_projects_update(
    project: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    visibility: Optional[str] = None,
    default_view: Optional[str] = None,
    workspace: Optional[str] = None,
) -> dict:
    """Update project settings. workspace is an optional workspace slug for this call."""
    current = _client().project(project)
    payload = {
        'name': name or current['name'],
        'key': current['key'],
        'description': description if description is not None else current.get('description') or '',
        'visibility': visibility or current['visibility'],
        'default_view': default_view or current['default_view'],
    }
    return _call(lambda: _client().update_project(project, **payload))


@tool
def sprrint_projects_archive(project: str, workspace: Optional[str] = None) -> dict:
    """Archive a project. workspace is an optional workspace slug for this call."""
    return _call(lambda: _client().archive_project(project))


@tool
def sprrint_projects_restore(project_id: int, workspace: Optional[str] = None) -> dict:
    """Restore an archived project by numeric id. Pass workspace when it is not the active workspace."""
    return _call(lambda: _client().restore_project(project_id))


@tool
def sprrint_projects_delete(project: str, confirm: str, workspace: Optional[str] = None) -> dict:
    """Delete a project. confirm must be the exact project name. workspace is an optional workspace slug for this call."""
    return _call(lambda: _client().delete_project(project, confirm))


@tool
def sprrint_projects_add_member(project: str, user: str, role: str = 'member', workspace: Optional[str] = None) -> dict:
    """Add a workspace member to a project. user is a username or id. role is member|owner."""
    return _call(lambda: _client().add_project_member(project, user, role))


@tool
def sprrint_projects_remove_member(project: str, user_id: int, workspace: Optional[str] = None) -> dict:
    """Remove a person from a project."""
    return _call(lambda: _client().remove_project_member(project, user_id))


@tool
def sprrint_home(project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """Project home dashboard."""
    return _call(lambda: _client().home(_project(project)))


@tool
def sprrint_tasks_list(
    project: Optional[str] = None,
    sprint: Optional[str] = None,
    assigned: str = 'any',
    due: str = 'any',
    q: Optional[str] = None,
    workspace: Optional[str] = None,
) -> dict:
    """List tasks on a project. assigned is me|any|username. due is any|overdue|soon|later. sprint can be a slug or free.

    workspace is an optional workspace slug for this call.
    """
    return _call(lambda: _client().tasks(_project(project), sprint=sprint or '', assigned=assigned, due=due, q=q or ''))


@tool
def sprrint_tasks_get(key: str, project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """Get a task by key (BR-12), including comments, attachments, git_refs, releases, and description_files.

    description keeps stable media:id tokens. description_files lists each inline file in order
    with id, name, content_type, kind, size, url, role (image|file), and markdown.
    The attachments list is separate and does not replace description_files.
    git_refs lists linked pull requests, branches, and commits.
    """
    def run():
        api = _client()
        ref = _project(project)
        return _with_description_files(api, ref, api.task(ref, key))
    return _call(run)


@tool
def sprrint_tasks_create(
    title: str,
    project: Optional[str] = None,
    description: str = '',
    status: str = 'todo',
    priority: str = 'none',
    sprint: Optional[str] = None,
    assignee: Optional[str] = None,
    due_on: Optional[str] = None,
    category: Optional[str] = None,
    parent: Optional[str] = None,
    blocked_note: Optional[str] = None,
    tags: Optional[str] = None,
    workspace: Optional[str] = None,
) -> dict:
    """Create a task. status is todo|progress|blocked|done. priority is none|low|medium|high. assignee and tags are comma-separated.

    workspace is an optional workspace slug for this call. A project key that exists in only one workspace is found without it.
    To embed a file, upload it with sprrint_files_upload first, then put the returned markdown
    in description: ![name](media:id) for an image, [name](media:id) for any other file.
    Text-only descriptions stay valid. A failed upload does not create the task.
    """
    fields = {'title': title, 'description': description, 'status': status, 'priority': priority}
    if sprint:
        fields['sprint'] = sprint
    if assignee:
        fields['assignees'] = [part.strip() for part in assignee.split(',') if part.strip()]
    if due_on:
        fields['due_on'] = due_on
    if category:
        fields['category'] = category
    if parent is not None:
        fields['parent'] = parent
    if blocked_note is not None:
        fields['blocked_note'] = blocked_note
    if tags:
        fields['tags'] = [part.strip() for part in tags.split(',') if part.strip()]
    def run():
        api = _client()
        ref = _project(project)
        return _with_description_files(api, ref, api.create_task(ref, **fields))
    return _call(run)


@tool
def sprrint_tasks_update(
    key: str,
    project: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    sprint: Optional[str] = None,
    assignee: Optional[str] = None,
    due_on: Optional[str] = None,
    category: Optional[str] = None,
    parent: Optional[str] = None,
    blocked_note: Optional[str] = None,
    tags: Optional[str] = None,
    workspace: Optional[str] = None,
) -> dict:
    """Update a task. Pass only the fields that should change; others stay as they are.

    When changing description, send the full description. Keep existing ![name](media:id) and
    [name](media:id) tokens so files stay in place. Insert new markdown from sprrint_files_upload
    at the position you want. This call does not upload bytes. If it fails, the previous description remains.
    """
    api = _client()
    ref = _project(project)
    current = api.task(ref, key)
    fields = {
        'title': title or current['title'],
        'description': description if description is not None else current.get('description') or '',
        'status': status or current['status'],
        'priority': priority or current['priority'],
    }
    if sprint is not None:
        fields['sprint'] = sprint
    elif current.get('sprint'):
        fields['sprint'] = current['sprint']['slug']
    if assignee is not None:
        fields['assignees'] = [part.strip() for part in assignee.split(',') if part.strip()]
    elif current.get('assignees'):
        fields['assignees'] = [person.get('username') for person in current['assignees'] if person.get('username')]
    elif current.get('assignee'):
        fields['assignees'] = [current['assignee']['username']]
    if due_on is not None:
        fields['due_on'] = due_on
    elif current.get('due_on'):
        fields['due_on'] = current['due_on']
    if category is not None:
        fields['category'] = category
    elif current.get('category'):
        fields['category'] = current['category']['slug']
    if parent is not None:
        fields['parent'] = parent
    elif current.get('parent'):
        fields['parent'] = current['parent']['key']
    if blocked_note is not None:
        fields['blocked_note'] = blocked_note
    elif current.get('blocked_note'):
        fields['blocked_note'] = current['blocked_note']
    if tags is not None:
        fields['tags'] = [part.strip() for part in tags.split(',') if part.strip()]
    return _call(lambda: _with_description_files(api, ref, api.update_task(ref, key, **fields)))


@tool
def sprrint_tasks_delete(key: str, project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """Permanently delete a task. Subtasks become top-level."""
    return _call(lambda: _client().delete_task(_project(project), key))


@tool
def sprrint_tasks_move(
    key: str,
    status: str,
    project: Optional[str] = None,
    blocked_note: Optional[str] = None,
    confirm_complete: bool = False,
    workspace: Optional[str] = None,
) -> dict:
    """Move a task to todo, progress, blocked, or done. blocked needs blocked_note. done may need confirm_complete when subtasks remain."""
    return _call(lambda: _client().move_task(
        _project(project),
        key,
        status,
        blocked_note=blocked_note,
        confirm_complete=confirm_complete,
    ))


@tool
def sprrint_files_upload(
    filename: str,
    content_base64: str,
    project: Optional[str] = None,
    content_type: Optional[str] = None,
    workspace: Optional[str] = None,
) -> dict:
    """Upload a file for a task description or a comment. Send the bytes as base64. Do not send a local filesystem path.

    Returns id, name, content_type, kind, size, url, role, and markdown.
    Description: insert markdown ![name](media:id) for an image, [name](media:id) for any other file,
    then call sprrint_tasks_create or sprrint_tasks_update.
    Comment: pass the returned id to sprrint_tasks_comment as file_ids. Markdown in the comment body
    is also saved as an attachment.

    New task: create the task (text is fine), upload, then update the description.
    Existing task: upload, then update with the previous description plus the new markdown in place.
    Multiple files: upload each, then put the markdown snippets in the order they should appear.

    Limits match the web app: 25 MB. Types: png, jpeg, gif, webp, mp4, webm, quicktime, pdf, txt, md, doc, docx.
    A failed upload writes nothing and does not change a description. Retry the upload, or reuse a returned id
    if only the description update failed. Unused uploads stay in the project library until someone deletes them.
    This tool does not delete them, so a retry cannot remove a file the description still needs.
    """
    def run():
        name, raw = _decode_upload(filename, content_base64)
        api = _client()
        ref = _project(project)
        payload = api.upload_bytes(ref, name, raw, content_type or None)
        file_id = str(payload.get('id') or '')
        label = payload.get('label') or payload.get('name') or name
        if payload.get('kind') == 'image' or (content_type or '').startswith('image/'):
            role = 'image'
        else:
            role = 'file'
        payload['role'] = role
        payload['label'] = label
        payload['markdown'] = payload.get('markdown') or _markdown_for(role, label, file_id)
        return payload
    return _call(run)


@tool
def sprrint_tasks_comment(
    key: str,
    body: str = '',
    project: Optional[str] = None,
    parent: Optional[int] = None,
    file_ids: Optional[str] = None,
    workspace: Optional[str] = None,
) -> dict:
    """Comment on a task. parent is an optional comment id for a reply.

    To attach a file, upload it with sprrint_files_upload first, then pass the returned id
    in file_ids (comma-separated). You can also put the returned markdown in body:
    ![name](media:id) or [name](media:id). Those files are saved as comment attachments.
    The stored body keeps the text. Attached markdown is not left as a raw token.
    A comment can be a file with an empty body. A failed upload does not create the comment.
    This call does not upload bytes. If it fails, nothing is attached and the previous comments remain.
    """
    ids = [part.strip() for part in file_ids.split(',') if part.strip()] if file_ids else None
    return _call(lambda: _client().comment(_project(project), key, body, parent, file_ids=ids))


@tool
def sprrint_tasks_git_link(
    key: str,
    value: str,
    project: Optional[str] = None,
    kind: Optional[str] = None,
    title: Optional[str] = None,
    workspace: Optional[str] = None,
) -> dict:
    """Link a pull request, branch, or commit to a task.

    value is a PR URL, commit URL/SHA, or branch name. kind is optional: pull_request|branch|commit.
    title is an optional PR title or commit subject.
    """
    return _call(lambda: _client().link_git_ref(_project(project), key, value, kind=kind, title=title))


@tool
def sprrint_tasks_git_unlink(key: str, ref_id: int, project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """Remove a git ref from a task. ref_id comes from git_refs on sprrint_tasks_get."""
    return _call(lambda: _client().unlink_git_ref(_project(project), key, ref_id))


@tool
def sprrint_sprints_list(project: Optional[str] = None, status: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """List sprints. status is planned|active|done."""
    return _call(lambda: _client().sprints(_project(project), status))


@tool
def sprrint_sprints_get(slug: str, project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """Get a sprint and its tasks."""
    return _call(lambda: _client().sprint(_project(project), slug))


@tool
def sprrint_sprints_create(
    name: str,
    starts_on: str,
    ends_on: str,
    project: Optional[str] = None,
    goal: str = '',
    status: str = 'planned',
    category: Optional[str] = None,
    take: Optional[str] = None,
    workspace: Optional[str] = None,
) -> dict:
    """Create a sprint. Dates are YYYY-MM-DD. take is comma-separated task keys to pull in."""
    fields = {'name': name, 'goal': goal, 'starts_on': starts_on, 'ends_on': ends_on, 'status': status}
    if category:
        fields['category'] = category
    if take:
        fields['take'] = [part.strip() for part in take.split(',') if part.strip()]
    return _call(lambda: _client().create_sprint(_project(project), **fields))


@tool
def sprrint_sprints_update(
    slug: str,
    project: Optional[str] = None,
    name: Optional[str] = None,
    goal: Optional[str] = None,
    starts_on: Optional[str] = None,
    ends_on: Optional[str] = None,
    status: Optional[str] = None,
    workspace: Optional[str] = None,
) -> dict:
    """Update a sprint."""
    fields = {k: v for k, v in {
        'name': name, 'goal': goal, 'starts_on': starts_on, 'ends_on': ends_on, 'status': status,
    }.items() if v is not None}
    return _call(lambda: _client().update_sprint(_project(project), slug, **fields))


@tool
def sprrint_sprints_start(slug: str, project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """Start a planned sprint."""
    return _call(lambda: _client().start_sprint(_project(project), slug))


@tool
def sprrint_sprints_pause(slug: str, project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """Pause an active sprint back to planned."""
    return _call(lambda: _client().pause_sprint(_project(project), slug))


@tool
def sprrint_sprints_complete(slug: str, project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """Mark an active sprint done."""
    return _call(lambda: _client().complete_sprint(_project(project), slug))


@tool
def sprrint_sprints_delete(slug: str, project: Optional[str] = None, move: str = 'free', workspace: Optional[str] = None) -> dict:
    """Delete a sprint. move=free sends remaining tasks to the Black Hole."""
    return _call(lambda: _client().delete_sprint(_project(project), slug, move))


@tool
def sprrint_releases_list(project: Optional[str] = None, status: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """List releases. status is upcoming|live|past. Membership is tasks (selected_tasks), not sprints."""
    return _call(lambda: _client().releases(_project(project), status))


@tool
def sprrint_releases_get(slug: str, project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """Get a release and its selected tasks."""
    return _call(lambda: _client().release(_project(project), slug))


@tool
def sprrint_releases_create(
    name: str = '',
    project: Optional[str] = None,
    version: str = '',
    description: str = '',
    status: str = 'upcoming',
    target_on: Optional[str] = None,
    environments: Optional[str] = None,
    owner: Optional[str] = None,
    tasks: Optional[str] = None,
    sprints: Optional[str] = None,
    workspace: Optional[str] = None,
) -> dict:
    """Create a release. name is optional; version and environments are the primary identity. target_on is YYYY-MM-DD. environments is comma-separated env slugs/ids (each creates its own release page). tasks is comma-separated task ids/keys. sprints is comma-separated sprint slugs/ids that expand to tasks server-side."""
    fields = {'name': name, 'version': version, 'description': description, 'status': status}
    if target_on:
        fields['target_on'] = target_on
    if environments:
        fields['environments'] = [part.strip() for part in environments.split(',') if part.strip()]
    if owner:
        fields['owner'] = owner
    if tasks:
        fields['selected_tasks'] = [part.strip() for part in tasks.split(',') if part.strip()]
    if sprints:
        fields['selected_sprints'] = [part.strip() for part in sprints.split(',') if part.strip()]
    return _call(lambda: _client().create_release(_project(project), **fields))


@tool
def sprrint_releases_update(
    slug: str,
    project: Optional[str] = None,
    name: Optional[str] = None,
    version: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    target_on: Optional[str] = None,
    environment: Optional[str] = None,
    owner: Optional[str] = None,
    tasks: Optional[str] = None,
    sprints: Optional[str] = None,
    workspace: Optional[str] = None,
) -> dict:
    """Update a release. Pass tasks/sprints to replace membership; sprints expand to tasks server-side."""
    fields = {k: v for k, v in {
        'name': name,
        'version': version,
        'description': description,
        'status': status,
        'target_on': target_on,
        'environment': environment,
        'owner': owner,
    }.items() if v is not None}
    if tasks is not None:
        fields['selected_tasks'] = [part.strip() for part in tasks.split(',') if part.strip()]
    if sprints is not None:
        fields['selected_sprints'] = [part.strip() for part in sprints.split(',') if part.strip()]
    return _call(lambda: _client().update_release(_project(project), slug, **fields))


@tool
def sprrint_blackhole_list(project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """List unsprinted open tasks in the Black Hole."""
    return _call(lambda: _client().blackhole(_project(project)))


@tool
def sprrint_blackhole_pull(key: str, project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """Pull a void task into the landing sprint (active first, else planned)."""
    return _call(lambda: _client().pull(_project(project), key))


@tool
def sprrint_blackhole_drop(key: str, project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """Drop a task out of its sprint back into the Black Hole."""
    return _call(lambda: _client().drop(_project(project), key))


@tool
def sprrint_workspace_get(workspace: Optional[str] = None) -> dict:
    """Workspace settings, members, pending invites, and archived projects.

    workspace is an optional workspace slug for this call.
    """
    return _call(lambda: _client().workspace())


@tool
def sprrint_workspace_update(name: Optional[str] = None, slug: Optional[str] = None, description: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """Update workspace name, slug, or description."""
    current = _client().workspace()['workspace']
    payload = {
        'name': name or current['name'],
        'slug': slug or current['slug'],
        'description': description if description is not None else current.get('description') or '',
    }
    return _call(lambda: _client().update_workspace(**payload))


@tool
def sprrint_workspace_invite(email: str, role: str = 'member', workspace: Optional[str] = None) -> dict:
    """Invite someone to the workspace by email. role is member|admin."""
    return _call(lambda: _client().invite(email, role))


@tool
def sprrint_workspace_set_role(user_id: int, role: str, workspace: Optional[str] = None) -> dict:
    """Change a workspace member role. role is owner|admin|member."""
    return _call(lambda: _client().set_role(user_id, role))


@tool
def sprrint_workspace_remove_member(user_id: int, workspace: Optional[str] = None) -> dict:
    """Remove a person from the workspace."""
    return _call(lambda: _client().remove_member(user_id))


@tool
def sprrint_profile_update(
    display_name: Optional[str] = None,
    username: Optional[str] = None,
    timezone: Optional[str] = None,
    avatar: Optional[str] = None,
) -> dict:
    """Update the signed-in profile."""
    fields = {k: v for k, v in {
        'display_name': display_name, 'username': username, 'timezone': timezone, 'avatar': avatar,
    }.items() if v is not None}
    return _call(lambda: _client().update_me(**fields))


@tool
def sprrint_categories_list(project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """List task and sprint categories."""
    return _call(lambda: _client().categories(_project(project)))


@tool
def sprrint_categories_create(kind: str, name: str, project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """Create a category. kind is task|sprint."""
    return _call(lambda: _client().create_category(_project(project), kind, name))


@tool
def sprrint_categories_delete(category_id: int, project: Optional[str] = None, workspace: Optional[str] = None) -> dict:
    """Delete an unused custom category."""
    return _call(lambda: _client().delete_category(_project(project), category_id))


@tool
def sprrint_keys_list() -> dict:
    """List active API keys for the signed-in user."""
    return _call(lambda: _client().keys())


@tool
def sprrint_keys_create(name: str = 'MCP', source: str = 'mcp') -> dict:
    """Create an API key. The full token is returned once."""
    return _call(lambda: _client().create_key(name, source))


def main():
    mcp.run(transport='stdio')


if __name__ == '__main__':
    main()
