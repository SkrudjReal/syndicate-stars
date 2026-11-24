"""Cache Telegram photo file IDs across chats and restarts."""
from alembic import op
import sqlalchemy as sa

revision = '82c4a9b17e31'
down_revision = '6f73b7c2724d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'telegram_photos',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('bot_id', sa.BigInteger(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('file_id', sa.String(512), nullable=False),
        sa.UniqueConstraint('bot_id', 'sha256'),
    )


def downgrade():
    op.drop_table('telegram_photos')
