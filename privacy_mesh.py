
"""
Survivors Network — Privacy Mesh
File: privacy_mesh.py

Purpose:
    Enable consent-based, mathematical matching without exchanging
    names, contact details, or narrative descriptions.

Security model:
    - Numeric feature vectors only.
    - Explicit opt-in required.
    - AES-256-GCM authenticated encryption.
    - Separate encryption key for each peer relationship.
    - Random aliases; never derive aliases from personal information.
    - Redundant delivery to authorized peers.
    - In-memory matching; no persistent trauma-profile database.
    - No email, SMS, phone, or external mailing integration.

IMPORTANT:
    This is a privacy-focused prototype module, not a complete
    production anonymity system. Network transport, key provisioning,
    authenticated peer identity, rate limiting, and independent
    security review are still required.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import secrets
import time
import uuid

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


PROTOCOL_VERSION = 1
VECTOR_MIN = 0.0
VECTOR_MAX = 1.0
MAX_VECTOR_DIMENSIONS = 256
MAX_MESSAGE_BYTES = 32_768


class PrivacyMeshError(Exception):
    """Base exception for privacy-mesh errors."""


class ConsentRequired(PrivacyMeshError):
    pass


class InvalidPayload(PrivacyMeshError):
    pass


class AuthenticationFailure(PrivacyMeshError):
    pass


@dataclass(frozen=True)
class Peer:
    """
    A network node, not a survivor.

    peer_id identifies an authorized service node only.
    key must be a unique 32-byte AES key for this peer relationship.
    """

    peer_id: str
    key: bytes
    enabled: bool = True

    def __post_init__(self):
        if not self.peer_id or len(self.peer_id) > 128:
            raise ValueError("Invalid peer ID")

        if not isinstance(self.key, bytes) or len(self.key) != 32:
            raise ValueError("Peer key must be exactly 32 bytes")


@dataclass(frozen=True)
class NumericVector:
    """
    A normalized mathematical representation.

    Dimension positions are meaningful only to the locally configured
    application. The transmitted vector contains no variable names.
    """

    values: Tuple[float, ...]

    def __post_init__(self):
        if not isinstance(self.values, tuple):
            raise InvalidPayload("Vector values must be a tuple")

        if not 1 <= len(self.values) <= MAX_VECTOR_DIMENSIONS:
            raise InvalidPayload("Invalid vector dimension count")

        for value in self.values:
            if isinstance(value, bool):
                raise InvalidPayload("Boolean values are prohibited")

            if not isinstance(value, (int, float)):
                raise InvalidPayload("Only numeric values are permitted")

            if not math.isfinite(float(value)):
                raise InvalidPayload("Non-finite vector value")

            if not VECTOR_MIN <= float(value) <= VECTOR_MAX:
                raise InvalidPayload("Vector value outside normalized range")

    def to_list(self) -> List[float]:
        return [float(value) for value in self.values]


def new_alias() -> str:
    """
    Generate a random, non-derived participant alias.

    This alias must not be used as a username or public identifier.
    Prefer a new alias for each independent matching session.
    """
    return secrets.token_urlsafe(24)


def cosine_similarity(
    left: NumericVector,
    right: NumericVector,
) -> float:
    """
    Return cosine similarity in the range 0..1.

    Vectors must have the same number of dimensions.
    A zero-magnitude vector returns 0.
    """

    if len(left.values) != len(right.values):
        raise InvalidPayload("Vector dimensions do not match")

    dot = sum(
        float(a) * float(b)
        for a, b in zip(left.values, right.values)
    )

    left_norm = math.sqrt(sum(float(x) ** 2 for x in left.values))
    right_norm = math.sqrt(sum(float(x) ** 2 for x in right.values))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    score = dot / (left_norm * right_norm)

    # Floating-point correction.
    return max(0.0, min(1.0, score))


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def _unb64(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value.encode("ascii"))
    except Exception as exc:
        raise InvalidPayload("Invalid encoded field") from exc


class PeerCipher:
    """
    Encrypt and authenticate messages for one peer relationship.

    A different 32-byte key must be provisioned for each peer pair.
    Never reuse one global mesh key for every node.
    """

    def __init__(self, local_node_id: str, peer: Peer):
        if not local_node_id or len(local_node_id) > 128:
            raise ValueError("Invalid local node ID")

        if not peer.enabled:
            raise ValueError("Peer is disabled")

        self.local_node_id = local_node_id
        self.peer = peer
        self.aes = AESGCM(peer.key)

    def encrypt(self, payload: dict) -> dict:
        message_id = str(uuid.uuid4())
        nonce = secrets.token_bytes(12)

        header = {
            "version": PROTOCOL_VERSION,
            "sender": self.local_node_id,
            "recipient": self.peer.peer_id,
            "message_id": message_id,
        }

        plaintext = _canonical_json(payload)
        aad = _canonical_json(header)

        ciphertext = self.aes.encrypt(nonce, plaintext, aad)

        envelope = {
            **header,
            "nonce": _b64(nonce),
            "ciphertext": _b64(ciphertext),
        }

        encoded_size = len(_canonical_json(envelope))

        if encoded_size > MAX_MESSAGE_BYTES:
            raise InvalidPayload("Message exceeds maximum size")

        return envelope

    def decrypt(
        self,
        envelope: dict,
        expected_sender: str,
    ) -> dict:
        required = {
            "version",
            "sender",
            "recipient",
            "message_id",
            "nonce",
            "ciphertext",
        }

        if not isinstance(envelope, dict):
            raise InvalidPayload("Envelope must be an object")

        if set(envelope.keys()) != required:
            raise InvalidPayload("Unexpected envelope fields")

        if envelope["version"] != PROTOCOL_VERSION:
            raise InvalidPayload("Unsupported protocol version")

        if envelope["sender"] != expected_sender:
            raise AuthenticationFailure("Unexpected sender")

        if envelope["recipient"] != self.local_node_id:
            raise AuthenticationFailure("Wrong recipient")

        header = {
            "version": envelope["version"],
            "sender": envelope["sender"],
            "recipient": envelope["recipient"],
            "message_id": envelope["message_id"],
        }

        nonce = _unb64(envelope["nonce"])
        ciphertext = _unb64(envelope["ciphertext"])

        if len(nonce) != 12:
            raise InvalidPayload("Invalid nonce length")

        if len(ciphertext) > MAX_MESSAGE_BYTES:
            raise InvalidPayload("Ciphertext too large")

        try:
            plaintext = self.aes.decrypt(
                nonce,
                ciphertext,
                _canonical_json(header),
            )
        except Exception as exc:
            raise AuthenticationFailure(
                "Message authentication failed"
            ) from exc

        try:
            payload = json.loads(plaintext.decode("utf-8"))
        except Exception as exc:
            raise InvalidPayload("Invalid message body") from exc

        if not isinstance(payload, dict):
            raise InvalidPayload("Message body must be an object")

        return payload


class NumericMatchEngine:
    """
    Local, in-memory matching engine.

    The engine does not receive names, emails, phone numbers,
    addresses, or narrative descriptions.

    The caller is responsible for collecting informed consent
    before submitting a vector.
    """

    def __init__(
        self,
        minimum_similarity: float = 0.90,
        maximum_results: int = 5,
    ):
        if not 0.0 <= minimum_similarity <= 1.0:
            raise ValueError("Similarity threshold must be 0..1")

        if not 1 <= maximum_results <= 20:
            raise ValueError("Invalid maximum result count")

        self.minimum_similarity = minimum_similarity
        self.maximum_results = maximum_results

        # alias -> (numeric vector, expiry timestamp)
        self._records: Dict[str, Tuple[NumericVector, float]] = {}

    def add(
        self,
        vector: NumericVector,
        *,
        consent: bool,
        ttl_seconds: int = 3600,
    ) -> str:
        if consent is not True:
            raise ConsentRequired("Explicit opt-in is required")

        if not 60 <= ttl_seconds <= 86_400:
            raise InvalidPayload("TTL must be between 60 and 86400 seconds")

        alias = new_alias()
        expires_at = time.time() + ttl_seconds

        self._records[alias] = (vector, expires_at)

        return alias

    def revoke(self, alias: str) -> bool:
        """
        Remove a participant's in-memory vector.
        """
        return self._records.pop(alias, None) is not None

    def purge_expired(self) -> int:
        now = time.time()

        expired = [
            alias
            for alias, (_, expiry) in self._records.items()
            if expiry <= now
        ]

        for alias in expired:
            self._records.pop(alias, None)

        return len(expired)

    def match(
        self,
        alias: str,
    ) -> List[dict]:
        """
        Return temporary aliases and scores only.

        No names or contact routes are returned.
        """
        self.purge_expired()

        if alias not in self._records:
            return []

        source_vector, _ = self._records[alias]
        candidates = []

        for other_alias, (other_vector, _) in self._records.items():
            if other_alias == alias:
                continue

            if len(source_vector.values) != len(other_vector.values):
                continue

            score = cosine_similarity(source_vector, other_vector)

            if score >= self.minimum_similarity:
                candidates.append({
                    "temporary_alias": new_alias(),
                    "similarity": round(score, 5),
                })

        candidates.sort(
            key=lambda item: item["similarity"],
            reverse=True,
        )

        return candidates[:self.maximum_results]

    def clear(self):
        self._records.clear()


class RedundantPeerMesh:
    """
    Sends one logical message to multiple authorized peers.

    Each peer receives a separately encrypted envelope.
    A peer's failure does not prevent delivery attempts to others.

    transport(peer_id, envelope) is supplied by the application.
    It must use authenticated HTTPS or an equivalently protected
    transport and return True only after an acknowledged receipt.
    """

    def __init__(
        self,
        local_node_id: str,
        peers: Iterable[Peer],
        transport: Callable[[str, dict], bool],
    ):
        self.local_node_id = local_node_id
        self.peers = {
            peer.peer_id: peer
            for peer in peers
            if peer.enabled
        }
        self.transport = transport

        if not callable(transport):
            raise TypeError("Transport must be callable")

        self._seen_message_ids = set()

    def broadcast(self, payload: dict) -> dict:
        """
        Redundant delivery to all configured authorized peers.

        This method accepts only the restricted message schema below.
        """

        allowed_fields = {
            "kind",
            "schema",
            "vector",
            "consent",
            "expires_at",
            "request_id",
        }

        if not isinstance(payload, dict):
            raise InvalidPayload("Payload must be an object")

        if set(payload.keys()) != allowed_fields:
            raise InvalidPayload("Unexpected payload fields")

        if payload.get("kind") != "numeric_match":
            raise InvalidPayload("Unsupported message kind")

        if payload.get("schema") != PROTOCOL_VERSION:
            raise InvalidPayload("Unsupported schema")

        if payload.get("consent") is not True:
            raise ConsentRequired("Explicit opt-in is required")

        vector = payload.get("vector")

        if not isinstance(vector, list):
            raise InvalidPayload("Vector must be a list")

        # Revalidate the vector before transmission.
        NumericVector(tuple(vector))

        expiry = payload.get("expires_at")

        if (
            isinstance(expiry, bool)
            or not isinstance(expiry, (int, float))
            or expiry <= time.time()
            or expiry > time.time() + 86_400
        ):
            raise InvalidPayload("Invalid or excessive message expiry")

        request_id = payload.get("request_id")

        if not isinstance(request_id, str) or len(request_id) > 128:
            raise InvalidPayload("Invalid request ID")

        results = {}

        for peer_id, peer in self.peers.items():
            try:
                cipher = PeerCipher(self.local_node_id, peer)
                envelope = cipher.encrypt(payload)

                acknowledged = self.transport(peer_id, envelope)

                results[peer_id] = {
                    "acknowledged": bool(acknowledged),
                }

            except Exception:
                # Do not expose peer keys or internal exception details.
                results[peer_id] = {
                    "acknowledged": False,
                }

        acknowledged_count = sum(
            1 for result in results.values()
            if result["acknowledged"]
        )

        return {
            "request_id": request_id,
            "attempted": len(results),
            "acknowledged": acknowledged_count,
            "peer_results": results,
        }


def build_numeric_match_message(
    vector: NumericVector,
    *,
    consent: bool,
    request_id: Optional[str] = None,
    ttl_seconds: int = 900,
) -> dict:
    """
    Build the restricted wire message.

    The vector's positions are defined locally. The message carries
    no variable names or human-readable trauma descriptions.
    """

    if consent is not True:
        raise ConsentRequired("Explicit opt-in is required")

    if not 60 <= ttl_seconds <= 86_400:
        raise InvalidPayload("Invalid message lifetime")

    return {
        "kind": "numeric_match",
        "schema": PROTOCOL_VERSION,
        "vector": vector.to_list(),
        "consent": True,
        "expires_at": time.time() + ttl_seconds,
        "request_id": request_id or secrets.token_urlsafe(18),
    }


def generate_peer_key() -> bytes:
    """
    Generate a 256-bit key for provisioning a peer relationship.

    Deliver keys through a separate authenticated provisioning
    process. Do not commit keys to GitHub or put them in source code.
    """
    return AESGCM.generate_key(bit_length=256)


# ------------------------------------------------------------------
# Minimal local self-test
# ------------------------------------------------------------------

def self_test():
    first = NumericVector((0.8, 0.2, 0.7, 0.1))
    second = NumericVector((0.79, 0.21, 0.68, 0.12))

    score = cosine_similarity(first, second)

    assert 0.0 <= score <= 1.0
    assert score > 0.90

    key = generate_peer_key()

    peer = Peer(
        peer_id="node-b",
        key=key,
    )

    sender = PeerCipher("node-a", peer)

    payload = {
        "kind": "numeric_match",
        "schema": PROTOCOL_VERSION,
        "vector": first.to_list(),
        "consent": True,
        "expires_at": time.time() + 300,
        "request_id": "test-request",
    }

    envelope = sender.encrypt(payload)

    receiver = PeerCipher(
        "node-b",
        Peer("node-a", key),
    )

    recovered = receiver.decrypt(
        envelope,
        expected_sender="node-a",
    )

    assert recovered == payload

    engine = NumericMatchEngine(minimum_similarity=0.90)

    alias_a = engine.add(first, consent=True)
    alias_b = engine.add(second, consent=True)

    matches = engine.match(alias_a)

    assert len(matches) == 1
    assert engine.revoke(alias_b) is True

    print("Privacy mesh self-test passed.")


if __name__ == "__main__":
    self_test()
