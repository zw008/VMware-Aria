"""MCP server wrapping VMware Aria Operations monitoring and capacity planning.

This module exposes VMware Aria Operations management tools via the Model
Context Protocol (MCP) using stdio transport.  Each ``@mcp.tool()``
function delegates to the corresponding function in the ``vmware_aria``
package (ops.resources, ops.alerts, ops.capacity, ops.anomaly, ops.health,
ops.reports).

Tool categories
---------------
* **Resource** (5 tools, read-only): list_resources, get_resource,
  get_resource_metrics, get_resource_health, get_top_consumers

* **Alerts** (5 tools, 3 read + 2 write): list_alerts, get_alert,
  list_alert_definitions, acknowledge_alert, cancel_alert

* **Alert Definitions** (4 tools, write): list_symptom_definitions,
  create_alert_definition, set_alert_definition_state, delete_alert_definition

* **Capacity** (4 tools, read-only): get_capacity_overview,
  get_remaining_capacity, get_time_remaining,
  list_rightsizing_recommendations

* **Anomaly** (2 tools, read-only): list_anomalies, get_resource_riskbadge

* **Health** (2 tools, read-only): get_aria_health, list_collector_groups

* **Reports** (5 tools): list_report_definitions, generate_report,
  list_reports, get_report, delete_report

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
from vmware_policy import vmware_tool

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


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_resources(
    resource_kind: str = "VirtualMachine",
    limit: int = 100,
    name_filter: str | None = None,
    target: str | None = None,
) -> list[dict]:
    """[READ] List resources in Aria Operations filtered by kind.

    Args:
        resource_kind: Resource kind to list. Common values: VirtualMachine,
            HostSystem, ClusterComputeResource, Datastore, Datacenter.
        limit: Maximum number of results (1–500). Default 100.
        name_filter: Optional substring to filter by resource name (case-insensitive).
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.resources import list_resources as _list

        return _list(_get_connection(target), resource_kind=resource_kind, limit=limit, name_filter=name_filter)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_resource(resource_id: str, target: str | None = None) -> dict:
    """[READ] Get full details for a specific resource including health, risk, and efficiency badges.

    Args:
        resource_id: The resource UUID.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.resources import get_resource as _get

        return _get(_get_connection(target), resource_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_resource_metrics(
    resource_id: str,
    metric_keys: list[str],
    hours: int = 1,
    rollup_type: str = "AVG",
    target: str | None = None,
) -> dict:
    """[READ] Fetch time-series metric statistics for a resource.

    Args:
        resource_id: The resource UUID.
        metric_keys: List of metric keys to fetch, e.g. ["cpu|usage_average", "mem|usage_average"].
            Common keys: cpu|usage_average, mem|usage_average, disk|usage_average,
            net|usage_average, cpu|demand_average, mem|workload.
        hours: Number of hours of history to retrieve. Default 1.
        rollup_type: Aggregation type: AVG, MAX, MIN, SUM, COUNT, LATEST. Default AVG.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        import time as _time

        from vmware_aria.ops.resources import get_resource_metrics as _get_metrics

        client = _get_connection(target)
        end_ms = int(_time.time() * 1000)
        begin_ms = end_ms - (hours * 3_600_000)
        return _get_metrics(client, resource_id, metric_keys, begin_time_ms=begin_ms, end_time_ms=end_ms, rollup_type=rollup_type)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_resource_health(resource_id: str, target: str | None = None) -> dict:
    """[READ] Get the health badge score for a resource (0–100, higher is healthier).

    Args:
        resource_id: The resource UUID.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.resources import get_resource_health as _get_health

        return _get_health(_get_connection(target), resource_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_top_consumers(
    metric_key: str = "cpu|usage_average",
    resource_kind: str = "VirtualMachine",
    top_n: int = 10,
    target: str | None = None,
) -> list[dict]:
    """[READ] Query resources with highest consumption of a given metric.

    Args:
        metric_key: The metric to rank by. Common values: cpu|usage_average,
            mem|usage_average, disk|usage_average, net|usage_average.
        resource_kind: Resource kind to scope the query. Default VirtualMachine.
        top_n: Number of top consumers to return (max 50). Default 10.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.resources import get_top_consumers as _get_top

        return _get_top(_get_connection(target), metric_key=metric_key, resource_kind=resource_kind, top_n=top_n)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}]


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT tools (5)
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_alerts(
    active_only: bool = True,
    criticality: str | None = None,
    resource_id: str | None = None,
    limit: int = 100,
    target: str | None = None,
) -> list[dict]:
    """[READ] List alerts from Aria Operations.

    Args:
        active_only: Return only active (non-cancelled) alerts. Default True.
        criticality: Filter by criticality: INFORMATION, WARNING, IMMEDIATE, CRITICAL.
        resource_id: Scope alerts to a specific resource UUID.
        limit: Maximum number of alerts to return (1–500). Default 100.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.alerts import list_alerts as _list

        return _list(_get_connection(target), active_only=active_only, criticality=criticality, resource_id=resource_id, limit=limit)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_alert(alert_id: str, target: str | None = None) -> dict:
    """[READ] Get full details for a specific alert including symptoms and recommendations.

    Args:
        alert_id: The alert UUID.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.alerts import get_alert as _get

        return _get(_get_connection(target), alert_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def acknowledge_alert(alert_id: str, confirmed: bool = False, target: str | None = None) -> dict:
    """[WRITE] Acknowledge an active alert (marks it as seen, does not cancel it).

    This is a WRITE operation — it changes the alert's control state to ACKNOWLEDGED.
    The alert remains active and will still fire notifications until cancelled.
    Default confirmed=False returns a preview without making any change.

    Args:
        alert_id: The alert UUID to acknowledge.
        confirmed: Must be True to actually acknowledge. Default False = preview only.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    if not confirmed:
        return {
            "preview": True,
            "action": "acknowledge",
            "alert_id": alert_id,
            "message": (
                f"[preview] Would acknowledge alert {alert_id}. "
                "Re-invoke with confirmed=True to execute."
            ),
        }
    try:
        from vmware_aria.ops.alerts import acknowledge_alert as _ack

        return _ack(_get_connection(target), alert_id, audit_logger=_audit, target_name=_target_name(target))
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def cancel_alert(alert_id: str, confirmed: bool = False, target: str | None = None) -> dict:
    """[WRITE] Cancel (dismiss) an active alert. This WRITE operation permanently closes the alert.

    Use acknowledge_alert if you only want to mark it as seen.
    Cancelled alerts will not re-trigger unless the underlying condition recurs.
    Default confirmed=False returns a preview without making any change.

    Args:
        alert_id: The alert UUID to cancel.
        confirmed: Must be True to actually cancel. Default False = preview only.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    if not confirmed:
        return {
            "preview": True,
            "action": "cancel",
            "alert_id": alert_id,
            "message": (
                f"[preview] Would cancel alert {alert_id}. "
                "Re-invoke with confirmed=True to execute."
            ),
        }
    try:
        from vmware_aria.ops.alerts import cancel_alert as _cancel

        return _cancel(_get_connection(target), alert_id, audit_logger=_audit, target_name=_target_name(target))
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_alert_definitions(
    name_filter: str | None = None,
    limit: int = 100,
    target: str | None = None,
) -> list[dict]:
    """[READ] List alert definitions (templates that generate alerts when triggered).

    Args:
        name_filter: Optional substring to filter by definition name (case-insensitive).
        limit: Maximum number of definitions to return (1–500). Default 100.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.alerts import list_alert_definitions as _list

        return _list(_get_connection(target), name_filter=name_filter, limit=limit)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}]


# ═══════════════════════════════════════════════════════════════════════════════
# CAPACITY tools (4)
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_capacity_overview(cluster_id: str, target: str | None = None) -> dict:
    """[READ] Get capacity recommendations and utilization overview for a cluster.

    Args:
        cluster_id: The cluster resource UUID (ClusterComputeResource).
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.capacity import get_capacity_overview as _get

        return _get(_get_connection(target), cluster_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_remaining_capacity(resource_id: str, target: str | None = None) -> dict:
    """[READ] Get remaining capacity for a cluster or host — how much more workload can be added.

    Reports remaining CPU, memory, disk, and network capacity before hitting limits.

    Args:
        resource_id: The resource UUID (typically ClusterComputeResource or HostSystem).
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.capacity import get_remaining_capacity as _get

        return _get(_get_connection(target), resource_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_time_remaining(resource_id: str, target: str | None = None) -> dict:
    """[READ] Predict when a cluster will exhaust its capacity based on usage trends.

    Returns projected days until each capacity dimension (CPU, memory, disk) is full.

    Args:
        resource_id: The resource UUID (typically ClusterComputeResource).
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.capacity import get_time_remaining as _get

        return _get(_get_connection(target), resource_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_rightsizing_recommendations(
    resource_id: str | None = None,
    limit: int = 50,
    target: str | None = None,
) -> list[dict]:
    """[READ] List VM rightsizing recommendations to reduce waste or improve performance.

    Identifies over-provisioned VMs (reclaim CPU/memory) and under-provisioned VMs
    (add resources to prevent performance degradation).

    Args:
        resource_id: Optional VM resource UUID to scope to a single VM.
        limit: Maximum recommendations to return (1–200). Default 50.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.capacity import list_rightsizing_recommendations as _list

        return _list(_get_connection(target), resource_id=resource_id, limit=limit)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}]


# ═══════════════════════════════════════════════════════════════════════════════
# ANOMALY tools (2)
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_anomalies(
    resource_id: str | None = None,
    limit: int = 50,
    target: str | None = None,
) -> list[dict]:
    """[READ] List anomalies detected by Aria Operations machine learning models.

    Anomalies are metric deviations that exceed expected behavioral patterns.

    Args:
        resource_id: Optional resource UUID to scope to a single resource.
        limit: Maximum anomalies to return (1–200). Default 50.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.anomaly import list_anomalies as _list

        return _list(_get_connection(target), resource_id=resource_id, limit=limit)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_resource_riskbadge(resource_id: str, target: str | None = None) -> dict:
    """[READ] Get the risk badge score for a resource (0–100, higher = more risk of future problems).

    The risk badge predicts likelihood of performance degradation or availability issues
    based on current trends and workload patterns.

    Args:
        resource_id: The resource UUID.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.anomaly import get_resource_riskbadge as _get

        return _get(_get_connection(target), resource_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH tools (2)
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_aria_health(target: str | None = None) -> dict:
    """[READ] Check Aria Operations platform health: all internal services and node status.

    Returns overall platform health, individual service states, and node information.
    Use this to verify Aria Operations is functioning correctly before investigating
    potential monitoring blind spots.

    Args:
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.health import get_aria_health as _get

        return _get(_get_connection(target))
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_collector_groups(target: str | None = None) -> list[dict]:
    """[READ] List Aria Operations collector groups and their member collector status.

    Collectors are remote agents that gather metrics from vSphere and other adapters.
    Check this when resources appear missing from Aria Operations or metrics are stale.

    Args:
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.health import list_collector_groups as _list

        return _list(_get_connection(target))
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}]


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT DEFINITION management tools (4)
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_symptom_definitions(
    name_filter: str | None = None,
    resource_kind: str | None = None,
    limit: int = 100,
    target: str | None = None,
) -> list[dict]:
    """[READ] List symptom definitions — use the returned IDs when calling create_alert_definition.

    Args:
        name_filter: Optional substring to filter by symptom name (case-insensitive).
        resource_kind: Optional resource kind filter, e.g. VirtualMachine, HostSystem.
        limit: Maximum number of symptom definitions to return (1–500). Default 100.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.alerts import list_symptom_definitions as _list

        return _list(_get_connection(target), name_filter=name_filter, resource_kind=resource_kind, limit=limit)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def create_alert_definition(
    name: str,
    description: str,
    resource_kind: str,
    symptom_definition_ids: list[str],
    criticality: str = "WARNING",
    adapter_kind: str = "VMWARE",
    target: str | None = None,
) -> dict:
    """[WRITE] Create a new alert definition referencing existing symptom definitions.

    Use list_symptom_definitions() to find symptom_definition_ids.

    Args:
        name: Alert definition name (must be unique in Aria Operations).
        description: Human-readable description of when/why this alert fires.
        resource_kind: Resource kind this alert applies to: VirtualMachine,
            HostSystem, ClusterComputeResource, Datastore.
        symptom_definition_ids: List of symptom definition UUIDs. ANY one symptom
            firing will trigger the alert.
        criticality: Alert severity: INFORMATION, WARNING, IMMEDIATE, CRITICAL.
        adapter_kind: Adapter kind key. Default VMWARE (vSphere adapter).
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.alerts import create_alert_definition as _create

        return _create(
            _get_connection(target),
            name=name,
            description=description,
            resource_kind=resource_kind,
            symptom_definition_ids=symptom_definition_ids,
            criticality=criticality,
            adapter_kind=adapter_kind,
            audit_logger=_audit,
            target_name=_target_name(target),
        )
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def set_alert_definition_state(
    definition_id: str,
    enabled: bool,
    target: str | None = None,
) -> dict:
    """[WRITE] Enable or disable an existing alert definition.

    Args:
        definition_id: Alert definition UUID (from list_alert_definitions).
        enabled: True to enable the definition, False to disable it.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.alerts import set_alert_definition_state as _set_state

        return _set_state(
            _get_connection(target),
            definition_id=definition_id,
            enabled=enabled,
            audit_logger=_audit,
            target_name=_target_name(target),
        )
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def delete_alert_definition(
    definition_id: str,
    target: str | None = None,
) -> dict:
    """[WRITE] Permanently delete an alert definition.

    This WRITE operation removes the alert definition from Aria Operations.
    Active alerts generated by this definition will not be affected.

    Args:
        definition_id: Alert definition UUID to delete.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.alerts import delete_alert_definition as _delete

        return _delete(
            _get_connection(target),
            definition_id=definition_id,
            audit_logger=_audit,
            target_name=_target_name(target),
        )
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT tools (5)
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_report_definitions(
    name_filter: str | None = None,
    limit: int = 100,
    target: str | None = None,
) -> list[dict]:
    """[READ] List available report definition templates in Aria Operations.

    Args:
        name_filter: Optional substring to filter by report name (case-insensitive).
        limit: Maximum number of definitions to return (1–500). Default 100.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.reports import list_report_definitions as _list

        return _list(_get_connection(target), name_filter=name_filter, limit=limit)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def generate_report(
    definition_id: str,
    resource_ids: list[str] | None = None,
    target: str | None = None,
) -> dict:
    """[WRITE] Trigger generation of a report from a report definition template.

    Returns immediately with a report_id and PENDING status.
    Poll get_report(report_id) until status == COMPLETED, then use download_url.

    Args:
        definition_id: Report definition (template) UUID from list_report_definitions.
        resource_ids: Optional list of resource UUIDs to scope the report.
            If omitted, the report runs against all resources in the template scope.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.reports import generate_report as _generate

        return _generate(
            _get_connection(target),
            definition_id=definition_id,
            resource_ids=resource_ids,
            audit_logger=_audit,
            target_name=_target_name(target),
        )
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_reports(
    definition_id: str | None = None,
    limit: int = 50,
    target: str | None = None,
) -> list[dict]:
    """[READ] List generated reports, optionally filtered by report definition.

    Args:
        definition_id: Optional report definition UUID to filter results.
        limit: Maximum number of reports to return (1–200). Default 50.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.reports import list_reports as _list

        return _list(_get_connection(target), definition_id=definition_id, limit=limit)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_report(
    report_id: str,
    target: str | None = None,
) -> dict:
    """[READ] Get status and download URLs for a generated report.

    Args:
        report_id: The report UUID (from generate_report or list_reports).
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.reports import get_report as _get

        return _get(_get_connection(target), report_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def delete_report(
    report_id: str,
    target: str | None = None,
) -> dict:
    """[WRITE] Delete a generated report from Aria Operations.

    Args:
        report_id: The report UUID to delete.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.reports import delete_report as _delete

        return _delete(
            _get_connection(target),
            report_id=report_id,
            audit_logger=_audit,
            target_name=_target_name(target),
        )
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


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
