"""Regression test for change_guard.py, run against a throwaway project root with fake approval files.

Usage: python3 .claude/hooks/test_change_guard.py
"""
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOOK = str(Path(__file__).with_name("change_guard.py"))
INV = ("python3 -c \"import sqlite3;c=sqlite3.connect('inventory/inventory.db');"
       "c.execute('UPDATE devices SET notes=1');c.commit()\"")


def run(root, tool, tin):
    p = subprocess.run([sys.executable, HOOK], input=json.dumps({"tool_name": tool, "tool_input": tin, "cwd": str(root)}),
                       capture_output=True, text=True, env={"CLAUDE_PROJECT_DIR": str(root), "PATH": "/usr/bin:/bin"})
    return "ALLOW" if p.returncode == 0 else "BLOCK"


def approve(root, name, age_min=0, status="approved"):
    d = root / ".claude" / "approvals"
    d.mkdir(parents=True, exist_ok=True)
    t = (datetime.now(timezone.utc) - timedelta(minutes=age_min)).isoformat(timespec="seconds")
    (d / f"{name}.json").write_text(json.dumps({"id": name, "status": status, "approved_at": t}))


def main():
    cases = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cases.append(("inventory write, no INV-EDIT", run(root, "Bash", {"command": INV}), "BLOCK"))
        approve(root, "INV-EDIT", age_min=20)
        cases.append(("inventory write, INV-EDIT expired (20 min)", run(root, "Bash", {"command": INV}), "BLOCK"))
        approve(root, "INV-EDIT", status="rejected")
        cases.append(("inventory write, INV-EDIT rejected", run(root, "Bash", {"command": INV}), "BLOCK"))
        approve(root, "INV-EDIT")
        cases += [
            ("inventory write, INV-EDIT valid", run(root, "Bash", {"command": INV}), "ALLOW"),
            ("inventory write in a .py file, INV-EDIT valid",
             run(root, "Write", {"file_path": str(root / "x.py"), "content": INV}), "ALLOW"),
            ("commit + netmiko import",
             run(root, "Bash", {"command": INV.replace("import sqlite3", "import sqlite3,netmiko")}), "BLOCK"),
            ("commit + urllib", run(root, "Bash", {"command": INV.replace("import sqlite3", "import sqlite3,urllib")}), "BLOCK"),
            ("commit on another DB", run(root, "Bash", {"command": INV.replace("inventory/inventory.db", "other.db")}), "BLOCK"),
            ("inventory write + send_config_set",
             run(root, "Bash", {"command": INV.replace("UPDATE", "send_config_set UPDATE")}), "BLOCK"),
            ("plain send_config_set", run(root, "Bash", {"command": "python3 -c 'conn.send_config_set([1])'"}), "BLOCK"),
            ("curl POST", run(root, "Bash", {"command": "curl -k -X POST https://10.0.0.1/api"}), "BLOCK"),
            ("read-only inventory query", run(root, "Bash", {"command": "python3 scripts/inventory.py list"}), "ALLOW"),
            ("edit protected hook, INV-EDIT only",
             run(root, "Edit", {"file_path": str(root / ".claude/hooks/change_guard.py"), "new_string": "x"}), "BLOCK"),
        ]
    capture = str(Path(__file__).with_name("approval_capture.py"))
    for prompt, want in [("APPROVE INV-EDIT", "approved"), ("REJECT INV-EDIT", "rejected"),
                         ("approve inv-edit please", "none")]:
        with tempfile.TemporaryDirectory() as td:
            subprocess.run([sys.executable, capture], input=json.dumps({"prompt": prompt, "cwd": td}),
                           capture_output=True, text=True, env={"CLAUDE_PROJECT_DIR": td, "PATH": "/usr/bin:/bin"})
            f = Path(td) / ".claude" / "approvals" / "INV-EDIT.json"
            got = json.loads(f.read_text())["status"] if f.exists() else "none"
        cases.append((f"capture {prompt!r}", got, want))
    bad = 0
    for name, got, want in cases:
        ok = got == want
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {got:5}  {name}")
    print(f"{len(cases) - bad}/{len(cases)} passed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
