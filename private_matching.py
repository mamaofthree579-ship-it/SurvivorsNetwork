
"""
Survivors Network — Private Mathematical Matching
File: private_matching.py

Two-party additive secret sharing with Beaver triples.

Design:
    Participant device:
        - Converts consented answers to numeric values.
        - Secret-shares the vector.
        - Reconstructs the final distance locally.

    Computation node A:
        - Receives only share A.
        - Never receives the original vector.

    Computation node B:
        - Receives only share B.
        - Never receives the original vector.

    Nodes:
        - Jointly calculate squared Euclidean distance.
        - Exchange only masked intermediate values.
        - Never reconstruct the final distance.

Security assumptions:
    - Nodes A and B do not collude.
    - Each Beaver triple is used exactly once.
    - Transport is authenticated and encrypted.
    - Triple provisioning is secure.
    - Participants explicitly opt in.
    - No survivor identity or narrative is transmitted.

This is a prototype MPC implementation.
It is not independently audited or production certified.
"""

from __future__ import annotations

import secrets
import time
import uuid

from dataclasses import dataclass
from typing import List, Tuple


# A prime modulus suitable for this prototype.
PRIME = (2**61) - 1

# Each input component is represented as an integer from 0 to 1000.
INPUT_SCALE = 1000

MAX_DIMENSIONS = 256

# Ensure maximum possible squared distance remains below PRIME / 2.
MAX_DISTANCE = MAX_DIMENSIONS * INPUT_SCALE**2

if MAX_DISTANCE >= PRIME // 2:
    raise RuntimeError("Numeric range exceeds safe modulus boundary")


class PrivateMatchingError(Exception):
    pass


class ConsentRequired(PrivateMatchingError):
    pass


class ProtocolError(PrivateMatchingError):
    pass


@dataclass(frozen=True)
class VectorShare:
    """
    One participant's share of a numeric vector.

    Node A and node B receive separate instances.
    Neither instance independently reveals the original vector.
    """

    session_id: str
    dimensions: int
    values: Tuple[int, ...]

    def __post_init__(self):
        if not self.session_id:
            raise ProtocolError("Missing session ID")

        if self.dimensions != len(self.values):
            raise ProtocolError("Dimension mismatch")

        if not 1 <= self.dimensions <= MAX_DIMENSIONS:
            raise ProtocolError("Invalid vector dimensions")

        for value in self.values:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ProtocolError("Share values must be integers")

            if not 0 <= value < PRIME:
                raise ProtocolError("Share outside modulus")


@dataclass(frozen=True)
class BeaverTripleShare:
    """
    One node's share of a Beaver multiplication triple.

    The underlying triple satisfies c = a * b mod PRIME.

    Each triple must be consumed once and never reused.
    """

    a: int
    b: int
    c: int

    def __post_init__(self):
        for value in (self.a, self.b, self.c):
            if not isinstance(value, int) or not 0 <= value < PRIME:
                raise ProtocolError("Invalid triple share")


@dataclass(frozen=True)
class MaskShare:
    """
    Local masked values produced by one computation node.
    """

    d: int
    e: int


def _random_field_element() -> int:
    return secrets.randbelow(PRIME)


def _split_secret(value: int) -> Tuple[int, int]:
    """
    Split one field element into two additive shares.
    """
    value %= PRIME
    first = _random_field_element()
    second = (value - first) % PRIME

    return first, second


def _reconstruct(first: int, second: int) -> int:
    """
    Reconstruct a field element.

    This operation belongs on the participant device,
    not on either computation node.
    """
    return (first + second) % PRIME


def encode_vector(values: List[float]) -> Tuple[int, ...]:
    """
    Convert normalized input values into fixed-point integers.

    The mapping from actual answers to vector positions must remain
    local to the participant's device.

    Do not transmit the mapping or variable descriptions.
    """

    if not isinstance(values, list):
        raise ProtocolError("Expected a numeric list")

    if not 1 <= len(values) <= MAX_DIMENSIONS:
        raise ProtocolError("Invalid vector length")

    encoded = []

    for value in values:
        if isinstance(value, bool):
            raise ProtocolError("Boolean inputs are prohibited")

        if not isinstance(value, (int, float)):
            raise ProtocolError("Numeric input required")

        if not 0.0 <= float(value) <= 1.0:
            raise ProtocolError("Input must be normalized between 0 and 1")

        encoded.append(round(float(value) * INPUT_SCALE))

    return tuple(encoded)


