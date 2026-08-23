import pytest

from app.domain.inbox import InboxCredentialUnavailable
from app.security.credential_vault import AesGcmCredentialVault


def test_credential_vault_round_trip_binds_tenant_connection_and_provider() -> None:
    vault = AesGcmCredentialVault(
        key=b"0123456789abcdef0123456789abcdef",
        key_id="test-v1",
    )
    envelope = vault.encrypt(
        refresh_token="refresh-secret",
        organization_id="ORG-TEST",
        connection_id="CON-TEST",
        provider="gmail",
    )

    assert "refresh-secret" not in repr(envelope)
    assert vault.decrypt(
        envelope=envelope,
        organization_id="ORG-TEST",
        connection_id="CON-TEST",
        provider="gmail",
    ) == "refresh-secret"

    with pytest.raises(InboxCredentialUnavailable):
        vault.decrypt(
            envelope=envelope,
            organization_id="ORG-OTHER",
            connection_id="CON-TEST",
            provider="gmail",
        )


def test_credential_vault_rejects_wrong_key_and_invalid_length() -> None:
    with pytest.raises(ValueError):
        AesGcmCredentialVault(key=b"short", key_id="test-v1")

    first = AesGcmCredentialVault(
        key=b"0123456789abcdef0123456789abcdef",
        key_id="test-v1",
    )
    second = AesGcmCredentialVault(
        key=b"abcdef0123456789abcdef0123456789",
        key_id="test-v1",
    )
    envelope = first.encrypt(
        refresh_token="refresh-secret",
        organization_id="ORG-TEST",
        connection_id="CON-TEST",
        provider="gmail",
    )

    with pytest.raises(InboxCredentialUnavailable):
        second.decrypt(
            envelope=envelope,
            organization_id="ORG-TEST",
            connection_id="CON-TEST",
            provider="gmail",
        )
