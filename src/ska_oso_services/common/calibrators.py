"""
Module that returns the calibrators
"""

from pathlib import Path
from typing import List

from astropy.io import ascii as astropy_ascii
from astropy.table import QTable
from ska_oso_pdm import ICRSCoordinates, RadialVelocity, Target
from ska_oso_services.common.calibrator_strategy import CalibratorChoice

CALIBRATOR_TABLE_PATH = Path(__file__).parents[0] / "static" / "calibrator_table.ecsv"

calibrator_table = astropy_ascii.read(CALIBRATOR_TABLE_PATH)


def to_pdm_target(table: QTable) -> List[Target]:
    """
    function to return a list of PDM Target from an AstroPy QTable
    """
    if not table:
        raise ValueError("No calibrators found that match the criteria.")

    targets = [
        Target(
            target_id=row["target_id"],
            name=row["name"],
            reference_coordinate=ICRSCoordinates(
                ra_str=str(row["ra"].to_string(unit="hourangle", sep=":", pad=True)),
                dec_str=str(row["dec"].to_string(unit="deg", sep=":", pad=True)),
            ),
            radial_velocity=RadialVelocity(
                redshift=row["redshift"],
            ),
        )
        for row in table
    ]
    return targets


def find_appropriate_calibrator(target: Target, calibrators: list[Target], discriminator: CalibratorChoice) -> Target:
    """
    function to find the appropriate calibrator
    """
    pass