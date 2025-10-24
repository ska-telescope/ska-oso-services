import pytest
from astropy import units as u
from astropy.table import QTable
from ska_oso_pdm import Target

from ska_oso_services.common.calibrators import calibrator_table, to_pdm_target


def test_table_is_correctly_loaded():
    assert type(calibrator_table) is QTable
    assert calibrator_table["ra"].unit is u.Unit("degree")
    assert calibrator_table["LAS"].unit is u.Unit("arcmin")


def test_to_pdm_target(dummy_calibrator_table):
    targets = to_pdm_target(dummy_calibrator_table)
    assert isinstance(targets, list)
    assert len(targets) == 6
    assert isinstance(targets[0], Target)


def test_to_pdm_target_can_handle_filtered_table(dummy_calibrator_table):
    filtered_table = dummy_calibrator_table[
        dummy_calibrator_table["Flux Density @ 200MHz"] > 400.0 * u.Unit("Jy")
    ]
    targets = to_pdm_target(filtered_table)
    assert len(targets) == 2


def test_to_pdm_target_can_handle_empty_table(dummy_calibrator_table):
    with pytest.raises(
        ValueError, match="No calibrators found that match the criteria."
    ):

        filtered_table = dummy_calibrator_table[
            dummy_calibrator_table["Flux Density @ 200MHz"] > 4000.0 * u.Unit("Jy")
        ]
        to_pdm_target(filtered_table)
