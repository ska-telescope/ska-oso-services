import os

KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE", "ska-oso-services")
OSO_SERVICES_URL = os.environ["OSO_SERVICES_URL"]
ODT_URL = f"{OSO_SERVICES_URL}/odt"
