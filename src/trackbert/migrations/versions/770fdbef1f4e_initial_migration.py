"""Initial migration

Revision ID: 770fdbef1f4e
Revises: 
Create Date: 2023-08-29 10:01:10.100731

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.exc import ProgrammingError, OperationalError

import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "770fdbef1f4e"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not table_exists("shipments"):
        op.create_table(
            "shipments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tracking_number", sa.String(), nullable=True),
            sa.Column("carrier", sa.String(), nullable=True),
            sa.Column("description", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if not table_exists("events"):
        op.create_table(
            "events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("event_time", sa.String(), nullable=True),
            sa.Column("event_description", sa.String(), nullable=True),
            sa.Column("raw_event", sa.String(), nullable=True),
            sa.Column("shipment_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["shipment_id"],
                ["shipments.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    op.drop_table("events")
    op.drop_table("shipments")


def table_exists(table_name):
    try:
        op.execute(f'SELECT 1 FROM "{table_name}" LIMIT 1;')
        return True
    except (OperationalError, ProgrammingError):
        return False
