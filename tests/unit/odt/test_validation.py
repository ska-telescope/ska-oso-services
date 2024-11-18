from unittest import mock

from ska_oso_pdm.sb_definition import SBDefinition

from ska_oso_services.odt.validation import _validate_csp, validate_sbd
from tests.unit.util import (
    VALID_LOW_SBDEFINITION_JSON,
    VALID_MID_SBDEFINITION_JSON,
    TestDataFactory,
)


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


def test_config_not_present_error():
    invalid_sbd = TestDataFactory.sbdefinition()

    fake_csp_conf_id = "csp config abc"
    invalid_sbd.scan_definitions[0].csp_configuration_ref = fake_csp_conf_id

    result = _validate_csp(invalid_sbd)

    assert result == {
        "csp_config_not_in_sb_calibrator scan": (
            "CSP configuration 'csp config abc' defined in scan definition"
            " 'calibrator scan' does not exist in the SB"
        ),
    }


def test_low_config_not_present_error():
    invalid_sbd = TestDataFactory.lowsbdefinition()

    fake_csp_conf_id = "csp config abc"
    invalid_sbd.scan_definitions[0].csp_configuration_ref = fake_csp_conf_id

    result = _validate_csp(invalid_sbd)

    assert result == {
        "csp_config_not_in_sb_science": (
            "CSP configuration 'csp config abc' defined in scan definition"
            " 'science' does not exist in the SB"
        ),
    }
