
"""
Survivors Network — Automated Directory Intelligence
=====================================================

Maintains the PUBLIC state resource directory using information
collected by resource_crawler.py.

Independent validation bots:
1. SourceBot          — source ingestion and identity
2. ContactBot         — phone and email extraction
3. LinkBot            — official website redirect validation
4. ServiceBot         — service-category extraction
5. FormatBot          — data and contact-format validation
6. CorroborationBot   — independent-source agreement
7. ConsistencyBot     — comparison with existing directory records
8. DecisionBot        — deterministic confidence scoring

Privacy boundary:
- This module reads public resource crawler data only.
- It never reads survivor entries, private records, or mailbox data.
- It never sends survivor information to external websites.

Storage:
- state_resource_directory.json lives in the repository root.
- Supporting JSON files live in resource_crawler_data/.
- Missing supporting files are initialized without overwriting existing data.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse


# =========================================================
# CONFIGURATION
# =========================================================

ROOT_DIR = Path(__file__).resolve().parent

DATA_DIR = ROOT_DIR / "resource_crawler_data"

SNAPSHOT_FILE = DATA_DIR / "snapshots.json"
REVIEW_FILE = DATA_DIR / "pending_reviews.json"
ACTIVITY_FILE = DATA_DIR / "activity_log.json"

# Canonical directory supplied for the application.
DIRECTORY_FILE = ROOT_DIR / "state_resource_directory.json"

# Legacy fallback location.
LEGACY_DIRECTORY_FILE = DATA_DIR / "state_resource_directory.json"

HISTORY_FILE = DATA_DIR / "directory_history.json"
EXCEPTION_FILE = DATA_DIR / "directory_exceptions.json"
REPORT_FILE = DATA_DIR / "directory_bot_report.json"

AUTO_APPLY_THRESHOLD = 0.82
CORROBORATION_THRESHOLD = 1

MAX_HISTORY = 100
MAX_EXCEPTIONS = 2000
MAX_ACTIVITY_EVENTS = 5000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("survivors_network_directory")


# =========================================================
# GENERAL UTILITIES
# =========================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def read_json(path: Path, default: Any) -> Any:
    path = Path(path)

    if not path.exists():
        return copy.deepcopy(default)

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read %s", path)
        return copy.deepcopy(default)


def write_json(path: Path, data: Any) -> bool:
    """
    Write JSON through a temporary file.

    Existing files are not replaced unless the new JSON has been
    completely written.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    try:
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False,
            )

            file.write("\n")
            file.flush()

        temporary.replace(path)
        return True

    except (OSError, TypeError, ValueError):
        logger.exception("Could not write %s", path)

        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass

        return False


def initialize_storage(storage_dir: Path = DATA_DIR) -> dict:
    """
    Initialize missing public-directory support files.

    Existing files are never overwritten.
    """

    storage_dir = Path(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)

    defaults = {
        "snapshots.json": {},
        "pending_reviews.json": [],
        "activity_log.json": [],
        "directory_history.json": [],
        "directory_exceptions.json": [],
        "directory_bot_report.json": {},
    }

    created = []

    for filename, default in defaults.items():
        path = storage_dir / filename

        if not path.exists():
            if write_json(path, default):
                created.append(filename)

    return {
        "success": True,
        "created": created,
        "storage_directory": str(storage_dir),
    }


def resolve_directory_path(
    storage_dir: Path = DATA_DIR,
) -> Path:
    """
    Prefer the repository-root directory.

    Retain compatibility with an older directory stored inside
    resource_crawler_data/.
    """

    if DIRECTORY_FILE.exists():
        return DIRECTORY_FILE

    legacy = Path(storage_dir) / DIRECTORY_FILE.name

    if legacy.exists():
        return legacy

    return DIRECTORY_FILE


def normalize_text(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", str(value or ""))

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) != 10:
        return ""

    return digits


def normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def normalize_host(value: str) -> str:
    try:
        host = (urlparse(str(value)).hostname or "").lower()

        if host.startswith("www."):
            host = host[4:]

        return host

    except ValueError:
        return ""


def valid_https_url(value: str) -> bool:
    try:
        parsed = urlparse(str(value))

        return (
            parsed.scheme.lower() == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )

    except ValueError:
        return False


def same_official_host(
    candidate_url: str,
    official_url: str,
) -> bool:
    candidate_host = normalize_host(candidate_url)
    official_host = normalize_host(official_url)

    if not candidate_host or not official_host:
        return False

    return (
        candidate_host == official_host
        or candidate_host.endswith("." + official_host)
    )


def unique_candidates(items: list[dict]) -> list[dict]:
    result = {}

    for item in items:
        value = item.get("value")

        if value:
            result[value] = item

    return list(result.values())


