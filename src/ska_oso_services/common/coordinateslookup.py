# https://stackoverflow.com/a/50099819
# pylint: disable=no-member,no-name-in-module
import astropy.units as u
from astropy.constants import c as speed_of_light
from astropy.coordinates import Angle, SkyCoord
from astroquery.ipac.ned import Ned
from astroquery.simbad import Simbad

from ska_oso_services.common.model import AppModel


# TODO should be able to use the PDM coordinates here instead
class Equatorial(AppModel):
    ra: str
    dec: str
    velocity: float
    redshift: float


class Galactic(AppModel):
    lon: float
    lat: float
    velocity: float
    redshift: float


def round_coord(ra: str, dec: str, velocity: float, redshift: float) -> Equatorial:
    """
    Rounds the seconds component of RA to 4 decimal places
    and the arcseconds component of DEC to 3.

    Parameters:
    - ra (str): Right Ascension in "HH:MM:SS.sssssssss"
    - dec (str): Declination in "DD:MM:SS.sssssssss"

    Returns:
    - dict: A dictionary with one key "equatorial",
            containing a nested dictionary with keys "right_ascension"
            and "declination", each containing a string value
            with the rounded RA and DEC coordinates.
    """

    ra_formatted = ":".join(
        f"{round(float(x), 4):07.4f}" if i == 2 else x
        for i, x in enumerate(ra.split(":"))
    )
    dec_formatted = ":".join(
        f"{round(float(x), 3):06.3f}" if i == 2 else x
        for i, x in enumerate(dec.split(":"))
    )

    return Equatorial(
        ra=ra_formatted,
        dec=dec_formatted,
        velocity=velocity,
        redshift=redshift,
    )


def convert_ra_dec_deg(ra_str: str, dec_str: str):
    """
    Convert RA and Dec from sexagesimal (string format) to decimal degrees.

    Parameters:
    ra_str (str): RA in the format "HH:MM:SS" (e.g., "5:35:17.3")
    dec_str (str): Dec in the format "DD:MM:SS" (e.g., "-1:2:37")

    Returns:
    tuple: RA and Dec in decimal degrees
    """
    ra = Angle(ra_str, unit=u.hour)
    dec = Angle(dec_str, unit=u.degree)

    return {"ra": round(ra.degree, 3), "dec": round(dec.degree, 3)}


def convert_to_galactic(
    ra: str, dec: str, velocity: float, redshift: float
) -> Galactic:
    """
    Converts RA and DEC coordinates to Galactic coordinates.

    Parameters:
    - ra (str): The Right Ascension in the format "HH:MM:SS.sss"
    - dec (str): The Declination in the format "+DD:MM:SS.sss"

    Returns:
    - dict: A dictionary with one key "galactic",
            containing a nested dictionary with keys lon
            and lat, representing the Galactic coordinates as floats in degrees.
    """
    # Creating a SkyCoord object with the given RA and DEC
    coord = SkyCoord(ra, dec, frame="icrs", unit=(u.hourangle, u.degree))
    # Converting to Galactic frame
    galactic_coord = coord.galactic

    return Galactic(
        lon=float(galactic_coord.l.to_string(decimal=True, unit=u.degree)),
        lat=float(galactic_coord.b.to_string(decimal=True, unit=u.degree)),
        velocity=velocity,
        redshift=redshift,
    )


def _calculate_redshift(radial_velocity) -> float:
    """
    Calculate the redshift from the radial velocity.

    :param radial_velocity: Radial velocity in km/s
    :return: redshift
    """
    # Convert input to m/s - eventually can refactor method signature
    radial_velocity = radial_velocity * 1e3
    # Non-relativistic approximation
    if abs(radial_velocity) < 0.01 * speed_of_light.value:
        redshift = radial_velocity / speed_of_light.value
    else:
        # Relativistic formula
        redshift = (1 + radial_velocity / speed_of_light.value) ** 0.5 / (
            1 - radial_velocity / speed_of_light.value
        ) ** 0.5 - 1
    return redshift


def get_coordinates(object_name: str) -> Equatorial:
    """
    Query celestial coordinates for a given object name in either the
    SIMBAD or the NED databases of astronomical sources. We search SIMBAD
    and if the source is not found, try NED.
    The function returns the Right Ascension (RA) and Declination (Dec)
    in the hour-minute-second (HMS) and degree-minute-second (DMS) format
    respectively.

    Velocities are handled in the following way:
    Simbad - for each object, a master value is stored which will be either
    a velocity or a redshift. The function finds out which one this is and
    stores it. The other is set to zero.
    NED - only the redshift is stored as the velocity has limited precision.
    Velocity is set to zero.
    """

    # Initialise velocity and redshift
    redshift = 0.0
    velocity = 0.0

    # First look in SIMBAD
    Simbad.add_votable_fields("velocity")
    result_table_simbad = Simbad.query_object(object_name)

    if len(result_table_simbad) != 0:
        ra = result_table_simbad["ra"][0]
        dec = result_table_simbad["dec"][0]

        # Determine if stored information is redshift or velocity
        rvz_type = result_table_simbad["rvz_type"]
        if rvz_type == "z":
            redshift = result_table_simbad["rvz_redshift"]
        elif rvz_type == "v":
            velocity = result_table_simbad["rvz_radvel"]
    else:
        # If not found in SIMBAD, search in NED
        result_table_ned = Ned.query_object(object_name)
        ra = result_table_ned["RA"][0]
        dec = result_table_ned["DEC"][0]

        # For NED we only take the redshift
        mask = result_table_ned["Redshift"].mask[0]
        if mask:
            redshift = 0.0
        else:
            redshift = result_table_ned["Redshift"][0]

    coordinates = SkyCoord(ra, dec, unit=(u.degree, u.degree), frame="icrs").to_string(
        "hmsdms", pad=True, sep=":"
    )

    return Equatorial(
        ra=coordinates.split(" ")[0],
        dec=coordinates.split(" ")[1],
        velocity=velocity,
        redshift=redshift,
    )
