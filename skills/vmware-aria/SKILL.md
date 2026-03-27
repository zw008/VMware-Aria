---
name: vmware-aria
description: >
  VMware Aria Operations (vRealize Operations) monitoring and capacity planning.
  Query VM/host/cluster metrics, manage alerts, check capacity, detect anomalies.
  Use when user asks to "check VM performance", "list alerts", "acknowledge alarm",
  "check capacity", "find top CPU consumers", "get rightsizing recommendations",
  "detect anomalies", "check Aria health", or mentions Aria Operations/vROps/vRealize Operations.
  For VM lifecycle operations use vmware-aiops, for NSX networking use vmware-nsx.
installer:
  kind: uv
  package: vmware-aria
allowed-tools:
  - Bash
metadata: {"openclaw":{"requires":{"env":["VMWARE_ARIA_CONFIG"],"bins":["vmware-aria"],"config":["~/.vmware-aria/config.yaml"]},"primaryEnv":"VMWARE_ARIA_CONFIG","homepage":"https://github.com/zw008/VMware-Aria","emoji":"📊","os":["macos","linux"]}}
---

# VMware Aria Operations

VMware Aria Operations (vRealize Operations) AI-assisted monitoring — 18 MCP tools for resources, alerts, capacity planning, anomaly detection, and platform health.

