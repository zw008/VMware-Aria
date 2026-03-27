"""MCP server wrapping VMware Aria Operations monitoring and capacity planning.

This module exposes VMware Aria Operations management tools via the Model
Context Protocol (MCP) using stdio transport.  Each ``@mcp.tool()``
function delegates to the corresponding function in the ``vmware_aria``
package (ops.resources, ops.alerts, ops.capacity, ops.anomaly, ops.health).

Tool categories
---------------
* **Resource** (5 tools, read-only): list_resources, get_resource,
  get_resource_metrics, get_resource_health, get_top_consumers

* **Alerts** (5 tools, 3 read + 2 write): list_alerts, get_alert,
  list_alert_definitions, acknowledge_alert, cancel_alert

* **Capacity** (4 tools, read-only): get_capacity_overview,
  get_remaining_capacity, get_time_remaining,
  list_rightsizing_recommendations

* **Anomaly** (2 tools, read-only): list_anomalies, get_resource_riskbadge

* **Health** (2 tools, read-only): get_aria_health, list_collector_groups

Security considerations
-----------------------
* **Credential handling**: Credentials are loaded from environment
  variables / ``.env`` file — never passed via MCP messages.
* **Transport**: Uses stdio transport (local only); no network listener.
* **Write operations**: acknowledge_alert, cancel_alert modify alert state;
  confirmation is recommended before execution.
* **Sanitization**: All API text responses pass through _sanitize() to strip
  control characters and truncate to prevent prompt injection.

For VM lifecycle operations use vmware-aiops.
For NSX networking use vmware-nsx.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from vmware_aria.config import load_config
from vmware_aria.connection import ConnectionManager
from vmware_aria.notify.audit import AuditLogger

logger = logging.getLogger(__name__)
_audit = AuditLogger()

mcp = FastMCP(
    "vmware-aria",
    instructions=(
        "VMware Aria Operations (vRealize Operations) monitoring, alerting, and capacity planning. "
        "Query VM/host/cluster metrics, manage alerts, check capacity and rightsizing recommendations, "
        "detect anomalies, and monitor Aria platform health. "
        "For VM lifecycle operations use vmware-aiops. "
        "For NSX networking use vmware-nsx."
    ),
)

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

_conn_mgr: ConnectionManager | None = None


def _get_connection(target: str | None = None) -> Any:
    """Return an AriaClient, lazily initialising the connection manager."""
    global _conn_mgr  # noqa: PLW0603
    if _conn_mgr is None:
        config_path_str = os.environ.get("VMWARE_ARIA_CONFIG")
        config_path = Path(config_path_str) if config_path_str else None
        config = load_config(config_path)
        _conn_mgr = ConnectionManager(config)
    return _conn_mgr.connect(target)


def _target_name(target: str | None) -> str:
    """Return display name for audit log entries."""
    return target or "default"


# ═══════════════════════════════════════════════════════════════════════════════
# RESOURCE tools (5)
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def list_resources(
    resource_kind: str = "VirtualMachine",
    limit: int = 100,
    name_filter: str | None = None,
    target: str | None = None,
) -> list[dict]:
    """List resources in Aria Operations filtered by kind.

    Args:
        resource_kind: Resource kind to list. Common values: VirtualMachine,
            HostSystem, ClusterComputeResource, Datastore, Datacenter.
        limit: Maximum number of results (1–500). Default 100.
        name_filter: Optional substring to filter by resource name (case-insensitive).
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.resources import list_resources as _list

    return _list(_get_connection(target), resource_kind=resource_kind, limit=limit, name_filter=name_filter)


