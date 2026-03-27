"""Aria Operations platform health: node status and collector group status.

All API responses pass through _sanitize() to strip control characters and limit length.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vmware_aria.connection import AriaClient

_log = logging.getLogger("vmware-aria.ops.health")

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _sanitize(text: str, max_len: int = 500) -> str:
    """Strip control characters and truncate to max_len."""
    if not text:
        return text
    return _CONTROL_CHAR_RE.sub("", text[:max_len])


# ---------------------------------------------------------------------------
# get_aria_health
# ---------------------------------------------------------------------------


def get_aria_health(client: AriaClient) -> dict:
    """Check the health status of the Aria Operations platform itself.

    Queries the deployment node status endpoint to determine if all
    Aria Ops internal services are running correctly.

    Args:
        client: Authenticated Aria Operations API client.

    Returns:
        Dict with overall platform health, service status list, and node info.
    """
    data = client.get("/deployment/node/status")

    services = data.get("services", [])
    service_statuses = [
        {
            "name": _sanitize(s.get("name", "")),
            "status": _sanitize(s.get("status", {}).get("state", "")),
            "health": _sanitize(s.get("status", {}).get("health", "")),
            "message": _sanitize(s.get("status", {}).get("statusMessage", ""), max_len=300),
        }
        for s in services
    ]

    unhealthy = [s for s in service_statuses if s["status"] != "RUNNING"]

    return {
        "node_type": _sanitize(data.get("nodeType", "")),
        "node_address": _sanitize(data.get("nodeAddress", "")),
        "overall_status": _sanitize(data.get("clusterStatus", {}).get("clusterVipAddress", "")),
        "service_count": len(services),
        "unhealthy_services": unhealthy,
        "all_services_healthy": len(unhealthy) == 0,
        "services": service_statuses,
    }


# ---------------------------------------------------------------------------
# list_collector_groups
# ---------------------------------------------------------------------------


def list_collector_groups(client: AriaClient) -> list[dict]:
    """List collector groups and their member collector status.

    Collector groups manage the remote collection agents (vRealize Operations
    Collector) that gather metrics from monitored environments.

    Args:
        client: Authenticated Aria Operations API client.

    Returns:
        List of collector group dicts with name, id, and member collector status.
    """
    data = client.get("/collectorgroups")
    groups = data.get("collectorGroups", [])

    return [
        {
            "id": _sanitize(g.get("id", "")),
            "name": _sanitize(g.get("name", "")),
            "description": _sanitize(g.get("description", ""), max_len=300),
            "collector_count": len(g.get("collectors", [])),
            "collectors": [
                {
                    "id": _sanitize(c.get("id", "")),
                    "name": _sanitize(c.get("name", "")),
                    "state": _sanitize(c.get("state", "")),
                    "type": _sanitize(c.get("collectorType", "")),
                    "host": _sanitize(c.get("hostname", "")),
                }
                for c in g.get("collectors", [])
            ],
        }
        for g in groups
    ]
