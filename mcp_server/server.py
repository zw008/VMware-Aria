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


import logging
import os
from pathlib import Path
from typing import Any, Optional

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

_conn_mgr: Optional[ConnectionManager] = None


def _get_connection(target: Optional[str] = None) -> Any:
    """Return an AriaClient, lazily initialising the connection manager."""
    global _conn_mgr  # noqa: PLW0603
    if _conn_mgr is None:
        config_path_str = os.environ.get("VMWARE_ARIA_CONFIG")
        config_path = Path(config_path_str) if config_path_str else None
        config = load_config(config_path)
        _conn_mgr = ConnectionManager(config)
    return _conn_mgr.connect(target)


def _target_name(target: Optional[str]) -> str:
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
    name_filter: Optional[str] = None,
    target: Optional[str] = None,
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
def get_resource(resource_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get full details for one resource by UUID, including health, risk, and efficiency badges (each a color plus 0-100 score), resource kind, adapter kind, identifiers, and status states. Use after list_resources to inspect a single resource in depth; use list_resources (not this tool) to discover UUIDs by kind or name. For just the health score use get_resource_health; for time-series metrics use get_resource_metrics.

    Args:
        resource_id: The resource UUID (from list_resources).
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
    target: Optional[str] = None,
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
def get_resource_health(resource_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get the health, risk, and efficiency badge scores for a resource.

    Badges come from the resource's badges[] array. Scores are 0–100
    (higher = healthier for HEALTH; -1 = unknown) with a color per badge.

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
    target: Optional[str] = None,
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
    criticality: Optional[str] = None,
    resource_id: Optional[str] = None,
    limit: int = 100,
    target: Optional[str] = None,
) -> list[dict]:
    """[READ] List alerts from Aria Operations.

    Returns alert summaries: name (from alertDefinitionName), criticality
    (from alertLevel), status, impact, resource_id, timestamps, and control
    state. The Alert model has no resource name field — resolve it via
    get_resource(resource_id).

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
def get_alert(alert_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get full details for one alert by UUID, including its contributing (triggered) symptoms fetched from the alerts/contributingsymptoms endpoint. Use after list_alerts to drill into a single alert; use list_alerts (not this tool) to discover or filter alerts. Returns one alert object: name (from alertDefinitionName), criticality (from alertLevel), status, impact, resource_id, start/update/cancel timestamps, control state, and symptoms. The Alert model carries no resource name — resolve it via get_resource(resource_id). Recommendations hang off the alert definition, not the alert. To act on the alert afterwards, use acknowledge_alert or cancel_alert.

    Args:
        alert_id: The alert UUID (from list_alerts).
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.alerts import get_alert as _get

        return _get(_get_connection(target), alert_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def acknowledge_alert(alert_id: str, confirmed: bool = False, target: Optional[str] = None) -> dict:
    """[WRITE] Acknowledge an active alert by taking ownership (does not cancel it).

    The suite-api has no dedicated "acknowledge" action; this maps to
    POST /alerts?action=takeownership, assigning the alert to the API user
    (control state ASSIGNED). The alert remains active until cancelled.
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
def cancel_alert(alert_id: str, confirmed: bool = False, target: Optional[str] = None) -> dict:
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
    name_filter: Optional[str] = None,
    limit: int = 100,
    target: Optional[str] = None,
) -> list[dict]:
    """[READ] List alert definitions (templates that generate alerts when triggered).

    criticality is the max severity across the definition's states[] (the
    AlertDefinition model has no top-level criticality or enabled field).

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
def get_capacity_overview(cluster_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get a capacity overview for a cluster — the group-level remaining-capacity percentage (capacity_remaining_pct; the percentage metric only exists at group level) plus per-dimension (cpu/mem/diskspace) absolute remaining capacity and projected days-until-full, from the OnlineCapacityAnalytics metrics. Values are None while capacity analytics are still warming up on a fresh instance. Start here when assessing overall cluster capacity health; for absolute headroom values use get_remaining_capacity, and for just the exhaustion projections use get_time_remaining.

    Args:
        cluster_id: The cluster resource UUID (ClusterComputeResource, from list_resources).
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.capacity import get_capacity_overview as _get

        return _get(_get_connection(target), cluster_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_remaining_capacity(resource_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get remaining capacity headroom for a cluster or host — how much more workload fits before hitting limits. Returns the group-level capacity_remaining_pct (the percentage metric only exists at group level) plus one entry per capacity dimension (cpu, mem, diskspace) with remaining_value (absolute, unit per dimension e.g. MHz/KB), from the OnlineCapacityAnalytics demand model. Values are None while capacity analytics warm up. Use get_capacity_overview for the combined view, or get_time_remaining for projected days-until-full.

    Args:
        resource_id: The resource UUID — a ClusterComputeResource or HostSystem (from list_resources).
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.capacity import get_remaining_capacity as _get

        return _get(_get_connection(target), resource_id)
    except Exception as e:
        return {"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_time_remaining(resource_id: str, target: Optional[str] = None) -> dict:
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
    resource_id: Optional[str] = None,
    limit: int = 50,
    target: Optional[str] = None,
) -> list[dict]:
    """[READ] List VM rightsizing data — recommended CPU/memory size per VM.

    Reads the OnlineCapacityAnalytics recommendedSize metrics (the public
    API's rightsizing signal; the UI Rightsize page uses internal APIs).
    Compare against the VM's provisioned size to find over/under-provisioning.
    Values are None while capacity analytics warm up. One stats call per VM —
    keep limit modest.

    Args:
        resource_id: Optional VM resource UUID to scope to a single VM.
        limit: Maximum VMs to evaluate when listing (1–100). Default 50.
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
    resource_id: Optional[str] = None,
    limit: int = 50,
    target: Optional[str] = None,
) -> list[dict]:
    """[READ] Report per-resource anomaly counts (System Attributes|total_alarms metric).

    The public suite-api does not expose the UI's anomalous-metrics list; this
    returns the Total Anomalies metric — active anomalies (symptoms, events,
    DT violations) on the object and its children. With
    resource_id: that resource's count. Without: scans up to `limit` VMs and
    returns those with non-zero counts, sorted descending. For root cause,
    follow up with list_alerts(resource_id=...). One stats call per VM when
    listing — keep limit modest.

    Args:
        resource_id: Optional resource UUID to scope to a single resource.
        limit: Maximum VMs to scan when listing (1–100). Default 50.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    try:
        from vmware_aria.ops.anomaly import list_anomalies as _list

        return _list(_get_connection(target), resource_id=resource_id, limit=limit)
    except Exception as e:
        return [{"error": str(e), "hint": "Run 'vmware-aria doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_resource_riskbadge(resource_id: str, target: Optional[str] = None) -> dict:
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
def get_aria_health(target: Optional[str] = None) -> dict:
    """[READ] Check Aria Operations platform node status (ONLINE/OFFLINE).

    Returns overall_status ("ONLINE" when all internal services run, else
    "OFFLINE" — the endpoint itself answers 503 when offline), healthy bool,
    system_time_ms, and details. Use this to verify Aria Operations is
    functioning before investigating monitoring blind spots; per-service
    breakdown is not exposed by the public API.

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
def list_collector_groups(target: Optional[str] = None) -> list[dict]:
    """[READ] List Aria Operations collector groups and their member collector status.

    Collectors are remote agents that gather metrics from vSphere and other adapters.
    Check this when resources appear missing from Aria Operations or metrics are stale.
    Groups list member collector IDs; details (name, state UP/DOWN, local) are
    enriched via one extra collectors call.

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
    name_filter: Optional[str] = None,
    resource_kind: Optional[str] = None,
    limit: int = 100,
    target: Optional[str] = None,
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
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Create a new alert definition referencing existing symptom definitions.

    Use list_symptom_definitions() to find symptom_definition_ids.

    Args:
        name: Alert definition name (must be unique in Aria Operations).
        description: Human-readable description of when/why this alert fires.
        resource_kind: Resource kind this alert applies to: VirtualMachine,
            HostSystem, ClusterComputeResource, Datastore.
        symptom_definition_ids: List of symptom definition UUIDs. Any one
            symptom firing triggers (OR across symptom ids).
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
    target: Optional[str] = None,
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
    confirmed: bool = False,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Permanently delete an alert definition. Irreversible.

    This WRITE operation removes the alert definition from Aria Operations.
    Active alerts generated by this definition will not be affected.
    Default confirmed=False returns a preview without making any change.

    Args:
        definition_id: Alert definition UUID to delete.
        confirmed: Must be True to actually delete. Default False = preview only.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    if not confirmed:
        return {
            "preview": True,
            "action": "delete_alert_definition",
            "definition_id": definition_id,
            "message": (
                f"[preview] Would permanently delete alert definition {definition_id}. "
                "Re-invoke with confirmed=True to execute."
            ),
        }
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
    name_filter: Optional[str] = None,
    limit: int = 100,
    target: Optional[str] = None,
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
    resource_ids: Optional[list[str]] = None,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Trigger generation of a report from a report definition template.

    Returns immediately with a report_id and PENDING status.
    Poll get_report(report_id) until status == COMPLETED, then use download_url.

    Args:
        definition_id: Report definition (template) UUID from list_report_definitions.
        resource_ids: REQUIRED — at least one resource UUID. The Report API
            generates against a single root resource (first ID is used); pass
            a cluster/datacenter UUID to cover its children. Find IDs via
            list_resources.
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
    definition_id: Optional[str] = None,
    limit: int = 50,
    target: Optional[str] = None,
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
    target: Optional[str] = None,
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
    confirmed: bool = False,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Permanently delete a generated report artifact from Aria Operations. Removes only the generated report instance and its downloadable output — the report definition and any schedules remain intact; re-run generate_report to recreate it. Deletion is irreversible and is recorded in the local audit log (~/.vmware/audit.db). Returns an error if the report_id does not exist; use list_reports to find valid UUIDs first. Default confirmed=False returns a preview without deleting.

    Args:
        report_id: The report UUID to delete (from generate_report or list_reports).
        confirmed: Must be True to actually delete. Default False = preview only.
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    if not confirmed:
        return {
            "preview": True,
            "action": "delete_report",
            "report_id": report_id,
            "message": (
                f"[preview] Would permanently delete report {report_id}. "
                "Re-invoke with confirmed=True to execute."
            ),
        }
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
