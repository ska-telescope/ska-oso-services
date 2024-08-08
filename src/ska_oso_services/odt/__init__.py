from fastapi import FastAPI

from ska_oso_services.odt.api import prjs, sbds

app = FastAPI()
app.include_router(prjs.router)
app.include_router(sbds.router)
