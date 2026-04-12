# VMware Aria Operations MCP Skill

> **Author**: Wei Zhou, VMware by Broadcom — wei-wz.zhou@broadcom.com
> This is a community-driven project by a VMware engineer, not an official VMware product.
> For official VMware developer tools see [developer.broadcom.com](https://developer.broadcom.com).

AI-assisted monitoring and capacity planning for VMware Aria Operations (vRealize Operations) via the Model Context Protocol (MCP).

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

`vmware-aria` exposes 18 MCP tools for interacting with Aria Operations through natural language AI agents (Claude Code, Cursor, Goose, etc.):

| Category | Tools | Type |
|----------|-------|------|
| **Resources** | list, get, metrics, health badge, top consumers | Read-only (5) |
| **Alerts** | list, get, acknowledge, cancel, definitions | Read + 2 Write (5) |
| **Capacity** | overview, remaining, time-remaining, rightsizing | Read-only (4) |
| **Anomaly** | list anomalies, risk badge | Read-only (2) |
| **Health** | platform health, collector groups | Read-only (2) |

**Total**: 18 tools — 16 read-only, 2 write (acknowledge/cancel alerts)

## Quick Start

```bash
# Install
uv tool install vmware-aria

# Configure
mkdir -p ~/.vmware-aria
cat > ~/.vmware-aria/config.yaml << 'EOF'
targets:
  prod:
    host: aria-ops.example.com
    username: admin
    port: 443
    verify_ssl: true
    auth_source: LOCAL
default_target: prod
EOF

# Set password (never in config.yaml)
echo "VMWARE_ARIA_PROD_PASSWORD=your_password" > ~/.vmware-aria/.env
chmod 600 ~/.vmware-aria/.env

# Verify setup
vmware-aria doctor
```

## CLI Examples

```bash
# List top CPU consumers
vmware-aria resource top --metric cpu|usage_average --top 10

# Check active CRITICAL alerts
vmware-aria alert list --criticality CRITICAL

# Acknowledge an alert
vmware-aria alert acknowledge <alert-id>

# Fetch 4-hour CPU + memory metrics for a VM
vmware-aria resource metrics <vm-id> --metrics cpu|usage_average,mem|usage_average --hours 4

# Check cluster capacity
vmware-aria capacity remaining <cluster-id>
vmware-aria capacity time-remaining <cluster-id>

# Find rightsizing opportunities
vmware-aria capacity rightsizing

# Check Aria platform health
vmware-aria health status
vmware-aria health collectors
```

## MCP Setup (Claude Code)

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "vmware-aria": {
      "command": "vmware-aria-mcp",
      "env": {
        "VMWARE_ARIA_CONFIG": "~/.vmware-aria/config.yaml"
      }
    }
  }
}
```

Then use natural language:
- *"Show me the top 10 CPU consumers right now"*
- *"List all CRITICAL alerts and acknowledge them"*
- *"How long until the prod cluster runs out of memory?"*
- *"Which VMs are over-provisioned? Show rightsizing recommendations"*
- *"Are there any anomalies on vm-web-01?"*

## Authentication

Aria Operations uses **OpsToken** authentication:

```
POST /suite-api/api/auth/token/acquire
{"username": "admin", "password": "...", "authSource": "LOCAL"}
→ {"token": "abc123", "validity": 1800000}

Subsequent requests: Authorization: OpsToken abc123
```

Tokens are valid for 30 minutes and automatically refreshed 60 seconds before expiry.

## Architecture

```
User (natural language)
  ↓
AI Agent (Claude Code / Goose / Cursor)
  ↓  [reads SKILL.md]
vmware-aria MCP server (stdio transport)
  ↓  [HTTPS + OpsToken]
Aria Operations Suite API
  ↓
VMs / Hosts / Clusters / Alerts / Capacity
```

### Companion Skills

| Skill | Scope | Tools | Install |
|-------|-------|:-----:|---------|
| **[vmware-aiops](https://github.com/zw008/VMware-AIops)** ⭐ entry point | VM lifecycle, deployment, guest ops, clusters | 31 | `uv tool install vmware-aiops` |
| **[vmware-monitor](https://github.com/zw008/VMware-Monitor)** | Read-only monitoring, alarms, events, VM info | 8 | `uv tool install vmware-monitor` |
| **[vmware-nsx](https://github.com/zw008/VMware-NSX)** | NSX networking: segments, gateways, NAT, IPAM | 31 | `uv tool install vmware-nsx-mgmt` |
| **[vmware-nsx-security](https://github.com/zw008/VMware-NSX-Security)** | DFW microsegmentation, security groups, Traceflow | 20 | `uv tool install vmware-nsx-security` |
| **[vmware-storage](https://github.com/zw008/VMware-Storage)** | Datastores, iSCSI, vSAN | 11 | `uv tool install vmware-storage` |
| **[vmware-vks](https://github.com/zw008/VMware-VKS)** | Tanzu Namespaces, TKC cluster lifecycle | 20 | `uv tool install vmware-vks` |

## Security

- Passwords loaded from env vars or `.env` file, never from `config.yaml`
- Write operations (acknowledge/cancel alert) audit-logged to `~/.vmware-aria/audit.log`
- API responses sanitized (control chars stripped, 500-char limit) to prevent prompt injection
- Supports self-signed certificates (`verify_ssl: false`) for lab environments

## License

MIT — see [LICENSE](LICENSE)
