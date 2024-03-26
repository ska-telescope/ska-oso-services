"""
Encoding and decoding functionality to be used by the Flask Application
"""
import json
from datetime import datetime

from ska_oso_pdm.generated.encoder import JSONEncoder
from ska_oso_pdm.generated.models.sb_definition import SBDefinition

from ska_oso_odt_services.generated.encoder import JSONEncoder as LocalJSONEncoder
from ska_oso_odt_services.generated.models.base_model_ import Model


class CustomJSONEncoder(JSONEncoder):
    """
    Extension of the generated JSONEncoder, allowing us to customise the
    encoding without editing generated code
    """

    JSONEncoder.include_nulls = False

    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, Model):
            return LocalJSONEncoder.default(self, o)
        return JSONEncoder.default(self, o)


def decode(json_data: str) -> SBDefinition:
    """
    Create an instance of an SBDefinition from a JSON string.
    """
    return SBDefinition.from_dict(json.loads(json_data))


def encode(obj: SBDefinition) -> str:
    """
    Return a string JSON representation of an SBDefinition instance.
    """
    return json.dumps(obj, cls=CustomJSONEncoder)
