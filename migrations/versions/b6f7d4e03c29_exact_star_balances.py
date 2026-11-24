"""Use exact hundredths for referral and internal balances."""
from alembic import op
import sqlalchemy as sa

revision = 'b6f7d4e03c29'
down_revision = 'a5e6c3d92b18'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('user_stars', 'stars', type_=sa.Numeric(20, 2), postgresql_using='round(stars::numeric, 2)')


def downgrade():
    op.alter_column('user_stars', 'stars', type_=sa.Float(), postgresql_using='stars::double precision')
