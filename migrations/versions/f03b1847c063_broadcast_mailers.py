"""Persist aiogram_broadcaster mailers without storing bot tokens."""
from alembic import op
import sqlalchemy as sa

revision = 'f03b1847c063'
down_revision = 'e92a0736bf52'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('broadcast_mailers',
                    sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
                    sa.Column('data', sa.String(), nullable=False))


def downgrade():
    op.drop_table('broadcast_mailers')