> Domain-focused monitoring skill for Aria Operations 8.x / vRealize Operations 8.x.
> **Companion skills**: [vmware-nsx](https://github.com/zw008/VMware-NSX) (networking), [vmware-aiops](https://github.com/zw008/VMware-AIops) (VM lifecycle), [vmware-monitor](https://github.com/zw008/VMware-Monitor) (read-only vSphere).

## What This Skill Does

| Category | Tools | Count |
|----------|-------|:-----:|
| **Resources** | list, get details, metrics, health badge, top consumers | 5 |
| **Alerts** | list, get details, acknowledge, cancel, list definitions | 5 |
| **Capacity** | cluster overview, remaining capacity, time remaining, rightsizing | 4 |
| **Anomaly** | list anomalies, risk badge | 2 |
| **Health** | Aria platform health, collector group status | 2 |

**Total**: 18 tools (16 read-only + 2 write)

## Quick Install

```bash
uv tool install vmware-aria
vmware-aria doctor
```

## When to Use This Skill

- Check VM, host, or cluster performance metrics
- List or investigate active alerts, acknowledge or cancel alarms
- Assess cluster capacity: remaining headroom, time-until-full predictions
- Find over-provisioned or under-provisioned VMs (rightsizing)
- Detect metric anomalies using Aria's machine learning models
- Check Aria Operations platform health and collector status

**Use companion skills for**:
- VM lifecycle: create, clone, snapshot, power → `vmware-aiops`
- NSX networking: segments, gateways, NAT, routing → `vmware-nsx`
- vSphere inventory, events → `vmware-monitor`
- Storage: iSCSI, vSAN, datastores → `vmware-storage`

## Related Skills — Skill Routing

| User Intent | Recommended Skill |
|-------------|-------------------|
| Aria Operations monitoring, alerts, capacity | **vmware-aria** ← this skill |
| VM lifecycle, deployment, guest ops | **vmware-aiops** |
| NSX networking: segments, gateways, NAT, routing | **vmware-nsx** |
| Read-only vSphere inventory, events, alarms | **vmware-monitor** |
| Storage: iSCSI, vSAN, datastores | **vmware-storage** |

## Common Workflows

### Investigate High CPU Alert

1. List active CRITICAL alerts → `vmware-aria alert list --criticality CRITICAL`
2. Get alert details → `vmware-aria alert get <alert-id>`
3. Find top CPU consumers → `vmware-aria resource top --metric cpu|usage_average`
4. Fetch 24h CPU metrics for the hot VM → `vmware-aria resource metrics <vm-id> --metrics cpu|usage_average --hours 24`
5. Check risk badge → `vmware-aria anomaly risk <vm-id>`
6. Acknowledge the alert → `vmware-aria alert acknowledge <alert-id>`

### Capacity Planning

1. List clusters → `vmware-aria resource list --kind ClusterComputeResource`
2. Get remaining capacity → `vmware-aria capacity remaining <cluster-id>`
3. Predict time until full → `vmware-aria capacity time-remaining <cluster-id>`
4. Get capacity overview with recommendations → `vmware-aria capacity overview <cluster-id>`
5. Find rightsizing candidates → `vmware-aria capacity rightsizing`

### Multi-Target Operations

All commands accept `--target <name>` to operate against a specific Aria Ops instance:

```bash
vmware-aria alert list --target prod
vmware-aria resource top --target lab
```

## MCP Tools (18)

All MCP tools accept an optional `target` parameter to select which Aria Operations instance to connect to.

| Category | Tool | Type | Description |
|----------|------|:----:|-------------|
| Resource | `list_resources` | Read | List VMs, hosts, clusters by resource kind |
| | `get_resource` | Read | Get resource details with health, risk, efficiency badges |
| | `get_resource_metrics` | Read | Fetch time-series metric stats for any resource |
| | `get_resource_health` | Read | Get health badge score (0–100) |
| | `get_top_consumers` | Read | Rank resources by CPU, memory, disk, or network usage |
| Alerts | `list_alerts` | Read | List active alerts with criticality and resource info |
| | `get_alert` | Read | Get alert details: symptoms and recommendations |
| | `acknowledge_alert` | Write | Mark an alert as acknowledged (does not close it) |
| | `cancel_alert` | Write | Cancel (dismiss) an active alert |
| | `list_alert_definitions` | Read | List alert templates configured in Aria Ops |
| Capacity | `get_capacity_overview` | Read | Cluster capacity recommendations from Aria |
| | `get_remaining_capacity` | Read | Remaining CPU, memory, disk before hitting limits |
| | `get_time_remaining` | Read | Days until cluster capacity is exhausted |
| | `list_rightsizing_recommendations` | Read | VMs to resize: over/under-provisioned |
| Anomaly | `list_anomalies` | Read | Machine-learning anomalies across monitored resources |
| | `get_resource_riskbadge` | Read | Risk score (0–100): likelihood of future problems |
| Health | `get_aria_health` | Read | Aria platform internal services health |
| | `list_collector_groups` | Read | Collector agents status and connectivity |

**Read/write split**: 16 read-only, 2 write (acknowledge_alert, cancel_alert). Write operations are audit-logged.

## CLI Quick Reference

```bash
# Resources
vmware-aria resource list [--kind VirtualMachine|HostSystem|ClusterComputeResource] [--name <filter>]
vmware-aria resource get <resource-id>
vmware-aria resource metrics <resource-id> --metrics cpu|usage_average,mem|usage_average --hours 4
vmware-aria resource health <resource-id>
vmware-aria resource top --metric cpu|usage_average --kind VirtualMachine --top 10

# Alerts
vmware-aria alert list [--criticality CRITICAL|IMMEDIATE|WARNING|INFORMATION]
vmware-aria alert get <alert-id>
vmware-aria alert acknowledge <alert-id>
vmware-aria alert cancel <alert-id>
vmware-aria alert definitions [--name <filter>]

# Capacity
vmware-aria capacity overview <cluster-id>
vmware-aria capacity remaining <resource-id>
vmware-aria capacity time-remaining <resource-id>
vmware-aria capacity rightsizing [--resource-id <vm-id>]

# Anomaly
vmware-aria anomaly list [--resource-id <id>]
vmware-aria anomaly risk <resource-id>

# Health
vmware-aria health status
vmware-aria health collectors

# Diagnostics
vmware-aria doctor [--skip-auth]
```

> Full CLI reference with all options and output formats: see `references/cli-reference.md`

## Troubleshooting

### "Token not found" error after setup

The token acquisition request failed. Verify:
1. Aria Ops is reachable: `vmware-aria doctor`
2. The `auth_source` in config matches your environment (LOCAL, LDAP, AD)
3. The password env var follows the naming convention: `VMWARE_ARIA_<TARGET>_PASSWORD`

### Resources appear missing from list_resources

The collector agent may be offline. Check `list_collector_groups` for any collectors in a non-RUNNING state. Restart the affected collector from the Aria Ops UI under Administration > Collector Groups.

### Metrics return empty data

The resource may not have metric collection configured, or the requested metric key is incorrect. Verify metric keys against the resource's available metrics in the Aria Ops UI (Metrics tab on the resource detail page).

### "Password not found" error

Variable names follow the pattern `VMWARE_ARIA_<TARGET_NAME_UPPER>_PASSWORD` where hyphens become underscores. Example: target `prod` needs `VMWARE_ARIA_PROD_PASSWORD`. Check your `~/.vmware-aria/.env` file.

## Safety

- **Read-heavy**: 16 of 18 tools are read-only
- **Audit logging**: Write operations logged to `~/.vmware-aria/audit.log` in JSON Lines format with timestamp, user, target, operation, and result
- **Token expiry handling**: OpsToken refreshed automatically 60 seconds before expiry (30-minute validity window)
- **Prompt injection defense**: API text values sanitized via `_sanitize()` — strips control characters, truncates to 500 chars
- **Credential safety**: Passwords loaded only from environment variables (`.env` file), never from `config.yaml`
- **Input validation**: resource_id and alert_id validated before API calls; criticality values validated against known enum

## Setup

```bash
uv tool install vmware-aria
mkdir -p ~/.vmware-aria
cp config.example.yaml ~/.vmware-aria/config.yaml
# Edit config.yaml with your Aria Operations host details

echo "VMWARE_ARIA_PROD_PASSWORD=your_password" > ~/.vmware-aria/.env
chmod 600 ~/.vmware-aria/.env

vmware-aria doctor
```

> Full setup guide with multi-target config, MCP server setup, and Docker: see `references/setup-guide.md`

## Architecture

```
User (natural language)
  |
AI Agent (Claude Code / Goose / Cursor)
  | reads SKILL.md
vmware-aria CLI or MCP server (stdio transport)
  | Aria Operations Suite API (REST/JSON over HTTPS)
  | POST /suite-api/api/auth/token/acquire → OpsToken
Aria Operations Manager
  |
VMs / Hosts / Clusters / Datastores / Alerts / Capacity
```

The MCP server uses stdio transport (local only, no network listener). Connections to Aria Ops use HTTPS on port 443 with OpsToken authentication (30-minute token validity, auto-refreshed).

## License

MIT — [github.com/zw008/VMware-Aria](https://github.com/zw008/VMware-Aria)
