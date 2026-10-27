# claude-for-network as a Claude Code plugin — design

Date: 2026-10-27 · Status: draft for review

## Intent

Turn this repo into a Claude Code plugin hosted on GitHub (`adelabdelgawad/claude-for-network`) so any team member can
install it once and then run `claude` in **any new directory**, type `setup claude for network here`, and get a ready site
workspace with its own inventory and `.env`. The repo becomes a **template / source only**: it holds code, skills,
hooks, schema and docs, and **never site data**.

Why: today the code and one site's data share a directory, so a second site means copying the repo and the data
risks being published. Separating "the tool" (plugin, shared, updated via plugin update) from "a site" (directory with
data) fixes both.

## Goals

1. Installable plugin from GitHub: `/plugin marketplace add adelabdelgawad/claude-for-network` then
   `/plugin install claude-for-network@<marketplace-name>`.
2. Typing `setup claude for network here` in a new directory scaffolds a site workspace — detected by a **UserPromptSubmit hook**.
3. All existing skills, scripts and the approval gate work unchanged from a site workspace.
4. One shared code copy: scripts run from the plugin install dir; data is read/written in the site directory.

## Non-goals

- Migrating this directory's current live data to a new workspace (user said not needed). It stays on disk,
  gitignored, untouched. Nothing is deleted.
- Per-site copies of the scripts.
- Publishing to the official Anthropic marketplace.
- Any change to device-facing behaviour of the scripts.

## Anti-goals (failure even if it "works")

- Any site data (DB, `.env`, backups, reports, approvals, `CLAUDE.local.md`, real hostnames/IPs) in the repo or pushed.
- The approval gate weakened or missing in a site workspace (hooks not active, or protected paths no longer protected).
- `setup claude for network here` overwriting an existing `.env`, `inventory.db`, `CLAUDE.md` or any other existing file.
- Site data ending up inside the plugin install/cache directory.

## Constraints

- CLAUDE.md CRITICAL rules apply. Editing `.claude/hooks/`, `.claude/settings*.json`, `scripts/change.py`,
  `scripts/netlib.py` needs the user to type `APPROVE GUARD-EDIT` (15-min window; may need re-approval during the build).
- `paramiko<4` pin stays.
- **Platforms: Linux and Windows** (decided by the user). All paths via `pathlib`; no bash-only code in hooks or the
  init script; venv interpreter resolved per OS (`.venv/bin/python` vs `.venv\Scripts\python.exe`); hook commands
  must work on both (Windows has `python`/`py`, often no `python3`); `.env` gets chmod 600 on Linux and an
  owner-only ACL (`icacls`) on Windows; guard/approval tests run on both path styles.
- **The GitHub repo is public** (decided by the user). The pre-push scan covers the full tracked tree *and git
  history*: credentials/tokens, private IPs (10/8, 172.16/12, 192.168/16) other than documentation ranges, real
  hostnames from the local inventory, site/company names and internal domains (e.g. the email domain). Examples in
  docs use RFC 5737 IPs (192.0.2.x) and placeholder names (`SW-ACCESS-01`). If history contains site data, the push
  is held and the user decides between rewriting history or starting a fresh repo.
- No commit or push without the user asking. Pushing to GitHub is outward-facing: confirm first, and run a
  secrets/IP scan of the tracked tree before the push.

## Decided

**Layout of the repo (plugin root):**

```
.claude-plugin/plugin.json          name: claude-for-network, version, description, author
.claude-plugin/marketplace.json     single-plugin marketplace, source "./"
skills/<existing 7>/SKILL.md        moved from .claude/skills/
skills/network-workspace-init/SKILL.md   new
hooks/hooks.json                    PreToolUse change_guard + UserPromptSubmit approval_capture + setup trigger
hooks/change_guard.py, approval_capture.py, test_change_guard.py
scripts/*.py                        unchanged role; root resolution changed (below)
scripts/init_workspace.py           new: idempotent scaffolder
inventory/schema.sql
templates/workspace/                CLAUDE.md, CLAUDE.local.md (blank), .gitignore, .env.example, .gitkeep tree
docs/                               updated: install, "setup claude for network here", workspace layout
requirements.txt, README.md, LICENSE
```

Repo-root `.gitkeep` data folders, `.claude/approvals/.gitkeep`, `.claude/settings.json` hooks and
`.claude/skills/` are removed from the tracked tree (they move into the plugin layout / workspace template).
The repo's own `CLAUDE.md` becomes developer guidance for working on the plugin; the site rules move to
`templates/workspace/CLAUDE.md`.

**Site workspace created by `setup claude for network here`:**

