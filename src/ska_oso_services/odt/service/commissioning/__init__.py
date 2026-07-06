# pylint: disable=no-member
import csv
from importlib import resources
from sys import maxsize

import astropy.units as u
from astropy.coordinates import SkyCoord
from ska_oso_pdm import ICRSCoordinates
from ska_oso_pdm.builders.utils import target_id

from ska_oso_services.common.error_handling import BadRequestError
from ska_oso_services.odt.service.commissioning import data as commissioning_data
from ska_oso_services.odt.service.target_grouping import PointingTarget


def load_pointings_as_targets(
    pointings_file_uri: str, max_rows: int = maxsize
) -> list[PointingTarget]:
    """Load pointings and per-target beam FWHM from a commissioning CSV."""
    data_file = resources.files(commissioning_data) / pointings_file_uri
    if not data_file.is_file():
        raise BadRequestError(
            detail=f"Pointings file '{pointings_file_uri}' not found in commissioning data."
        )

    pointings: list[PointingTarget] = []
    with resources.as_file(data_file) as path:
        with open(path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                # Read per-target beam FWHM in the same loop as coordinates.
                fwhm_deg = float(row["beam_fwhm"])

                # TODO Astropy supports vectorized operations so we could do one
                #  SkyCoord call for all rows
                coord = SkyCoord(ra=float(row["ra"]), dec=float(row["dec"]), unit="deg")
                pointing = PointingTarget(
                    target_id=target_id(),
                    name=row["beam_name"],
                    reference_coordinate=ICRSCoordinates(
                        ra_str=coord.ra.to_string(u.hour, sep=":"),
                        dec_str=coord.dec.to_string(u.degree, sep=":"),
                    ),
                    fwhm_deg=fwhm_deg,
                )
                pointings.append(pointing)

    return pointings
