from __future__ import annotations

import os

import re

import json

import time

import hashlib

import logging

from pathlib import Path

from datetime import datetime, timezone

from html.parser import HTMLParser

from urllib.parse import urlparse

from urllib.robotparser import RobotFileParser

import requests

# ============================================================

# CONFIGURATION

# ============================================================

CRAWLER_VERSION = "1.0"

DEFAULT_STORAGE = Path("resource_crawler_data")

REQUEST_TIMEOUT = 15

MAX_RESPONSE_BYTES = 3_000_000

REQUEST_DELAY_SECONDS = 2.0

USER_AGENT = (

    "SurvivorsNetworkResourceCrawler/1.0 "

    "(public-resource-directory; contact: project-maintainer)"

)

NATIONAL_SOURCES = [

    {

        "name": "NNEDV State and U.S. Territory Coalitions",

        "category": "National coalition directory",

        "url": (

            "https://nnedv.org/content/"

            "state-u-s-territory-coalitions/"

        ),

    },

    {

        "name": "DOJ State and Territory Coalitions",

        "category": "National coalition directory",

        "url": (

            "https://www.justice.gov/ovw/"

            "state-and-territory-coalitions"

        ),

    },

    {

        "name": "Legal Services Corporation",

        "category": "Legal assistance directory",

        "url": (

            "https://www.lsc.gov/about-lsc/"

            "what-legal-aid/i-need-legal-help"

        ),

    },

    {

        "name": "HUD Find Shelter",

        "category": "Shelter directory",

        "url": "https://www.hud.gov/FindShelter",

    },

    {

        "name": "211",

        "category": "Community services directory",

        "url": "https://www.211.org/",

    },

    {

        "name": "Findhelp",

        "category": "Community services directory",

        "url": "https://www.findhelp.org/",

    },

]

logging.basicConfig(

    level=logging.INFO,

    format="%(asctime)s | %(levelname)s | %(message)s",

)

LOGGER = logging.getLogger("survivors_resource_crawler")

# ============================================================

# HTML TEXT EXTRACTION

# ============================================================

class PublicPageTextParser(HTMLParser):

    """

    Extract visible page text without requiring BeautifulSoup.

    Scripts, styles, navigation metadata, and other non-content

    sections are excluded from the extracted text.

    """

    IGNORED_TAGS = {

        "script",

        "style",

        "noscript",

        "svg",

        "head",

    }

    def __init__(self):

        super().__init__()

        self.parts = []

        self.ignore_depth = 0

    def handle_starttag(self, tag, attrs):

        if tag.lower() in self.IGNORED_TAGS:

            self.ignore_depth += 1

    def handle_endtag(self, tag):

        if tag.lower() in self.IGNORED_TAGS:

            self.ignore_depth = max(0, self.ignore_depth - 1)

    def handle_data(self, data):

        if self.ignore_depth == 0 and data.strip():

            self.parts.append(data.strip())

    def get_text(self):

        return " ".join(self.parts)

def extract_page_text(html: str) -> str:

    parser = PublicPageTextParser()

    parser.feed(html)

    text = parser.get_text()

    text = re.sub(r"\s+", " ", text)

    text = re.sub(r"\b(cookie|cookies)\b", "", text, flags=re.I)

    return text.strip()

# ============================================================

# STORAGE

# ============================================================

