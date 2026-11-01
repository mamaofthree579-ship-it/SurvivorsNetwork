from pathlib import Path
import ast
import json
import sys

# Ensure the repository root is importable when pytest collects this file
# from a tests/ directory or from a copied update bundle.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import directory_updates
import resource_crawler


def test_updater_reads_crawlers_combined_snapshot_file(tmp_path, monkeypatch):
    data_dir = tmp_path / "resource_crawler_data"
    data_dir.mkdir()
    monkeypatch.setattr(directory_updates, "DATA_DIR", data_dir)
    monkeypatch.setattr(directory_updates, "SNAPSHOT_DIR", data_dir / "snapshots")
    monkeypatch.setattr(directory_updates, "PENDING_REVIEW_FILE", data_dir / "pending_reviews.json")

    (data_dir / "snapshots.json").write_text(json.dumps({
        "source-1": {
            "source_id": "source-1",
            "url": "https://example.org/",
            "fetched_at": "2026-11-01T10:00:00+00:00",
            "excerpt": "Public resource information",
        }
    }))

    snapshots = directory_updates.load_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0]["source_id"] == "source-1"
    assert snapshots[0]["_snapshot_file"] == "snapshots.json"


def test_robots_cache_applies_path_rules_per_url(monkeypatch):
    class FakeResponse:
        status_code = 200

        def iter_content(self, chunk_size=8192):
            yield b"User-agent: *\nDisallow: /private\n"

        def close(self):
            pass

    class FakeSession:
        calls = 0

        def get(self, *args, **kwargs):
            self.calls += 1
            return FakeResponse()

    monkeypatch.setattr(resource_crawler, "resolve_public_host", lambda host: True)
    session = FakeSession()
    cache = resource_crawler.RobotsPolicyCache()

    allowed_public, _ = cache.get("https://example.org/public", session)
    allowed_private, _ = cache.get("https://example.org/private/secret", session)
    assert allowed_public is True
    assert allowed_private is False
    assert session.calls == 1


def test_failed_review_persistence_does_not_advance_snapshots(monkeypatch):
    class FakeSession:
        def close(self):
            pass

    class FakeStorage:
        def __init__(self, directory=None):
            self.snapshot_save_called = False

        def get_snapshots(self):
            return {"source-1": {"fingerprint": "old"}}

        def get_reviews(self):
            return []

        def save_reviews(self, reviews):
            return False

        def save_snapshots(self, snapshots):
            self.snapshot_save_called = True
            return True

        def log_activity(self, *args, **kwargs):
            return True

    storage = FakeStorage()
    monkeypatch.setattr(resource_crawler, "CrawlerStorage", lambda directory=None: storage)
    monkeypatch.setattr(resource_crawler, "build_source_registry", lambda **kwargs: [{
        "source_id": "source-1", "name": "Example", "category": "Test",
        "state": "West Virginia", "state_code": "WV", "url": "https://example.org/",
    }])
    monkeypatch.setattr(resource_crawler, "create_session", lambda: FakeSession())
    monkeypatch.setattr(resource_crawler, "check_robots_permission", lambda *a, **k: (True, "allowed"))
    monkeypatch.setattr(resource_crawler, "fetch_public_page", lambda *a, **k: {
        "success": True, "text": "Updated public service information",
        "url": "https://example.org/", "fetched_at": "2026-11-01T10:00:00+00:00",
        "bytes_received": 100,
    })
    monkeypatch.setattr(resource_crawler, "create_change_record", lambda *a, **k: {
        "review_id": "review-1", "status": "pending",
    })

    result = resource_crawler.run_crawl(
        state_coalitions={}, include_national=False, storage_dir="unused"
    )

    assert result["reviews_saved"] is False
    assert result["snapshots_saved"] is False
    assert storage.snapshot_save_called is False