# =========================================================
# STORAGE EVENT LOG
# =========================================================

def record_activity(
    event: str,
    details: Optional[dict] = None,
    storage_dir: Path = DATA_DIR,
) -> bool:
    """
    Records public-directory maintenance events only.

    Never pass survivor-submitted notes, identities, or private
    incident details to this function.
    """

    path = Path(storage_dir) / ACTIVITY_FILE.name

    events = read_json(path, [])

    if not isinstance(events, list):
        events = []

    events.append({
        "timestamp": utc_now(),
        "event": event,
        "details": details or {},
    })

    events = events[-MAX_ACTIVITY_EVENTS:]

    return write_json(path, events)


# =========================================================
# STATE DIRECTORY HELPERS
# =========================================================

def build_state_lookup(directory: dict) -> dict:
    """
    Supports state names and two-letter state codes.
    """

    lookup = {}

    for state_name, record in directory.items():

        if not isinstance(record, dict):
            continue

        lookup[state_name.lower()] = state_name

        code = str(record.get("code", "")).upper()

        if code:
            lookup[code.lower()] = state_name

    return lookup


def resolve_state(
    state_value: Any,
    directory: dict,
) -> Optional[str]:

    lookup = build_state_lookup(directory)

    normalized = normalize_text(
        str(state_value or "")
    ).lower()

    return lookup.get(normalized)


# =========================================================
# SOURCE DATA INGESTION
# =========================================================

class SourceBot:
    """
    Reads public resource crawler snapshots and pending reviews.

    Supported text fields:
    - extracted_text
    - text
    - excerpt
    - new_excerpt
    """

    def __init__(self, storage_dir: Path = DATA_DIR):
        self.storage_dir = Path(storage_dir)

    def load_sources(self) -> list[dict]:

        snapshots = read_json(
            self.storage_dir / SNAPSHOT_FILE.name,
            {},
        )

        reviews = read_json(
            self.storage_dir / REVIEW_FILE.name,
            [],
        )

        sources = []

        if isinstance(snapshots, dict):
            snapshot_items = snapshots.items()

        elif isinstance(snapshots, list):
            snapshot_items = enumerate(snapshots)

        else:
            snapshot_items = []

        for source_id, snapshot in snapshot_items:

            if not isinstance(snapshot, dict):
                continue

            text = (
                snapshot.get("extracted_text")
                or snapshot.get("text")
                or snapshot.get("excerpt")
                or snapshot.get("new_excerpt")
                or ""
            )

            if not text:
                continue

            sources.append({
                **snapshot,
                "source_id": snapshot.get(
                    "source_id",
                    str(source_id),
                ),
                "source_text": text,
                "source_origin": "snapshot",
            })

        if isinstance(reviews, dict):
            review_items = list(reviews.values())

        elif isinstance(reviews, list):
            review_items = reviews

        else:
            review_items = []

        known_ids = {
            str(source.get("source_id"))
            for source in sources
        }

        for review in review_items:

            if not isinstance(review, dict):
                continue

            source_id = review.get("source_id")

            if source_id and str(source_id) in known_ids:
                continue

            text = (
                review.get("extracted_text")
                or review.get("new_excerpt")
                or review.get("excerpt")
                or ""
            )

            if not text:
                continue

            sources.append({
                **review,
                "source_id": source_id or stable_hash(review)[:20],
                "source_text": text,
                "source_origin": "review",
            })

            known_ids.add(str(source_id))

        return sources


# =========================================================
# CONTACT EXTRACTION BOT
# =========================================================

