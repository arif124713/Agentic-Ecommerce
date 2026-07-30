"""mfa_secrets_and_challenge_tokens

Revision ID: 67e8283370b3
Revises: 27cfdf5e6288
Create Date: 2026-07-31 00:44:04.398573

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '67e8283370b3'
down_revision: Union[str, None] = '27cfdf5e6288'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Hand-fixed after autogenerate: the raw output wanted to create the new table's own index as
    # 'ix_password_reset_user' (a name collision with password_reset_tokens' *existing* index —
    # an autogenerate mismatch, not a real rename) and then drop that name off
    # password_reset_tokens itself, which would have broken a table this migration never actually
    # touches. Renamed to the correct 'ix_mfa_challenge_user' and dropped the erroneous drop.
    op.create_table('mfa_challenge_tokens',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.CHAR(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index('ix_mfa_challenge_user', 'mfa_challenge_tokens', ['user_id'], unique=False)
    op.add_column('users', sa.Column('mfa_secret', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('mfa_recovery_codes', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Explicit drop_index call removed (the recurring fix documented in every migration this
    # project has written): drop_table removes the table's own index for free.
    op.drop_column('users', 'mfa_recovery_codes')
    op.drop_column('users', 'mfa_secret')
    op.drop_table('mfa_challenge_tokens')
