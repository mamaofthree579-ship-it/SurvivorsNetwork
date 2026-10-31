
"""
Survivors Network — Resource Maintenance Orchestrator
Author: Hope Jones

Coordinates the existing:
    resource_crawler.py
    directory_updates.py
    State Resource Directory module

This script is intended to run locally or through GitHub Actions.
It does not import or launch the Streamlit application.

The eight directory bots remain responsible for validating and
scoring proposed directory changes. Low-confidence or conflicting
changes remain in the exception/review records.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "resource_crawler_data"
DIRECTORY_FILE = DATA_DIR / "state_resource_directory.json"

CRAWLER_MODULE = ROOT / "resource_crawler.py"
UPDATER_MODULE = ROOT / "directory_updates.py"

EXCLUDED_MODULES = {
    "survivors_network.py",
    "resource_crawler.py",
    "directory_updates.py",
    "resource_update.py",
}


def load_module(path: Path, module_name: str):
    """Load an existing Python module from an exact file path."""
    if not path.is_file():
        raise FileNotFoundError(f"Required module not found: {path.name}")

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module: {path.name}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def find_state_directory_module():
    """
    Find the supplied state-directory data module without assuming
    its filename.

    The module must expose both existing functions:
        export_directory()
        get_all_state_records()

    The Streamlit application is deliberately excluded.
    """
    candidates = []

    for path in ROOT.glob("*.py"):
        if path.name in EXCLUDED_MODULES:
            continue

        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue

        if (
            "def export_directory" in source
            and "def get_all_state_records" in source
        ):
            candidates.append(path)

    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise RuntimeError(
            "More than one state-directory module was found: "
            f"{names}. Keep only the intended directory data module "
            "or configure the runner to select it explicitly."
        )

    if not candidates:
        return None

    return load_module(candidates[0], "survivors_state_directory")


def load_saved_directory():
    """Load an existing directory file when the data module is absent."""
    if not DIRECTORY_FILE.is_file():
        return None

    try:
        with DIRECTORY_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Could not read {DIRECTORY_FILE}: {exc}"
        ) from exc


def normalize_state_records(directory_data: Any) -> list[dict]:
    """
    Accept the state module's exported structure or a saved state
    mapping, and return a normalized list of state records.
    """
    if isinstance(directory_data, dict) and isinstance(
        directory_data.get("states"), list
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
        raise ValueError("The state directory has an unsupported format.")

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
    Prefer the supplied Python data module. Fall back to the
    previously saved directory file when necessary.
    """
    module = find_state_directory_module()

    if module is not None:
        exported = module.export_directory()
        records = normalize_state_records(exported)

        # Preserve the original exported state information for the
        # directory updater, keyed by the full state name.
        current_directory = {
            record["state"]: dict(record)
            for record in records
        }

        return records, current_directory

    saved = load_saved_directory()

    if saved is not None:
        records = normalize_state_records(saved)

        if isinstance(saved, dict) and isinstance(saved.get("states"), list):
            current_directory = {
                record["state"]: dict(record)
                for record in records
            }
        else:
            current_directory = {
                record["state"]: dict(record)
                for record in records
            }

        return records, current_directory

    raise FileNotFoundError(
        "Could not locate the state-directory module or an existing "
        "state_resource_directory.json. The runner will not invent "
        "or replace the 50-state resource data."
    )


def build_crawler_state_data(records: list[dict]) -> dict:
    """
    Convert the state module's full-state-name records into the
    abbreviation-keyed format expected by resource_crawler.py.

    The crawler expects:
        {
            "WV": {
                "name": "West Virginia",
                "abbr": "WV",
                "url": "https://..."
            }
        }
    """
    crawler_states = {}

    for record in records:
        code = record["code"]

        crawler_states[code] = {
            "name": record["state"],
            "abbr": code,
            "url": record.get("website", ""),
        }

    return crawler_states


def write_json_atomic(path: Path, data: Any):
    """Write JSON without leaving a partially written file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(path.suffix + ".tmp")

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")

    temporary.replace(path)


def run_resource_maintenance():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading the existing 50-state resource directory...")
    state_records, current_directory = load_state_directory()

    print(f"Loaded {len(state_records)} state records.")

    crawler_states = build_crawler_state_data(state_records)

    print("Loading the existing public resource crawler...")
    crawler = load_module(CRAWLER_MODULE, "survivors_resource_crawler")

    print("Starting public resource website checks...")
    crawl_result = crawler.run_crawl(
        state_coalitions=crawler_states,
        include_national=True,
        storage_dir=str(DATA_DIR),
    )

    print("Public resource crawl completed.")
    print(f"Crawler result: {crawl_result}")

    print("Loading the existing eight-bot directory updater...")
    updater = load_module(UPDATER_MODULE, "survivors_directory_updates")

    print("Passing collected public-source data to the eight bots...")
    update_result = updater.run_automated_updates(
        current_directory=current_directory,
        storage_dir=str(DATA_DIR),
        auto_apply=True,
    )

    print("Directory intelligence run completed.")
    print(f"Updater result: {update_result}")

    report = {
        "application": "Survivors Network",
        "orchestrator": "resource_update.py",
        "state_count": len(state_records),
        "crawler_result": crawl_result,
        "directory_update_result": update_result,
    }

    write_json_atomic(
        DATA_DIR / "resource_maintenance_report.json",
        report,
    )

    print("Resource maintenance process finished.")
    return report


if __name__ == "__main__":
    try:
        run_resource_maintenance()
    except Exception as exc:
        print(f"RESOURCE MAINTENANCE FAILED: {exc}", file=sys.stderr)
        raise