class ContactBot:
    """
    Extracts public phone numbers and email addresses.

    Telephone numbers require nearby contact-related context.
    """

    PHONE_PATTERN = re.compile(
        r"(?<!\d)"
        r"(?:\+?1[\s.-]?)?"
        r"(?:\(?\d{3}\)?[\s.-]?)"
        r"\d{3}[\s.-]?\d{4}"
        r"(?!\d)"
    )

    EMAIL_PATTERN = re.compile(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        re.IGNORECASE,
    )

    PHONE_CONTEXT = re.compile(
        r"\b("
        r"phone|telephone|tel|call|contact|office|"
        r"hotline|helpline|main line|intake|"
        r"information line|reach us"
        r")\b",
        re.IGNORECASE,
    )

    EMAIL_CONTEXT = re.compile(
        r"\b("
        r"email|e-mail|contact|write to us|"
        r"reach us|inquiries|office"
        r")\b",
        re.IGNORECASE,
    )

    def extract(self, text: str) -> dict:

        text = normalize_text(text)

        phones = []
        emails = []

        for match in self.PHONE_PATTERN.finditer(text):

            raw = match.group(0)
            normalized = normalize_phone(raw)

            if not normalized:
                continue

            start = max(0, match.start() - 90)
            end = min(len(text), match.end() + 90)

            context = text[start:end]

            contextual = bool(
                self.PHONE_CONTEXT.search(context)
            )

            if contextual:
                phones.append({
                    "value": normalized,
                    "display": raw,
                    "context": context,
                    "contextual": True,
                })

        for match in self.EMAIL_PATTERN.finditer(text):

            raw = match.group(0)
            normalized = normalize_email(raw)

            if normalized.endswith((
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".webp",
            )):
                continue

            if any(term in normalized for term in (
                "example.com",
                "example.org",
                "yourdomain",
                "noreply@",
                "no-reply@",
            )):
                continue

            start = max(0, match.start() - 90)
            end = min(len(text), match.end() + 90)

            context = text[start:end]

            emails.append({
                "value": normalized,
                "display": raw,
                "context": context,
                "contextual": bool(
                    self.EMAIL_CONTEXT.search(context)
                ),
            })

        return {
            "phones": unique_candidates(phones),
            "emails": unique_candidates(emails),
        }


# =========================================================
# LINK VALIDATION BOT
# =========================================================

class LinkBot:
    """
    Accepts only same-host HTTPS redirects.

    Cross-domain redirects are never automatically adopted.
    """

    def extract(self, source: dict) -> Optional[dict]:

        original_url = source.get("url", "")
        resolved_url = source.get("resolved_url", "")

        if not original_url or not resolved_url:
            return None

        if not valid_https_url(original_url):
            return None

        if not valid_https_url(resolved_url):
            return None

        if not same_official_host(
            resolved_url,
            original_url,
        ):
            return None

        if original_url.rstrip("/") == resolved_url.rstrip("/"):
            return None

        return {
            "field": "website",
            "value": resolved_url,
            "source_id": source.get("source_id"),
            "source_authority": True,
            "contextual": True,
            "reason": "Same-host HTTPS redirect.",
        }


# =========================================================
# SERVICE CLASSIFICATION BOT
# =========================================================

class ServiceBot:

    SERVICE_TERMS = {
        "domestic_violence": [
            "domestic violence",
            "intimate partner violence",
            "abuse by a partner",
        ],
        "sexual_assault": [
            "sexual assault",
            "rape crisis",
            "sexual violence",
        ],
        "shelter": [
            "emergency shelter",
            "safe shelter",
            "transitional housing",
        ],
        "legal_assistance": [
            "legal assistance",
            "legal advocacy",
            "protective order",
            "legal services",
        ],
        "counseling": [
            "counseling",
            "therapy",
            "support group",
            "crisis counseling",
        ],
        "children_and_family": [
            "children's services",
            "child advocacy",
            "family support",
        ],
        "human_trafficking": [
            "human trafficking",
            "trafficking survivor",
        ],
        "financial_assistance": [
            "financial assistance",
            "economic empowerment",
            "financial advocacy",
        ],
        "housing": [
            "housing assistance",
            "housing advocacy",
            "rental assistance",
        ],
    }

    def extract(self, text: str) -> list[str]:

        lowered = normalize_text(text).lower()

        services = []

        for category, terms in self.SERVICE_TERMS.items():

            if any(term in lowered for term in terms):
                services.append(category)

        return sorted(set(services))


# =========================================================
# FORMAT VALIDATION BOT
# =========================================================

class FormatBot:

    VALID_SERVICES = set(
        ServiceBot.SERVICE_TERMS.keys()
    )

    def validate(self, field: str, value: Any) -> bool:

        if field == "phone":
            return bool(normalize_phone(str(value)))

        if field == "email":
            return bool(
                re.fullmatch(
                    r"[^@\s]+@[^@\s]+\.[^@\s]+",
                    str(value),
                )
            )

        if field in ("url", "website", "local_resource_url"):
            return valid_https_url(str(value))

        if field == "services":
            return (
                isinstance(value, list)
                and bool(value)
                and all(
                    isinstance(item, str)
                    and item in self.VALID_SERVICES
                    for item in value
                )
            )

        return False


# =========================================================
# CORROBORATION BOT
# =========================================================

