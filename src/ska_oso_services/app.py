"""
ska_oso_services app.py
"""

import logging
import os
from importlib.metadata import version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from ska_aaa_authhelpers import AuditLogFilter, watchdog
from ska_db_oda.repository.domain import ODAError, ODANotFound, UniqueConstraintViolation
from ska_db_oda.repository.domain.errors import ODAIntegrityError
from ska_ser_logging import configure_logging

from ska_oso_services import odt, pht
from ska_oso_services.common import api, oda
from ska_oso_services.common.error_handling import (
    OSDError,
    dangerous_internal_server_handler,
    oda_error_handler,
    oda_integrity_error_handler,
    oda_not_found_handler,
    oda_unique_constraint_handler,
    osd_error_handler,
    pydantic_validation_error_handler,
)
from ska_oso_services.validation.api.routes import router as validation_router

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
    Create the FastAPI application with required config.

    Note: The application is wrapped with CORSMiddleware at module level
    to ensure CORS headers are included on ALL responses, including error responses
    from exception handlers. FastAPI recommends this approach
    https://github.com/fastapi/fastapi/discussions/8027#discussioncomment-12483840
    """
    configure_logging(level=LOG_LEVEL, tags_filter=AuditLogFilter)
    LOGGER.info("Creating FastAPI app")

    fastapi_app = FastAPI(
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/ui",
        lifespan=watchdog(
            allow_unsecured=["get_systemcoordinates", "get_osd_by_cycle", "visibility_svg", "get_all_osd_cycles"]
        ),
        # Need this param for code generation - see
        # https://fastapi.tiangolo.com/how-to/separate-openapi-schemas
        separate_input_output_schemas=False,
    )

    # Assemble the constituent APIs:
    fastapi_app.include_router(api.common_router, prefix=API_PREFIX)
    fastapi_app.include_router(odt.router, prefix=API_PREFIX)
    fastapi_app.include_router(pht.router, prefix=API_PREFIX)
    fastapi_app.include_router(validation_router, prefix=API_PREFIX)
    fastapi_app.exception_handler(ODANotFound)(oda_not_found_handler)
    fastapi_app.exception_handler(ODAIntegrityError)(oda_integrity_error_handler)
    fastapi_app.exception_handler(ODAError)(oda_error_handler)
    fastapi_app.exception_handler(ValidationError)(pydantic_validation_error_handler)
    fastapi_app.exception_handler(UniqueConstraintViolation)(oda_unique_constraint_handler)
    fastapi_app.exception_handler(OSDError)(osd_error_handler)

    if not production:
        fastapi_app.exception_handler(Exception)(dangerous_internal_server_handler)

    return fastapi_app


# Create the FastAPI app
app = create_app()
oda.init_app(app)

# Wrap with CORSMiddleware to ensure CORS headers are added to all responses,
# including error responses from exception handlers
main = CORSMiddleware(
    app=app,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
    expose_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(main, host="localhost", port=8000)
