import os
from pathlib import Path

from argon2.low_level import Type, hash_secret_raw
from Crypto.Cipher import AES


class SecurityError(Exception):
    pass


class VaultSecurity:

    KEY_LENGTH = 32
    SALT_LENGTH = 16
    NONCE_LENGTH = 12

    TIME_COST = 3
    MEMORY_COST = 65536
    PARALLELISM = 2

    @staticmethod
    def get_salt(salt_path):

        path = Path(salt_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            salt = path.read_bytes()

            if len(salt) != VaultSecurity.SALT_LENGTH:
                raise SecurityError("Invalid vault salt.")

            return salt

        salt = os.urandom(VaultSecurity.SALT_LENGTH)

        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL

        fd = os.open(str(path), flags, 0o600)

        with os.fdopen(fd, "wb") as file:
            file.write(salt)

        return salt

    @staticmethod
    def derive_key(passphrase, salt):

        if not isinstance(passphrase, str):
            raise SecurityError("Invalid passphrase.")

        if len(passphrase) < 12:
            raise SecurityError(
                "Passphrase must contain at least 12 characters."
            )

        return hash_secret_raw(
            secret=passphrase.encode("utf-8"),
            salt=salt,
            time_cost=VaultSecurity.TIME_COST,
            memory_cost=VaultSecurity.MEMORY_COST,
            parallelism=VaultSecurity.PARALLELISM,
            hash_len=VaultSecurity.KEY_LENGTH,
            type=Type.ID
        )

    @staticmethod
    def encrypt(data, key, associated_data=b""):

        if len(key) != VaultSecurity.KEY_LENGTH:
            raise SecurityError("Invalid encryption key.")

        nonce = os.urandom(VaultSecurity.NONCE_LENGTH)

        cipher = AES.new(
            key,
            AES.MODE_GCM,
            nonce=nonce
        )

        cipher.update(associated_data)

        ciphertext, tag = cipher.encrypt_and_digest(data)

        return (
            b"SNV1"
            + nonce
            + tag
            + ciphertext
        )

    @staticmethod
    def decrypt(blob, key, associated_data=b""):

        if not blob.startswith(b"SNV1"):
            raise SecurityError("Unknown encrypted data format.")

        nonce = blob[4:16]
        tag = blob[16:32]
        ciphertext = blob[32:]

        cipher = AES.new(
            key,
            AES.MODE_GCM,
            nonce=nonce
        )

        cipher.update(associated_data)

        try:
            return cipher.decrypt_and_verify(
                ciphertext,
                tag
            )

        except ValueError as exc:
            raise SecurityError(
                "Authentication failed. Incorrect key or damaged data."
            ) from exc