class CorroborationBot:
    """
    Counts agreement across independent source hosts.

    Multiple pages on the same host count as one source.
    The originating source is excluded.
    """

    def __init__(self, sources: list[dict]):
        self.sources = sources
        self.service_bot = ServiceBot()

    def count_matches(
        self,
        state: str,
        field: str,
        value: Any,
        exclude_source: Optional[str] = None,
        exclude_url: Optional[str] = None,
    ) -> int:

        matching_hosts = set()

        for source in self.sources:

            if source.get("state") != state:
                continue

            source_id = source.get("source_id")

            if (
                exclude_source is not None
                and str(source_id) == str(exclude_source)
            ):
                continue

            source_url = source.get("url", "")

            if (
                exclude_url
                and source_url
                and normalize_host(source_url)
                == normalize_host(exclude_url)
            ):
                continue

            host = normalize_host(source_url)

            if not host:
                continue

            text = normalize_text(
                source.get("source_text", "")
            ).lower()

            matched = False

            if field == "phone":

                candidate = normalize_phone(str(value))

                matched = bool(
                    candidate
                    and candidate in normalize_phone_text(text)
                )

            elif field == "email":

                matched = (
                    normalize_email(str(value)) in text
                )

            elif field == "services":

                detected = set(
                    self.service_bot.extract(text)
                )

                matched = set(value).issubset(detected)

            if matched:
                matching_hosts.add(host)

        return len(matching_hosts)


def normalize_phone_text(text: str) -> str:
    return re.sub(r"\D", "", text or "")


# =========================================================
# CONSISTENCY BOT
# =========================================================

class ConsistencyBot:

    def evaluate(
        self,
        current_record: dict,
        field: str,
        candidate: Any,
        corroborated: bool,
    ) -> dict:

        existing = current_record.get(field)

        if existing in (None, "", []):

            return {
                "passed": True,
                "reason": "Directory field is currently empty.",
            }

        if field == "phone":

            same = (
                normalize_phone(str(existing))
                == normalize_phone(str(candidate))
            )

        elif field == "email":

            same = (
                normalize_email(str(existing))
                == normalize_email(str(candidate))
            )

        elif field == "website":

            same = (
                str(existing).rstrip("/")
                == str(candidate).rstrip("/")
            )

        elif field == "services":

            same = set(existing or []) == set(candidate or [])

        else:
            same = existing == candidate

        if same:

            return {
                "passed": True,
                "reason": "Candidate agrees with existing directory.",
            }

        if corroborated:

            return {
                "passed": True,
                "reason": "Changed value independently corroborated.",
            }

        return {
            "passed": False,
            "reason": (
                "Candidate conflicts with the current directory "
                "and lacks independent corroboration."
            ),
        }


# =========================================================
# DECISION BOT
# =========================================================

class DecisionBot:
    """
    Deterministic engineering score, not a statistical probability.
    """

    WEIGHTS = {
        "source_authority": 0.25,
        "format": 0.20,
        "context": 0.20,
        "corroboration": 0.20,
        "consistency": 0.15,
    }

    def score(
        self,
        source_authority: bool,
        format_valid: bool,
        contextual: bool,
        corroborated: bool,
        consistent: bool,
    ) -> dict:

        checks = {
            "source_authority": source_authority,
            "format": format_valid,
            "context": contextual,
            "corroboration": corroborated,
            "consistency": consistent,
        }

        score = sum(
            self.WEIGHTS[name] * float(passed)
            for name, passed in checks.items()
        )

        automatic_update = (
            score >= AUTO_APPLY_THRESHOLD
            and all(checks.values())
        )

        return {
            "confidence": round(score, 3),
            "checks": checks,
            "automatic_update": automatic_update,
        }


# =========================================================
# SOURCE AUTHORITY AND CANDIDATE COLLECTION
# =========================================================

def is_state_source(
    source: dict,
    directory: dict,
) -> bool:

    category = normalize_text(
        str(source.get("category", ""))
    ).lower()

    accepted_categories = {
        "state coalition",
        "state_coalition",
        "state coalition resource",
    }

    if category not in accepted_categories:
        return False

    state = resolve_state(
        source.get("state"),
        directory,
    )

    if not state:
        return False

    record = directory.get(state, {})

    official_website = record.get("website", "")

    source_url = source.get("url", "")

    if not official_website or not source_url:
        return False

    # The crawler source must belong to the official domain
    # already recorded in the directory.
    return same_official_host(
        source_url,
        official_website,
    )


