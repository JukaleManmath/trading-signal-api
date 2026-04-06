"""Add 'pending' to SuccessCriteria enum

Revision ID: 4f2a031b5f0c
Revises: d60412b84bf9
Create Date: 2025-06-14 14:23:11.308853

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f2a031b5f0c'
down_revision: Union[str, None] = 'd60412b84bf9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE successcriteria ADD VALUE IF NOT EXISTS 'pending'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
