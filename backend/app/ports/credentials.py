from typing import Protocol

from app.domain.inbox import EncryptedCredential


class CredentialProtector(Protocol):
    def encrypt(
        self,
        *,
        refresh_token: str,
        organization_id: str,
        connection_id: str,
        provider: str,
    ) -> EncryptedCredential: ...

    def decrypt(
        self,
        *,
        envelope: EncryptedCredential,
        organization_id: str,
        connection_id: str,
        provider: str,
    ) -> str: ...
