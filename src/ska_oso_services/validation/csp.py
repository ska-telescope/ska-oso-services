# https://stackoverflow.com/a/50099819
# pylint: disable=no-member
import math

from astropy import units as u
from astropy.units import Quantity
from ska_oso_pdm import TelescopeType
from ska_oso_pdm.sb_definition import CSPConfiguration
from ska_oso_pdm.sb_definition.csp.lowcbf import Correlation
from ska_oso_pdm.sb_definition.csp.midcbf import CorrelationSPWConfiguration

from ska_oso_services.common.osdmapper import (
    Band5bSubband,
    MidFrequencyBand,
    get_mid_frequency_band_data_from_osd,
    get_subarray_specific_parameter_from_osd,
)
from ska_oso_services.common.static.constants import (
    low_continuum_channel_width,
    low_maximum_frequency,
    low_minimum_frequency,
    mid_channel_width,
    mid_frequency_slice_bandwidth,
)
from ska_oso_services.validation.model import (
    ValidationContext,
    ValidationIssue,
    ValidationIssueType,
    check_relevant_context_contains,
    validate,
    validator,
)


@validator
def validate_csp(
    csp_context: ValidationContext[CSPConfiguration],
) -> list[ValidationIssue]:
    """
    :param csp_context: a ValidationContext containing a ScanDefinition
        to be validated. This should also contain a relevant_context with the target
        and csp_config for the scan
    :return: the collated ValidationIssues resulting from applying each of
            scan Validators to the scan_definition
    """
    if csp_context.telescope == TelescopeType.SKA_MID:
        validators = [validate_mid_spws]
    else:
        validators = [validate_low_spws]

    return validate(csp_context, validators)


@validator
def validate_low_spws(
    csp_context: ValidationContext[CSPConfiguration],
) -> list[ValidationIssue]:
    lowcbf = csp_context.primary_entity.lowcbf

    spws_validation_results = [
        issue
        for index, spw in enumerate(lowcbf.correlation_spws)
        for issue in validate_low_spw(
            ValidationContext(
                primary_entity=spw,
                source_jsonpath=f"$.lowcbf.correlation_spws[{index}]",
                telescope=csp_context.telescope,
                array_assembly=csp_context.array_assembly,
            )
        )
    ]

    return spws_validation_results


@validator
def validate_mid_spws(
    csp_context: ValidationContext[CSPConfiguration],
) -> list[ValidationIssue]:
    midcbf = csp_context.primary_entity.midcbf

    if midcbf.band5b_subband is None:
        band_data = get_mid_frequency_band_data_from_osd(midcbf.frequency_band)
    else:
        band_data = get_mid_frequency_band_data_from_osd(
            midcbf.frequency_band, midcbf.band5b_subband
        )

    # currently only supporting one subband per CSP config for Mid

    spws_validation_results = [
        issue
        for index, spw in enumerate(midcbf.subbands[0].correlation_spws)
        for issue in validate_mid_spw(
            ValidationContext(
                primary_entity=spw,
                source_jsonpath=f"$.midcbf.subbands[0].correlation_spws[{index}]",
                relevant_context={
                    "band_data_from_osd": band_data,
                    "subband_frequency_slice_offset": midcbf.subbands[0].frequency_slice_offset,
                },
                telescope=csp_context.telescope,
                array_assembly=csp_context.array_assembly,
            )
        )
    ]

    return spws_validation_results


@validator
def validate_low_spw(
    spw_context: ValidationContext[Correlation],
) -> list[ValidationIssue]:
    validators = [
        validate_low_spw_centre_frequency,
        validate_continuum_spw_bandwidth,
        validate_low_spw_window,
    ]

    return validate(spw_context, validators)


@validator
def validate_mid_spw(
    spw_context: ValidationContext[CorrelationSPWConfiguration],
) -> list[ValidationIssue]:
    check_relevant_context_contains(
        [
            "band_data_from_osd",
        ],
        spw_context,
    )

    validators = [
        validate_mid_spw_centre_frequency,
        validate_continuum_spw_bandwidth,
        validate_mid_spw_window,
        validate_mid_fsps,
    ]

    return validate(spw_context, validators)


@validator
def validate_low_spw_centre_frequency(
    spw_context: ValidationContext[Correlation],
) -> list[ValidationIssue]:

    centre_frequency_hz = spw_context.primary_entity.centre_frequency * u.Hz

    if (
        centre_frequency_hz < low_minimum_frequency()
        or centre_frequency_hz > low_maximum_frequency()
    ):
        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message=f"Centre frequency of "
                f"spectral window {centre_frequency_hz}"
                f" is outside of the telescope capabilities",
            )
        ]

    return []


