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
        # change-guard copies in other repos: locked without GUARD-EDIT, editable with it
        other = Path(td) / "other-repo" / "hooks" / "change_guard.py"
        cases.append(("other repo's guard file, no GUARD-EDIT",
                      run(root, "Edit", {"file_path": str(other), "new_string": "x = 1"}), "BLOCK"))
        approve(root, "GUARD-EDIT")
        cases.append(("other repo's guard file, GUARD-EDIT valid",
                      run(root, "Edit", {"file_path": str(other), "new_string": "PUSH = ['send_config_set']"}), "ALLOW"))
        cases.append(("other repo's normal file still content-checked",
                      run(root, "Write", {"file_path": str(other.parent.parent / "x.py"), "content": "c.send_config_set(x)"}),
                      "BLOCK"))
        (root / ".claude" / "approvals" / "GUARD-EDIT.json").unlink()
        # remote-shell tools: blocked when used, allowed when only named
        py = str(root / "x.py")
        for name, tool, tin, want in [
            ("bash: telnet <ip>", "Bash", {"command": "telnet 10.0.0.1 23"}, "BLOCK"),
            ("bash: chained telnet", "Bash", {"command": "ls; telnet 10.0.0.1"}, "BLOCK"),
            ("bash: piped plink", "Bash", {"command": "echo y | plink -ssh admin@10.0.0.1"}, "BLOCK"),
            ("bash: sudo -u x telnet", "Bash", {"command": "sudo -u x telnet sw1"}, "BLOCK"),
            ("bash: timeout 5 /usr/bin/telnet", "Bash", {"command": "timeout 5 /usr/bin/telnet sw1"}, "BLOCK"),
            ("bash: sshpass", "Bash", {"command": "sshpass -p x ssh admin@sw1"}, "BLOCK"),
            ("bash: bash -c 'telnet'", "Bash", {"command": "bash -c 'telnet 10.0.0.1'"}, "BLOCK"),
            ("bash: $(telnet)", "Bash", {"command": "x=$(telnet sw1)"}, "BLOCK"),
            ("bash: python telnetlib", "Bash", {"command": "python3 -c 'import telnetlib'"}, "BLOCK"),
            ("bash: heredoc line telnet", "Bash", {"command": "cat > a.sh <<EOF\ntelnet 10.0.0.1\nEOF"}, "BLOCK"),
            ("file: import telnetlib", "Write", {"file_path": py, "content": "import telnetlib\n"}, "BLOCK"),
            ("file: netmiko cisco_ios_telnet", "Write", {"file_path": py, "content": "d = {'device_type': 'cisco_ios_telnet'}"}, "BLOCK"),
            ("file: subprocess argv", "Write", {"file_path": py, "content": "subprocess.run(['telnet', host])"}, "BLOCK"),
            ("file: os.system string", "Write", {"file_path": py, "content": "os.system('telnet 10.0.0.1')"}, "BLOCK"),
            ("file: f-string command", "Write", {"file_path": py, "content": "cmd = f\"telnet {host}\""}, "BLOCK"),
            ("file: .sh line", "Write", {"file_path": str(root / "a.sh"), "content": "#!/bin/sh\ntelnet 10.0.0.1\n"}, "BLOCK"),
            ("file: check title naming telnet", "Write",
             {"file_path": py, "content": "TITLE = 'Risky services (SMBv1, RDP without NLA, telnet, ftp)'\n"}, "ALLOW"),
            ("file: regex alternation", "Write",
             {"file_path": py, "content": "RISKY_RE = re.compile(r'(ftp|telnet|rsh)')\nPORTS = {21: 'ftp', 23: 'telnet'}\n"},
             "ALLOW"),
            ("file: shell=True string w/ chain", "Write",
             {"file_path": py, "content": "subprocess.run('ls; telnet 10.0.0.1', shell=True)"}, "BLOCK"),
            ("file: telnet user@host string", "Write", {"file_path": py, "content": "c = 'plink admin@sw1'"}, "BLOCK"),
            ("file: extensionless script line", "Write",
             {"file_path": str(root / "bin/connect"), "content": "#!/bin/sh\nexec telnet sw1\n"}, "BLOCK"),
            # IOS command words: blocked as commands, allowed when only parsed or named
            ("file: send_command('reload')", "Write", {"file_path": py, "content": "conn.send_command('reload')"}, "BLOCK"),
            ("file: no shutdown in a command list", "Write",
             {"file_path": py, "content": "cmds = ['interface Gi1/0/1', 'no shutdown']"}, "BLOCK"),
            ("file: ' shutdown' literal", "Write", {"file_path": py, "content": "cmds.append(' shutdown')"}, "BLOCK"),
            ("file: conf t via timing", "Write", {"file_path": py, "content": "c.send_command_timing(\"conf t\")"}, "BLOCK"),
            ("file: f-string reload in", "Write", {"file_path": py, "content": "x = f\"reload in {m}\""}, "BLOCK"),
            ("file: wr mem literal", "Write", {"file_path": py, "content": "c.send_command('write memory')"}, "BLOCK"),
            ("file: reload-reason title + regex", "Write",
             {"file_path": py, "content": "TITLE = 'Uptime; last reload reason'\nRE = re.compile(r'Last reload reason: (.+)')\n"},
             "ALLOW"),
            ("file: env-state regex with shutdown", "Write",
             {"file_path": py, "content": "BAD = re.compile(r'(shutdown|critical|faulty)', re.I)  # PSU shutdown state\n"},
             "ALLOW"),
            ("file: show reload literal", "Write", {"file_path": py, "content": "conn.send_command('show reload')"}, "ALLOW"),
            ("bash: reload still blocked", "Bash", {"command": "echo reload | python3 x.py"}, "BLOCK"),
            ("file: .sh shutdown", "Write", {"file_path": str(root / "a.sh"), "content": "printf 'shutdown\\n'\n"}, "BLOCK"),
            ("file: port map + comment", "Write",
             {"file_path": py, "content": "RISKY = {'telnet': 23, 'ftp': 21}  # flag telnet listening\n"}, "ALLOW"),
            ("bash: grep for telnet", "Bash", {"command": "grep -n \"telnet\" scripts/guest_show.py"}, "ALLOW"),
            ("bash: ss filter port 23", "Bash", {"command": "python3 scripts/guest_show.py --grep 'telnet|:23 ' --all"}, "ALLOW"),
        ]:
            cases.append((name, run(root, tool, tin), want))
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
