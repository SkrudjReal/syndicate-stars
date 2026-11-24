"""Record explicit welcome confirmation separately from historical delivery."""
from alembic import op
import sqlalchemy as sa

revision = 'c708e5f14d30'
down_revision = 'b6f7d4e03c29'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('welcome_accepted', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('users', 'welcome_accepted')
