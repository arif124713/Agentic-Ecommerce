"""Seed the RBAC scaffold: roles, permissions, and the role->permission matrix from spec §3.2/§3.3.

Idempotent — safe to re-run. Every new registrant is assigned the `customer` role in
AuthService.register(); this script only needs to run once per environment to create the
roles/permissions themselves. Run: python scripts/seed_rbac.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.auth import Permission, Role  # noqa: E402

ROLES = [
    ("customer", "Customer", "Registered shopper"),
    ("support", "Support Agent", "Handles tickets and order queries"),
    ("catalog_manager", "Catalogue Manager", "Merchandiser: products, categories, inventory, promotions"),
    ("ops_manager", "Operations Manager", "Fulfilment: order status, shipments, refunds"),
    ("admin", "Admin", "Store operator: all business operations"),
    ("super_admin", "Super Admin", "Platform owner: everything, incl. role assignment and system settings"),
]

PERMISSIONS = [
    "catalog:product:read",
    "catalog:product:write",
    "catalog:product:delete",
    "catalog:inventory:write",
    "order:order:read_own",
    "order:order:read_all",
    "order:order:transition",
    "order:refund:issue",
    "promo:coupon:write",
    "review:review:moderate",
    "support:ticket:manage",
    "cms:page:write",
    "iam:user:read",
    "iam:user:assign_role",
    "system:feature_flag:write",
    "system:audit_log:read",
    "analytics:dashboard:read",
]

# RBAC matrix, spec §3.3 — role code -> permission codes.
ROLE_PERMISSIONS = {
    "customer": ["catalog:product:read", "order:order:read_own"],
    "support": [
        "catalog:product:read",
        "order:order:read_own",
        "order:order:read_all",
        "review:review:moderate",
        "support:ticket:manage",
        "iam:user:read",
    ],
    "catalog_manager": [
        "catalog:product:read",
        "catalog:product:write",
        "catalog:product:delete",
        "catalog:inventory:write",
        "order:order:read_own",
        "promo:coupon:write",
        "cms:page:write",
        "analytics:dashboard:read",
    ],
    "ops_manager": [
        "catalog:product:read",
        "catalog:inventory:write",
        "order:order:read_own",
        "order:order:read_all",
        "order:order:transition",
        "order:refund:issue",
        "analytics:dashboard:read",
    ],
    "admin": [
        "catalog:product:read",
        "catalog:product:write",
        "catalog:product:delete",
        "catalog:inventory:write",
        "order:order:read_own",
        "order:order:read_all",
        "order:order:transition",
        "order:refund:issue",
        "promo:coupon:write",
        "review:review:moderate",
        "support:ticket:manage",
        "cms:page:write",
        "iam:user:read",
        "system:audit_log:read",
        "analytics:dashboard:read",
    ],
    "super_admin": PERMISSIONS,  # everything
}


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        permissions_by_code: dict[str, Permission] = {}
        for code in PERMISSIONS:
            existing = (await session.execute(select(Permission).where(Permission.code == code))).scalar_one_or_none()
            if existing is None:
                existing = Permission(code=code, description=code)
                session.add(existing)
                await session.flush()
            permissions_by_code[code] = existing

        for code, name, description in ROLES:
            stmt = select(Role).where(Role.code == code).options(selectinload(Role.permissions))
            role = (await session.execute(stmt)).scalar_one_or_none()
            wanted = {permissions_by_code[p] for p in ROLE_PERMISSIONS[code]}

            if role is None:
                # Assign permissions before adding: once a role is flushed (persistent), touching
                # its never-loaded `.permissions` collection triggers a lazy SELECT, which fails
                # under async SQLAlchemy outside an awaited context (MissingGreenlet). Setting it
                # here, while the object is still transient, is a pure in-memory assignment.
                role = Role(code=code, name=name, description=description, is_system=True, permissions=list(wanted))
                session.add(role)
            else:
                current = set(role.permissions)
                for perm in wanted - current:
                    role.permissions.append(perm)

        await session.commit()
        print(f"Seeded {len(ROLES)} roles and {len(PERMISSIONS)} permissions.")


if __name__ == "__main__":
    asyncio.run(seed())
