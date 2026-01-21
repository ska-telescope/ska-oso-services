from ska_oso_pdm import ICRSCoordinates
from ska_oso_pdm.builders.target_builder import MidTargetBuilder

LMC_TARGET = MidTargetBuilder(  # use the Mid builder but really this target is valid for either
    name="LMC",
    reference_coordinate=ICRSCoordinates(ra_str="05:23:34.6000", dec_str="-69:45:22.000"),
)
