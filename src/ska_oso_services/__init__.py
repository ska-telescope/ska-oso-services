"""
ska_oso_services
"""
import os
from importlib.metadata import version
from typing import Any, Dict

import prance
from connexion import App
from ska_db_oda.rest.flask_oda import FlaskODA

from ska_oso_services.odt.codec import CustomJSONEncoder

KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE", "ska-oso-services")
OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
# The base path includes the namespace which is known at runtime
# to avoid clashes in deployments, for example in CICD
API_PATH = f"/{KUBE_NAMESPACE}/odt/api/v{OSO_SERVICES_MAJOR_VERSION}"

oda = FlaskODA()


def resolve_openapi_spec() -> Dict[str, Any]:
    """
    Resolves the $ref in the OpenAPI spec before it is used by Connexion,
    as Connexion can't parse them.
    See https://github.com/spec-first/connexion/issues/967
    """
    cwd, _ = os.path.split(__file__)
    path = os.path.join(cwd, "./openapi/odt-openapi-v1.yaml")
    parser = prance.ResolvingParser(path, lazy=True, strict=True)
    parser.parse()
    return parser.specification


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


def create_app(open_api_spec=None) -> App:
    """
    Create the Connexion application with required config
    """

    if open_api_spec is None:
        open_api_spec = resolve_openapi_spec()

    connexion = App(__name__, specification_dir="openapi/")

    connexion.app.json_encoder = CustomJSONEncoder

    def set_default_headers_on_response(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "*"
        return response

    connexion.app.after_request(set_default_headers_on_response)

    validator_map = {
        "body": CustomRequestBodyValidator,
    }
    connexion.add_api(
        open_api_spec,
        arguments={"title": "OpenAPI ODT"},
        base_path=API_PATH,
        pythonic_params=True,
        validator_map=validator_map,
    )

    oda.init_app(connexion.app)

    return connexion
