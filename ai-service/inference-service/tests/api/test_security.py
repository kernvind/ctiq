import pytest
from fastapi import HTTPException

from src.app.core.config import Settings
from src.app.api.security import verify_internal_token


def _settings(token: str) -> Settings:
    # init kwargs take precedence over env/.env in pydantic-settings, so this is
    # deterministic regardless of the local .env value.
    return Settings(search_api_token=token)


def test_valid_token_is_accepted():
    # Should not raise.
    verify_internal_token(_settings("s3cret"), "s3cret")


def test_wrong_token_is_rejected_401():
    with pytest.raises(HTTPException) as exc:
        verify_internal_token(_settings("s3cret"), "wrong-token")
    assert exc.value.status_code == 401


def test_missing_token_is_rejected_401():
    with pytest.raises(HTTPException) as exc:
        verify_internal_token(_settings("s3cret"), None)
    assert exc.value.status_code == 401


def test_unconfigured_token_fails_closed_503():
    # Even with a token presented, an empty configured secret must reject (not allow).
    with pytest.raises(HTTPException) as exc:
        verify_internal_token(_settings(""), "anything")
    assert exc.value.status_code == 503
