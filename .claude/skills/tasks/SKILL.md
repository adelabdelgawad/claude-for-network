---
name: tasks
description: Use when the user asks for their tasks, to-do list, findings, open issues, "what's left", "what needs fixing", progress on findings, or wants to add, start, block, assign, close or re-check a task — and after any audit or report run whose findings should become tracked tasks.
---

# Task list

## Overview

Findings and follow-up work live in the `tasks` table of `inventory/inventory.db`, managed by `scripts/tasks.py`. Each task has a severity (`crit`/`warn`/`info`), a category, a status (`todo` → `in_progress` / `blocked` → `done` / `wontfix`), the object it concerns, a suggested action, and `needs_change` (1 = doing it modifies a device or VM).

## Quick reference

```bash
.venv/bin/python scripts/tasks.py list                     # open tasks, grouped checklist
.venv/bin/python scripts/tasks.py list --category storage --severity crit
.venv/bin/python scripts/tasks.py list --md                # markdown checklist (paste into Teams/email)
.venv/bin/python scripts/tasks.py list --status all --brief
.venv/bin/python scripts/tasks.py summary                  # counts only
.venv/bin/python scripts/tasks.py show 12
.venv/bin/python scripts/tasks.py start 12 | done 12 --note "extended C: to 150 GB" | block 12 --note "waiting for vendor"
.venv/bin/python scripts/tasks.py add "Replace PSU on core switch" --category network --severity warn --object core-sw-01

# refresh from findings (dedupes, reopens, auto-resolves what disappeared)
.venv/bin/python scripts/vsphere.py discover && .venv/bin/python scripts/tasks.py import vmtools
.venv/bin/python scripts/vsphere_storage.py  && .venv/bin/python scripts/tasks.py import storage
```

## How to present tasks to the user

- When the user asks for tasks or findings, run `tasks.py list` (with filters if they named a category, severity or machine) and show the output as a checklist. Lead with the counts by severity, then the items. Run `list --md` when they want something to paste or share.
- Before showing tasks, offer to refresh them: re-run the source report and its import so the list isn't stale. Say when the data was last imported.
- Never change a task's status unless the user says so, or a re-import shows the finding is gone (auto-resolved). Tell the user what changed.

## Doing a task

- `needs_change = 1` means that carrying the task out (upgrading VMware Tools, extending a disk, removing a snapshot, cleaning up a guest, any config) is a **change** under the CRITICAL rules in CLAUDE.md, so it needs the user's `APPROVE <CHG-ID>`. vSphere and guest changes have **no `change.py` backend yet**. For those, give the user the exact steps to run themselves, then mark the task `done` once they confirm.
- Investigation tasks (read-only) can be worked directly: use `vsphere`, `network-show-collect` or `guest_show.py`, and put the findings in `--note`.
