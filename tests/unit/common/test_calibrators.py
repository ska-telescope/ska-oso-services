from datetime import timedelta

import pytest
from astropy import units as u
from astropy.table import QTable
from ska_oso_pdm import ICRSCoordinates, Target, TelescopeType

from ska_oso_services.common.calibrator_strategy import (
    OBSERVATORY_CALIBRATION_STRATEGIES,
)
from ska_oso_services.common.calibrators import (
    ClosestCalibrator,
    HighestCalibrator,
    calibrator_table,
    find_appropriate_calibrator,
    to_pdm_targets,
)

TEST_TARGET = Target(
    target_id="target-12345",
    name="SMC X-1",
    reference_coordinate=ICRSCoordinates(
        ra_str="01:17:05.14572884", dec_str="-73:26:36.01480816"
    ),
)


def test_table_is_correctly_loaded():
    assert type(calibrator_table) is QTable
    assert calibrator_table["ra"].unit is u.Unit("degree")
    assert calibrator_table["LAS"].unit is u.Unit("arcmin")


def test_to_pdm_target(dummy_calibrator_table):
    targets = to_pdm_targets(dummy_calibrator_table)
    assert isinstance(targets, list)
    assert len(targets) == 6
    assert isinstance(targets[0], Target)


def test_to_pdm_target_can_handle_filtered_table(dummy_calibrator_table):
    filtered_table = dummy_calibrator_table[
        dummy_calibrator_table["Flux Density @ 200MHz"] > 400.0 * u.Unit("Jy")
    ]
    targets = to_pdm_targets(filtered_table)
    assert len(targets) == 2


def test_to_pdm_target_can_handle_empty_table(dummy_calibrator_table):
    with pytest.raises(
        ValueError, match="No calibrators found that match the criteria."
    ):

        filtered_table = dummy_calibrator_table[
            dummy_calibrator_table["Flux Density @ 200MHz"] > 4000.0 * u.Unit("Jy")
        ]
        to_pdm_targets(filtered_table)


def test_find_closest_calibrator_works_as_expected():
    strategy = OBSERVATORY_CALIBRATION_STRATEGIES["closest"]

    appropriate_calibrators = find_appropriate_calibrator(
        TEST_TARGET, strategy, timedelta(hours=8.0), TelescopeType.SKA_LOW
    )

    assert len(appropriate_calibrators) == 2
    assert isinstance(appropriate_calibrators[0], ClosestCalibrator)
    assert (
        appropriate_calibrators[0].calibrator != appropriate_calibrators[1].calibrator
    )
    assert appropriate_calibrators[0].calibrator.name == "3C 444"
    assert appropriate_calibrators[1].calibrator.name == "Pictor A"


def test_find_highest_calibrator_works_as_expected():
    strategy = OBSERVATORY_CALIBRATION_STRATEGIES["highest_elevation"]

    appropriate_calibrators = find_appropriate_calibrator(
        TEST_TARGET, strategy, timedelta(hours=0.5), TelescopeType.SKA_LOW
    )

    assert len(appropriate_calibrators) == 2
    assert isinstance(appropriate_calibrators[0], HighestCalibrator)
    assert (
        appropriate_calibrators[0].calibrator.name
        == appropriate_calibrators[1].calibrator.name
    )
