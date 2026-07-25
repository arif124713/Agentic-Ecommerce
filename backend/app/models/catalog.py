import datetime
import decimal

from sqlalchemy import (
    CHAR,
    DECIMAL,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class Brand(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False, index=True)
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)

    products: Mapped[list["Product"]] = relationship(back_populates="brand")


class Category(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    depth: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    seo_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    parent: Mapped["Category | None"] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list["Category"]] = relationship(back_populates="parent")
    products: Mapped[list["Product"]] = relationship(back_populates="category")

    __table_args__ = (Index("ix_categories_parent_sort", "parent_id", "sort_order"),)


class Product(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(CHAR(26), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id", ondelete="RESTRICT"), nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )

    gender: Mapped[str | None] = mapped_column(String(12), nullable=True)
    material: Mapped[str | None] = mapped_column(String(120), nullable=True)
    base_color: Mapped[str | None] = mapped_column(String(40), nullable=True)

    currency: Mapped[str] = mapped_column(CHAR(3), default="BDT", nullable=False)
    mrp: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    price: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)

    rating_avg: Mapped[decimal.Decimal | None] = mapped_column(DECIMAL(3, 2), nullable=True)
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sold_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stock_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_trending: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_new_arrival: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    thumbnail_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    seo_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    search_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    published_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)

    brand: Mapped["Brand"] = relationship(back_populates="products")
    category: Mapped["Category"] = relationship(back_populates="products")
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductImage.sort_order"
    )
    attributes: Mapped[list["ProductAttribute"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_products_listing", "status", "deleted_at", "category_id", "price"),
        Index("ix_products_brand", "brand_id", "status"),
        Index("ix_products_price", "price"),
        Index("ix_products_rating", "rating_avg", "rating_count"),
        Index("ix_products_sold", "sold_count"),
        # Spec §14.1/§14.2 MySQL FULLTEXT fallback — ngram parser tokenises into overlapping
        # n-grams so short fashion terms ("tee", "bag") stay searchable below MySQL's default
        # ft_min_word_len=4. Declared here (not just hand-written DDL in the migration) so
        # `alembic check` sees no drift between the models and the schema.
        Index(
            "ft_products",
            "title",
            "search_keywords",
            mysql_prefix="FULLTEXT",
            mysql_with_parser="ngram",
        ),
        CheckConstraint("mrp >= 0", name="ck_products_mrp_positive"),
        CheckConstraint("price >= 0", name="ck_products_price_positive"),
    )

    @property
    def discount_percent(self) -> decimal.Decimal:
        if not self.mrp or self.mrp <= 0:
            return decimal.Decimal("0")
        return ((self.mrp - self.price) / self.mrp * 100).quantize(decimal.Decimal("0.01"))


class ProductVariant(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    size: Mapped[str | None] = mapped_column(String(24), nullable=True)
    color: Mapped[str | None] = mapped_column(String(40), nullable=True)
    color_hex: Mapped[str | None] = mapped_column(CHAR(7), nullable=True)
    mrp: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    price: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    product: Mapped["Product"] = relationship(back_populates="variants")

    __table_args__ = (
        UniqueConstraint("product_id", "size", "color", name="uq_variant_product_size_color"),
        Index("ix_variants_product_active", "product_id", "is_active"),
        Index("ix_variants_stock", "stock"),
        CheckConstraint("stock >= reserved", name="ck_variants_stock_ge_reserved"),
        CheckConstraint("stock >= 0", name="ck_variants_stock_nonneg"),
    )

    @property
    def available(self) -> int:
        return self.stock - self.reserved


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True
    )
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    url_webp: Mapped[str | None] = mapped_column(String(512), nullable=True)
    blurhash: Mapped[str | None] = mapped_column(CHAR(40), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

    product: Mapped["Product"] = relationship(back_populates="images")


class ProductAttribute(Base):
    __tablename__ = "product_attributes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    group_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    is_filterable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)

    product: Mapped["Product"] = relationship(back_populates="attributes")

    __table_args__ = (Index("ix_attributes_name_value", "name", "value"),)


class InventoryMovement(Base):
    """Append-only ledger — the single source of truth for stock changes (spec §8.3). Any
    discrepancy between a variant's `stock` column and the sum of its ledger rows should be
    caught by reconciliation, not silently corrected — none built yet (see done.MD)."""

    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(nullable=True)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

    __table_args__ = (Index("ix_inventory_movements_variant", "variant_id", "created_at"),)
