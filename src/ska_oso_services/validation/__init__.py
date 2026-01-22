from typing import Union

from ska_oso_pdm import SubArrayLOW, SubArrayMID, TelescopeType, ValidationArrayAssembly
from ska_oso_pdm.sb_definition.csp.midcbf import Band5bSubband as pdm_Band5bSubband
from ska_oso_pdm.sb_definition.csp.midcbf import ReceiverBand

from ska_oso_services.common.osdmapper import (
    Band5bSubband,
    MidFrequencyBand,
    configuration_from_osd,
)

OSD = configuration_from_osd().__dict__


def get_low_basic_capability_parameter_from_osd(parameter: str):
    """
    Utility function to extract one of the SKA Low basic capabilities from the OSD
    """
    telescope_osd = OSD[TelescopeType.SKA_LOW].frequency_band.__dict__

    if parameter not in telescope_osd.keys():
        raise ValueError("parameter specified is not available for validation")

    return telescope_osd[parameter]


def get_mid_frequency_band_data_from_osd(
    obs_band: ReceiverBand, band5b_subband: Union[pdm_Band5bSubband, None] = None
) -> Union[MidFrequencyBand, Band5bSubband]:
    if obs_band != ReceiverBand.BAND_5B and band5b_subband is not None:
        raise ValueError(f"cannot specify and band 5b subband for band {obs_band}")
    elif obs_band == ReceiverBand.BAND_5B and band5b_subband is None:
        raise ValueError("band 5b subband must be specified for band 5b observation")

    bands = OSD["ska_mid"].frequency_band

    if band5b_subband is None:
        band_info = next(band for band in bands if band.rx_id == "Band_" + obs_band.value)

    else:
        subbands_info = next(
            band for band in bands if band.rx_id == "Band_" + obs_band.value
        ).band5b_subbands
        band_info = next(
            subband for subband in subbands_info if subband.sub_band == band5b_subband.value
        )

    return band_info


def get_subarray_specific_parameter_from_osd(
    telescope: TelescopeType,
    validation_array_assembly: Union[ValidationArrayAssembly, SubArrayMID, SubArrayLOW],
    parameter: str,
):
    """
    utility function to extract subarray specific parameters from the OSD
    """
    if telescope.value not in OSD.keys():
        raise ValueError(f"invalid telescope: {telescope.value}")

    telescope_osd = OSD[telescope.value]

    # extracting the subarray from the OSD
    subarray = next(
        subarray
        for subarray in telescope_osd.subarrays
        if subarray.name == validation_array_assembly.value
    )

    if not subarray:
        raise ValueError("invalid validation array assembly for specified telescope")
    # turning it into dictionary

    dict_subarray = subarray.__dict__
    if parameter not in dict_subarray.keys():
        raise ValueError("parameter specified is not available for validation")

    return dict_subarray[parameter]
