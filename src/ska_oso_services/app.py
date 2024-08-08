"""
ska_oso_services app.py
"""

import os
from functools import partial
from importlib.metadata import version

KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE", "ska-oso-services")
OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
# The base path includes the namespace which is known at runtime
# to avoid clashes in deployments, for example in CICD
ROUTE_PREFIX = partial(
    "/{namespace}/{service}/api/v{version}".format,
    namespace=KUBE_NAMESPACE,
    version=OSO_SERVICES_MAJOR_VERSION,
)


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
    app.mount(ROUTE_PREFIX(service="odt"), odt.app)
    # app.mount(ROUTE_PREFIX(service='ptt'), ptt.app)
    app.exception_handler(KeyError)(oda_not_found_handler)
    if not production:
        app.exception_handler(Exception)(dangerous_internal_server_handler)
    return app


main = create_app()
