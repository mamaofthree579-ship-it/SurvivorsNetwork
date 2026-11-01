
"""
Survivors Network — Resource Maintenance Orchestrator
Author: Hope Jones

Coordinates the existing:
    resource_directory.py
    resource_crawler.py
    directory_updates.py

Designed for local execution and GitHub Actions.

This script:
    1. Loads the existing 50-state directory.
    2. Converts state records into the crawler's expected format.
    3. Runs the public resource crawler.
    4. Runs the existing eight-bot directory updater.
    5. Saves a maintenance report.

It does not import or launch the Streamlit application.
It does not crawl participant devices or private information.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# PATHS AND CONFIGURATION
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parent

DATA_DIR = ROOT / "resource_crawler_data"

DIRECTORY_FILE = ROOT / "state_resource_directory.json"

STATE_MODULE_FILE = ROOT / "resource_directory.py"

CRAWLER_MODULE_FILE = ROOT / "resource_crawler.py"

UPDATER_MODULE_FILE = ROOT / "directory_updates.py"


# ---------------------------------------------------------
# MODULE LOADING
# ---------------------------------------------------------

def load_module(path: Path, module_name: str):
    """
    Load an existing Python module from an explicit file path.
    """

    if not path.is_file():
        raise FileNotFoundError(
            f"Required module not found: {path}"
        )

    spec = importlib.util.spec_from_file_location(
        module_name,
        path
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Could not load module: {path.name}"
        )

    module = importlib.util.module_from_spec(spec)

    sys.modules[module_name] = module

    spec.loader.exec_module(module)

    return module


def find_state_directory_module():
    """
    Explicitly load resource_directory.py.

    This avoids scanning the repository and accidentally
    identifying the Streamlit application as a data module.
    """

    if not STATE_MODULE_FILE.is_file():
        raise FileNotFoundError(
            "The state directory module was not found: "
            f"{STATE_MODULE_FILE.name}"
        )

    module = load_module(
        STATE_MODULE_FILE,
        "survivors_state_directory"
    )

    required_functions = (
        "export_directory",
        "get_all_state_records",
    )

    for function_name in required_functions:

        if not callable(
            getattr(module, function_name, None)
        ):
            raise AttributeError(
                f"{STATE_MODULE_FILE.name} is missing "
                f"required function: {function_name}"
            )

    return module


# ---------------------------------------------------------
# DIRECTORY LOADING
# ---------------------------------------------------------

def load_saved_directory():
    """
    Load the previously saved directory if available.
    """

    if not DIRECTORY_FILE.is_file():
        return None

    try:

        with DIRECTORY_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except (OSError, json.JSONDecodeError) as exc:

        raise RuntimeError(
            f"Could not read {DIRECTORY_FILE}: {exc}"
        ) from exc


def normalize_state_records(
    directory_data: Any
) -> list[dict]:
    """
    Normalize the supplied state directory records.

    Supports:
        - export_directory() output
        - A list of state records
        - A dictionary keyed by state name
    """

    if (
        isinstance(directory_data, dict)
        and isinstance(directory_data.get("states"), list)
    ):

        records = directory_data["states"]

    elif isinstance(directory_data, dict):

        records = []

        for state_name, value in directory_data.items():

            if not isinstance(value, dict):
                continue

            record = dict(value)

            record.setdefault("state", state_name)

            records.append(record)

    elif isinstance(directory_data, list):

        records = directory_data

    else:

        raise ValueError(
            "The state directory has an unsupported format."
        )

    normalized = []

    for original in records:

        if not isinstance(original, dict):
            continue

        record = dict(original)

        state_name = (
            record.get("state")
            or record.get("state_name")
            or record.get("name")
        )

        state_code = (
            record.get("code")
            or record.get("abbr")
            or record.get("abbreviation")
        )

        website = (
            record.get("website")
            or record.get("url")
            or record.get("website_url")
        )

        if not state_name or not state_code:
            continue

        record["state"] = str(state_name)

        record["code"] = str(state_code).upper()

        record["website"] = website or ""

        normalized.append(record)

    if len(normalized) != 50:

        raise RuntimeError(
            "The state directory must contain all 50 states. "
            f"Found {len(normalized)} usable state records. "
            "No crawl or directory update was started."
        )

    return normalized


def load_state_directory():
    """
    Prefer the existing Python state-directory module.

    Fall back to the saved JSON directory only if the
    Python module is unavailable.
    """

    try:

        module = find_state_directory_module()

        exported = module.export_directory()

        records = normalize_state_records(exported)

        current_directory = {
            record["state"]: dict(record)
            for record in records
        }

        return records, current_directory

    except FileNotFoundError:

        saved = load_saved_directory()

        if saved is None:
            raise

        records = normalize_state_records(saved)

        current_directory = {
            record["state"]: dict(record)
            for record in records
        }

        return records, current_directory


# ---------------------------------------------------------
# CRAWLER DATA CONVERSION
# ---------------------------------------------------------

def build_crawler_state_data(
    records: list[dict]
) -> dict:
    """
    Convert the full-state-name directory records into the
    abbreviation-keyed format expected by resource_crawler.py.

    Expected crawler structure:

        {
            "WV": {
                "name": "West Virginia",
                "abbr": "WV",
                "url": "https://example.org"
            }
        }

    The original directory records remain unchanged.
    """

    crawler_states = {}

    for record in records:

        code = record["code"]

        coalition_name = (
            record.get("coalition")
            or record.get("coalition_name")
            or record.get("name")
            or record["state"]
        )
        crawler_states[code] = {
            "name": coalition_name,
            "coalition": coalition_name,
            "state_name": record["state"],
            "abbr": code,
            "url": record.get("website", ""),
        }

    return crawler_states


# ---------------------------------------------------------
# JSON STORAGE
# ---------------------------------------------------------

def write_json_atomic(
    path: Path,
    data: Any
):
    """
    Write JSON atomically to avoid partially written files.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    with temporary.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
            default=str
        )

        file.write("\n")

    temporary.replace(path)


