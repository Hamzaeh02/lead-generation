"""Signed, stateless unsubscribe tokens (section 45).

Reuses the same JWT signing infrastructure as auth tokens (`SECRET_KEY`,
`python-jose`) rather than adding a new signing mechanism. Deliberately
has no expiration — an unsubscribe link must keep working indefinitely,
unlike an access token.
"""
from __future__ import annotations

import uuid

from jose import JWTError, jwt

from app.core.config import get_settings

_TOKEN_TYPE = "unsubscribe"


def create_unsubscribe_token(*, workspace_id: uuid.UUID, contact_id: uuid.UUID) -> str:
    settings = get_settings()
    payload = {"type": _TOKEN_TYPE, "workspace_id": str(workspace_id), "contact_id": str(contact_id)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_unsubscribe_token(token: str) -> tuple[uuid.UUID, uuid.UUID] | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != _TOKEN_TYPE:
        return None
    try:
        return uuid.UUID(payload["workspace_id"]), uuid.UUID(payload["contact_id"])
    except (KeyError, ValueError):
        return None