def collect_candidates(
    sources: list[dict],
    directory: dict,
) -> list[dict]:

    contact_bot = ContactBot()
    link_bot = LinkBot()
    service_bot = ServiceBot()

    candidates = []

    for source in sources:

        if not is_state_source(source, directory):
            continue

        state = resolve_state(
            source.get("state"),
            directory,
        )

        text = source.get("source_text", "")

        if not state or not text:
            continue

        contacts = contact_bot.extract(text)

        for phone in contacts["phones"]:

            candidates.append({
                "state": state,
                "field": "phone",
                "value": phone["value"],
                "display": phone["display"],
                "context": phone["context"],
                "contextual": phone["contextual"],
                "source_id": source.get("source_id"),
                "source_name": source.get("name"),
                "source_url": source.get("url"),
                "source_authority": True,
            })

        for email in contacts["emails"]:

            candidates.append({
                "state": state,
                "field": "email",
                "value": email["value"],
                "display": email["display"],
                "context": email["context"],
                "contextual": email["contextual"],
                "source_id": source.get("source_id"),
                "source_name": source.get("name"),
                "source_url": source.get("url"),
                "source_authority": True,
            })

        link = link_bot.extract(source)

        if link:

            candidates.append({
                "state": state,
                **link,
                "display": link["value"],
                "context": link["reason"],
                "source_name": source.get("name"),
                "source_url": source.get("url"),
            })

        services = service_bot.extract(text)

        if services:

            candidates.append({
                "state": state,
                "field": "services",
                "value": services,
                "display": ", ".join(services),
                "context": (
                    "Service terminology found on official "
                    "state coalition page."
                ),
                "contextual": True,
                "source_id": source.get("source_id"),
                "source_name": source.get("name"),
                "source_url": source.get("url"),
                "source_authority": True,
            })

    return candidates


# =========================================================
# AUTOMATED VALIDATION PIPELINE
# =========================================================

def validate_candidates(
    candidates: list[dict],
    sources: list[dict],
    directory: dict,
) -> dict:

    format_bot = FormatBot()
    corroboration_bot = CorroborationBot(sources)
    consistency_bot = ConsistencyBot()
    decision_bot = DecisionBot()

    accepted = []
    exceptions = []

    for candidate in candidates:

        state = candidate["state"]
        field = candidate["field"]
        value = candidate["value"]

        current_record = directory.get(state, {})

        if not isinstance(current_record, dict):

            exceptions.append({
                **candidate,
                "exception_reason": (
                    "Invalid state directory record."
                ),
            })

            continue

        format_valid = format_bot.validate(
            field,
            value,
        )

        corroboration_count = corroboration_bot.count_matches(
            state=state,
            field=field,
            value=value,
            exclude_source=candidate.get("source_id"),
            exclude_url=candidate.get("source_url"),
        )

        # A same-host HTTPS redirect from the already verified
        # official state coalition domain is sufficient for a
        # website-path correction.
        if field == "website":
            corroborated = bool(
                candidate.get("source_authority")
                and candidate.get("contextual")
            )
        else:
            corroborated = (
                corroboration_count >= CORROBORATION_THRESHOLD
            )

        consistency = consistency_bot.evaluate(
            current_record=current_record,
            field=field,
            candidate=value,
            corroborated=corroborated,
        )

        score = decision_bot.score(
            source_authority=bool(
                candidate.get("source_authority")
            ),
            format_valid=format_valid,
            contextual=bool(candidate.get("contextual")),
            corroborated=corroborated,
            consistent=consistency["passed"],
        )

        result = {
            **candidate,
            "corroborating_sources": corroboration_count,
            "confidence": score["confidence"],
            "checks": score["checks"],
            "consistency_reason": consistency["reason"],
            "automatic_update": score["automatic_update"],
            "evaluated_at": utc_now(),
        }

        if score["automatic_update"]:

            accepted.append(result)

        else:

            result["exception_reason"] = (
                consistency["reason"]
                if not consistency["passed"]
                else (
                    "Confidence or validation threshold "
                    "not met."
                )
            )

            exceptions.append(result)

    return {
        "accepted": accepted,
        "exceptions": exceptions,
    }


# =========================================================
# AUTOMATED DIRECTORY ENGINE
# =========================================================

