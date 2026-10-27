---
name: checklist
description: Use when the user says "check <system>" — "check vsphere X", "check vcenter X", "check switches", "check switch X", "check core", "check sophos X", "check firewall X", "check veeam", "check everything" — or asks for a "checklist", "health check", "check list", "run the checks" or "is everything OK" on a device type or system — vSphere/vCenter/ESXi/VMs, and later switches, firewalls or Veeam — or wants to add, change or approve checklist items or thresholds for a device type.
---

# Device-type checklists

## Overview

A checklist is a fixed, user-approved list of read-only checks per device type. Every item is reported every run as ✅ pass / ⚠️ warn / ❌ crit / ℹ️ info / ➖ skip (with the reason), so a passing item is visible too, not just findings. Item IDs (`C11`, `E27`, ...) are stable; the approved lists live next to this file:

| Device type | Items | Runner |
|---|---|---|
| vSphere (vCenter, clusters, ESXi, datastores, VMs, guest OS, backup coverage) | [`vsphere.md`](vsphere.md) (approved 2026-10-27) | `scripts/vsphere_checklist.py` (+ `scripts/guest_security.py` for E2) |
| Cisco switches / routers | [`switch.md`](switch.md) (approved 2026-10-27) | `scripts/switch_checklist.py` |
| Sophos XG firewalls | [`sophos.md`](sophos.md) (approved 2026-10-27) | `scripts/sophos_checklist.py` |
| Veeam Backup & Replication | [`veeam.md`](veeam.md) (approved 2026-10-27) | `scripts/veeam_checklist.py` |

**Triggers → runner** (run it, no questions first; resolve the name against the inventory, list candidates if it matches nothing):

| User says | Runs |
|---|---|
| "check vsphere X", "check vcenter X" | `vsphere_checklist.py --vcenter X` (+ E2) |
| "check switches", "check switch X", "check core", "check routers" | `switch_checklist.py` with `X` / `--match` / `--role` / `--all` |
| "check sophos X", "check firewall X" | `sophos_checklist.py X` (or `--all`) |
| "check veeam" | `veeam_checklist.py --host <veeam host from CLAUDE.local.md>` |
| "check everything" | all four, one after another; one combined summary |

All runners share the CLI shape `[targets] [--out DIR] [--workers N]` and write `reports/checklist/<type>/<ts>/` (`checklist.md`, `summary.json`, `findings.csv`, `raw/`).

## Running the vSphere checklist

**"check vsphere X" means: run this full checklist for vCenter X** (no questions first). Resolve X against `scripts/inventory.py vcenters` (name, host or a unique prefix, e.g. `vc01` → `vc01-vcsa`); "check vsphere" with no name or "all" → every active vCenter. If X matches nothing, list the vCenters and ask. Scope E2 (`guest_security.py`) to that vCenter's VMs.

```bash
# E2 (in-guest OS security) — only when NET_WINDOWS_* / NET_LINUX_* are set in .env
.venv/bin/python scripts/guest_security.py --all --workers 16
# everything else; merges the newest guest_security run (<24h) automatically
.venv/bin/python scripts/vsphere_checklist.py --veeam-host <veeam host from CLAUDE.local.md>
.venv/bin/python scripts/vsphere_checklist.py --vcenter vc01-vcsa     # one vCenter
```

Output: `reports/checklist/vsphere/<ts>/` — `checklist.md` (full checklist), `summary.json` (`items[]` with `id`, `status`, `findings[]`), `findings.csv`, `raw/`.

1. Check credential sets first (`dotenv_values`, print only `set`/`EMPTY`): `VCENTER` (or the vCenter's `credential_ref`), `WINDOWS`/`LINUX` for E2, `VEEAM` for H. Missing ones make their items ➖ skip; say which and why rather than failing.
2. Run each script once (they are concurrent internally) with the console summary only; never paste raw output.
3. Present to the user from `summary.json` (parse with Python): totals per status, then the checklist grouped by section — every item on one line with its icon and finding count — and under each ❌/⚠️ item the top findings (target, detail). Point to `checklist.md` for the full tables.
4. Offer to track ❌/⚠️ findings in the task list (`tasks` skill).

The data is collected live, so no inventory-freshness question is needed.

## Changing a checklist

- **Never add, drop or re-threshold items on your own.** List the proposed items (ID, title, thresholds) and get the user's approval first; then update the item file here and the runner script together, and the date in the table above.
- A new device type: draft its item list in `<type>.md`, get approval, then build a read-only runner that writes the same `summary.json` item schema (see `vsphere.md`).
- Every check is read-only. Remediation of a finding is a **change** under the CRITICAL rules in CLAUDE.md (`network-change` skill; vSphere/guest changes have no `change.py` backend — give the user the steps).
