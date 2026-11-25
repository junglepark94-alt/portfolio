from sqlalchemy import inspect

import schema as schema_mod
from app import db


def _columns(table):
    return {c["name"] for c in inspect(db.engine).get_columns(table)}


def test_up_to_date_schema_runs_no_alter_statements(portfolio_app):
    with db.engine.connect() as conn:
        assert schema_mod._missing_column_migrations(conn) == []


def test_missing_column_is_added_once(portfolio_app, monkeypatch):
    monkeypatch.setattr(schema_mod, "start_boot_network_tasks", lambda: None)
    with db.engine.connect() as conn:
        conn.execute(db.text("ALTER TABLE visit_event DROP COLUMN source"))
        conn.commit()
    assert "source" not in _columns("visit_event")

    with db.engine.connect() as conn:
        assert schema_mod._missing_column_migrations(conn) == [
            "ALTER TABLE visit_event ADD COLUMN source VARCHAR(40) DEFAULT ''"]

    schema_mod.init_db()
    assert "source" in _columns("visit_event")
    with db.engine.connect() as conn:
        assert schema_mod._missing_column_migrations(conn) == []


def test_every_migration_targets_a_model_column(portfolio_app):
    """목록의 ALTER 문이 실제 모델 컬럼과 어긋나면(오타 등) 테스트가 잡는다."""
    for sql in schema_mod.ADD_COLUMN_MIGRATIONS:
        table, column = schema_mod._ADD_COLUMN_RE.match(sql).groups()
        assert column in _columns(table), sql


def test_kpi_widening_is_skipped_on_sqlite(portfolio_app):
    with db.engine.connect() as conn:
        schema_mod._widen_kpi_column(conn)  # SQLite에서는 아무것도 하지 않아야 한다
