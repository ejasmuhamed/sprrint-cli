"""Sprrint MCP server — every product action, for agents."""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from sprrint.client import Client
from sprrint.errors import SprrintError

mcp = FastMCP(
    'sprrint',
    instructions=(
        'Sprrint is a sprint and task workspace. Use these tools the same way a person '
        'uses the Sprrint app: look at Now, create and move tasks, run sprints, pull work '
        'out of the Black Hole, search, comment, and manage the workspace. '
        'Identify projects by key (BR) or slug. Identify tasks by key (BR-12).'
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
        return {'ok': False, 'error': exc.message, 'code': exc.code}


@mcp.tool()
def sprrint_whoami() -> dict:
    """Show the signed-in Sprrint user and workspace."""
    return _call(lambda: _client().me())


@mcp.tool()
def sprrint_overview() -> dict:
    """Workspace home: greeting, counts, active sprints, and tasks that need a nudge."""
    return _call(lambda: _client().overview())


@mcp.tool()
def sprrint_now(
    project: Optional[str] = None,
    sprint: Optional[str] = None,
    assigned: str = 'any',
    due: str = 'any',
    q: Optional[str] = None,
) -> dict:
    """Show the Now board for a project. Filter by sprint slug, assignee username, due window, or search text."""
    return _call(lambda: _client().now(_project(project), sprint=sprint or '', assigned=assigned, due=due, q=q or ''))


@mcp.tool()
def sprrint_search(q: str, project: Optional[str] = None) -> dict:
    """Search tasks, sprints, and people. Optionally scope to a project key or slug."""
    return _call(lambda: _client().search(q, project))


@mcp.tool()
def sprrint_activity(
    project: Optional[str] = None,
    tab: str = 'all',
    range: str = '7',
    actor: Optional[str] = None,
    type: Optional[str] = None,
    q: Optional[str] = None,
) -> dict:
    """Activity feed. tab is you|all. range is 0 (today), 7, 30, or all."""
    params = {'tab': tab, 'range': range}
    if actor:
        params['actor'] = actor
    if type:
        params['type'] = type
    if q:
        params['q'] = q
    return _call(lambda: _client().activity(project, **params))


@mcp.tool()
def sprrint_projects_list() -> dict:
    """List visible projects."""
    return _call(lambda: _client().projects())


@mcp.tool()
def sprrint_projects_get(project: str) -> dict:
    """Get one project by key or slug, including members."""
    return _call(lambda: _client().project(project))


@mcp.tool()
def sprrint_projects_create(
    name: str,
    key: Optional[str] = None,
    description: str = '',
    visibility: str = 'private',
    default_view: str = 'now',
) -> dict:
    """Create a project. Key is exactly 2 letters or numbers. visibility is private|workspace."""
    fields = {'name': name, 'description': description, 'visibility': visibility, 'default_view': default_view}
    if key:
        fields['key'] = key
    return _call(lambda: _client().create_project(**fields))


@mcp.tool()
def sprrint_projects_update(
    project: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    visibility: Optional[str] = None,
    default_view: Optional[str] = None,
) -> dict:
    """Update project settings."""
    current = _client().project(project)
    payload = {
        'name': name or current['name'],
        'key': current['key'],
        'description': description if description is not None else current.get('description') or '',
        'visibility': visibility or current['visibility'],
        'default_view': default_view or current['default_view'],
    }
    return _call(lambda: _client().update_project(project, **payload))


@mcp.tool()
def sprrint_projects_archive(project: str) -> dict:
    """Archive a project."""
    return _call(lambda: _client().archive_project(project))


@mcp.tool()
def sprrint_projects_restore(project_id: int) -> dict:
    """Restore an archived project by numeric id."""
    return _call(lambda: _client().restore_project(project_id))


@mcp.tool()
def sprrint_projects_delete(project: str, confirm: str) -> dict:
    """Delete a project. confirm must be the exact project name."""
    return _call(lambda: _client().delete_project(project, confirm))


@mcp.tool()
def sprrint_projects_add_member(project: str, user: str, role: str = 'member') -> dict:
    """Add a workspace member to a project. user is a username or id. role is member|owner."""
    return _call(lambda: _client().add_project_member(project, user, role))


@mcp.tool()
def sprrint_projects_remove_member(project: str, user_id: int) -> dict:
    """Remove a person from a project."""
    return _call(lambda: _client().remove_project_member(project, user_id))


@mcp.tool()
def sprrint_home(project: Optional[str] = None) -> dict:
    """Project home dashboard."""
    return _call(lambda: _client().home(_project(project)))


@mcp.tool()
def sprrint_tasks_list(
    project: Optional[str] = None,
    sprint: Optional[str] = None,
    assigned: str = 'any',
    due: str = 'any',
    q: Optional[str] = None,
) -> dict:
    """List tasks on a project. assigned is me|any|username. due is any|overdue|soon|later. sprint can be a slug or free."""
    return _call(lambda: _client().tasks(_project(project), sprint=sprint or '', assigned=assigned, due=due, q=q or ''))


@mcp.tool()
def sprrint_tasks_get(key: str, project: Optional[str] = None) -> dict:
    """Get a task by key (BR-12), including comments and attachments."""
    return _call(lambda: _client().task(_project(project), key))


@mcp.tool()
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
    tags: Optional[str] = None,
) -> dict:
    """Create a task. status is todo|progress|blocked|done. priority is none|low|medium|high. tags is comma-separated."""
    fields = {'title': title, 'description': description, 'status': status, 'priority': priority}
    if sprint:
        fields['sprint'] = sprint
    if assignee:
        fields['assignee'] = assignee
    if due_on:
        fields['due_on'] = due_on
    if category:
        fields['category'] = category
    if tags:
        fields['tags'] = [part.strip() for part in tags.split(',') if part.strip()]
    return _call(lambda: _client().create_task(_project(project), **fields))


@mcp.tool()
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
    tags: Optional[str] = None,
) -> dict:
    """Update a task. Pass only the fields that should change; others stay as they are."""
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
        fields['assignee'] = assignee
    elif current.get('assignee'):
        fields['assignee'] = current['assignee']['username']
    if due_on is not None:
        fields['due_on'] = due_on
    elif current.get('due_on'):
        fields['due_on'] = current['due_on']
    if category is not None:
        fields['category'] = category
    elif current.get('category'):
        fields['category'] = current['category']['slug']
    if tags is not None:
        fields['tags'] = [part.strip() for part in tags.split(',') if part.strip()]
    return _call(lambda: api.update_task(ref, key, **fields))