@mcp.tool()
def get_resource(resource_id: str, target: str | None = None) -> dict:
    """Get full details for a specific resource including health, risk, and efficiency badges.

    Args:
        resource_id: The resource UUID.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.resources import get_resource as _get

    return _get(_get_connection(target), resource_id)


@mcp.tool()
def get_resource_metrics(
    resource_id: str,
    metric_keys: list[str],
    hours: int = 1,
    rollup_type: str = "AVG",
    target: str | None = None,
) -> dict:
    """Fetch time-series metric statistics for a resource.

    Args:
        resource_id: The resource UUID.
        metric_keys: List of metric keys to fetch, e.g. ["cpu|usage_average", "mem|usage_average"].
            Common keys: cpu|usage_average, mem|usage_average, disk|usage_average,
            net|usage_average, cpu|demand_average, mem|workload.
        hours: Number of hours of history to retrieve. Default 1.
        rollup_type: Aggregation type: AVG, MAX, MIN, SUM, COUNT, LATEST. Default AVG.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    import time as _time

    from vmware_aria.ops.resources import get_resource_metrics as _get_metrics

    client = _get_connection(target)
    end_ms = int(_time.time() * 1000)
    begin_ms = end_ms - (hours * 3_600_000)
    return _get_metrics(client, resource_id, metric_keys, begin_time_ms=begin_ms, end_time_ms=end_ms, rollup_type=rollup_type)


@mcp.tool()
def get_resource_health(resource_id: str, target: str | None = None) -> dict:
    """Get the health badge score for a resource (0–100, higher is healthier).

    Args:
        resource_id: The resource UUID.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.resources import get_resource_health as _get_health

    return _get_health(_get_connection(target), resource_id)


@mcp.tool()
def get_top_consumers(
    metric_key: str = "cpu|usage_average",
    resource_kind: str = "VirtualMachine",
    top_n: int = 10,
    target: str | None = None,
) -> list[dict]:
    """Query resources with highest consumption of a given metric.

    Args:
        metric_key: The metric to rank by. Common values: cpu|usage_average,
            mem|usage_average, disk|usage_average, net|usage_average.
        resource_kind: Resource kind to scope the query. Default VirtualMachine.
        top_n: Number of top consumers to return (max 50). Default 10.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.resources import get_top_consumers as _get_top

    return _get_top(_get_connection(target), metric_key=metric_key, resource_kind=resource_kind, top_n=top_n)


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT tools (5)
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def list_alerts(
    active_only: bool = True,
    criticality: str | None = None,
    resource_id: str | None = None,
    limit: int = 100,
    target: str | None = None,
) -> list[dict]:
    """List alerts from Aria Operations.

    Args:
        active_only: Return only active (non-cancelled) alerts. Default True.
        criticality: Filter by criticality: INFORMATION, WARNING, IMMEDIATE, CRITICAL.
        resource_id: Scope alerts to a specific resource UUID.
        limit: Maximum number of alerts to return (1–500). Default 100.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.alerts import list_alerts as _list

    return _list(_get_connection(target), active_only=active_only, criticality=criticality, resource_id=resource_id, limit=limit)


@mcp.tool()
def get_alert(alert_id: str, target: str | None = None) -> dict:
    """Get full details for a specific alert including symptoms and recommendations.

    Args:
        alert_id: The alert UUID.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.alerts import get_alert as _get

    return _get(_get_connection(target), alert_id)


@mcp.tool()
def acknowledge_alert(alert_id: str, target: str | None = None) -> dict:
    """Acknowledge an active alert (marks it as seen, does not cancel it).

    This is a WRITE operation — it changes the alert's control state to ACKNOWLEDGED.
    The alert remains active and will still fire notifications until cancelled.

    Args:
        alert_id: The alert UUID to acknowledge.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.alerts import acknowledge_alert as _ack

    return _ack(_get_connection(target), alert_id, audit_logger=_audit, target_name=_target_name(target))


@mcp.tool()
def cancel_alert(alert_id: str, target: str | None = None) -> dict:
    """Cancel (dismiss) an active alert. This WRITE operation permanently closes the alert.

    Use acknowledge_alert if you only want to mark it as seen.
    Cancelled alerts will not re-trigger unless the underlying condition recurs.

    Args:
        alert_id: The alert UUID to cancel.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.alerts import cancel_alert as _cancel

    return _cancel(_get_connection(target), alert_id, audit_logger=_audit, target_name=_target_name(target))


