"""Persist expected payment amounts and verified notifications."""
from alembic import op
import sqlalchemy as sa

revision = 'd819f6a25e41'
down_revision = 'c708e5f14d30'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'notification_orders',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('payment_id', sa.String(100), nullable=False, unique=True),
        sa.Column('shop_id', sa.BigInteger(), nullable=False),
        sa.Column('amount', sa.Numeric(20, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('provider_payment_id', sa.String(100), nullable=True, unique=True),
        sa.Column('confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_table('notification_orders')