def test_streamlit_page_config_is_first_streamlit_command():
    source = Path("survivors_network.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    first_streamlit_call = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "st":
                position = (node.lineno, node.col_offset)
                if first_streamlit_call is None or position < first_streamlit_call[0]:
                    first_streamlit_call = (position, node.func.attr)
    assert first_streamlit_call is not None
    assert first_streamlit_call[1] == "set_page_config"


def test_app_test_form_uses_defined_evidence_notes_and_location_opt_in():
    source = Path("survivors_network.py").read_text(encoding="utf-8")
    assert 'include_location = st.checkbox(' in source
    assert '"notes": evidence_notes.strip()' in source
    assert '"notes": notes.strip()' not in source
    assert 'user_key = st.text_input(' not in source


def test_app_directory_migration_preserves_existing_state_records(tmp_path):
    source = Path("survivors_network.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    seed_node = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "STATE_DIRECTORY_SEED"
                for target in node.targets)
    )
    initializer_node = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "initialize_directory"
    )

    seed_namespace = {}
    exec(
        compile(ast.Module(body=[seed_node], type_ignores=[]), "survivors_network.py", "exec"),
        seed_namespace,
    )
    seed = seed_namespace["STATE_DIRECTORY_SEED"]
    original = {
        value["name"]: {
            "code": code,
            "name": value.get("coalition", value["name"]),
            "website": value.get("url", ""),
        }
        for code, value in seed.items()
    }
    original["West Virginia"]["resources"] = [{
        "resource_id": "preserve-me",
        "name": "Existing local resource",
        "website": "https://example.org/",
    }]
    canonical = tmp_path / "state_resource_directory.json"
    canonical.write_text(json.dumps(original), encoding="utf-8")

    namespace = {
        "Path": Path,
        "json": json,
        "STATE_DIRECTORY_SEED": seed,
        "DIRECTORY_FILE": canonical,
        "LEGACY_DIRECTORY_FILE": tmp_path / "legacy" / "state_resource_directory.json",
    }
    exec(compile(ast.Module(body=[initializer_node], type_ignores=[]), "survivors_network.py", "exec"), namespace)

    converted = namespace["initialize_directory"]()
    assert len(converted) == 50
    assert converted["WV"]["name"] == "West Virginia"
    assert converted["WV"]["coalition"] == original["West Virginia"]["name"]
    assert converted["WV"]["resources"][0]["resource_id"] == "preserve-me"
    assert namespace["initialize_directory"]() == converted


def test_automated_updater_uses_and_persists_canonical_directory(tmp_path, monkeypatch):
    data_dir = tmp_path / "resource_crawler_data"
    directory_file = tmp_path / "state_resource_directory.json"
    directory_file.write_text(json.dumps({
        "WV": {"code": "WV", "name": "West Virginia", "resources": []}
    }), encoding="utf-8")

    path_values = {
        "ROOT_DIR": tmp_path,
        "DATA_DIR": data_dir,
        "DIRECTORY_FILE": directory_file,
        "LEGACY_DIRECTORY_FILE": data_dir / "state_resource_directory.json",
        "SNAPSHOT_DIR": data_dir / "snapshots",
        "PENDING_REVIEW_FILE": data_dir / "pending_reviews.json",
        "CANDIDATES_FILE": data_dir / "directory_candidates.json",
        "EXCEPTIONS_FILE": data_dir / "directory_exceptions.json",
        "HISTORY_FILE": data_dir / "directory_history.json",
        "REPORT_FILE": data_dir / "directory_update_report.json",
        "ACTIVITY_FILE": data_dir / "directory_activity.json",
        "BACKUP_DIR": data_dir / "directory_backups",
    }
    for name, value in path_values.items():
        monkeypatch.setattr(directory_updates, name, value)

    result = directory_updates.run_automated_updates(
        current_directory=None,
        auto_apply=True,
    )
    saved = json.loads(directory_file.read_text(encoding="utf-8"))

    assert result["status"] == "completed"
    assert result["updated_directory"] == saved
    assert result["private_data_accessed"] is False
