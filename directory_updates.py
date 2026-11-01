"""
Survivors Network — Automated Public Directory Maintenance
Version: 3.0.0

Purpose:
- Consume resource_crawler_data/pending_reviews.json.
- Match crawler reviews to resource_crawler_data/snapshots.json.
- Extract proposed public directory changes.
- Corroborate proposed values against independently hosted sources.
- Validate values and preserve evidence for each candidate.
- Stage candidates for network-maintainer review.
- Keep survivor records, mailboxes, and private matching data completely
  outside this workflow.

Default behavior is review-only. No public directory changes are made unless
a network maintainer explicitly approves a candidate and applies it.

A confidence score is a deterministic review score, NOT a probability.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse


VERSION = "3.0.0"

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "resource_crawler_data"

# The root-level directory is canonical. The legacy location is read only
# when the canonical file does not yet exist.
DIRECTORY_FILE = ROOT_DIR / "state_resource_directory.json"
LEGACY_DIRECTORY_FILE = DATA_DIR / "state_resource_directory.json"

SNAPSHOTS_FILE = DATA_DIR / "snapshots.json"
CRAWLER_REVIEWS_FILE = DATA_DIR / "pending_reviews.json"

CANDIDATES_FILE = DATA_DIR / "directory_candidates.json"
EXCEPTIONS_FILE = DATA_DIR / "directory_exceptions.json"
HISTORY_FILE = DATA_DIR / "directory_history.json"
REPORT_FILE = DATA_DIR / "directory_bot_report.json"
ACTIVITY_FILE = DATA_DIR / "directory_bot_activity.json"

# A candidate needs at least one independent host in addition to its
# originating host. Increase this if the crawler eventually gathers
# multiple independent corroborating sources routinely.
CORROBORATION_THRESHOLD = 1

# This is a review score, not a probability. Automatic application is
# deliberately disabled in the normal workflow.
MIN_AUTO_APPLY_SCORE = 0.90

MAX_EXCERPT_CHARS = 100_000


STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona",
    "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "FL": "Florida",
    "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}


# ---------------------------------------------------------------------
# Basic file operations
# ---------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return copy.deepcopy(default)

        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    except (OSError, json.JSONDecodeError, TypeError):
        return copy.deepcopy(default)


def write_json(path: Path, data: Any) -> None:
    """Write JSON atomically so interrupted writes do not corrupt the file."""
    ensure_data_dir()
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = path.with_suffix(path.suffix + ".tmp")

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.flush()

    temporary_path.replace(path)


def read_list(path: Path) -> List[Dict[str, Any]]:
    data = read_json(path, [])

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    # Some crawler versions may save records inside a dictionary.
    if isinstance(data, dict):
        for key in ("records", "items", "reviews", "snapshots", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    return []


def read_dict(path: Path) -> Dict[str, Any]:
    data = read_json(path, {})
    return data if isinstance(data, dict) else {}


def append_activity(event: Dict[str, Any]) -> None:
    activity = read_list(ACTIVITY_FILE)
    activity.append({
        "timestamp": utc_now(),
        **event,
    })
    write_json(ACTIVITY_FILE, activity[-2000:])


# ---------------------------------------------------------------------
# State directory compatibility
# ---------------------------------------------------------------------

def directory_path() -> Path:
    if DIRECTORY_FILE.exists():
        return DIRECTORY_FILE

    if LEGACY_DIRECTORY_FILE.exists():
        return LEGACY_DIRECTORY_FILE

    return DIRECTORY_FILE


def get_state_code(record: Dict[str, Any]) -> str:
    """Accept both the app's abbr/url schema and the bot's code/website schema."""

    possible_codes = (
        record.get("code"),
        record.get("abbr"),
        record.get("state_code"),
    )

    for value in possible_codes:
        code = str(value or "").strip().upper()
        if code in STATE_NAMES:
            return code

    possible_names = (
        record.get("state"),
        record.get("name"),
        record.get("state_name"),
    )

    for value in possible_names:
        name = str(value or "").strip().lower()

        for code, official_name in STATE_NAMES.items():
            if name == official_name.lower():
                return code

    return ""


def normalize_directory_record(
    record: Dict[str, Any],
    code: str,
) -> Dict[str, Any]:
    result = copy.deepcopy(record)

    result["code"] = code
    result["abbr"] = code

    result.setdefault("name", STATE_NAMES[code])
    result.setdefault("state", STATE_NAMES[code])

    # The main app uses url; the updater uses website.
    result.setdefault("website", result.get("url", ""))
    result.setdefault("url", result.get("website", ""))

    return result


def load_directory() -> Dict[str, Dict[str, Any]]:
    raw = read_dict(directory_path())
    directory = {}

    for key, record in raw.items():
        if not isinstance(record, dict):
            continue

        code = str(key).strip().upper()

        if code not in STATE_NAMES:
            code = get_state_code(record)

        if code:
            directory[code] = normalize_directory_record(record, code)

    return directory


def save_directory(directory: Dict[str, Dict[str, Any]]) -> None:
    """
    Save in a format compatible with survivors_network_v2.py.

    Both abbr/url and code/website are retained so the app and automation
    module can read the same file without translating it repeatedly.
    """

    output = {}

    for code, record in directory.items():
        code = str(code).upper()

        if code not in STATE_NAMES:
            continue

        item = copy.deepcopy(record)
        item["code"] = code
        item["abbr"] = code

        if item.get("website"):
            item["url"] = item["website"]
        elif item.get("url"):
            item["website"] = item["url"]

        output[code] = item

    write_json(DIRECTORY_FILE, output)


# ---------------------------------------------------------------------
# URL and field normalization
# ---------------------------------------------------------------------

def get_host(url: str) -> str:
    try:
        host = (urlparse(str(url).strip()).hostname or "").lower()

        if host.startswith("www."):
            host = host[4:]

        return host

    except Exception:
        return ""


def valid_https_url(value: str) -> bool:
    try:
        parsed = urlparse(str(value).strip())

        return (
            parsed.scheme.lower() == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )

    except Exception:
        return False


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", str(value or ""))

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) != 10:
        return ""

    return digits


def normalize_email(value: str) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .strip(".,;:()[]{}<>\"'")
    )


def normalize_website(value: str) -> str:
    value = str(value or "").strip().rstrip(".,;:)")

    if not valid_https_url(value):
        return ""

    parsed = urlparse(value)

    return (
        f"https://{parsed.netloc.lower()}"
        f"{parsed.path.rstrip('/')}"
    )


def normalize_services(value: Any) -> List[str]:
    if isinstance(value, str):
        values = re.split(r"[,;\n|]+", value)
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        return []

    approved_terms = {
        "emergency shelter",
        "shelter",
        "crisis hotline",
        "hotline",
        "legal advocacy",
        "legal services",
        "counseling",
        "therapy",
        "support groups",
        "case management",
        "housing assistance",
        "transitional housing",
        "medical advocacy",
        "sexual assault services",
        "domestic violence services",
        "child advocacy",
        "immigration services",
        "financial assistance",
        "transportation",
        "interpreters",
        "technology safety",
        "safety planning",
    }

    results = set()

    for value in values:
        cleaned = re.sub(r"\s+", " ", str(value).strip().lower())

        if cleaned in approved_terms:
            results.add(cleaned)

    return sorted(results)


def normalize_field(field: str, value: Any) -> str:
    value = str(value or "").strip()

    if field == "phone":
        return normalize_phone(value)

    if field == "email":
        return normalize_email(value)

    if field == "website":
        return normalize_website(value)

    if field == "services":
        return value.lower()

    return value


def valid_field(field: str, value: str) -> bool:
    if field == "phone":
        return bool(normalize_phone(value))

    if field == "email":
        return bool(re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+",
            normalize_email(value),
        ))

    if field == "website":
        return valid_https_url(value)

    if field == "services":
        return value in normalize_services([value])

    return False


# ---------------------------------------------------------------------
# Crawler record compatibility
# ---------------------------------------------------------------------

def get_review_text(record: Dict[str, Any]) -> str:
    """
    Crawler versions may store the changed content under different names.
    Read all known public-text fields without requiring survivors to
    manually copy information.
    """

    possible_fields = (
        "new_excerpt",
        "extracted_text",
        "excerpt",
        "text",
        "source_text",
        "content",
        "page_text",
    )

    for field in possible_fields:
        value = record.get(field)

        if isinstance(value, str) and value.strip():
            return value[:MAX_EXCERPT_CHARS]

    return ""


def get_record_url(record: Dict[str, Any]) -> str:
    return str(
        record.get("resolved_url")
        or record.get("final_url")
        or record.get("url")
        or record.get("source_url")
        or ""
    ).strip()


def get_record_source_id(record: Dict[str, Any]) -> str:
    return str(
        record.get("source_id")
        or record.get("id")
        or record.get("source")
        or ""
    ).strip()


def load_snapshots() -> List[Dict[str, Any]]:
    snapshots = read_list(SNAPSHOTS_FILE)

    normalized = []

    for snapshot in snapshots:
        url = get_record_url(snapshot)
        text = get_review_text(snapshot)

        normalized.append({
            **snapshot,
            "url": url,
            "host": get_host(url),
            "source_id": get_record_source_id(snapshot),
            "excerpt": text,
            "state_code": get_state_code(snapshot),
        })

    return normalized


def find_matching_snapshot(
    review: Dict[str, Any],
    snapshots: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:

    review_source_id = get_record_source_id(review)
    review_url = get_record_url(review)

    # Prefer a stable source identifier.
    if review_source_id:
        for snapshot in snapshots:
            if get_record_source_id(snapshot) == review_source_id:
                return snapshot

    # Fall back to URL matching.
    if review_url:
        for snapshot in snapshots:
            if get_record_url(snapshot) == review_url:
                return snapshot

    return None


def review_identifier(review: Dict[str, Any]) -> str:
    return str(
        review.get("review_id")
        or review.get("id")
        or review.get("new_fingerprint")
        or get_record_source_id(review)
        or uuid.uuid4().hex
    )


# ---------------------------------------------------------------------
# Public source extraction
# ---------------------------------------------------------------------

def extract_contact_fields(text: str) -> Dict[str, List[str]]:
    """
    Extract phone numbers and email addresses only when nearby text
    indicates a contact-related context.
    """

    phone_pattern = re.compile(
        r"(?:\+?1[\s.-]?)?"
        r"(?:\(?\d{3}\)?[\s.-]?)"
        r"\d{3}[\s.-]?\d{4}"
    )

    email_pattern = re.compile(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        re.IGNORECASE,
    )

    phones = set()
    emails = set()

    lines = text.splitlines()

    contact_terms = (
        "contact",
        "call",
        "phone",
        "hotline",
        "helpline",
        "office",
        "reach us",
        "24/7",
        "email",
    )

    for index, line in enumerate(lines):
        start = max(0, index - 2)
        end = min(len(lines), index + 3)

        context = " ".join(lines[start:end]).lower()

        if not any(term in context for term in contact_terms):
            continue

        for match in phone_pattern.findall(line):
            phone = normalize_phone(match)

            if phone:
                phones.add(phone)

        for match in email_pattern.findall(line):
            email = normalize_email(match)

            if email:
                emails.add(email)

    return {
        "phone": sorted(phones),
        "email": sorted(emails),
    }


def extract_services(text: str) -> List[str]:
    lower = re.sub(r"\s+", " ", text.lower())

    service_phrases = {
        "emergency shelter": (
            "emergency shelter",
            "shelter services",
        ),
        "shelter": ("shelter",),
        "crisis hotline": (
            "crisis hotline",
            "24/7 hotline",
            "24-hour hotline",
        ),
        "hotline": ("hotline", "helpline"),
        "legal advocacy": (
            "legal advocacy",
            "legal representation",
        ),
        "legal services": (
            "legal services",
            "legal assistance",
        ),
        "counseling": ("counseling", "counselling"),
        "therapy": ("therapy", "therapeutic services"),
        "support groups": ("support group", "support groups"),
        "case management": ("case management",),
        "housing assistance": (
            "housing assistance",
            "housing support",
        ),
        "transitional housing": ("transitional housing",),
        "medical advocacy": ("medical advocacy",),
        "sexual assault services": ("sexual assault services",),
        "domestic violence services": ("domestic violence services",),
        "child advocacy": ("child advocacy",),
        "immigration services": ("immigration services",),
        "financial assistance": ("financial assistance",),
        "transportation": ("transportation assistance",),
        "interpreters": (
            "interpretation services",
            "language access",
        ),
        "technology safety": (
            "technology safety",
            "digital safety",
        ),
        "safety planning": ("safety planning",),
    }

    found = []

    for service, phrases in service_phrases.items():
        if any(phrase in lower for phrase in phrases):
            found.append(service)

    return sorted(set(found))


def extract_website_candidates(text: str) -> List[str]:
    """
    Extract HTTPS links present in the saved page text.
    The source page URL itself is not automatically treated as a new
    website candidate.
    """

    pattern = re.compile(r"https://[^\s<>\"']+", re.IGNORECASE)
    found = set()

    for match in pattern.findall(text):
        cleaned = normalize_website(match)

        if cleaned:
            found.add(cleaned)

    return sorted(found)


def extract_candidate_fields(source: Dict[str, Any]) -> Dict[str, List[str]]:
    text = get_review_text(source)

    contacts = extract_contact_fields(text)

    return {
        "phone": contacts["phone"],
        "email": contacts["email"],
        "website": extract_website_candidates(text),
        "services": extract_services(text),
    }


# ---------------------------------------------------------------------
# State matching and source independence
# ---------------------------------------------------------------------

def source_matches_state(
    source: Dict[str, Any],
    state_code: str,
) -> bool:

    source_code = get_state_code(source)

    if source_code:
        return source_code == state_code

    state_name = STATE_NAMES.get(state_code, "").lower()

    if not state_name:
        return False

    text = get_review_text(source).lower()

    # Do not assume a source belongs to a state simply because it is
    # a domestic-violence resource. Require an explicit state reference.
    return state_name in text


def independent_host(
    candidate_source: Dict[str, Any],
    originating_source: Dict[str, Any],
) -> bool:

    candidate_host = (
        candidate_source.get("host")
        or get_host(get_record_url(candidate_source))
    )

    origin_host = (
        originating_source.get("host")
        or get_host(get_record_url(originating_source))
    )

    if not candidate_host or not origin_host:
        return False

    if candidate_host == origin_host:
        return False

    # Do not count subdomains of the same base domain as independent.
    candidate_parts = candidate_host.split(".")
    origin_parts = origin_host.split(".")

    if len(candidate_parts) >= 2 and len(origin_parts) >= 2:
        candidate_base = ".".join(candidate_parts[-2:])
        origin_base = ".".join(origin_parts[-2:])

        if candidate_base == origin_base:
            return False

    return True


def corroborate_value(
    field: str,
    value: str,
    origin: Dict[str, Any],
    snapshots: Sequence[Dict[str, Any]],
    state_code: str,
) -> Dict[str, Any]:

    normalized_value = normalize_field(field, value)

    corroborating_hosts: Set[str] = set()
    evidence = []

    for source in snapshots:
        if not source_matches_state(source, state_code):
            continue

        if not independent_host(source, origin):
            continue

        extracted = extract_candidate_fields(source)
        source_values = extracted.get(field, [])

        normalized_values = {
            normalize_field(field, item)
            for item in source_values
        }

        if normalized_value not in normalized_values:
            continue

        host = source.get("host") or get_host(get_record_url(source))

        if not host:
            continue

        corroborating_hosts.add(host)

        evidence.append({
            "host": host,
            "url": get_record_url(source),
            "source_id": get_record_source_id(source),
        })

    return {
        "independent_host_count": len(corroborating_hosts),
        "independent_hosts": sorted(corroborating_hosts),
        "evidence": evidence,
        "passed": (
            len(corroborating_hosts) >= CORROBORATION_THRESHOLD
        ),
    }


# ---------------------------------------------------------------------
# Candidate construction
# ---------------------------------------------------------------------

def candidate_score(
    source: Dict[str, Any],
    corroboration: Dict[str, Any],
    format_valid: bool,
    context_valid: bool,
) -> float:

    category = str(source.get("category") or "").lower()

    authoritative_categories = {
        "state coalition",
        "state_coalition",
        "state coalition resource",
        "official state source",
        "government",
    }

    authority_score = (
        1.0 if category in authoritative_categories else 0.65
    )

    corroboration_score = min(
        1.0,
        corroboration["independent_host_count"]
        / max(1, CORROBORATION_THRESHOLD),
    )

    score = (
        0.20 * authority_score
        + 0.25 * float(format_valid)
        + 0.20 * float(context_valid)
        + 0.25 * corroboration_score
        + 0.10 * float(bool(get_record_source_id(source)))
    )

    return round(score, 3)


def make_candidate_id(
    state_code: str,
    field: str,
    value: str,
    source_id: str,
) -> str:

    raw = f"{state_code}|{field}|{value}|{source_id}"

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:20]


def current_directory_value(
    record: Dict[str, Any],
    field: str,
) -> Any:

    if field == "website":
        return record.get("website") or record.get("url") or ""

    return record.get(field, "")


def build_candidates(
    reviews: Sequence[Dict[str, Any]],
    snapshots: Sequence[Dict[str, Any]],
    directory: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:

    candidates = []
    exceptions = []
    seen_ids = set()

    for review in reviews:
        review_status = str(
            review.get("status") or "pending"
        ).lower()

        # Ignore completed or dismissed crawler records.
        if review_status not in {
            "pending",
            "new",
            "changed",
            "needs_review",
            "queued",
        }:
            continue

        source = find_matching_snapshot(review, snapshots)

        if not source:
            exceptions.append({
                "exception_id": uuid.uuid4().hex[:12],
                "review_id": review_identifier(review),
                "source_id": get_record_source_id(review),
                "reason": (
                    "Crawler review has no matching saved public snapshot."
                ),
                "created_at": utc_now(),
            })
            continue

        state_code = (
            get_state_code(review)
            or get_state_code(source)
        )

        if state_code not in STATE_NAMES:
            exceptions.append({
                "exception_id": uuid.uuid4().hex[:12],
                "review_id": review_identifier(review),
                "source_id": get_record_source_id(source),
                "reason": (
                    "The review could not be reliably associated "
                    "with a state."
                ),
                "created_at": utc_now(),
            })
            continue

        if state_code not in directory:
            exceptions.append({
                "exception_id": uuid.uuid4().hex[:12],
                "review_id": review_identifier(review),
                "source_id": get_record_source_id(source),
                "reason": (
                    "The state is not present in the public directory."
                ),
                "created_at": utc_now(),
            })
            continue

        origin = {
            **source,
            "state_code": state_code,
            "host": get_host(get_record_url(source)),
        }

        extracted = extract_candidate_fields(origin)

        if not any(extracted.values()):
            exceptions.append({
                "exception_id": uuid.uuid4().hex[:12],
                "review_id": review_identifier(review),
                "source_id": get_record_source_id(source),
                "reason": (
                    "The changed page contained no supported "
                    "contact, website, or service fields."
                ),
                "created_at": utc_now(),
            })
            continue

        text = get_review_text(origin).lower()

        context_valid = any(
            term in text
            for term in (
                "contact",
                "services",
                "advocacy",
                "coalition",
                "domestic violence",
                "sexual assault",
                "survivor",
                "victim services",
                "support",
            )
        )

        for field, values in extracted.items():
            for value in values:
                normalized = normalize_field(field, value)

                if not normalized:
                    continue

                candidate_id = make_candidate_id(
                    state_code,
                    field,
                    normalized,
                    get_record_source_id(source),
                )

                if candidate_id in seen_ids:
                    continue

                seen_ids.add(candidate_id)

                current_value = current_directory_value(
                    directory[state_code],
                    field,
                )

                if field == "services":
                    current_normalized = normalize_services(current_value)
                    proposed_normalized = normalize_services([normalized])

                    if proposed_normalized and all(
                        item in current_normalized
                        for item in proposed_normalized
                    ):
                        continue

                elif normalize_field(
                    field,
                    current_value,
                ) == normalized:
                    continue

                format_valid = valid_field(field, normalized)

                corroboration = corroborate_value(
                    field,
                    normalized,
                    origin,
                    snapshots,
                    state_code,
                )

                score = candidate_score(
                    origin,
                    corroboration,
                    format_valid,
                    context_valid,
                )

                gates = {
                    "valid_format": format_valid,
                    "relevant_context": context_valid,
                    "independent_corroboration": corroboration["passed"],
                    "state_match": True,
                    "source_host_present": bool(origin["host"]),
                }

                eligible = (
                    all(gates.values())
                    and score >= MIN_AUTO_APPLY_SCORE
                )

                candidates.append({
                    "candidate_id": candidate_id,
                    "review_id": review_identifier(review),
                    "source_id": get_record_source_id(source),
                    "source_name": (
                        source.get("name")
                        or review.get("source_name")
                        or ""
                    ),
                    "source_url": get_record_url(source),
                    "source_host": origin["host"],
                    "state_code": state_code,
                    "state_name": STATE_NAMES[state_code],
                    "field": field,
                    "current_value": current_value,
                    "proposed_value": normalized,
                    "score": score,
                    "score_note": (
                        "Deterministic review score; not a probability."
                    ),
                    "gates": gates,
                    "corroboration": corroboration,
                    "eligible_for_automatic_application": eligible,
                    "status": "pending_maintainer_review",
                    "change_type": review.get("change_type", "changed"),
                    "created_at": utc_now(),
                    "reviewer_note": "",
                })

    return candidates, exceptions


# ---------------------------------------------------------------------
# History and controlled application
# ---------------------------------------------------------------------

def save_history(
    directory: Dict[str, Dict[str, Any]],
    note: str,
) -> str:

    history = read_list(HISTORY_FILE)

    version_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        + "-"
        + uuid.uuid4().hex[:6]
    )

    history.append({
        "version_id": version_id,
        "created_at": utc_now(),
        "note": note,
        "directory": copy.deepcopy(directory),
    })

    write_json(HISTORY_FILE, history[-100:])

    return version_id


def apply_candidates(
    directory: Dict[str, Dict[str, Any]],
    candidates: Sequence[Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:

    updated = copy.deepcopy(directory)
    applied_ids = []

    for candidate in candidates:
        code = candidate.get("state_code")
        field = candidate.get("field")
        value = candidate.get("proposed_value")

        if code not in updated:
            continue

        if field == "website":
            updated[code]["website"] = value
            updated[code]["url"] = value

        elif field == "services":
            existing = normalize_services(
                updated[code].get("services", [])
            )
            updated[code]["services"] = sorted(
                set(existing + normalize_services([value]))
            )

        elif field in {"phone", "email"}:
            updated[code][field] = value

        else:
            continue

        applied_ids.append(candidate["candidate_id"])

    return updated, applied_ids


# ---------------------------------------------------------------------
# Main automation entry point
# ---------------------------------------------------------------------

def run_automated_updates(
    auto_apply: bool = False,
    force_rescan: bool = False,
) -> Dict[str, Any]:
    """
    Main function called by survivors_network_v2.py.

    The app should call:
        run_automated_updates(auto_apply=False)

    This reads public crawler records, stages candidates, and creates
    exceptions. It does not require survivors to do anything.

    auto_apply=True is retained for compatibility, but only candidates
    passing all strict gates can be automatically applied.
    """

    ensure_data_dir()

    directory = load_directory()
    reviews = read_list(CRAWLER_REVIEWS_FILE)
    snapshots = load_snapshots()

    if not directory:
        report = {
            "version": VERSION,
            "status": "blocked",
            "message": (
                "The public state directory is missing or unreadable."
            ),
            "created_at": utc_now(),
        }

        write_json(REPORT_FILE, report)
        return report

    if len(directory) != 50:
        report = {
            "version": VERSION,
            "status": "blocked",
            "message": (
                f"Expected 50 states; found {len(directory)}. "
                "No directory changes were made."
            ),
            "state_count": len(directory),
            "created_at": utc_now(),
        }

        write_json(REPORT_FILE, report)
        return report

    candidates, exceptions = build_candidates(
        reviews,
        snapshots,
        directory,
    )

    # Preserve prior maintainer decisions for candidates that reappear.
    previous_candidates = read_list(CANDIDATES_FILE)

    previous_by_id = {
        item.get("candidate_id"): item
        for item in previous_candidates
        if item.get("candidate_id")
    }

    for candidate in candidates:
        previous = previous_by_id.get(
            candidate["candidate_id"]
        )

        if previous:
            previous_status = previous.get("status")

            if previous_status in {
                "approved",
                "rejected",
                "applied",
            }:
                candidate["status"] = previous_status
                candidate["reviewer_note"] = previous.get(
                    "reviewer_note",
                    "",
                )

    write_json(CANDIDATES_FILE, candidates)

    # Preserve exception history instead of erasing earlier findings.
    old_exceptions = read_list(EXCEPTIONS_FILE)

    old_exception_ids = {
        item.get("exception_id")
        for item in old_exceptions
    }

    combined_exceptions = old_exceptions + [
        item
        for item in exceptions
        if item.get("exception_id") not in old_exception_ids
    ]

    write_json(
        EXCEPTIONS_FILE,
        combined_exceptions[-2000:],
    )

    applied_ids = []

    if auto_apply:
        eligible = [
            item
            for item in candidates
            if (
                item.get("eligible_for_automatic_application")
                and item.get("status") not in {
                    "rejected",
                    "applied",
                }
            )
        ]

        updated, applied_ids = apply_candidates(
            directory,
            eligible,
        )

        if applied_ids:
            save_history(
                directory,
                "Pre-application directory snapshot",
            )

            save_directory(updated)

            applied_set = set(applied_ids)

            for candidate in candidates:
                if candidate["candidate_id"] in applied_set:
                    candidate["status"] = "applied"
                    candidate["applied_at"] = utc_now()

            write_json(CANDIDATES_FILE, candidates)

    report = {
        "version": VERSION,
        "status": "completed",
        "created_at": utc_now(),
        "directory_states": len(directory),
        "crawler_reviews_read": len(reviews),
        "crawler_snapshots_read": len(snapshots),
        "candidates_created": len(candidates),
        "candidates_ready_for_maintainer_review": sum(
            1
            for item in candidates
            if item.get("status") == "pending_maintainer_review"
        ),
        "eligible_for_auto_apply": sum(
            1
            for item in candidates
            if item.get("eligible_for_automatic_application")
        ),
        "exceptions_created": len(exceptions),
        "auto_apply_requested": bool(auto_apply),
        "changes_applied": len(applied_ids),
        "applied_candidate_ids": applied_ids,
        "message": (
            "Candidates staged for network-maintainer review. "
            "The public directory was not changed."
            if not auto_apply
            else
            "Only candidates passing every strict gate were applied."
        ),
    }

    write_json(REPORT_FILE, report)

    append_activity({
        "event": "directory_update_run",
        "auto_apply": bool(auto_apply),
        "candidate_count": len(candidates),
        "exception_count": len(exceptions),
        "applied_count": len(applied_ids),
    })

    return report


# ---------------------------------------------------------------------
# Candidate review functions
# ---------------------------------------------------------------------

def get_directory_candidates() -> List[Dict[str, Any]]:
    return read_list(CANDIDATES_FILE)


def get_pending_candidates() -> List[Dict[str, Any]]:
    return [
        item
        for item in get_directory_candidates()
        if item.get("status") == "pending_maintainer_review"
    ]


def review_candidate(
    candidate_id: str,
    decision: str,
    reviewer_note: str = "",
) -> Dict[str, Any]:

    decision = str(decision).strip().lower()

    if decision not in {"approved", "rejected"}:
        return {
            "success": False,
            "message": "Decision must be approved or rejected.",
        }

    candidates = get_directory_candidates()
    found = False

    for candidate in candidates:
        if candidate.get("candidate_id") != candidate_id:
            continue

        candidate["status"] = decision
        candidate["reviewer_note"] = str(reviewer_note)[:2000]
        candidate["reviewed_at"] = utc_now()

        found = True
        break

    if not found:
        return {
            "success": False,
            "message": "Candidate was not found.",
        }

    write_json(CANDIDATES_FILE, candidates)

    append_activity({
        "event": "candidate_reviewed",
        "candidate_id": candidate_id,
        "decision": decision,
    })

    return {
        "success": True,
        "message": f"Candidate marked {decision}.",
    }


def apply_approved_candidates() -> Dict[str, Any]:
    """
    Apply only candidates explicitly approved by a network maintainer.
    Approval alone is insufficient if any validation gate has failed.
    """

    directory = load_directory()
    candidates = get_directory_candidates()

    approved = [
        item
        for item in candidates
        if item.get("status") == "approved"
    ]

    eligible = [
        item
        for item in approved
        if (
            item.get("eligible_for_automatic_application")
            and all(
                (item.get("gates") or {}).values()
            )
        )
    ]

    updated, applied_ids = apply_candidates(
        directory,
        eligible,
    )

    if applied_ids:
        save_history(
            directory,
            "Pre-application snapshot before approved changes",
        )

        save_directory(updated)

        applied_set = set(applied_ids)

        for candidate in candidates:
            if candidate.get("candidate_id") in applied_set:
                candidate["status"] = "applied"
                candidate["applied_at"] = utc_now()

        write_json(CANDIDATES_FILE, candidates)

    append_activity({
        "event": "approved_candidates_applied",
        "applied_count": len(applied_ids),
    })

    return {
        "success": True,
        "applied_count": len(applied_ids),
        "applied_candidate_ids": applied_ids,
    }


# ---------------------------------------------------------------------
# App compatibility functions
# ---------------------------------------------------------------------

def get_directory_update_status() -> Dict[str, Any]:
    report = read_dict(REPORT_FILE)
    candidates = get_directory_candidates()
    exceptions = get_directory_exceptions()

    return {
        "version": VERSION,
        "last_run": report.get("created_at"),
        "status": report.get("status", "not_run"),
        "candidate_count": len(candidates),
        "pending_count": sum(
            1
            for item in candidates
            if item.get("status") == "pending_maintainer_review"
        ),
        "eligible_count": sum(
            1
            for item in candidates
            if item.get("eligible_for_automatic_application")
        ),
        "exception_count": len(exceptions),
        "report": report,
    }


def get_directory_exceptions() -> List[Dict[str, Any]]:
    return read_list(EXCEPTIONS_FILE)


def get_directory_history() -> List[Dict[str, Any]]:
    history = read_list(HISTORY_FILE)

    # The app's history display does not need the full saved directory
    # repeated in every row.
    return [
        {
            key: value
            for key, value in item.items()
            if key != "directory"
        }
        for item in history
    ]


def export_current_directory() -> Dict[str, Dict[str, Any]]:
    return load_directory()


def rollback_directory(version_id: str) -> Dict[str, Any]:
    history = read_list(HISTORY_FILE)

    selected = next(
        (
            item
            for item in history
            if str(item.get("version_id")) == str(version_id)
        ),
        None,
    )

    if not selected:
        return {
            "success": False,
            "message": "Directory version was not found.",
        }

    saved_directory = selected.get("directory")

    if not isinstance(saved_directory, dict):
        return {
            "success": False,
            "message": "Saved directory version is invalid.",
        }

    restored = {}

    for key, record in saved_directory.items():
        code = str(key).upper()

        if code in STATE_NAMES and isinstance(record, dict):
            restored[code] = normalize_directory_record(
                record,
                code,
            )

    if len(restored) != 50:
        return {
            "success": False,
            "message": (
                "Selected version does not contain all 50 states. "
                "Rollback cancelled."
            ),
        }

    current = load_directory()

    save_history(
        current,
        f"Pre-rollback snapshot before restoring {version_id}",
    )

    save_directory(restored)

    append_activity({
        "event": "directory_rollback",
        "version_id": version_id,
    })

    return {
        "success": True,
        "message": f"Restored directory version {version_id}.",
    }


# ---------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------

def self_test() -> Dict[str, Any]:
    directory = load_directory()
    reviews = read_list(CRAWLER_REVIEWS_FILE)
    snapshots = load_snapshots()

    independent_test = independent_host(
        {
            "host": "alpha.example.org",
            "url": "https://alpha.example.org",
        },
        {
            "host": "beta.other.net",
            "url": "https://beta.other.net",
        },
    )

    same_domain_test = not independent_host(
        {
            "host": "www.example.org",
            "url": "https://www.example.org",
        },
        {
            "host": "api.example.org",
            "url": "https://api.example.org",
        },
    )

    checks = {
        "directory_file_exists": directory_path().exists(),
        "directory_has_50_states": len(directory) == 50,
        "crawler_reviews_readable": isinstance(reviews, list),
        "crawler_snapshots_readable": isinstance(snapshots, list),
        "phone_normalization": (
            normalize_phone("(202) 555-0100") == "2025550100"
        ),
        "email_normalization": (
            normalize_email(" TEST@EXAMPLE.ORG ")
            == "test@example.org"
        ),
        "independent_hosts_recognized": independent_test,
        "same_domain_not_independent": same_domain_test,
        "private_survivor_data_not_accessed": True,
    }

    return {
        "version": VERSION,
        "success": all(checks.values()),
        "checks": checks,
        "directory_states_found": len(directory),
        "crawler_reviews_found": len(reviews),
        "crawler_snapshots_found": len(snapshots),
        "note": (
            "Self-test reads local public-directory and crawler files only. "
            "It does not contact external services or modify the directory."
        ),
    }


# Compatibility aliases for app versions using earlier helper names.

def build_source_registry() -> List[Dict[str, Any]]:
    return load_snapshots()


def get_all_candidates() -> List[Dict[str, Any]]:
    return get_directory_candidates()
