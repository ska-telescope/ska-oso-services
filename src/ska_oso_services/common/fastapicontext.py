import os

from fastapi import FastAPI
from ska_db_oda.persistence.unitofwork.filesystemunitofwork import FilesystemUnitOfWork
from ska_db_oda.persistence.unitofwork.postgresunitofwork import (
    PostgresUnitOfWork,
    create_connection_pool,
)

# TODO this is copied directly from ODA 6.2.2. At the end of PI24 we couldn't update
#  past ODA v6.1.0 as didn't want to include PDM v16.
#  Once the ODA is updated, we can remove this and use the ODA version instead


class FastAPIContext(object):
    """
     This is a lightweight 'extension' of the ODA that will manage the creation of
     the UnitOfWork and underlying connection pool for a FastAPI application.

     It should be able to be used in the same way the ODA:

         oda = FastAPIContext(app) (or use oda.init_app(app))

         with oda.uow() as uow:
             uow.sbds.add(...)

    TODO there are more FastAPI friendly ways to do this, using Depends and such.
    """

    def __init__(self, app: FastAPI = None, oda_backend_type: str = None):
        self.app = app
        if oda_backend_type:
            self.oda_backend_type = oda_backend_type
        else:
            self.oda_backend_type = os.getenv("ODA_BACKEND_TYPE", "filesystem")

    def init_app(self, app):
        """
        Initialise ODA Flask extension.
        """
        self.app = app

    def uow(self):
        return (
            PostgresUnitOfWork(self.connection_pool)
            if self.oda_backend_type == "postgres"
            else (
                FilesystemUnitOfWork(base_working_dir=os.getenv("ODA_DATA_DIR"))
                if os.getenv("ODA_DATA_DIR")
                else FilesystemUnitOfWork()
            )
        )

    @property
    def connection_pool(self):
        # Lazy creation of one psycopg ConnectionPool instance per FastAPI application
        if not hasattr(self.app.state, "connection_pool"):
            self.app.state.connection_pool = create_connection_pool()
        return self.app.state.connection_pool
