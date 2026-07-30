from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class VariantWriteIn(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    size: str | None = Field(default=None, max_length=24)
    color: str | None = Field(default=None, max_length=40)
    color_hex: str | None = Field(default=None, max_length=7)
    mrp: Decimal
    price: Decimal
    stock: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=5, ge=0)
    is_active: bool = True


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    size: str | None
    color: str | None
    color_hex: str | None
    mrp: Decimal
    price: Decimal
    stock: int
    reserved: int
    available: int
    low_stock_threshold: int
    is_active: bool


class ProductWriteIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subtitle: str | None = Field(default=None, max_length=255)
    description: str | None = None
    brand_id: int
    category_id: int
    gender: str | None = Field(default=None, max_length=12)
    material: str | None = Field(default=None, max_length=120)
    base_color: str | None = Field(default=None, max_length=40)
    currency: str = Field(default="INR", max_length=3)
    mrp: Decimal
    price: Decimal
    status: str = Field(default="draft", pattern="^(draft|active|archived)$")
    is_featured: bool = False
    is_trending: bool = False
    is_new_arrival: bool = False
    thumbnail_url: str | None = None
    seo_title: str | None = Field(default=None, max_length=255)
    seo_description: str | None = Field(default=None, max_length=255)


class AdminProductListItem(BaseModel):
    id: int
    slug: str
    title: str
    brand: str
    category: str
    price: Decimal
    mrp: Decimal
    status: str
    stock_total: int
    thumbnail_url: str | None
    is_deleted: bool


class AdminProductListMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool


class AdminProductListOut(BaseModel):
    data: list[AdminProductListItem]
    meta: AdminProductListMeta


class AdminProductDetail(BaseModel):
    id: int
    slug: str
    title: str
    subtitle: str | None
    description: str | None
    brand_id: int
    category_id: int
    gender: str | None
    material: str | None
    base_color: str | None
    currency: str
    mrp: Decimal
    price: Decimal
    status: str
    is_deleted: bool
    is_featured: bool
    is_trending: bool
    is_new_arrival: bool
    thumbnail_url: str | None
    seo_title: str | None
    seo_description: str | None
    variants: list[VariantOut]


class InventoryAdjustIn(BaseModel):
    delta: int
    reason: str = Field(default="admin_adjust", max_length=30)
    note: str | None = Field(default=None, max_length=255)


class LowStockVariantOut(BaseModel):
    variant_id: int
    sku: str
    product_title: str
    product_slug: str
    size: str | None
    color: str | None
    available: int
    low_stock_threshold: int


class BrandOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class CategoryOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    path: str
    depth: int


class ProductImportRowResult(BaseModel):
    row: int
    status: str  # created | updated | error
    slug: str | None = None
    message: str | None = None


class ProductImportSummary(BaseModel):
    total: int
    created: int
    updated: int
    failed: int
    results: list[ProductImportRowResult]


class ProductBulkActionIn(BaseModel):
    product_ids: list[int] = Field(min_length=1, max_length=500)
    action: str = Field(pattern="^(activate|archive|delete)$")


class ProductBulkActionResult(BaseModel):
    action: str
    requested: int
    succeeded: int
    failed: list[int]
