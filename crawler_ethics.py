
"""
Survivors Network — Crawler Ethics Kernel
File: crawler_ethics.py

The crawler is restricted to public resource discovery and verification.

It must never:
- Receive survivor records or trauma vectors.
- Receive MPC secret shares or matching results.
- Collect personal identities or participant contact details.
- Access private messages or account-only content.
- Expand its own domain or action permissions.
- Execute functions supplied by remote peers.

This module is an application-level policy gate.
Run the crawler in a separate process/service with separate credentials.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlsplit


ALLOWED_ACTIONS = frozenset({
    "discover",
    "verify",
    "update",
})

ALLOWED_RESOURCE_FIELDS = frozenset({
    "organization_name",
    "public_url",
    "public_phone",
    "public_email",
    "public_address",
    "service_category",
    "service_area",
    "source_timestamp",
    "source_url",
    "verification_status",
})

FORBIDDEN_FIELD_NAMES = frozenset({
    "name",
    "full_name",
    "first_name",
    "last_name",
    "survivor_name",
    "participant_name",
    "trauma",
    "trauma_history",
    "diagnosis",
    "medical_history",
    "case_notes",
    "private_message",
    "email",
    "phone",
    "address",
    "date_of_birth",
    "ip_address",
    "password",
    "identity",
    "contact_details",
    "vector",
    "secret_share",
    "matching_share",
    "match_score",
    "session_token",
    "participant_id",
})


class EthicsViolation(Exception):
    pass


@dataclass(frozen=True)
class CrawlerPolicy:
    node_id: str
    allowed_domains: frozenset[str]
    enabled: bool = True
    requests_per_minute: int = 12
    max_job_depth: int = 1
    max_payload_fields: int = 16

    def __post_init__(self):
        if not self.node_id:
            raise ValueError("A node ID is required")

        if not self.allowed_domains:
            raise ValueError("At least one authorized domain is required")

        if self.requests_per_minute < 1:
            raise ValueError("Rate limit must be positive")

        if self.max_job_depth < 0:
            raise ValueError("Invalid maximum job depth")


@dataclass(frozen=True)
class ApprovedJob:
    action: str
    node_id: str
    url: str
    depth: int
    request_id: str


class EthicsKernel:

    def __init__(self, policy: CrawlerPolicy):
        self.policy = policy
        self.emergency_stop = False
        self.handlers: dict[str, Callable] = {}
        self.request_history: dict[str, list[float]] = {}

    def register_handler(self, action: str, handler: Callable):
        if action not in ALLOWED_ACTIONS:
            raise EthicsViolation("Action is not permitted")

        if not callable(handler):
            raise TypeError("Handler must be callable")

        if action in self.handlers:
            raise EthicsViolation("Handler already registered")

        self.handlers[action] = handler

    def stop(self):
        """Local emergency stop."""
        self.emergency_stop = True

    def resume(self, *, local_admin_authorized: bool):
        """
        A remote job cannot resume a stopped crawler.
        Production should additionally require authenticated admin access.
        """
        if local_admin_authorized is not True:
            raise EthicsViolation("Local administrator authorization required")

        if not self.policy.enabled:
            raise EthicsViolation("Crawler policy remains disabled")

        self.emergency_stop = False

    @staticmethod
    def _contains_forbidden_fields(value, depth=0):
        if depth > 8:
            return True

        if isinstance(value, dict):
            for key, child in value.items():
                normalized = str(key).strip().lower()

                if normalized in FORBIDDEN_FIELD_NAMES:
                    return True

                if EthicsKernel._contains_forbidden_fields(
                    child, depth + 1
                ):
                    return True

        elif isinstance(value, (list, tuple)):
            for child in value:
                if EthicsKernel._contains_forbidden_fields(
                    child, depth + 1
                ):
                    return True

        return False

    def _validate_url(self, url: str):
        if not isinstance(url, str) or len(url) > 2048:
            raise EthicsViolation("Invalid URL")

        try:
            parsed = urlsplit(url)
            host = (parsed.hostname or "").lower().rstrip(".")
        except Exception as exc:
            raise EthicsViolation("Malformed URL") from exc

        if parsed.scheme != "https":
            raise EthicsViolation("HTTPS is required")

        if not host:
            raise EthicsViolation("Missing hostname")

        if parsed.username or parsed.password:
            raise EthicsViolation("Embedded credentials prohibited")

        if parsed.port not in (None, 443):
            raise EthicsViolation("Nonstandard port prohibited")

        allowed = {
            domain.lower().rstrip(".")
            for domain in self.policy.allowed_domains
        }

        if not any(
            host == domain or host.endswith("." + domain)
            for domain in allowed
        ):
            raise EthicsViolation("Domain outside authorized scope")

        return host

    def validate(self, payload: dict) -> ApprovedJob:
        """
        Validate metadata only.

        Never accept a callable or executable code from a peer.
        """

        if self.emergency_stop:
            raise EthicsViolation("Emergency stop active")

        if not self.policy.enabled:
            raise EthicsViolation("Crawler disabled")

        if not isinstance(payload, dict):
            raise EthicsViolation("Payload must be an object")

        allowed_keys = {
            "action",
            "node_id",
            "url",
            "depth",
            "request_id",
        }

        if set(payload) != allowed_keys:
            raise EthicsViolation("Unexpected or missing job fields")

        if self._contains_forbidden_fields(payload):
            raise EthicsViolation("Sensitive data prohibited")

        action = payload["action"]

        if action not in ALLOWED_ACTIONS:
            raise EthicsViolation("Unauthorized action")

        if action not in self.handlers:
            raise EthicsViolation("No local handler registered")

        if payload["node_id"] != self.policy.node_id:
            raise EthicsViolation("Node identity mismatch")

        depth = payload["depth"]

        if (
            isinstance(depth, bool)
            or not isinstance(depth, int)
            or depth < 0
            or depth > self.policy.max_job_depth
        ):
            raise EthicsViolation("Invalid job depth")

        request_id = payload["request_id"]

        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
            raise EthicsViolation("Invalid request ID")

        self._validate_url(payload["url"])

        return ApprovedJob(
            action=action,
            node_id=self.policy.node_id,
            url=payload["url"],
            depth=depth,
            request_id=request_id,
        )

    def _reserve_rate_slot(self, url: str):
        """
        Reserve only when execution is about to begin.
        Use monotonic time to avoid wall-clock changes.
        """
        host = urlsplit(url).hostname.lower()
        now = time.monotonic()

        history = self.request_history.setdefault(host, [])

        history[:] = [
            stamp for stamp in history
            if now - stamp < 60
        ]

        if len(history) >= self.policy.requests_per_minute:
            raise EthicsViolation("Domain rate limit reached")

        history.append(now)

    def execute(self, payload: dict):
        """
        Resolve the action to a trusted local handler.
        Remote peers cannot supply executable functions.
        """

        try:
            job = self.validate(payload)
            self._reserve_rate_slot(job.url)

            handler = self.handlers[job.action]

            result = handler(
                url=job.url,
                request_id=job.request_id,
            )

            return {
                "success": True,
                "executed": True,
                "request_id": job.request_id,
                "result": result,
            }

        except EthicsViolation as exc:
            return {
                "success": False,
                "executed": False,
                "reason": str(exc),
            }

        except Exception as exc:
            # Avoid exposing internal data or exception details.
            return {
                "success": False,
                "executed": False,
                "reason": f"Execution failed: {type(exc).__name__}",
            }
