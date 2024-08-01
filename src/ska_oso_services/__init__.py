"""
ska_oso_services
"""

import os
from importlib.metadata import version
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ska_oso_services.common import (
    dangerous_internal_server_handler,
    oda,
    oda_not_found_handler,
)
from ska_oso_services.odt.api.prjs import router as projects_router
from ska_oso_services.odt.api.sbds import router as sbds_router

KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE", "ska-oso-services")
OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
# The base path includes the namespace which is known at runtime
# to avoid clashes in deployments, for example in CICD
API_PATH = f"/{KUBE_NAMESPACE}/odt/api/v{OSO_SERVICES_MAJOR_VERSION}"


class CustomRequestBodyValidator:  # pylint: disable=too-few-public-methods
    """
        There is a (another) issue with Connexion where it cannot validate against a
        spec with polymorphism, like the SBDefinition.
    See https://github.com/spec-first/connexion/issues/1569
    As a temporary hack, this basically turns off the validation
    """

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, function):
        return function


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
    app.include_router(projects_router)
    app.include_router(sbds_router)
    app.exception_handler(KeyError)(oda_not_found_handler)
    if not production:
        app.exception_handler(Exception)(dangerous_internal_server_handler)
    return app
