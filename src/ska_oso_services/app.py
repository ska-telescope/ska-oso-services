"""
ska_oso_services app.py
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ska_oso_services import odt
from ska_oso_services.common import (
    dangerous_internal_server_handler,
    oda_not_found_handler,
)


def create_app(production=True) -> FastAPI:
    """
    Create the Connexion application with required config
    """

    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    # Assemble the constituent APIs:
    app.include_router(odt.router)
    # app.include_router(ptt.router)...
    app.exception_handler(KeyError)(oda_not_found_handler)
    if not production:
        app.exception_handler(Exception)(dangerous_internal_server_handler)
    return app


main = create_app()
