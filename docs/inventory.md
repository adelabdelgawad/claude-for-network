# Inventory

The inventory is a SQLite database at `inventory/inventory.db` (path overridable with
`INVENTORY_DB` in `.env`). The schema is in [`inventory/schema.sql`](../inventory/schema.sql) and
is idempotent (`CREATE ... IF NOT EXISTS`), so you can re-apply it to upgrade an existing database.

The database holds real hostnames, IPs and serials, so it is gitignored.

## Network tables

| Table | Contents |
|---|---|
| `sites` | `name`, `location`, `notes` |
| `devices` | One row per managed device: `hostname`, `mgmt_ip`, `site_id`, `device_type`, `role`, `vendor`, `model`, `os_type`, `os_version`, `serial`, `port`, `credential_ref`, `status`, `notes`, timestamps |
| `change_log` | Every change applied by `change.py`: `device_id`, `action`, `details`, `performed_by`, `performed_at` |
| `firewall_details` | Sophos XG facts per firewall device: API port and credential, HA mode/role/peer, license expiry |

### `devices` conventions

- `os_type` is the Netmiko `device_type` (`cisco_ios`, `cisco_xe`, `cisco_nxos`, `sophos_sfos`, ...).
- `status`:
  - `active` — targeted by default
  - `spare`, `decommissioned` — ignored unless `--status` asks for them
  - `auth_failed` — SSH is open but the credentials were rejected; set another `credential_ref`
- `credential_ref` selects `NET_<REF>_*` variables in `.env`.

## VMware vSphere tables

Kept separate from `devices` on purpose: the network scripts select from `devices` only, so they
can never target a VM or ESXi host.

| Table | Contents |
|---|---|
| `vcenters` | vCenter servers (`host`, `version`, `verify_ssl`, `credential_ref`) |
| `esxi_hosts` | Hosts with cluster, hardware, version, connection and maintenance state |
| `port_groups` | VM networks mapped to VLAN IDs on the physical switches |
| `machines` | VMs, keyed by `instance_uuid`: guest OS, sizing, power state, tools, owner, management protocol |
| `machine_nics` | VM NICs with MAC, port group and IPs |

## Querying

Use `scripts/inventory.py` (see [scripts.md](scripts.md)). For ad-hoc SQL without the `sqlite3` CLI:

```bash
python3 -c "import sqlite3;c=sqlite3.connect('inventory/inventory.db');print(c.execute(\"SELECT status,COUNT(*) FROM devices GROUP BY status\").fetchall())"
```
