"""Identity primitive — PKI signing/verification and agent DIDs."""

from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import base64
import json
from dataclasses import dataclass, field


@dataclass
class IdentityPrimitive:
    agent_id: str
    _private_key: ed25519.Ed25519PrivateKey = field(init=False, repr=False)
    _public_key: ed25519.Ed25519PublicKey = field(init=False, repr=False)

    def __post_init__(self):
        self._private_key = ed25519.Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()

    @property
    def did(self) -> str:
        pub_bytes = self._public_key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return f"did:key:z{base64.urlsafe_b64encode(pub_bytes).decode().rstrip('=')}"

    @property
    def public_key_bytes(self) -> bytes:
        return self._public_key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )

    async def sign(self, message: str | bytes) -> str:
        data = message.encode() if isinstance(message, str) else message
        sig = self._private_key.sign(data)
        return base64.urlsafe_b64encode(sig).decode()

    async def verify(self, message: str | bytes, signature: str) -> bool:
        data = message.encode() if isinstance(message, str) else message
        sig = base64.urlsafe_b64decode(signature + "==")
        try:
            self._public_key.verify(sig, data)
            return True
        except Exception:
            return False

    def export_public_key(self) -> str:
        return base64.urlsafe_b64encode(self.public_key_bytes).decode()
