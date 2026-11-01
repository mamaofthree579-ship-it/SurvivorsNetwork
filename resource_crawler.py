
from __future__ import annotations

import difflib
import hashlib
import ipaddress
import json
import logging
import re
import socket
import time

from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests


# =========================================================
# CONFIGURATION
# =========================================================

PROJECT_DIR = Path(__file__).resolve().parent

DEFAULT_STORAGE_DIR = PROJECT_DIR / "resource_crawler_data"
DEFAULT_DIRECTORY_FILE = PROJECT_DIR / "state_resource_directory.json"

SNAPSHOT_FILE = "snapshots.json"
REVIEW_FILE = "pending_reviews.json"
ACTIVITY_FILE = "activity_log.json"

REQUEST_TIMEOUT = 15
REQUEST_DELAY_SECONDS = 2

MAX_PAGE_BYTES = 2_000_000
MAX_ROBOTS_BYTES = 512_000
MAX_REDIRECTS = 4

MAX_ACTIVITY_ENTRIES = 2000
MAX_REVIEW_ENTRIES = 10000

ROBOTS_CACHE_SECONDS = 3600

USER_AGENT = (
    "SurvivorsNetworkResourceCrawler/2.0 "
    "(public resource directory maintenance)"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Encoding": "gzip, deflate",
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("survivors_network_crawler")


# =========================================================
# GENERAL HELPERS
# =========================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_storage_dir(directory: Any = None) -> Path:

    if directory is None:
        return DEFAULT_STORAGE_DIR

    path = Path(directory).expanduser()

    if not path.is_absolute():
        path = PROJECT_DIR / path

    return path.resolve()


def normalize_url(url: str) -> str:

    url = (url or "").strip()

    try:
        parsed = urlparse(url)

        return urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or "/",
            parsed.params,
            parsed.query,
            "",
        ))

    except ValueError:
        return ""


def get_hostname(url: str) -> str:

    try:
        return (
            urlparse(url).hostname or ""
        ).lower().rstrip(".")

    except ValueError:
        return ""


def get_origin(url: str) -> str:

    parsed = urlparse(url)

    return (
        f"{parsed.scheme.lower()}://"
        f"{parsed.netloc.lower()}"
    )


def valid_public_url(url: str) -> bool:
    """
    Validate URL structure.

    Network-level DNS validation is performed separately immediately
    before outbound requests.
    """

    try:
        parsed = urlparse((url or "").strip())

        if parsed.scheme.lower() not in ("http", "https"):
            return False

        if not parsed.hostname:
            return False

        if parsed.username or parsed.password:
            return False

        if parsed.port not in (None, 80, 443):
            return False

        hostname = parsed.hostname.lower().rstrip(".")

        if (
            hostname == "localhost"
            or hostname.endswith(".localhost")
            or hostname.endswith(".local")
        ):
            return False

        if " " in hostname:
            return False

        try:
            address = ipaddress.ip_address(hostname)

            if not address.is_global:
                return False

        except ValueError:
            pass

        return True

    except (ValueError, TypeError):
        return False


def resolve_public_host(hostname: str) -> bool:
    """
    Reject DNS names resolving to private, local, or non-public
    addresses.

    Important: this is an additional application-level safeguard.
    It does not completely eliminate DNS rebinding between validation
    and connection. Production deployment should also enforce
    outbound network restrictions.
    """

    if not hostname:
        return False

    try:
        address = ipaddress.ip_address(hostname)

        return address.is_global

    except ValueError:
        pass

    try:
        results = socket.getaddrinfo(
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )

        if not results:
            return False

        addresses = {
            result[4][0]
            for result in results
        }

        for address_text in addresses:

            address = ipaddress.ip_address(
                address_text
            )

            if not address.is_global:
                return False

        return True

    except (OSError, ValueError):
        return False


def fingerprint_text(text: str) -> str:

    normalized = re.sub(
        r"\s+",
        " ",
        text or "",
    ).strip().lower()

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


def make_source_id(url: str) -> str:

    return hashlib.sha256(
        normalize_url(url).encode("utf-8")
    ).hexdigest()[:16]


def safe_text(value: Any) -> str:

    if value is None:
        return ""

    if isinstance(value, (str, int, float)):
        return str(value).strip()

    return ""


