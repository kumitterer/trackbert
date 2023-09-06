"""Shipment.disabled

Revision ID: 91ca1665ca83
Revises: 770fdbef1f4e
Create Date: 2023-09-06 11:44:48.214655

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91ca1665ca83'
down_revision: Union[str, None] = '770fdbef1f4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('shipments', sa.Column('disabled', sa.Boolean(), nullable=True))
    op.execute("UPDATE shipments SET disabled = true WHERE carrier = ''")


def downgrade() -> None:
    op.execute("UPDATE shipments SET carrier = '' WHERE disabled = true")
    op.drop_column('shipments', 'disabled')