class CrawlerStorage:

    def __init__(self, storage_dir=DEFAULT_STORAGE):

        self.storage_dir = Path(storage_dir)

        self.storage_dir.mkdir(

            parents=True,

            exist_ok=True,

        )

        self.snapshots_file = (

            self.storage_dir / "source_snapshots.json"

        )

        self.review_file = (

            self.storage_dir / "review_queue.json"

        )

        self.activity_file = (

            self.storage_dir / "crawler_activity.json"

        )

    @staticmethod

    def read_json(path: Path, default):

        if not path.exists():

            return default

        try:

            with path.open("r", encoding="utf-8") as file:

                return json.load(file)

        except (OSError, json.JSONDecodeError):

            LOGGER.exception("Could not read %s", path)

            raise RuntimeError(

                f"Storage file could not be read safely: {path}"

            )

    @staticmethod

    def write_json(path: Path, data):

        temporary = path.with_suffix(path.suffix + ".tmp")

        with temporary.open("w", encoding="utf-8") as file:

            json.dump(

                data,

                file,

                indent=2,

                ensure_ascii=False,

            )

        os.replace(temporary, path)

    def get_snapshots(self):

        return self.read_json(

            self.snapshots_file,

            {},

        )

    def save_snapshots(self, snapshots):

        self.write_json(

            self.snapshots_file,

            snapshots,

        )

    def get_review_queue(self):

        return self.read_json(

            self.review_file,

            [],

        )

    def save_review_queue(self, queue):

        self.write_json(

            self.review_file,

            queue,

        )

    def get_activity(self):

        return self.read_json(

            self.activity_file,

            [],

        )

    def add_activity(self, event):

        activity = self.get_activity()

        activity.append(event)

        # Keep the most recent 2,000 activity records.

        activity = activity[-2000:]

        self.write_json(

            self.activity_file,

            activity,

        )

# ============================================================

# SOURCE REGISTRY

# ============================================================

def build_source_registry(state_coalitions):

    """

    Convert the application's state directory into crawler sources.

    Expected state_coalitions structure:

    {

        "West Virginia": {

            "abbr": "WV",

            "name": "Coalition Name",

            "url": "https://example.org/"

        }

    }

    Only public source URLs are included.

    """

    sources = []

    for state, record in state_coalitions.items():

        url = record.get("url", "").strip()

        if not url:

            continue

        sources.append({

            "source_id": f"state_{record.get('abbr', state)}",

            "name": record.get("name", state),

            "category": "State coalition",

            "state": state,

            "url": url,

        })

    for index, source in enumerate(NATIONAL_SOURCES):

        sources.append({

            "source_id": f"national_{index + 1}",

            "name": source["name"],

            "category": source["category"],

            "state": None,

            "url": source["url"],

        })

    return sources

# ============================================================

# URL VALIDATION AND ROBOTS.TXT

# ============================================================

def normalize_hostname(url: str) -> str:

    parsed = urlparse(url)

    if parsed.scheme.lower() != "https":

        raise ValueError("Only HTTPS source URLs are allowed.")

    if not parsed.hostname:

        raise ValueError("Source URL has no hostname.")

    if parsed.username or parsed.password:

        raise ValueError("Credentials in source URLs are not allowed.")

    return parsed.hostname.lower().rstrip(".")

def host_is_allowed(url: str, allowed_host: str) -> bool:

    try:

        host = normalize_hostname(url)

    except ValueError:

        return False

    allowed_host = allowed_host.lower().rstrip(".")

    return (

        host == allowed_host

        or host.endswith("." + allowed_host)

    )

def check_robots_permission(

    session: requests.Session,

    url: str,

) -> tuple[bool, str]:

    """

    Check the source's robots.txt before requesting its homepage.

    A missing robots.txt (404 or 410) is treated as no published

    restriction. Other failures fail closed.

    """

    parsed = urlparse(url)

    robots_url = (

        f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    )

    try:

        response = session.get(

            robots_url,

            timeout=REQUEST_TIMEOUT,

            allow_redirects=False,

            headers={

                "User-Agent": USER_AGENT,

            },

        )

        if response.status_code in (404, 410):

            return True, "No robots.txt file published."

        if response.status_code != 200:

            return (

                False,

                f"Robots check returned HTTP {response.status_code}.",

            )

        parser = RobotFileParser()

        parser.set_url(robots_url)

        parser.parse(response.text.splitlines())

        allowed = parser.can_fetch(

            USER_AGENT,

            url,

        )

        if not allowed:

            return False, "robots.txt disallows this page."

        return True, "robots.txt permits this page."

    except requests.RequestException as exc:

        return False, f"Robots check failed: {exc}"

# ============================================================

# PAGE RETRIEVAL

# ============================================================