def create_session() -> requests.Session:
    """
    Create an isolated HTTP session.

    Environment-configured proxies are disabled so that an
    unexpected proxy configuration cannot change the crawler's
    network destination.
    """

    session = requests.Session()

    session.trust_env = False
    session.headers.update(HEADERS)

    return session


# =========================================================
# REQUEST RATE LIMITING
# =========================================================

class HostRateLimiter:
    """
    Maintain a minimum interval between requests to each hostname.

    This applies independently to robots.txt and page requests.
    """

    def __init__(
        self,
        delay: float = REQUEST_DELAY_SECONDS,
    ):

        self.delay = max(0.0, float(delay))
        self.last_request = {}

    def wait(self, hostname: str):

        now = time.monotonic()

        previous = self.last_request.get(
            hostname,
            0.0,
        )

        remaining = self.delay - (now - previous)

        if remaining > 0:
            time.sleep(remaining)

        self.last_request[hostname] = time.monotonic()


# =========================================================
# JSON STORAGE
# =========================================================

class StorageDataError(RuntimeError):
    pass


class CrawlerStorage:

    def __init__(self, directory: Any = None):

        self.directory = resolve_storage_dir(directory)

        self.directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.snapshot_file = (
            self.directory / SNAPSHOT_FILE
        )

        self.review_file = (
            self.directory / REVIEW_FILE
        )

        self.activity_file = (
            self.directory / ACTIVITY_FILE
        )

    def read_json(
        self,
        path: Path,
        default: Any,
    ) -> Any:

        if not path.exists():
            return default

        try:

            with path.open(
                "r",
                encoding="utf-8",
            ) as file:

                return json.load(file)

        except (json.JSONDecodeError, OSError) as error:

            logger.exception(
                "Storage read failed: %s",
                path,
            )

            raise StorageDataError(
                f"Cannot safely read {path.name}. "
                "Existing data was preserved."
            ) from error

    def write_json(
        self,
        path: Path,
        data: Any,
    ) -> bool:
        """
        Write through a temporary file and atomic replacement.

        Flush and fsync reduce the risk of losing recently written
        records if the application stops unexpectedly.
        """

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = path.with_suffix(
            path.suffix + ".tmp"
        )

        try:

            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as file:

                json.dump(
                    data,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

                file.flush()

                import os
                os.fsync(file.fileno())

            temporary_path.replace(path)

            return True

        except (OSError, TypeError, ValueError):

            logger.exception(
                "Storage write failed: %s",
                path,
            )

            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            return False

    def get_snapshots(self) -> dict:

        data = self.read_json(
            self.snapshot_file,
            {},
        )

        if not isinstance(data, dict):
            raise StorageDataError(
                "snapshots.json must contain an object."
            )

        return data

    def save_snapshots(self, snapshots: dict) -> bool:

        if not isinstance(snapshots, dict):
            return False

        return self.write_json(
            self.snapshot_file,
            snapshots,
        )

    def get_reviews(self) -> list:

        data = self.read_json(
            self.review_file,
            [],
        )

        if not isinstance(data, list):
            raise StorageDataError(
                "pending_reviews.json must contain a list."
            )

        return data

    def save_reviews(self, reviews: list) -> bool:

        if not isinstance(reviews, list):
            return False

        # Do not truncate this queue. Older pending reviews
        # must never disappear simply because the queue grows.

        return self.write_json(
            self.review_file,
            reviews,
        )

    def get_activity(self) -> list:

        data = self.read_json(
            self.activity_file,
            [],
        )

        if not isinstance(data, list):
            raise StorageDataError(
                "activity_log.json must contain a list."
            )

        return data

    def log_activity(
        self,
        event: str,
        details: Optional[dict] = None,
    ) -> bool:

        try:

            activity = self.get_activity()

        except StorageDataError:

            logger.exception(
                "Activity log was not modified."
            )

            return False

        activity.append({
            "timestamp": utc_now(),
            "event": safe_text(event),
            "details": (
                details
                if isinstance(details, dict)
                else {}
            ),
        })

        return self.write_json(
            self.activity_file,
            activity[-MAX_ACTIVITY_ENTRIES:],
        )


# =========================================================
# STATE DIRECTORY LOADING
# =========================================================

def load_state_directory(
    directory_file: Any = None,
) -> dict:
    """
    Read the registered public state directory.

    This function never modifies the source directory.
    """

    path = (
        Path(directory_file).expanduser()
        if directory_file is not None
        else DEFAULT_DIRECTORY_FILE
    )

    if not path.is_absolute():
        path = PROJECT_DIR / path

    if not path.exists():
        logger.warning(
            "State directory not found: %s",
            path,
        )
        return {}

    try:

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

    except (OSError, json.JSONDecodeError) as error:

        raise StorageDataError(
            f"State directory could not be read: {path}"
        ) from error

    if not isinstance(data, dict):
        raise StorageDataError(
            "State directory must contain an object."
        )

    states = data.get("states", data)

    if not isinstance(states, dict):
        raise StorageDataError(
            "The states field must contain an object."
        )

    return states


# =========================================================
# HTML TEXT EXTRACTION
# =========================================================

class PublicPageTextParser(HTMLParser):

    IGNORED_TAGS = {
        "script",
        "style",
        "noscript",
        "svg",
        "iframe",
        "template",
        "form",
    }

    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "section",
        "tr",
        "ul",
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
            return

        if (
            self.ignore_depth == 0
            and tag in self.BLOCK_TAGS
        ):
            self.parts.append(" ")

    def handle_endtag(self, tag):

        tag = tag.lower()

        if tag in self.IGNORED_TAGS:

            if tag in self.active_ignored_tags:

                reverse_index = (
                    self.active_ignored_tags[::-1].index(tag)
                )

                index = (
                    len(self.active_ignored_tags)
                    - 1
                    - reverse_index
                )

                self.active_ignored_tags.pop(index)

                self.ignore_depth = max(
                    0,
                    self.ignore_depth - 1,
                )

            return

        if (
            self.ignore_depth == 0
            and tag in self.BLOCK_TAGS
        ):
            self.parts.append(" ")

    def handle_data(self, data):

        if self.ignore_depth == 0 and data.strip():
            self.parts.append(data.strip())

    def get_text(self):

        return re.sub(
            r"\s+",
            " ",
            " ".join(self.parts),
        ).strip()


def extract_page_text(html: str) -> str:

    parser = PublicPageTextParser()

    try:

        parser.feed(html)
        parser.close()

        return parser.get_text()

    except Exception:

        logger.exception(
            "HTML extraction failed."
        )

        return ""


# =========================================================
# ROBOTS.TXT POLICY CACHE
# =========================================================

class RobotsPolicyCache:

    def __init__(self):

        self.cache = {}

    def get(
        self,
        url: str,
        session: requests.Session,
        limiter: Optional[HostRateLimiter] = None,
    ) -> tuple[bool, str]:

        origin = get_origin(url)

        cached = self.cache.get(origin)

        if cached:

            expires_at = cached["expires_at"]

            if time.monotonic() < expires_at:

                return (
                    cached["allowed"],
                    cached["message"],
                )

        parsed = urlparse(url)

        robots_url = (
            f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        )

        if not valid_public_url(robots_url):
            return False, "Invalid robots.txt URL."

        hostname = get_hostname(robots_url)

        if not resolve_public_host(hostname):
            return False, "Robots host failed public DNS validation."

        if limiter:
            limiter.wait(hostname)

        response = None

        try:

            response = session.get(
                robots_url,
                timeout=REQUEST_TIMEOUT,
                stream=True,
                allow_redirects=False,
            )

            if response.status_code in (404, 410):

                result = (
                    True,
                    "No robots.txt file was found.",
                )

            elif response.status_code != 200:

                result = (
                    False,
                    (
                        "Robots policy could not be verified: "
                        f"HTTP {response.status_code}."
                    ),
                )

            else:

                content = bytearray()

                for chunk in response.iter_content(
                    chunk_size=8192
                ):

                    if not chunk:
                        continue

                    content.extend(chunk)

                    if len(content) > MAX_ROBOTS_BYTES:

                        result = (
                            False,
                            "Robots file exceeds size limit.",
                        )

                        break

                else:

                    parser = RobotFileParser()
                    parser.parse(
                        bytes(content).decode(
                            "utf-8",
                            errors="replace",
                        ).splitlines()
                    )

                    allowed = parser.can_fetch(
                        USER_AGENT,
                        url,
                    )

                    result = (
                        allowed,
                        (
                            "robots.txt permits access."
                            if allowed
                            else "robots.txt disallows access."
                        ),
                    )

            self.cache[origin] = {
                "allowed": result[0],
                "message": result[1],
                "expires_at": (
                    time.monotonic()
                    + ROBOTS_CACHE_SECONDS
                ),
            }

            return result

        except requests.RequestException as error:

            return (
                False,
                f"Robots request failed: {error}",
            )

        finally:

            if response is not None:
                response.close()


def check_robots_permission(
    url: str,
    session: requests.Session,
    cache: Optional[RobotsPolicyCache] = None,
    limiter: Optional[HostRateLimiter] = None,
) -> tuple[bool, str]:

    cache = cache or RobotsPolicyCache()

    return cache.get(
        url,
        session,
        limiter,
    )


# =========================================================
# SAFE PUBLIC PAGE FETCHING
# =========================================================

def fetch_public_page(
    url: str,
    session: Optional[requests.Session] = None,
    allowed_hosts: Optional[set[str]] = None,
    limiter: Optional[HostRateLimiter] = None,
) -> dict:
    """
    Fetch one explicitly registered public page.

    Redirects are handled manually and each destination is validated.

    Cross-host redirects require explicit registration in allowed_hosts.

    DNS resolution is checked before each request. Network-level
    egress filtering is still required for complete DNS-rebinding
    protection.
    """

    owns_session = session is None

    session = session or create_session()

    url = normalize_url(url)

    if not valid_public_url(url):

        if owns_session:
            session.close()

        return {
            "success": False,
            "error": "Invalid or non-public URL.",
        }

    original_host = get_hostname(url)

    if allowed_hosts is None:
        allowed_hosts = {original_host}

    allowed_hosts = {
        str(host).lower().strip().rstrip(".")
        for host in allowed_hosts
        if host
    }

    if original_host not in allowed_hosts:

        if owns_session:
            session.close()

        return {
            "success": False,
            "error": "Initial host is not allowlisted.",
        }

    current_url = url

    try:

        for redirect_number in range(
            MAX_REDIRECTS + 1
        ):

            if not valid_public_url(current_url):

                return {
                    "success": False,
                    "error": "Invalid redirect destination.",
                }

            current_host = get_hostname(
                current_url
            )

            if current_host not in allowed_hosts:

                return {
                    "success": False,
                    "error": "Redirect host is not allowlisted.",
                }

            if not resolve_public_host(current_host):

                return {
                    "success": False,
                    "error": (
                        "Destination failed public DNS validation."
                    ),
                }

            if limiter:
                limiter.wait(current_host)

            response = None

            try:

                response = session.get(
                    current_url,
                    timeout=REQUEST_TIMEOUT,
                    stream=True,
                    allow_redirects=False,
                )

                if (
                    response.is_redirect
                    or response.is_permanent_redirect
                ):

                    location = response.headers.get(
                        "Location"
                    )

                    if not location:

                        return {
                            "success": False,
                            "error": "Redirect destination missing.",
                        }

                    if redirect_number >= MAX_REDIRECTS:

                        return {
                            "success": False,
                            "error": "Maximum redirects exceeded.",
                        }

                    next_url = urljoin(
                        current_url,
                        location,
                    )

                    if not valid_public_url(next_url):

                        return {
                            "success": False,
                            "error": "Invalid redirect destination.",
                        }

                    if (
                        get_hostname(next_url)
                        not in allowed_hosts
                    ):

                        return {
                            "success": False,
                            "error": (
                                "Cross-host redirect blocked. "
                                "Register the destination host first."
                            ),
                        }

                    current_url = next_url
                    continue

                if response.status_code != 200:

                    return {
                        "success": False,
                        "error": (
                            f"HTTP {response.status_code}"
                        ),
                    }

                content_type = response.headers.get(
                    "Content-Type",
                    "",
                ).lower()

                if (
                    "text/html" not in content_type
                    and "application/xhtml+xml"
                    not in content_type
                ):

                    return {
                        "success": False,
                        "error": "Resource is not an HTML page.",
                    }

                content_length = response.headers.get(
                    "Content-Length"
                )

                if content_length:

                    try:

                        if (
                            int(content_length)
                            > MAX_PAGE_BYTES
                        ):

                            return {
                                "success": False,
                                "error": "Page exceeds size limit.",
                            }

                    except ValueError:
                        pass

                chunks = []
                total_bytes = 0

                for chunk in response.iter_content(
                    chunk_size=16384
                ):

                    if not chunk:
                        continue

                    total_bytes += len(chunk)

                    if total_bytes > MAX_PAGE_BYTES:

                        return {
                            "success": False,
                            "error": "Page exceeds size limit.",
                        }

                    chunks.append(chunk)

                raw_html = b"".join(chunks)

                encoding = response.encoding or "utf-8"

                try:

                    html = raw_html.decode(
                        encoding,
                        errors="replace",
                    )

                except LookupError:

                    html = raw_html.decode(
                        "utf-8",
                        errors="replace",
                    )

                text = extract_page_text(html)

                if not text:

                    return {
                        "success": False,
                        "error": (
                            "No readable page text extracted. "
                            "Previous snapshot preserved."
                        ),
                    }

                return {
                    "success": True,
                    "url": current_url,
                    "status_code": 200,
                    "text": text,
                    "bytes_received": total_bytes,
                    "fetched_at": utc_now(),
                }

            except requests.RequestException as error:

                return {
                    "success": False,
                    "error": str(error),
                }

            finally:

                if response is not None:
                    response.close()

        return {
            "success": False,
            "error": "Redirect processing failed.",
        }

    finally:

        if owns_session:
            session.close()


# =========================================================
# SOURCE REGISTRY
# =========================================================

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


def get_record_url(record: dict) -> str:

    return normalize_url(
        safe_text(
            record.get("website")
            or record.get("url")
            or record.get("website_url")
        )
    )


def build_source_registry(
    state_coalitions: Optional[dict] = None,
    include_national: bool = True,
) -> list:

    if state_coalitions is None:
        state_coalitions = load_state_directory()

    registry = []

    if isinstance(state_coalitions, dict):

        for state_key, record in state_coalitions.items():

            if not isinstance(record, dict):
                continue

            url = get_record_url(record)

            if not valid_public_url(url):
                continue

            state_name = (
                safe_text(record.get("state_name"))
                or safe_text(record.get("name"))
                or safe_text(state_key)
            )

            state_code = (
                safe_text(record.get("code"))
                or safe_text(record.get("abbr"))
                or safe_text(record.get("abbreviation"))
                or (
                    safe_text(state_key)
                    if len(safe_text(state_key)) == 2
                    else ""
                )
            )

            source_name = (
                safe_text(record.get("coalition_name"))
                or safe_text(record.get("organization"))
                or safe_text(record.get("coalition"))
                or safe_text(record.get("name"))
                or state_name
            )

            registry.append({
                "source_id": make_source_id(url),
                "name": source_name,
                "category": "State Coalition",
                "state": state_name,
                "state_code": state_code.upper(),
                "url": url,
            })

    if include_national:

        for source in NATIONAL_SOURCES:

            registry.append({
                **source,
                "source_id": make_source_id(
                    source["url"]
                ),
                "state": None,
                "state_code": None,
            })

    unique = {}

    for source in registry:

        key = normalize_url(
            source["url"]
        ).lower()

        if key not in unique:
            unique[key] = source

    return list(unique.values())


# =========================================================
# CHANGE DETECTION
# =========================================================

def create_change_summary(
    previous_text: str,
    current_text: str,
) -> dict:
    """
    Produce a compact comparison for human review.

    The crawler preserves the complete extracted text in neither
    snapshots nor reviews. Only bounded excerpts and a summary are
    retained.
    """

    old_lines = (
        previous_text or ""
    ).split(". ")

    new_lines = (
        current_text or ""
    ).split(". ")

    difference = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="previous",
            tofile="current",
            lineterm="",
        )
    )

    return {
        "added_sections": sum(
            1 for line in difference
            if line.startswith("+")
            and not line.startswith("+++")
        ),
        "removed_sections": sum(
            1 for line in difference
            if line.startswith("-")
            and not line.startswith("---")
        ),
        "diff_excerpt": "\n".join(
            difference[:40]
        )[:4000],
    }


