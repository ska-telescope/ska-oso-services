"""
ska_oso_services
"""
import os
from importlib.metadata import version
from typing import Any, Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ska_db_oda.rest import PdmJsonEncoder
from ska_db_oda.rest.flask_oda import FlaskODA


KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE", "ska-oso-services")
OSO_SERVICES_MAJOR_VERSION = version("ska-oso-services").split(".")[0]
# The base path includes the namespace which is known at runtime
# to avoid clashes in deployments, for example in CICD
API_PATH = f"/{KUBE_NAMESPACE}/odt/api/v{OSO_SERVICES_MAJOR_VERSION}"

oda = FlaskODA()



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

    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


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
