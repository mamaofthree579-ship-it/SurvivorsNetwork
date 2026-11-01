"""
Survivors Network — Automated Public Directory Updates
Version: 4.0.0

Purpose
-------
1. Read public crawler snapshots and pending-review records.
2. Normalize discovered resource candidates.
3. Verify candidate structure, source provenance, URLs, contacts,
   service evidence, state association, and corroboration.
4. Automatically publish only candidates that pass strict gates.
5. Detect likely duplicates without merging on name similarity alone.
6. Mark existing records stale or retired without destructive deletion.
7. Preserve audit history, evidence, exceptions, and rollback snapshots.

Privacy boundary
----------------
This module handles PUBLIC resource-directory information only.
It must never read survivor profiles, private matching records,
private messages, case notes, or incident-pattern datasets.

No survivor action is required for routine directory maintenance.
Uncertain cases are queued for network maintenance, not survivors.

Important
---------
A valid-looking phone number is not proof that the number is active.
A successful website response is not proof that every listed service
is currently available. Verification status describes the evidence
actually checked, not a guarantee of service availability.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import re
import shutil
import time
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse


# ---------------------------------------------------------------------
# PATHS AND SETTINGS
# ---------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "resource_crawler_data"

DIRECTORY_FILE = ROOT_DIR / "state_resource_directory.json"
LEGACY_DIRECTORY_FILE = DATA_DIR / "state_resource_directory.json"

SNAPSHOT_DIR = DATA_DIR / "snapshots"
PENDING_REVIEW_FILE = DATA_DIR / "pending_reviews.json"

CANDIDATES_FILE = DATA_DIR / "directory_candidates.json"
EXCEPTIONS_FILE = DATA_DIR / "directory_exceptions.json"
HISTORY_FILE = DATA_DIR / "directory_history.json"
REPORT_FILE = DATA_DIR / "directory_update_report.json"
ACTIVITY_FILE = DATA_DIR / "directory_activity.json"

BACKUP_DIR = DATA_DIR / "directory_backups"

VERSION = "4.0.0"

# Strict automatic publication threshold.
AUTO_PUBLISH_SCORE = 0.90

# A candidate needs at least one corroborating source in addition
# to its originating source, unless it is explicitly identified as
# an official state-operated resource directory entry.
MIN_INDEPENDENT_SOURCES = 1

# Existing listings are not retired because of ordinary crawl failures.
# Retirement requires positive closure evidence on multiple checks.
RETIREMENT_CONFIRMATIONS_REQUIRED = 3

# Stale records are retained and retried.
STALE_AFTER_DAYS = 45

# Limit text extraction to avoid accidentally processing enormous files.
MAX_TEXT_LENGTH = 250_000

# Do not use private survivor data here.
PRIVATE_DATA_FILENAMES = {
    "survivor_profiles.json",
    "survivor_records.json",
    "match_mailbox.json",
    "private_matches.json",
    "incident_patterns.json",
    "case_notes.json",
    "private_messages.json",
}

LOGGER = logging.getLogger("survivors_network.directory_updates")


# ---------------------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str = "item") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        return ""

    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_text(value).lower())


def normalize_state_code(value: Any) -> str:
    value = normalize_text(value).upper()
    return value if re.fullmatch(r"[A-Z]{2}", value) else ""


def safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if value is None:
        return []

    return [value]


def safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def file_is_private(path: Path) -> bool:
    return path.name.lower() in PRIVATE_DATA_FILENAMES


def ensure_directories() -> None:
    for path in (
        DATA_DIR,
        SNAPSHOT_DIR,
        BACKUP_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any = None) -> Any:
    if default is None:
        default = {}

    if not path.exists() or file_is_private(path):
        return copy.deepcopy(default)

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        LOGGER.warning("Could not read %s: %s", path.name, exc)
        return copy.deepcopy(default)


def atomic_write_json(path: Path, data: Any) -> None:
    """
    Write JSON through a temporary file and replace the destination.

    This protects against partial writes if the process stops during
    a save. It does not claim to provide cross-process locking.
    """
    ensure_directories()

    if file_is_private(path):
        raise ValueError(
            f"Private data file is outside this module's scope: {path.name}"
        )

    temp_path = path.with_suffix(path.suffix + ".tmp")

    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.flush()
        os.fsync(file.fileno())

    os.replace(temp_path, path)


def append_json_record(path: Path, record: Dict[str, Any]) -> None:
    existing = read_json(path, default=[])

    if not isinstance(existing, list):
        existing = []

    existing.append(record)
    atomic_write_json(path, existing)


def stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def host_from_url(value: Any) -> str:
    value = normalize_text(value)

    if not value:
        return ""

    try:
        parsed = urlparse(value if "://" in value else f"https://{value}")
        return (parsed.hostname or "").lower().rstrip(".")
    except Exception:
        return ""


def normalize_url(value: Any) -> str:
    """
    Normalize a public URL without fetching it.

    Only HTTP and HTTPS URLs are accepted. Automatic publication
    requires HTTPS. This function does not certify that a site is safe.
    """
    value = normalize_text(value)

    if not value:
        return ""

    if not re.match(r"^https?://", value, flags=re.I):
        value = "https://" + value

    try:
        parsed = urlparse(value)

        if parsed.scheme.lower() not in {"http", "https"}:
            return ""

        if not parsed.hostname:
            return ""

        if parsed.username or parsed.password:
            return ""

        cleaned = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
            fragment="",
        )

        return urlunparse(cleaned).rstrip("/")
    except Exception:
        return ""


def url_is_https(value: Any) -> bool:
    url = normalize_url(value)
    return bool(url and urlparse(url).scheme == "https")


def get_first(record: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, "", [], {}):
            return record[key]

    return None


def extract_text(record: Dict[str, Any]) -> str:
    """
    Read common crawler text fields without assuming one exact schema.
    """
    fields = (
        "extracted_text",
        "source_text",
        "text",
        "content",
        "excerpt",
        "new_excerpt",
        "description",
        "summary",
        "body",
        "page_text",
    )

    parts = []

    for field in fields:
        value = record.get(field)

        if isinstance(value, str) and value.strip():
            parts.append(value.strip())

    return "\n".join(parts)[:MAX_TEXT_LENGTH]


def unwrap_records(data: Any) -> List[Dict[str, Any]]:
    """
    Accept list files and common dictionary wrappers.
    """
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if isinstance(data, dict):
        for key in (
            "records",
            "items",
            "reviews",
            "pending",
            "snapshots",
            "sources",
            "results",
            "data",
        ):
            value = data.get(key)

            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

            if isinstance(value, dict):
                return [
                    item for item in value.values()
                    if isinstance(item, dict)
                ]

        if data and all(isinstance(v, dict) for v in data.values()):
            return list(data.values())

        return [data] if data else []

    return []


# ---------------------------------------------------------------------
# STATE NORMALIZATION
# ---------------------------------------------------------------------

STATE_CODES = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
}

STATE_NAMES = {code: name.title() for name, code in STATE_CODES.items()}


def resolve_state_code(value: Any) -> str:
    value = normalize_text(value)

    if not value:
        return ""

    code = normalize_state_code(value)

    if code in STATE_NAMES:
        return code

    return STATE_CODES.get(value.lower(), "")


def normalize_state_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Preserve original state fields while normalizing aliases used by
    the app and earlier directory updater versions.
    """
    result = copy.deepcopy(record)

    code = resolve_state_code(
        get_first(result, ("code", "abbr", "state_code", "abbreviation"))
    )

    name = normalize_text(
        get_first(result, ("name", "state", "state_name"))
    )

    if not code and name:
        code = resolve_state_code(name)

    if not name and code:
        name = STATE_NAMES.get(code, "")

    result["code"] = code
    result["abbr"] = result.get("abbr") or code
    result["name"] = name

    website = normalize_url(
        get_first(result, ("website", "url", "official_url"))
    )

    if website:
        result["website"] = website

    return result