def create_change_record(
    source: dict,
    previous: Optional[dict],
    current: dict,
) -> Optional[dict]:

    current_text = current.get("text", "")

    current_hash = fingerprint_text(
        current_text
    )

    if (
        previous
        and previous.get("fingerprint") == current_hash
    ):
        return None

    previous_hash = (
        previous.get("fingerprint")
        if previous
        else None
    )

    previous_excerpt = (
        previous.get("excerpt", "")
        if isinstance(previous, dict)
        else ""
    )

    change_type = (
        "updated_source"
        if previous
        else "new_source"
    )

    summary = create_change_summary(
        previous_excerpt,
        current_text[:1500],
    )

    review_id = hashlib.sha256(
        (
            source["source_id"]
            + current_hash
        ).encode("utf-8")
    ).hexdigest()[:20]

    return {
        "review_id": review_id,
        "source_id": source["source_id"],
        "source_name": source["name"],
        "category": source["category"],
        "state": source.get("state"),
        "state_code": source.get("state_code"),
        "url": source["url"],
        "resolved_url": current.get(
            "url",
            source["url"],
        ),
        "change_type": change_type,
        "previous_fingerprint": previous_hash,
        "new_fingerprint": current_hash,
        "previous_excerpt": previous_excerpt[:1500],
        "new_excerpt": current_text[:1500],
        "change_summary": summary,
        "detected_at": utc_now(),
        "status": "pending",
        "reviewer_note": "",
    }


