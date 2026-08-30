from __future__ import annotations

import sys
import time
from contextlib import contextmanager

from rich.console import Console, Group
from rich.live import Live
from rich.text import Text

POSES = {
    'idle': (
        '  o  ',
        ' /|\\ ',
        ' / \\ ',
    ),
    'wave': (
        '  o  ',
        ' /|\\>',
        ' / \\ ',
    ),
    'walk_a': (
        '  o  ',
        ' /|\\ ',
        ' /   ',
    ),
    'walk_b': (
        '  o  ',
        ' /|\\ ',
        '   \\ ',
    ),
    'think': (
        '  o ?',
        ' /|\\ ',
        ' / \\ ',
    ),
    'pull': (
        '  o  ',
        ' /|=>',
        ' / \\ ',
    ),
    'drop': (
        '  o  ',
        '<|\\  ',
        ' / \\ ',
    ),
    'win': (
        '\\o/  ',
        ' |   ',
        '/ \\  ',
    ),
    'fail': (
        '  x  ',
        ' /|\\ ',
        ' / \\ ',
    ),
}

STORIES = {
    'login': 'Waving you in',
    'work': 'On the move',
    'search': 'Looking around',
    'pull': 'Hauling it out of the void',
    'drop': 'Letting it drift',
    'save': 'Pinning it down',
    'read': 'Reading the board',
}


def enabled(console: Console | None = None, plain=False) -> bool:
    if plain:
        return False
    console = console or Console(stderr=True)
    return console.is_terminal and not console.is_dumb_terminal


def render(pose: str, caption: str, style='cyan') -> Group:
    lines = POSES.get(pose, POSES['idle'])
    body = Text('\n'.join(lines), style=style)
    note = Text(caption, style='dim')
    return Group(body, note)


@contextmanager
def action(console: Console, kind='work', caption: str | None = None, plain=False):
    label = caption or STORIES.get(kind, 'Working')
    if not enabled(console, plain):
        yield
        return
    frames = {
        'login': ['wave', 'idle', 'wave', 'idle'],
        'search': ['think', 'idle', 'walk_a', 'walk_b'],
        'pull': ['pull', 'walk_a', 'pull', 'walk_b'],
        'drop': ['drop', 'idle', 'drop', 'walk_a'],
        'save': ['walk_a', 'walk_b', 'idle'],
        'read': ['idle', 'think', 'idle'],
    }.get(kind, ['walk_a', 'walk_b', 'idle', 'walk_a'])
    index = 0
    with Live(render(frames[0], f'{label}…'), console=console, refresh_per_second=8, transient=True) as live:
        running = True

        def spin():
            nonlocal index
            while running:
                live.update(render(frames[index % len(frames)], f'{label}…'))
                index += 1
                time.sleep(0.16)

        import threading
        thread = threading.Thread(target=spin, daemon=True)
        thread.start()
        try:
            yield
        finally:
            running = False
            thread.join(timeout=0.4)


def celebrate(console: Console, message: str, plain=False):
    if not enabled(console, plain):
        console.print(message)
        return
    console.print(render('win', message, 'green'))


def stumble(console: Console, message: str, plain=False):
    if not enabled(console, plain):
        console.print(f'Error: {message}', style='red')
        return
    console.print(render('fail', message, 'red'))


def banner(console: Console):
    if not console.is_terminal:
        return
    console.print(Text('  o   Sprrint', style='bold cyan'))
    console.print(Text(' /|\\  same board, smaller door', style='dim'))
    console.print(Text(' / \\', style='dim'))
