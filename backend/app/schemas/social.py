import uuid

from pydantic import BaseModel


class SocialProfileRead(BaseModel):
    platform: str
    profile_url: str
    display_name: str | None
    headline: str | None


class SocialPostRead(BaseModel):
    platform: str
    post_url: str
    author_profile_url: str | None
    text: str | None
    posted_at: str | None


class DiscoverProfileRequest(BaseModel):
    workspace_id: uuid.UUID
    full_name: str | None = None
    company_domain: str | None = None


class DiscoverPostsRequest(BaseModel):
    workspace_id: uuid.UUID
    keywords: str
    limit: int = 25