def load_directory() -> Tuple[Any, str]:
    """
    Root-level directory is canonical.
    Legacy location is read only when the canonical file is absent.
    """
    if DIRECTORY_FILE.exists():
        return read_json(DIRECTORY_FILE, default=[]), str(DIRECTORY_FILE)

    if LEGACY_DIRECTORY_FILE.exists():
        return read_json(LEGACY_DIRECTORY_FILE, default=[]), str(
            LEGACY_DIRECTORY_FILE
        )

    return [], str(DIRECTORY_FILE)


def save_directory(data: Any) -> None:
    """
    Always save to the root-level canonical path.
    """
    atomic_write_json(DIRECTORY_FILE, data)


def directory_state_records(directory: Any) -> List[Dict[str, Any]]:
    if isinstance(directory, list):
        return [
            normalize_state_record(item)
            for item in directory
            if isinstance(item, dict)
        ]

    if isinstance(directory, dict):
        for key in ("states", "state_directory", "records"):
            if isinstance(directory.get(key), list):
                return [
                    normalize_state_record(item)
                    for item in directory[key]
                    if isinstance(item, dict)
                ]

        # A dictionary keyed by state code/name.
        records = []

        for key, value in directory.items():
            if isinstance(value, dict):
                item = copy.deepcopy(value)

                if not get_first(item, ("code", "abbr", "state_code")):
                    item["code"] = key

                records.append(normalize_state_record(item))

        return records

    return []


def locate_state_container(directory: Any, state_code: str):
    """
    Return the state record and its container location.
    """
    if isinstance(directory, list):
        for index, item in enumerate(directory):
            if not isinstance(item, dict):
                continue

            normalized = normalize_state_record(item)

            if normalized.get("code") == state_code:
                return item, ("list", index)

    if isinstance(directory, dict):
        for container_key in ("states", "state_directory", "records"):
            values = directory.get(container_key)

            if isinstance(values, list):
                for index, item in enumerate(values):
                    if not isinstance(item, dict):
                        continue

                    normalized = normalize_state_record(item)

                    if normalized.get("code") == state_code:
                        return item, ("dict_list", container_key, index)

        for key, item in directory.items():
            if not isinstance(item, dict):
                continue

            normalized = normalize_state_record(item)

            if normalized.get("code") == state_code:
                return item, ("dict_key", key)

    return None, None


def insert_resource_into_directory(
    directory: Any,
    state_code: str,
    resource: Dict[str, Any],
) -> Tuple[Any, bool]:
    """
    Add a resource under its state record.

    Existing directory fields are retained. A missing state record is
    not silently fabricated; the candidate is rejected by the caller.
    """
    state_record, location = locate_state_container(directory, state_code)

    if state_record is None or location is None:
        return directory, False

    resources = state_record.get("resources")

    if not isinstance(resources, list):
        resources = []
        state_record["resources"] = resources

    resource_id = resource.get("resource_id")

    if any(
        isinstance(existing, dict)
        and existing.get("resource_id") == resource_id
        for existing in resources
    ):
        return directory, False

    resources.append(copy.deepcopy(resource))
    return directory, True


# ---------------------------------------------------------------------
# CRAWLER INPUT
# ---------------------------------------------------------------------

def load_pending_reviews() -> List[Dict[str, Any]]:
    return unwrap_records(read_json(PENDING_REVIEW_FILE, default=[]))


def load_snapshots() -> List[Dict[str, Any]]:
    records = []

    if not SNAPSHOT_DIR.exists():
        return records

    for path in SNAPSHOT_DIR.glob("*.json"):
        if file_is_private(path):
            continue

        data = read_json(path, default={})

        for item in unwrap_records(data):
            item = copy.deepcopy(item)
            item.setdefault("_snapshot_file", path.name)
            records.append(item)

    return records


def load_crawler_inputs() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    return load_pending_reviews(), load_snapshots()


