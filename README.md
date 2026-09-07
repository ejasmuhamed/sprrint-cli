# Sprrint CLI + MCP

The same Sprrint product, from a terminal or an agent.

People who never open the web app can still run the board, write tasks, move cards, run sprints, plan releases, pull work out of the Black Hole, comment, invite teammates, and manage the workspace.

```
  o
 /|\   sprrint now
 / \
```

## Install

```bash
pipx install git+https://github.com/ejasmuhamed/sprrint-cli.git
# or from this repo
pipx install .
# later: pipx install sprrint
```

You need an account on [sprrint.run](https://sprrint.run).

## Sign in

```bash
sprrint login
```

Sprrint emails a 6-digit code. After it checks out, the CLI stores an API key in `~/.config/sprrint/config.toml` (mode `600`). The CLI and MCP always talk to `https://sprrint.run`.

You can also mint a key in the web app: **You → Keys**, then:

```bash
sprrint config set api_key spr_live_…
sprrint config set workspace acme
sprrint config set project BR
```

Environment variables override the file: `SPRRINT_API_KEY`, `SPRRINT_WORKSPACE`, `SPRRINT_PROJECT`.

## Everyday commands

```bash
sprrint whoami
sprrint now
sprrint overview
sprrint search "login"
sprrint tasks create --title "Ship the CLI"
sprrint tasks move BR-12 progress
sprrint tasks move BR-12 blocked --blocked-note "Waiting on design"
sprrint tasks comment BR-12 "Landed."
sprrint sprints start launch-week
sprrint sprints pause launch-week
sprrint sprints complete launch-week
sprrint sprints create --name "Launch Week" --starts-on 2026-09-01 --ends-on 2026-09-14
sprrint releases list
sprrint releases create --name "1.0" --version v1.0 --task BR-12 --task BR-13 --sprint launch-week
sprrint releases update 1-0 --status live
sprrint blackhole list
sprrint blackhole pull BR-9
sprrint activity
```

Every mutating command has `--json` for scripts and `--plain` to skip the stickman.

```bash
sprrint --help
sprrint tasks --help
```

## MCP

The same client is an MCP server.

```bash
sprrint mcp
```

Cursor / Claude Desktop:

```json
{
  "mcpServers": {
    "sprrint": {
      "command": "sprrint",
      "args": ["mcp"],
      "env": {
        "SPRRINT_API_KEY": "spr_live_…"
      }
    }
  }
}
```

Or sign in with the CLI first and omit the env block — the server reads `~/.config/sprrint/config.toml`.

There is also a `sprrint-mcp` entry point if your client wants a dedicated binary.

## What it can do

Everything the Sprrint app can do:

| Area | Commands / tools |
|---|---|
| You | login, whoami, me update, emails, keys |
| Workspaces | list, create, use (`config set workspace`) |
| Workspace | get, update, invite, roles, leave, delete |
| Projects | list, create, update, archive, restore, delete, members |
| Now / Home | `now`, `overview`, project home |
| Tasks | list, get, create, update, move, comment, attach (subtasks, blocked notes) |
| Sprints | list, get, create, update, start, pause, complete, delete |
| Releases | list, get, create, update (task membership; optional sprint expand) |
| Black Hole | list, pull, drop |
| Search / Activity | `search`, `activity` |
| Categories / files | categories, `files` |

The web app, CLI, and MCP share `/api/v1` and the same permissions.

## Stickman

TTY sessions show a small stick figure while work is in flight — walking, waving, pulling from the void, arms up when it lands. `--plain` or a pipe turns that off.
