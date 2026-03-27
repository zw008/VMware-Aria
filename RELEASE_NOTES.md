# Release Notes

## v1.3.0 (2026-03-27)

Initial release of `vmware-aria` — VMware Aria Operations AI monitoring skill.

### Features

**Resource Monitoring (5 tools)**
- `list_resources` — List VMs, hosts, clusters, datastores by resource kind with health badge
- `get_resource` — Full resource details including health, risk, and efficiency badge scores
- `get_resource_metrics` — Time-series metric stats with configurable window and rollup type
- `get_resource_health` — Health badge score (0–100) with color and description
- `get_top_consumers` — Rank VMs or hosts by CPU, memory, disk, or network usage

**Alert Management (5 tools)**
- `list_alerts` — Active or all alerts with criticality and resource scope filtering
- `get_alert` — Full alert details: symptom list, recommendations, timeline
- `acknowledge_alert` — Mark alert as acknowledged (write, audit-logged)
- `cancel_alert` — Dismiss an active alert (write, audit-logged)
- `list_alert_definitions` — Browse alert definition templates

**Capacity Planning (4 tools)**
- `get_capacity_overview` — Cluster capacity recommendations
- `get_remaining_capacity` — Remaining CPU, memory, disk headroom
- `get_time_remaining` — Days until capacity dimensions are exhausted
- `list_rightsizing_recommendations` — Over/under-provisioned VM recommendations

**Anomaly Detection (2 tools)**
- `list_anomalies` — ML-detected metric anomalies, per-resource or global
- `get_resource_riskbadge` — Risk score with contributing causes

**Platform Health (2 tools)**
- `get_aria_health` — All Aria internal service states
- `list_collector_groups` — Remote collector agent status

### Authentication
- OpsToken authentication: `POST /suite-api/api/auth/token/acquire`
- Auto-refresh: token refreshed 60s before 30-minute expiry
- Supports LOCAL, LDAP, and AD authentication sources

### Security
- Passwords loaded from env vars / `.env` file only
- All API text sanitized (control chars stripped, 500-char max)
- Write operations (acknowledge/cancel) audit-logged to `~/.vmware-aria/audit.log`

### CLI
- Full CLI with 5 command groups: `resource`, `alert`, `capacity`, `anomaly`, `health`
- `vmware-aria doctor` — pre-flight diagnostics for config, network, auth, MCP import
- Rich table output for list commands, JSON output for detail commands

### Compatibility
- Python 3.10+
- Aria Operations 8.x (vRealize Operations 8.x)
- Suite API v2 (`/suite-api/api/`)
