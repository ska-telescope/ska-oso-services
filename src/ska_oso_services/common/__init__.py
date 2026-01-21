from ska_db_oda.rest.fastapicontext import FastAPIContext

# use of this is deprecated - inject the
# ska_db_oda.persistence.fastapicontext.UnitOfWork Dependency instead
oda = FastAPIContext()
