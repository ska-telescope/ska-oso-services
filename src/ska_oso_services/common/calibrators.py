"""
Module that returns the calibrators
"""

from abc import ABC
from datetime import timedelta
from pathlib import Path
from typing import List

from astroplan import Observer
from astropy.coordinates import AltAz, Angle, EarthLocation
from astropy.io import ascii as astropy_ascii
from astropy.table import QTable
from astropy.time import Time
from pydantic import BaseModel, ConfigDict
from ska_oso_pdm import ICRSCoordinates, RadialVelocity, Target, TelescopeType

from ska_oso_services.common.calibrator_strategy import (
    CalibrationStrategy,
    CalibrationWhen,
    CalibratorChoice,
)

CALIBRATOR_TABLE_PATH = Path(__file__).parents[0] / "static" / "calibrator_table.ecsv"

calibrator_table = astropy_ascii.read(CALIBRATOR_TABLE_PATH)


class BestCalibrator(BaseModel, ABC):
    """
    BaseClass to hold the calibrators chosen
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    calibrator: Target
    when: CalibrationWhen


class ClosestCalibrator(BestCalibrator):
    """
    class to hold the closest calibrators
    """

    separation: Angle


class HighestCalibrator(BestCalibrator):
    """
    class to hold the highest calibrators
    """

    elevation: Angle


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
    scan_duration: timedelta | None = None,
    telescope: TelescopeType | None = None,
) -> list[ClosestCalibrator | HighestCalibrator]:
    """
    function to find the appropriate calibrator
    """
    match strategy.calibrator_choice:
        case CalibratorChoice.CLOSEST:
            calibrator = find_closest_calibrator(target, calibrators, strategy)
        case CalibratorChoice.HIGHEST_ELEVATION:
            calibrator = find_highest_elevation_calibrator(
                target, calibrators, strategy, scan_duration, telescope
            )
        case _:
            raise NotImplementedError(
                f"this calibration strategy is not implemented for {
                    strategy.calibration_strategy_id
                }"
            )

    return calibrator


def find_closest_calibrator(
    target: Target, calibrators: list[Target], strategy: CalibrationStrategy
) -> list[ClosestCalibrator]:
    """ "
    function to find the closest calibrator to the science target
    """
    science_sky_coord = target.reference_coordinate.to_sky_coord()

    closest_calibrators = []
    for when in strategy.when:
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

        closest_calibrators.append(
            ClosestCalibrator(
                when=when,
                calibrator=separation[0][1],
                separation=separation[0][0],
            )
        )

    return closest_calibrators


def find_highest_elevation_calibrator(
    target: Target,
    calibrators: list[Target],
    strategy: CalibrationStrategy,
    scan_duration: timedelta,
    telescope: TelescopeType,
) -> list[HighestCalibrator]:
    """
    function to find the calibrator with the highest elevation when
    the target is observed

    This assumes that the target is observed as it crosses the meridian
    """

    coords = target.reference_coordinate.to_sky_coord()

    # first setting the location
    match telescope:
        case TelescopeType.SKA_LOW:
            location = EarthLocation.of_site("SKA Low")
        case TelescopeType.SKA_MID:
            location = EarthLocation.of_site("SKA Mid")
        case _:
            raise ValueError(f"Telescope {telescope} not supported")

    observer = Observer(location=location)

    # then calculate the transit time
    target_transit_time = observer.target_meridian_transit_time(
        time=Time.now(), target=coords, which="next"
    )

    highest_elevation_calibrators = []
    # then finding the calibrators with the highest elevation at this transit time
    for when in strategy.when:
        offset_time = (scan_duration - strategy.duration_ms) / 2.0
        match when:
            case CalibrationWhen.BEFORE_EACH_SCAN:
                calibrator_obs_time = target_transit_time - offset_time
            case CalibrationWhen.AFTER_EACH_SCAN:
                calibrator_obs_time = target_transit_time + offset_time
            case _:
                raise NotImplementedError(
                    f"this calibration strategy is not implemented for {
                        strategy.calibration_strategy_id
                    }"
                )

        elevation = [
            (
                calibrator.reference_coordinate.to_sky_coord()
                .transform_to(
                    AltAz(obstime=calibrator_obs_time, location=location),
                )
                .alt,
                calibrator,
            )
            for calibrator in calibrators
        ]

        elevation.sort()

        highest_elevation_calibrators.append(
            HighestCalibrator(
                when=when,
                calibrators=elevation[-1][1],
                elevation=elevation[-1][0],
            )
        )

    return highest_elevation_calibrators
