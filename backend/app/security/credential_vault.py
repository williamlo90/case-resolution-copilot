from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha256
from hmac import compare_digest
from hmac import new as new_hmac
from os import urandom

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.domain.inbox import EncryptedCredential, InboxCredentialUnavailable
from app.ports.credentials import CredentialProtector

VAULT_ALGORITHM = "AES-256-GCM"


CredentialEnvelope = EncryptedCredential
CredentialVault = CredentialProtector


class AesGcmCredentialVault:
    def __init__(self, *, key: bytes, key_id: str) -> None:
        if len(key) != 32:
            raise ValueError("Credential vault key must contain exactly 32 bytes.")
        if not key_id:
            raise ValueError("Credential vault key ID is required.")
        self._cipher = AESGCM(key)
        self._fingerprint_key = key
        self._key_id = key_id

    def encrypt(
        self,
        *,
        refresh_token: str,
        organization_id: str,
        connection_id: str,
        provider: str,
    ) -> CredentialEnvelope:
        if not refresh_token:
            raise ValueError("A refresh credential is required.")
        nonce = urandom(12)
        associated_data = _associated_data(
            organization_id=organization_id,
            connection_id=connection_id,
            provider=provider,
            key_id=self._key_id,
        )
        sealed = self._cipher.encrypt(
            nonce,
            refresh_token.encode("utf-8"),
            associated_data,
        )
        return EncryptedCredential(
            ciphertext=_encode(sealed[:-16]),
            nonce=_encode(nonce),
            authentication_tag=_encode(sealed[-16:]),
            key_id=self._key_id,
            algorithm=VAULT_ALGORITHM,
            credential_fingerprint=self._fingerprint(refresh_token),
        )

    def decrypt(
        self,
        *,
        envelope: CredentialEnvelope,
        organization_id: str,
        connection_id: str,
        provider: str,
    ) -> str:
        if envelope.algorithm != VAULT_ALGORITHM or envelope.key_id != self._key_id:
            raise InboxCredentialUnavailable("The inbox credential key is unavailable.")
        associated_data = _associated_data(
            organization_id=organization_id,
            connection_id=connection_id,
            provider=provider,
            key_id=envelope.key_id,
        )
        try:
            plaintext = self._cipher.decrypt(
                _decode(envelope.nonce),
                _decode(envelope.ciphertext) + _decode(envelope.authentication_tag),
                associated_data,
            )
        except (InvalidTag, ValueError) as exc:
            raise InboxCredentialUnavailable(
                "The inbox credential could not be decrypted."
            ) from exc
        value = plaintext.decode("utf-8")
        if not compare_digest(
            self._fingerprint(value),
            envelope.credential_fingerprint,
        ):
            raise InboxCredentialUnavailable("The inbox credential fingerprint is invalid.")
        return value

    def _fingerprint(self, refresh_token: str) -> str:
        return new_hmac(
            self._fingerprint_key,
            refresh_token.encode("utf-8"),
            sha256,
        ).hexdigest()


def _associated_data(
    *,
    organization_id: str,
    connection_id: str,
    provider: str,
    key_id: str,
) -> bytes:
    return "\0".join(
        [organization_id, connection_id, provider, key_id, VAULT_ALGORITHM]
    ).encode("utf-8")


def _encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode("ascii"))
