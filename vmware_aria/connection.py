"""Aria Operations REST API client with token-based authentication.

Authenticates via POST /suite-api/api/auth/token/acquire with username/password/authSource.
Stores the OpsToken and refreshes it automatically when it expires (30-minute validity).

Base URL pattern: https://<aria-host>/suite-api/api/
"""

from __future__ import annotations

import logging
import time
import warnings
from typing import Any

import httpx

from vmware_aria.config import AppConfig, TargetConfig, load_config

_log = logging.getLogger("vmware-aria.connection")

# Token validity buffer: refresh 60 seconds before actual expiry
_EXPIRY_BUFFER_SEC = 60


class AriaClient:
    """REST client for a single Aria Operations instance."""

    def __init__(self, target: TargetConfig, password: str) -> None:
        self._target = target
        self._base_url = f"https://{target.host}:{target.port}/suite-api/api"
        self._password = password
        self._token: str | None = None
        # Epoch seconds when the token expires
        self._token_expires_at: float = 0.0

        # Suppress InsecureRequestWarning for self-signed certs
        if not target.verify_ssl:
            warnings.filterwarnings("ignore", message="Unverified HTTPS request")

        self._client = httpx.Client(
            base_url=self._base_url,
            verify=target.verify_ssl,
            timeout=30.0,
        )
        self._acquire_token()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _acquire_token(self) -> None:
        """Acquire a new OpsToken from Aria Operations."""
        url = f"{self._base_url}/auth/token/acquire"
        payload = {
            "username": self._target.username,
            "password": self._password,
            "authSource": self._target.auth_source,
        }
        resp = self._client.post(url, json=payload, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()

        token = data.get("token")
        if not token:
            raise ConnectionError(
                "Aria Operations token acquisition succeeded but no token returned"
            )

        # validity is in milliseconds
        validity_ms = data.get("validity", 1_800_000)
        self._token = token
        self._token_expires_at = time.time() + (validity_ms / 1000.0)
        _log.info("Aria Operations token acquired for %s (valid %.0fs)", self._target.host, validity_ms / 1000.0)

    def _ensure_token(self) -> None:
        """Re-acquire token if expired or near expiry."""
        if time.time() >= (self._token_expires_at - _EXPIRY_BUFFER_SEC):
            _log.info("Token expired or near expiry, re-acquiring...")
            self._acquire_token()

    def _headers(self) -> dict[str, str]:
        """Request headers with OpsToken authorization."""
        self._ensure_token()
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"OpsToken {self._token}",
        }

    # ------------------------------------------------------------------
    # HTTP methods
    # ------------------------------------------------------------------

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """Single GET request. Returns parsed JSON response."""
        resp = self._client.get(path, headers=self._headers(), params=params)
        if resp.status_code in (401, 403):
            _log.info("Auth error on GET, re-acquiring token...")
            self._acquire_token()
            resp = self._client.get(path, headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def post(self, path: str, json_data: dict[str, Any] | None = None) -> dict:
        """POST request. Returns parsed JSON response."""
        resp = self._client.post(path, headers=self._headers(), json=json_data)
        if resp.status_code in (401, 403):
            self._acquire_token()
            resp = self._client.post(path, headers=self._headers(), json=json_data)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def delete(self, path: str) -> None:
        """DELETE request."""
        resp = self._client.delete(path, headers=self._headers())
        if resp.status_code in (401, 403):
            self._acquire_token()
            resp = self._client.delete(path, headers=self._headers())
        resp.raise_for_status()

    def is_alive(self) -> bool:
        """Check if the connection is still valid by probing the deployment endpoint."""
        try:
            self.get("/deployment/node/status")
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Release the OpsToken and close the HTTP client."""
        if self._token:
            try:
                self._client.post(
                    "/auth/token/release",
                    headers=self._headers(),
                    json={"token": self._token},
                )
            except Exception:
                pass
            finally:
                self._token = None
        self._client.close()


class ConnectionManager:
    """Manages connections to multiple Aria Operations targets."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._clients: dict[str, AriaClient] = {}

    @classmethod
    def from_config(cls, config: AppConfig | None = None) -> ConnectionManager:
        """Create a ConnectionManager from config, loading defaults if needed."""
        cfg = config or load_config()
        return cls(cfg)

    def connect(self, target_name: str | None = None) -> AriaClient:
        """Get or create an AriaClient for the specified target."""
        name = target_name or self._config.default_target
        if not name:
            raise ValueError("No target specified and no default target configured")

        if name in self._clients and self._clients[name].is_alive():
            return self._clients[name]

        target_cfg = self._config.get_target(name)
        if target_cfg is None:
            available = ", ".join(self._config.targets.keys())
            raise ValueError(f"Target '{name}' not found. Available: {available}")

        password = target_cfg.get_password(name)
        client = AriaClient(target_cfg, password)
        self._clients[name] = client
        return client

    def disconnect(self, target_name: str) -> None:
        """Close and remove a client."""
        if target_name in self._clients:
            self._clients[target_name].close()
            del self._clients[target_name]

    def disconnect_all(self) -> None:
        """Disconnect from all targets."""
        for name in list(self._clients):
            self.disconnect(name)

    def list_targets(self) -> list[str]:
        """List available target names."""
        return list(self._config.targets.keys())

    def list_connected(self) -> list[str]:
        """List currently connected target names."""
        return list(self._clients.keys())
