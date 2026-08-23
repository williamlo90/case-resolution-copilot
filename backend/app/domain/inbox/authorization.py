from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class InboxCapability(StrEnum):
    READ_CONVERSATIONS = "conversation_read"
    CREATE_DRAFTS = "draft_create"


class AuthorizationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_id: str = Field(min_length=1, max_length=500)
    redirect_uri: str = Field(min_length=1, max_length=2000)
    scopes: tuple[str, ...] = Field(min_length=1)
    state: str = Field(min_length=32, max_length=512)
    code_challenge: str = Field(min_length=43, max_length=128)
    login_hint: str | None = Field(default=None, max_length=320)


class AuthorizationCallback(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: SecretStr
    redirect_uri: str = Field(min_length=1, max_length=2000)
    code_verifier: SecretStr


class GrantedCredential(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_token: SecretStr
    refresh_token: SecretStr
    granted_scopes: tuple[str, ...] = Field(min_length=1)
    expires_at: datetime


class RefreshCredential(BaseModel):
    model_config = ConfigDict(frozen=True)

    refresh_token: SecretStr


class AccessCredential(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_token: SecretStr
    expires_at: datetime


class ProviderAccount(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_account_id: str = Field(min_length=1, max_length=500)
    address: str = Field(min_length=3, max_length=320)
    history_id: str | None = Field(default=None, max_length=500)


class RevocationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    revoked: bool
    provider_confirmed: bool


class EncryptedCredential(BaseModel):
    model_config = ConfigDict(frozen=True)

    ciphertext: str = Field(min_length=1)
    nonce: str = Field(min_length=1, max_length=64)
    authentication_tag: str = Field(min_length=1, max_length=64)
    key_id: str = Field(min_length=1, max_length=64)
    algorithm: str = Field(pattern=r"^AES-256-GCM$")
    credential_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class OAuthSessionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    public_id: str
    organization_id: UUID
    actor_id: UUID
    provider: str
    requested_capabilities: tuple[InboxCapability, ...]
    return_path: str
    verifier: EncryptedCredential
    expires_at: datetime


class InboxCredentialRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: UUID
    connection_id: UUID
    connection_public_id: str
    adapter_key: str
    provider: str
    account_address: str
    import_mode: str
    granted_scopes: tuple[str, ...]
    credential: EncryptedCredential


class InboxAuthorizationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    connection_public_id: str
    account_address: str
    return_path: str
    granted_capabilities: tuple[InboxCapability, ...]


class InboxAuthorizationStart(BaseModel):
    model_config = ConfigDict(frozen=True)

    authorization_url: str
    expires_at: datetime


class InboxAccessContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: UUID
    connection_id: UUID
    connection_public_id: str
    adapter_key: str
    account_address: str
    import_mode: str
    access: AccessCredential


class InboxDisconnectResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    connection_public_id: str
    provider_revoked: bool
    local_credential_deleted: bool = True
