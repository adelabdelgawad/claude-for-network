---
name: network-inventory
description: Use when looking up which network devices exist, their IPs, models, OS versions, serials, roles, sites or status, choosing targets for a task, or recording newly learned device facts in inventory/inventory.db.
---

# Network Inventory

## Overview

`inventory/inventory.db` (SQLite) is the source of truth for devices; the schema is in CLAUDE.md. `scripts/inventory.py` is the read-only query tool. Use it before anything that touches devices.

## Quick reference

```bash
.venv/bin/python scripts/inventory.py list                       # all active
.venv/bin/python scripts/inventory.py list --match 'SW-*' --json
.venv/bin/python scripts/inventory.py list --status auth_failed
.venv/bin/python scripts/inventory.py list --status any
.venv/bin/python scripts/inventory.py get CORE-SW1              # or an IP
.venv/bin/python scripts/inventory.py counts                     # by status / model
```

## Updating inventory facts

Updating *inventory records* (OS version, serial, model, role, site, status, credential_ref) does **not** change a device, so it needs no `APPROVE`. Do it with a short `python3 -c "import sqlite3; ..."` UPDATE keyed by `hostname` or `mgmt_ip`, using parameterized queries, and tell the user what you changed.

- New or missing devices: `.venv/bin/python scripts/discover.py <ip|subnet> [--cred REF]`. Run it only when the user asks or when a device is missing; it upserts by `mgmt_ip`.
- `change_log` is written by `scripts/change.py apply`. Don't insert fake entries by hand.
- `status` values: `active` | `spare` | `decommissioned` | `auth_failed`.

## VMware vSphere (VMs, ESXi, vCenter)

- VMs and their guest OS go in `machines` (+ `machine_nics`), hypervisors in `esxi_hosts`, controllers in `vcenters`, and VM networks/VLANs in `port_groups`. Never put them in `devices`, because network scripts target every row in `devices`.
- Upsert VMs by `instance_uuid` and ESXi hosts by `hostname`. Set `os_family` (`windows`/`linux`/`other`), `mgmt_protocol` and `credential_ref` (`WINDOWS`/`LINUX`).
- To check which switch port or VLAN a VM uses, join `machine_nics.mac` against the switches' `show mac address-table` output and `port_groups.vlan_id`.

## Choosing targets for bulk work

Pick targets with selectors (`--match`, `--role`, `--all`) and give them to a single concurrent script call (`network-fanout` skill), not a per-device loop.

## Common mistakes

- Rescanning the known subnets to "refresh" the device list. Query the DB instead.
- Targeting non-`active` devices without being asked.
- Changing `status`/`credential_ref` to make a failing device "work" without telling the user.
