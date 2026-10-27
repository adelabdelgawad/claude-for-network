#!/usr/bin/env python3
"""UserPromptSubmit hook: record explicit user approvals typed as `APPROVE <ID>` / `REJECT <ID>`.

Only the user's own prompt reaches this hook, so approval files cannot be created by Claude.
Always exits 0 and never blocks the prompt.
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

LINE = re.compile(r"^\s*(APPROVE|REJECT)\s+(CHG-[0-9]{8}-[0-9]{6}-[0-9a-f]{4}|GUARD-EDIT)\s*$")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main():
    try:
        data = json.load(sys.stdin)
        prompt = data.get("prompt") or ""
        root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or ".")
        session = data.get("session_id")
    except Exception:  # noqa: BLE001 - never block the prompt
        return
    adir = root / ".claude" / "approvals"
    for line in prompt.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        verb, cid = m.groups()
        try:
            adir.mkdir(parents=True, exist_ok=True)
            if cid == "GUARD-EDIT":
                if verb == "APPROVE":
                    (adir / "GUARD-EDIT.json").write_text(
                        json.dumps({"id": cid, "status": "approved", "approved_at": now()}, indent=2))
                    print("[approval-gate] User APPROVED GUARD-EDIT: protected guard files may be edited "
                          "for 15 minutes (multi-use).")
                else:
                    (adir / "GUARD-EDIT.json").write_text(json.dumps({"id": cid, "status": "rejected"}))
                    print("[approval-gate] GUARD-EDIT rejected; protected files stay locked.")
                continue
            plan = root / "changes" / cid / "plan.json"
            if verb == "REJECT":
                (adir / f"{cid}.json").write_text(json.dumps(
                    {"id": cid, "status": "rejected", "rejected_at": now(), "session_id": session}, indent=2))
                print(f"[approval-gate] User REJECTED {cid}. Do NOT apply it.")
            elif not plan.is_file():
                print(f"[approval-gate] APPROVE {cid} ignored: no such plan")
            else:
                digest = hashlib.sha256(plan.read_bytes()).hexdigest()
                (adir / f"{cid}.json").write_text(json.dumps({
                    "id": cid, "status": "approved", "plan_sha256": digest, "approved_at": now(),
                    "session_id": session, "consumed": False}, indent=2, sort_keys=True))
                print(f"[approval-gate] User APPROVED {cid} (plan sha256 {digest[:12]}). Valid 60 min, "
                      f"single use. Run: .venv/bin/python scripts/change.py apply {cid}")
        except OSError:
            print(f"[approval-gate] could not record {verb} {cid}")


if __name__ == "__main__":
    try:
        main()
    finally:
        sys.exit(0)
