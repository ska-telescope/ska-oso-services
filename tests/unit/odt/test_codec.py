"""
Tests for the encoding and decoding of the requests/responses to model objects
"""

from ska_oso_pdm.openapi import CODEC
from ska_oso_pdm.sb_definition import SBDefinition

from tests.unit.util import VALID_MID_SBDEFINITION_JSON, assert_json_is_equal


def test_mid_sbd_codec():
    """
    Test that the model decoder and encoder works correctly by decoding a
    string into the model then encoding it back to a string
    """
    # Decode string into model object
    model = CODEC.loads(SBDefinition, VALID_MID_SBDEFINITION_JSON)

    # Encode model back into json
    result = CODEC.dumps(model)

    assert_json_is_equal(result, VALID_MID_SBDEFINITION_JSON)
