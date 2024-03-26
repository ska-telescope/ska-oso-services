"""
Tests for the encoding and decoding of the requests/responses to model objects
"""

from ska_oso_pdm.generated.models.sb_definition import SBDefinition
from ska_oso_pdm.openapi import CODEC as OPENAPI_CODEC

from .util import VALID_MID_SBDEFINITION_JSON, assert_json_is_equal


def test_mid_sbd_codec():
    """
    Test that the model decoder and encoder works correctly by decoding a
    string into the model then encoding it back to a string
    """
    # Decode string into model object
    model = OPENAPI_CODEC.loads(SBDefinition, VALID_MID_SBDEFINITION_JSON)

    # Encode model back into json
    result = OPENAPI_CODEC.dumps(model)

    assert_json_is_equal(result, VALID_MID_SBDEFINITION_JSON)
