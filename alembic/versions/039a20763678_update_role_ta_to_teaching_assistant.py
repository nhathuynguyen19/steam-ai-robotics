"""update_role_ta_to_teaching_assistant

Revision ID: 039a20763678
Revises: 10d367358475
Create Date: 2025-12-06 18:01:09.553494

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '039a20763678'
down_revision: Union[str, Sequence[str], None] = '10d367358475'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
