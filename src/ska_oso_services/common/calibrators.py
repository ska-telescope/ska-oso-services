"""
Module that returns the calibrators
"""

from pathlib import Path
from typing import List

from astropy.table import QTable
from ska_oso_pdm import ICRSCoordinates, Target

CALIBRATOR_TABLE_PATH = Path(__file__).parents[0] / "static" / "calibrator_table.ecsv"

calibrator_table = QTable.read(CALIBRATOR_TABLE_PATH)


def to_pdm_target(table: QTable) -> List[Target]:
    """
    function to return a list of PDM Target from an AstroPy QTable
    """
    targets = [
        Target(
            target_id=row["target_id"],
            name=row["name"],
            reference_coordinate=ICRSCoordinates(
                ra_str=str(row["ra"].to_string(unit="hourangle", sep=":", pad=True)),
                dec_str=str(row["dec"].to_string(unit="deg", sep=":", pad=True)),
            ),
        )
        for row in table
    ]
    return targets
