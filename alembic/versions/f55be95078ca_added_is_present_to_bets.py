"""added is_present to bets

Revision ID: f55be95078ca
Revises: a6ff20405cf2
Create Date: 2025-04-30 11:43:41.520689

"""

import sqlalchemy as sa

from alembic import op

revision = "f55be95078ca"
down_revision = "a6ff20405cf2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_present", sa.Boolean(), nullable=False, server_default=sa.true()
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("is_present")