def fetch_public_page(

    session: requests.Session,

    source: dict,

) -> dict:

    url = source["url"]

    original_host = normalize_hostname(url)

    allowed, robots_message = check_robots_permission(

        session,

        url,

    )

    if not allowed:

        raise PermissionError(robots_message)

    response = session.get(

        url,

        timeout=REQUEST_TIMEOUT,

        allow_redirects=True,

        stream=True,

        headers={

            "User-Agent": USER_AGENT,

            "Accept": "text/html,application/xhtml+xml",

        },

    )

    try:

        final_url = response.url

        if not host_is_allowed(final_url, original_host):

            raise PermissionError(

                "Redirect left the registered source domain."

            )

        response.raise_for_status()

        content_type = response.headers.get(

            "Content-Type",

            "",

        ).lower()

        if (

            "text/html" not in content_type

            and "application/xhtml+xml" not in content_type

        ):

            raise ValueError(

                f"Unsupported content type: {content_type}"

            )

        chunks = []

        total_bytes = 0

        for chunk in response.iter_content(

            chunk_size=16384,

        ):

            if not chunk:

                continue

            total_bytes += len(chunk)

            if total_bytes > MAX_RESPONSE_BYTES:

                raise ValueError(

                    "Page exceeded the configured size limit."

                )

            chunks.append(chunk)

        raw_content = b"".join(chunks)

        encoding = response.encoding or "utf-8"

        html = raw_content.decode(

            encoding,

            errors="replace",

        )

        page_text = extract_page_text(html)

        if not page_text:

            raise ValueError(

                "No readable page text was extracted."

            )

        fingerprint = hashlib.sha256(

            page_text.encode("utf-8")

        ).hexdigest()

        return {

            "final_url": final_url,

            "http_status": response.status_code,

            "content_type": content_type,

            "bytes_received": total_bytes,

            "fingerprint": fingerprint,

            "text_excerpt": page_text[:1500],

            "text_length": len(page_text),

            "robots_result": robots_message,

        }

    finally:

        response.close()

# ============================================================

# REVIEW QUEUE

# ============================================================

def create_change_record(

    source: dict,

    previous: Optional[dict],

    current: dict,

) -> dict:

    now = datetime.now(timezone.utc).isoformat()

    if previous is None:

        change_type = "new_source"

        old_fingerprint = None

        old_excerpt = None

    else:

        change_type = "content_changed"

        old_fingerprint = previous.get("fingerprint")

        old_excerpt = previous.get("text_excerpt")

    return {

        "change_id": hashlib.sha256(

            (

                source["source_id"]

                + current["fingerprint"]

                + now

            ).encode("utf-8")

        ).hexdigest()[:20],

        "source_id": source["source_id"],

        "source_name": source["name"],

        "category": source["category"],

        "state": source.get("state"),

        "source_url": source["url"],

        "detected_at": now,

        "change_type": change_type,

        "previous_fingerprint": old_fingerprint,

        "current_fingerprint": current["fingerprint"],

        "previous_excerpt": old_excerpt,

        "current_excerpt": current["text_excerpt"],

        "status": "pending_review",

        "reviewed_at": None,

        "reviewer_note": "",

    }

def add_pending_change(storage, change):

    queue = storage.get_review_queue()

    # Do not create duplicate pending records for the same

    # source and current fingerprint.

    for existing in queue:

        if (

            existing.get("source_id") == change["source_id"]

            and existing.get("current_fingerprint")

            == change["current_fingerprint"]

            and existing.get("status") == "pending_review"

        ):

            return False

    queue.append(change)

    storage.save_review_queue(queue)

    return True

def review_change(

    storage,

    change_id: str,

    decision: str,

    reviewer_note: str = "",

):

    """

    Mark a proposed change approved or rejected.

    Approval does not automatically edit the resource directory.

    A maintainer must separately verify and apply any actual update.

    """

    allowed_decisions = {

        "approved",

        "rejected",

    }

    if decision not in allowed_decisions:

        raise ValueError("Invalid review decision.")

    queue = storage.get_review_queue()

    found = False

    for record in queue:

        if record.get("change_id") == change_id:

            if record.get("status") != "pending_review":

                raise ValueError(

                    "This record has already been reviewed."

                )

            record["status"] = decision

            record["reviewed_at"] = (

                datetime.now(timezone.utc).isoformat()

            )

            record["reviewer_note"] = reviewer_note

            found = True

            break

    if not found:

        raise KeyError("Review record not found.")

    storage.save_review_queue(queue)

    storage.add_activity({

        "event": "review_completed",

        "change_id": change_id,

        "decision": decision,

        "timestamp": datetime.now(timezone.utc).isoformat(),

    })

    return True

