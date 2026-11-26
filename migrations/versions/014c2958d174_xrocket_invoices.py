"""Reuse durable delivery claims for xRocket invoices."""
from alembic import op
import sqlalchemy as sa

revision = '014c2958d174'
down_revision = 'f03b1847c063'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('wallet_invoices', sa.Column('provider', sa.String(20), nullable=False, server_default='wallet'))
    op.add_column('wallet_invoices', sa.Column('provider_invoice_id', sa.String(100), nullable=True))
    op.create_unique_constraint('uq_wallet_provider_invoice', 'wallet_invoices', ['provider_invoice_id'])


def downgrade():
    op.drop_constraint('uq_wallet_provider_invoice', 'wallet_invoices', type_='unique')
    op.drop_column('wallet_invoices', 'provider_invoice_id')
    op.drop_column('wallet_invoices', 'provider')
