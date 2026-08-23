"""support-mcp (chat_spec.md §4.3). Scoped to the authenticated user's own records.

**`user_id` on every tool below is a real function parameter, but it is NEVER part of the JSON
schema the bridge (M3) exposes to DeepSeek.** MCP itself has no per-argument visibility control, so
the enforcement point is the bridge: it builds the OpenAI-style `tools[]` payload from each tool's
inputSchema *minus* `user_id`, and always injects the session's own user_id into the actual
`tools/call` request itself — the model never sees the field, let alone sets it. This is the same
guarantee spec §4.3 describes ("injected server-side from the session, never passed by the
model"), just implemented at the bridge layer since MCP has no native concept of a hidden argument.
Every tool re-derives ownership from `user_id`, never trusts an id alone — an order_number or
order_item_id that exists but belongs to someone else 404s exactly like one that doesn't exist.
"""

from __future__ import annotations

import datetime
import re

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ulid import ULID

from app.core.config import get_settings
from app.core.timeutil import utcnow
from app.mcp.common import primary_session, to_jsonable
from app.models.auth import User
from app.models.cms import CmsPage
from app.models.commerce import Order, OrderItem, Refund, Return, Shipment
from app.models.support import SupportTicket, TicketMessage

mcp = FastMCP(name="support-mcp", instructions="Order status, returns, refunds, and support tickets for the authenticated user only.")


def _order_card(order: Order) -> dict:
    return {
        "order_number": order.order_number,
        "status": order.status,
        "payment_status": order.payment_status,
        "fulfilment_status": order.fulfilment_status,
        "grand_total": order.grand_total,
        "currency": order.currency,
        "placed_at": order.created_at,
        "promised_delivery_from": order.promised_delivery_from,
        "promised_delivery_to": order.promised_delivery_to,
        "delivered_at": order.delivered_at,
        "items": [
            {
                "order_item_id": item.id,
                "title": item.title_snapshot,
                "size": item.size_snapshot,
                "color": item.color_snapshot,
                "quantity": item.quantity,
                "line_total": item.line_total,
            }
            for item in order.items
        ],
    }


@mcp.tool()
async def get_order_status(user_id: int, order_number: str) -> dict:
    """Order status and tracking for one order, addressed by its order_number. 404s (returns
    {"error": "not_found"}) if the order doesn't belong to this user — same response whether the
    order_number is wrong or just not theirs, so ownership can't be probed."""
    async with primary_session() as session:
        stmt = (
            select(Order)
            .where(Order.order_number == order_number, Order.user_id == user_id)
            .options(selectinload(Order.items))
        )
        order = (await session.execute(stmt)).scalar_one_or_none()
        if order is None:
            return {"error": "not_found", "order_number": order_number}

        shipment_stmt = select(Shipment).where(Shipment.order_id == order.id).order_by(Shipment.created_at.desc())
        shipment = (await session.execute(shipment_stmt)).scalars().first()

        card = _order_card(order)
        card["shipment"] = (
            {
                "carrier": shipment.carrier,
                "tracking_number": shipment.tracking_number,
                "status": shipment.status,
                "estimated_delivery_at": shipment.estimated_delivery_at,
            }
            if shipment
            else None
        )
        return to_jsonable(card)