# ============================================================

# CRAWL ENGINE

# ============================================================

def run_crawl(

    state_coalitions: dict,

    storage_dir=DEFAULT_STORAGE,

    delay_seconds=REQUEST_DELAY_SECONDS,

    selected_source_ids: Optional[list[str]] = None,

) -> dict:

    """

    Run one independent public-resource crawl.

    The caller supplies the existing state directory.

    No survivor records or private user data are accepted.

    """

    storage = CrawlerStorage(storage_dir)

    sources = build_source_registry(

        state_coalitions

    )

    if selected_source_ids is not None:

        selected = set(selected_source_ids)

        sources = [

            source

            for source in sources

            if source["source_id"] in selected

        ]

    snapshots = storage.get_snapshots()

    session = requests.Session()

    session.headers.update({

        "User-Agent": USER_AGENT,

    })

    results = []

    run_id = hashlib.sha256(

        datetime.now(timezone.utc).isoformat().encode("utf-8")

    ).hexdigest()[:16]

    started_at = datetime.now(timezone.utc).isoformat()

    try:

        for index, source in enumerate(sources):

            if index > 0:

                time.sleep(max(0, float(delay_seconds)))

            source_id = source["source_id"]

            result = {

                "source_id": source_id,

                "source_name": source["name"],

                "source_url": source["url"],

                "state": source.get("state"),

                "status": "not_checked",

                "message": "",

            }

            try:

                page = fetch_public_page(

                    session,

                    source,

                )

                previous = snapshots.get(source_id)

                snapshot = {

                    "source_id": source_id,

                    "source_name": source["name"],

                    "category": source["category"],

                    "state": source.get("state"),

                    "source_url": source["url"],

                    "final_url": page["final_url"],

                    "checked_at": (

                        datetime.now(timezone.utc).isoformat()

                    ),

                    "fingerprint": page["fingerprint"],

                    "text_excerpt": page["text_excerpt"],

                    "text_length": page["text_length"],

                    "http_status": page["http_status"],

                    "bytes_received": page["bytes_received"],

                }

                if previous is None:

                    change = create_change_record(

                        source,

                        None,

                        snapshot,

                    )

                    added = add_pending_change(

                        storage,

                        change,

                    )

                    result["status"] = "new_source"

                    result["message"] = (

                        "First snapshot recorded. "

                        "Initial review item created."

                        if added

                        else "Initial snapshot already has a review item."

                    )

                elif (

                    previous.get("fingerprint")

                    != page["fingerprint"]

                ):

                    change = create_change_record(

                        source,

                        previous,

                        snapshot,

                    )

                    added = add_pending_change(

                        storage,

                        change,

                    )

                    result["status"] = "changed"

                    result["message"] = (

                        "Page content changed. "

                        "Review item created."

                        if added

                        else "A matching pending review already exists."

                    )

                else:

                    result["status"] = "unchanged"

                    result["message"] = (

                        "No text-content change detected."

                    )

                # Store the newest observation separately from

                # the human approval state.

                snapshots[source_id] = snapshot

                result["fingerprint"] = page["fingerprint"]

                result["checked_at"] = snapshot["checked_at"]

            except Exception as exc:

                LOGGER.warning(

                    "Source check failed for %s: %s",

                    source_id,

                    exc,

                )

                result["status"] = "error"

                result["message"] = str(exc)

            results.append(result)

            storage.add_activity({

                "event": "source_checked",

                "run_id": run_id,

                "source_id": source_id,

                "status": result["status"],

                "timestamp": (

                    datetime.now(timezone.utc).isoformat()

                ),

            })

    finally:

        session.close()

    storage.save_snapshots(snapshots)

    finished_at = datetime.now(timezone.utc).isoformat()

    summary = {

        "run_id": run_id,

        "crawler_version": CRAWLER_VERSION,

        "started_at": started_at,

        "finished_at": finished_at,

        "sources_attempted": len(results),

        "successful": sum(

            1 for item in results

            if item["status"] in (

                "new_source",

                "changed",

                "unchanged",

            )

        ),

        "changed": sum(

            1 for item in results

            if item["status"] == "changed"

        ),

        "new_sources": sum(

            1 for item in results

            if item["status"] == "new_source"

        ),

        "errors": sum(

            1 for item in results

            if item["status"] == "error"

        ),

        "results": results,

    }

    storage.add_activity({

        "event": "crawl_completed",

        "run_id": run_id,

        "summary": {

            key: summary[key]

            for key in (

                "sources_attempted",

                "successful",

                "changed",

                "new_sources",

                "errors",

            )

        },

        "timestamp": finished_at,

    })

    return summary

