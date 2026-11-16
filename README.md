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

Sprrint emails a 6-digit code. After it checks out, the CLI stores an API key in `~/.config/sprrint/config.toml` (mode `600`). The CLI always talks to `https://sprrint.run`. Agents use `https://mcp.sprrint.run/mcp`.

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

Agents connect at `https://mcp.sprrint.run/mcp`. Send the key on every request. No local install.

```json
{
  "mcpServers": {
    "sprrint": {
      "url": "https://mcp.sprrint.run/mcp",
      "headers": {
        "Authorization": "Bearer spr_live_…"
      }
    }
  }
}
```

`sprrint mcp` (and the `sprrint-mcp` entry point) still runs a local stdio server for clients that cannot open a URL. It reads `SPRRINT_API_KEY` or `~/.config/sprrint/config.toml`.

## What it can do

Everything the Sprrint app can do:

| Area | Commands / tools |
|---|---|
| You | login, whoami, me update, emails, keys |
| Workspaces | list, create, use (`config set workspace`) |
| Workspace | get, update, invite, roles, leave, delete |
| Projects | list, create, update, archive, restore, delete, members |
| Now / Home | `now`, `overview`, project home |
| Tasks | list, get, create, update, move, comment, attach, git-link / git-unlink (subtasks, blocked notes) |
| Description files | `sprrint_files_upload` (base64), then `![name](media:id)` or `[name](media:id)` in the description |
| Comment files | `sprrint_files_upload`, then `file_ids` on `sprrint_tasks_comment`. Markdown in the comment body is attached too |
| Sprints | list, get, create, update, start, pause, complete, delete |
| Releases | list, get, create, update (task membership; optional sprint expand) |
| Black Hole | list, pull, drop |
| Search / Activity | `search`, `activity` |
| Categories / files | categories, `files` |

The web app, CLI, and MCP share `/api/v1` and the same permissions.

## Stickman

TTY sessions show a small stick figure while work is in flight — walking, waving, pulling from the void, arms up when it lands. `--plain` or a pipe turns that off.

### QA workflow

Use `sprrint tasks qa KEY ACTION` to record QA handoffs, findings, fixes, and results. Each `submit` creates a numbered round; the QA owner starts testing and records the verdict. Findings remain linked to engineer responses and later verification.

```sh
sprrint tasks qa BR-12 configure --owner 7
sprrint tasks qa BR-12 submit --body "Ready to test"
sprrint tasks qa BR-12 start
sprrint tasks qa BR-12 finding --body "Password error is missing"
sprrint tasks qa BR-12 fail --body "Password validation fails"
sprrint tasks list --sprint all --status qa_failed
sprrint tasks qa BR-12 fix --finding 8 --body "Added error handling"
sprrint tasks qa BR-12 submit --body "Fixed; ready for retest"
sprrint tasks qa BR-12 start
sprrint tasks qa BR-12 verify --finding 8 --body "Verified error feedback"
sprrint tasks qa BR-12 pass --body "All checks passed"
sprrint tasks get BR-12 --json
```

`--finding` takes the database finding ID returned in `qa.findings`; `--owner` takes a workspace user ID. Use `note` anytime, `reply` for discussion, and `reopen` for a finding that still fails testing. `--file-ids` attaches existing project files. `projects update BR --qa-required` sets the default for new tasks; `--no-qa-required` clears it. Before any round or finding exists, `tasks qa BR-12 disable` makes an individual task exempt.

The local MCP server exposes `sprrint_tasks_qa` with the same actions, plus `owner_id`, `finding_id`, `body`, `file_ids`, `project`, and `workspace`. Task reads include the complete QA history. Use `sprrint_tasks_list(status="qa_failed", sprint="all")` to find failed tasks. General moves cannot bypass required QA.
