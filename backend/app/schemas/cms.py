import datetime

from pydantic import BaseModel, ConfigDict


class CmsPageOut(BaseModel):
    """Public payload — a published page only, per `CmsService.get_published_page`."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    body: str
    seo_title: str | None
    seo_description: str | None
    published_at: datetime.datetime | None


class BannerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    placement: str
    title: str
    image_url: str
    link_url: str | None
    sort_order: int
