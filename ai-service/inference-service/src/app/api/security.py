import hmac
import logging
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status

from src.app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def verify_internal_token(
    settings: Annotated[Settings, Depends(get_settings)],
    x_internal_token: Annotated[Optional[str], Header()] = None,
) -> None:
    """Authorize internal service-to-service calls.

    api-core (the only caller) sends a shared secret as the ``X-Internal-Token`` header.
    Requests without a valid token are rejected, so the inference endpoint is not open to
    anything that can reach it on the network. The comparison is constant-time.

    Fails closed: if no token is configured the request is rejected (503) rather than
    silently allowed.
    """
    expected = settings.search_api_token
    if not expected:
        logger.error(
            "internal auth not configured: SEARCH_API_TOKEN is empty; rejecting request"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service authentication is not configured",
        )

    if not x_internal_token or not hmac.compare_digest(x_internal_token, expected):
        logger.warning("rejected request: invalid or missing X-Internal-Token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal token",
        )
