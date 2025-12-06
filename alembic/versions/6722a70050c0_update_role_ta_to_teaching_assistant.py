"""update_role_ta_to_teaching_assistant

Revision ID: 6722a70050c0
Revises: 039a20763678
Create Date: 2025-12-06 18:02:04.297237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6722a70050c0'
down_revision: Union[str, Sequence[str], None] = '039a20763678'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("UPDATE user_event SET role = 'teaching_assistant' WHERE role = 'ta'")   
    


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE user_event SET role = 'ta' WHERE role = 'teaching_assistant'")
