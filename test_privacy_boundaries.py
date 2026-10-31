
"""
Survivors Network — Privacy Boundary Tests
File: test_privacy_boundaries.py

Run:
    python test_privacy_boundaries.py
"""

from privacy_boundary import (
    PrivacyBoundary,
    PrivacyBoundaryError,
    ServiceRole,
)


def run_tests():
    boundary = PrivacyBoundary()

    # Public resource metadata is accepted.
    resource = {
        "organization_name": "Example Support Center",
        "public_url": "https://example.org",
        "service_category": "Community support",
        "verification_status": "pending",
    }

    assert boundary.validate_resource_record(resource)

    # Identity-bearing fields are rejected.
    try:
        boundary.validate_resource_record({
            **resource,
            "survivor_id": "person-123",
        })
        raise AssertionError("Identity field was accepted")
    except PrivacyBoundaryError:
        pass

    # Narrative trauma information is rejected.
    try:
        boundary.validate_resource_record({
            **resource,
            "trauma_history": "private narrative",
        })
        raise AssertionError("Trauma field was accepted")
    except PrivacyBoundaryError:
        pass

    # Crawler-to-MPC communication is denied.
    decision = boundary.authorize_transition(
        ServiceRole.RESOURCE_CRAWLER,
        ServiceRole.MPC_NODE_A,
    )

    assert decision.allowed is False

    # MPC-to-crawler communication is denied.
    decision = boundary.authorize_transition(
        ServiceRole.MPC_NODE_A,
        ServiceRole.RESOURCE_CRAWLER,
    )

    assert decision.allowed is False

    # A valid share can be validated for its designated MPC node.
    share = {
        "protocol_version": 1,
        "session_id": "temporary-session",
        "dimensions": 2,
        "share_values": [123456, 789012],
        "expires_at": 2_000_000_000,
        "message_id": "message-001",
    }

    assert boundary.validate_mpc_share(
        share,
        ServiceRole.MPC_NODE_A,
    )

    # The same share cannot be delivered to the crawler.
    try:
        boundary.validate_mpc_share(
            share,
            ServiceRole.RESOURCE_CRAWLER,
        )
        raise AssertionError("Crawler received an MPC share")
    except PrivacyBoundaryError:
        pass

    # Extra fields are rejected.
    try:
        boundary.validate_mpc_share(
            {**share, "participant_name": "Example"},
            ServiceRole.MPC_NODE_A,
        )
        raise AssertionError("Unexpected field was accepted")
    except PrivacyBoundaryError:
        pass

    assert boundary.crawler_can_access_matching() is False
    assert boundary.matching_can_access_directory_private_records() is False

    print("All privacy-boundary tests passed.")


if __name__ == "__main__":
    run_tests()
