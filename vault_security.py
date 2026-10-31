
import os
import stat
from pathlib import Path

from argon2.low_level import Type, hash_secret_raw
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import HKDF


class SecurityError(Exception):
    pass


class VaultSecurity:

    KEY_LENGTH = 32
    SALT_LENGTH = 16
    NONCE_LENGTH = 12
    TAG_LENGTH = 16

    FORMAT_HEADER = b"SNV1"

    TIME_COST = 3
    MEMORY_COST = 65536
    PARALLELISM = 2

    MAX_PASSPHRASE_LENGTH = 4096

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    @staticmethod
    def _validate_bytes(value, field_name):
        if not isinstance(value, bytes):
            raise SecurityError(
                f"{field_name} must be bytes."
            )

    @staticmethod
    def _validate_key(key):
        VaultSecurity._validate_bytes(key, "Encryption key")

        if len(key) != VaultSecurity.KEY_LENGTH:
            raise SecurityError("Invalid encryption key.")

    @staticmethod
    def _validate_associated_data(associated_data):
        VaultSecurity._validate_bytes(
            associated_data,
            "Associated data"
        )

    # ---------------------------------------------------------
    # SALT MANAGEMENT
    # ---------------------------------------------------------

    @staticmethod
    def get_salt(salt_path):

        path = Path(salt_path)
        path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if path.is_symlink():
            raise SecurityError(
                "Vault salt cannot be a symbolic link."
            )

        if path.exists():
            if not path.is_file():
                raise SecurityError(
                    "Vault salt path is not a regular file."
                )

            salt = path.read_bytes()

            if len(salt) != VaultSecurity.SALT_LENGTH:
                raise SecurityError(
                    "Invalid vault salt."
                )

            # Best-effort restriction of existing file permissions.
            if os.name == "posix":
                os.chmod(path, 0o600)

            return salt

        salt = os.urandom(
            VaultSecurity.SALT_LENGTH
        )

        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
        )

        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW

        try:
            fd = os.open(
                str(path),
                flags,
                0o600
            )

            with os.fdopen(fd, "wb") as file:
                file.write(salt)
                file.flush()
                os.fsync(file.fileno())

            return salt

        except FileExistsError:
            # Another process may have created the salt
            # between the existence check and file creation.
            if path.is_symlink() or not path.is_file():
                raise SecurityError(
                    "Unsafe vault salt file."
                )

            existing = path.read_bytes()

            if len(existing) != VaultSecurity.SALT_LENGTH:
                raise SecurityError(
                    "Invalid vault salt."
                )

            return existing

        except OSError as exc:
            raise SecurityError(
                "Unable to create vault salt."
            ) from exc

    # ---------------------------------------------------------
    # MASTER KEY DERIVATION
    # ---------------------------------------------------------

    @staticmethod
    def derive_key(passphrase, salt):

        if not isinstance(passphrase, str):
            raise SecurityError(
                "Invalid passphrase."
            )

        if not 12 <= len(passphrase) <= VaultSecurity.MAX_PASSPHRASE_LENGTH:
            raise SecurityError(
                "Passphrase must contain at least 12 characters."
            )

        VaultSecurity._validate_bytes(
            salt,
            "Salt"
        )

        if len(salt) != VaultSecurity.SALT_LENGTH:
            raise SecurityError(
                "Invalid salt length."
            )

        try:
            return hash_secret_raw(
                secret=passphrase.encode("utf-8"),
                salt=salt,
                time_cost=VaultSecurity.TIME_COST,
                memory_cost=VaultSecurity.MEMORY_COST,
                parallelism=VaultSecurity.PARALLELISM,
                hash_len=VaultSecurity.KEY_LENGTH,
                type=Type.ID
            )

        except Exception as exc:
            raise SecurityError(
                "Key derivation failed."
            ) from exc

    # ---------------------------------------------------------
    # PURPOSE-SPECIFIC SUBKEY DERIVATION
    # ---------------------------------------------------------

    @staticmethod
    def derive_subkey(master_key, purpose, context=b""):

        VaultSecurity._validate_key(master_key)

        if not isinstance(purpose, str) or not purpose:
            raise SecurityError(
                "A valid key purpose is required."
            )

        if len(purpose) > 128:
            raise SecurityError(
                "Key purpose is too long."
            )

        VaultSecurity._validate_bytes(
            context,
            "Key context"
        )

        info = (
            b"SurvivorsNetwork/"
            + purpose.encode("utf-8")
            + b"/v1/"
            + context
        )

        try:
            return HKDF(
                master_key,
                VaultSecurity.KEY_LENGTH,
                b"SN-HKDF-v1",
                SHA256,
                context=info
            )

        except Exception as exc:
            raise SecurityError(
                "Subkey derivation failed."
            ) from exc

    # ---------------------------------------------------------
    # AES-256-GCM ENCRYPTION
    # ---------------------------------------------------------

    @staticmethod
    def encrypt(data, key, associated_data=b""):

        VaultSecurity._validate_bytes(
            data,
            "Plaintext"
        )

        VaultSecurity._validate_key(key)

        VaultSecurity._validate_associated_data(
            associated_data
        )

        nonce = os.urandom(
            VaultSecurity.NONCE_LENGTH
        )

        try:
            cipher = AES.new(
                key,
                AES.MODE_GCM,
                nonce=nonce,
                mac_len=VaultSecurity.TAG_LENGTH
            )

            cipher.update(associated_data)

            ciphertext, tag = cipher.encrypt_and_digest(
                data
            )

            return (
                VaultSecurity.FORMAT_HEADER
                + nonce
                + tag
                + ciphertext
            )

        except Exception as exc:
            raise SecurityError(
                "Encryption failed."
            ) from exc

    # ---------------------------------------------------------
    # AES-256-GCM DECRYPTION
    # ---------------------------------------------------------

    @staticmethod
    def decrypt(blob, key, associated_data=b""):

        VaultSecurity._validate_bytes(
            blob,
            "Encrypted data"
        )

        VaultSecurity._validate_key(key)

        VaultSecurity._validate_associated_data(
            associated_data
        )

        minimum_length = (
            len(VaultSecurity.FORMAT_HEADER)
            + VaultSecurity.NONCE_LENGTH
            + VaultSecurity.TAG_LENGTH
        )

        if len(blob) < minimum_length:
            raise SecurityError(
                "Encrypted data is incomplete."
            )

        if not blob.startswith(
            VaultSecurity.FORMAT_HEADER
        ):
            raise SecurityError(
                "Unknown encrypted data format."
            )

        offset = len(VaultSecurity.FORMAT_HEADER)

        nonce = blob[
            offset:offset + VaultSecurity.NONCE_LENGTH
        ]

        offset += VaultSecurity.NONCE_LENGTH

        tag = blob[
            offset:offset + VaultSecurity.TAG_LENGTH
        ]

        offset += VaultSecurity.TAG_LENGTH

        ciphertext = blob[offset:]

        try:
            cipher = AES.new(
                key,
                AES.MODE_GCM,
                nonce=nonce,
                mac_len=VaultSecurity.TAG_LENGTH
            )

            cipher.update(associated_data)

            return cipher.decrypt_and_verify(
                ciphertext,
                tag
            )

        except (ValueError, KeyError) as exc:
            raise SecurityError(
                "Authentication failed. Incorrect key, "
                "associated data, or damaged encrypted data."
            ) from exc

        except Exception as exc:
            raise SecurityError(
                "Decryption failed."
            ) from exc