class DirectoryUpdateEngine:

    def __init__(
        self,
        storage_dir: Path = DATA_DIR,
    ):

        self.storage_dir = Path(storage_dir)

        initialize_storage(self.storage_dir)

        self.source_bot = SourceBot(self.storage_dir)

    def load_existing_directory(
        self,
        supplied_directory: Optional[dict] = None,
    ) -> dict:

        if supplied_directory is not None:
            return copy.deepcopy(supplied_directory)

        directory_path = resolve_directory_path(
            self.storage_dir
        )

        return read_json(directory_path, {})

    def apply_candidates(
        self,
        directory: dict,
        accepted: list[dict],
    ) -> tuple[dict, list[dict], list[dict]]:

        updated = copy.deepcopy(directory)

        changes = []
        conflicts = []

        grouped = defaultdict(list)

        for candidate in accepted:

            grouped[
                (
                    candidate["state"],
                    candidate["field"],
                )
            ].append(candidate)

        for (state, field), items in grouped.items():

            if state not in updated:
                continue

            if not isinstance(updated[state], dict):
                continue

            values = {
                json.dumps(
                    item["value"],
                    sort_keys=True,
                    ensure_ascii=False,
                )
                for item in items
            }

            if len(values) != 1:

                for item in items:

                    conflicts.append({
                        **item,
                        "exception_reason": (
                            "Conflicting automated candidates "
                            "for the same state and field."
                        ),
                    })

                continue

            candidate = max(
                items,
                key=lambda item: item["confidence"],
            )

            new_value = candidate["value"]

            old_value = updated[state].get(field)

            if field == "services":

                old_services = updated[state].get(
                    "services",
                    [],
                )

                if isinstance(old_services, str):
                    old_services = [old_services]

                new_value = sorted(
                    set(old_services or [])
                    | set(new_value)
                )

            if old_value == new_value:
                continue

            updated[state][field] = new_value

            changes.append({
                "state": state,
                "field": field,
                "old_value": old_value,
                "new_value": new_value,
                "source": candidate.get("source_name"),
                "source_url": candidate.get("source_url"),
                "confidence": candidate["confidence"],
                "updated_at": utc_now(),
            })

        return updated, changes, conflicts

    def save_new_version(
        self,
        old_directory: dict,
        new_directory: dict,
        changes: list[dict],
    ) -> dict:

        directory_path = resolve_directory_path(
            self.storage_dir
        )

        history_path = (
            self.storage_dir / HISTORY_FILE.name
        )

        history = read_json(history_path, [])

        if not isinstance(history, list):
            history = []

        valid_versions = [
            item.get("version", 0)
            for item in history
            if isinstance(item, dict)
            and isinstance(item.get("version"), int)
        ]

        next_version = (
            max(valid_versions, default=0) + 1
        )

        history_entry = {
            "version": next_version,
            "created_at": utc_now(),
            "previous_hash": stable_hash(old_directory),
            "new_hash": stable_hash(new_directory),
            "changes": changes,
            "directory": new_directory,
        }

        updated_history = (
            history + [history_entry]
        )[-MAX_HISTORY:]

        # Save history first. If directory writing fails,
        # restore the previous history file.
        if not write_json(history_path, updated_history):

            return {
                "success": False,
                "message": "Could not save directory history.",
            }

        if not write_json(directory_path, new_directory):

            write_json(history_path, history)

            return {
                "success": False,
                "message": (
                    "Could not save updated directory. "
                    "Previous history was restored."
                ),
            }

        return {
            "success": True,
            "version": next_version,
            "directory_path": str(directory_path),
        }

    def save_exceptions(
        self,
        exceptions: list[dict],
    ) -> bool:

        path = (
            self.storage_dir / EXCEPTION_FILE.name
        )

        existing = read_json(path, [])

        if not isinstance(existing, list):
            existing = []

        existing_ids = {
            item.get("candidate_id")
            for item in existing
            if isinstance(item, dict)
        }

        for item in exceptions:

            candidate_id = stable_hash({
                "state": item.get("state"),
                "field": item.get("field"),
                "value": item.get("value"),
                "source": item.get("source_id"),
                "reason": item.get("exception_reason"),
            })[:24]

            item = {
                **item,
                "candidate_id": candidate_id,
                "recorded_at": utc_now(),
            }

            if candidate_id not in existing_ids:

                existing.append(item)
                existing_ids.add(candidate_id)

        return write_json(
            path,
            existing[-MAX_EXCEPTIONS:],
        )

    def run(
        self,
        current_directory: Optional[dict] = None,
        auto_apply: bool = True,
    ) -> dict:

        directory = self.load_existing_directory(
            current_directory
        )

        if (
            not isinstance(directory, dict)
            or len(directory) != 50
        ):

            return {
                "success": False,
                "message": (
                    "A valid 50-state resource directory "
                    "is required. Check the repository-root "
                    "state_resource_directory.json file."
                ),
            }

        sources = self.source_bot.load_sources()

        candidates = collect_candidates(
            sources,
            directory,
        )

        validation = validate_candidates(
            candidates=candidates,
            sources=sources,
            directory=directory,
        )

        updated_directory, changes, conflicts = (
            self.apply_candidates(
                directory=directory,
                accepted=validation["accepted"],
            )
        )

        validation["exceptions"].extend(conflicts)

        # Identify accepted candidates that did not produce a
        # change because the grouped update was unresolved.
        applied_keys = {
            (change["state"], change["field"])
            for change in changes
        }

        conflict_keys = {
            (
                item.get("state"),
                item.get("field"),
            )
            for item in conflicts
        }

        for candidate in validation["accepted"]:

            key = (
                candidate["state"],
                candidate["field"],
            )

            if key in applied_keys or key in conflict_keys:
                continue

            current_value = directory.get(
                candidate["state"],
                {},
            ).get(candidate["field"])

            if candidate["field"] == "services":

                existing = current_value or []

                if isinstance(existing, str):
                    existing = [existing]

                if set(existing).issuperset(
                    candidate["value"]
                ):
                    continue

            elif current_value == candidate["value"]:
                continue

            validation["exceptions"].append({
                **candidate,
                "exception_reason": (
                    "Candidate was not applied because "
                    "the update could not be resolved."
                ),
            })

        report = {
            "run_at": utc_now(),
            "sources_loaded": len(sources),
            "candidates_found": len(candidates),
            "automatically_validated": len(
                validation["accepted"]
            ),
            "updates_applied": len(changes),
            "exceptions_created": len(
                validation["exceptions"]
            ),
            "auto_apply_enabled": auto_apply,
            "changes": changes,
        }

        version_result = None

        if auto_apply and changes:

            version_result = self.save_new_version(
                old_directory=directory,
                new_directory=updated_directory,
                changes=changes,
            )

            if not version_result["success"]:

                return {
                    "success": False,
                    "message": version_result["message"],
                    "report": report,
                }

            report["directory_version"] = (
                version_result["version"]
            )

        if not self.save_exceptions(
            validation["exceptions"]
        ):

            logger.error("Could not save directory exceptions.")

        report_path = (
            self.storage_dir / REPORT_FILE.name
        )

        if not write_json(report_path, report):

            logger.error("Could not save directory bot report.")

        record_activity(
            event="directory_maintenance_completed",
            details={
                "sources_loaded": len(sources),
                "candidates_found": len(candidates),
                "updates_applied": (
                    len(changes) if auto_apply else 0
                ),
                "exceptions_created": len(
                    validation["exceptions"]
                ),
                "auto_apply_enabled": auto_apply,
            },
            storage_dir=self.storage_dir,
        )

        return {
            "success": True,
            "message": (
                "Automated directory maintenance completed."
                if auto_apply
                else (
                    "Directory analysis completed without "
                    "applying changes."
                )
            ),
            "report": report,
            "updated_directory": (
                updated_directory if auto_apply else directory
            ),
            "changes": changes if auto_apply else [],
            "proposed_changes": changes,
            "exceptions": validation["exceptions"],
        }


