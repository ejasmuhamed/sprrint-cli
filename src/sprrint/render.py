from __future__ import annotations

import json

from rich.table import Table
from rich.panel import Panel


def dump(data, json_mode=False):
    if json_mode:
        return json.dumps(data, indent=2, default=str)
    return data


def task_table(tasks, title='Tasks'):
    table = Table(title=title, show_lines=False, expand=True)
    table.add_column('Key', style='cyan', no_wrap=True)
    table.add_column('Title')
    table.add_column('Status', style='magenta')
    table.add_column('Sprint')
    table.add_column('Who')
    table.add_column('Due')
    for task in tasks:
        table.add_row(
            task.get('key') or '',
            task.get('title') or '',
            task.get('status') or '',
            (task.get('sprint') or {}).get('name') or 'Black Hole',
            ', '.join(
                person.get('display_name')
                for person in (task.get('assignees') or [])
                if person and person.get('display_name')
            )
            or (task.get('assignee') or {}).get('display_name')
            or '—',
            task.get('due_on') or '—',
        )
    return table


def project_table(projects):
    table = Table(title='Projects', expand=True)
    table.add_column('Key', style='cyan', no_wrap=True)
    table.add_column('Name')
    table.add_column('Visibility')
    table.add_column('View')
    for project in projects:
        table.add_row(project.get('key'), project.get('name'), project.get('visibility'), project.get('default_view'))
    return table


def sprint_table(sprints):
    table = Table(title='Sprints', expand=True)
    table.add_column('Slug', style='cyan')
    table.add_column('Name')
    table.add_column('Status')
    table.add_column('Dates')
    table.add_column('Health')
    for sprint in sprints:
        dates = f"{sprint.get('starts_on') or '?'} → {sprint.get('ends_on') or '?'}"
        health = (sprint.get('stats') or {}).get('health_label') or sprint.get('remaining') or ''
        table.add_row(sprint.get('slug'), sprint.get('name'), sprint.get('status'), dates, health)
    return table


def event_table(events):
    table = Table(title='Activity', expand=True)
    table.add_column('When', no_wrap=True)
    table.add_column('Who')
    table.add_column('What')
    for event in events:
        actor = (event.get('actor') or {}).get('display_name') or 'System'
        table.add_row((event.get('created_at') or '')[:16], actor, event.get('summary') or '')
    return table


def member_table(members):
    table = Table(title='People', expand=True)
    table.add_column('Name')
    table.add_column('Username', style='cyan')
    table.add_column('Role')
    for item in members:
        user = item.get('user') or item
        table.add_row(user.get('display_name'), f"@{user.get('username')}", item.get('role') or '')
    return table


def now_panel(payload):
    counts = payload.get('counts') or {}
    summary = (
        f"Todo {counts.get('todo', 0)} · "
        f"Doing {counts.get('progress', 0)} · "
        f"Blocked {counts.get('blocked', 0)} · "
        f"Done {counts.get('done', 0)}"
    )
    return Panel(summary, title=f"Now · {(payload.get('project') or {}).get('name') or 'board'}", border_style='cyan')