@mcp.tool()
def list_alert_definitions(
    name_filter: str | None = None,
    limit: int = 100,
    target: str | None = None,
) -> list[dict]:
    """List alert definitions (templates that generate alerts when triggered).

    Args:
        name_filter: Optional substring to filter by definition name (case-insensitive).
        limit: Maximum number of definitions to return (1–500). Default 100.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.alerts import list_alert_definitions as _list

    return _list(_get_connection(target), name_filter=name_filter, limit=limit)


# ═══════════════════════════════════════════════════════════════════════════════
# CAPACITY tools (4)
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_capacity_overview(cluster_id: str, target: str | None = None) -> dict:
    """Get capacity recommendations and utilization overview for a cluster.

    Args:
        cluster_id: The cluster resource UUID (ClusterComputeResource).
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.capacity import get_capacity_overview as _get

    return _get(_get_connection(target), cluster_id)


@mcp.tool()
def get_remaining_capacity(resource_id: str, target: str | None = None) -> dict:
    """Get remaining capacity for a cluster or host — how much more workload can be added.

    Reports remaining CPU, memory, disk, and network capacity before hitting limits.

    Args:
        resource_id: The resource UUID (typically ClusterComputeResource or HostSystem).
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.capacity import get_remaining_capacity as _get

    return _get(_get_connection(target), resource_id)


@mcp.tool()
def get_time_remaining(resource_id: str, target: str | None = None) -> dict:
    """Predict when a cluster will exhaust its capacity based on usage trends.

    Returns projected days until each capacity dimension (CPU, memory, disk) is full.

    Args:
        resource_id: The resource UUID (typically ClusterComputeResource).
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.capacity import get_time_remaining as _get

    return _get(_get_connection(target), resource_id)


@mcp.tool()
def list_rightsizing_recommendations(
    resource_id: str | None = None,
    limit: int = 50,
    target: str | None = None,
) -> list[dict]:
    """List VM rightsizing recommendations to reduce waste or improve performance.

    Identifies over-provisioned VMs (reclaim CPU/memory) and under-provisioned VMs
    (add resources to prevent performance degradation).

    Args:
        resource_id: Optional VM resource UUID to scope to a single VM.
        limit: Maximum recommendations to return (1–200). Default 50.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.capacity import list_rightsizing_recommendations as _list

    return _list(_get_connection(target), resource_id=resource_id, limit=limit)


# ═══════════════════════════════════════════════════════════════════════════════
# ANOMALY tools (2)
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def list_anomalies(
    resource_id: str | None = None,
    limit: int = 50,
    target: str | None = None,
) -> list[dict]:
    """List anomalies detected by Aria Operations machine learning models.

    Anomalies are metric deviations that exceed expected behavioral patterns.

    Args:
        resource_id: Optional resource UUID to scope to a single resource.
        limit: Maximum anomalies to return (1–200). Default 50.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.anomaly import list_anomalies as _list

    return _list(_get_connection(target), resource_id=resource_id, limit=limit)


@mcp.tool()
def get_resource_riskbadge(resource_id: str, target: str | None = None) -> dict:
    """Get the risk badge score for a resource (0–100, higher = more risk of future problems).

    The risk badge predicts likelihood of performance degradation or availability issues
    based on current trends and workload patterns.

    Args:
        resource_id: The resource UUID.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.anomaly import get_resource_riskbadge as _get

    return _get(_get_connection(target), resource_id)


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH tools (2)
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_aria_health(target: str | None = None) -> dict:
    """Check Aria Operations platform health: all internal services and node status.

    Returns overall platform health, individual service states, and node information.
    Use this to verify Aria Operations is functioning correctly before investigating
    potential monitoring blind spots.

    Args:
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.health import get_aria_health as _get

    return _get(_get_connection(target))


@mcp.tool()
def list_collector_groups(target: str | None = None) -> list[dict]:
    """List Aria Operations collector groups and their member collector status.

    Collectors are remote agents that gather metrics from vSphere and other adapters.
    Check this when resources appear missing from Aria Operations or metrics are stale.

    Args:
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from vmware_aria.ops.health import list_collector_groups as _list

    return _list(_get_connection(target))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the MCP server using stdio transport."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    mcp.run()


if __name__ == "__main__":
    main()