# ============================================================

# REVIEW AND STATUS HELPERS

# ============================================================

def get_pending_reviews(

    storage_dir=DEFAULT_STORAGE,

) -> list[dict]:

    storage = CrawlerStorage(storage_dir)

    return [

        item

        for item in storage.get_review_queue()

        if item.get("status") == "pending_review"

    ]

def get_all_reviews(

    storage_dir=DEFAULT_STORAGE,

) -> list[dict]:

    storage = CrawlerStorage(storage_dir)

    return storage.get_review_queue()

def get_crawler_status(

    storage_dir=DEFAULT_STORAGE,

) -> dict:

    storage = CrawlerStorage(storage_dir)

    snapshots = storage.get_snapshots()

    queue = storage.get_review_queue()

    activity = storage.get_activity()

    return {

        "crawler_version": CRAWLER_VERSION,

        "sources_with_snapshots": len(snapshots),

        "pending_reviews": sum(

            1 for item in queue

            if item.get("status") == "pending_review"

        ),

        "approved_reviews": sum(

            1 for item in queue

            if item.get("status") == "approved"

        ),

        "rejected_reviews": sum(

            1 for item in queue

            if item.get("status") == "rejected"

        ),

        "last_activity": (

            activity[-1] if activity else None

        ),

    }

def export_review_queue(

    storage_dir=DEFAULT_STORAGE,

) -> dict:

    return {

        "application": "Survivors Network",

        "crawler_version": CRAWLER_VERSION,

        "exported_at": datetime.now(

            timezone.utc

        ).isoformat(),

        "records": get_all_reviews(storage_dir),

    }

# ============================================================

# COMMAND-LINE SELF TEST

# ============================================================

def self_test():

    """

    Test local storage, text extraction, fingerprinting,

    and review-state transitions without contacting websites.

    """

    import tempfile

    test_html = """

    <html>

      <head><title>Test</title></head>

      <body>

        <h1>Public Resource Directory</h1>

        <p>Contact information updated.</p>

        <script>private_script_data()</script>

      </body>

    </html>

    """

    extracted = extract_page_text(test_html)

    assert "Public Resource Directory" in extracted

    assert "private_script_data" not in extracted

    fingerprint = hashlib.sha256(

        extracted.encode("utf-8")

    ).hexdigest()

    assert len(fingerprint) == 64

    with tempfile.TemporaryDirectory() as temporary:

        storage = CrawlerStorage(temporary)

        change = {

            "change_id": "test123",

            "source_id": "test_source",

            "current_fingerprint": fingerprint,

            "status": "pending_review",

        }

        storage.save_review_queue([change])

        review_change(

            storage,

            "test123",

            "approved",

            "Local self-test approval.",

        )

        records = storage.get_review_queue()

        assert records[0]["status"] == "approved"

    print("Survivors Network crawler self-test passed.")

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(

        description="Survivors Network resource crawler"

    )

    parser.add_argument(

        "--self-test",

        action="store_true",

        help="Run offline tests without contacting websites.",

    )

    args = parser.parse_args()

    if args.self_test:

        self_test()

    else:

        print(

            "This module is called by survivors-network.py. "

            "Use --self-test for an offline test."

        )
