
"""
Survivors Network — Privacy Boundary
File: privacy_boundary.py

Defines separate permissions for:
    RESOURCE_CRAWLER
    MPC_NODE_A
    MPC_NODE_B
    PARTICIPANT_DEVICE

The crawler receives public resource metadata only.
MPC nodes receive their own mathematical shares only.
The participant device retains identity-to-session mapping.

This module is a schema and permission gate, not an OS-level
security boundary. Production deployment must isolate services.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class PrivacyBoundaryError(Exception):
    pass


class ServiceRole(str, Enum):
    RESOURCE_CRAWLER = "resource_crawler"
    MPC_NODE_A = "mpc_node_a"
    MPC_NODE_B = "mpc_node_b"
    PARTICIPANT_DEVICE = "participant_device"


RESOURCE_FIELDS = frozenset({
    "organization_name",
    "public_url",
    "public_phone",
    "public_email",
    "public_address",
    "service_category",
    "service_area",
    "source_timestamp",
    "verification_status",
})

MPC_SHARE_FIELDS = frozenset({
    "protocol_version",
    "session_id",
    "dimensions",
    "share_values",
    "expires_at",
    "message_id",
})

IDENTITY_FIELDS = frozenset({
    "name",
    "full_name",
    "first_name",
    "last_name",
    "email",
    "phone",
    "address",
    "date_of_birth",
    "ip_address",
    "survivor_id",
    "participant_name",
    "participant_id",
    "trauma_history",
    "case_notes",
    "diagnosis",
    "private_message",
    "password",
    "identity",
})


@dataclass(frozen=True)
class BoundaryDecision:
    allowed: bool
    reason: str


class PrivacyBoundary:

    def __init__(self):
        self._blocked_transitions = {
            (
                ServiceRole.RESOURCE_CRAWLER,
                ServiceRole.MPC_NODE_A,
            ),
            (
                ServiceRole.RESOURCE_CRAWLER,
                ServiceRole.MPC_NODE_B,
            ),
            (
                ServiceRole.MPC_NODE_A,
                ServiceRole.RESOURCE_CRAWLER,
            ),
            (
                ServiceRole.MPC_NODE_B,
                ServiceRole.RESOURCE_CRAWLER,
            ),
        }

    def authorize_transition(
        self,
        sender: ServiceRole,
        recipient: ServiceRole,
    ) -> BoundaryDecision:

        if (sender, recipient) in self._blocked_transitions:
            return BoundaryDecision(
                False,
                "Cross-domain access is prohibited",
            )

        if sender == recipient:
            return BoundaryDecision(
                True,
                "Same-domain operation",
            )

        if sender == ServiceRole.RESOURCE_CRAWLER:
            if recipient != ServiceRole.RESOURCE_CRAWLER:
                return BoundaryDecision(
                    False,
                    "Crawler cannot communicate with private matching services",
                )

        return BoundaryDecision(
            False,
            "Transition requires an explicitly authorized protocol",
        )

    @staticmethod
    def _reject_identity_fields(value: Any, depth: int = 0):
        if depth > 8:
            raise PrivacyBoundaryError("Payload nesting too deep")

        if isinstance(value, dict):
            for key, child in value.items():
                normalized = str(key).strip().lower()

                if normalized in IDENTITY_FIELDS:
                    raise PrivacyBoundaryError(
                        "Identity-bearing field prohibited"
                    )

                PrivacyBoundary._reject_identity_fields(
                    child, depth + 1
                )

        elif isinstance(value, (list, tuple)):
            for child in value:
                PrivacyBoundary._reject_identity_fields(
                    child, depth + 1
                )

    def validate_resource_record(self, record: dict) -> dict:
        """
        Validate public directory data before crawler storage.

        Unknown fields are rejected rather than silently retained.
        """

        if not isinstance(record, dict):
            raise PrivacyBoundaryError("Resource record must be an object")

        if not set(record).issubset(RESOURCE_FIELDS):
            raise PrivacyBoundaryError("Unapproved resource field")

        self._reject_identity_fields(record)

        if not record.get("organization_name"):
            raise PrivacyBoundaryError("Organization name is required")

        if not record.get("public_url"):
            raise PrivacyBoundaryError("Public URL is required")

        return dict(record)

    def validate_mpc_share(
        self,
        share: dict,
        receiving_role: ServiceRole,
    ) -> dict:
        """
        Validate a single MPC share for its designated node.

        A crawler is never an allowed recipient.
        """

        if receiving_role not in {
            ServiceRole.MPC_NODE_A,
            ServiceRole.MPC_NODE_B,
        }:
            raise PrivacyBoundaryError(
                "Only an authorized MPC node may receive a share"
            )

        if not isinstance(share, dict):
            raise PrivacyBoundaryError("Share must be an object")

        if set(share) != MPC_SHARE_FIELDS:
            raise PrivacyBoundaryError("Unexpected MPC share fields")

        self._reject_identity_fields(share)

        values = share["share_values"]
        dimensions = share["dimensions"]

        if (
            isinstance(dimensions, bool)
            or not isinstance(dimensions, int)
            or not 1 <= dimensions <= 256
        ):
            raise PrivacyBoundaryError("Invalid share dimensions")

        if not isinstance(values, list) or len(values) != dimensions:
            raise PrivacyBoundaryError("Share dimension mismatch")

        for value in values:
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise PrivacyBoundaryError("Invalid share value")

        if not isinstance(share["session_id"], str):
            raise PrivacyBoundaryError("Invalid session identifier")

        if not isinstance(share["message_id"], str):
            raise PrivacyBoundaryError("Invalid message identifier")

        return dict(share)

    def crawler_can_access_matching(self) -> bool:
        return False

    def matching_can_access_directory_private_records(self) -> bool:
        return False
