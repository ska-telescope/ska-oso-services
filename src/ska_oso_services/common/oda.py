from os import getenv

from ska_db_oda.persistence.unitofwork.filesystemunitofwork import FilesystemUnitOfWork
from ska_db_oda.persistence.unitofwork.postgresunitofwork import PostgresUnitOfWork

oda = (
    FilesystemUnitOfWork()
    if getenv("ODA_BACKEND_TYPE", "filesystem") == "filesystem"
    else PostgresUnitOfWork()
)