def create_vector_shares(
    values: List[float],
    *,
    consent: bool,
) -> Tuple[VectorShare, VectorShare]:
    """
    Run on the participant's device.

    Returns one share for node A and one for node B.

    Neither node receives the original numeric vector.
    """

    if consent is not True:
        raise ConsentRequired("Explicit opt-in is required")

    encoded = encode_vector(values)

    session_id = secrets.token_urlsafe(24)

    shares_a = []
    shares_b = []

    for value in encoded:
        a, b = _split_secret(value)
        shares_a.append(a)
        shares_b.append(b)

    return (
        VectorShare(
            session_id=session_id,
            dimensions=len(encoded),
            values=tuple(shares_a),
        ),
        VectorShare(
            session_id=session_id,
            dimensions=len(encoded),
            values=tuple(shares_b),
        ),
    )


def generate_beaver_triples(
    count: int,
) -> Tuple[
    Tuple[BeaverTripleShare, ...],
    Tuple[BeaverTripleShare, ...],
]:
    """
    Generate independent Beaver triples for two nodes.

    This function represents a trusted offline triple dealer.

    The dealer generates random triples independently of participant
    inputs. In deployment, each node receives only its own shares.

    Never regenerate or reuse a triple for another multiplication.
    """

    if not isinstance(count, int) or isinstance(count, bool):
        raise ProtocolError("Invalid triple count")

    if not 1 <= count <= MAX_DIMENSIONS:
        raise ProtocolError("Invalid triple count")

    triples_a = []
    triples_b = []

    for _ in range(count):
        a = _random_field_element()
        b = _random_field_element()
        c = (a * b) % PRIME

        a0, a1 = _split_secret(a)
        b0, b1 = _split_secret(b)
        c0, c1 = _split_secret(c)

        triples_a.append(
            BeaverTripleShare(a=a0, b=b0, c=c0)
        )

        triples_b.append(
            BeaverTripleShare(a=a1, b=b1, c=c1)
        )

    return tuple(triples_a), tuple(triples_b)


def prepare_mask_share(
    x_share: int,
    triple: BeaverTripleShare,
) -> MaskShare:
    """
    Each node calculates its local masked differences.

    Nodes exchange these shares and add them to obtain public
    masked values d and e.

    The opened values are protected by random Beaver masks.
    """

    return MaskShare(
        d=(x_share - triple.a) % PRIME,
        e=(x_share - triple.b) % PRIME,
    )


def combine_open_masks(
    mask_a: MaskShare,
    mask_b: MaskShare,
) -> Tuple[int, int]:
    """
    Simulated exchange of masked values between nodes.

    In a real deployment, the nodes exchange these values
    over authenticated encrypted channels.
    """

    d = (mask_a.d + mask_b.d) % PRIME
    e = (mask_a.e + mask_b.e) % PRIME

    return d, e


def multiply_local_shares(
    triple: BeaverTripleShare,
    opened_d: int,
    opened_e: int,
    party_index: int,
) -> int:
    """
    Beaver multiplication.

    Computes one node's output share for x * x.

    The public masked values d and e are exchanged between nodes.
    No node receives x itself.
    """

    if party_index not in (0, 1):
        raise ProtocolError("Invalid party index")

    result = (
        triple.c
        + opened_d * triple.b
        + opened_e * triple.a
    ) % PRIME

    # The public d*e term is assigned to exactly one node.
    if party_index == 0:
        result = (result + opened_d * opened_e) % PRIME

    return result


def prepare_difference_shares(
    left: VectorShare,
    right: VectorShare,
) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
    """
    Subtract secret-shared vectors locally.

    Node A subtracts A shares.
    Node B subtracts B shares.

    Neither node learns the actual difference.
    """

    if left.dimensions != right.dimensions:
        raise ProtocolError("Vector dimensions differ")

    if left.dimensions != len(left.values):
        raise ProtocolError("Invalid left vector")

    if right.dimensions != len(right.values):
        raise ProtocolError("Invalid right vector")

    difference_a = []
    difference_b = []

    for a, b in zip(left.values, right.values):
        difference_a.append((a - b) % PRIME)

    # This function is called separately for each node's local shares.
    # The caller must not send both sets to one computation node.

    return tuple(difference_a), tuple(difference_b)


