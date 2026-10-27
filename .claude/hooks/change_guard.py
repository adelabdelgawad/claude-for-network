#!/usr/bin/env python3
"""PreToolUse hook: block device-changing actions and edits to the guard itself.

Device changes must go through scripts/change.py plan -> user types APPROVE <ID> -> scripts/change.py apply <ID>.
Deny = message on stderr + exit 2. Anything else exits 0 silently.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOLS = {"Bash", "Write", "Edit", "MultiEdit", "NotebookEdit"}
PROTECTED = [".claude/hooks/", ".claude/settings.json", ".claude/settings.local.json",
             ".claude/approvals/", "scripts/change.py", "scripts/netlib.py"]
WRITEISH = ["sed -i", "perl -i", "tee", "cp ", "mv ", "rm ", "truncate", "chmod", "chown", "ln ",
            "install ", "dd ", "open(", "write_text", "unlink"]
DEVICE_PATTERNS = [re.compile(p, re.I) for p in [
    r"send_config_set", r"send_config_from_file", r"save_config", r"write_channel", r"\.commit\s*\(",
    r"\bconf(ig(ure)?)?\s+t(erm(inal)?)?\b", r"\bwr(ite)?\s+mem(ory)?\b", r"\bwrite\s+erase\b",
    r"\bcopy\s+run(ning-config)?\s+start(up-config)?\b", r"(?<!show )\breload\b",
    r"\bno\s+shut(down)?\b", r"\bshutdown\b", r"\berase\s+(startup|nvram|flash)",
    r"\b(sshpass|telnet|plink)\b", r"\bssh\s+\S*@?\d+\.\d+\.\d+\.\d+",
    r"\b(curl|wget|http|https|httpie)\b.*(-X\s*(POST|PUT|PATCH|DELETE)|--data|\s-d\s|--request\s+(POST|PUT|PATCH|DELETE))",
    r"postman\s+request\b.*\b(POST|PUT|PATCH|DELETE)\b",
]]
COMMIT = r"\.commit\s*\("
INV_DB = "inventory/inventory.db"
DEVICE_IO = re.compile(r"netmiko|ConnectHandler|paramiko|\bssh\b|urllib|requests|https?:|curl|wget|socket|telnetlib",
                       re.I)
SINGLE_CHANGE = re.compile(r"^\s*(\S*python3?\s+)?\S*scripts/change\.py\s+(plan|show|list|apply)\b")
CHAINERS = [";", "&&", "||", "|", "`", "$(", "\n"]
NOISE = ["2>&1", ">&2", "2>/dev/null", ">/dev/null"]
DATA_EXT = (".py", ".sh", ".bash", ".pl", ".rb", ".js")

HOW = ("Device changes go only through `scripts/change.py plan` -> the user types `APPROVE <ID>` -> "
       "`scripts/change.py apply <ID>`. Do not try to work around this hook.")


def deny(reason):
    print(f"[change-guard] BLOCKED: {reason} {HOW}", file=sys.stderr)
    sys.exit(2)


def approval_valid(root, name):
    """True if the user typed `APPROVE <name>` (GUARD-EDIT / INV-EDIT) within the last 15 minutes."""
    try:
        d = json.loads((root / ".claude" / "approvals" / f"{name}.json").read_text())
        age = datetime.now(timezone.utc) - datetime.fromisoformat(d["approved_at"])
        return d.get("status") == "approved" and age.total_seconds() < 15 * 60
    except Exception:  # noqa: BLE001
        return False


def guard_edit_valid(root):
    return approval_valid(root, "GUARD-EDIT")


def inventory_write(text):
    """A local inventory DB write: `.commit(` is the only device pattern hit, and nothing can reach a device."""
    hits = [p.pattern for p in DEVICE_PATTERNS if p.search(text)]
    return hits == [COMMIT] and INV_DB in text and not DEVICE_IO.search(text)


def rel_to_root(path, root, cwd):
    p = Path(path)
    if not p.is_absolute():
        p = cwd / p
    try:
        return os.path.normpath(p).replace(os.sep, "/"), os.path.relpath(os.path.normpath(p), root).replace(os.sep, "/")
    except ValueError:
        return str(p), str(p)


def is_protected(rel):
    for pr in PROTECTED:
        if pr.endswith("/"):
            if rel == pr[:-1] or rel.startswith(pr):
                return pr
        elif rel == pr:
            return pr
    return None


def contents(tool_input):
    out = [tool_input.get(k) for k in ("content", "new_string", "new_source")]
    out += [e.get("new_string") for e in tool_input.get("edits") or [] if isinstance(e, dict)]
    return [c for c in out if isinstance(c, str)]


def check_patterns(text, root):
    if inventory_write(text):
        if approval_valid(root, "INV-EDIT"):
            return
        deny("local inventory DB write needs the user to type `APPROVE INV-EDIT` (valid 15 min).")
    for pat in DEVICE_PATTERNS:
        if pat.search(text):
            deny(f"device-changing pattern /{pat.pattern}/ detected.")


def handle_file_tool(tool_input, root, cwd):
    path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not path:
        return
    absn, rel = rel_to_root(path, root, cwd)
    prot = is_protected(rel)
    if prot:
        if prot == ".claude/approvals/":
            deny("approval files are written only by the user's APPROVE prompt.")
        if not guard_edit_valid(root):
            deny(f"{rel} is a protected guard file (the user must type `APPROVE GUARD-EDIT` to unlock for 15 min).")
        return
    if rel.endswith(".md"):
        return
    if rel.startswith("changes/") and not rel.endswith(DATA_EXT):
        return
    for text in contents(tool_input):
        check_patterns(text, root)


def handle_bash(cmd, root):
    stripped = cmd
    for n in NOISE:
        stripped = stripped.replace(n, "")
    if ".claude/approvals" in cmd or "approvals/" in cmd:
        deny("the approvals directory may not be touched from Bash.")
    hit = [p for p in PROTECTED if p.rstrip("/") in cmd]
    if hit and not guard_edit_valid(root):
        low = stripped
        if ">" in low or any(t in low for t in WRITEISH):
            deny(f"command appears to modify protected file(s) {hit} (user must type `APPROVE GUARD-EDIT`).")
    if SINGLE_CHANGE.match(cmd):
        rest = cmd.replace("2>&1", "")
        if not any(c in rest for c in CHAINERS):
            return
    if re.search(r"scripts/change\.py\s+apply\b", cmd) and not re.match(r"^\s*(cat|less|grep|head|tail|ls)\b", cmd):
        deny("`change.py apply` must be run as a single, unchained command.")
    check_patterns(cmd, root)


def main():
    try:
        data = json.load(sys.stdin)
        tool = data.get("tool_name")
        tin = data.get("tool_input") or {}
        root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or ".").resolve()
        cwd = Path(data.get("cwd") or root)
    except Exception:  # noqa: BLE001 - fail open on malformed input
        return
    if tool not in TOOLS:
        return
    if tool == "Bash":
        handle_bash(tin.get("command") or "", root)
    else:
        handle_file_tool(tin, root, cwd)


if __name__ == "__main__":
    main()
