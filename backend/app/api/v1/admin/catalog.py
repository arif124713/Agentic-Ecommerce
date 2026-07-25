from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.models.auth import User
from app.schemas.admin_catalog import (
    AdminProductDetail,
    AdminProductListOut,
    BrandOption,
    CategoryOption,
    InventoryAdjustIn,
    LowStockVariantOut,
    ProductWriteIn,
    VariantOut,
    VariantWriteIn,
)
from app.services.admin.catalog_service import AdminCatalogService

router = APIRouter(prefix="/admin", tags=["admin-catalog"])


@router.get("/products", response_model=AdminProductListOut)
async def list_products(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("catalog:product:write")),
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    category_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
):
    return await AdminCatalogService(db).list_products(
        q=q, status=status, category_id=category_id, page=page, per_page=per_page
    )


@router.get("/products/{product_id}", response_model=AdminProductDetail)
async def get_product(
    product_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(require("catalog:product:write"))
):
    return await AdminCatalogService(db).get_product(product_id)


@router.post("/products", response_model=AdminProductDetail, status_code=201)
async def create_product(
    payload: ProductWriteIn, db: AsyncSession = Depends(get_db), _user: User = Depends(require("catalog:product:write"))
):
    return await AdminCatalogService(db).create_product(payload)


@router.patch("/products/{product_id}", response_model=AdminProductDetail)
async def update_product(
    product_id: int,
    payload: ProductWriteIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("catalog:product:write")),
):
    return await AdminCatalogService(db).update_product(product_id, payload)


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(
    product_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(require("catalog:product:delete"))
):
    await AdminCatalogService(db).soft_delete_product(product_id)
    return Response(status_code=204)


@router.post("/products/{product_id}/restore", response_model=AdminProductDetail)
async def restore_product(
    product_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(require("catalog:product:delete"))
):
    return await AdminCatalogService(db).restore_product(product_id)


@router.post("/products/{product_id}/variants", response_model=VariantOut, status_code=201)
async def add_variant(
    product_id: int,
    payload: VariantWriteIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("catalog:product:write")),
):
    return await AdminCatalogService(db).add_variant(product_id, payload)


@router.patch("/variants/{variant_id}", response_model=VariantOut)
async def update_variant(
    variant_id: int,
    payload: VariantWriteIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("catalog:product:write")),
):
    return await AdminCatalogService(db).update_variant(variant_id, payload)


@router.delete("/variants/{variant_id}", status_code=204)
async def delete_variant(
    variant_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(require("catalog:product:write"))
):
    await AdminCatalogService(db).delete_variant(variant_id)
    return Response(status_code=204)


@router.post("/inventory/{variant_id}/adjust", response_model=VariantOut)
async def adjust_inventory(
    variant_id: int,
    payload: InventoryAdjustIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require("catalog:inventory:write")),
):
    return await AdminCatalogService(db).adjust_inventory(variant_id, payload, user.id)


@router.get("/inventory/low-stock", response_model=list[LowStockVariantOut])
async def low_stock(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("catalog:inventory:write")),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await AdminCatalogService(db).low_stock(limit=limit)


@router.get("/catalog-options/brands", response_model=list[BrandOption])
async def brand_options(db: AsyncSession = Depends(get_db), _user: User = Depends(require("catalog:product:write"))):
    return await AdminCatalogService(db).list_brand_options()


@router.get("/catalog-options/categories", response_model=list[CategoryOption])
async def category_options(
    db: AsyncSession = Depends(get_db), _user: User = Depends(require("catalog:product:write"))
):
    return await AdminCatalogService(db).list_category_options()