def collect_candidate_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Some crawler versions store a structured resource object inside
    a review. Others place the fields directly on the review.
    """
    for key in (
        "candidate",
        "resource",
        "resource_record",
        "directory_entry",
        "record",
        "data",
    ):
        value = record.get(key)

        if isinstance(value, dict):
            merged = copy.deepcopy(value)

            for parent_key in (
                "state",
                "state_code",
                "state_name",
                "source_url",
                "url",
                "source_id",
                "review_id",
            ):
                if parent_key not in merged and parent_key in record:
                    merged[parent_key] = record[parent_key]

            return merged

    return copy.deepcopy(record)


def record_source_url(record: Dict[str, Any]) -> str:
    return normalize_url(
        get_first(
            record,
            (
                "source_url",
                "url",
                "page_url",
                "origin_url",
                "website",
                "resolved_url",
            ),
        )
    )


def record_source_id(record: Dict[str, Any]) -> str:
    return normalize_text(
        get_first(
            record,
            (
                "source_id",
                "id",
                "review_id",
                "snapshot_id",
                "record_id",
            ),
        )
    )


def source_origin_host(record: Dict[str, Any]) -> str:
    return host_from_url(record_source_url(record))


def match_snapshots(
    review: Dict[str, Any],
    snapshots: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Match review evidence to crawler snapshots by source ID or URL.
    If neither is available, do not attach unrelated snapshots.
    """
    review_id = record_source_id(review)
    review_url = record_source_url(review)

    matches = []

    for snapshot in snapshots:
        snapshot_id = record_source_id(snapshot)
        snapshot_url = record_source_url(snapshot)

        if review_id and snapshot_id and review_id == snapshot_id:
            matches.append(snapshot)
            continue

        if review_url and snapshot_url and review_url == snapshot_url:
            matches.append(snapshot)

    return matches


# ---------------------------------------------------------------------
# EXTRACTION AND FIELD CHECKS
# ---------------------------------------------------------------------

EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.I,
)

PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+?1[\s.-]?)?"
    r"(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\w)"
)

SERVICE_KEYWORDS = {
    "emergency shelter": (
        "emergency shelter",
        "crisis shelter",
        "safe shelter",
    ),
    "housing assistance": (
        "housing assistance",
        "transitional housing",
        "rapid rehousing",
        "housing support",
    ),
    "legal assistance": (
        "legal aid",
        "legal assistance",
        "legal services",
        "legal advocacy",
    ),
    "counseling": (
        "counseling",
        "therapy",
        "behavioral health",
        "mental health services",
    ),
    "hotline": (
        "hotline",
        "crisis line",
        "24-hour line",
        "24 hour line",
    ),
    "advocacy": (
        "victim advocacy",
        "survivor advocacy",
        "advocacy services",
    ),
    "financial assistance": (
        "financial assistance",
        "emergency financial assistance",
        "relocation assistance",
    ),
    "child and family services": (
        "child services",
        "family services",
        "children's services",
        "childcare assistance",
    ),
    "medical assistance": (
        "medical assistance",
        "healthcare assistance",
        "medical advocacy",
    ),
    "transportation": (
        "transportation assistance",
        "transportation support",
        "bus vouchers",
    ),
}


def extract_email(text: str) -> str:
    matches = EMAIL_PATTERN.findall(text or "")

    return matches[0].strip(".,;:") if matches else ""


def normalize_phone(value: Any) -> str:
    value = normalize_text(value)

    if not value:
        return ""

    digits = re.sub(r"\D", "", value)

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) != 10:
        return ""

    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"


def extract_phone(text: str) -> str:
    matches = PHONE_PATTERN.findall(text or "")

    for match in matches:
        normalized = normalize_phone(match)

        if normalized:
            return normalized

    return ""


def extract_services(text: str) -> List[str]:
    lowered = (text or "").lower()
    found = []

    for service, phrases in SERVICE_KEYWORDS.items():
        if any(phrase in lowered for phrase in phrases):
            found.append(service)

    return sorted(set(found))


def extract_context_for_value(text: str, value: str, radius: int = 120) -> str:
    if not text or not value:
        return ""

    index = text.lower().find(value.lower())

    if index < 0:
        return ""

    start = max(0, index - radius)
    end = min(len(text), index + len(value) + radius)

    return re.sub(r"\s+", " ", text[start:end]).strip()


def has_service_context(text: str, service: str) -> bool:
    lowered = (text or "").lower()
    phrases = SERVICE_KEYWORDS.get(service, (service,))

    return any(phrase in lowered for phrase in phrases)


def validate_email(value: Any) -> bool:
    value = normalize_text(value)

    return bool(
        value
        and EMAIL_PATTERN.fullmatch(value)
        and len(value) <= 254
    )


def validate_phone(value: Any) -> bool:
    return bool(normalize_phone(value))


def validate_resource_url(value: Any) -> bool:
    url = normalize_url(value)

    if not url:
        return False

    parsed = urlparse(url)

    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and "." in parsed.hostname
    )


def extract_candidate_fields(
    payload: Dict[str, Any],
    evidence_text: str,
) -> Dict[str, Any]:
    name = normalize_text(
        get_first(
            payload,
            (
                "resource_name",
                "organization_name",
                "organization",
                "provider_name",
                "agency_name",
                "name",
                "title",
            ),
        )
    )

    state_code = resolve_state_code(
        get_first(
            payload,
            (
                "state_code",
                "abbr",
                "state_abbreviation",
                "state",
                "state_name",
            ),
        )
    )

    website = normalize_url(
        get_first(
            payload,
            (
                "resource_website",
                "organization_website",
                "website",
                "url",
                "official_url",
            ),
        )
    )

    phone = normalize_phone(
        get_first(payload, ("phone", "telephone", "phone_number"))
    )

    email = normalize_text(
        get_first(payload, ("email", "contact_email"))
    )

    if not phone:
        phone = extract_phone(evidence_text)

    if not email:
        email = extract_email(evidence_text)

    services_value = get_first(
        payload,
        ("services", "service_types", "categories", "resource_type"),
    )

    services = []

    for item in safe_list(services_value):
        item_text = normalize_text(item)

        if item_text:
            services.append(item_text.lower())

    if not services:
        services = extract_services(evidence_text)

    services = sorted(set(services))

    description = normalize_text(
        get_first(payload, ("description", "summary", "details"))
    )

    return {
        "name": name,
        "state_code": state_code,
        "website": website,
        "phone": phone,
        "email": email,
        "services": services,
        "description": description,
    }


