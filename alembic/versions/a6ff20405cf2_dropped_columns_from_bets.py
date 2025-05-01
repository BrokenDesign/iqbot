"""dropped columns from bets

Revision ID: a6ff20405cf2
Revises: 9b387848f87f
Create Date: 2025-04-30 10:26:09.042176

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a6ff20405cf2"
down_revision: Union[str, None] = "9b387848f87f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create a new table without the dropped columns
    op.create_table(
        "bets_temp",
        sa.Column("guild_id", sa.Integer, index=True),
        sa.Column("message_id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "timestamp", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
        sa.Column("user_id_1", sa.Integer, index=True),
        sa.Column("user_id_2", sa.Integer, index=True),
    )

    # 2. Copy data from old table (only matching columns)
    op.execute(
        """
        INSERT INTO bets_temp (guild_id, message_id, timestamp, user_id_1, user_id_2)
        SELECT guild_id, message_id, timestamp, user_id_1, user_id_2 FROM bets
    """
    )

    # 3. Drop the old table
    op.drop_table("bets")

    # 4. Rename temp table to original name
    op.rename_table("bets_temp", "bets")


def downgrade() -> None:
    op.create_table(
        "bets_old",
        sa.Column("guild_id", sa.Integer, index=True),
        sa.Column("message_id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "timestamp", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
        sa.Column("user_id_1", sa.Integer, index=True),
        sa.Column("user_id_2", sa.Integer, index=True),
        sa.Column("is_open", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("winner", sa.Integer, nullable=True),
    )

    op.execute(
        """
        INSERT INTO bets_old (guild_id, message_id, timestamp, user_id_1, user_id_2)
        SELECT guild_id, message_id, timestamp, user_id_1, user_id_2 FROM bets
    """
    )

    op.drop_table("bets")
    op.rename_table("bets_old", "bets")