# =========================================================
# CRAWLER EXECUTION
# =========================================================

def run_crawl(
    state_coalitions: Optional[dict] = None,
    include_national: bool = True,
    storage_dir: Any = None,
    max_sources: Optional[int] = None,
) -> dict:
    """
    Run one registered public-resource check.

    Persistence order:
      1. Read existing records.
      2. Fetch registered pages.
      3. Save newly detected review records.
      4. Save successful snapshots.

    If snapshot saving fails after review saving succeeds, the
    review remains available and the next run can recover the
    snapshot without duplicating the review.
    """

    storage = CrawlerStorage(storage_dir)

    registry = build_source_registry(
        state_coalitions=state_coalitions,
        include_national=include_national,
    )

    if max_sources is not None:

        registry = registry[
            :max(0, int(max_sources))
        ]

    snapshots = storage.get_snapshots()
    reviews = storage.get_reviews()

    existing_review_ids = {
        item.get("review_id")
        for item in reviews
        if isinstance(item, dict)
    }

    session = create_session()

    limiter = HostRateLimiter()
    robots_cache = RobotsPolicyCache()

    checked = 0
    changed = 0
    failed = 0
    skipped = 0

    results = []

    try:

        for source in registry:

            url = source["url"]
            source_id = source["source_id"]

            allowed, robots_message = (
                check_robots_permission(
                    url,
                    session,
                    cache=robots_cache,
                    limiter=limiter,
                )
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
                allowed_hosts={
                    get_hostname(url)
                },
                limiter=limiter,
            )

            if not fetched.get("success"):

                failed += 1

                result = {
                    "source": source["name"],
                    "url": url,
                    "status": "failed",
                    "message": fetched.get(
                        "error",
                        "Unknown error",
                    ),
                }

                results.append(result)

                storage.log_activity(
                    "source_fetch_failed",
                    result,
                )

                continue

            checked += 1

            current_hash = fingerprint_text(
                fetched["text"]
            )

            current_snapshot = {
                "source_id": source_id,
                "name": source["name"],
                "category": source["category"],
                "state": source.get("state"),
                "state_code": source.get("state_code"),
                "url": url,
                "resolved_url": fetched["url"],
                "fingerprint": current_hash,
                "excerpt": fetched["text"][:1500],
                "fetched_at": fetched["fetched_at"],
                "bytes_received": fetched["bytes_received"],
            }

            previous_snapshot = snapshots.get(
                source_id
            )

            change_record = create_change_record(
                source,
                previous_snapshot,
                fetched,
            )

            newly_queued = False

            if change_record:

                review_id = change_record["review_id"]

                if review_id not in existing_review_ids:

                    reviews.append(change_record)

                    existing_review_ids.add(
                        review_id
                    )

                    changed += 1
                    newly_queued = True

            snapshots[source_id] = current_snapshot

            result = {
                "source": source["name"],
                "url": url,
                "status": "checked",
                "changed": newly_queued,
                "fetched_at": fetched["fetched_at"],
            }

            results.append(result)

            storage.log_activity(
                "source_checked",
                result,
            )

    finally:

        session.close()

    # Save review records first. This ensures a detected change
    # is not lost if the snapshot file cannot subsequently save.

    reviews_saved = storage.save_reviews(
        reviews
    )

    snapshots_saved = storage.save_snapshots(
        snapshots
    )

    pending_count = sum(
        1 for item in reviews
        if (
            isinstance(item, dict)
            and item.get("status") == "pending"
        )
    )

    report = {
        "run_at": utc_now(),
        "total_sources": len(registry),
        "checked": checked,
        "changed": changed,
        "failed": failed,
        "skipped": skipped,
        "pending_reviews": pending_count,
        "snapshots_saved": snapshots_saved,
        "reviews_saved": reviews_saved,
        "results": results,
    }

    storage.log_activity(
        "crawl_completed",
        {
            "checked": checked,
            "changed": changed,
            "failed": failed,
            "skipped": skipped,
            "snapshots_saved": snapshots_saved,
            "reviews_saved": reviews_saved,
        },
    )

    return report


