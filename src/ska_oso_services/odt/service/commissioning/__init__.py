# pylint: disable=no-member
import csv
from importlib import resources

import astropy.units as u
from astropy.coordinates import SkyCoord
from ska_oso_pdm import ICRSCoordinates, Target
from ska_oso_pdm.builders.utils import target_id

from ska_oso_services.common.error_handling import BadRequestError
from ska_oso_services.odt.service.commissioning import data as commissioning_data


def load_pointings_as_targets(
    pointings_file_uri: str, max_rows: int | None = None
) -> list[Target]:
    """Load pointings from a CSV in the commissioning data directory as Target objects.

    The CSV is expected to have columns: beam_name, ra (degrees), dec (degrees).
    """
    data_file = resources.files(commissioning_data) / pointings_file_uri
    if not data_file.is_file():
        raise BadRequestError(
            detail=f"Pointings file '{pointings_file_uri}' not found in commissioning data."
        )

    targets = []
    with resources.as_file(data_file) as path:
        with open(path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for i, row in enumerate(reader):
                if max_rows is not None and i >= max_rows:
                    break
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

    return targets
