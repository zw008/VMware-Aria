# CLI Reference

Complete reference for `vmware-aria` command-line interface.

## Global Options

All commands accept:
- `--target / -t <name>` — Target name from config (uses default if omitted)
- `--config / -c <path>` — Custom config file path

---

## `vmware-aria doctor`

Run pre-flight diagnostics.

```
vmware-aria doctor [OPTIONS]

Options:
  --skip-auth    Skip authentication check (only tests config + network)
  --config -c    Path to config file
```

**Checks performed**:
1. Config file exists at `~/.vmware-aria/config.yaml`
2. `.env` file permissions (warns if wider than 600)
3. Config parse succeeds (validates YAML and target structure)
4. Password env vars are set for each target
5. Network TCP connectivity to port 443 for each target
6. Aria Operations token acquisition (unless `--skip-auth`)
7. Aria node type / deployment info
8. MCP server module importable

---

## Resource Commands

### `vmware-aria resource list`

List resources by kind.

```
vmware-aria resource list [OPTIONS]

Options:
  --kind -k TEXT    Resource kind [default: VirtualMachine]
                    Values: VirtualMachine, HostSystem, ClusterComputeResource,
                            Datastore, Datacenter, ResourcePool
  --limit -n INT    Max results [default: 50]
  --name TEXT       Filter by name substring (case-insensitive)
  --target -t TEXT  Target name
```

**Output**: Table with Name, ID, Health (color + score), Status.

### `vmware-aria resource get`

Get full resource details.

```
vmware-aria resource get <resource-id> [OPTIONS]

Arguments:
  resource-id  Resource UUID (required)

Options:
  --target -t TEXT  Target name
```

**Output**: JSON with all resource fields including health, risk, efficiency badges and identifiers.

### `vmware-aria resource metrics`

Fetch time-series metrics for a resource.

```
vmware-aria resource metrics <resource-id> [OPTIONS]

Arguments:
  resource-id  Resource UUID (required)

Options:
  --metrics -m TEXT    Comma-separated metric keys
                       [default: cpu|usage_average,mem|usage_average]
  --hours INT          History window in hours [default: 1]
  --target -t TEXT     Target name
```

**Common metric keys**:
- `cpu|usage_average` — CPU utilization percentage
- `mem|usage_average` — Memory utilization percentage
- `cpu|demand_average` — CPU demand (MHz)
- `mem|workload` — Memory workload
- `disk|usage_average` — Disk I/O usage
- `net|usage_average` — Network usage

**Output**: JSON keyed by metric, each containing list of `{timestamp_ms, value}` points.

### `vmware-aria resource health`

Get health badge for a resource.

```
vmware-aria resource health <resource-id> [OPTIONS]
```

**Output**: JSON with health score (0–100), color, description.

### `vmware-aria resource top`

List top resource consumers by metric.

```
vmware-aria resource top [OPTIONS]

Options:
  --metric TEXT     Metric key to rank by [default: cpu|usage_average]
  --kind -k TEXT    Resource kind [default: VirtualMachine]
  --top -n INT      Number of top consumers [default: 10]
  --target -t TEXT  Target name
```

---

## Alert Commands

### `vmware-aria alert list`

List alerts.

```
vmware-aria alert list [OPTIONS]

Options:
  --active / --all          Active alerts only vs all [default: active]
  --criticality TEXT        Filter: INFORMATION, WARNING, IMMEDIATE, CRITICAL
  --limit -n INT            Max results [default: 50]
  --target -t TEXT          Target name
```

### `vmware-aria alert get`

Get full alert details with symptoms and recommendations.

```
vmware-aria alert get <alert-id> [OPTIONS]
```

### `vmware-aria alert acknowledge`

Acknowledge an alert (marks as seen, does not close it).

```
vmware-aria alert acknowledge <alert-id> [OPTIONS]

Options:
  --yes -y          Skip confirmation prompt
  --target -t TEXT  Target name
```

**Audit logged**: yes.

### `vmware-aria alert cancel`

Cancel (dismiss) an alert.

```
vmware-aria alert cancel <alert-id> [OPTIONS]

Options:
  --yes -y          Skip confirmation prompt
  --target -t TEXT  Target name
```

**Audit logged**: yes. Cancelled alerts will not re-trigger unless the underlying condition recurs.

### `vmware-aria alert definitions`

List alert definition templates.

```
vmware-aria alert definitions [OPTIONS]

Options:
  --name TEXT       Filter by name substring
  --limit -n INT    Max results [default: 50]
  --target -t TEXT  Target name
```

---

## Capacity Commands

### `vmware-aria capacity overview`

Get capacity recommendations for a cluster.

```
vmware-aria capacity overview <cluster-id> [OPTIONS]
```

### `vmware-aria capacity remaining`

Get remaining capacity headroom for a cluster or host.

```
vmware-aria capacity remaining <resource-id> [OPTIONS]
```

**Output**: JSON with remaining CPU (GHz), memory (GB), disk (GB) per dimension.

### `vmware-aria capacity time-remaining`

Predict how many days until capacity is exhausted.

```
vmware-aria capacity time-remaining <resource-id> [OPTIONS]
```

**Output**: JSON with projected days per capacity dimension and confidence levels.

### `vmware-aria capacity rightsizing`

List VM rightsizing recommendations.

```
vmware-aria capacity rightsizing [OPTIONS]

Options:
  --resource-id TEXT   Scope to a specific VM UUID
  --limit -n INT       Max results [default: 20]
  --target -t TEXT     Target name
```

**Output**: Table with VM name, recommendation type, current/recommended CPU count and memory.

---

## Anomaly Commands

### `vmware-aria anomaly list`

List detected anomalies.

```
vmware-aria anomaly list [OPTIONS]

Options:
  --resource-id TEXT   Scope to a specific resource
  --limit -n INT       Max results [default: 20]
  --target -t TEXT     Target name
```

### `vmware-aria anomaly risk`

Get risk badge score for a resource.

```
vmware-aria anomaly risk <resource-id> [OPTIONS]
```

**Output**: JSON with risk score (0–100), color, and contributing causes.

---

## Health Commands

### `vmware-aria health status`

Check Aria Operations platform health.

```
vmware-aria health status [OPTIONS]
```

**Output**: Console summary (HEALTHY / DEGRADED) + table of unhealthy services.

### `vmware-aria health collectors`

List collector groups and member status.

```
vmware-aria health collectors [OPTIONS]
```

**Output**: Per-group tables listing collector name, state, type, and host.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (API failure, auth failure, validation error) |
| 2 | Usage error (invalid arguments) |

`vmware-aria doctor` exits 0 if all checks pass, 1 if any fail.
