"""rename races to sessions, add weather positions race_control messages, relationships indexes constraints

Revision ID: 9ca960e64720
Revises: f218a6a6c57e
Create Date: 2026-06-29 14:13:15.205030

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9ca960e64720'
down_revision: Union[str, None] = 'f218a6a6c57e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Renamed in place (instead of autogenerate's drop+create) to preserve
    # already-ingested data. Postgres FKs reference tables by OID, so the
    # existing laps/pit_stops/results foreign keys keep working unchanged.
    op.rename_table('races', 'sessions')
    op.create_index('ix_sessions_circuit_key', 'sessions', ['circuit_key'], unique=False)
    op.create_index('ix_sessions_date_start', 'sessions', ['date_start'], unique=False)
    op.create_index('ix_sessions_year_session_type', 'sessions', ['year', 'session_type'], unique=False)

    op.create_table('messages',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('session_key', sa.Integer(), nullable=False),
    sa.Column('driver_number', sa.Integer(), nullable=False),
    sa.Column('date', sa.DateTime(), nullable=False),
    sa.Column('recording_url', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['driver_number'], ['drivers.driver_number'], ),
    sa.ForeignKeyConstraint(['session_key'], ['sessions.session_key'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('session_key', 'driver_number', 'date', name='uq_messages_session_driver_date')
    )
    op.create_index('ix_messages_driver_number', 'messages', ['driver_number'], unique=False)
    op.create_index('ix_messages_session_key', 'messages', ['session_key'], unique=False)
    op.create_table('positions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('session_key', sa.Integer(), nullable=False),
    sa.Column('driver_number', sa.Integer(), nullable=False),
    sa.Column('date', sa.DateTime(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.CheckConstraint('position > 0', name='ck_positions_position_positive'),
    sa.ForeignKeyConstraint(['driver_number'], ['drivers.driver_number'], ),
    sa.ForeignKeyConstraint(['session_key'], ['sessions.session_key'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('session_key', 'driver_number', 'date', name='uq_positions_session_driver_date')
    )
    op.create_index('ix_positions_driver_number', 'positions', ['driver_number'], unique=False)
    op.create_index('ix_positions_session_key', 'positions', ['session_key'], unique=False)
    op.create_table('race_control',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('session_key', sa.Integer(), nullable=False),
    sa.Column('driver_number', sa.Integer(), nullable=True),
    sa.Column('date', sa.DateTime(), nullable=False),
    sa.Column('category', sa.String(), nullable=True),
    sa.Column('flag', sa.String(), nullable=True),
    sa.Column('scope', sa.String(), nullable=True),
    sa.Column('sector', sa.Integer(), nullable=True),
    sa.Column('lap_number', sa.Integer(), nullable=True),
    sa.Column('message', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['driver_number'], ['drivers.driver_number'], ),
    sa.ForeignKeyConstraint(['session_key'], ['sessions.session_key'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_race_control_category', 'race_control', ['category'], unique=False)
    op.create_index('ix_race_control_session_key', 'race_control', ['session_key'], unique=False)
    op.create_table('weather',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('session_key', sa.Integer(), nullable=False),
    sa.Column('date', sa.DateTime(), nullable=False),
    sa.Column('air_temperature', sa.Float(), nullable=True),
    sa.Column('track_temperature', sa.Float(), nullable=True),
    sa.Column('humidity', sa.Float(), nullable=True),
    sa.Column('pressure', sa.Float(), nullable=True),
    sa.Column('rainfall', sa.Float(), nullable=True),
    sa.Column('wind_direction', sa.Integer(), nullable=True),
    sa.Column('wind_speed', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['session_key'], ['sessions.session_key'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('session_key', 'date', name='uq_weather_session_date')
    )
    op.create_index('ix_weather_session_key', 'weather', ['session_key'], unique=False)

    op.create_index('ix_constructor_standings_team_name', 'constructor_standings', ['team_name'], unique=False)
    op.create_check_constraint(
        'ck_constructor_standings_points_non_negative', 'constructor_standings', 'points >= 0'
    )
    op.create_check_constraint(
        'ck_constructor_standings_wins_non_negative', 'constructor_standings', 'wins >= 0'
    )
    op.create_check_constraint(
        'ck_constructor_standings_position_positive',
        'constructor_standings',
        'position IS NULL OR position > 0',
    )

    op.create_index('ix_driver_standings_driver_number', 'driver_standings', ['driver_number'], unique=False)
    op.create_check_constraint(
        'ck_driver_standings_points_non_negative', 'driver_standings', 'points >= 0'
    )
    op.create_check_constraint('ck_driver_standings_wins_non_negative', 'driver_standings', 'wins >= 0')
    op.create_check_constraint(
        'ck_driver_standings_position_positive', 'driver_standings', 'position IS NULL OR position > 0'
    )

    op.create_index('ix_drivers_team_name', 'drivers', ['team_name'], unique=False)

    op.create_index('ix_laps_driver_number', 'laps', ['driver_number'], unique=False)
    op.create_check_constraint('ck_laps_lap_number_positive', 'laps', 'lap_number > 0')

    op.create_index('ix_pit_stops_driver_number', 'pit_stops', ['driver_number'], unique=False)
    op.create_check_constraint('ck_pit_stops_lap_number_positive', 'pit_stops', 'lap_number > 0')

    op.create_index('ix_results_driver_number', 'results', ['driver_number'], unique=False)
    op.create_check_constraint(
        'ck_results_position_positive', 'results', 'position IS NULL OR position > 0'
    )
    op.create_check_constraint(
        'ck_results_points_non_negative', 'results', 'points IS NULL OR points >= 0'
    )


def downgrade() -> None:
    op.drop_constraint('ck_results_points_non_negative', 'results', type_='check')
    op.drop_constraint('ck_results_position_positive', 'results', type_='check')
    op.drop_index('ix_results_driver_number', table_name='results')

    op.drop_constraint('ck_pit_stops_lap_number_positive', 'pit_stops', type_='check')
    op.drop_index('ix_pit_stops_driver_number', table_name='pit_stops')

    op.drop_constraint('ck_laps_lap_number_positive', 'laps', type_='check')
    op.drop_index('ix_laps_driver_number', table_name='laps')

    op.drop_index('ix_drivers_team_name', table_name='drivers')

    op.drop_constraint('ck_driver_standings_position_positive', 'driver_standings', type_='check')
    op.drop_constraint('ck_driver_standings_wins_non_negative', 'driver_standings', type_='check')
    op.drop_constraint('ck_driver_standings_points_non_negative', 'driver_standings', type_='check')
    op.drop_index('ix_driver_standings_driver_number', table_name='driver_standings')

    op.drop_constraint('ck_constructor_standings_position_positive', 'constructor_standings', type_='check')
    op.drop_constraint('ck_constructor_standings_wins_non_negative', 'constructor_standings', type_='check')
    op.drop_constraint('ck_constructor_standings_points_non_negative', 'constructor_standings', type_='check')
    op.drop_index('ix_constructor_standings_team_name', table_name='constructor_standings')

    op.drop_index('ix_weather_session_key', table_name='weather')
    op.drop_table('weather')
    op.drop_index('ix_race_control_session_key', table_name='race_control')
    op.drop_index('ix_race_control_category', table_name='race_control')
    op.drop_table('race_control')
    op.drop_index('ix_positions_session_key', table_name='positions')
    op.drop_index('ix_positions_driver_number', table_name='positions')
    op.drop_table('positions')
    op.drop_index('ix_messages_session_key', table_name='messages')
    op.drop_index('ix_messages_driver_number', table_name='messages')
    op.drop_table('messages')

    op.drop_index('ix_sessions_year_session_type', table_name='sessions')
    op.drop_index('ix_sessions_date_start', table_name='sessions')
    op.drop_index('ix_sessions_circuit_key', table_name='sessions')
    op.rename_table('sessions', 'races')