# ---------------------------------------------------------------------
# EVIDENCE AND CORROBORATION
# ---------------------------------------------------------------------

def source_record(
    record: Dict[str, Any],
    role: str,
) -> Dict[str, Any]:
    url = record_source_url(record)

    return {
        "source_id": record_source_id(record) or make_id("source"),
        "url": url,
        "host": host_from_url(url),
        "role": role,
        "checked_at": now_iso(),
        "snapshot_file": normalize_text(record.get("_snapshot_file")),
        "evidence_hash": stable_hash(extract_text(record)),
    }


def is_independent_host(host_a: str, host_b: str) -> bool:
    """
    Conservative independence test.

    Different subdomains of the same apparent base domain do not count
    as independent. This intentionally errs on the side of not counting
    corroboration. It is not a complete public-suffix-list implementation.
    """
    host_a = (host_a or "").lower().strip(".")
    host_b = (host_b or "").lower().strip(".")

    if not host_a or not host_b or host_a == host_b:
        return False

    if host_a.endswith("." + host_b) or host_b.endswith("." + host_a):
        return False

    parts_a = host_a.split(".")
    parts_b = host_b.split(".")

    if len(parts_a) >= 2 and len(parts_b) >= 2:
        apparent_a = ".".join(parts_a[-2:])
        apparent_b = ".".join(parts_b[-2:])

        if apparent_a == apparent_b:
            return False

    return True


def collect_evidence(
    review: Dict[str, Any],
    matched_snapshots: List[Dict[str, Any]],
) -> Tuple[str, List[Dict[str, Any]]]:
    text_parts = []
    sources = []

    review_text = extract_text(review)

    if review_text:
        text_parts.append(review_text)

    sources.append(source_record(review, "origin"))

    for snapshot in matched_snapshots:
        snapshot_text = extract_text(snapshot)

        if snapshot_text:
            text_parts.append(snapshot_text)

        sources.append(source_record(snapshot, "snapshot"))

    unique_sources = []
    seen = set()

    for source in sources:
        key = (
            source.get("url"),
            source.get("source_id"),
            source.get("evidence_hash"),
        )

        if key not in seen:
            seen.add(key)
            unique_sources.append(source)

    combined_text = "\n".join(text_parts)[:MAX_TEXT_LENGTH]

    return combined_text, unique_sources


def independent_source_count(sources: List[Dict[str, Any]]) -> int:
    hosts = sorted({
        source.get("host", "")
        for source in sources
        if source.get("host")
    })

    if len(hosts) < 2:
        return 0

    independent = set()

    for host in hosts:
        if any(is_independent_host(host, other) for other in hosts if other != host):
            independent.add(host)

    return len(independent)


