"""relax telemetry throttle constraint

Revision ID: 4eb2d85b8e3f
Revises: 6e8255c75f7d
Create Date: 2026-06-29 15:11:04.496034

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4eb2d85b8e3f'
down_revision: Union[str, None] = '6e8255c75f7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('ck_telemetry_throttle_range', 'telemetry', type_='check')
    op.create_check_constraint(
        'ck_telemetry_throttle_non_negative', 'telemetry', 'throttle IS NULL OR throttle >= 0'
    )


def downgrade() -> None:
    op.drop_constraint('ck_telemetry_throttle_non_negative', 'telemetry', type_='check')
    op.create_check_constraint(
        'ck_telemetry_throttle_range', 'telemetry', 'throttle IS NULL OR throttle BETWEEN 0 AND 100'
    )
