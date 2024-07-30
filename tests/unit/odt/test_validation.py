import json

from ska_oso_pdm.sb_definition.dish.dish_configuration import ReceiverBand

from ska_oso_services.odt.validation import (
    _validate_csp_and_dish_combination,
    validate_sbd,
)
from tests.unit.util import VALID_MID_SBDEFINITION_JSON, TestDataFactory


def test_valid_sbd_returns_no_messages():
    result = validate_sbd(VALID_MID_SBDEFINITION_JSON)

    assert result == {}


def test_sbd_deserialise_error():
    result = validate_sbd(json.dumps({"telescope": "not a valid telescope"}))

    assert (
        "Input should be 'ska_mid', 'ska_low' or 'MeerKAT' "
        "[type=enum, input_value='not a valid telescope', input_type=str]"
        in result["deserialisation_error"]
    )


def test_config_not_present_error():
    invalid_sbd = TestDataFactory.sbdefinition()

    # dish config specified in scan definition must be present in SB
    fake_dish_conf_id = "dish config abc"
    fake_csp_conf_id = "csp config abc"
    invalid_sbd.scan_definitions[0].dish_configuration_ref = fake_dish_conf_id
    invalid_sbd.scan_definitions[0].csp_configuration_ref = fake_csp_conf_id

    result = _validate_csp_and_dish_combination(invalid_sbd)

    assert result == {
        "dish_config_not_in_sb_calibrator scan": (
            "Dish configuration 'dish config abc' defined in scan definition "
            "'calibrator scan' does not exist in the SB"
        ),
        "csp_config_not_in_sb_calibrator scan": (
            "CSP configuration 'csp config abc' defined in scan definition"
            " 'calibrator scan' does not exist in the SB"
        ),
    }


def test_band_5_tuning():
    invalid_sbd = TestDataFactory.sbdefinition()
    invalid_sbd.dish_configurations[0].receiver_band = (
        ReceiverBand.BAND_1
    )  # Not Band 5a

    result = _validate_csp_and_dish_combination(invalid_sbd)

    assert result == {
        "csp_and_dish_band_mismatch_calibrator scan": (
            "Scan definition 'calibrator scan' specifies CSP configuration with "
            "band_5_tuning but dish configuration with "
            "receiver band ReceiverBand.BAND_1"
        ),
        "csp_and_dish_band_mismatch_science scan": (
            "Scan definition 'science scan' specifies CSP configuration with "
            "band_5_tuning but dish configuration with "
            "receiver band ReceiverBand.BAND_1"
        ),
    }
