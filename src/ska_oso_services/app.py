"""
ska_oso_services app.py
"""

import os
from importlib.metadata import version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ska_oso_services import odt
from ska_oso_services.common import (
    dangerous_internal_server_handler,
    oda_not_found_handler,
)

KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE", "ska-oso-services")
OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
# The base path includes the namespace which is known at runtime
# to avoid clashes in deployments, for example in CICD
API_PREFIX = f"/{KUBE_NAMESPACE}/oso/api/v{OSO_SERVICES_MAJOR_VERSION}"


def create_app(production=True) -> FastAPI:
    """
    Create the Connexion application with required config
    """
    app = FastAPI(openapi_url=f"{API_PREFIX}/openapi.json", docs_url=f"{API_PREFIX}/ui")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    # Assemble the constituent APIs:
    app.include_router(odt.router, prefix=API_PREFIX)
    # app.include_router(pht.router)...
    app.exception_handler(KeyError)(oda_not_found_handler)

    if not production:
        app.exception_handler(Exception)(dangerous_internal_server_handler)
    return app


main = create_app()
