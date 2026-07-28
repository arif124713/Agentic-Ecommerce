"""CMS pages and banners (spec §8.3): public read-only for published/active content, full CRUD
gated by cms:page:write (spec §3.3's RBAC matrix)."""

from sqlalchemy import select

from app.core.timeutil import utcnow
from app.models.auth import Role, User, UserRole
from tests.conftest import register_and_login


async def _promote(db_session, user_id: int, role_code: str) -> None:
    role = (await db_session.execute(select(Role).where(Role.code == role_code))).scalar_one()
    db_session.add(UserRole(user_id=user_id, role_id=role.id, granted_at=utcnow()))
    await db_session.flush()


async def _make_admin(client, db_session):
    creds = await register_and_login(client)
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    await _promote(db_session, user.id, "admin")
    # perms are baked into the access-token JWT at login (spec §3.2's documented no-Redis gap) —
    # a role grant only takes effect on the next login, same pattern as test_reviews.py.
    await client.post("/api/v1/auth/login", json={"email": creds["email"], "password": creds["password"]})
    return user


async def test_public_page_404_for_missing_slug(client, db_session):
    resp = await client.get("/api/v1/pages/does-not-exist")
    assert resp.status_code == 404


async def test_draft_page_is_not_publicly_visible(client, db_session):
    await _make_admin(client, db_session)
    create_resp = await client.post(
        "/api/v1/admin/cms/pages",
        json={"slug": "draft-page", "title": "Draft", "body": "<p>wip</p>", "status": "draft"},
    )
    assert create_resp.status_code == 201, create_resp.text

    public_resp = await client.get("/api/v1/pages/draft-page")
    assert public_resp.status_code == 404


async def test_admin_can_publish_a_page_and_it_becomes_publicly_readable(client, db_session):
    await _make_admin(client, db_session)
    create_resp = await client.post(
        "/api/v1/admin/cms/pages",
        json={
            "slug": "about-us",
            "title": "About Us",
            "body": "<p>We sell clothes.</p>",
            "status": "published",
            "seo_title": "About",
            "seo_description": "Learn more",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    assert create_resp.json()["data"]["published_at"] is not None

    public_resp = await client.get("/api/v1/pages/about-us")
    assert public_resp.status_code == 200, public_resp.text
    body = public_resp.json()["data"]
    assert body["title"] == "About Us"
    assert body["seo_title"] == "About"


async def test_duplicate_slug_is_rejected(client, db_session):
    await _make_admin(client, db_session)
    payload = {"slug": "faq", "title": "FAQ", "body": "<p>q and a</p>", "status": "published"}
    first = await client.post("/api/v1/admin/cms/pages", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/admin/cms/pages", json=payload)
    assert second.status_code == 409


async def test_cms_admin_endpoints_require_permission(client, db_session):
    await register_and_login(client)  # plain customer, no cms:page:write
    resp = await client.get("/api/v1/admin/cms/pages")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_deleted_page_can_be_restored(client, db_session):
    await _make_admin(client, db_session)
    create_resp = await client.post(
        "/api/v1/admin/cms/pages",
        json={"slug": "terms", "title": "Terms", "body": "<p>terms</p>", "status": "published"},
    )
    page_id = create_resp.json()["data"]["id"]

    delete_resp = await client.delete(f"/api/v1/admin/cms/pages/{page_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["data"]["is_deleted"] is True

    # A soft-deleted page must not be publicly reachable even though status is still "published".
    assert (await client.get("/api/v1/pages/terms")).status_code == 404

    restore_resp = await client.post(f"/api/v1/admin/cms/pages/{page_id}/restore")
    assert restore_resp.status_code == 200
    assert restore_resp.json()["data"]["is_deleted"] is False
    assert (await client.get("/api/v1/pages/terms")).status_code == 200


async def test_banner_placement_scoping_and_inactive_banners_are_excluded(client, db_session):
    await _make_admin(client, db_session)
    active = await client.post(
        "/api/v1/admin/cms/banners",
        json={"placement": "home_promo", "title": "Sale", "image_url": "http://x/1.jpg", "sort_order": 1},
    )
    assert active.status_code == 201, active.text
    inactive = await client.post(
        "/api/v1/admin/cms/banners",
        json={
            "placement": "home_promo",
            "title": "Old promo",
            "image_url": "http://x/2.jpg",
            "sort_order": 0,
            "is_active": False,
        },
    )
    assert inactive.status_code == 201
    other_placement = await client.post(
        "/api/v1/admin/cms/banners",
        json={"placement": "category_top", "title": "Category banner", "image_url": "http://x/3.jpg"},
    )
    assert other_placement.status_code == 201

    resp = await client.get("/api/v1/banners", params={"placement": "home_promo"})
    assert resp.status_code == 200, resp.text
    titles = [b["title"] for b in resp.json()["data"]]
    assert titles == ["Sale"]  # inactive excluded, other placement excluded, sort_order respected
