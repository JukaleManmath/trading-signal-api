"""Setting default status to 'pending'

Revision ID: a8565285d7ea
Revises: 4f2a031b5f0c
Create Date: 2025-06-14 14:24:41.097884

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8565285d7ea'
down_revision: Union[str, None] = '4f2a031b5f0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # op.alter_column(
    #     'polling_jobs',
    #     'status',
    #     server_default=sa.text("'pending'"),
    #     existing_type=sa.Enum('success', 'failed', 'pending', name='successcriteria')
    # )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'polling_jobs',
        'status',
        server_default=sa.text("'failed'"),
        existing_type=sa.Enum('success', 'failed', 'pending', name='successcriteria')
    )

