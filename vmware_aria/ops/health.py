"""Aria Operations platform health: node status and collector group status.

All API responses pass through sanitize() to strip control characters and limit length.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vmware_policy import sanitize

if TYPE_CHECKING:
    from vmware_aria.connection import AriaClient

_log = logging.getLogger("vmware-aria.ops.health")


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
            "name": sanitize(s.get("name", "")),
            "status": sanitize(s.get("status", {}).get("state", "")),
            "health": sanitize(s.get("status", {}).get("health", "")),
            "message": sanitize(s.get("status", {}).get("statusMessage", ""), max_len=300),
        }
        for s in services
    ]

    unhealthy = [s for s in service_statuses if s["status"] != "RUNNING"]

    return {
        "node_type": sanitize(data.get("nodeType", "")),
        "node_address": sanitize(data.get("nodeAddress", "")),
        "overall_status": sanitize(data.get("clusterStatus", {}).get("clusterVipAddress", "")),
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
            "id": sanitize(g.get("id", "")),
            "name": sanitize(g.get("name", "")),
            "description": sanitize(g.get("description", ""), max_len=300),
            "collector_count": len(g.get("collectors", [])),
            "collectors": [
                {
                    "id": sanitize(c.get("id", "")),
                    "name": sanitize(c.get("name", "")),
                    "state": sanitize(c.get("state", "")),
                    "type": sanitize(c.get("collectorType", "")),
                    "host": sanitize(c.get("hostname", "")),
                }
                for c in g.get("collectors", [])
            ],
        }
        for g in groups
    ]
