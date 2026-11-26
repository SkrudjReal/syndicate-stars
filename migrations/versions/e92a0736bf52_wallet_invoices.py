"""Persist direct wallet invoices and delivery claims."""
from alembic import op
import sqlalchemy as sa

revision = 'e92a0736bf52'
down_revision = 'd819f6a25e41'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'wallet_invoices',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('order_id', sa.String(32), nullable=False, unique=True),
        sa.Column('bot_id', sa.BigInteger(), nullable=False),
        sa.Column('buyer_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('recipient', sa.String(32), nullable=False),
        sa.Column('product', sa.String(10), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('asset', sa.String(4), nullable=False),
        sa.Column('receiver', sa.String(100), nullable=False),
        sa.Column('atomic_amount', sa.Numeric(30, 0), nullable=False),
        sa.Column('base_stars', sa.Numeric(20, 8), nullable=False),
        sa.Column('created', sa.BigInteger(), nullable=False),
        sa.Column('expires', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('transaction', sa.String(64), nullable=True, unique=True),
        sa.Column('delivery_transaction', sa.String(128), nullable=True),
    )
    op.create_index('ix_wallet_invoices_bot_id', 'wallet_invoices', ['bot_id'])
    op.create_index('ix_wallet_invoices_status', 'wallet_invoices', ['status'])


def downgrade():
    op.drop_table('wallet_invoices')
