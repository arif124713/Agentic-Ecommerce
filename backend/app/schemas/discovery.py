from pydantic import BaseModel, EmailStr, Field

from app.schemas.catalog import ProductCardOut


class WishlistItemOut(BaseModel):
    item_id: int
    product: ProductCardOut


class WishlistOut(BaseModel):
    items: list[WishlistItemOut]


class WishlistAddIn(BaseModel):
    product_slug: str


class StockAlertIn(BaseModel):
    variant_id: int
    email: EmailStr | None = None


class NewsletterSubscribeIn(BaseModel):
    email: EmailStr = Field(max_length=255)
