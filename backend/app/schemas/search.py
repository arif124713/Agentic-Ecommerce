from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SuggestProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slug: str
    title: str
    thumbnail_url: str | None
    price: Decimal
    currency: str


class SuggestBrandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    slug: str


class SuggestCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    slug: str


class SearchSuggestOut(BaseModel):
    products: list[SuggestProductOut]
    brands: list[SuggestBrandOut]
    categories: list[SuggestCategoryOut]
    popular_queries: list[str]
