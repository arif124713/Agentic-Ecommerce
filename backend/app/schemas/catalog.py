from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class BrandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    slug: str
    logo_url: str | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    slug: str
    path: str
    depth: int
    image_url: str | None = None
    icon: str | None = None


class CategoryTreeNode(CategoryOut):
    children: list["CategoryTreeNode"] = []


class ProductImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    url: str
    alt_text: str | None = None
    is_primary: bool


class ProductVariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku: str
    size: str | None = None
    color: str | None = None
    color_hex: str | None = None
    price: Decimal
    mrp: Decimal
    available: int
    is_active: bool


class ProductCardOut(BaseModel):
    """Trimmed payload for listing grids — spec §17.3 ProductCard."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    brand: str
    thumbnail_url: str | None
    price: Decimal
    mrp: Decimal
    discount_percent: Decimal
    rating_avg: Decimal | None
    rating_count: int
    currency: str
    in_stock: bool


class ProductDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    subtitle: str | None
    description: str | None
    brand: BrandOut
    category: CategoryOut
    gender: str | None
    material: str | None
    base_color: str | None
    currency: str
    price: Decimal
    mrp: Decimal
    discount_percent: Decimal
    rating_avg: Decimal | None
    rating_count: int
    review_count: int
    images: list[ProductImageOut]
    variants: list[ProductVariantOut]


class ProductListMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    search_fallback: bool = False


class FacetBucket(BaseModel):
    value: str
    count: int


class CategoryFacetBucket(BaseModel):
    slug: str
    name: str
    count: int
    is_active: bool = False


class ProductFacets(BaseModel):
    brands: list[FacetBucket] = []
    categories: list[CategoryFacetBucket] = []
    sizes: list[FacetBucket] = []
    colors: list[FacetBucket] = []
    price_range: dict[str, Decimal] | None = None


class ProductListOut(BaseModel):
    data: list[ProductCardOut]
    meta: ProductListMeta
    facets: ProductFacets
