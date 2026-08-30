# Sprrint CLI + MCP

The same Sprrint product, from a terminal or an agent.

People who never open the web app can still run the board, write tasks, move cards, run sprints, pull work out of the Black Hole, comment, invite teammates, and manage the workspace.

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

You need a Sprrint site (your team’s instance) and an account.

## Sign in

```bash
sprrint login --url https://your-sprrint.example
```

Sprrint emails a 6-digit code. After it checks out, the CLI stores an API key in `~/.config/sprrint/config.toml` (mode `600`).

You can also mint a key in the web app: **You → Keys**, then:

```bash
sprrint config set api_url https://your-sprrint.example
sprrint config set api_key spr_live_…
sprrint config set project BR
```

Environment variables override the file: `SPRRINT_API_URL`, `SPRRINT_API_KEY`, `SPRRINT_PROJECT`.

## Everyday commands

```bash
sprrint whoami
sprrint now
sprrint overview
sprrint search "login"
sprrint tasks create --title "Ship the CLI"
sprrint tasks move BR-12 progress
sprrint tasks comment BR-12 "Landed."
sprrint sprints create --name "Launch Week" --starts-on 2026-09-01 --ends-on 2026-09-14
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
        "SPRRINT_API_URL": "https://your-sprrint.example",
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
| Workspace | get, update, invite, roles, leave, delete |
| Projects | list, create, update, archive, restore, delete, members |
| Now / Home | `now`, `overview`, project home |
| Tasks | list, get, create, update, move, comment, attach |
| Sprints | list, get, create, update, delete |
| Black Hole | list, pull, drop |
| Search / Activity | `search`, `activity` |
| Categories / files | categories, `files` |

The web app, CLI, and MCP share `/api/v1` and the same permissions.

## Stickman

TTY sessions show a small stick figure while work is in flight — walking, waving, pulling from the void, arms up when it lands. `--plain` or a pipe turns that off.
