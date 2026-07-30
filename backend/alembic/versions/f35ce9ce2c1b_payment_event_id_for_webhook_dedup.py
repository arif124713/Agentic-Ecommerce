"""payment_event_id_for_webhook_dedup

Revision ID: f35ce9ce2c1b
Revises: be87372a85fd
Create Date: 2026-07-31 02:16:45.422228

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f35ce9ce2c1b'
down_revision: Union[str, None] = 'be87372a85fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable first, then backfilled, then tightened to NOT NULL — existing payment_events rows
    # (written before this webhook-dedup column existed) need a synthetic-but-unique value before
    # the NOT NULL + UNIQUE constraints can apply.
    op.add_column('payment_events', sa.Column('event_id', sa.String(length=64), nullable=True))
    op.execute("UPDATE payment_events SET event_id = CONCAT('legacy_', id) WHERE event_id IS NULL")
    op.alter_column('payment_events', 'event_id', existing_type=sa.String(length=64), nullable=False)
    op.create_unique_constraint('uq_payment_events_event_id', 'payment_events', ['event_id'])


def downgrade() -> None:
    op.drop_constraint('uq_payment_events_event_id', 'payment_events', type_='unique')
    op.drop_column('payment_events', 'event_id')