def corroboration_details(
    sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    hosts = sorted({
        source.get("host", "")
        for source in sources
        if source.get("host")
    })

    return {
        "source_count": len(sources),
        "distinct_hosts": hosts,
        "independent_source_count": independent_source_count(sources),
        "source_urls": sorted({
            source.get("url", "")
            for source in sources
            if source.get("url")
        }),
    }


# ---------------------------------------------------------------------
# DUPLICATE DETECTION
# ---------------------------------------------------------------------

def canonical_name(value: Any) -> str:
    value = normalize_text(value).lower()
    value = re.sub(r"\b(inc|llc|ltd|corp|corporation|nonprofit)\b", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def resource_domain(value: Any) -> str:
    host = host_from_url(value)

    if not host:
        return ""

    return host


def find_duplicate(
    candidate: Dict[str, Any],
    directory: Any,
) -> Optional[Dict[str, Any]]:
    """
    Strong match:
      - same state and exact website host; OR
      - same state, same normalized phone, and same normalized name.

    Name-only similarity is not enough to merge or reject a record.
    """
    state_code = candidate.get("state_code")
    name = canonical_name(candidate.get("name"))
    domain = resource_domain(candidate.get("website"))
    phone = normalize_phone(candidate.get("phone"))

    state_record, _ = locate_state_container(directory, state_code)

    if not state_record:
        return None

    resources = state_record.get("resources", [])

    if not isinstance(resources, list):
        return None

    for existing in resources:
        if not isinstance(existing, dict):
            continue

        existing_name = canonical_name(existing.get("name"))
        existing_domain = resource_domain(existing.get("website"))
        existing_phone = normalize_phone(existing.get("phone"))

        exact_domain_match = bool(
            domain and existing_domain and domain == existing_domain
        )

        name_phone_match = bool(
            name
            and existing_name
            and name == existing_name
            and phone
            and existing_phone
            and phone == existing_phone
        )

        if exact_domain_match or name_phone_match:
            return existing

    return None


# ---------------------------------------------------------------------
# CANDIDATE DECISION ENGINE
# ---------------------------------------------------------------------

def evaluate_candidate(
    fields: Dict[str, Any],
    sources: List[Dict[str, Any]],
    evidence_text: str,
    directory: Any,
) -> Dict[str, Any]:
    checks = {}

    checks["name_present"] = bool(fields.get("name"))
    checks["state_recognized"] = fields.get("state_code") in STATE_NAMES
    checks["website_https"] = validate_resource_url(fields.get("website"))
    checks["source_provenance"] = any(
        source.get("url") for source in sources
    )

    checks["service_evidence"] = bool(
        fields.get("services")
        and any(
            has_service_context(evidence_text, service)
            for service in fields.get("services", [])
        )
    )

    checks["contact_format"] = bool(
        not fields.get("phone") or validate_phone(fields.get("phone"))
    ) and bool(
        not fields.get("email") or validate_email(fields.get("email"))
    )

    corroboration = corroboration_details(sources)

    checks["independent_corroboration"] = (
        corroboration["independent_source_count"]
        >= MIN_INDEPENDENT_SOURCES
    )

    duplicate = find_duplicate(fields, directory)
    checks["not_duplicate"] = duplicate is None

    # Weighted score is a rule-based review score, NOT a probability.
    weights = {
        "name_present": 0.15,
        "state_recognized": 0.15,
        "website_https": 0.20,
        "source_provenance": 0.10,
        "service_evidence": 0.15,
        "contact_format": 0.05,
        "independent_corroboration": 0.15,
        "not_duplicate": 0.05,
    }

    score = sum(
        weights[key]
        for key, passed in checks.items()
        if passed
    )

    # Auto-publish requires every critical gate, not just a score.
    critical_gates = (
        "name_present",
        "state_recognized",
        "website_https",
        "source_provenance",
        "service_evidence",
        "independent_corroboration",
        "not_duplicate",
    )

    auto_publish = (
        score >= AUTO_PUBLISH_SCORE
        and all(checks[key] for key in critical_gates)
    )

    if duplicate:
        status = "duplicate"
    elif auto_publish:
        status = "verified"
    elif not fields.get("state_code") or not fields.get("name"):
        status = "needs_maintenance"
    else:
        status = "pending_maintenance"

    return {
        "score": round(score, 3),
        "checks": checks,
        "status": status,
        "auto_publish": auto_publish,
        "duplicate_resource_id": (
            duplicate.get("resource_id") if duplicate else None
        ),
        "corroboration": corroboration,
        "decision_note": (
            "Rule-based evidence score; not a statistical probability."
        ),
    }


# ---------------------------------------------------------------------
# CANDIDATE CREATION
# ---------------------------------------------------------------------

def build_candidate(
    review: Dict[str, Any],
    snapshots: List[Dict[str, Any]],
    directory: Any,
) -> Dict[str, Any]:
    payload = collect_candidate_payload(review)
    matched = match_snapshots(review, snapshots)

    evidence_text, sources = collect_evidence(review, matched)
    fields = extract_candidate_fields(payload, evidence_text)

    decision = evaluate_candidate(
        fields,
        sources,
        evidence_text,
        directory,
    )

    candidate_id = normalize_text(
        get_first(review, ("candidate_id", "review_id", "id"))
    ) or make_id("candidate")

    return {
        "candidate_id": candidate_id,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status": decision["status"],
        "resource": {
            **fields,
            "resource_id": make_id("resource"),
            "status": "active",
            "verification_status": "verified"
            if decision["auto_publish"]
            else "pending",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        "evidence": {
            "sources": sources,
            "text_excerpt": evidence_text[:3000],
            "evidence_hash": stable_hash(evidence_text),
        },
        "decision": decision,
        "review_source": {
            "source_id": record_source_id(review),
            "source_url": record_source_url(review),
            "source_status": normalize_text(
                get_first(review, ("status", "review_status", "action"))
            ),
        },
    }


def build_candidates(
    reviews: List[Dict[str, Any]],
    snapshots: List[Dict[str, Any]],
    directory: Any,
) -> List[Dict[str, Any]]:
    candidates = []
    seen = set()

    for review in reviews:
        candidate = build_candidate(review, snapshots, directory)

        fingerprint = stable_hash({
            "name": canonical_name(candidate["resource"].get("name")),
            "state": candidate["resource"].get("state_code"),
            "website": resource_domain(candidate["resource"].get("website")),
            "source": candidate["review_source"].get("source_url"),
        })

        if fingerprint in seen:
            continue

        seen.add(fingerprint)
        candidate["fingerprint"] = fingerprint
        candidates.append(candidate)

    return candidates


# ---------------------------------------------------------------------
# HISTORY, EXCEPTIONS, AND AUDIT
# ---------------------------------------------------------------------

def save_history_event(
    action: str,
    details: Dict[str, Any],
    before_hash: str = "",
    after_hash: str = "",
) -> None:
    append_json_record(
        HISTORY_FILE,
        {
            "event_id": make_id("event"),
            "timestamp": now_iso(),
            "action": action,
            "details": details,
            "before_hash": before_hash,
            "after_hash": after_hash,
            "version": VERSION,
        },
    )


def save_activity(action: str, details: Dict[str, Any]) -> None:
    append_json_record(
        ACTIVITY_FILE,
        {
            "timestamp": now_iso(),
            "action": action,
            "details": details,
            "version": VERSION,
        },
    )


def save_exception(
    category: str,
    message: str,
    candidate_id: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> None:
    append_json_record(
        EXCEPTIONS_FILE,
        {
            "exception_id": make_id("exception"),
            "timestamp": now_iso(),
            "category": category,
            "message": message,
            "candidate_id": candidate_id,
            "details": details or {},
            "status": "open",
        },
    )


def save_candidates(candidates: List[Dict[str, Any]]) -> None:
    atomic_write_json(
        CANDIDATES_FILE,
        {
            "version": VERSION,
            "updated_at": now_iso(),
            "candidates": candidates,
        },
    )


def load_candidates() -> List[Dict[str, Any]]:
    data = read_json(CANDIDATES_FILE, default={})

    if isinstance(data, list):
        return data

    return unwrap_records(data)


def save_report(report: Dict[str, Any]) -> None:
    atomic_write_json(REPORT_FILE, report)


# ---------------------------------------------------------------------
# BACKUPS AND DIRECTORY MUTATIONS
# ---------------------------------------------------------------------

def create_directory_backup(directory: Any, label: str = "before_update") -> str:
    ensure_directories()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{label}_{timestamp}_{uuid.uuid4().hex[:6]}.json"

    atomic_write_json(backup_path, directory)

    return str(backup_path)


def apply_candidate_to_directory(
    directory: Any,
    candidate: Dict[str, Any],
) -> Tuple[Any, bool]:
    resource = copy.deepcopy(candidate.get("resource", {}))
    state_code = resource.get("state_code", "")

    if not state_code or state_code not in STATE_NAMES:
        return directory, False

    # Preserve provenance and verification details on the public record.
    resource["sources"] = copy.deepcopy(
        candidate.get("evidence", {}).get("sources", [])
    )

    resource["verification"] = {
        "status": "verified",
        "verified_at": now_iso(),
        "verification_version": VERSION,
        "checks": copy.deepcopy(
            candidate.get("decision", {}).get("checks", {})
        ),
        "score": candidate.get("decision", {}).get("score"),
        "score_is_probability": False,
    }

    resource["status"] = "active"
    resource["verification_status"] = "verified"
    resource["updated_at"] = now_iso()

    return insert_resource_into_directory(
        directory,
        state_code,
        resource,
    )


def publish_verified_candidates(
    directory: Any,
    candidates: List[Dict[str, Any]],
) -> Tuple[Any, List[str]]:
    published = []

    for candidate in candidates:
        decision = safe_dict(candidate.get("decision"))

        if not decision.get("auto_publish"):
            continue

        if candidate.get("status") not in {"verified", "approved"}:
            continue

        updated_directory, changed = apply_candidate_to_directory(
            directory,
            candidate,
        )

        if changed:
            directory = updated_directory
            candidate["status"] = "published"
            candidate["published_at"] = now_iso()
            published.append(candidate["candidate_id"])

    return directory, published


# ---------------------------------------------------------------------
# EXISTING RECORD VERIFICATION / RETIREMENT SAFETY
# ---------------------------------------------------------------------

CLOSURE_PHRASES = (
    "permanently closed",
    "organization has closed",
    "services have permanently ended",
    "no longer providing services",
    "program permanently discontinued",
)


def positive_closure_evidence(text: str) -> bool:
    lowered = (text or "").lower()

    return any(phrase in lowered for phrase in CLOSURE_PHRASES)


def update_existing_resource_status(
    resource: Dict[str, Any],
    crawl_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Safe lifecycle handling for existing public listings.

    A failed crawl is not proof of closure.
    A timeout, DNS error, 403, 404, robots denial, or missing snapshot
    does not cause deletion or retirement.

    Positive closure language is recorded for later repeated checks.
    This function does not hard-delete records.
    """
    updated = copy.deepcopy(resource)

    text = extract_text(crawl_result)
    status_code = crawl_result.get("status_code")
    error = normalize_text(
        get_first(crawl_result, ("error", "crawl_error", "failure_reason"))
    )

    if positive_closure_evidence(text):
        history = updated.get("closure_evidence", [])

        if not isinstance(history, list):
            history = []

        evidence_hash = stable_hash(text)

        if not any(
            item.get("evidence_hash") == evidence_hash
            for item in history
            if isinstance(item, dict)
        ):
            history.append({
                "checked_at": now_iso(),
                "evidence_hash": evidence_hash,
                "excerpt": text[:1000],
                "source_url": record_source_url(crawl_result),
            })

        updated["closure_evidence"] = history

        if len(history) >= RETIREMENT_CONFIRMATIONS_REQUIRED:
            updated["status"] = "retired"
            updated["retired_at"] = now_iso()
            updated["retirement_reason"] = (
                "Repeated positive closure evidence; record retained."
            )
        else:
            updated["status"] = "verification_pending"

        updated["updated_at"] = now_iso()
        return updated

    # A crawl error is not a closure signal.
    if error or status_code in (403, 404, 408, 429, 500, 502, 503, 504):
        updated["verification_status"] = "stale"
        updated["last_verification_error"] = error or str(status_code)
        updated["last_verification_attempt"] = now_iso()
        updated["status"] = updated.get("status", "active")
        return updated

    if not text:
        updated["verification_status"] = "stale"
        updated["last_verification_attempt"] = now_iso()
        updated["status"] = updated.get("status", "active")
        return updated

    updated["last_verification_attempt"] = now_iso()
    updated["verification_status"] = "checked"
    updated["last_verification_error"] = ""
    return updated


def mark_old_records_stale(directory: Any) -> Tuple[Any, int]:
    """
    Mark old records for rechecking without removing them.
    """
    changed = 0
    cutoff = time.time() - (STALE_AFTER_DAYS * 86400)

    def process_state(state_record: Dict[str, Any]) -> None:
        nonlocal changed

        resources = state_record.get("resources", [])

        if not isinstance(resources, list):
            return

        for index, resource in enumerate(resources):
            if not isinstance(resource, dict):
                continue

            last_checked = normalize_text(
                get_first(
                    resource,
                    (
                        "last_verification_attempt",
                        "verified_at",
                        "updated_at",
                        "created_at",
                    ),
                )
            )

            if not last_checked:
                continue

            try:
                parsed = datetime.fromisoformat(
                    last_checked.replace("Z", "+00:00")
                )
                age = parsed.timestamp()
            except Exception:
                continue

            if age < cutoff and resource.get("status") != "retired":
                if resource.get("verification_status") != "stale":
                    resources[index]["verification_status"] = "stale"
                    resources[index]["last_stale_marked"] = now_iso()
                    changed += 1

    if isinstance(directory, list):
        for state_record in directory:
            if isinstance(state_record, dict):
                process_state(state_record)

    elif isinstance(directory, dict):
        for key in ("states", "state_directory", "records"):
            values = directory.get(key)

            if isinstance(values, list):
                for state_record in values:
                    if isinstance(state_record, dict):
                        process_state(state_record)

        for key, state_record in directory.items():
            if key not in {"states", "state_directory", "records"}:
                if isinstance(state_record, dict):
                    process_state(state_record)

    return directory, changed


# ---------------------------------------------------------------------
# MAIN ORCHESTRATOR
# ---------------------------------------------------------------------

def run_automated_updates(
    auto_apply: bool = False,
) -> Dict[str, Any]:
    """
    Run the public directory workflow.

    auto_apply=False:
        Discover, verify, score, and stage candidates.

    auto_apply=True:
        Also publish only candidates passing all strict gates.

    Uncertain candidates remain in the maintenance queue.
    """
    ensure_directories()

    directory, directory_path = load_directory()

    if not directory:
        report = {
            "version": VERSION,
            "timestamp": now_iso(),
            "status": "blocked",
            "message": "No public directory file was found or loaded.",
            "directory_path": directory_path,
            "published": 0,
            "staged": 0,
        }

        save_report(report)
        save_exception("directory_missing", report["message"])
        return report

    before_hash = stable_hash(directory)

    reviews, snapshots = load_crawler_inputs()

    candidates = build_candidates(
        reviews,
        snapshots,
        directory,
    )

    published_ids = []

    if auto_apply:
        publishable = [
            item for item in candidates
            if item.get("decision", {}).get("auto_publish")
        ]

        if publishable:
            create_directory_backup(directory, "before_publish")

            directory, published_ids = publish_verified_candidates(
                directory,
                publishable,
            )

            if published_ids:
                save_directory(directory)

    # Preserve all candidates, including those that need maintenance.
    save_candidates(candidates)

    after_hash = stable_hash(directory)

    if before_hash != after_hash:
        save_history_event(
            "automated_publish",
            {
                "published_candidate_ids": published_ids,
                "published_count": len(published_ids),
                "directory_path": str(DIRECTORY_FILE),
            },
            before_hash,
            after_hash,
        )

    pending_count = sum(
        1 for item in candidates
        if item.get("status") in {
            "pending_maintenance",
            "needs_maintenance",
        }
    )

    duplicate_count = sum(
        1 for item in candidates
        if item.get("status") == "duplicate"
    )

    verified_count = sum(
        1 for item in candidates
        if item.get("decision", {}).get("auto_publish")
    )

    report = {
        "version": VERSION,
        "timestamp": now_iso(),
        "status": "completed",
        "directory_path": str(DIRECTORY_FILE),
        "crawler_reviews_read": len(reviews),
        "crawler_snapshots_read": len(snapshots),
        "candidates_discovered": len(candidates),
        "verified_candidates": verified_count,
        "published": len(published_ids),
        "pending_maintenance": pending_count,
        "duplicates_detected": duplicate_count,
        "auto_apply": bool(auto_apply),
        "published_candidate_ids": published_ids,
        "private_data_accessed": False,
        "message": (
            "Public directory workflow completed. "
            "Uncertain records remain queued for network maintenance."
        ),
    }

    save_report(report)

    save_activity(
        "directory_workflow_completed",
        report,
    )

    return report


# ---------------------------------------------------------------------
# MAINTENANCE APPROVAL
# ---------------------------------------------------------------------

def review_candidate(
    candidate_id: str,
    decision: str,
    notes: str = "",
) -> Dict[str, Any]:
    """
    Network-maintainer decision for an uncertain candidate.

    This is not a survivor-facing task.

    Allowed decisions:
      approve
      reject
      defer
    """
    allowed = {"approve", "reject", "defer"}

    if decision not in allowed:
        return {
            "success": False,
            "message": f"Decision must be one of: {sorted(allowed)}",
        }

    candidates = load_candidates()
    found = None

    for candidate in candidates:
        if candidate.get("candidate_id") == candidate_id:
            found = candidate
            break

    if found is None:
        return {
            "success": False,
            "message": "Candidate not found.",
        }

    found["maintenance_review"] = {
        "decision": decision,
        "notes": normalize_text(notes),
        "reviewed_at": now_iso(),
    }

    if decision == "approve":
        # Approval does not bypass missing core evidence.
        checks = safe_dict(
            found.get("decision", {}).get("checks")
        )

        required = (
            "name_present",
            "state_recognized",
            "website_https",
            "source_provenance",
            "service_evidence",
            "not_duplicate",
        )

        if not all(checks.get(key) for key in required):
            found["status"] = "pending_maintenance"
            found["maintenance_review"]["decision"] = "defer"
            found["maintenance_review"]["notes"] = (
                "Approval blocked because required evidence checks failed. "
                + normalize_text(notes)
            )
        else:
            found["status"] = "approved"

    elif decision == "reject":
        found["status"] = "rejected"

    else:
        found["status"] = "pending_maintenance"

    found["updated_at"] = now_iso()
    save_candidates(candidates)

    save_history_event(
        "candidate_maintenance_review",
        {
            "candidate_id": candidate_id,
            "decision": found["status"],
            "notes": normalize_text(notes),
        },
    )

    return {
        "success": True,
        "candidate": found,
    }


def apply_approved_candidates() -> Dict[str, Any]:
    directory, _ = load_directory()
    candidates = load_candidates()

    approved = [
        candidate for candidate in candidates
        if candidate.get("status") == "approved"
    ]

    if not approved:
        return {
            "success": True,
            "published": 0,
            "message": "No approved candidates are ready to publish.",
        }

    create_directory_backup(directory, "before_approved_publish")

    before_hash = stable_hash(directory)
    published_ids = []

    for candidate in approved:
        directory, changed = apply_candidate_to_directory(
            directory,
            candidate,
        )

        if changed:
            candidate["status"] = "published"
            candidate["published_at"] = now_iso()
            published_ids.append(candidate["candidate_id"])

    if published_ids:
        save_directory(directory)
        save_candidates(candidates)

    after_hash = stable_hash(directory)

    save_history_event(
        "approved_candidates_published",
        {
            "published_candidate_ids": published_ids,
        },
        before_hash,
        after_hash,
    )

    return {
        "success": True,
        "published": len(published_ids),
        "published_candidate_ids": published_ids,
    }


# ---------------------------------------------------------------------
# APP COMPATIBILITY FUNCTIONS
# ---------------------------------------------------------------------

def get_directory_update_status() -> Dict[str, Any]:
    report = read_json(REPORT_FILE, default={})
    candidates = load_candidates()

    return {
        "version": VERSION,
        "last_report": report,
        "candidate_count": len(candidates),
        "pending_maintenance": sum(
            1 for item in candidates
            if item.get("status") in {
                "pending_maintenance",
                "needs_maintenance",
            }
        ),
        "verified": sum(
            1 for item in candidates
            if item.get("decision", {}).get("auto_publish")
        ),
        "published": sum(
            1 for item in candidates
            if item.get("status") == "published"
        ),
        "duplicates": sum(
            1 for item in candidates
            if item.get("status") == "duplicate"
        ),
        "directory_file": str(DIRECTORY_FILE),
    }


def get_directory_exceptions() -> List[Dict[str, Any]]:
    data = read_json(EXCEPTIONS_FILE, default=[])

    return data if isinstance(data, list) else []


def get_directory_history() -> List[Dict[str, Any]]:
    data = read_json(HISTORY_FILE, default=[])

    return data if isinstance(data, list) else []


def export_current_directory() -> Any:
    directory, _ = load_directory()
    return directory


def get_all_candidates() -> List[Dict[str, Any]]:
    return load_candidates()


def get_directory_candidates() -> List[Dict[str, Any]]:
    return get_all_candidates()


def build_source_registry() -> Dict[str, Dict[str, Any]]:
    """
    Compatibility helper for the app's source registry display.
    """
    reviews, snapshots = load_crawler_inputs()
    registry = {}

    for record in reviews + snapshots:
        url = record_source_url(record)

        if not url:
            continue

        registry[url] = {
            "url": url,
            "host": host_from_url(url),
            "source_id": record_source_id(record),
            "last_seen": now_iso(),
            "snapshot_file": record.get("_snapshot_file", ""),
        }

    return registry


def rollback_directory(version_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Restore a prior backup while preserving the current state as a backup.

    Rollback itself is recorded as a new history event.
    """
    ensure_directories()

    if version_file:
        requested = Path(version_file)

        if not requested.is_absolute():
            requested = BACKUP_DIR / requested

        backup_path = requested
    else:
        backups = sorted(
            BACKUP_DIR.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        backup_path = backups[0] if backups else None

    if not backup_path or not backup_path.exists():
        return {
            "success": False,
            "message": "No valid directory backup was found.",
        }

    restored = read_json(backup_path, default=None)

    if restored is None:
        return {
            "success": False,
            "message": "The selected backup could not be read.",
        }

    current, _ = load_directory()
    before_hash = stable_hash(current)

    create_directory_backup(current, "before_rollback")

    save_directory(restored)
    after_hash = stable_hash(restored)

    save_history_event(
        "directory_rollback",
        {
            "restored_backup": backup_path.name,
        },
        before_hash,
        after_hash,
    )

    return {
        "success": True,
        "message": "Directory restored. Previous state was backed up.",
        "restored_backup": backup_path.name,
    }


# ---------------------------------------------------------------------
# SELF TEST
# ---------------------------------------------------------------------

def self_test() -> Dict[str, Any]:
    """
    Offline tests for the directory updater.

    Contact information is optional. Missing email or phone must
    never cause an otherwise valid resource to fail verification.

    No network requests are made.
    """

    tests = {}

    # State normalization
    tests["state_alias_abbr"] = (
        normalize_state_record({
            "abbr": "WV",
            "name": "West Virginia",
            "url": "https://example.org",
        }).get("code") == "WV"
    )

    tests["state_name_resolution"] = (
        resolve_state_code("West Virginia") == "WV"
    )

    # Website validation
    tests["https_url_validation"] = (
        validate_resource_url("https://example.org")
    )

    tests["http_rejected_for_auto_publish"] = (
        not validate_resource_url("http://example.org")
    )

    # Contact extraction when contact details exist
    sample_with_contact = (
        "Emergency shelter services. "
        "Call (304) 555-0182. "
        "Contact us at help@example.org."
    )

    tests["email_extraction"] = (
        extract_email(sample_with_contact) == "help@example.org"
    )

    tests["phone_extraction"] = (
        extract_phone(sample_with_contact) == "304-555-0182"
    )

    # Contact extraction when no contact details exist
    sample_without_contact = (
        "This organization provides emergency shelter "
        "and housing assistance."
    )

    missing_email = extract_email(sample_without_contact)
    missing_phone = extract_phone(sample_without_contact)

    tests["missing_email_is_allowed"] = (
        missing_email == ""
    )

    tests["missing_phone_is_allowed"] = (
        missing_phone == ""
    )

    tests["missing_contact_does_not_fail_format"] = (
        (
            not missing_phone
            or validate_phone(missing_phone)
        )
        and (
            not missing_email
            or validate_email(missing_email)
        )
    )

    # Service extraction
    tests["service_extraction"] = (
        "emergency shelter" in extract_services(
            sample_without_contact
        )
    )

    # Temporary website failure must not retire a resource
    failed_resource = update_existing_resource_status(
        {"status": "active"},
        {
            "status_code": 503,
            "error": "Service unavailable",
        },
    )

    tests["temporary_failure_not_retired"] = (
        failed_resource.get("status") == "active"
    )

    tests["failed_crawl_marks_stale"] = (
        failed_resource.get("verification_status") == "stale"
    )

    # Closure evidence must not retire after one observation
    closure_resource = update_existing_resource_status(
        {"status": "active"},
        {
            "text": "Our organization has permanently closed.",
            "url": "https://example.org/closure",
        },
    )

    tests["closure_requires_repeated_evidence"] = (
        closure_resource.get("status") != "retired"
    )

    # Source independence
    tests["same_domain_not_independent"] = (
        not is_independent_host(
            "www.example.org",
            "services.example.org",
        )
    )

    tests["different_domains_independent"] = (
        is_independent_host(
            "example.org",
            "another-example.net",
        )
    )

    # Privacy boundary
    tests["private_file_guard"] = file_is_private(
        DATA_DIR / "survivor_profiles.json"
    )

    passed = sum(
        1 for result in tests.values()
        if result is True
    )

    failed = [
        name for name, result in tests.items()
        if result is not True
    ]

    return {
        "version": VERSION,
        "passed": passed,
        "failed": len(failed),
        "total": len(tests),
        "success": len(failed) == 0,
        "failed_tests": failed,
        "tests": tests,
        "network_requests": 0,
        "contact_information_required": False,
    }


# ---------------------------------------------------------------------
# OPTIONAL COMMAND-LINE ENTRY
# ---------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print(json.dumps(self_test(), indent=2))

    result = run_automated_updates(auto_apply=False)
    print(json.dumps(result, indent=2))