@mcp.tool()
async def list_my_recent_orders(user_id: int, limit: int = 10) -> dict:
    """This user's most recent orders, newest first. Max 10 regardless of what's requested."""
    limit = max(1, min(limit, 10))
    async with primary_session() as session:
        stmt = (
            select(Order)
            .where(Order.user_id == user_id)
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        orders = list((await session.execute(stmt)).scalars().all())
        return to_jsonable({"count": len(orders), "orders": [_order_card(o) for o in orders]})


async def _owned_order_item(session, user_id: int, order_item_id: int) -> tuple[OrderItem, Order] | None:
    stmt = (
        select(OrderItem, Order)
        .join(Order, OrderItem.order_id == Order.id)
        .where(OrderItem.id == order_item_id, Order.user_id == user_id)
    )
    row = (await session.execute(stmt)).first()
    return (row[0], row[1]) if row else None


async def _eligibility(session, user_id: int, order_item_id: int) -> dict:
    settings = get_settings()
    owned = await _owned_order_item(session, user_id, order_item_id)
    if owned is None:
        return {"eligible": False, "reason": "not_found"}
    item, order = owned

    if order.delivered_at is None:
        return {"eligible": False, "reason": "not_yet_delivered", "order_item_id": order_item_id}

    deadline = order.delivered_at + datetime.timedelta(days=settings.return_window_days)
    if utcnow() > deadline:
        return {
            "eligible": False,
            "reason": "window_expired",
            "order_item_id": order_item_id,
            "delivered_at": order.delivered_at,
            "window_closed_at": deadline,
        }

    existing_stmt = select(Return).where(
        Return.order_item_id == order_item_id,
        Return.status.notin_(("rejected", "cancelled")),
    )
    existing = (await session.execute(existing_stmt)).scalars().first()
    if existing is not None:
        return {
            "eligible": False,
            "reason": "already_requested",
            "order_item_id": order_item_id,
            "existing_return_status": existing.status,
        }

    return {
        "eligible": True,
        "order_item_id": order_item_id,
        "delivered_at": order.delivered_at,
        "window_closes_at": deadline,
    }


@mcp.tool()
async def get_return_eligibility(user_id: int, order_item_id: int) -> dict:
    """Return window, condition rules, and computed eligibility for one order item."""
    async with primary_session() as session:
        result = await _eligibility(session, user_id, order_item_id)
        return to_jsonable(result)


@mcp.tool()
async def initiate_return(user_id: int, order_item_id: int, reason_code: str) -> dict:
    """Creates a return (RMA) draft. The agent must have restated the item and reason and gotten
    explicit user confirmation before calling this — it is not re-confirmed here. Always
    re-validates eligibility itself rather than trusting a prior get_return_eligibility call."""
    async with primary_session() as session:
        eligibility = await _eligibility(session, user_id, order_item_id)
        if not eligibility["eligible"]:
            return to_jsonable({"created": False, **eligibility})

        rma = Return(
            public_id=str(ULID()),
            order_item_id=order_item_id,
            user_id=user_id,
            reason_code=reason_code,
            status="requested",
        )
        session.add(rma)
        await session.commit()
        return to_jsonable(
            {"created": True, "rma_id": rma.public_id, "order_item_id": order_item_id, "status": rma.status}
        )


@mcp.tool()
async def get_refund_status(user_id: int, refund_id: str | None = None, order_number: str | None = None) -> dict:
    """Refund stage and expected settlement date, addressed by refund_id (transaction_id) or the
    parent order_number. Exactly one of the two should be given."""
    if not refund_id and not order_number:
        return {"error": "invalid_arguments", "message": "Provide refund_id or order_number."}

    async with primary_session() as session:
        stmt = (
            select(Refund, Order.currency)
            .join(Order, Refund.order_id == Order.id)
            .where(Order.user_id == user_id)
        )
        if refund_id:
            stmt = stmt.where(Refund.transaction_id == refund_id)
        else:
            stmt = stmt.where(Order.order_number == order_number)
        stmt = stmt.order_by(Refund.created_at.desc())

        row = (await session.execute(stmt)).first()
        if row is None:
            return {"error": "not_found"}
        refund, currency = row
        return to_jsonable(
            {
                "refund_id": refund.transaction_id,
                "amount": refund.amount,
                "currency": currency,
                "status": refund.status,
                "reason": refund.reason,
                "requested_at": refund.created_at,
                "processed_at": refund.processed_at,
            }
        )


_STOPWORDS = {"the", "a", "an", "is", "are", "to", "for", "of", "and", "or", "my", "i", "in", "on", "do", "does", "how"}


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS and len(t) > 1]


def _split_sections(slug: str, title: str, body: str) -> list[dict]:
    """Splits a CmsPage body on `## Heading` markdown into (heading, text, anchor) sections —
    every policy page seeded by scripts/seed_policy_pages.py is written this way. A page with no
    `##` headings is treated as one section under the page's own title."""
    parts = re.split(r"(?m)^##\s+(.+)$", body)
    if len(parts) == 1:
        return [{"heading": title, "text": body.strip(), "anchor": _anchor(title)}]
    sections = []
    # parts[0] is any preamble before the first heading; then alternating heading/text pairs.
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        text = parts[i + 1].strip() if i + 1 < len(parts) else ""
        sections.append({"heading": heading, "text": text, "anchor": _anchor(heading)})
    return sections


def _anchor(heading: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")


@mcp.tool()
async def search_policy_kb(query: str, top_k: int = 3) -> dict:
    """Keyword search over published store policy pages (shipping, returns, refunds, sizing,
    payment methods). Returns retrieved passages with a citation anchor — quote timelines and
    rules from these results, never from memory."""
    top_k = max(1, min(top_k, 10))
    tokens = _tokenize(query)
    settings = get_settings()

    async with primary_session() as session:
        stmt = select(CmsPage).where(CmsPage.status == "published")
        pages = list((await session.execute(stmt)).scalars().all())

        scored: list[tuple[int, dict, CmsPage]] = []
        for page in pages:
            for section in _split_sections(page.slug, page.title, page.body):
                haystack = f"{page.title} {section['heading']} {section['text']}".lower()
                score = sum(haystack.count(t) for t in tokens) if tokens else 0
                if score > 0:
                    scored.append((score, section, page))

        scored.sort(key=lambda row: row[0], reverse=True)
        results = [
            {
                "doc_slug": page.slug,
                "doc_title": page.title,
                "heading": section["heading"],
                "excerpt": section["text"][:500],
                "policy_url": f"{settings.app_base_url}/pages/{page.slug}#{section['anchor']}",
            }
            for _, section, page in scored[:top_k]
        ]
        return to_jsonable({"count": len(results), "results": results})


@mcp.tool()
async def create_support_ticket(user_id: int, subject: str, body: str, category: str) -> dict:
    """Escalates to a human. Reuses the existing support ticket system — the same one staff use
    in the admin console."""
    async with primary_session() as session:
        contact_email = (await session.execute(select(User.email).where(User.id == user_id))).scalar_one()

        ticket = SupportTicket(
            public_id=str(ULID()),
            user_id=user_id,
            contact_email=contact_email,
            subject=subject,
            status="open",
            priority="medium",
        )
        session.add(ticket)
        await session.flush()
        session.add(TicketMessage(ticket_id=ticket.id, author_user_id=user_id, author_type="customer", body=body,
                                   created_at=utcnow()))
        await session.commit()
        return to_jsonable({"created": True, "ticket_id": ticket.public_id, "category": category, "status": ticket.status})
