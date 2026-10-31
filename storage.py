import sqlite3
import json
import uuid

from pathlib import Path
from datetime import datetime, timezone

from security import VaultSecurity


class VaultError(Exception):
    pass


class LocalVault:

    def __init__(self, database_path, key):

        self.database_path = Path(database_path)
        self.key = key

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.initialize()

    def connect(self):

        return sqlite3.connect(
            self.database_path,
            timeout=10
        )

    def initialize(self):

        with self.connect() as db:

            db.execute("""
                CREATE TABLE IF NOT EXISTS records (

                    record_id TEXT PRIMARY KEY,

                    encrypted_payload BLOB NOT NULL,

                    created_at TEXT NOT NULL

                )
            """)

            db.execute("""
                CREATE TABLE IF NOT EXISTS vault_metadata (

                    metadata_key TEXT PRIMARY KEY,

                    encrypted_value BLOB NOT NULL

                )
            """)

            db.commit()

    def initialize_vault(self):

        with self.connect() as db:

            row = db.execute(
                "SELECT metadata_key FROM vault_metadata "
                "WHERE metadata_key = 'verifier'"
            ).fetchone()

            if row:
                return False

            verifier = VaultSecurity.encrypt(
                b"SURVIVORS_NETWORK_VAULT_OK",
                self.key,
                b"vault-verifier"
            )

            db.execute(
                """
                INSERT INTO vault_metadata
                (metadata_key, encrypted_value)
                VALUES (?, ?)
                """,
                ("verifier", verifier)
            )

            db.commit()

        return True

    def verify_key(self):

        with self.connect() as db:

            row = db.execute(
                """
                SELECT encrypted_value
                FROM vault_metadata
                WHERE metadata_key = ?
                """,
                ("verifier",)
            ).fetchone()

        if not row:
            return False

        try:

            result = VaultSecurity.decrypt(
                row[0],
                self.key,
                b"vault-verifier"
            )

            return result == b"SURVIVORS_NETWORK_VAULT_OK"

        except Exception:
            return False

    def add_record(
        self,
        title,
        category,
        content
    ):

        record_id = str(uuid.uuid4())

        created_at = datetime.now(
            timezone.utc
        ).isoformat()

        payload = json.dumps({
            "title": title,
            "category": category,
            "content": content,
            "created_at": created_at
        }).encode("utf-8")

        encrypted = VaultSecurity.encrypt(
            payload,
            self.key,
            record_id.encode("utf-8")
        )

        with self.connect() as db:

            db.execute(
                """
                INSERT INTO records
                (record_id, encrypted_payload, created_at)
                VALUES (?, ?, ?)
                """,
                (
                    record_id,
                    encrypted,
                    created_at
                )
            )

            db.commit()

        return record_id

    def list_records(self):

        with self.connect() as db:

            rows = db.execute(
                """
                SELECT record_id, encrypted_payload
                FROM records
                ORDER BY created_at DESC
                """
            ).fetchall()

        results = []

        for record_id, encrypted in rows:

            try:

                raw = VaultSecurity.decrypt(
                    encrypted,
                    self.key,
                    record_id.encode("utf-8")
                )

                record = json.loads(raw.decode("utf-8"))

                results.append({
                    "id": record_id,
                    "title": record["title"],
                    "category": record["category"],
                    "created_at": record["created_at"]
                })

            except Exception:
                continue

        return results

    def read_record(self, record_id):

        with self.connect() as db:

            row = db.execute(
                """
                SELECT encrypted_payload
                FROM records
                WHERE record_id = ?
                """,
                (record_id,)
            ).fetchone()

        if row is None:
            raise VaultError("Record not found.")

        raw = VaultSecurity.decrypt(
            row[0],
            self.key,
            record_id.encode("utf-8")
        )

        return json.loads(raw.decode("utf-8"))

    def delete_record(self, record_id):

        with self.connect() as db:

            db.execute(
                "DELETE FROM records WHERE record_id = ?",
                (record_id,)
            )

            db.commit()

    def record_count(self):

        with self.connect() as db:

            result = db.execute(
                "SELECT COUNT(*) FROM records"
            ).fetchone()

        return result[0]
