import os
from importlib.metadata import version

KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE", "ska-oso-services")
OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
# The base path includes the namespace which is known at runtime
# to avoid clashes in deployments, for example in CICD
API_PREFIX = f"/{KUBE_NAMESPACE}/odt/api/v{OSO_SERVICES_MAJOR_VERSION}"

from fastapi import APIRouter

from ska_oso_services.odt.api import prjs, sbds

router = APIRouter(prefix=API_PREFIX, tags=["ODT"])
router.include_router(prjs.router)
router.include_router(sbds.router)