```
CLAUDE.md                 site copy of the CRITICAL rules + tools table (script paths via the plugin)
CLAUDE.local.md           blank site context (subnets, notes)
.env                      from .env.example, chmod 600 (only if absent)
.gitignore                same data rules as today
inventory/inventory.db    created from schema.sql (only if absent)
backups/ outputs/ reports/ audits/ changes/ .claude/approvals/
```

Idempotent: creates only what is missing, never overwrites, prints a created/skipped list.

**Trigger:** a UserPromptSubmit hook in the plugin matches the prompt `setup claude for network here` (case-insensitive,
whole prompt, minor variants like "set up claude for network here" allowed). It does not scaffold by itself; it injects
context telling Claude to use the `network-workspace-init` skill. The skill runs `init_workspace.py`, reports what
was created, sets up the shared venv if missing, and tells the user to fill in `.env` and `CLAUDE.local.md`, then
offers a first `discover.py`. *(My call: hook → skill → script, so the venv install and the explanation happen in
the session instead of inside a hook timeout.)*

**Root resolution:** scripts (via `netlib.py`, `vmlib.py`, and any script that uses `Path(__file__)` for data)
resolve the site root as `CLAUDE_PROJECT_DIR` → cwd — the same order in scripts, both hooks and `change.py`, so
approvals are always written and read in the same site. No separate `NETWORK_WORKSPACE` variable. *(My call.)* Data paths (`.env`, inventory DB,
backups, outputs, reports, audits, changes, approvals) use the site root; code paths (schema, templates) use the
plugin root. Scripts refuse to run when the site root has no `inventory/inventory.db`, with "run `setup claude for network here`
first", so data never lands in the plugin dir.

**Python env:** one shared venv in the plugin's persistent data dir (`${CLAUDE_PLUGIN_DATA}/.venv`), created with `uv`
from `requirements.txt` on first setup. *(My call, user did not object.)*

**Guard in the plugin:** `change_guard.py` keeps protecting the gate files at their plugin paths (hooks, `change.py`,
`netlib.py`, `hooks.json`) plus the site's `.claude/settings*.json` and `.claude/approvals/`. Approvals are stored
per site in `<site>/.claude/approvals/`. `test_change_guard.py` updated and passing.

**Site marker and hook scope** *(my calls)*: the init script writes a marker file `.claude-for-network` in the site
root. The guard, approval-capture and rules hooks act only in directories with that marker, so installing the plugin
at user scope does not block `reload`/`curl -X POST` in unrelated repos. Scripts refuse to run without the marker,
so there is no site without a gate.

**Gate always on in a site** *(my call)*: the init script writes `<site>/.claude/settings.json` declaring the GitHub
marketplace (`extraKnownMarketplaces`) and enabling the plugin (`enabledPlugins`), so opening a site prompts to
install/enable it. No extra fail-closed check in `change.py`: `apply` already needs an approval file that only the
plugin hook can create.

**Rules delivery** *(my call)*: the CRITICAL rules and tools table are injected by a plugin SessionStart hook in
marked sites, so they update with the plugin and an existing `CLAUDE.md` cannot hide them. The site `CLAUDE.md`
from the template is a short pointer (created only if absent); `CLAUDE.local.md` stays for site subnets.

**This directory** (decided by the user): the repo is template-only. Its current live data stays on disk, gitignored
and inert (no marker is written here). Before any push, real hostnames/IPs/site names are scrubbed from the tracked
skills and docs (e.g. real switch hostnames and management subnets in examples).

## Left to the builder

- How skills and docs refer to scripts (e.g. `${CLAUDE_PLUGIN_ROOT}` expansion in skills, a plugin `bin/` on PATH,
  or a path written into the site `CLAUDE.md` by the init script). Verify what Claude Code 2.1.x actually supports
  and pick the most robust option; check that the guard's `change.py` regex still matches the chosen invocation.
- Exact marketplace name and plugin version (start at 0.1.0).
- Wording of the site `CLAUDE.md` template.
- Whether this source repo keeps a `.claude/settings.json` that loads its own hooks for local development (it must
  not double-load them alongside the installed plugin).

## Done when

- `claude plugin validate` (or equivalent) passes; marketplace installs locally from the repo path.
- In an empty temp dir, `setup claude for network here` produces the workspace above; a second run changes nothing.
- `inventory.py counts` and `change.py list` run from that workspace against its empty DB; nothing is written to
  the plugin dir.
- Guard tests pass; a blocked change command is still blocked in the workspace.
- `git ls-files` contains no `.db`, `.env`, backups/reports content, or real IPs/hostnames.
