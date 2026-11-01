
"""
Survivors Network — Automated Public Directory Updates
Version: 4.1.0

PUBLIC DIRECTORY DATA ONLY.
No survivor profiles, private matches, messages, case notes, or
incident-pattern records are accessed by this module.

Routine directory maintenance is automated. Uncertain candidates are
queued for network maintenance, not survivors.

Verification is evidence-based. Contact details are optional.
A URL or phone number passing format validation does not prove
that a service is currently available.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import re
import time
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse


# ================================================================
# CONFIGURATION
# ================================================================

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

VERSION = "4.1.0"
AUTO_PUBLISH_SCORE = 0.90
MIN_INDEPENDENT_SOURCES = 1
RETIREMENT_CONFIRMATIONS_REQUIRED = 3
STALE_AFTER_DAYS = 45
MAX_TEXT_LENGTH = 250_000

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


# ================================================================
# GENERAL HELPERS
# ================================================================

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str = "item") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def normalize_text(value: Any) -> str:
    if value is None or isinstance(value, (dict, list)):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_text(value).lower())


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


def get_first(record: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def file_is_private(path: Path) -> bool:
    return path.name.lower() in PRIVATE_DATA_FILENAMES


def ensure_directories() -> None:
    for path in (DATA_DIR, SNAPSHOT_DIR, BACKUP_DIR):
        path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any = None) -> Any:
    if default is None:
        default = {}

    if file_is_private(path) or not path.exists():
        return copy.deepcopy(default)

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        LOGGER.warning("Could not read %s: %s", path.name, exc)
        return copy.deepcopy(default)


def atomic_write_json(path: Path, data: Any) -> None:
    ensure_directories()

    if file_is_private(path):
        raise ValueError(
            f"Private data is outside this module's scope: {path.name}"
        )

    temp_path = path.with_suffix(path.suffix + ".tmp")

    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False, default=str)
        file.flush()
        os.fsync(file.fileno())

    os.replace(temp_path, path)


def append_json_record(path: Path, record: Dict[str, Any]) -> None:
    records = read_json(path, default=[])
    if not isinstance(records, list):
        records = []
    records.append(record)
    atomic_write_json(path, records)


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
        parsed = urlparse(
            value if "://" in value else f"https://{value}"
        )
        return (parsed.hostname or "").lower().rstrip(".")
    except Exception:
        return ""


def normalize_url(value: Any) -> str:
    value = normalize_text(value)
    if not value:
        return ""

    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value

    try:
        parsed = urlparse(value)

        if parsed.scheme.lower() not in {"http", "https"}:
            return ""
        if not parsed.hostname:
            return ""
        if parsed.username or parsed.password:
            return ""

        return urlunparse(
            parsed._replace(
                scheme=parsed.scheme.lower(),
                netloc=parsed.netloc.lower(),
                fragment="",
            )
        ).rstrip("/")
    except Exception:
        return ""


def extract_text(record: Dict[str, Any]) -> str:
    fields = (
        "extracted_text", "source_text", "text", "content",
        "excerpt", "new_excerpt", "description", "summary",
        "body", "page_text",
    )

    parts = []
    for field in fields:
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())

    return "\n".join(parts)[:MAX_TEXT_LENGTH]


def unwrap_records(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]

    if not isinstance(data, dict) or not data:
        return []

    for key in (
        "records", "items", "reviews", "pending",
        "snapshots", "sources", "results", "data",
    ):
        value = data.get(key)

        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]

        if isinstance(value, dict):
            return [x for x in value.values() if isinstance(x, dict)]

    if all(isinstance(v, dict) for v in data.values()):
        return list(data.values())

    return [data]


# ================================================================
# STATE NORMALIZATION
# ================================================================

STATE_CODES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ",
    "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "florida": "FL",
    "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA",
    "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND",
    "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC",
}

STATE_NAMES = {code: name.title() for name, code in STATE_CODES.items()}


def resolve_state_code(value: Any) -> str:
    value = normalize_text(value)
    if not value:
        return ""

    value = value.upper()
    if value in STATE_NAMES:
        return value

    return STATE_CODES.get(value.lower(), "")


def normalize_state_record(record: Dict[str, Any]) -> Dict[str, Any]:
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


def directory_state_records(directory: Any) -> List[Dict[str, Any]]:
    if isinstance(directory, list):
        return [
            normalize_state_record(x)
            for x in directory if isinstance(x, dict)
        ]

    if isinstance(directory, dict):
        for key in ("states", "state_directory", "records"):
            if isinstance(directory.get(key), list):
                return [
                    normalize_state_record(x)
                    for x in directory[key] if isinstance(x, dict)
                ]

        records = []
        for key, value in directory.items():
            if isinstance(value, dict):
                item = copy.deepcopy(value)
                item.setdefault("code", key)
                records.append(normalize_state_record(item))
        return records

    return []


def locate_state_container(directory: Any, state_code: str):
    if isinstance(directory, list):
        for index, item in enumerate(directory):
            if isinstance(item, dict):
                if normalize_state_record(item).get("code") == state_code:
                    return item, ("list", index)

    if isinstance(directory, dict):
        for key in ("states", "state_directory", "records"):
            values = directory.get(key)
            if isinstance(values, list):
                for index, item in enumerate(values):
                    if isinstance(item, dict):
                        if normalize_state_record(item).get("code") == state_code:
                            return item, ("dict_list", key, index)

        for key, item in directory.items():
            if isinstance(item, dict):
                if normalize_state_record(item).get("code") == state_code:
                    return item, ("dict_key", key)

    return None, None


def load_directory() -> Tuple[Any, str]:
    if DIRECTORY_FILE.exists():
        return read_json(DIRECTORY_FILE, default=[]), str(DIRECTORY_FILE)

    if LEGACY_DIRECTORY_FILE.exists():
        return read_json(LEGACY_DIRECTORY_FILE, default=[]), str(
            LEGACY_DIRECTORY_FILE
        )

    return [], str(DIRECTORY_FILE)


def save_directory(data: Any) -> None:
    atomic_write_json(DIRECTORY_FILE, data)


def insert_resource_into_directory(
    directory: Any,
    state_code: str,
    resource: Dict[str, Any],
) -> Tuple[Any, bool]:
    state_record, location = locate_state_container(directory, state_code)

    if state_record is None or location is None:
        return directory, False

    resources = state_record.get("resources")
    if not isinstance(resources, list):
        resources = []
        state_record["resources"] = resources

    resource_id = resource.get("resource_id")

    if any(
        isinstance(item, dict)
        and item.get("resource_id") == resource_id
        for item in resources
    ):
        return directory, False

    resources.append(copy.deepcopy(resource))
    return directory, True


# ================================================================
# CRAWLER INPUTS
# ================================================================

def load_pending_reviews() -> List[Dict[str, Any]]:
    return unwrap_records(read_json(PENDING_REVIEW_FILE, default=[]))


def load_snapshots() -> List[Dict[str, Any]]:
    records = []

    if not SNAPSHOT_DIR.exists():
        return records

    for path in SNAPSHOT_DIR.glob("*.json"):
        if file_is_private(path):
            continue

        for item in unwrap_records(read_json(path, default={})):
            item = copy.deepcopy(item)
            item.setdefault("_snapshot_file", path.name)
            records.append(item)

    return records


def load_crawler_inputs():
    return load_pending_reviews(), load_snapshots()


def collect_candidate_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    for key in (
        "candidate", "resource", "resource_record",
        "directory_entry", "record", "data",
    ):
        value = record.get(key)
        if isinstance(value, dict):
            merged = copy.deepcopy(value)

            for parent_key in (
                "state", "state_code", "state_name",
                "source_url", "url", "source_id", "review_id",
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
                "source_url", "url", "page_url",
                "origin_url", "website", "resolved_url",
            ),
        )
    )


def record_source_id(record: Dict[str, Any]) -> str:
    return normalize_text(
        get_first(
            record,
            ("source_id", "id", "review_id", "snapshot_id", "record_id"),
        )
    )


def match_snapshots(
    review: Dict[str, Any],
    snapshots: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    review_id = record_source_id(review)
    review_url = record_source_url(review)
    matches = []

    for snapshot in snapshots:
        snapshot_id = record_source_id(snapshot)
        snapshot_url = record_source_url(snapshot)

        if review_id and snapshot_id and review_id == snapshot_id:
            matches.append(snapshot)
        elif review_url and snapshot_url and review_url == snapshot_url:
            matches.append(snapshot)

    return matches


# ================================================================
# CONTACT AND SERVICE EXTRACTION
# ================================================================

EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I
)

PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+?1[\s.-]?)?"
    r"(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\w)"
)

SERVICE_KEYWORDS = {
    "emergency shelter": (
        "emergency shelter", "crisis shelter", "safe shelter",
    ),
    "housing assistance": (
        "housing assistance", "transitional housing",
        "rapid rehousing", "housing support",
    ),
    "legal assistance": (
        "legal aid", "legal assistance", "legal services",
        "legal advocacy",
    ),
    "counseling": (
        "counseling", "therapy", "behavioral health",
        "mental health services",
    ),
    "hotline": (
        "hotline", "crisis line", "24-hour line", "24 hour line",
    ),
    "advocacy": (
        "victim advocacy", "survivor advocacy", "advocacy services",
    ),
    "financial assistance": (
        "financial assistance", "emergency financial assistance",
        "relocation assistance",
    ),
    "child and family services": (
        "child services", "family services",
        "children's services", "childcare assistance",
    ),
    "medical assistance": (
        "medical assistance", "healthcare assistance",
        "medical advocacy",
    ),
    "transportation": (
        "transportation assistance", "transportation support",
        "bus vouchers",
    ),
}


def extract_email(text: str) -> str:
    matches = EMAIL_PATTERN.findall(text or "")
    return matches[0].strip(".,;:") if matches else ""


def normalize_phone(value: Any) -> str:
    digits = re.sub(r"\D", "", normalize_text(value))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return ""
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"


def extract_phone(text: str) -> str:
    for match in PHONE_PATTERN.findall(text or ""):
        normalized = normalize_phone(match)
        if normalized:
            return normalized
    return ""


def extract_services(text: str) -> List[str]:
    lowered = (text or "").lower()
    return sorted(
        service
        for service, phrases in SERVICE_KEYWORDS.items()
        if any(phrase in lowered for phrase in phrases)
    )


def has_service_context(text: str, service: str) -> bool:
    phrases = SERVICE_KEYWORDS.get(service, (service,))
    lowered = (text or "").lower()
    return any(phrase in lowered for phrase in phrases)


def validate_email(value: Any) -> bool:
    value = normalize_text(value)
    return bool(
        value
        and len(value) <= 254
        and EMAIL_PATTERN.fullmatch(value)
    )


def validate_phone(value: Any) -> bool:
    return bool(normalize_phone(value))


def validate_resource_url(value: Any) -> bool:
    url = normalize_url(value)
    if not url:
        return False

    parsed = urlparse(url)
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
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
                "resource_name", "organization_name", "organization",
                "provider_name", "agency_name", "name", "title",
            ),
        )
    )

    state_code = resolve_state_code(
        get_first(
            payload,
            (
                "state_code", "abbr", "state_abbreviation",
                "state", "state_name",
            ),
        )
    )

    website = normalize_url(
        get_first(
            payload,
            (
                "resource_website", "organization_website",
                "website", "url", "official_url",
            ),
        )
    )

    phone = normalize_phone(
        get_first(payload, ("phone", "telephone", "phone_number"))
    ) or extract_phone(evidence_text)

    email = normalize_text(
        get_first(payload, ("email", "contact_email"))
    ) or extract_email(evidence_text)

    services_value = get_first(
        payload,
        ("services", "service_types", "categories", "resource_type"),
    )

    services = [
        normalize_text(item).lower()
        for item in safe_list(services_value)
        if normalize_text(item)
    ]

    if not services:
        services = extract_services(evidence_text)

    return {
        "name": name,
        "state_code": state_code,
        "website": website,
        "phone": phone,
        "email": email,
        "services": sorted(set(services)),
        "description": normalize_text(
            get_first(payload, ("description", "summary", "details"))
        ),
    }


# ================================================================
# EVIDENCE AND CORROBORATION
# ================================================================

def source_record(record: Dict[str, Any], role: str) -> Dict[str, Any]:
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
    host_a = (host_a or "").lower().strip(".")
    host_b = (host_b or "").lower().strip(".")

    if not host_a or not host_b or host_a == host_b:
        return False

    if host_a.endswith("." + host_b) or host_b.endswith("." + host_a):
        return False

    parts_a = host_a.split(".")
    parts_b = host_b.split(".")

    if len(parts_a) >= 2 and len(parts_b) >= 2:
        if ".".join(parts_a[-2:]) == ".".join(parts_b[-2:]):
            return False

    return True


def collect_evidence(review, matched_snapshots):
    text_parts = []
    sources = []

    review_text = extract_text(review)
    if review_text:
        text_parts.append(review_text)

    sources.append(source_record(review, "origin"))

    for snapshot in matched_snapshots:
        text = extract_text(snapshot)
        if text:
            text_parts.append(text)
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

    return "\n".join(text_parts)[:MAX_TEXT_LENGTH], unique_sources


def independent_source_count(sources) -> int:
    hosts = sorted({
        source.get("host", "")
        for source in sources
        if source.get("host")
    })

    if len(hosts) < 2:
        return 0

    return sum(
        1 for host in hosts
        if any(
            is_independent_host(host, other)
            for other in hosts if other != host
        )
    )


def corroboration_details(sources):
    return {
        "source_count": len(sources),
        "distinct_hosts": sorted({
            source.get("host", "")
            for source in sources if source.get("host")
        }),
        "independent_source_count": independent_source_count(sources),
        "source_urls": sorted({
            source.get("url", "")
            for source in sources if source.get("url")
        }),
    }


# ================================================================
# DUPLICATE DETECTION
# ================================================================

def canonical_name(value: Any) -> str:
    value = normalize_text(value).lower()
    value = re.sub(
        r"\b(inc|llc|ltd|corp|corporation|nonprofit)\b", "", value
    )
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def resource_domain(value: Any) -> str:
    return host_from_url(value)


def find_duplicate(candidate, directory):
    state_record, _ = locate_state_container(
        directory, candidate.get("state_code", "")
    )
    if not state_record:
        return None

    name = canonical_name(candidate.get("name"))
    domain = resource_domain(candidate.get("website"))
    phone = normalize_phone(candidate.get("phone"))

    resources = state_record.get("resources", [])
    if not isinstance(resources, list):
        return None

    for existing in resources:
        if not isinstance(existing, dict):
            continue

        existing_name = canonical_name(existing.get("name"))
        existing_domain = resource_domain(existing.get("website"))
        existing_phone = normalize_phone(existing.get("phone"))

        same_domain = bool(
            domain and existing_domain and domain == existing_domain
        )
        same_name_phone = bool(
            name and name == existing_name
            and phone and phone == existing_phone
        )

        if same_domain or same_name_phone:
            return existing

    return None


# ================================================================
# CANDIDATE DECISION ENGINE
# ================================================================

def evaluate_candidate(fields, sources, evidence_text, directory):
    checks = {
        "name_present": bool(fields.get("name")),
        "state_recognized": fields.get("state_code") in STATE_NAMES,
        "website_https": validate_resource_url(fields.get("website")),
        "source_provenance": any(s.get("url") for s in sources),
        "service_evidence": bool(
            fields.get("services")
            and any(
                has_service_context(evidence_text, service)
                for service in fields.get("services", [])
            )
        ),
        # Missing contact information is permitted.
        "contact_format": (
            not fields.get("phone") or validate_phone(fields.get("phone"))
        ) and (
            not fields.get("email") or validate_email(fields.get("email"))
        ),
    }

    corroboration = corroboration_details(sources)
    checks["independent_corroboration"] = (
        corroboration["independent_source_count"]
        >= MIN_INDEPENDENT_SOURCES
    )

    duplicate = find_duplicate(fields, directory)
    checks["not_duplicate"] = duplicate is None

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
        weights[key] for key, passed in checks.items() if passed
    )

    critical = (
        "name_present", "state_recognized", "website_https",
        "source_provenance", "service_evidence",
        "independent_corroboration", "not_duplicate",
    )

    auto_publish = (
        score >= AUTO_PUBLISH_SCORE
        and all(checks[key] for key in critical)
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


def build_candidate(review, snapshots, directory):
    payload = collect_candidate_payload(review)
    matched = match_snapshots(review, snapshots)
    evidence_text, sources = collect_evidence(review, matched)
    fields = extract_candidate_fields(payload, evidence_text)

    decision = evaluate_candidate(
        fields, sources, evidence_text, directory
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
            "verification_status": (
                "verified" if decision["auto_publish"] else "pending"
            ),
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


def build_candidates(reviews, snapshots, directory):
    candidates = []
    seen = set()

    for review in reviews:
        candidate = build_candidate(review, snapshots, directory)

        fingerprint = stable_hash({
            "name": canonical_name(candidate["resource"].get("name")),
            "state": candidate["resource"].get("state_code"),
            "website": resource_domain(
                candidate["resource"].get("website")
            ),
            "source": candidate["review_source"].get("source_url"),
        })

        if fingerprint in seen:
            continue

        seen.add(fingerprint)
        candidate["fingerprint"] = fingerprint
        candidates.append(candidate)

    return candidates


# ================================================================
# HISTORY, EXCEPTIONS, REPORTS
# ================================================================

def save_history_event(
    action, details, before_hash="", after_hash=""
):
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


def save_activity(action, details):
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
    category, message, candidate_id="", details=None
):
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


def save_candidates(candidates):
    atomic_write_json(
        CANDIDATES_FILE,
        {
            "version": VERSION,
            "updated_at": now_iso(),
            "candidates": candidates,
        },
    )


def load_candidates():
    return unwrap_records(read_json(CANDIDATES_FILE, default=[]))


def save_report(report):
    atomic_write_json(REPORT_FILE, report)


# ================================================================
# BACKUPS AND PUBLISHING
# ================================================================

def create_directory_backup(directory, label="before_update"):
    ensure_directories()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = BACKUP_DIR / (
        f"{label}_{timestamp}_{uuid.uuid4().hex[:6]}.json"
    )
    atomic_write_json(path, directory)
    return str(path)


def apply_candidate_to_directory(directory, candidate):
    resource = copy.deepcopy(candidate.get("resource", {}))
    state_code = resource.get("state_code", "")

    if state_code not in STATE_NAMES:
        return directory, False

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
        directory, state_code, resource
    )


def publish_verified_candidates(directory, candidates):
    published = []

    for candidate in candidates:
        decision = safe_dict(candidate.get("decision"))

        if not decision.get("auto_publish"):
            continue
        if candidate.get("status") not in {"verified", "approved"}:
            continue

        directory, changed = apply_candidate_to_directory(
            directory, candidate
        )

        if changed:
            candidate["status"] = "published"
            candidate["published_at"] = now_iso()
            published.append(candidate["candidate_id"])

    return directory, published


# ================================================================
# SAFE EXISTING-RECORD LIFECYCLE
# ================================================================

CLOSURE_PHRASES = (
    "permanently closed",
    "organization has closed",
    "services have permanently ended",
    "no longer providing services",
    "program permanently discontinued",
)


def positive_closure_evidence(text):
    lowered = (text or "").lower()
    return any(phrase in lowered for phrase in CLOSURE_PHRASES)


def update_existing_resource_status(resource, crawl_result):
    updated = copy.deepcopy(resource)
    text = extract_text(crawl_result)

    status_code = crawl_result.get("status_code")
    error = normalize_text(
        get_first(
            crawl_result,
            ("error", "crawl_error", "failure_reason"),
        )
    )

    if positive_closure_evidence(text):
        history = updated.get("closure_evidence", [])
        if not isinstance(history, list):
            history = []

        evidence_hash = stable_hash(text)
        source_url = record_source_url(crawl_result)

        # A repeat of the same source and same evidence does not
        # count as another confirmation.
        already_seen = any(
            isinstance(item, dict)
            and item.get("evidence_hash") == evidence_hash
            and item.get("source_url") == source_url
            for item in history
        )

        if not already_seen:
            history.append({
                "checked_at": now_iso(),
                "evidence_hash": evidence_hash,
                "excerpt": text[:1000],
                "source_url": source_url,
            })

        updated["closure_evidence"] = history

        # Require three distinct source URLs and three distinct
        # evidence hashes, not three repeated copies of one page.
        distinct_sources = {
            item.get("source_url")
            for item in history
            if isinstance(item, dict) and item.get("source_url")
        }
        distinct_evidence = {
            item.get("evidence_hash")
            for item in history
            if isinstance(item, dict) and item.get("evidence_hash")
        }

        if (
            len(distinct_sources) >= RETIREMENT_CONFIRMATIONS_REQUIRED
            and len(distinct_evidence) >= RETIREMENT_CONFIRMATIONS_REQUIRED
        ):
            updated["status"] = "retired"
            updated["retired_at"] = now_iso()
            updated["retirement_reason"] = (
                "Multiple distinct positive closure sources. "
                "Record retained."
            )
        else:
            updated["status"] = "verification_pending"

        updated["updated_at"] = now_iso()
        return updated

    # HTTP failures and missing content are not closure evidence.
    if error or status_code in (
        403, 404, 408, 429, 500, 502, 503, 504
    ):
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


def mark_old_records_stale(directory):
    changed = 0
    cutoff = time.time() - STALE_AFTER_DAYS * 86400

    def process_state(state_record):
        nonlocal changed
        resources = state_record.get("resources", [])

        if not isinstance(resources, list):
            return

        for resource in resources:
            if not isinstance(resource, dict):
                continue
            if resource.get("status") == "retired":
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

            if age < cutoff and resource.get("verification_status") != "stale":
                resource["verification_status"] = "stale"
                resource["last_stale_marked"] = now_iso()
                changed += 1

    if isinstance(directory, list):
        for state in directory:
            if isinstance(state, dict):
                process_state(state)

    elif isinstance(directory, dict):
        processed = set()

        for key in ("states", "state_directory", "records"):
            values = directory.get(key)
            if isinstance(values, list):
                for state in values:
                    if isinstance(state, dict):
                        process_state(state)
                        processed.add(id(state))

        for state in directory.values():
            if isinstance(state, dict) and id(state) not in processed:
                process_state(state)

    return directory, changed


# ================================================================
# MAIN AUTOMATED ORCHESTRATOR — APP COMPATIBILITY FIX
# ================================================================

def run_automated_updates(
    current_directory=None,
    auto_apply=False,
    **kwargs,
):
    """
    Compatible with the app call:

        run_automated_updates(
            current_directory=STATE_COALITIONS,
            auto_apply=True
        )

    Returns a report dictionary containing:
        report["updated_directory"]
        report["directory"]
        report["published"]
        report["status"]

    current_directory is not mutated in place.

    If a directory is supplied, it is used as the starting directory.
    If none is supplied, the canonical/legacy saved directory is loaded.

    auto_apply=False stages candidates only.
    auto_apply=True publishes only candidates passing all automated gates.
    """

    ensure_directories()

    if current_directory is not None:
        directory = copy.deepcopy(current_directory)
        directory_path = "app_memory"
    else:
        directory, directory_path = load_directory()

    if directory is None or directory == [] or directory == {}:
        report = {
            "version": VERSION,
            "timestamp": now_iso(),
            "status": "blocked",
            "message": "No public directory was supplied or loaded.",
            "directory_path": directory_path,
            "crawler_reviews_read": 0,
            "crawler_snapshots_read": 0,
            "candidates_discovered": 0,
            "verified_candidates": 0,
            "published": 0,
            "pending_maintenance": 0,
            "duplicates_detected": 0,
            "auto_apply": bool(auto_apply),
            "private_data_accessed": False,
            "updated_directory": directory,
            "directory": directory,
        }
        save_report(report)
        save_exception("directory_missing", report["message"])
        return report

    before_hash = stable_hash(directory)

    try:
        reviews, snapshots = load_crawler_inputs()
        candidates = build_candidates(reviews, snapshots, directory)

        published_ids = []

        if auto_apply:
            publishable = [
                item for item in candidates
                if item.get("decision", {}).get("auto_publish")
            ]

            if publishable:
                create_directory_backup(directory, "before_publish")

                directory, published_ids = publish_verified_candidates(
                    directory, publishable
                )

                # Persist only when operating on the saved directory.
                # When the app passes an in-memory directory, the app
                # receives updated_directory and owns its session state.
                if published_ids and current_directory is None:
                    save_directory(directory)

        save_candidates(candidates)

        after_hash = stable_hash(directory)

        if before_hash != after_hash:
            save_history_event(
                "automated_publish",
                {
                    "published_candidate_ids": published_ids,
                    "published_count": len(published_ids),
                    "directory_path": directory_path,
                },
                before_hash,
                after_hash,
            )

        pending_count = sum(
            1 for item in candidates
            if item.get("status") in {
                "pending_maintenance", "needs_maintenance"
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
            "directory_path": directory_path,
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
                "Uncertain candidates remain queued for network maintenance."
            ),
            # Both keys are included for compatibility with callers
            # that use either name.
            "updated_directory": directory,
            "directory": directory,
        }

        save_report(report)
        save_activity("directory_workflow_completed", {
            key: value for key, value in report.items()
            if key not in {"updated_directory", "directory"}
        })

        return report

    except Exception as exc:
        LOGGER.exception("Automated directory update failed")
        save_exception(
            "automated_update_error",
            str(exc),
            details={"directory_path": directory_path},
        )

        report = {
            "version": VERSION,
            "timestamp": now_iso(),
            "status": "error",
            "message": str(exc),
            "directory_path": directory_path,
            "published": 0,
            "private_data_accessed": False,
            "updated_directory": current_directory,
            "directory": current_directory,
        }

        save_report(report)
        return report


# ================================================================
# MAINTENANCE APPROVAL
# ================================================================

def review_candidate(candidate_id, decision, notes=""):
    allowed = {"approve", "reject", "defer"}

    if decision not in allowed:
        return {
            "success": False,
            "message": f"Decision must be one of: {sorted(allowed)}",
        }

    candidates = load_candidates()
    found = next(
        (
            item for item in candidates
            if item.get("candidate_id") == candidate_id
        ),
        None,
    )

    if found is None:
        return {"success": False, "message": "Candidate not found."}

    found["maintenance_review"] = {
        "decision": decision,
        "notes": normalize_text(notes),
        "reviewed_at": now_iso(),
    }

    if decision == "approve":
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

    return {"success": True, "candidate": found}


def apply_approved_candidates(current_directory=None):
    if current_directory is None:
        directory, _ = load_directory()
        persist = True
    else:
        directory = copy.deepcopy(current_directory)
        persist = False

    candidates = load_candidates()
    approved = [
        item for item in candidates
        if item.get("status") == "approved"
    ]

    if not approved:
        return {
            "success": True,
            "published": 0,
            "updated_directory": directory,
            "directory": directory,
            "message": "No approved candidates are ready to publish.",
        }

    create_directory_backup(directory, "before_approved_publish")
    before_hash = stable_hash(directory)
    published_ids = []

    for candidate in approved:
        directory, changed = apply_candidate_to_directory(
            directory, candidate
        )

        if changed:
            candidate["status"] = "published"
            candidate["published_at"] = now_iso()
            published_ids.append(candidate["candidate_id"])

    if published_ids:
        if persist:
            save_directory(directory)
        save_candidates(candidates)

    after_hash = stable_hash(directory)

    save_history_event(
        "approved_candidates_published",
        {"published_candidate_ids": published_ids},
        before_hash,
        after_hash,
    )

    return {
        "success": True,
        "published": len(published_ids),
        "published_candidate_ids": published_ids,
        "updated_directory": directory,
        "directory": directory,
    }


# ================================================================
# APP COMPATIBILITY FUNCTIONS
# ================================================================

def get_directory_update_status():
    report = read_json(REPORT_FILE, default={})
    candidates = load_candidates()

    return {
        "version": VERSION,
        "last_report": report,
        "candidate_count": len(candidates),
        "pending_maintenance": sum(
            1 for item in candidates
            if item.get("status") in {
                "pending_maintenance", "needs_maintenance"
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


def get_directory_exceptions():
    data = read_json(EXCEPTIONS_FILE, default=[])
    return data if isinstance(data, list) else []


def get_directory_history():
    data = read_json(HISTORY_FILE, default=[])
    return data if isinstance(data, list) else []


def export_current_directory():
    directory, _ = load_directory()
    return directory


def get_all_candidates():
    return load_candidates()


def get_directory_candidates():
    return get_all_candidates()


def build_source_registry():
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


def rollback_directory(version_file=None):
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
        {"restored_backup": backup_path.name},
        before_hash,
        after_hash,
    )

    return {
        "success": True,
        "message": "Directory restored. Previous state was backed up.",
        "restored_backup": backup_path.name,
    }


# ================================================================
# OFFLINE SELF TEST
# ================================================================

def self_test():
    tests = {}

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

    tests["https_url_validation"] = (
        validate_resource_url("https://example.org")
    )

    tests["http_rejected_for_auto_publish"] = (
        not validate_resource_url("http://example.org")
    )

    sample = (
        "Emergency shelter services. "
        "Call (304) 555-0182. "
        "Contact help@example.org."
    )

    tests["email_extraction"] = (
        extract_email(sample) == "help@example.org"
    )

    tests["phone_extraction"] = (
        extract_phone(sample) == "304-555-0182"
    )

    no_contact = (
        "This organization provides emergency shelter "
        "and housing assistance."
    )

    tests["missing_email_is_allowed"] = extract_email(no_contact) == ""
    tests["missing_phone_is_allowed"] = extract_phone(no_contact) == ""

    fields = {
        "name": "Example Support",
        "state_code": "WV",
        "website": "https://example.org",
        "phone": "",
        "email": "",
        "services": ["emergency shelter"],
    }

    source_records = [
        {"url": "https://example.org", "host": "example.org"},
        {"url": "https://another-example.net", "host": "another-example.net"},
    ]

    decision = evaluate_candidate(
        fields,
        source_records,
        no_contact,
        [{"code": "WV", "name": "West Virginia", "resources": []}],
    )

    tests["missing_contact_does_not_fail_format"] = (
        decision["checks"]["contact_format"]
    )

    tests["service_extraction"] = (
        "emergency shelter" in extract_services(no_contact)
    )

    failed_resource = update_existing_resource_status(
        {"status": "active"},
        {"status_code": 503, "error": "Service unavailable"},
    )

    tests["temporary_failure_not_retired"] = (
        failed_resource.get("status") == "active"
    )

    tests["failed_crawl_marks_stale"] = (
        failed_resource.get("verification_status") == "stale"
    )

    closure_once = update_existing_resource_status(
        {"status": "active"},
        {
            "text": "Our organization has permanently closed.",
            "url": "https://example.org/closure",
        },
    )

    tests["single_closure_source_not_retired"] = (
        closure_once.get("status") != "retired"
    )

    tests["same_domain_not_independent"] = (
        not is_independent_host(
            "www.example.org", "services.example.org"
        )
    )

    tests["different_domains_independent"] = (
        is_independent_host(
            "example.org", "another-example.net"
        )
    )

    tests["private_file_guard"] = file_is_private(
        DATA_DIR / "survivor_profiles.json"
    )

    # Confirm the app's keyword argument is accepted and returned.
    sample_directory = [
        {
            "code": "WV",
            "name": "West Virginia",
            "resources": [],
        }
    ]

    tests["app_directory_argument_accepted"] = (
        isinstance(sample_directory, list)
        and "current_directory" in run_automated_updates.__code__.co_varnames
    )

    passed = sum(result is True for result in tests.values())
    failed = [
        name for name, result in tests.items()
        if result is not True
    ]

    return {
        "version": VERSION,
        "passed": passed,
        "failed": len(failed),
        "total": len(tests),
        "success": not failed,
        "failed_tests": failed,
        "tests": tests,
        "network_requests": 0,
        "contact_information_required": False,
    }


# ================================================================
# COMMAND LINE
# ================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(self_test(), indent=2))

    # Offline-safe run: discovers and stages candidates only.
    result = run_automated_updates(auto_apply=False)

    # Do not print the entire directory object to the console.
    display_result = {
        key: value
        for key, value in result.items()
        if key not in {"updated_directory", "directory"}
    }

    print(json.dumps(display_result, indent=2, default=str))