# =========================================================
# REVIEW QUEUE
# =========================================================

def get_pending_reviews(
    storage_dir: Any = None,
) -> list:

    storage = CrawlerStorage(storage_dir)

    return [
        item
        for item in storage.get_reviews()
        if (
            isinstance(item, dict)
            and item.get("status") == "pending"
        )
    ]


def get_all_reviews(
    storage_dir: Any = None,
) -> list:

    storage = CrawlerStorage(storage_dir)

    return storage.get_reviews()


def review_change(
    review_id: str,
    decision: str,
    reviewer_note: str = "",
    storage_dir: Any = None,
) -> dict:
    """
    Record a human review decision.

    This operation never modifies the resource directory.
    """

    decision = (
        decision or ""
    ).strip().lower()

    if decision not in ("approve", "reject"):

        return {
            "success": False,
            "message": "Decision must be approve or reject.",
        }

    storage = CrawlerStorage(storage_dir)

    try:

        reviews = storage.get_reviews()

    except StorageDataError as error:

        return {
            "success": False,
            "message": str(error),
        }

    for item in reviews:

        if not isinstance(item, dict):
            continue

        if item.get("review_id") != review_id:
            continue

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

        item["reviewer_note"] = safe_text(
            reviewer_note
        )

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
            "directory_modified": False,
        }

    return {
        "success": False,
        "message": "Review record not found.",
    }


