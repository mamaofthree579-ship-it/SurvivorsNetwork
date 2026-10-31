
"""
Survivors Network — Public Resource Directory Crawler

Purpose:
- Check public state coalition and national resource websites.
- Respect robots.txt and apply request rate limits.
- Detect changes to public resource pages.
- Save snapshots and place detected changes in a human-review queue.
- Never automatically alter the Survivors Network resource directory.
- Never collect survivor records, private messages, or account credentials.

This module is designed to be imported by survivors-network.py.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time

from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

DATA_DIR = Path("resource_crawler_data")

SNAPSHOT_FILE = DATA_DIR / "snapshots.json"
REVIEW_FILE = DATA_DIR / "pending_reviews.json"
ACTIVITY_FILE = DATA_DIR / "activity_log.json"

REQUEST_TIMEOUT = 15
REQUEST_DELAY_SECONDS = 2
MAX_PAGE_BYTES = 2_000_000
MAX_REDIRECTS = 4

USER_AGENT = (
    "SurvivorsNetworkResourceCrawler/1.0 "
    "(public resource directory maintenance; "
    "contact the project maintainer through the project repository)"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml",
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("survivors_network_crawler")


# ---------------------------------------------------------
# JSON STORAGE
# ---------------------------------------------------------

class CrawlerStorage:
    """Local JSON storage with atomic file replacement."""

    def __init__(self, directory: Path = DATA_DIR):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self.snapshot_file = self.directory / "snapshots.json"
        self.review_file = self.directory / "pending_reviews.json"
        self.activity_file = self.directory / "activity_log.json"

    def read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default

        try:
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, OSError):
            logger.exception("Could not read %s", path)
            return default

    def write_json(self, path: Path, data: Any) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)

        temporary_path = path.with_suffix(path.suffix + ".tmp")

        try:
            with temporary_path.open("w", encoding="utf-8") as file:
                json.dump(data, file, indent=2, ensure_ascii=False)

            temporary_path.replace(path)
            return True

        except OSError:
            logger.exception("Could not write %s", path)

            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

            return False

    def get_snapshots(self) -> dict:
        return self.read_json(self.snapshot_file, {})

    def save_snapshots(self, snapshots: dict) -> bool:
        return self.write_json(self.snapshot_file, snapshots)

    def get_reviews(self) -> list:
        return self.read_json(self.review_file, [])

    def save_reviews(self, reviews: list) -> bool:
        return self.write_json(self.review_file, reviews)

    def get_activity(self) -> list:
        return self.read_json(self.activity_file, [])

    def log_activity(self, event: str, details: Optional[dict] = None):
        activity = self.get_activity()

        activity.append({
            "timestamp": utc_now(),
            "event": event,
            "details": details or {},
        })

        # Keep the local activity log bounded.
        self.write_json(self.activity_file, activity[-2000:])


# ---------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


def get_hostname(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def valid_public_url(url: str) -> bool:
    """Reject non-HTTP URLs and URLs without a hostname."""

    try:
        parsed = urlparse(url)

        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )

    except ValueError:
        return False


def fingerprint_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text or "").strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def make_source_id(url: str) -> str:
    return hashlib.sha256(
        normalize_url(url).encode("utf-8")
    ).hexdigest()[:16]


# ---------------------------------------------------------
# HTML TEXT EXTRACTION
# ---------------------------------------------------------

class PublicPageTextParser(HTMLParser):
    """Extract readable page text without executing page content."""

    IGNORED_TAGS = {
        "script",
        "style",
        "noscript",
        "svg",
        "iframe",
        "template",
        "form",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignore_depth = 0
        self.active_ignored_tags = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag in self.IGNORED_TAGS:
            self.ignore_depth += 1
            self.active_ignored_tags.append(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in self.IGNORED_TAGS and tag in self.active_ignored_tags:
            self.active_ignored_tags.remove(tag)
            self.ignore_depth = max(0, self.ignore_depth - 1)

    def handle_data(self, data):
        if self.ignore_depth == 0 and data.strip():
            self.parts.append(data.strip())

    def get_text(self) -> str:
        return re.sub(
            r"\s+",
            " ",
            " ".join(self.parts)
        ).strip()


def extract_page_text(html: str) -> str:
    parser = PublicPageTextParser()

    try:
        parser.feed(html)
        parser.close()
        return parser.get_text()
    except Exception:
        logger.exception("HTML extraction failed")
        return ""


# ---------------------------------------------------------
# ROBOTS.TXT
# ---------------------------------------------------------

def check_robots_permission(
    url: str,
    session: requests.Session,
) -> tuple[bool, str]:
    """
    Check robots.txt for the requested public page.

    A robots.txt retrieval error fails closed.
    """

    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    parser = RobotFileParser()
    parser.set_url(robots_url)

    try:
        response = session.get(
            robots_url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
        )

        if response.status_code in (404, 410):
            return True, "No robots.txt restriction found."

        if response.status_code != 200:
            return False, (
                f"Robots policy could not be verified "
                f"(HTTP {response.status_code})."
            )

        parser.parse(response.text.splitlines())

        allowed = parser.can_fetch(USER_AGENT, url)

        if not allowed:
            return False, "robots.txt disallows this page."

        return True, "robots.txt permits this page."

    except requests.RequestException as error:
        return False, f"Robots check failed: {error}"


# ---------------------------------------------------------
# SAFE REQUEST HANDLING
# ---------------------------------------------------------

def fetch_public_page(
    url: str,
    session: Optional[requests.Session] = None,
    allowed_hosts: Optional[set[str]] = None,
) -> dict:
    """
    Fetch a public page.

    Redirects are handled manually. The next destination is validated
    before another request is made. Redirects to unrelated hosts are
    rejected.
    """

    session = session or requests.Session()

    url = normalize_url(url)

    if not valid_public_url(url):
        return {
            "success": False,
            "error": "Invalid URL.",
        }

    original_host = get_hostname(url)

    if allowed_hosts is None:
        allowed_hosts = {original_host}

    allowed_hosts = {
        host.lower().strip()
        for host in allowed_hosts
        if host
    }

    if original_host not in allowed_hosts:
        return {
            "success": False,
            "error": "Initial host is not allowlisted.",
        }

    current_url = url

    for redirect_number in range(MAX_REDIRECTS + 1):

        if not valid_public_url(current_url):
            return {
                "success": False,
                "error": "Redirect produced an invalid URL.",
            }

        current_host = get_hostname(current_url)

        if current_host not in allowed_hosts:
            return {
                "success": False,
                "error": (
                    "Redirect blocked because its hostname "
                    "is not allowlisted."
                ),
            }

        try:
            response = session.get(
                current_url,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
                stream=True,
                allow_redirects=False,
            )

        except requests.RequestException as error:
            return {
                "success": False,
                "error": str(error),
            }

        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            response.close()

            if not location:
                return {
                    "success": False,
                    "error": "Redirect did not provide a destination.",
                }

            if redirect_number >= MAX_REDIRECTS:
                return {
                    "success": False,
                    "error": "Maximum redirects exceeded.",
                }

            next_url = urljoin(current_url, location)

            if not valid_public_url(next_url):
                return {
                    "success": False,
                    "error": "Redirect destination is invalid.",
                }

            if get_hostname(next_url) not in allowed_hosts:
                return {
                    "success": False,
                    "error": (
                        "Cross-host redirect blocked. "
                        "Add the destination host to the approved "
                        "source registry before following it."
                    ),
                }

            current_url = next_url
            continue

        if response.status_code != 200:
            status = response.status_code
            response.close()

            return {
                "success": False,
                "error": f"HTTP {status}",
            }

        content_type = response.headers.get("Content-Type", "").lower()

        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            response.close()

            return {
                "success": False,
                "error": "The resource is not an HTML page.",
            }

        content_length = response.headers.get("Content-Length")

        if content_length:
            try:
                if int(content_length) > MAX_PAGE_BYTES:
                    response.close()

                    return {
                        "success": False,
                        "error": "Page exceeds maximum allowed size.",
                    }
            except ValueError:
                pass

        chunks = []
        total_bytes = 0

        try:
            for chunk in response.iter_content(chunk_size=16384):
                if not chunk:
                    continue

                total_bytes += len(chunk)

                if total_bytes > MAX_PAGE_BYTES:
                    response.close()

                    return {
                        "success": False,
                        "error": "Page exceeded maximum allowed size.",
                    }

                chunks.append(chunk)

        except requests.RequestException as error:
            response.close()

            return {
                "success": False,
                "error": str(error),
            }

        encoding = response.encoding or "utf-8"
        response.close()

        try:
            html = b"".join(chunks).decode(
                encoding,
                errors="replace",
            )
        except LookupError:
            html = b"".join(chunks).decode(
                "utf-8",
                errors="replace",
            )

        return {
            "success": True,
            "url": current_url,
            "status_code": 200,
            "html": html,
            "text": extract_page_text(html),
            "bytes_received": total_bytes,
            "fetched_at": utc_now(),
        }

    return {
        "success": False,
        "error": "Redirect processing failed.",
    }


# ---------------------------------------------------------
# SOURCE REGISTRY
# ---------------------------------------------------------

NATIONAL_SOURCES = [
    {
        "name": "National Network to End Domestic Violence",
        "category": "National Coalition",
        "url": "https://nnedv.org/",
    },
    {
        "name": "Legal Services Corporation",
        "category": "Legal Assistance",
        "url": "https://www.lsc.gov/",
    },
    {
        "name": "U.S. Department of Housing and Urban Development",
        "category": "Housing Assistance",
        "url": "https://www.hud.gov/",
    },
    {
        "name": "U.S. Department of Justice",
        "category": "Government Survivor Resources",
        "url": "https://www.justice.gov/ovw",
    },
    {
        "name": "211",
        "category": "Community Resources",
        "url": "https://www.211.org/",
    },
    {
        "name": "Findhelp",
        "category": "Community Resource Directory",
        "url": "https://www.findhelp.org/",
    },
]


def build_source_registry(
    state_coalitions: Optional[dict] = None,
    include_national: bool = True,
) -> list:
    """
    Convert the state directory and national sources into a crawler
    registry.

    Expected state format:
        {
            "WV": {
                "name": "West Virginia",
                "abbr": "WV",
                "url": "https://example.org"
            }
        }
    """

    registry = []

    if state_coalitions:
        for abbreviation, record in state_coalitions.items():

            if not isinstance(record, dict):
                continue

            url = normalize_url(record.get("url", ""))

            if not valid_public_url(url):
                continue

            registry.append({
                "source_id": make_source_id(url),
                "name": record.get(
                    "name",
                    abbreviation,
                ),
                "category": "State Coalition",
                "state": abbreviation,
                "url": url,
            })

    if include_national:
        for source in NATIONAL_SOURCES:
            registry.append({
                **source,
                "source_id": make_source_id(source["url"]),
                "state": None,
            })

    # Avoid duplicate URLs.
    unique = {}

    for source in registry:
        unique[normalize_url(source["url"])] = source

    return list(unique.values())


# ---------------------------------------------------------
# CHANGE DETECTION
# ---------------------------------------------------------

def create_change_record(
    source: dict,
    previous: Optional[dict],
    current: dict,
) -> Optional[dict]:
    """Create a review record when a source is new or has changed."""

    current_hash = fingerprint_text(current.get("text", ""))

    if previous and previous.get("fingerprint") == current_hash:
        return None

    previous_hash = (
        previous.get("fingerprint")
        if previous
        else None
    )

    change_type = "updated_source" if previous else "new_source"

    old_excerpt = (
        previous.get("excerpt", "")
        if previous
        else ""
    )

    new_excerpt = current.get("text", "")[:1500]

    review_id = hashlib.sha256(
        (
            source["source_id"]
            + current_hash
            + current.get("fetched_at", "")
        ).encode("utf-8")
    ).hexdigest()[:20]

    return {
        "review_id": review_id,
        "source_id": source["source_id"],
        "source_name": source["name"],
        "category": source["category"],
        "state": source.get("state"),
        "url": source["url"],
        "change_type": change_type,
        "previous_fingerprint": previous_hash,
        "new_fingerprint": current_hash,
        "previous_excerpt": old_excerpt,
        "new_excerpt": new_excerpt,
        "detected_at": utc_now(),
        "status": "pending",
        "reviewer_note": "",
    }


# ---------------------------------------------------------
# CRAWLER EXECUTION
# ---------------------------------------------------------

def run_crawl(
    state_coalitions: Optional[dict] = None,
    include_national: bool = True,
    storage_dir: str = "resource_crawler_data",
    max_sources: Optional[int] = None,
) -> dict:
    """
    Run one public-source check.

    This checks only registered public URLs. It does not crawl
    survivor-submitted content or private user records.
    """

    storage = CrawlerStorage(Path(storage_dir))

    registry = build_source_registry(
        state_coalitions=state_coalitions,
        include_national=include_national,
    )

    if max_sources is not None:
        registry = registry[:max(0, int(max_sources))]

    snapshots = storage.get_snapshots()
    reviews = storage.get_reviews()

    session = requests.Session()

    checked = 0
    changed = 0
    failed = 0
    skipped = 0

    results = []

    for source in registry:
        url = source["url"]
        source_id = source["source_id"]

        allowed, robots_message = check_robots_permission(
            url,
            session,
        )

        if not allowed:
            skipped += 1

            result = {
                "source": source["name"],
                "url": url,
                "status": "skipped",
                "message": robots_message,
            }

            results.append(result)

            storage.log_activity(
                "source_skipped",
                result,
            )

            continue

        fetched = fetch_public_page(
            url,
            session=session,
            allowed_hosts={get_hostname(url)},
        )

        if not fetched.get("success"):
            failed += 1

            result = {
                "source": source["name"],
                "url": url,
                "status": "failed",
                "message": fetched.get("error", "Unknown error"),
            }

            results.append(result)

            storage.log_activity(
                "source_fetch_failed",
                result,
            )

            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        checked += 1

        current_hash = fingerprint_text(fetched["text"])

        current_snapshot = {
            "source_id": source_id,
            "name": source["name"],
            "category": source["category"],
            "state": source.get("state"),
            "url": url,
            "resolved_url": fetched["url"],
            "fingerprint": current_hash,
            "excerpt": fetched["text"][:1500],
            "fetched_at": fetched["fetched_at"],
            "bytes_received": fetched["bytes_received"],
        }

        previous_snapshot = snapshots.get(source_id)

        change_record = create_change_record(
            source,
            previous_snapshot,
            fetched,
        )

        if change_record:
            existing_ids = {
                item.get("review_id")
                for item in reviews
            }

            if change_record["review_id"] not in existing_ids:
                reviews.append(change_record)
                changed += 1

        # Keep the latest snapshot even if the detected change
        # is waiting for human review. The review record remains
        # available until approved or rejected.
        snapshots[source_id] = current_snapshot

        results.append({
            "source": source["name"],
            "url": url,
            "status": "checked",
            "changed": bool(change_record),
            "fetched_at": fetched["fetched_at"],
        })

        storage.log_activity(
            "source_checked",
            {
                "source": source["name"],
                "url": url,
                "changed": bool(change_record),
            },
        )

        time.sleep(REQUEST_DELAY_SECONDS)

    storage.save_snapshots(snapshots)
    storage.save_reviews(reviews)

    report = {
        "run_at": utc_now(),
        "total_sources": len(registry),
        "checked": checked,
        "changed": changed,
        "failed": failed,
        "skipped": skipped,
        "pending_reviews": len([
            item for item in reviews
            if item.get("status") == "pending"
        ]),
        "results": results,
    }

    storage.log_activity(
        "crawl_completed",
        {
            "checked": checked,
            "changed": changed,
            "failed": failed,
            "skipped": skipped,
        },
    )

    return report


# ---------------------------------------------------------
# REVIEW QUEUE
# ---------------------------------------------------------

def get_pending_reviews(
    storage_dir: str = "resource_crawler_data",
) -> list:
    storage = CrawlerStorage(Path(storage_dir))

    return [
        item for item in storage.get_reviews()
        if item.get("status") == "pending"
    ]


def get_all_reviews(
    storage_dir: str = "resource_crawler_data",
) -> list:
    storage = CrawlerStorage(Path(storage_dir))
    return storage.get_reviews()


def review_change(
    review_id: str,
    decision: str,
    reviewer_note: str = "",
    storage_dir: str = "resource_crawler_data",
) -> dict:
    """
    Approve or reject a detected change.

    Approval records the human decision. It does not automatically
    modify STATE_COALITIONS or any other resource directory.
    """

    decision = (decision or "").strip().lower()

    if decision not in ("approve", "reject"):
        return {
            "success": False,
            "message": "Decision must be approve or reject.",
        }

    storage = CrawlerStorage(Path(storage_dir))
    reviews = storage.get_reviews()

    for item in reviews:
        if item.get("review_id") == review_id:

            if item.get("status") != "pending":
                return {
                    "success": False,
                    "message": "This item has already been reviewed.",
                }

            item["status"] = (
                "approved"
                if decision == "approve"
                else "rejected"
            )

            item["reviewed_at"] = utc_now()
            item["reviewer_note"] = reviewer_note

            if not storage.save_reviews(reviews):
                return {
                    "success": False,
                    "message": "Could not save review decision.",
                }

            storage.log_activity(
                "review_decision",
                {
                    "review_id": review_id,
                    "decision": decision,
                },
            )

            return {
                "success": True,
                "message": f"Change {decision}d.",
                "review_id": review_id,
                "status": item["status"],
            }

    return {
        "success": False,
        "message": "Review record not found.",
    }


def export_review_queue(
    storage_dir: str = "resource_crawler_data",
) -> dict:
    storage = CrawlerStorage(Path(storage_dir))

    return {
        "exported_at": utc_now(),
        "reviews": storage.get_reviews(),
    }


# ---------------------------------------------------------
# STATUS AND DIAGNOSTICS
# ---------------------------------------------------------

def get_crawler_status(
    storage_dir: str = "resource_crawler_data",
) -> dict:
    storage = CrawlerStorage(Path(storage_dir))

    snapshots = storage.get_snapshots()
    reviews = storage.get_reviews()
    activity = storage.get_activity()

    pending = [
        item for item in reviews
        if item.get("status") == "pending"
    ]

    approved = [
        item for item in reviews
        if item.get("status") == "approved"
    ]

    rejected = [
        item for item in reviews
        if item.get("status") == "rejected"
    ]

    return {
        "storage_directory": str(storage.directory),
        "snapshot_count": len(snapshots),
        "review_count": len(reviews),
        "pending_reviews": len(pending),
        "approved_reviews": len(approved),
        "rejected_reviews": len(rejected),
        "activity_entries": len(activity),
        "last_activity": (
            activity[-1]
            if activity
            else None
        ),
    }


# ---------------------------------------------------------
# OFFLINE SELF-TEST
# ---------------------------------------------------------

def self_test() -> dict:
    """
    Offline tests for parsing, fingerprinting, source IDs,
    storage, and review-state logic.

    No network requests are made.
    """

    test_results = {}

    try:
        sample_html = """
        <html>
          <head><title>Test</title></head>
          <body>
            <h1>Survivor Support</h1>
            <p>Legal assistance and housing resources.</p>
            <script>private_script_data()</script>
          </body>
        </html>
        """

        extracted = extract_page_text(sample_html)

        test_results["html_extraction"] = (
            "Survivor Support" in extracted
            and "private_script_data" not in extracted
        )

        test_results["fingerprint"] = (
            fingerprint_text("Resource Page")
            == fingerprint_text(" resource   page ")
        )

        test_results["source_id"] = (
            len(make_source_id("https://example.org")) == 16
        )

        test_results["url_validation"] = (
            valid_public_url("https://example.org")
            and not valid_public_url("file:///etc/passwd")
        )

        test_results["redirect_host_validation"] = (
            get_hostname("https://example.org/path")
            != get_hostname("https://unrelated.example/path")
        )

        test_dir = Path("resource_crawler_self_test")
        storage = CrawlerStorage(test_dir)

        sample_data = {
            "test": {
                "fingerprint": fingerprint_text("sample"),
            }
        }

        write_ok = storage.save_snapshots(sample_data)
        read_back = storage.get_snapshots()

        test_results["local_storage"] = (
            write_ok and read_back == sample_data
        )

        source = {
            "source_id": "test-source",
            "name": "Test Source",
            "category": "Test",
            "url": "https://example.org",
            "state": None,
        }

        current = {
            "text": "A new public resource page.",
            "fetched_at": utc_now(),
        }

        record = create_change_record(
            source,
            None,
            current,
        )

        test_results["new_source_review"] = (
            record is not None
            and record["status"] == "pending"
        )

        # Clean up test artifacts.
        for path in test_dir.glob("*"):
            path.unlink(missing_ok=True)

        test_dir.rmdir()

    except Exception as error:
        logger.exception("Crawler self-test failed")
        test_results["unexpected_error"] = str(error)

    return {
        "passed": all(
            value is True
            for value in test_results.values()
        ),
        "tests": test_results,
    }


# ---------------------------------------------------------
# COMMAND-LINE ENTRY POINT
# ---------------------------------------------------------

if __name__ == "__main__":
    print(json.dumps(self_test(), indent=2))
