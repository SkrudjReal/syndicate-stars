"""Remember first-start welcome delivery."""
from alembic import op
import sqlalchemy as sa

revision = '94d5b2c81a07'
down_revision = '82c4a9b17e31'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('welcome_sent', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('users', 'welcome_sent')
