from ska_oso_pdm import TelescopeType, ValidationArrayAssembly

from ska_oso_services.common.osdmapper import configuration_from_osd

OSD = configuration_from_osd().__dict__


def get_subarray_specific_parameter_from_osd(
    telescope: TelescopeType,
    validation_array_assembly: ValidationArrayAssembly,
    parameter: str,
):
    """
    utility function to extract subarray specific parameters from the OSD
    """
    if telescope.value not in OSD.keys():
        raise ValueError("invalid telescope")

    telescope_osd = OSD[telescope.value]

    if validation_array_assembly.value not in telescope_osd.__dict__.keys():
        raise ValueError("invalid validation array assembly for specified telescope")

    # extracting the subarray from the OSD
    subarray = next(
        subarray
        for subarray in telescope_osd.subarrays
        if subarray.name == validation_array_assembly.value
    )

    # turning it into dictionary

    dict_subarray = subarray.__dict__
    if parameter not in dict_subarray.keys():
        raise ValueError("parameter specified is not available for validation")

    return dict_subarray[parameter]
