"""ALERT read tools (4, read-only).

list_alerts, get_alert, list_alert_definitions, list_symptom_definitions.

The write/destructive alert tools (acknowledge_alert, cancel_alert,
create_alert_definition, set_alert_definition_state, delete_alert_definition)
keep their definitions in ``mcp_server/server.py`` because their confirmed-gate
preview contract is asserted there by AST inspection in
``tests/test_no_destructive_ops.py``.
"""

from typing import Optional

from vmware_policy import vmware_tool

from mcp_server._shared import mcp


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
    from mcp_server import server

    try:
        from vmware_aria.ops.alerts import list_alerts as _list

        return _list(server._get_connection(target), active_only=active_only, criticality=criticality, resource_id=resource_id, limit=limit)
    except Exception as e:
        return [{"error": server._safe_error(e, "list_alerts"), "hint": "Run 'vmware-aria doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_alert(alert_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get full details for one alert by UUID, including its contributing (triggered) symptoms fetched from the alerts/contributingsymptoms endpoint. Use after list_alerts to drill into a single alert; use list_alerts (not this tool) to discover or filter alerts. Returns one alert object: name (from alertDefinitionName), criticality (from alertLevel), status, impact, resource_id, start/update/cancel timestamps, control state, and symptoms. The Alert model carries no resource name — resolve it via get_resource(resource_id). Recommendations hang off the alert definition, not the alert. To act on the alert afterwards, use acknowledge_alert or cancel_alert.

    Args:
        alert_id: The alert UUID (from list_alerts).
        target: Optional Aria Operations target name from config. Uses default if omitted.
    """
    from mcp_server import server

    try:
        from vmware_aria.ops.alerts import get_alert as _get

        return _get(server._get_connection(target), alert_id)
    except Exception as e:
        return {"error": server._safe_error(e, "get_alert"), "hint": "Run 'vmware-aria doctor' to verify connectivity."}


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
    from mcp_server import server

    try:
        from vmware_aria.ops.alerts import list_alert_definitions as _list

        return _list(server._get_connection(target), name_filter=name_filter, limit=limit)
    except Exception as e:
        return [{"error": server._safe_error(e, "list_alert_definitions"), "hint": "Run 'vmware-aria doctor' to verify connectivity."}]


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
    from mcp_server import server

    try:
        from vmware_aria.ops.alerts import list_symptom_definitions as _list

        return _list(server._get_connection(target), name_filter=name_filter, resource_kind=resource_kind, limit=limit)
    except Exception as e:
        return [{"error": server._safe_error(e, "list_symptom_definitions"), "hint": "Run 'vmware-aria doctor' to verify connectivity."}]
