# Capabilities

## Automation Level Reference

Each operation is classified by autonomy level per the Enterprise Harness Engineering framework. **vmware-aria is heavily L1/L2 (21 read / 6 write)** — primarily a monitoring and analysis skill.

| Level | Meaning | Agent autonomy | Examples in this skill |
|:-:|---|---|---|
| **L1** | Read-only, raw data | Always auto-run | `list_resources`, `get_resource`, `get_metrics`, `list_alerts`, `get_alert_details`, `list_alert_definitions`, capacity/efficiency badge queries |
| **L2** | Read + analysis / recommendation | Always auto-run | anomaly detection, top-N consumer ranking, capacity trend forecasting, alert correlation, symptom-to-recommendation mapping |
| **L3** | Single write — user must approve | Only after explicit confirmation | `acknowledge_alert`, `cancel_alert`, `suspend_alert`, `take_alert_ownership` *(the only writes; all auditable)* |
| **L4** | Multi-step plan / apply workflow | *N/A currently* | — *(no multi-step orchestration; Aria is observe/analyze, not configure)* |
| **L5** | Auto-remediation from learned pattern | Pattern library only; requires `risk:low` + `reversible:true` + `repeatable:true` | *(roadmap — candidates: auto-acknowledge known-noisy alerts, auto-cancel resolved-by-event alerts)* |

**Notes**:
- L1/L2 tools are always safe for agents to call without confirmation.
- L3 alert-state writes pass through the `@vmware_tool` decorator: connection check → policy check → audit log. Cancel is irreversible by Aria API design and treated as a destructive operation.
- For VM/host operations see [vmware-aiops](https://github.com/zw008/VMware-AIops); Aria recommendations are advisory, not actuating.

## What vmware-aria Can Do

### Resource Monitoring

- **List any resource type**: VirtualMachine, HostSystem, ClusterComputeResource, Datastore, Datacenter, ResourcePool
- **Filter by name**: substring match across any resource list
- **Get resource details**: health, risk, and efficiency badges plus all identifiers
- **Fetch metric time series**: any metric key with configurable time window and rollup (AVG/MAX/MIN)
- **Find top consumers**: rank VMs or hosts by CPU, memory, disk, or network usage

### Alert Management

- **List active or all alerts**: filter by criticality (INFORMATION/WARNING/IMMEDIATE/CRITICAL) or resource
- **Inspect alert details**: full symptom list, recommendations, timeline
- **Acknowledge alerts**: mark as seen without closing (control state → ACKNOWLEDGED)
- **Cancel alerts**: permanently dismiss (status → CANCELLED)
- **Browse alert definitions**: the templates that define when alerts fire

### Capacity Planning

- **Cluster capacity overview**: Aria's own recommendations for the cluster
- **Remaining capacity**: how much more CPU, memory, disk can be added before hitting limits
- **Time remaining**: predicted days until each capacity dimension is exhausted (based on trend)
- **Rightsizing recommendations**: identify over-provisioned VMs (reclaim resources) and under-provisioned VMs (prevent degradation)

### Anomaly Detection

- **List anomalies**: metric deviations detected by Aria's ML models, optionally scoped to one resource
- **Risk badge**: composite risk score (0–100) with contributing causes — predicts likelihood of future problems

### Platform Health

- **Aria health check**: all internal Aria Ops services (RUNNING / STOPPED / ERROR)
- **Collector group status**: list remote collector agents and their connectivity state

---

## What vmware-aria Cannot Do

| Capability | Use Instead |
|-----------|-------------|
| Create / delete / power VMs | `vmware-aiops` |
| Configure NSX segments, gateways, NAT | `vmware-nsx` |
| NSX DFW / firewall rules | `vmware-nsx-security` |
| vSphere inventory (VMs, hosts, clusters) read-only | `vmware-monitor` |
| Storage: iSCSI, vSAN, datastores | `vmware-storage` |
| Tanzu Kubernetes cluster management | `vmware-vks` |
| Create alert definitions | Supported via `create_alert_definition` (from symptom definition IDs) |
| Configure dashboards | Not supported (UI required) |
| Manage Aria adapter instances | Not supported (UI required) |

---

## Aria Operations API Coverage

| Endpoint | Used For |
|----------|---------|
| `POST /suite-api/api/auth/token/acquire` | Token authentication |
| `POST /suite-api/api/auth/token/release` | Token release on close |
| `GET /suite-api/api/resources` | list_resources |
| `GET /suite-api/api/resources/{id}` | get_resource |
| `POST /suite-api/api/resources/{id}/stats/query` | get_resource_metrics |
| `GET /suite-api/api/resources/{id}/badge/health` | get_resource_health |
| `POST /suite-api/api/resources/query/topn` | get_top_consumers |
| `GET /suite-api/api/alerts` | list_alerts |
| `GET /suite-api/api/alerts/{id}` | get_alert |
| `POST /suite-api/api/alerts/{id}/acknowledge` | acknowledge_alert |
| `DELETE /suite-api/api/alerts/{id}` | cancel_alert |
| `GET /suite-api/api/alertdefinitions` | list_alert_definitions |
| `GET /suite-api/api/resources/{id}/recommendations` | get_capacity_overview |
| `GET /suite-api/api/resources/{id}/remainingcapacity` | get_remaining_capacity |
| `GET /suite-api/api/resources/{id}/timeremaining` | get_time_remaining |
| `GET /suite-api/api/recommendations/rightsizing` | list_rightsizing_recommendations |
| `GET /suite-api/api/resources/{id}/anomalies` | list_anomalies (per resource) |
| `GET /suite-api/api/anomalies` | list_anomalies (global) |
| `GET /suite-api/api/resources/{id}/badge/risk` | get_resource_riskbadge |
| `GET /suite-api/api/deployment/node/status` | get_aria_health, is_alive |
| `GET /suite-api/api/collectorgroups` | list_collector_groups |

---

## Aria Operations Version Compatibility

| Feature | Minimum Version |
|---------|----------------|
| Token authentication | 6.6+ |
| Resource metrics stats query | 6.7+ |
| Rightsizing recommendations | 7.0+ |
| Anomaly detection | 7.5+ |
| Suite API v2 paths used | 8.0+ |

**Recommended**: Aria Operations 8.x (vROps 8.x). All endpoints verified against Aria Operations 8.6.
