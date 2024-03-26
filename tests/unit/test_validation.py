import json
from copy import deepcopy

from ska_oso_odt_services.validation import validate_sbd

from .util import VALID_MID_SBDEFINITION_JSON


def test_valid_sbd_returns_no_messages():
    result = validate_sbd(VALID_MID_SBDEFINITION_JSON)

    assert result["validation_errors"] == []


def test_sbd_deserailise_error():
    result = validate_sbd(json.dumps({"i am": "not a valid sbd"}))

    assert result["validation_errors"] == [
        "{'interface': ['Missing data for required field.'], 'telescope': ['Missing"
        " data for required field.']}"
    ]


def test_config_not_present_error():
    invalid_sbd = json.loads(deepcopy(VALID_MID_SBDEFINITION_JSON))

    # dish config specified in scan definition must be present in SB
    fake_dish_conf_id = "dish config abc"
    fake_csp_conf_id = "csp config abc"
    invalid_sbd["scan_definitions"][0]["dish_configuration"] = fake_dish_conf_id
    invalid_sbd["scan_definitions"][0]["csp_configuration"] = fake_csp_conf_id

    result = validate_sbd(json.dumps(invalid_sbd))

    assert result["validation_errors"] == [
        (
            "Dish configuration 'dish config abc' defined in scan definition"
            " 'calibrator scan' does not exist in the SB"
        ),
        (
            "CSP configuration 'csp config abc' defined in scan definition 'calibrator"
            " scan' does not exist in the SB"
        ),
    ]


def test_band_5_tuning():
    invalid_sbd = json.loads(deepcopy(VALID_MID_SBDEFINITION_JSON))
    invalid_sbd["dish_configurations"][0]["receiver_band"] = "1"  # Not Band 5a

    result = validate_sbd(json.dumps(invalid_sbd))

    assert result["validation_errors"] == [
        (
            "Scan definition 'calibrator scan' specifies CSP configuration with"
            " band_5_tuning but dish configuration with receiver band"
            " ReceiverBand.BAND_1"
        ),
        (
            "Scan definition 'science scan' specifies CSP configuration with"
            " band_5_tuning but dish configuration with receiver band"
            " ReceiverBand.BAND_1"
        ),
    ]
