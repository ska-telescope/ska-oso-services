"""Constants for component tests.

These are relative API paths used by ``fastapi.testclient.TestClient``,
which mounts the FastAPI app in-process — there is no host/port.
"""

from importlib.metadata import version

OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
KUBE_NAMESPACE = "ska-oso-services"
OSO_SERVICES_BASE_API_URL = f"/{KUBE_NAMESPACE}/oso/api/v{OSO_SERVICES_MAJOR_VERSION}"
ODT_BASE_API_URL = f"{OSO_SERVICES_BASE_API_URL}/odt"
PHT_BASE_API_URL = f"{OSO_SERVICES_BASE_API_URL}/pht"
ENGINEERING_BASE_API_URL = f"{OSO_SERVICES_BASE_API_URL}/engineering"
