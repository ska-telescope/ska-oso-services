from os import getenv

from ska_db_oda.persistence.unitofwork.filesystemunitofwork import FilesystemUnitOfWork
from ska_db_oda.persistence.unitofwork.postgresunitofwork import PostgresUnitOfWork

# TODO remove this when updating to ODA v6.2.0
oda = (
    FilesystemUnitOfWork()
    if getenv("ODA_BACKEND_TYPE", "filesystem") == "filesystem"
    else PostgresUnitOfWork()
)
