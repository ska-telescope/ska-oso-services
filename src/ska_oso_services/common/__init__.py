from ska_db_oda.persistence.fastapicontext import FastAPIContext

from .error_handling import dangerous_internal_server_handler, oda_not_found_handler

oda = FastAPIContext()
