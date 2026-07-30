"""Bulk product CSV import/export and bulk actions (spec §10.8, §24.3 E2E journey 7: "Bulk CSV
import -> validation errors surfaced per row -> successful rows imported")."""

import csv
import io

from sqlalchemy import select

from app.core.timeutil import utcnow
from app.models.auth import Role, User, UserRole
from app.models.catalog import Brand, Category
from tests.conftest import make_product_with_variant, register_and_login


async def _promote(db_session, user_id: int, role_code: str) -> None:
    role = (await db_session.execute(select(Role).where(Role.code == role_code))).scalar_one()
    db_session.add(UserRole(user_id=user_id, role_id=role.id, granted_at=utcnow()))
    await db_session.flush()


async def _make_admin(client, db_session):
    creds = await register_and_login(client)
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    await _promote(db_session, user.id, "admin")
    await client.post("/api/v1/auth/login", json={"email": creds["email"], "password": creds["password"]})
    return user


def _csv_bytes(rows: list[dict]) -> bytes:
    fieldnames = ["slug", "title", "brand", "category", "price", "mrp", "status"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


async def test_import_partial_success_creates_updates_and_reports_row_errors(client, db_session):
    await _make_admin(client, db_session)
    product, _variant = await make_product_with_variant(db_session, title="Existing Item", price="100.00", mrp="200.00")
    # brand/category relationships aren't eager-loaded on the tuple returned by the helper; look
    # them up fresh to get their real (randomly-suffixed) names.
    brand = (await db_session.execute(select(Brand).where(Brand.id == product.brand_id))).scalar_one()
    category = (await db_session.execute(select(Category).where(Category.id == product.category_id))).scalar_one()

    rows = [
        # row 2: valid update of the existing product
        {"slug": product.slug, "title": "Updated Title", "brand": brand.name, "category": category.name, "price": "150.00", "mrp": "250.00", "status": "active"},
        # row 3: valid new product
        {"slug": "", "title": "Brand New Product", "brand": brand.name, "category": category.name, "price": "50.00", "mrp": "100.00", "status": "draft"},
        # row 4: invalid — unknown brand
        {"slug": "", "title": "Bad Brand Row", "brand": "Nonexistent Brand XYZ", "category": category.name, "price": "10.00", "mrp": "20.00", "status": "draft"},
        # row 5: invalid — price exceeds mrp
        {"slug": "", "title": "Bad Price Row", "brand": brand.name, "category": category.name, "price": "999.00", "mrp": "10.00", "status": "draft"},
    ]
    csv_body = _csv_bytes(rows)

    resp = await client.post(
        "/api/v1/admin/products/import", files={"file": ("products.csv", csv_body, "text/csv")}
    )
    assert resp.status_code == 200, resp.text
    summary = resp.json()["data"]
    assert summary["total"] == 4
    assert summary["created"] == 1
    assert summary["updated"] == 1
    assert summary["failed"] == 2

    by_row = {r["row"]: r for r in summary["results"]}
    assert by_row[2]["status"] == "updated"
    assert by_row[2]["slug"] == product.slug
    assert by_row[3]["status"] == "created"
    assert by_row[4]["status"] == "error"
    assert "brand" in by_row[4]["message"]
    assert by_row[5]["status"] == "error"
    assert "mrp" in by_row[5]["message"]

    await db_session.refresh(product)
    assert product.title == "Updated Title"


async def test_import_missing_required_columns_is_rejected(client, db_session):
    await _make_admin(client, db_session)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["title", "price"])  # missing brand/category/mrp
    writer.writeheader()
    writer.writerow({"title": "x", "price": "10"})
    resp = await client.post(
        "/api/v1/admin/products/import",
        files={"file": ("bad.csv", buf.getvalue().encode(), "text/csv")},
    )
    assert resp.status_code == 409, resp.text


async def test_import_requires_permission(client, db_session):
    await register_and_login(client)  # plain customer
    resp = await client.post(
        "/api/v1/admin/products/import", files={"file": ("products.csv", b"title,brand,category,price,mrp\n", "text/csv")}
    )
    assert resp.status_code == 403


async def test_export_returns_real_product_data_as_csv(client, db_session):
    await _make_admin(client, db_session)
    product, _variant = await make_product_with_variant(db_session, title="Exportable Product")

    resp = await client.get("/api/v1/admin/products/export")
    assert resp.status_code == 200, resp.text
    assert "text/csv" in resp.headers["content-type"]

    reader = csv.DictReader(io.StringIO(resp.text))
    slugs = [row["slug"] for row in reader]
    assert product.slug in slugs


async def test_bulk_archive_and_delete(client, db_session):
    await _make_admin(client, db_session)
    product_a, _ = await make_product_with_variant(db_session, title="Bulk A")
    product_b, _ = await make_product_with_variant(db_session, title="Bulk B")

    archive_resp = await client.post(
        "/api/v1/admin/products/bulk", json={"product_ids": [product_a.id, product_b.id], "action": "archive"}
    )
    assert archive_resp.status_code == 200, archive_resp.text
    body = archive_resp.json()["data"]
    assert body["succeeded"] == 2
    assert body["failed"] == []

    await db_session.refresh(product_a)
    await db_session.refresh(product_b)
    assert product_a.status == "archived"
    assert product_b.status == "archived"

    delete_resp = await client.post(
        "/api/v1/admin/products/bulk", json={"product_ids": [product_a.id], "action": "delete"}
    )
    assert delete_resp.status_code == 200
    await db_session.refresh(product_a)
    assert product_a.deleted_at is not None

    logs_resp = await client.get("/api/v1/admin/audit-logs", params={"resource_type": "product"})
    actions = [log["action"] for log in logs_resp.json()["data"] if log["resource_id"] == str(product_a.id)]
    assert "bulk_archive" in actions
    assert "bulk_delete" in actions


async def test_bulk_action_reports_unknown_ids_as_failed(client, db_session):
    await _make_admin(client, db_session)
    product, _ = await make_product_with_variant(db_session)

    resp = await client.post(
        "/api/v1/admin/products/bulk", json={"product_ids": [product.id, 9_999_999], "action": "archive"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["succeeded"] == 1
    assert body["failed"] == [9_999_999]