@validator
def validate_mid_spw_centre_frequency(
    spw_context: ValidationContext[CorrelationSPWConfiguration],
) -> list[ValidationIssue]:
    """
    function to validate an individual MID spectral window central frequency

    """
    centre_frequency_hz = spw_context.primary_entity.centre_frequency
    band_data = spw_context.relevant_context["band_data_from_osd"]
    if (
        centre_frequency_hz > band_data.max_frequency_hz
        or centre_frequency_hz < band_data.min_frequency_hz
    ):
        match band_data:
            case Band5bSubband():
                band_id = "Band5b subband " + str(band_data.sub_band)
            case MidFrequencyBand():
                band_id = band_data.rx_id

        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message=f"Centre frequency of "
                f"spectral window {centre_frequency_hz} Hz"
                f" is outside of {band_id}",
            )
        ]

    return []


@validator
def validate_continuum_spw_bandwidth(
    spw_context: ValidationContext[CorrelationSPWConfiguration] | ValidationContext[Correlation],
) -> list[ValidationIssue]:
    """
    function to validate the bandwidth
    of an individual MID spectral window
    """
    available_bandwidth = (
        get_subarray_specific_parameter_from_osd(
            spw_context.telescope, spw_context.array_assembly, "available_bandwidth_hz"
        )
        * u.Hz
    )

    spw_bandwidth = _calculate_continuum_spw_bandwidth(spw_context)

    if spw_bandwidth > available_bandwidth:
        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message=f"Bandwidth of spectral window {float(spw_bandwidth.to('MHz').value)} MHz"
                " is outside of available bandwidth"
                " {float(available_bandwidth.to('MHz').value)} Hz for "
                f"{spw_context.telescope} {spw_context.array_assembly.value}",
            )
        ]

    return []


@validator
def validate_low_spw_window(
    spw_context: ValidationContext[Correlation],
) -> list[ValidationIssue]:
    centre_frequency = spw_context.primary_entity.centre_frequency * u.Hz
    spw_bandwidth = _calculate_continuum_spw_bandwidth(spw_context)

    if (centre_frequency + 0.5 * spw_bandwidth) > low_maximum_frequency() or (
        centre_frequency - 0.5 * spw_bandwidth
    ) < low_minimum_frequency():

        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message="Spectral window is outside allowed range",
            )
        ]

    return []


@validator
def validate_mid_spw_window(
    spw_context: ValidationContext[CorrelationSPWConfiguration],
) -> list[ValidationIssue]:

    centre_frequency = spw_context.primary_entity.centre_frequency * u.Hz
    spw_bandwidth = _calculate_continuum_spw_bandwidth(spw_context)

    band_data = spw_context.relevant_context["band_data_from_osd"]

    if (centre_frequency + 0.5 * spw_bandwidth) > band_data.max_frequency_hz * u.Hz or (
        centre_frequency - 0.5 * spw_bandwidth
    ) < band_data.min_frequency_hz * u.Hz:

        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message="Spectral window is outside allowed range",
            )
        ]

    return []


@validator
def validate_mid_fsps(
    spw_context: ValidationContext[CorrelationSPWConfiguration],
) -> list[ValidationIssue]:
    """
    validator to check that the number of fsps required is feasible for the array assembly
    """

    centre_frequency = spw_context.primary_entity.centre_frequency * u.Hz
    spw_bandwidth = _calculate_continuum_spw_bandwidth(spw_context)

    frequency_offset = spw_context.relevant_context[
        "subband_frequency_slice_offset"
    ]  # should be zero

    minimum_spw_frequency = centre_frequency - 0.5 * spw_bandwidth
    maximum_spw_frequency = centre_frequency + 0.5 * spw_bandwidth

    coarse_channel_low = math.floor(
        (minimum_spw_frequency - frequency_offset + (0.5 * mid_frequency_slice_bandwidth()))
        / mid_frequency_slice_bandwidth()
    )
    coarse_channel_high = math.floor(
        (maximum_spw_frequency - frequency_offset + (0.5 * mid_frequency_slice_bandwidth()))
        / mid_frequency_slice_bandwidth()
    )

    n_fsps = coarse_channel_high - coarse_channel_low + 1

    available_fsps = get_subarray_specific_parameter_from_osd(
        spw_context.telescope, spw_context.array_assembly, "number_fsps"
    )

    if n_fsps > available_fsps:
        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message="Number of FSPs required for spectral window is greater than the number"
                f" of FSPs available for array assembly {spw_context.array_assembly}",
            )
        ]

    return []


def _calculate_continuum_spw_bandwidth(
    spw_context: ValidationContext[CorrelationSPWConfiguration] | ValidationContext[Correlation],
) -> Quantity:
    """
    private function to calculate the bandwidth of spectral windows
    """

    number_of_channels = spw_context.primary_entity.number_of_channels
    # this is currently always zero for both MID and LOW
    zoom_factor = spw_context.primary_entity.zoom_factor
    if zoom_factor != 0:
        raise ValueError("zoom windows are not yet supported")

    if spw_context.telescope == TelescopeType.SKA_MID:
        channel_width = mid_channel_width()
    else:
        channel_width = low_continuum_channel_width()

    spw_bandwidth = channel_width * number_of_channels

    return spw_bandwidth
