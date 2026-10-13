"""Explicit additive migration for the manual RT ledger. No automatic startup DDL."""
from sqlalchemy import inspect
from radiotherapy import TABLES

def apply(m):
    wanted=[m.db.metadata.tables[name] for name in TABLES]
    assert set(t.name for t in wanted)==set(TABLES)
    with m.db.engine.begin() as connection:
        before=set(inspect(connection).get_table_names())
        # Dependencies are existing RIS tables; create only these six new ledger tables.
        m.db.metadata.create_all(bind=connection,tables=wanted,checkfirst=True)
        after=set(inspect(connection).get_table_names())
        assert after-before <= set(TABLES)
        assert set(TABLES) <= after
    return {'migration':'manual_rt_ledger_v1','created_tables':sorted(after-before),'existing_tables_not_altered':True}
