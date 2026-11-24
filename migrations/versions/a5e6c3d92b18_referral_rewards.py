"""Persistent referral rewards and withdrawal reservations."""
from alembic import op
import sqlalchemy as sa

revision = 'a5e6c3d92b18'
down_revision = '94d5b2c81a07'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'referral_payments',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('provider', sa.String(20), nullable=False),
        sa.Column('payment_id', sa.String(100), nullable=False),
        sa.Column('buyer_id', sa.BigInteger(), nullable=False),
        sa.Column('referrer_id', sa.BigInteger(), nullable=False),
        sa.Column('base_stars', sa.Numeric(20, 8), nullable=False),
        sa.Column('reward_stars', sa.Numeric(20, 2), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('provider', 'payment_id'),
    )
    op.create_index('ix_referral_payments_referrer_id', 'referral_payments', ['referrer_id'])
    op.add_column('user_withdraws', sa.Column('request_id', sa.BigInteger(), nullable=True))
    op.add_column('user_withdraws', sa.Column('status', sa.String(20), nullable=False, server_default='sent'))
    op.add_column('user_withdraws', sa.Column('tx_hash', sa.String(128), nullable=True))
    op.create_unique_constraint('uq_user_withdraws_request', 'user_withdraws', ['user_id', 'request_id'])


def downgrade():
    op.drop_constraint('uq_user_withdraws_request', 'user_withdraws')
    op.drop_column('user_withdraws', 'tx_hash')
    op.drop_column('user_withdraws', 'status')
    op.drop_column('user_withdraws', 'request_id')
    op.drop_table('referral_payments')
