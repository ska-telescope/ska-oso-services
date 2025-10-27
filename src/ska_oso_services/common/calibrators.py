"""
Module that returns the calibrators
"""

from datetime import timedelta
from pathlib import Path
from typing import List

from astropy.coordinates import AltAz, Angle, EarthLocation
from astropy.coordinates.tests.test_spectral_coordinate import observer
from astropy.io import ascii as astropy_ascii
from astropy.table import QTable
from astropy.time import Time
from astropy.units import Unit as u
from astroplan import Observer, FixedTarget

from ska_oso_pdm import ICRSCoordinates, RadialVelocity, Target, TelescopeType
from ska_oso_services.common.calibrator_strategy import CalibratorChoice, CalibrationStrategy

CALIBRATOR_TABLE_PATH = Path(__file__).parents[0] / "static" / "calibrator_table.ecsv"

calibrator_table = astropy_ascii.read(CALIBRATOR_TABLE_PATH)


def to_pdm_targets(table: QTable) -> List[Target]:
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


def find_appropriate_calibrator(
    target: Target,
    calibrators: list[Target],
    strategy: CalibrationStrategy,
    scan_duration: timedelta,
    telescope: TelescopeType,
) -> tuple[Angle, Target]:
    """
    function to find the appropriate calibrator
    """
    match strategy.calibrator_choice:
        case CalibratorChoice.CLOSEST:
            calibrator = find_closest_calibrator(target, calibrators)
        case CalibratorChoice.HIGHEST_ELEVATION:
            calibrator = find_highest_elevation_calibrator(
                target, calibrators, strategy, scan_duration, telescope
            )
        case _:
            raise NotImplementedError(
                f"this calibration strategy is not implemented for {strategy.calibration_strategy_id}"
            )

    return calibrator


def find_closest_calibrator(
    target: Target, calibrators: list[Target]
) -> tuple[Angle, Target]:
    """ "
    function to find the closest calibrator to the science target
    """
    science_sky_coord = target.reference_coordinate.to_sky_coord()

    separation = [
        (
            science_sky_coord.separation(
                calibrator.reference_coordinate.to_sky_coord()
            ),
            calibrator,
        )
        for calibrator in calibrators
    ]
    separation.sort()

    return separation[0]