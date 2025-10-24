import pytest
from astropy import units as u
from astropy.table import QTable
from ska_oso_pdm import Target

from ska_oso_services.common.calibrators import calibrator_table, to_pdm_target


def test_table_is_correctly_loaded():
    assert type(calibrator_table) is QTable
    assert calibrator_table["ra"].unit is u.deg
    assert calibrator_table["LAS"].unit is u.arcmin


def test_to_pdm_target():
    targets = to_pdm_target(calibrator_table)
    assert type(targets) is list
    assert len(targets) == 6
    assert type(targets[0]) == Target


def test_to_pdm_target_can_handle_filtered_table():
    filtered_table = calibrator_table[
        calibrator_table["Flux Density @ 200MHz"] > 400.0 * u.Jy
    ]
    targets = to_pdm_target(filtered_table)
    assert len(targets) == 2


def test_to_pdm_target_can_handle_empty_table():
    with pytest.raises(
        ValueError, match="No calibrators found that match the criteria."
    ):

        filtered_table = calibrator_table[
            calibrator_table["Flux Density @ 200MHz"] > 4000.0 * u.Jy
        ]
        to_pdm_target(filtered_table)
