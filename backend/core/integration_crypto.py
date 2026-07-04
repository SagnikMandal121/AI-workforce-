from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CredentialCipher:
    def __init__(self, key_material: str) -> None:
        self._key = hashlib.sha256(key_material.encode("utf-8")).digest()

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)
        ciphertext = AESGCM(self._key).encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        raw = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
        nonce = raw[:12]
        payload = raw[12:]
        plaintext = AESGCM(self._key).decrypt(nonce, payload, None)
        return plaintext.decode("utf-8")