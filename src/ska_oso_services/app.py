"""
ska_oso_services app.py
"""

import logging
import os
from importlib.metadata import version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ska_aaa_authhelpers import AuditLogFilter, watchdog
from ska_db_oda.persistence.domain.errors import (
    ODAError,
    ODANotFound,
    UniqueConstraintViolation,
)
from ska_ser_logging import configure_logging

from ska_oso_services import odt, pht
from ska_oso_services.common import api, oda
from ska_oso_services.common.error_handling import (
    dangerous_internal_server_handler,
    oda_error_handler,
    oda_not_found_handler,
    oda_unique_constraint_handler,
)

KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE", "ska-oso-services")
OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
# The base path includes the namespace which is known at runtime
# to avoid clashes in deployments, for example in CICD
API_PREFIX = f"/{KUBE_NAMESPACE}/oso/api/v{OSO_SERVICES_MAJOR_VERSION}"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
PRODUCTION = os.getenv("PRODUCTION", "false").lower() == "true"

LOGGER = logging.getLogger(__name__)


def create_app(production=PRODUCTION) -> FastAPI:
    """
    Create the Connexion application with required config
    """
    configure_logging(level=LOG_LEVEL, tags_filter=AuditLogFilter)
    LOGGER.info("Creating FastAPI app")

    app = FastAPI(
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/ui",
        lifespan=watchdog(
            allow_unsecured=[
                "get_systemcoordinates",
                "create_proposal",
                "get_proposal",
                "get_proposals_for_user",
                "update_proposal",
                "validate_proposal",
                "send_email",
                "create_upload_pdf_url",
                "create_download_pdf_url",
                "create_delete_pdf_url",
                "get_reviewers",
                "create_panel",
            ]
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    # Assemble the constituent APIs:
    app.include_router(api.common_router, prefix=API_PREFIX)
    app.include_router(odt.router, prefix=API_PREFIX)
    app.include_router(pht.router, prefix=API_PREFIX)
    app.exception_handler(ODANotFound)(oda_not_found_handler)
    app.exception_handler(ODAError)(oda_error_handler)
    app.exception_handler(UniqueConstraintViolation)(oda_unique_constraint_handler)

    if not production:
        app.exception_handler(Exception)(dangerous_internal_server_handler)
    return app


main = create_app()
oda.init_app(main)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(main, host="localhost", port=8000)
