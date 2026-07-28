import datetime

from pydantic import BaseModel, ConfigDict, Field


class CmsPageWriteIn(BaseModel):
    slug: str = Field(min_length=1, max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=255)
    body: str
    status: str = Field(default="draft", pattern="^(draft|published)$")
    seo_title: str | None = None
    seo_description: str | None = None


class CmsPageAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    body: str
    status: str
    seo_title: str | None
    seo_description: str | None
    published_at: datetime.datetime | None
    is_deleted: bool


class BannerWriteIn(BaseModel):
    placement: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=255)
    image_url: str = Field(min_length=1, max_length=512)
    link_url: str | None = None
    sort_order: int = 0
    starts_at: datetime.datetime | None = None
    ends_at: datetime.datetime | None = None
    is_active: bool = True


class BannerAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    placement: str
    title: str
    image_url: str
    link_url: str | None
    sort_order: int
    starts_at: datetime.datetime | None
    ends_at: datetime.datetime | None
    is_active: bool
