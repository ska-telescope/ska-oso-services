import os

from ska_oso_services.app import OSO_SERVICES_MAJOR_VERSION

KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE", "ska-oso-services")
OSO_SERVICES_URL = os.getenv(
    "OSO_SERVICES_URL",
    "http://192.168.49.2"
    f"/{KUBE_NAMESPACE}/oso/api/v0",
)
ODT_URL = f"{OSO_SERVICES_URL}/odt"
