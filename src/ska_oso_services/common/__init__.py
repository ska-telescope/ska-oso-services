from ska_db_oda.unitofwork.postgresunitofwork import PostgresUnitOfWork


class _ODA:
    """Thin wrapper to keep the oda.uow() call pattern used in PHT APIs."""

    def uow(self):
        return PostgresUnitOfWork()


oda = _ODA()
