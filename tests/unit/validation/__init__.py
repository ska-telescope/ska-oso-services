from ska_oso_pdm import (
    AltAzCoordinates,
    GalacticCoordinates,
    ICRSCoordinates,
    SpecialCoordinates,
    Target,
)
from ska_oso_pdm.builders.target_builder import MidTargetBuilder

from ska_oso_services.common.static.constants import LOW_LOCATION

LMC_TARGET = MidTargetBuilder(  # use the Mid builder but really this target is valid for either
    name="LMC",
    reference_coordinate=ICRSCoordinates(ra_str="05:23:34.6000", dec_str="-69:45:22.000"),
)

GALACTIC_TARGET = Target(
    target_id="target-23456", name="Sgr A*", reference_coordinate=GalacticCoordinates(l=0.0, b=0.0)
)

SSO_TARGET = Target(
    target_id="target-23456", name="Venus", reference_coordinate=SpecialCoordinates(name="Venus")
)

ALTAZ_TARGET = Target(
    target_id="target-45678",
    name="altaz scan",
    reference_coordinate=AltAzCoordinates(az=270.0, el=60.0),
)

FAKE_TARGET_AT_LOW_ZENTIH = Target(
    target_id="target2-34567",
    name="not a real target",
    reference_coordinate=ICRSCoordinates(
        ra_str="01:00:0.00",
        dec_str=str(LOW_LOCATION.lat.to_string(sep=":")),
    ),
)