def make_report_value(value: Any):
    """
    Convert a result into JSON-compatible data.
    """

    try:

        json.dumps(value)

        return value

    except (TypeError, ValueError):

        return str(value)


# ---------------------------------------------------------
# RESOURCE MAINTENANCE
# ---------------------------------------------------------

def run_resource_maintenance():

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print(
        "Loading the existing 50-state resource directory..."
    )

    state_records, _ = load_state_directory()

    print(
        f"Loaded {len(state_records)} state records."
    )

    crawler_states = build_crawler_state_data(
        state_records
    )

    print(
        "Loading the existing public resource crawler..."
    )

    crawler = load_module(
        CRAWLER_MODULE_FILE,
        "survivors_resource_crawler"
    )

    if not callable(
        getattr(crawler, "run_crawl", None)
    ):

        raise AttributeError(
            "resource_crawler.py does not expose run_crawl()."
        )

    print(
        "Starting public resource website checks..."
    )

    crawl_result = crawler.run_crawl(
        state_coalitions=crawler_states,
        include_national=True,
        storage_dir=str(DATA_DIR),
    )

    print(
        "Public resource crawl completed."
    )

    print(
        "Loading the existing eight-bot directory updater..."
    )

    updater = load_module(
        UPDATER_MODULE_FILE,
        "survivors_directory_updates"
    )

    if not callable(
        getattr(updater, "run_automated_updates", None)
    ):

        raise AttributeError(
            "directory_updates.py does not expose "
            "run_automated_updates()."
        )

    print(
        "Passing collected public-source data to the eight bots..."
    )

    # Let the updater load and persist the canonical repository-root
    # directory. Passing an in-memory copy would intentionally prevent
    # persistence and make scheduled updates disappear after the job.
    update_result = updater.run_automated_updates(
        current_directory=None,
        auto_apply=True,
    )

    print(
        "Directory intelligence run completed."
    )

    # -----------------------------------------------------
    # MAINTENANCE REPORT
    # -----------------------------------------------------

    report = {
        "application": "Survivors Network",
        "author": "Hope Jones",
        "orchestrator": "resource_update.py",
        "state_count": len(state_records),
        "crawler_result": make_report_value(
            crawl_result
        ),
        "directory_update_result": make_report_value(
            update_result
        ),
    }

    report_file = (
        DATA_DIR / "resource_maintenance_report.json"
    )

    write_json_atomic(
        report_file,
        report
    )

    print(
        "Resource maintenance report saved."
    )

    print(
        "Resource maintenance process finished."
    )

    return report


# ---------------------------------------------------------
# COMMAND-LINE ENTRY POINT
# ---------------------------------------------------------

if __name__ == "__main__":

    try:

        run_resource_maintenance()

    except Exception as exc:

        print(
            f"RESOURCE MAINTENANCE FAILED: {exc}",
            file=sys.stderr
        )

        raise
