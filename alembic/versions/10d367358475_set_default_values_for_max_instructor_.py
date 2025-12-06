"""set default values for max instructor and max teaching assistant

Revision ID: 10d367358475
Revises: 902159baef27
Create Date: 2025-12-06 17:25:58.918873

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10d367358475'
down_revision: Union[str, Sequence[str], None] = '902159baef27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE events
        SET max_instructor = 0
        WHERE max_instructor IS NULL;
    """)

    op.execute("""
        UPDATE events
        SET max_teaching_assistant = 1
        WHERE max_teaching_assistant IS NULL;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    pass
