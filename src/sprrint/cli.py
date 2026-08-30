from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from sprrint import __version__
from sprrint.client import Client
from sprrint.config import config_path, load, save, update
from sprrint.errors import AuthError, SprrintError
from sprrint.render import event_table, member_table, now_panel, project_table, sprint_table, task_table
from sprrint import stickman

app = typer.Typer(
    name='sprrint',
    help='Sprrint from a terminal. Same workspace, same work, smaller door.',
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
projects_app = typer.Typer(help='Projects')
tasks_app = typer.Typer(help='Tasks')
sprints_app = typer.Typer(help='Sprints')
blackhole_app = typer.Typer(help='Black Hole')
workspace_app = typer.Typer(help='Workspace')
keys_app = typer.Typer(help='API keys')
me_app = typer.Typer(help='Your profile')
config_app = typer.Typer(help='Local CLI settings')
categories_app = typer.Typer(help='Categories')

app.add_typer(projects_app, name='projects')
app.add_typer(tasks_app, name='tasks')
app.add_typer(sprints_app, name='sprints')
app.add_typer(blackhole_app, name='blackhole')
app.add_typer(workspace_app, name='workspace')
app.add_typer(keys_app, name='keys')
app.add_typer(me_app, name='me')
app.add_typer(config_app, name='config')
app.add_typer(categories_app, name='categories')

console = Console()
err = Console(stderr=True)


def _plain() -> bool:
    return any(ctx.params.get('plain') for ctx in [typer.get_current_context(silent=True)] if ctx)


def run(kind, caption, fn, *, plain=False):
    try:
        with stickman.action(err, kind, caption, plain=plain):
            result = fn()
    except (SprrintError, AuthError) as exc:
        stickman.stumble(err, exc.message, plain=plain)
        raise typer.Exit(1) from exc
    return result


def out(data, json_mode=False, render=None, win=None, plain=False):
    if json_mode:
        console.print_json(json.dumps(data, default=str))
        return
    if render:
        console.print(render)
    elif isinstance(data, str):
        console.print(data)
    if win:
        stickman.celebrate(console, win, plain=plain)


def client() -> Client:
    return Client()


def project_ref(project: Optional[str]) -> str:
    return Client().resolve_project(project)


@app.callback()
def _root(
    version: bool = typer.Option(False, '--version', help='Show version and exit.'),
):
    if version:
        console.print(__version__)
        raise typer.Exit()


@app.command()
def login(
    url: Optional[str] = typer.Option(None, '--url', help='Sprrint site, e.g. https://sprrint.run'),
    email: Optional[str] = typer.Option(None, '--email', '-e'),
    name: str = typer.Option('CLI', '--name', help='Name stored on the API key.'),
    plain: bool = typer.Option(False, '--plain'),
    json_mode: bool = typer.Option(False, '--json'),
):
    """Sign in with an email code and store an API key."""
    settings = load()
    if url:
        settings.api_url = url.rstrip('/')
        save(settings)
    if not email:
        email = typer.prompt('Email')
    api = Client(settings)
    run('login', 'Sending a code', lambda: api.login_start(email), plain=plain)
    if not json_mode:
        console.print(f'Check {email} for a 6-digit code.')
    code = typer.prompt('Code')
    result = run('login', 'Opening the door', lambda: api.login_verify(email, code, name=name), plain=plain)
    settings.api_key = result['token']
    save(settings)
    me = result.get('user') or {}
    out(result, json_mode, win=f"In as {me.get('display_name') or me.get('username') or email}", plain=plain)
    if not json_mode:
        console.print(f"Key saved to {settings.host()}. Run `sprrint now` or `sprrint mcp`.")


@app.command()
def logout(plain: bool = typer.Option(False, '--plain')):
    """Forget the stored API key."""
    settings = load()
    settings.api_key = ''
    save(settings)
    out('Signed out.', win='See you on the next orbit.', plain=plain)


@app.command()
def whoami(json_mode: bool = typer.Option(False, '--json'), plain: bool = typer.Option(False, '--plain')):
    """Show the signed-in person and workspace."""
    data = run('read', 'Checking the badge', lambda: client().me(), plain=plain)
    if json_mode:
        out(data, True)
        return
    user = data.get('user') or {}
    workspace = data.get('workspace') or {}
    console.print(f"{user.get('display_name')}  @{user.get('username')}  {user.get('email')}")
    if workspace:
        console.print(f"{workspace.get('name')}  /{workspace.get('slug')}  {workspace.get('role')}")
    stickman.celebrate(err, 'That is you.', plain=plain)


@app.command()
def now(
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    sprint: Optional[str] = typer.Option(None),
    assigned: str = typer.Option('any'),
    due: str = typer.Option('any'),
    q: Optional[str] = typer.Option(None, '--q'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    """The working board."""
    api = client()
    ref = run('read', 'Finding the board', lambda: api.resolve_project(project), plain=plain)
    payload = run('read', 'Walking the columns', lambda: api.now(ref, sprint=sprint or '', assigned=assigned, due=due, q=q or ''), plain=plain)
    if json_mode:
        out(payload, True)
        return
    console.print(now_panel(payload))
    tasks = [task for column in payload.get('columns') or [] for task in column.get('tasks') or []]
    console.print(task_table(tasks, title='Now'))
    stickman.celebrate(err, 'Board is up.', plain=plain)


@app.command()
def overview(json_mode: bool = typer.Option(False, '--json'), plain: bool = typer.Option(False, '--plain')):
    """Workspace home: counts, sprints, attention."""
    data = run('read', 'Looking over the workspace', lambda: client().overview(), plain=plain)
    if json_mode:
        out(data, True)
        return
    console.print(data.get('greeting') or 'Hello.')
    counts = data.get('counts') or {}
    console.print(f"Open {counts.get('open', 0)} · Done {counts.get('done', 0)}")
    console.print(task_table(data.get('attention') or [], title='Needs a nudge'))
    console.print(sprint_table(data.get('active_sprints') or []))


@app.command()
def search(
    q: str = typer.Argument(...),
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    """Search tasks, sprints, and people."""
    data = run('search', f'Searching for {q}', lambda: client().search(q, project), plain=plain)
    if json_mode:
        out(data, True)
        return
    console.print(task_table(data.get('tasks') or [], title='Tasks'))
    console.print(sprint_table(data.get('sprints') or []))
    people = [{'user': person} for person in data.get('people') or []]
    console.print(member_table(people))


@app.command()
def activity(
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    tab: str = typer.Option('all'),
    range: str = typer.Option('7', '--range'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    """Activity feed."""
    api = client()
    ref = project or api.settings.project or None
    data = run('read', 'Reading the diary', lambda: api.activity(ref, tab=tab, range=range), plain=plain)
    out(data, json_mode, render=None if json_mode else event_table(data.get('events') or []))


@app.command()
def mcp():
    """Run the Sprrint MCP server on stdio."""
    from sprrint.mcp_server import main as mcp_main
    mcp_main()


@projects_app.command('list')
def projects_list(json_mode: bool = typer.Option(False, '--json'), plain: bool = typer.Option(False, '--plain')):
    data = run('read', 'Listing projects', lambda: client().projects(), plain=plain)
    out(data, json_mode, None if json_mode else project_table(data))


@projects_app.command('get')
def projects_get(ref: str, json_mode: bool = typer.Option(False, '--json'), plain: bool = typer.Option(False, '--plain')):
    data = run('read', 'Opening the project', lambda: client().project(ref), plain=plain)
    out(data, json_mode, win=data.get('name') if not json_mode else None, plain=plain)
    if not json_mode:
        console.print(f"{data.get('key')}  {data.get('name')}  {data.get('visibility')}")


@projects_app.command('create')
def projects_create(
    name: str = typer.Option(...),
    key: Optional[str] = typer.Option(None),
    description: str = typer.Option(''),
    visibility: str = typer.Option('private'),
    default_view: str = typer.Option('now'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    fields = {'name': name, 'description': description, 'visibility': visibility, 'default_view': default_view}
    if key:
        fields['key'] = key
    data = run('save', f'Opening {name}', lambda: client().create_project(**fields), plain=plain)
    out(data, json_mode, win=f"{data.get('key')} is ready.", plain=plain)


@projects_app.command('update')
def projects_update(
    ref: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    visibility: Optional[str] = None,
    default_view: Optional[str] = None,
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    fields = {k: v for k, v in {
        'name': name, 'description': description, 'visibility': visibility, 'default_view': default_view,
    }.items() if v is not None}
    current = client().project(ref)
    payload = {
        'name': fields.get('name', current['name']),
        'key': current['key'],
        'description': fields.get('description', current.get('description') or ''),
        'visibility': fields.get('visibility', current['visibility']),
        'default_view': fields.get('default_view', current['default_view']),
    }
    data = run('save', 'Saving project', lambda: client().update_project(ref, **payload), plain=plain)
    out(data, json_mode, win='Project saved.', plain=plain)


@projects_app.command('archive')
def projects_archive(ref: str, json_mode: bool = typer.Option(False, '--json'), plain: bool = typer.Option(False, '--plain')):
    data = run('save', 'Archiving', lambda: client().archive_project(ref), plain=plain)
    out(data, json_mode, win='Archived.', plain=plain)


@projects_app.command('restore')
def projects_restore(project_id: int, json_mode: bool = typer.Option(False, '--json'), plain: bool = typer.Option(False, '--plain')):
    data = run('save', 'Restoring', lambda: client().restore_project(project_id), plain=plain)
    out(data, json_mode, win='Back on the switcher.', plain=plain)


@projects_app.command('delete')
def projects_delete(
    ref: str,
    confirm: str = typer.Option(..., help='Type the project name.'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    data = run('save', 'Deleting project', lambda: client().delete_project(ref, confirm), plain=plain)
    out(data, json_mode, win='Gone.', plain=plain)


@projects_app.command('add-member')
def projects_add_member(
    ref: str,
    user: str,
    role: str = typer.Option('member'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    data = run('save', 'Adding to the crew', lambda: client().add_project_member(ref, user, role), plain=plain)
    out(data, json_mode, win='They are on this project.', plain=plain)


@projects_app.command('remove-member')
def projects_remove_member(
    ref: str,
    user_id: int,
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    data = run('save', 'Taking them off', lambda: client().remove_project_member(ref, user_id), plain=plain)
    out(data, json_mode, win='Off the project.', plain=plain)


@tasks_app.command('list')
def tasks_list(
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    sprint: Optional[str] = None,
    assigned: str = 'any',
    due: str = 'any',
    q: Optional[str] = None,
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    data = run('read', 'Listing tasks', lambda: api.tasks(ref, sprint=sprint or '', assigned=assigned, due=due, q=q or ''), plain=plain)
    out(data, json_mode, None if json_mode else task_table(data))


@tasks_app.command('get')
def tasks_get(
    key: str,
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    data = run('read', f'Reading {key}', lambda: api.task(ref, key), plain=plain)
    if json_mode:
        out(data, True)
        return
    console.print(f"{data.get('key')}  {data.get('title')}")
    console.print(f"{data.get('status')}  {(data.get('sprint') or {}).get('name') or 'Black Hole'}")
    if data.get('description'):
        console.print(data['description'])
    for comment in data.get('comments') or []:
        author = (comment.get('author') or {}).get('display_name')
        console.print(f"- {author}: {comment.get('body')}")
    stickman.celebrate(err, 'Task is open.', plain=plain)


@tasks_app.command('create')
def tasks_create(
    title: str = typer.Option(...),
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    description: str = typer.Option(''),
    status: str = typer.Option('todo'),
    priority: str = typer.Option('none'),
    sprint: Optional[str] = None,
    assignee: Optional[str] = None,
    due: Optional[str] = typer.Option(None, '--due'),
    category: Optional[str] = None,
    tags: Optional[str] = typer.Option(None, help='Comma-separated tags.'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    fields = {'title': title, 'description': description, 'status': status, 'priority': priority}
    if sprint:
        fields['sprint'] = sprint
    if assignee:
        fields['assignee'] = assignee
    if due:
        fields['due_on'] = due
    if category:
        fields['category'] = category
    if tags:
        fields['tags'] = [part.strip() for part in tags.split(',') if part.strip()]
    data = run('save', f'Planting {title}', lambda: api.create_task(ref, **fields), plain=plain)
    out(data, json_mode, win=f"{data.get('key')} is on the board.", plain=plain)


@tasks_app.command('update')
def tasks_update(
    key: str,
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    sprint: Optional[str] = None,
    assignee: Optional[str] = None,
    due: Optional[str] = typer.Option(None, '--due'),
    category: Optional[str] = None,
    tags: Optional[str] = None,
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
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
    if due is not None:
        fields['due_on'] = due
    elif current.get('due_on'):
        fields['due_on'] = current['due_on']
    if category is not None:
        fields['category'] = category
    elif current.get('category'):
        fields['category'] = current['category']['slug']
    if tags is not None:
        fields['tags'] = [part.strip() for part in tags.split(',') if part.strip()]
    data = run('save', f'Saving {key}', lambda: api.update_task(ref, key, **fields), plain=plain)
    out(data, json_mode, win='Saved.', plain=plain)


@tasks_app.command('move')
def tasks_move(
    key: str,
    status: str,
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    data = run('work', f'Moving {key}', lambda: api.move_task(ref, key, status), plain=plain)
    out(data, json_mode, win=f"{key} → {status}", plain=plain)


@tasks_app.command('comment')
def tasks_comment(
    key: str,
    body: str,
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    parent: Optional[int] = None,
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    data = run('save', 'Leaving a note', lambda: api.comment(ref, key, body, parent), plain=plain)
    out(data, json_mode, win='Noted.', plain=plain)


@tasks_app.command('attach')
def tasks_attach(
    key: str,
    file: Path,
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    data = run('save', f'Attaching {file.name}', lambda: api.attach(ref, key, file), plain=plain)
    out(data, json_mode, win='Attached.', plain=plain)


@sprints_app.command('list')
def sprints_list(
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    status: Optional[str] = None,
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    data = run('read', 'Listing sprints', lambda: api.sprints(ref, status), plain=plain)
    out(data, json_mode, None if json_mode else sprint_table(data))


@sprints_app.command('get')
def sprints_get(
    slug: str,
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    data = run('read', f'Reading {slug}', lambda: api.sprint(ref, slug), plain=plain)
    if json_mode:
        out(data, True)
        return
    console.print(f"{data.get('name')}  {data.get('status')}  {data.get('remaining')}")
    console.print(task_table(data.get('tasks') or []))


@sprints_app.command('create')
def sprints_create(
    name: str = typer.Option(...),
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    goal: str = typer.Option(''),
    starts_on: str = typer.Option(...),
    ends_on: str = typer.Option(...),
    status: str = typer.Option('planned'),
    category: Optional[str] = None,
    take: Optional[str] = typer.Option(None, help='Comma-separated task keys to pull in.'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    fields = {'name': name, 'goal': goal, 'starts_on': starts_on, 'ends_on': ends_on, 'status': status}
    if category:
        fields['category'] = category
    if take:
        fields['take'] = [part.strip() for part in take.split(',') if part.strip()]
    data = run('save', f'Opening {name}', lambda: api.create_sprint(ref, **fields), plain=plain)
    out(data, json_mode, win=f"{data.get('name')} is on the calendar.", plain=plain)


@sprints_app.command('update')
def sprints_update(
    slug: str,
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    name: Optional[str] = None,
    goal: Optional[str] = None,
    starts_on: Optional[str] = None,
    ends_on: Optional[str] = None,
    status: Optional[str] = None,
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    fields = {k: v for k, v in {
        'name': name, 'goal': goal, 'starts_on': starts_on, 'ends_on': ends_on, 'status': status,
    }.items() if v is not None}
    data = run('save', f'Saving {slug}', lambda: api.update_sprint(ref, slug, **fields), plain=plain)
    out(data, json_mode, win='Sprint saved.', plain=plain)


@sprints_app.command('delete')
def sprints_delete(
    slug: str,
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    move: str = typer.Option('free'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    data = run('save', f'Deleting {slug}', lambda: api.delete_sprint(ref, slug, move), plain=plain)
    out(data, json_mode, win='Sprint is gone. Work is in Free-fly.', plain=plain)


@blackhole_app.command('list')
def blackhole_list(
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    data = run('read', 'Peering into the void', lambda: api.blackhole(ref), plain=plain)
    if json_mode:
        out(data, True)
        return
    console.print(f"{data.get('count', 0)} drifting")
    rows = [
        {
            'key': item.get('id'),
            'title': item.get('title'),
            'status': item.get('status'),
            'due_on': item.get('age'),
            'assignee': {'display_name': item.get('owner')},
            'sprint': None,
        }
        for item in data.get('tasks') or []
    ]
    console.print(task_table(rows, title='Black Hole'))


@blackhole_app.command('pull')
def blackhole_pull(
    key: str,
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    data = run('pull', f'Pulling {key}', lambda: api.pull(ref, key), plain=plain)
    dest = (data.get('sprint') or {}).get('name') or 'a sprint'
    out(data, json_mode, win=f'{key} landed in {dest}.', plain=plain)


@blackhole_app.command('drop')
def blackhole_drop(
    key: str,
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    data = run('drop', f'Dropping {key}', lambda: api.drop(ref, key), plain=plain)
    out(data, json_mode, win=f'{key} is drifting again.', plain=plain)


@workspace_app.command('get')
def workspace_get(json_mode: bool = typer.Option(False, '--json'), plain: bool = typer.Option(False, '--plain')):
    data = run('read', 'Opening workspace', lambda: client().workspace(), plain=plain)
    if json_mode:
        out(data, True)
        return
    ws = data.get('workspace') or {}
    console.print(f"{ws.get('name')}  /{ws.get('slug')}  {ws.get('role')}")
    console.print(member_table(data.get('members') or []))


@workspace_app.command('update')
def workspace_update(
    name: Optional[str] = None,
    slug: Optional[str] = None,
    description: Optional[str] = None,
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    current = client().workspace()['workspace']
    payload = {
        'name': name or current['name'],
        'slug': slug or current['slug'],
        'description': description if description is not None else current.get('description') or '',
    }
    data = run('save', 'Saving workspace', lambda: client().update_workspace(**payload), plain=plain)
    out(data, json_mode, win='Workspace saved.', plain=plain)


@workspace_app.command('invite')
def workspace_invite(
    email: str,
    role: str = typer.Option('member'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    data = run('save', f'Inviting {email}', lambda: client().invite(email, role), plain=plain)
    out(data, json_mode, win=f'Invite sent to {email}.', plain=plain)


@workspace_app.command('role')
def workspace_role(
    user_id: int,
    role: str,
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    data = run('save', 'Changing role', lambda: client().set_role(user_id, role), plain=plain)
    out(data, json_mode, win='Role updated.', plain=plain)


@workspace_app.command('remove')
def workspace_remove(
    user_id: int,
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    data = run('save', 'Removing member', lambda: client().remove_member(user_id), plain=plain)
    out(data, json_mode, win='Removed.', plain=plain)


@workspace_app.command('leave')
def workspace_leave(json_mode: bool = typer.Option(False, '--json'), plain: bool = typer.Option(False, '--plain')):
    data = run('save', 'Leaving', lambda: client().leave(), plain=plain)
    out(data, json_mode, win='You left.', plain=plain)


@workspace_app.command('delete')
def workspace_delete(
    confirm: str = typer.Option(..., help='Type the workspace name.'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    data = run('save', 'Deleting workspace', lambda: client().delete_workspace(confirm), plain=plain)
    out(data, json_mode, win='Workspace deleted.', plain=plain)


@keys_app.command('list')
def keys_list(json_mode: bool = typer.Option(False, '--json'), plain: bool = typer.Option(False, '--plain')):
    data = run('read', 'Listing keys', lambda: client().keys(), plain=plain)
    if json_mode:
        out(data, True)
        return
    for key in data:
        console.print(f"{key.get('id')}  {key.get('name')}  {key.get('prefix')}  {key.get('source')}")


@keys_app.command('create')
def keys_create(
    name: str = typer.Option('CLI'),
    source: str = typer.Option('cli'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    data = run('save', 'Minting a key', lambda: client().create_key(name, source), plain=plain)
    out(data, json_mode, win='Copy the token now. Sprrint will not show it again.', plain=plain)
    if not json_mode:
        console.print(data.get('token'))


@keys_app.command('revoke')
def keys_revoke(key_id: int, json_mode: bool = typer.Option(False, '--json'), plain: bool = typer.Option(False, '--plain')):
    data = run('save', 'Revoking key', lambda: client().revoke_key(key_id), plain=plain)
    out(data, json_mode, win='Revoked.', plain=plain)


@me_app.command('get')
def me_get(json_mode: bool = typer.Option(False, '--json'), plain: bool = typer.Option(False, '--plain')):
    whoami(json_mode=json_mode, plain=plain)


@me_app.command('update')
def me_update(
    display_name: Optional[str] = None,
    username: Optional[str] = None,
    timezone: Optional[str] = None,
    avatar: Optional[str] = None,
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    fields = {k: v for k, v in {
        'display_name': display_name, 'username': username, 'timezone': timezone, 'avatar': avatar,
    }.items() if v is not None}
    data = run('save', 'Saving you', lambda: client().update_me(**fields), plain=plain)
    out(data, json_mode, win='Profile saved.', plain=plain)


@categories_app.command('list')
def categories_list(
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    data = run('read', 'Listing categories', lambda: api.categories(ref), plain=plain)
    out(data, json_mode)
    if not json_mode:
        console.print('Tasks: ' + ', '.join(item.get('name') for item in data.get('task') or []))
        console.print('Sprints: ' + ', '.join(item.get('name') for item in data.get('sprint') or []))


@categories_app.command('create')
def categories_create(
    kind: str,
    name: str,
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    data = run('save', f'Adding {name}', lambda: api.create_category(ref, kind, name), plain=plain)
    out(data, json_mode, win=f'{name} is ready.', plain=plain)


@categories_app.command('delete')
def categories_delete(
    category_id: int,
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    api = client()
    ref = api.resolve_project(project)
    data = run('save', 'Removing category', lambda: api.delete_category(ref, category_id), plain=plain)
    out(data, json_mode, win='Removed.', plain=plain)


@config_app.command('show')
def config_show(json_mode: bool = typer.Option(False, '--json')):
    settings = load()
    payload = {
        'api_url': settings.api_url,
        'project': settings.project,
        'api_key': f"{settings.api_key[:12]}…" if settings.api_key else '',
        'path': str(config_path()),
    }
    out(payload, json_mode)
    if not json_mode:
        console.print(f"url      {settings.api_url}")
        console.print(f"project  {settings.project or '—'}")
        console.print(f"key      {payload['api_key'] or '—'}")
        console.print(f"file     {payload['path']}")


@config_app.command('set')
def config_set(
    key: str = typer.Argument(..., help='api_url | project | api_key'),
    value: str = typer.Argument(...),
):
    if key not in {'api_url', 'project', 'api_key'}:
        raise typer.BadParameter('Use api_url, project, or api_key.')
    settings = update(**{key: value})
    console.print(f'{key} = {getattr(settings, key)}')


@app.command('files')
def files_upload(
    file: Path,
    project: Optional[str] = typer.Option(None, '--project', '-p'),
    json_mode: bool = typer.Option(False, '--json'),
    plain: bool = typer.Option(False, '--plain'),
):
    """Upload a file for comments or markdown."""
    api = client()
    ref = api.resolve_project(project)
    data = run('save', f'Uploading {file.name}', lambda: api.upload_file(ref, file), plain=plain)
    out(data, json_mode, win=f"{data.get('name')} is up. id={data.get('id')}", plain=plain)


def main():
    if len(__import__('sys').argv) == 1:
        stickman.banner(console)
    app()