# -------------------------------------------------------------
# LOCAL SELF-TEST
# -------------------------------------------------------------

def self_test():

    import tempfile

    print("Testing Survivors Network vault security...")

    with tempfile.TemporaryDirectory() as temp_dir:

        salt_path = Path(temp_dir) / "vault.salt"

        salt = VaultSecurity.get_salt(
            salt_path
        )

        assert len(salt) == 16

        # Verify that the same installation salt is retained.
        assert VaultSecurity.get_salt(
            salt_path
        ) == salt

        master_key = VaultSecurity.derive_key(
            "Example-Long-Testing-Passphrase-2026",
            salt
        )

        assert len(master_key) == 32

        # Separate encryption keys by purpose.
        private_record_key = VaultSecurity.derive_subkey(
            master_key,
            "private-records"
        )

        directory_key = VaultSecurity.derive_subkey(
            master_key,
            "resource-directory"
        )

        matching_key = VaultSecurity.derive_subkey(
            master_key,
            "matching-storage"
        )

        assert private_record_key != directory_key
        assert private_record_key != matching_key
        assert directory_key != matching_key

        original = b"synthetic test data only"

        encrypted = VaultSecurity.encrypt(
            original,
            private_record_key,
            associated_data=b"private-record-test"
        )

        recovered = VaultSecurity.decrypt(
            encrypted,
            private_record_key,
            associated_data=b"private-record-test"
        )

        assert recovered == original

        # Verify authentication rejects a wrong key.
        try:
            VaultSecurity.decrypt(
                encrypted,
                directory_key,
                associated_data=b"private-record-test"
            )
            raise AssertionError(
                "Incorrect key was accepted."
            )
        except SecurityError:
            pass

        # Verify authentication rejects modified context.
        try:
            VaultSecurity.decrypt(
                encrypted,
                private_record_key,
                associated_data=b"wrong-context"
            )
            raise AssertionError(
                "Incorrect associated data was accepted."
            )
        except SecurityError:
            pass

        # Verify authentication rejects damaged ciphertext.
        damaged = encrypted[:-1] + bytes(
            [encrypted[-1] ^ 1]
        )

        try:
            VaultSecurity.decrypt(
                damaged,
                private_record_key,
                associated_data=b"private-record-test"
            )
            raise AssertionError(
                "Modified ciphertext was accepted."
            )
        except SecurityError:
            pass

    print("All vault security tests passed.")


if __name__ == "__main__":
    self_test()
