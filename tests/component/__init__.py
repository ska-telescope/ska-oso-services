import os
from importlib.metadata import version

KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE", "ska-oso-services")
OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
ODT_URL = os.getenv(
    "ODT_URL",
    "http://ska-oso-services-rest-test:5000"
    f"/{KUBE_NAMESPACE}/odt/api/v{OSO_SERVICES_MAJOR_VERSION}",
)
