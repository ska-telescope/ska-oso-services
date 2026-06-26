# pylint: disable=no-member
import csv
from importlib import resources
from sys import maxsize

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from ska_oso_pdm import ICRSCoordinates, Target
from ska_oso_pdm.builders.utils import target_id

from ska_oso_services.common.error_handling import BadRequestError
from ska_oso_services.odt.service.commissioning import data as commissioning_data


def load_pointings_as_targets_and_fwhm(
    pointings_file_uri: str, max_rows: int = maxsize
) -> tuple[list[Target], np.ndarray]:
    """Load targets and beam_fwhm values from a pointings CSV in one pass."""
    data_file = resources.files(commissioning_data) / pointings_file_uri
    if not data_file.is_file():
        raise BadRequestError(
            detail=f"Pointings file '{pointings_file_uri}' not found in commissioning data."
        )

    targets: list[Target] = []
    fwhm_deg_values: list[float] = []
    with resources.as_file(data_file) as path:
        with open(path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            if "beam_fwhm" not in (reader.fieldnames or []):
                raise BadRequestError(
                    detail=(
                        f"Pointings file '{pointings_file_uri}' is missing required "
                        "column 'beam_fwhm'."
                    )
                )
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                try:
                    fwhm_deg = float(row["beam_fwhm"])
                except (TypeError, ValueError) as exc:
                    raise BadRequestError(
                        detail=(
                            f"Pointings file '{pointings_file_uri}' contains invalid "
                            f"beam_fwhm value '{row.get('beam_fwhm')}'."
                        )
                    ) from exc
                if not np.isfinite(fwhm_deg) or fwhm_deg <= 0.0:
                    raise BadRequestError(
                        detail=(
                            f"Pointings file '{pointings_file_uri}' contains non-positive "
                            f"beam_fwhm value '{fwhm_deg}'."
                        )
                    )
                fwhm_deg_values.append(fwhm_deg)

                # TODO Astropy supports vectorized operations so we could do one
                #  SkyCoord call for all rows
                coord = SkyCoord(ra=float(row["ra"]), dec=float(row["dec"]), unit="deg")
                targets.append(
                    Target(
                        target_id=target_id(),
                        name=row["beam_name"],
                        reference_coordinate=ICRSCoordinates(
                            ra_str=coord.ra.to_string(u.hour, sep=":"),
                            dec_str=coord.dec.to_string(u.degree, sep=":"),
                        ),
                    )
                )

    if not fwhm_deg_values:
        raise BadRequestError(
            detail=f"Pointings file '{pointings_file_uri}' has no rows with beam_fwhm values."
        )
    return targets, np.asarray(fwhm_deg_values, dtype=float)
