"""Promote an existing user to an admin-ish role for local testing.

There's no admin UI to assign the *first* admin (chicken-and-egg — spec doesn't solve this either,
real systems usually seed one via a migration or CLI, which is what this is). Idempotent — running
it twice for the same user just leaves the role assignment as-is.

Usage: python scripts/promote_admin.py <email> [role_code]
       role_code defaults to "admin". One of: catalog_manager, ops_manager, admin, super_admin.
"""

import asyncio
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.auth import Role, User, UserRole  # noqa: E402


async def promote(email: str, role_code: str) -> None:
    async with AsyncSessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email.lower()))
        ).scalar_one_or_none()
        if user is None:
            print(f"No user found with email {email}")
            return

        role = (await session.execute(select(Role).where(Role.code == role_code))).scalar_one_or_none()
        if role is None:
            print(f"No role found with code {role_code} — run scripts/seed_rbac.py first.")
            return

        existing = (
            await session.execute(
                select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
            )
        ).scalar_one_or_none()
        if existing is not None:
            print(f"{email} already has role {role_code}.")
            return

        session.add(UserRole(user_id=user.id, role_id=role.id, granted_at=datetime.datetime.now(datetime.UTC)))
        await session.commit()
        print(f"Granted role {role_code} to {email}.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/promote_admin.py <email> [role_code]")
        sys.exit(1)
    email_arg = sys.argv[1]
    role_arg = sys.argv[2] if len(sys.argv) > 2 else "admin"
    asyncio.run(promote(email_arg, role_arg))