def node_local_distance_share(
    left_local: VectorShare,
    right_local: VectorShare,
    triples: Tuple[BeaverTripleShare, ...],
    opened_masks: Tuple[Tuple[int, int], ...],
    party_index: int,
) -> int:
    """
    Calculate one node's share of the total squared distance.

    This function receives only that node's local vector shares
    and that node's Beaver triple shares.

    opened_masks are public masked values exchanged by both nodes.
    """

    if left_local.dimensions != right_local.dimensions:
        raise ProtocolError("Vector dimension mismatch")

    dimensions = left_local.dimensions

    if len(triples) != dimensions:
        raise ProtocolError("Incorrect triple count")

    if len(opened_masks) != dimensions:
        raise ProtocolError("Incorrect mask count")

    output = 0

    for index in range(dimensions):
        x = (
            left_local.values[index]
            - right_local.values[index]
        ) % PRIME

        opened_d, opened_e = opened_masks[index]

        square_share = multiply_local_shares(
            triple=triples[index],
            opened_d=opened_d,
            opened_e=opened_e,
            party_index=party_index,
        )

        output = (output + square_share) % PRIME

    return output


def reconstruct_distance_on_device(
    share_a: int,
    share_b: int,
    dimensions: int,
) -> int:
    """
    Reconstruct the squared distance on the participant's device.

    This should never run on a crawler or matching node.

    The output is an integer in fixed-point squared units.
    """

    if not 1 <= dimensions <= MAX_DIMENSIONS:
        raise ProtocolError("Invalid dimensions")

    result = _reconstruct(share_a, share_b)

    # Decode a signed field element.
    if result > PRIME // 2:
        result -= PRIME

    if not 0 <= result <= MAX_DISTANCE:
        raise ProtocolError("Reconstructed result outside valid range")

    return result


def distance_to_normalized_score(
    squared_distance: int,
    dimensions: int,
) -> float:
    """
    Optional local display calculation.

    This score is for the participant's device only.
    It is not sent to the mesh.

    1.0 means identical vectors.
    0.0 means maximum possible distance.
    """

    maximum = dimensions * INPUT_SCALE**2

    if maximum <= 0:
        raise ProtocolError("Invalid normalization")

    ratio = min(1.0, max(0.0, squared_distance / maximum))

    return max(0.0, 1.0 - ratio)


def run_local_protocol_test():
    """
    A single-process simulation for synthetic data only.

    Production must run the two nodes in separate processes
    and separate security boundaries.
    """

    print("Starting synthetic MPC test...")

    participant_a = [0.80, 0.20, 0.70, 0.10]
    participant_b = [0.79, 0.21, 0.68, 0.12]

    # Participant devices create shares.
    a_share_a, a_share_b = create_vector_shares(
        participant_a,
        consent=True,
    )

    b_share_a, b_share_b = create_vector_shares(
        participant_b,
        consent=True,
    )

    # Independent offline dealer provisions one triple per dimension.
    triples_a, triples_b = generate_beaver_triples(
        a_share_a.dimensions
    )

    # Node A and node B calculate their local difference shares.
    diff_a = tuple(
        (x - y) % PRIME
        for x, y in zip(a_share_a.values, b_share_a.values)
    )

    diff_b = tuple(
        (x - y) % PRIME
        for x, y in zip(a_share_b.values, b_share_b.values)
    )

    # Each node creates its own masked openings.
    opened_masks = []

    for index in range(a_share_a.dimensions):
        mask_a = prepare_mask_share(
            diff_a[index],
            triples_a[index],
        )

        mask_b = prepare_mask_share(
            diff_b[index],
            triples_b[index],
        )

        opened_masks.append(
            combine_open_masks(mask_a, mask_b)
        )

    # Each node calculates only its own output share.
    output_a = 0
    output_b = 0

    for index in range(a_share_a.dimensions):
        d, e = opened_masks[index]

        output_a = (
            output_a
            + multiply_local_shares(
                triples_a[index],
                d,
                e,
                party_index=0,
            )
        ) % PRIME

        output_b = (
            output_b
            + multiply_local_shares(
                triples_b[index],
                d,
                e,
                party_index=1,
            )
        ) % PRIME

    # Only the participant device reconstructs the result.
    distance = reconstruct_distance_on_device(
        output_a,
        output_b,
        a_share_a.dimensions,
    )

    score = distance_to_normalized_score(
        distance,
        a_share_a.dimensions,
    )

    assert distance >= 0
    assert score > 0.99

    print("Synthetic MPC test passed.")
    print("Dimensions:", a_share_a.dimensions)
    print("Local normalized similarity:", round(score, 5))
    print("No original vector was sent to either node.")

    return {
        "success": True,
        "dimensions": a_share_a.dimensions,
        "local_score": round(score, 5),
    }


if __name__ == "__main__":
    run_local_protocol_test()