@mcp.tool()
def sprrint_tasks_move(key: str, status: str, project: Optional[str] = None) -> dict:
    """Move a task to todo, progress, blocked, or done."""
    return _call(lambda: _client().move_task(_project(project), key, status))


@mcp.tool()
def sprrint_tasks_comment(key: str, body: str, project: Optional[str] = None, parent: Optional[int] = None) -> dict:
    """Comment on a task. parent is an optional comment id for a reply."""
    return _call(lambda: _client().comment(_project(project), key, body, parent))


@mcp.tool()
def sprrint_sprints_list(project: Optional[str] = None, status: Optional[str] = None) -> dict:
    """List sprints. status is planned|active|done."""
    return _call(lambda: _client().sprints(_project(project), status))


@mcp.tool()
def sprrint_sprints_get(slug: str, project: Optional[str] = None) -> dict:
    """Get a sprint and its tasks."""
    return _call(lambda: _client().sprint(_project(project), slug))


@mcp.tool()
def sprrint_sprints_create(
    name: str,
    starts_on: str,
    ends_on: str,
    project: Optional[str] = None,
    goal: str = '',
    status: str = 'planned',
    category: Optional[str] = None,
    take: Optional[str] = None,
) -> dict:
    """Create a sprint. Dates are YYYY-MM-DD. take is comma-separated task keys to pull in."""
    fields = {'name': name, 'goal': goal, 'starts_on': starts_on, 'ends_on': ends_on, 'status': status}
    if category:
        fields['category'] = category
    if take:
        fields['take'] = [part.strip() for part in take.split(',') if part.strip()]
    return _call(lambda: _client().create_sprint(_project(project), **fields))


