
"""
Survivors Network — Automated Directory Intelligence
=====================================================

Consumes resource_crawler.py data and automatically maintains
the state resource directory.

Independent validation bots:
1. SourceBot          — source identity and authority
2. ContactBot         — phone and email extraction
3. LinkBot            — official website and link validation
4. ServiceBot         — service-category extraction
5. FormatBot          — data and contact-format validation
6. CorroborationBot   — agreement across independent sources
7. ConsistencyBot     — comparison with existing directory records
8. DecisionBot        — confidence scoring and update decisions

High-confidence changes are automatically applied to a versioned
directory copy. Uncertain or conflicting changes are held in an
automated exception queue.

Survivor records and private data are never accessed by this module.
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

DATA_DIR = Path("resource_crawler_data")

SNAPSHOT_FILE = DATA_DIR / "snapshots.json"
REVIEW_FILE = DATA_DIR / "pending_reviews.json"

DIRECTORY_FILE = DATA_DIR / "state_resource_directory.json"
HISTORY_FILE = DATA_DIR / "directory_history.json"
EXCEPTION_FILE = DATA_DIR / "directory_exceptions.json"
REPORT_FILE = DATA_DIR / "directory_bot_report.json"

AUTO_APPLY_THRESHOLD = 0.82
CORROBORATION_THRESHOLD = 0.75

MAX_HISTORY = 100
MAX_EXCEPTIONS = 2000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("survivors_network_directory")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read %s", path)
        return default


def write_json(path: Path, data: Any) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")

    try:
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                indent=2,
                ensure_ascii=False,
            )

        temporary.replace(path)
        return True

    except OSError:
        logger.exception("Could not write %s", path)
        temporary.unlink(missing_ok=True)
        return False


# =========================================================
# SOURCE DATA INGESTION
# =========================================================

class SourceBot:
    """
    Reads existing crawler snapshots and review records.

    Supports:
    - extracted_text
    - text
    - excerpt
    - new_excerpt

    The current resource_crawler.py stores excerpts. A later crawler
    enhancement can provide extracted_text for more complete coverage.
    """

    def __init__(self, storage_dir: Path = DATA_DIR):
        self.storage_dir = Path(storage_dir)

    def load_sources(self) -> list[dict]:
        snapshots = read_json(
            self.storage_dir / "snapshots.json",
            {},
        )

        reviews = read_json(
            self.storage_dir / "pending_reviews.json",
            [],
        )

        sources = []

        if isinstance(snapshots, dict):
            for source_id, snapshot in snapshots.items():
                if not isinstance(snapshot, dict):
                    continue

                text = (
                    snapshot.get("extracted_text")
                    or snapshot.get("text")
                    or snapshot.get("excerpt")
                    or ""
                )

                if not text:
                    continue

                sources.append({
                    **snapshot,
                    "source_id": snapshot.get(
                        "source_id",
                        source_id,
                    ),
                    "source_text": text,
                    "source_origin": "snapshot",
                })

        # Use a review excerpt only when there is no snapshot for
        # the same source. This avoids double-counting the same page.
        known_ids = {
            source.get("source_id")
            for source in sources
        }

        for review in reviews:
            if not isinstance(review, dict):
                continue

            source_id = review.get("source_id")

            if source_id in known_ids:
                continue

            text = (
                review.get("extracted_text")
                or review.get("new_excerpt")
                or ""
            )

            if not text:
                continue

            sources.append({
                **review,
                "source_text": text,
                "source_origin": "review",
            })

            known_ids.add(source_id)

        return sources


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) != 10:
        return ""

    return digits


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def valid_https_url(value: str) -> bool:
    try:
        parsed = urlparse(value)

        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )
    except ValueError:
        return False


# =========================================================
# CONTACT EXTRACTION BOT
# =========================================================

class ContactBot:
    """
    Extracts public contact information from official resource pages.

    Context is required for telephone numbers to reduce false matches.
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


def unique_candidates(items: list[dict]) -> list[dict]:
    result = {}
    for item in items:
        result[item["value"]] = item
    return list(result.values())


# =========================================================
# LINK VALIDATION BOT
# =========================================================

