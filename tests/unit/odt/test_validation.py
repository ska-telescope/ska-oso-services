from unittest import mock

from ska_oso_pdm.sb_definition import SBDefinition

from ska_oso_services.odt.validation import validate_sbd
from tests.unit.util import VALID_LOW_SBDEFINITION_JSON, VALID_MID_SBDEFINITION_JSON


def test_valid_sbd_returns_no_messages():
    sbd = SBDefinition.model_validate_json(VALID_MID_SBDEFINITION_JSON)
    result = validate_sbd(sbd)
    assert result == {}


def test_valid_low_sbd_returns_no_messages():
    sbd = SBDefinition.model_validate_json(VALID_LOW_SBDEFINITION_JSON)
    result = validate_sbd(sbd)
    assert result == {}


def test_validate_runs_functions():
    fakes = [
        mock.Mock(return_value={"result1": "bad1"}),
        mock.Mock(return_value={"result2": "bad2"}),
    ]
    with mock.patch("ska_oso_services.odt.validation.MID_VALIDATION_FNS", fakes):
        fake_sbd = mock.Mock()
        result = validate_sbd(fake_sbd)
    for fn in fakes:
        fn.assert_called_once_with(fake_sbd)
    assert result == {"result1": "bad1", "result2": "bad2"}
