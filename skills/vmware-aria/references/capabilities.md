# Capabilities

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
| Create alert definitions or policies | Not supported (UI required) |
| Configure dashboards or reports | Not supported (UI required) |
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