class LinkBot:

    def extract(self, source: dict) -> Optional[dict]:
        original_url = source.get("url", "")
        resolved_url = source.get("resolved_url", "")

        if not original_url or not resolved_url:
            return None

        if not valid_https_url(original_url):
            return None

        if not valid_https_url(resolved_url):
            return None

        original_host = (
            urlparse(original_url).hostname or ""
        ).lower()

        resolved_host = (
            urlparse(resolved_url).hostname or ""
        ).lower()

        # A crawler redirect to another domain is not accepted
        # as an automatic official-domain replacement.
        if original_host != resolved_host:
            return None

        if original_url.rstrip("/") == resolved_url.rstrip("/"):
            return None

        return {
            "field": "url",
            "value": resolved_url,
            "source_id": source.get("source_id"),
            "authority": True,
            "reason": "Same-host HTTPS redirect verified by crawler.",
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

        if field in ("url", "local_resource_url"):
            return valid_https_url(str(value))

        if field == "services":
            return (
                isinstance(value, list)
                and all(isinstance(item, str) for item in value)
            )

        return False


# =========================================================
# CORROBORATION BOT
# =========================================================

class CorroborationBot:
    """
    Checks whether independent sources report the same value.

    Sources are counted by unique source_id, not by repeated
    mentions on the same page.
    """

    def __init__(self, sources: list[dict]):
        self.sources = sources

    def count_matches(
        self,
        state: str,
        field: str,
        value: Any,
        exclude_source: Optional[str] = None,
    ) -> int:

        matching_sources = set()

        for source in self.sources:

            if source.get("state") != state:
                continue

            if source.get("source_id") == exclude_source:
                continue

            text = normalize_text(
                source.get("source_text", "")
            ).lower()

            if field == "phone":
                candidate = normalize_phone(str(value))

                if candidate and candidate in normalize_phone_text(text):
                    matching_sources.add(source.get("source_id"))

            elif field == "email":
                if normalize_email(str(value)) in text:
                    matching_sources.add(source.get("source_id"))

            elif field == "services":
                if str(value).lower() in text:
                    matching_sources.add(source.get("source_id"))

        return len(matching_sources)


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
    Independent checks are combined into a confidence score.

    The score is a deterministic engineering rule, not a statistical
    probability that the information is correct.
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

        return {
            "confidence": round(score, 3),
            "checks": checks,
            "automatic_update": (
                score >= AUTO_APPLY_THRESHOLD
                and source_authority
                and format_valid
                and contextual
                and consistent
            ),
        }


# =========================================================
# CANDIDATE COLLECTION
# =========================================================

def is_state_source(source: dict) -> bool:
    return bool(
        source.get("state")
        and source.get("category") == "State Coalition"
    )


def collect_candidates(sources: list[dict]) -> list[dict]:

    contact_bot = ContactBot()
    link_bot = LinkBot()
    service_bot = ServiceBot()

    candidates = []

    for source in sources:

        if not is_state_source(source):
            continue

        state = source.get("state")
        text = source.get("source_text", "")

        if not text:
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
                "contextual": True,
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
                "context": "Service terminology found on state coalition page.",
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
                "reason": "Invalid state directory record.",
            })
            continue

        format_valid = format_bot.validate(field, value)

        corroboration_count = corroboration_bot.count_matches(
            state=state,
            field=field,
            value=value,
            exclude_source=candidate.get("source_id"),
        )

        corroborated = (
            corroboration_count >= 1
            or field == "url"
        )

        consistency = consistency_bot.evaluate(
            current_record=current_record,
            field=field,
            candidate=value,
            corroborated=corroborated,
        )

        score = decision_bot.score(
            source_authority=bool(
                candidate.get("source_authority", True)
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
                else "Confidence or validation threshold not met."
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

    def __init__(self, storage_dir: Path = DATA_DIR):
        self.storage_dir = Path(storage_dir)
        self.source_bot = SourceBot(self.storage_dir)

    def load_existing_directory(
        self,
        supplied_directory: Optional[dict] = None,
    ) -> dict:

        if supplied_directory is not None:
            return copy.deepcopy(supplied_directory)

        return read_json(
            self.storage_dir / DIRECTORY_FILE.name,
            {},
        )

    def apply_candidates(
        self,
        directory: dict,
        accepted: list[dict],
    ) -> tuple[dict, list[dict]]:

        updated = copy.deepcopy(directory)
        changes = []

        # Group candidates by state and field.
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

            # Require agreement among all automatic candidates for
            # the same field. A disagreement becomes an exception.
            values = {
                json.dumps(
                    item["value"],
                    sort_keys=True,
                )
                for item in items
            }

            if len(values) != 1:
                for item in items:
                    item["exception_reason"] = (
                        "Conflicting automated candidates."
                    )
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

        return updated, changes

    def run(
        self,
        current_directory: Optional[dict] = None,
        auto_apply: bool = True,
    ) -> dict:

        directory = self.load_existing_directory(
            current_directory
        )

        if not directory:
            return {
                "success": False,
                "message": (
                    "No state directory supplied or saved. "
                    "Pass STATE_COALITIONS from survivors-network.py."
                ),
            }

        sources = self.source_bot.load_sources()

        candidates = collect_candidates(sources)

        validation = validate_candidates(
            candidates=candidates,
            sources=sources,
            directory=directory,
        )

        updated_directory, changes = self.apply_candidates(
            directory=directory,
            accepted=validation["accepted"],
        )

        # Any accepted candidate not actually applied due to a
        # conflict in the grouped results becomes an exception.
        applied_keys = {
            (change["state"], change["field"])
            for change in changes
        }

        for candidate in validation["accepted"]:
            key = (
                candidate["state"],
                candidate["field"],
            )

            if key not in applied_keys:
                if candidate.get("field") == "services":
                    existing = directory.get(
                        candidate["state"], {}
                    ).get("services", [])

                    if isinstance(existing, str):
                        existing = [existing]

                    if set(existing or []).issuperset(
                        candidate["value"]
                    ):
                        continue

                if directory.get(
                    candidate["state"], {}
                ).get(candidate["field"]) == candidate["value"]:
                    continue

                validation["exceptions"].append({
                    **candidate,
                    "exception_reason": (
                        "Candidate was not applied because "
                        "the update group could not be resolved."
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

        if auto_apply and changes:

            directory_path = (
                self.storage_dir / DIRECTORY_FILE.name
            )

            history_path = (
                self.storage_dir / HISTORY_FILE.name
            )

            history = read_json(history_path, [])

            history.append({
                "version": len(history) + 1,
                "created_at": utc_now(),
                "previous_hash": stable_hash(directory),
                "new_hash": stable_hash(updated_directory),
                "changes": changes,
                "directory": updated_directory,
            })

            history = history[-MAX_HISTORY:]

            if not write_json(history_path, history):
                return {
                    "success": False,
                    "message": (
                        "Could not save directory history. "
                        "No new directory version was written."
                    ),
                    "report": report,
                }

            if not write_json(directory_path, updated_directory):
                return {
                    "success": False,
                    "message": "Could not save updated directory.",
                    "report": report,
                }

        # Store unresolved exceptions separately.
        exception_path = (
            self.storage_dir / EXCEPTION_FILE.name
        )

        existing_exceptions = read_json(
            exception_path,
            [],
        )

        existing_ids = {
            item.get("candidate_id")
            for item in existing_exceptions
        }

        for item in validation["exceptions"]:

            item["candidate_id"] = stable_hash({
                "state": item.get("state"),
                "field": item.get("field"),
                "value": item.get("value"),
                "source": item.get("source_id"),
            })[:20]

            if item["candidate_id"] not in existing_ids:
                existing_exceptions.append(item)

        write_json(
            exception_path,
            existing_exceptions[-MAX_EXCEPTIONS:],
        )

        write_json(REPORT_FILE, report)

        return {
            "success": True,
            "message": (
                "Automated directory maintenance completed."
                if auto_apply
                else "Directory analysis completed without applying changes."
            ),
            "report": report,
            "updated_directory": updated_directory,
            "changes": changes,
            "exceptions": validation["exceptions"],
        }


# =========================================================
# PUBLIC FUNCTIONS — STREAMLIT INTEGRATION
# =========================================================

def run_automated_updates(
    current_directory: Optional[dict] = None,
    storage_dir: str = "resource_crawler_data",
    auto_apply: bool = True,
) -> dict:

    engine = DirectoryUpdateEngine(Path(storage_dir))

    return engine.run(
        current_directory=current_directory,
        auto_apply=auto_apply,
    )


def get_directory_update_status(
    storage_dir: str = "resource_crawler_data",
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
    }


def get_directory_exceptions(
    storage_dir: str = "resource_crawler_data",
) -> list:

    return read_json(
        Path(storage_dir) / EXCEPTION_FILE.name,
        [],
    )


def get_directory_history(
    storage_dir: str = "resource_crawler_data",
) -> list:

    return read_json(
        Path(storage_dir) / HISTORY_FILE.name,
        [],
    )


def export_current_directory(
    storage_dir: str = "resource_crawler_data",
) -> dict:

    return read_json(
        Path(storage_dir) / DIRECTORY_FILE.name,
        {},
    )


def rollback_directory(
    version: int,
    storage_dir: str = "resource_crawler_data",
) -> dict:
    """
    Restore a previously saved directory version.

    Version numbers start at 1.
    """

    directory = Path(storage_dir)
    history = read_json(
        directory / HISTORY_FILE.name,
        [],
    )

    selected = next(
        (
            item for item in history
            if item.get("version") == version
        ),
        None,
    )

    if not selected:
        return {
            "success": False,
            "message": "Requested directory version not found.",
        }

    restored = selected.get("directory")

    if not isinstance(restored, dict):
        return {
            "success": False,
            "message": "Stored directory version is invalid.",
        }

    if not write_json(
        directory / DIRECTORY_FILE.name,
        restored,
    ):
        return {
            "success": False,
            "message": "Could not restore directory version.",
        }

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
            "state": "WV",
            "category": "State Coalition",
            "name": "Test Coalition",
            "url": "https://example.org",
            "resolved_url": "https://example.org/resources",
            "source_text": sample,
        }

        link = LinkBot().extract(source)

        tests["same_host_redirect"] = (
            link is not None
            and link["value"].endswith("/resources")
        )

        bad_source = {
            **source,
            "resolved_url": "https://unrelated.example/resources",
        }

        tests["external_redirect_rejected"] = (
            LinkBot().extract(bad_source) is None
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
    print(json.dumps(self_test(), indent=2))
