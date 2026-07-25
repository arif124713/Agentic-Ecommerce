"""baseline catalogue schema

Revision ID: 3b87e7cbe117
Revises:
Create Date: 2026-07-23 21:00:02.615251

Regenerated 2026-07-26: the version of this file that had been in the repo only created
`product_images` — a real bug, not a stylistic issue. `alembic upgrade head` against a genuinely
empty database (never exercised before: the dev DB was seeded once via `Base.metadata.create_all`
before Alembic was introduced, and `blackcart_test` in tests/conftest.py bypasses Alembic the same
way, so this gap went undetected until CI's from-scratch migration gate tried it). Regenerated via
`alembic.autogenerate.produce_migrations`/`render_python_code` against an empty DB scoped to just
`app.models.catalog`'s tables, so this now actually creates the full catalogue schema the later
migrations (auth, commerce, inventory/refunds, discovery, reviews) all assume already exists.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b87e7cbe117'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('brands',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('slug', sa.String(length=140), nullable=False),
    sa.Column('logo_url', sa.String(length=512), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.SmallInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_brands_slug'), 'brands', ['slug'], unique=True)
    op.create_table('categories',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('slug', sa.String(length=140), nullable=False),
    sa.Column('path', sa.String(length=512), nullable=False),
    sa.Column('depth', sa.SmallInteger(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('image_url', sa.String(length=512), nullable=True),
    sa.Column('icon', sa.String(length=64), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.SmallInteger(), nullable=False),
    sa.Column('seo_title', sa.String(length=255), nullable=True),
    sa.Column('seo_description', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['parent_id'], ['categories.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_categories_parent_sort', 'categories', ['parent_id', 'sort_order'], unique=False)
    op.create_index(op.f('ix_categories_path'), 'categories', ['path'], unique=False)
    op.create_index(op.f('ix_categories_slug'), 'categories', ['slug'], unique=True)
    op.create_table('products',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('public_id', sa.CHAR(length=26), nullable=False),
    sa.Column('slug', sa.String(length=255), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('subtitle', sa.String(length=255), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('brand_id', sa.Integer(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('gender', sa.String(length=12), nullable=True),
    sa.Column('material', sa.String(length=120), nullable=True),
    sa.Column('base_color', sa.String(length=40), nullable=True),
    sa.Column('currency', sa.CHAR(length=3), nullable=False),
    sa.Column('mrp', sa.DECIMAL(precision=12, scale=2), nullable=False),
    sa.Column('price', sa.DECIMAL(precision=12, scale=2), nullable=False),
    sa.Column('rating_avg', sa.DECIMAL(precision=3, scale=2), nullable=True),
    sa.Column('rating_count', sa.Integer(), nullable=False),
    sa.Column('review_count', sa.Integer(), nullable=False),
    sa.Column('sold_count', sa.Integer(), nullable=False),
    sa.Column('view_count', sa.Integer(), nullable=False),
    sa.Column('stock_total', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('is_featured', sa.Boolean(), nullable=False),
    sa.Column('is_trending', sa.Boolean(), nullable=False),
    sa.Column('is_new_arrival', sa.Boolean(), nullable=False),
    sa.Column('thumbnail_url', sa.String(length=512), nullable=True),
    sa.Column('seo_title', sa.String(length=255), nullable=True),
    sa.Column('seo_description', sa.String(length=255), nullable=True),
    sa.Column('search_keywords', sa.Text(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('published_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('mrp >= 0', name='ck_products_mrp_positive'),
    sa.CheckConstraint('price >= 0', name='ck_products_price_positive'),
    sa.ForeignKeyConstraint(['brand_id'], ['brands.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('public_id')
    )
    op.create_index('ft_products', 'products', ['title', 'search_keywords'], unique=False, mysql_prefix='FULLTEXT', mysql_with_parser='ngram')
    op.create_index('ix_products_brand', 'products', ['brand_id', 'status'], unique=False)
    op.create_index('ix_products_listing', 'products', ['status', 'deleted_at', 'category_id', 'price'], unique=False)
    op.create_index('ix_products_price', 'products', ['price'], unique=False)
    op.create_index('ix_products_rating', 'products', ['rating_avg', 'rating_count'], unique=False)
    op.create_index(op.f('ix_products_slug'), 'products', ['slug'], unique=True)
    op.create_index('ix_products_sold', 'products', ['sold_count'], unique=False)
    op.create_table('product_attributes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('value', sa.String(length=255), nullable=False),
    sa.Column('group_name', sa.String(length=60), nullable=True),
    sa.Column('is_filterable', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.SmallInteger(), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_attributes_name_value', 'product_attributes', ['name', 'value'], unique=False)
    op.create_table('product_variants',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('sku', sa.String(length=64), nullable=False),
    sa.Column('size', sa.String(length=24), nullable=True),
    sa.Column('color', sa.String(length=40), nullable=True),
    sa.Column('color_hex', sa.CHAR(length=7), nullable=True),
    sa.Column('mrp', sa.DECIMAL(precision=12, scale=2), nullable=False),
    sa.Column('price', sa.DECIMAL(precision=12, scale=2), nullable=False),
    sa.Column('stock', sa.Integer(), nullable=False),
    sa.Column('reserved', sa.Integer(), nullable=False),
    sa.Column('low_stock_threshold', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('position', sa.SmallInteger(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('stock >= 0', name='ck_variants_stock_nonneg'),
    sa.CheckConstraint('stock >= reserved', name='ck_variants_stock_ge_reserved'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('product_id', 'size', 'color', name='uq_variant_product_size_color'),
    sa.UniqueConstraint('sku')
    )
    op.create_index('ix_variants_product_active', 'product_variants', ['product_id', 'is_active'], unique=False)
    op.create_index('ix_variants_stock', 'product_variants', ['stock'], unique=False)
    op.create_table('inventory_movements',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('variant_id', sa.Integer(), nullable=False),
    sa.Column('delta', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(length=30), nullable=False),
    sa.Column('reference_type', sa.String(length=30), nullable=True),
    sa.Column('reference_id', sa.Integer(), nullable=True),
    sa.Column('balance_after', sa.Integer(), nullable=False),
    sa.Column('actor_user_id', sa.Integer(), nullable=True),
    sa.Column('note', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_inventory_movements_variant', 'inventory_movements', ['variant_id', 'created_at'], unique=False)
    op.create_table('product_images',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('variant_id', sa.Integer(), nullable=True),
    sa.Column('url', sa.String(length=512), nullable=False),
    sa.Column('url_webp', sa.String(length=512), nullable=True),
    sa.Column('blurhash', sa.CHAR(length=40), nullable=True),
    sa.Column('width', sa.Integer(), nullable=True),
    sa.Column('height', sa.Integer(), nullable=True),
    sa.Column('alt_text', sa.String(length=255), nullable=True),
    sa.Column('sort_order', sa.SmallInteger(), nullable=False),
    sa.Column('is_primary', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Explicit drop_index calls removed for ix_products_brand / ix_categories_parent_sort /
    # ix_variants_product_active / ix_inventory_movements_variant: each leads with the exact
    # column backing a live FK constraint (brand_id, parent_id, product_id, variant_id
    # respectively), and MySQL refuses to drop an index still needed by an FK until the
    # table (and its FK) is gone — the same recurring drop-order bug documented in every
    # later migration in this project. drop_table removes each of these for free.
    op.drop_table('product_images')
    op.drop_table('inventory_movements')
    op.drop_index('ix_variants_stock', table_name='product_variants')
    op.drop_table('product_variants')
    op.drop_index('ix_attributes_name_value', table_name='product_attributes')
    op.drop_table('product_attributes')
    op.drop_index('ix_products_sold', table_name='products')
    op.drop_index(op.f('ix_products_slug'), table_name='products')
    op.drop_index('ix_products_rating', table_name='products')
    op.drop_index('ix_products_price', table_name='products')
    op.drop_index('ix_products_listing', table_name='products')
    op.drop_index('ft_products', table_name='products', mysql_prefix='FULLTEXT', mysql_with_parser='ngram')
    op.drop_table('products')
    op.drop_index(op.f('ix_categories_slug'), table_name='categories')
    op.drop_index(op.f('ix_categories_path'), table_name='categories')
    op.drop_table('categories')
    op.drop_index(op.f('ix_brands_slug'), table_name='brands')
    op.drop_table('brands')