def export_review_queue(
    storage_dir: Any = None,
) -> dict:

    storage = CrawlerStorage(storage_dir)

    return {
        "exported_at": utc_now(),
        "reviews": storage.get_reviews(),
    }


# =========================================================
# STATUS AND DIAGNOSTICS
# =========================================================

def get_crawler_status(
    storage_dir: Any = None,
) -> dict:

    storage = CrawlerStorage(storage_dir)

    snapshots = storage.get_snapshots()
    reviews = storage.get_reviews()
    activity = storage.get_activity()

    pending = [
        item for item in reviews
        if (
            isinstance(item, dict)
            and item.get("status") == "pending"
        )
    ]

    approved = [
        item for item in reviews
        if (
            isinstance(item, dict)
            and item.get("status") == "approved"
        )
    ]

    rejected = [
        item for item in reviews
        if (
            isinstance(item, dict)
            and item.get("status") == "rejected"
        )
    ]

    return {
        "storage_directory": str(storage.directory),
        "directory_file": str(DEFAULT_DIRECTORY_FILE),
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


# =========================================================
# OFFLINE SELF-TEST
# =========================================================

def self_test() -> dict:
    """
    Offline tests.

    No websites are contacted.
    """

    test_results = {}

    test_dir = (
        PROJECT_DIR / "resource_crawler_self_test"
    )

    try:

        sample_html = """
        <html>
          <head>
            <title>Test</title>
          </head>
          <body>
            <h1>Survivor Support</h1>
            <p>Legal assistance and housing resources.</p>
            <script>private_script_data()</script>
            <style>.hidden { display: none; }</style>
          </body>
        </html>
        """

        extracted = extract_page_text(
            sample_html
        )

        test_results["html_extraction"] = (
            "Survivor Support" in extracted
            and "Legal assistance" in extracted
            and "private_script_data" not in extracted
            and "display: none" not in extracted
        )

        test_results["fingerprint"] = (
            fingerprint_text("Resource Page")
            == fingerprint_text(" resource   page ")
        )

        test_results["source_id"] = (
            len(
                make_source_id(
                    "https://example.org"
                )
            ) == 16
        )

        test_results["url_validation"] = (
            valid_public_url("https://example.org")
            and not valid_public_url(
                "file:///etc/passwd"
            )
            and not valid_public_url(
                "http://localhost/"
            )
            and not valid_public_url(
                "http://127.0.0.1/"
            )
            and not valid_public_url(
                "https://user:password@example.org/"
            )
        )

        test_results["redirect_host_validation"] = (
            get_hostname(
                "https://example.org/path"
            )
            != get_hostname(
                "https://unrelated.example/path"
            )
        )

        sample_directory = {
            "West Virginia": {
                "name": "West Virginia",
                "code": "WV",
                "website": "https://example.org",
            },
            "Invalid State": {
                "name": "Invalid State",
                "website": "file:///etc/passwd",
            },
        }

        registry = build_source_registry(
            state_coalitions=sample_directory,
            include_national=False,
        )

        test_results["website_field_compatibility"] = (
            len(registry) == 1
            and registry[0]["url"]
            == "https://example.org"
            and registry[0]["state_code"] == "WV"
        )

        legacy_directory = {
            "WV": {
                "name": "West Virginia",
                "abbr": "WV",
                "url": "https://example.org",
            }
        }

        legacy_registry = build_source_registry(
            state_coalitions=legacy_directory,
            include_national=False,
        )

        test_results["legacy_url_compatibility"] = (
            len(legacy_registry) == 1
            and legacy_registry[0]["url"]
            == "https://example.org"
        )

        storage = CrawlerStorage(test_dir)

        sample_data = {
            "test": {
                "fingerprint": fingerprint_text(
                    "sample"
                ),
            }
        }

        write_ok = storage.save_snapshots(
            sample_data
        )

        read_back = storage.get_snapshots()

        test_results["local_storage"] = (
            write_ok
            and read_back == sample_data
        )

        review_write_ok = storage.save_reviews([
            {
                "review_id": "test-review",
                "status": "pending",
            }
        ])

        test_results["review_storage"] = (
            review_write_ok
            and len(storage.get_reviews()) == 1
            and storage.get_reviews()[0]["status"]
            == "pending"
        )

        source = {
            "source_id": "test-source",
            "name": "Test Source",
            "category": "Test",
            "url": "https://example.org",
            "state": None,
        }

        current = {
            "url": "https://example.org",
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

        unchanged = create_change_record(
            source,
            {
                "fingerprint": fingerprint_text(
                    current["text"]
                ),
                "excerpt": current["text"],
            },
            current,
        )

        test_results["unchanged_page_detection"] = (
            unchanged is None
        )

        summary = create_change_summary(
            "Old legal assistance information.",
            "New legal assistance information.",
        )

        test_results["change_summary"] = (
            summary["added_sections"] > 0
            and summary["removed_sections"] > 0
        )

        # Confirm that approved reviews remain separate
        # from directory data.

        test_results["directory_separation"] = (
            DEFAULT_DIRECTORY_FILE.name
            == "state_resource_directory.json"
            and storage.review_file.name
            == REVIEW_FILE
        )

    except Exception as error:

        logger.exception(
            "Crawler self-test failed."
        )

        test_results["unexpected_error"] = str(
            error
        )

    finally:

        if test_dir.exists():

            try:

                for path in test_dir.iterdir():

                    if path.is_file():
                        path.unlink(missing_ok=True)

                test_dir.rmdir()

            except OSError:

                logger.warning(
                    "Could not completely remove self-test directory."
                )

    return {
        "passed": all(
            value is True
            for value in test_results.values()
        ),
        "tests": test_results,
    }


# =========================================================
# COMMAND-LINE ENTRY POINT
# =========================================================

if __name__ == "__main__":

    print(
        json.dumps(
            self_test(),
            indent=2,
        )
    )