# =========================================================
# PUBLIC FUNCTIONS — STREAMLIT INTEGRATION
# =========================================================

def run_automated_updates(
    current_directory: Optional[dict] = None,
    storage_dir: str = str(DATA_DIR),
    auto_apply: bool = True,
) -> dict:

    engine = DirectoryUpdateEngine(
        Path(storage_dir)
    )

    return engine.run(
        current_directory=current_directory,
        auto_apply=auto_apply,
    )


def get_directory_update_status(
    storage_dir: str = str(DATA_DIR),
) -> dict:

    directory = Path(storage_dir)

    report = read_json(
        directory / REPORT_FILE.name,
        {},
    )

    exceptions = read_json(
        directory / EXCEPTION_FILE.name,
        [],
    )

    history = read_json(
        directory / HISTORY_FILE.name,
        [],
    )

    return {
        "last_run": report.get("run_at"),
        "sources_loaded": report.get("sources_loaded", 0),
        "candidates_found": report.get("candidates_found", 0),
        "updates_applied": report.get("updates_applied", 0),
        "exception_count": len(exceptions),
        "directory_versions": len(history),
        "directory_file": str(
            resolve_directory_path(directory)
        ),
    }


def get_directory_exceptions(
    storage_dir: str = str(DATA_DIR),
) -> list:

    return read_json(
        Path(storage_dir) / EXCEPTION_FILE.name,
        [],
    )


def get_directory_history(
    storage_dir: str = str(DATA_DIR),
) -> list:

    return read_json(
        Path(storage_dir) / HISTORY_FILE.name,
        [],
    )


def export_current_directory(
    storage_dir: str = str(DATA_DIR),
) -> dict:

    path = resolve_directory_path(
        Path(storage_dir)
    )

    return read_json(path, {})


