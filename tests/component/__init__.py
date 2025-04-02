import os

from ska_oso_services.app import OSO_SERVICES_MAJOR_VERSION

KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE", "ska-oso-services")
OSO_SERVICES_URL = os.getenv(
    "OSO_SERVICES_URL",
    "http://ska-oso-services-rest-test:5000"
    f"/{KUBE_NAMESPACE}/oso/api/v{OSO_SERVICES_MAJOR_VERSION}",
)
ODT_URL = f"{OSO_SERVICES_URL}/odt"
