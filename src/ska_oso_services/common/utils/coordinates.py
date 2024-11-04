import astropy.units as u
from astropy.coordinates import Angle, SkyCoord
from astroquery.exceptions import RemoteServiceError
from astroquery.ipac.ned import Ned
from astroquery.simbad import Simbad


def round_coord_to_3_decimal_places(
    ra: str, dec: str, velocity: float, redshift: float
) -> dict:
    """
    Rounds the seconds component of RA and the arcseconds component of DEC
    to 3 decimal places.

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
        f"{round(float(x), 3):06.3f}" if i == 2 else x
        for i, x in enumerate(ra.split(":"))
    )
    dec_formatted = ":".join(
        f"{round(float(x), 3):06.3f}" if i == 2 else x
        for i, x in enumerate(dec.split(":"))
    )

    return {
        "equatorial": {
            "ra": ra_formatted,
            "dec": dec_formatted,
            "velocity": velocity,
            "redshift": redshift,
        }
    }


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


def convert_to_galactic(ra: str, dec: str, velocity: float, redshift: float):
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

    return {
        "galactic": {
            "lon": float(galactic_coord.l.to_string(decimal=True, unit=u.degree)),
            "lat": float(galactic_coord.b.to_string(decimal=True, unit=u.degree)),
            "velocity": velocity,
            "redshift": redshift,
        }
    }


def _calculate_redshift(radial_velocity, speed_light=299792.458):
    """
    Calculate the redshift from the radial velocity.

    :param radial_velocity: Radial velocity in km/s
    :param speed_light: Speed of light in km/s (default is 299792.458 km/s)
    :return: redshift
    """
    # Non-relativistic approximation
    if abs(radial_velocity) < 0.01 * speed_light:
        redshift = radial_velocity / speed_light
    else:
        # Relativistic formula
        redshift = (1 + radial_velocity / speed_light) ** 0.5 / (
            1 - radial_velocity / speed_light
        ) ** 0.5 - 1
    return redshift


def get_coordinates(object_name: str):
    """
    Query celestial coordinates for a given object name from SIMBAD and NED databases.
    If the object is not found in SIMBAD database
    it then queries the NED (NASA/IPAC Extragalactic Database).
    The function returns the Right Ascension (RA)
    and Declination (Dec) in the hour-minute-second (HMS) and
    degree-minute-second (DMS) format respectively.
    Parameters:
    object_name (str): name of the celestial object to query.
    Returns:
    dict: a dict with ra, dec, velocity and redshift values
    """
    # Try searching in SIMBAD
    Simbad.add_votable_fields("ra", "dec", "rvz_radvel", "rv_value", "z_value")
    result_table_simbad = Simbad.query_object(object_name)
    if result_table_simbad is not None:
        ra = result_table_simbad["RA"][0]
        dec = result_table_simbad["DEC"][0]
        velocity = next(
            (
                value
                for value in [
                    result_table_simbad["RVZ_RADVEL"][0],
                    result_table_simbad["RV_VALUE"][0],
                ]
                if value is not None and value != ""
            ),
            None,
        )
        if velocity is not None:
            redshift = _calculate_redshift(velocity)
        else:
            redshift = None
    else:
        # If not found in SIMBAD, search in NED
        try:
            result_table_ned = Ned.query_object(object_name)
        except RemoteServiceError as e:
            return f"{'Object not found in SIMBAD or NED', e}"
        ra = result_table_ned["RA"][0]
        dec = result_table_ned["DEC"][0]
    coordinates = (
        SkyCoord(ra, dec, unit=(u.hourangle, u.degree), frame="icrs")
        .to_string("hmsdms")
        .replace("h", ":")
        .replace("d", ":")
        .replace("m", ":")
        .replace("s", "")
    )
    return {
        "ra": coordinates.split(" ")[0],
        "dec": coordinates.split(" ")[1],
        "velocity": velocity,
        "redshift": redshift,
    }
