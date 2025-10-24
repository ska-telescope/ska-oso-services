import pytest

from ska_oso_services.common.calibrator_strategy import (
    CalibratorChoice,
    lookup_observatory_calibration_strategy,
)


def test_observatory_calibrator_strategy_lookup_default():
    default_calibration_strategy_id = "default"
    result = lookup_observatory_calibration_strategy(default_calibration_strategy_id)

    assert result.calibration_strategy_id == default_calibration_strategy_id
    assert result.calibrator_choice == CalibratorChoice.CLOSEST


def test_observatory_calibrator_strategy_lookup_highest_elevation():
    default_calibration_strategy_id = "highest_elevation"
    result = lookup_observatory_calibration_strategy(default_calibration_strategy_id)

    assert result.calibration_strategy_id == default_calibration_strategy_id
    assert result.calibrator_choice == CalibratorChoice.HIGHEST_ELEVATION


def test_observatory_calibrator_strategy_lookup_not_found():

    with pytest.raises(KeyError) as excinfo:
        lookup_observatory_calibration_strategy("fake_id")
    assert (
        str(excinfo.value)
        == "'Observatory Calibration Strategy with calibration_strategy_id "
        "fake_id not found.'"
    )
