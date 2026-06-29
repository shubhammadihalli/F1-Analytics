"""relax telemetry brake constraint

Revision ID: 6e8255c75f7d
Revises: 829cdde0d3ff
Create Date: 2026-06-29 15:08:28.480619

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '6e8255c75f7d'
down_revision: Union[str, None] = '829cdde0d3ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('ck_telemetry_brake_range', 'telemetry', type_='check')
    op.create_check_constraint(
        'ck_telemetry_brake_non_negative', 'telemetry', 'brake IS NULL OR brake >= 0'
    )


def downgrade() -> None:
    op.drop_constraint('ck_telemetry_brake_non_negative', 'telemetry', type_='check')
    op.create_check_constraint(
        'ck_telemetry_brake_range', 'telemetry', 'brake IS NULL OR brake BETWEEN 0 AND 100'
    )
