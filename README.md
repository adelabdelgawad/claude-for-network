# Claude for Network

An approval-gated workspace for running IT network operations with
[Claude Code](https://claude.com/claude-code). It covers device inventory, read-only `show`
collection, config backups, security and logging audits, and configuration changes across Cisco
switches, Sophos XG firewalls and VMware vSphere inventory.

Claude does the legwork: it finds targets, collects output from many devices at once, analyses
it, and drafts changes. **A human approves every change.** No command that modifies a device runs
until the user types `APPROVE <CHG-ID>` for that exact plan, and Claude Code hooks enforce this.

## Features

- **Inventory first.** A SQLite inventory is the source of truth for devices, credentials
  references, sites, firewalls and vSphere objects, populated by an SSH discovery sweep.
- **Concurrent, read-only collection.** One script call runs allowlisted `show` commands on
  dozens of switches in parallel and keeps raw output in files instead of the chat context.
- **Audits.** Security posture audit (SSH, SNMP, HTTP, VTP, Smart Install, DHCP snooping ...)
  and logging-coverage audit, with JSON/CSV/Markdown reports.
- **Approval-gated changes.** `plan → APPROVE → apply`, with hash-bound single-use approvals,
  automatic pre-change backups, verify commands, rollback files and a change log.
- **Guard hooks.** A `PreToolUse` hook blocks config commands, raw SSH and write API calls
  outside the change tool, and protects the gate's own files.
- **Claude skills.** Project skills teach Claude the change workflow, read-only collection,
  inventory lookups and multi-device fan-out.
- **Task list.** Audit findings become tracked tasks (severity, status, owner, due date,
  suggested fix) in the inventory DB. Re-importing a report removes duplicates, reopens findings that
  return, and auto-closes the ones that are fixed. Ask Claude "show my tasks" at any time.

## Quick start

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt

cp .env.example .env && chmod 600 .env         # fill in credentials
python3 -c "import sqlite3;c=sqlite3.connect('inventory/inventory.db');c.executescript(open('inventory/schema.sql').read())"

.venv/bin/python scripts/discover.py 192.0.2.0/24   # read-only sweep, fills the inventory
.venv/bin/python scripts/inventory.py counts

claude                                              # then: /model opus
```

Then ask Claude things like:

- "Which access switches are still running IOS 12.2?"
- "Back up the running config of every core switch."
- "Audit logging coverage across all active switches."
- "Set the NTP servers on all `SW-*` switches." → Claude plans the change and waits for
  `APPROVE <CHG-ID>`.
- "Show my open tasks" / "List the critical storage findings as a checklist" / "Mark task 12 done."

See [docs/setup.md](docs/setup.md) for the full setup.

## How a change works

```
1. Claude reads state         scripts/show.py, scripts/backup.py        (read-only)
2. Claude plans               scripts/change.py plan ...                → CHG-YYYYMMDD-HHMMSS-xxxx
3. Claude shows the plan      targets, commands, verify, rollback, save → and stops
4. You approve                APPROVE CHG-...                           (typed by you)
5. Claude applies             scripts/change.py apply CHG-...           backup → push → verify → log
```

Details: [docs/change-workflow.md](docs/change-workflow.md).

## Task list

Findings from audits and reports are tracked as tasks in `inventory/inventory.db` (`tasks` table):

```bash
.venv/bin/python scripts/tasks.py import storage     # from the newest reports/vsphere_storage/<ts>/
.venv/bin/python scripts/tasks.py import vmtools     # VMs with old / missing / stopped VMware Tools
.venv/bin/python scripts/tasks.py list               # open tasks as a checklist, grouped by category
.venv/bin/python scripts/tasks.py list --md          # markdown checklist to paste into Teams or email
.venv/bin/python scripts/tasks.py summary
.venv/bin/python scripts/tasks.py start 12 | done 12 --note "..." | block 12 --note "..."
```

`[ ]` todo · `[~]` in progress · `[!]` blocked · `[x]` done · `[-]` won't fix. Tasks marked
*needs approval* modify a device or VM when carried out, so they go through the approval gate.

Where the tasks live:

| Path | What it is |
|---|---|
| `inventory/inventory.db` → `tasks` table | Source of truth (gitignored) |
| `reports/tasks/TASKS.md` | Readable checklist of open and recently closed tasks, rewritten after every task update (gitignored) |
| `reports/tasks/tasks.csv` | All tasks for Excel (gitignored) |
| `reports/tasks/tasks.json` | All tasks, machine-readable (gitignored) |
| `scripts/tasks.py` | The CLI (`list`, `summary`, `show`, `add`, `start`, `done`, `block`, `set`, `import`, `export`) |
| `.claude/skills/tasks/SKILL.md` | Tells Claude how to show and update tasks when you ask |

## Project structure

```
.
├── CLAUDE.md                       # Instructions Claude Code loads every session (rules, tools, roles)
├── CLAUDE.local.md                 # (gitignored) site-specific subnets and hostnames
├── README.md
├── LICENSE
├── requirements.txt                # netmiko, paramiko<4, python-dotenv, pyvmomi, pywinrm
├── .env.example                    # Credential template → copy to .env (gitignored)
├── .gitignore
│
├── .claude/
│   ├── settings.json               # Registers the guard hooks
│   ├── hooks/
│   │   ├── change_guard.py         # PreToolUse: blocks device changes outside change.py
│   │   └── approval_capture.py     # UserPromptSubmit: records APPROVE / REJECT <ID>
│   ├── approvals/                  # (gitignored) approval records written by the hook
│   └── skills/
│       ├── network-change/         # plan → APPROVE → apply workflow
│       ├── network-show-collect/   # read-only show collection and backups
│       ├── network-inventory/      # inventory lookups and updates
│       ├── network-fanout/         # running one task across many devices
│       ├── vsphere/                # vCenter / ESXi / VM / guest OS work
│       └── tasks/                  # task list: list, import findings, track status
│
├── scripts/
│   ├── inventory.py                # Query devices, VMs, ESXi hosts, vCenters
│   ├── discover.py                 # SSH sweep + show version → inventory
│   ├── show.py                     # Parallel read-only commands
│   ├── backup.py                   # Running-config backups
│   ├── audit.py                    # Security audit
│   ├── log_audit.py                # Logging coverage / abnormal log audit
│   ├── change.py                   # plan / show / list / apply (the only change path)
│   ├── vsphere.py                  # vCenter discovery → inventory, read-only views
│   ├── vsphere_audit.py            # vSphere audit
│   ├── vsphere_storage.py          # Storage risk (datastores, guest volumes, snapshots)
│   ├── tasks.py                    # Task list: import findings, list, track status
│   ├── guest_show.py               # Read-only commands inside Linux/Windows VMs
│   ├── netlib.py                   # Shared targeting, credentials, read-only allowlist
│   └── vmlib.py                    # Read-only vSphere helpers
│
├── inventory/
│   ├── schema.sql                  # SQLite schema (network + vSphere tables)
│   └── inventory.db                # (gitignored) the live inventory
│
├── docs/
│   ├── setup.md                    # Installation and first run
│   ├── change-workflow.md          # The approval gate in detail
│   ├── scripts.md                  # Script reference
│   ├── inventory.md                # Database schema and conventions
│   └── security.md                 # Threat model and what never to commit
│
├── changes/                        # (gitignored) command files and CHG-*/plan.json, result.json
├── backups/                        # (gitignored) backups/<hostname>/<timestamp>.cfg
├── outputs/                        # (gitignored) show.py --out results
├── audits/                         # (gitignored) audit.py results
└── reports/                        # (gitignored) log_audit.py and other reports
```

## Model roles

The lead session runs on Opus: it plans, talks to you, and obtains approvals. It delegates
read-only scanning to Haiku subagents and script writing or applying approved changes to Sonnet
subagents. Subagents follow the same rules and can only apply a change ID you already approved.

## Safety

The guard is a pattern-based seatbelt, not a sandbox. Give the automation accounts least privilege
and review every plan before approving it. Read [docs/security.md](docs/security.md) before using
this on a production network, and before pushing a fork anywhere.

## Documentation

| Doc | Contents |
|---|---|
| [docs/setup.md](docs/setup.md) | Requirements, venv, credentials, inventory, first run |
| [docs/change-workflow.md](docs/change-workflow.md) | Approval gate, hooks, protected files |
| [docs/scripts.md](docs/scripts.md) | Every script and its options |
| [docs/inventory.md](docs/inventory.md) | Database tables and conventions |
| [docs/security.md](docs/security.md) | Defences, secrets, publishing checklist |

## License

[MIT](LICENSE)
