"""Transform and update proposal data.
This module contains functions to transform and update proposal data
for submission and creation processes.
"""

from typing import Any

from sqlalchemy import Select, Table, and_, select


def select_with_conditions(table: Table, **conditions: Any) -> Select:
    """Build a SQLAlchemy Select statement for the given table with optional filters.

    Arguably a called could just construct `select(TABLES.projects).where(name='name')`
    instead of `select_with_conditions(TABLES.projects, name='name')`
    but this handles some more complex cases and null checks that are used in a lot of
    PHT queries.
    """
    stmt = select(*(c for c in table.columns if not c.info.get("generated")))
    clauses = [
        table.c[key] == getattr(value, "value", value)
        for key, value in conditions.items()
        if value is not None
    ]
    return stmt.where(and_(*clauses)) if clauses else stmt
