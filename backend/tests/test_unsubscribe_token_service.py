import uuid

from app.services.unsubscribe_token_service import create_unsubscribe_token, decode_unsubscribe_token


def test_round_trip():
    workspace_id, contact_id = uuid.uuid4(), uuid.uuid4()
    token = create_unsubscribe_token(workspace_id=workspace_id, contact_id=contact_id)

    decoded = decode_unsubscribe_token(token)

    assert decoded == (workspace_id, contact_id)


def test_garbage_token_returns_none():
    assert decode_unsubscribe_token("not-a-real-token") is None


def test_token_from_wrong_purpose_rejected():
    # A well-formed JWT but signed for a different purpose (no "type": "unsubscribe")
    from jose import jwt

    from app.core.config import get_settings

    settings = get_settings()
    token = jwt.encode({"type": "access", "sub": "someone"}, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    assert decode_unsubscribe_token(token) is None
