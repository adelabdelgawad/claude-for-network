# Setup

## Requirements

- Linux or macOS with Python 3.11+ (developed on 3.13)
- [`uv`](https://docs.astral.sh/uv/) to create the virtual environment
- [Claude Code](https://claude.com/claude-code)
- SSH reachability from this host to the management IPs of your devices

## 1. Python environment

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

Always run the scripts with `.venv/bin/python`.

> **Keep `paramiko` below 4.** Older Cisco switches (2960 / 2960+ / 2960L on IOS 12.2–15.x)
> only offer `diffie-hellman-group1-sha1`, which paramiko 4+ removed.

## 2. Credentials

```bash
cp .env.example .env
chmod 600 .env
```

Fill in the credential sets you need. Each device row has a `credential_ref`; the scripts read
`NET_<REF>_USERNAME`, `NET_<REF>_PASSWORD` and `NET_<REF>_ENABLE` from `.env`.

| `credential_ref` | Used for |
|---|---|
| `DEFAULT` | Switches and routers (default for new devices) |
| `SOPHOS` / `SOPHOSAPI` | Sophos XG SSH console / XML API (Get-only) |
| `VCENTER` / `ESXI` | vSphere (use a read-only role) |
| `WINDOWS` / `LINUX` | Guest operating systems (WinRM / SSH) |

Hosts and IPs go in the inventory, never in `.env`.

## 3. Inventory

Create an empty database from the schema:

```bash
python3 -c "import sqlite3;c=sqlite3.connect('inventory/inventory.db');c.executescript(open('inventory/schema.sql').read())"
```

Then discover devices (read-only: SSH port sweep plus `show version`):

```bash
.venv/bin/python scripts/discover.py 192.0.2.0/24 --cred DEFAULT
.venv/bin/python scripts/inventory.py counts
```

Devices that answer SSH but reject the credentials are stored as `auth_failed`; give them a
different `credential_ref` and rerun discovery for their IPs.

## 4. Site context for Claude (optional)

Put site-specific facts — known subnets, core switch names, naming conventions — in
`CLAUDE.local.md`. Claude Code loads it alongside `CLAUDE.md`, and it is gitignored, so your
network details stay out of the repository.

## 5. Start Claude Code

```bash
claude
```

Run `/model opus` for the lead session (see *Model roles* in `CLAUDE.md`). The approval hooks in
`.claude/settings.json` load automatically; confirm with `/hooks`.

Next: [change workflow](change-workflow.md) · [scripts](scripts.md)