@mcp.tool()
def sprrint_sprints_update(
    slug: str,
    project: Optional[str] = None,
    name: Optional[str] = None,
    goal: Optional[str] = None,
    starts_on: Optional[str] = None,
    ends_on: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """Update a sprint."""
    fields = {k: v for k, v in {
        'name': name, 'goal': goal, 'starts_on': starts_on, 'ends_on': ends_on, 'status': status,
    }.items() if v is not None}
    return _call(lambda: _client().update_sprint(_project(project), slug, **fields))


@mcp.tool()
def sprrint_sprints_delete(slug: str, project: Optional[str] = None, move: str = 'free') -> dict:
    """Delete a sprint. move=free sends remaining tasks to the Black Hole."""
    return _call(lambda: _client().delete_sprint(_project(project), slug, move))


@mcp.tool()
def sprrint_blackhole_list(project: Optional[str] = None) -> dict:
    """List unsprinted open tasks in the Black Hole."""
    return _call(lambda: _client().blackhole(_project(project)))


@mcp.tool()
def sprrint_blackhole_pull(key: str, project: Optional[str] = None) -> dict:
    """Pull a void task into the landing sprint (active first, else planned)."""
    return _call(lambda: _client().pull(_project(project), key))


@mcp.tool()
def sprrint_blackhole_drop(key: str, project: Optional[str] = None) -> dict:
    """Drop a task out of its sprint back into the Black Hole."""
    return _call(lambda: _client().drop(_project(project), key))


@mcp.tool()
def sprrint_workspace_get() -> dict:
    """Workspace settings, members, pending invites, and archived projects."""
    return _call(lambda: _client().workspace())


@mcp.tool()
def sprrint_workspace_update(name: Optional[str] = None, slug: Optional[str] = None, description: Optional[str] = None) -> dict:
    """Update workspace name, slug, or description."""
    current = _client().workspace()['workspace']
    payload = {
        'name': name or current['name'],
        'slug': slug or current['slug'],
        'description': description if description is not None else current.get('description') or '',
    }
    return _call(lambda: _client().update_workspace(**payload))


@mcp.tool()
def sprrint_workspace_invite(email: str, role: str = 'member') -> dict:
    """Invite someone to the workspace by email. role is member|admin."""
    return _call(lambda: _client().invite(email, role))


@mcp.tool()
def sprrint_workspace_set_role(user_id: int, role: str) -> dict:
    """Change a workspace member role. role is owner|admin|member."""
    return _call(lambda: _client().set_role(user_id, role))


@mcp.tool()
def sprrint_workspace_remove_member(user_id: int) -> dict:
    """Remove a person from the workspace."""
    return _call(lambda: _client().remove_member(user_id))


@mcp.tool()
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


@mcp.tool()
def sprrint_categories_list(project: Optional[str] = None) -> dict:
    """List task and sprint categories."""
    return _call(lambda: _client().categories(_project(project)))


@mcp.tool()
def sprrint_categories_create(kind: str, name: str, project: Optional[str] = None) -> dict:
    """Create a category. kind is task|sprint."""
    return _call(lambda: _client().create_category(_project(project), kind, name))


@mcp.tool()
def sprrint_categories_delete(category_id: int, project: Optional[str] = None) -> dict:
    """Delete an unused custom category."""
    return _call(lambda: _client().delete_category(_project(project), category_id))


@mcp.tool()
def sprrint_keys_list() -> dict:
    """List active API keys for the signed-in user."""
    return _call(lambda: _client().keys())


@mcp.tool()
def sprrint_keys_create(name: str = 'MCP', source: str = 'mcp') -> dict:
    """Create an API key. The full token is returned once."""
    return _call(lambda: _client().create_key(name, source))


def main():
    mcp.run(transport='stdio')


if __name__ == '__main__':
    main()