def rollback_directory(
    version: int,
    storage_dir: str = str(DATA_DIR),
) -> dict:
    """
    Restore a previously saved directory version.

    Version numbers are monotonically increasing.
    """

    storage_dir = Path(storage_dir)

    initialize_storage(storage_dir)

    history = read_json(
        storage_dir / HISTORY_FILE.name,
        [],
    )

    selected = next(
        (
            item for item in history
            if isinstance(item, dict)
            and item.get("version") == version
        ),
        None,
    )

    if not selected:

        return {
            "success": False,
            "message": "Requested directory version not found.",
        }

    restored = selected.get("directory")

    if (
        not isinstance(restored, dict)
        or len(restored) != 50
    ):

        return {
            "success": False,
            "message": "Stored directory version is invalid.",
        }

    directory_path = resolve_directory_path(
        storage_dir
    )

    current = read_json(directory_path, {})

    if not write_json(directory_path, restored):

        return {
            "success": False,
            "message": "Could not restore directory version.",
        }

    record_activity(
        event="directory_rollback",
        details={
            "restored_version": version,
            "previous_hash": stable_hash(current),
            "restored_hash": stable_hash(restored),
        },
        storage_dir=storage_dir,
    )

    return {
        "success": True,
        "message": f"Directory restored to version {version}.",
        "directory": restored,
    }


# =========================================================
# OFFLINE SELF-TEST
# =========================================================

def self_test() -> dict:

    tests = {}

    try:

        contact_bot = ContactBot()

        sample = (
            "For assistance, call our office at "
            "(304) 555-0182. Contact us at help@example.org."
        )

        extracted = contact_bot.extract(sample)

        tests["phone_extraction"] = any(
            item["value"] == "3045550182"
            for item in extracted["phones"]
        )

        tests["email_extraction"] = any(
            item["value"] == "help@example.org"
            for item in extracted["emails"]
        )

        tests["https_validation"] = (
            valid_https_url("https://example.org")
            and not valid_https_url("http://example.org")
        )

        tests["phone_normalization"] = (
            normalize_phone("(304) 555-0182")
            == "3045550182"
        )

        service_bot = ServiceBot()

        services = service_bot.extract(
            "We provide domestic violence advocacy, "
            "emergency shelter and legal assistance."
        )

        tests["service_classification"] = (
            "domestic_violence" in services
            and "shelter" in services
            and "legal_assistance" in services
        )

        decision = DecisionBot().score(
            source_authority=True,
            format_valid=True,
            contextual=True,
            corroborated=True,
            consistent=True,
        )

        tests["decision_engine"] = (
            decision["automatic_update"]
            and decision["confidence"] == 1.0
        )

        source = {
            "source_id": "test",
            "state": "West Virginia",
            "category": "State Coalition",
            "name": "Test Coalition",
            "url": "https://example.org",
            "resolved_url": "https://example.org/resources",
            "source_text": sample,
        }

        link = LinkBot().extract(source)

        tests["same_host_redirect"] = (
            link is not None
            and link["field"] == "website"
            and link["value"].endswith("/resources")
        )

        bad_source = {
            **source,
            "resolved_url": "https://unrelated.example/resources",
        }

        tests["external_redirect_rejected"] = (
            LinkBot().extract(bad_source) is None
        )

        test_directory = {
            "West Virginia": {
                "code": "WV",
                "name": "Test Coalition",
                "website": "https://example.org",
            }
        }

        tests["state_code_resolution"] = (
            resolve_state("WV", test_directory)
            == "West Virginia"
        )

        tests["website_field_consistency"] = (
            ConsistencyBot().evaluate(
                current_record={
                    "website": "https://example.org"
                },
                field="website",
                candidate="https://example.org",
                corroborated=True,
            )["passed"]
        )

        # Service corroboration must compare service categories,
        # not the string representation of a Python list.
        corroboration_sources = [
            {
                "source_id": "source-a",
                "state": "West Virginia",
                "url": "https://one.example.org",
                "source_text": (
                    "We provide emergency shelter "
                    "and legal assistance."
                ),
            },
            {
                "source_id": "source-b",
                "state": "West Virginia",
                "url": "https://two.example.org",
                "source_text": (
                    "We provide emergency shelter "
                    "and legal assistance."
                ),
            },
        ]

        corroboration = CorroborationBot(
            corroboration_sources
        )

        tests["service_corroboration"] = (
            corroboration.count_matches(
                state="West Virginia",
                field="services",
                value=["legal_assistance", "shelter"],
                exclude_source="source-a",
                exclude_url="https://one.example.org",
            ) == 1
        )

        tests["independent_host_counting"] = (
            corroboration.count_matches(
                state="West Virginia",
                field="services",
                value=["legal_assistance", "shelter"],
                exclude_source="source-a",
                exclude_url="https://one.example.org",
            ) == 1
        )

    except Exception as error:

        logger.exception("Self-test failed")
        tests["unexpected_error"] = str(error)

    return {
        "passed": all(
            value is True
            for value in tests.values()
        ),
        "tests": tests,
    }


if __name__ == "__main__":

    print(json.dumps(
        self_test(),
        indent=4,
    ))
