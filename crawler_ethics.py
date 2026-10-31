
"""
Survivors Network — Ethics Kernel
Based on Hope Jones's original EthicsKernel concept.

Purpose:
    Enforce ethical and operational boundaries before crawler jobs execute.

Security principle:
    A crawler may not expand its own permissions or inherit
    permissions from another mesh node.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional
from urllib.parse import urlparse
import time


@dataclass
class CrawlerPolicy:
    node_id: str
    allowed_domains: set = field(default_factory=set)
    allowed_actions: set = field(
        default_factory=lambda: {"discover", "verify", "update"}
    )
    allowed_data_types: set = field(
        default_factory=lambda: {
            "organization_name",
            "public_url",
            "public_phone",
            "public_email",
            "public_address",
            "service_category",
            "service_area",
            "source_timestamp",
        }
    )
    requests_per_minute: int = 12
    max_job_depth: int = 2
    enabled: bool = True


class EthicsKernel:

    def __init__(self, policy: CrawlerPolicy):
        self.policy = policy
        self.emergency_stop = False
        self.request_history = {}
        self.registered_handlers = {}

    def register_handler(self, action: str, handler: Callable):
        """Register trusted local execution functions."""
        if action not in self.policy.allowed_actions:
            raise PermissionError("Action is not permitted by policy")

        if not callable(handler):
            raise TypeError("Handler must be callable")

        self.registered_handlers[action] = handler

    def stop(self):
        """Immediately suspend this crawler."""
        self.emergency_stop = True

    def resume(self):
        """Resume only if the node policy remains enabled."""
        if self.policy.enabled:
            self.emergency_stop = False

    def _check_domain(self, url: str):
        try:
            parsed = urlparse(url)

            if parsed.scheme != "https":
                return False, "HTTPS required"

            hostname = (parsed.hostname or "").lower()

            if not hostname:
                return False, "Missing hostname"

            if parsed.username or parsed.password:
                return False, "Embedded URL credentials prohibited"

            allowed = {
                domain.lower().lstrip(".")
                for domain in self.policy.allowed_domains
            }

            if not any(
                hostname == domain or hostname.endswith("." + domain)
                for domain in allowed
            ):
                return False, "Domain outside authorized scope"

            return True, "Domain approved"

        except Exception:
            return False, "Invalid URL"

    def _check_rate(self, domain: str):
        now = time.time()

        history = self.request_history.setdefault(domain, [])

        history[:] = [
            timestamp for timestamp in history
            if now - timestamp < 60
        ]

        if len(history) >= self.policy.requests_per_minute:
            return False, "Domain rate limit reached"

        history.append(now)
        return True, "Rate approved"

    def validate(self, job_payload: dict):
        """Validate a job before any network or storage operation."""

        if self.emergency_stop:
            return False, "Emergency shutdown active"

        if not self.policy.enabled:
            return False, "Crawler disabled"

        if not isinstance(job_payload, dict):
            return False, "Invalid job payload"

        if "compute" not in job_payload:
            return False, "Missing compute function"

        if not callable(job_payload["compute"]):
            return False, "Compute must be callable"

        action = job_payload.get("action")

        if action not in self.policy.allowed_actions:
            return False, "Action not authorized"

        # Only registered local functions may execute.
        if self.registered_handlers.get(action) is not job_payload["compute"]:
            return False, "Unregistered execution function"

        node_id = job_payload.get("node_id")

        if node_id != self.policy.node_id:
            return False, "Node identity mismatch"

        depth = job_payload.get("depth", 0)

        if not isinstance(depth, int) or isinstance(depth, bool):
            return False, "Invalid job depth"

        if depth < 0 or depth > self.policy.max_job_depth:
            return False, "Mesh depth boundary exceeded"

        data_types = job_payload.get("data_types", [])

        if not isinstance(data_types, list):
            return False, "Invalid data type declaration"

        if not set(data_types).issubset(
            self.policy.allowed_data_types
        ):
            return False, "Prohibited data collection"

        url = job_payload.get("url")

        if url:
            approved, reason = self._check_domain(url)

            if not approved:
                return False, reason

            domain = urlparse(url).hostname.lower()

            approved, reason = self._check_rate(domain)

            if not approved:
                return False, reason

        return True, "Approved"

    def execute(self, job_payload: dict):
        """Validate first; execute only after approval."""

        approved, reason = self.validate(job_payload)

        if not approved:
            return {
                "success": False,
                "reason": reason,
                "executed": False,
            }

        try:
            result = job_payload["compute"]()

            return {
                "success": True,
                "reason": "Approved",
                "executed": True,
                "result": result,
            }

        except Exception as exc:
            return {
                "success": False,
                "reason": f"Execution failed: {type(exc).__name__}",
                "executed": False,
            }
