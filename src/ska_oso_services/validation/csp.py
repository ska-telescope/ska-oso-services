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
    low_maximum_frequency,
    low_minimum_frequency,
    low_station_channel_width,
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
    :param csp_context: a ValidationContext containing a CSP Configuration
        to be validated
    :return: the collated ValidationIssues resulting from applying each of
            CSP Validators to the CSP Configuration
    """
    if csp_context.telescope == TelescopeType.SKA_MID:
        validators = [validate_mid_spws, validate_mid_fsps]
    else:
        validators = [validate_low_spws]

    return validate(csp_context, validators)


@validator
def validate_low_spws(
    csp_context: ValidationContext[CSPConfiguration],
) -> list[ValidationIssue]:
    """
    :param csp_context: a ValidationContext containing a CSP Configuration to
        be validated
    :return: the collated ValidationIssues resulting from applying each of
        SKA Low spectral window validators to the spectral windows in the
        CSP Configuration
    """
    lowcbf = csp_context.primary_entity.lowcbf

    spws_validation_results = [
        issue
        for index, spw in enumerate(lowcbf.correlation_spws)
        for issue in validate_low_spw(
            ValidationContext(
                primary_entity=spw,
                source_jsonpath=f"$.lowcbf.correlation_spws.{index}",
                relevant_context={"spw_index": index},
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
    """
    :param csp_context: a ValidationContext containing a CSP Configuration to
        be validated
    :return: the collated ValidationIssues resulting from applying each of
        SKA Mid spectral window validators to the spectral windows in the
        CSP Configuration
    """
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
                source_jsonpath=f"$.midcbf.subbands.0.correlation_spws.{index}",
                relevant_context={
                    "band_data_from_osd": band_data,
                    "subband_frequency_slice_offset": midcbf.subbands[0].frequency_slice_offset,
                    "spw_index": index,
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
    """
    :param spw_context: a ValidationContext containing an SKA Low Correlation to
        be validated
    :return: the collated ValidationIssues resulting from applying each of
        the SKA Low spectral window validators to a single Low spectral window
    """
    check_relevant_context_contains(["spw_index"], spw_context)

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
    """
    :param spw_context: a ValidationContext containing an SKA Mid
        CorrelationSPWConfiguration to be validated
    :return: the collated ValidationIssues resulting from applying each of
        the SKA Mid spectral window validators to a single Mid spectral window
    """
    check_relevant_context_contains(
        ["band_data_from_osd", "spw_index"],
        spw_context,
    )

    validators = [
        validate_mid_spw_centre_frequency,
        validate_continuum_spw_bandwidth,
        validate_mid_spw_window,
    ]

    return validate(spw_context, validators)


@validator
def validate_low_spw_centre_frequency(
    spw_context: ValidationContext[Correlation],
) -> list[ValidationIssue]:
    """
    :param spw_context: a ValidationContext containing an SKA Low
        Correlation to be validated
    :return: a validation error if the central frequency of the window
        is outside the frequency range of SKA Low
    """
    centre_frequency_hz = spw_context.primary_entity.centre_frequency * u.Hz
    spw_index = spw_context.relevant_context["spw_index"]

    if (
        centre_frequency_hz < low_minimum_frequency()
        or centre_frequency_hz > low_maximum_frequency()
    ):
        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message=f"Centre frequency of "
                f"spectral window {spw_index + 1}, {centre_frequency_hz},"
                f" is outside of the telescope capabilities",
            )
        ]

    return []


@validator
def validate_mid_spw_centre_frequency(
    spw_context: ValidationContext[CorrelationSPWConfiguration],
) -> list[ValidationIssue]:
    """
    :param spw_context: a ValidationContext containing an SKA Mid
        CorrelationSPWConfiguration to be validated
    :return: a validation error if the central frequency of the window
        is outside the frequency range of the SKA Mid frequency band
    """
    centre_frequency_hz = spw_context.primary_entity.centre_frequency
    band_data = spw_context.relevant_context["band_data_from_osd"]
    spw_index = spw_context.relevant_context["spw_index"]

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
                f"spectral window {spw_index + 1}, {centre_frequency_hz} Hz, "
                f"is outside of {band_id}",
            )
        ]

    return []


@validator
def validate_continuum_spw_bandwidth(
    spw_context: ValidationContext[CorrelationSPWConfiguration] | ValidationContext[Correlation],
) -> list[ValidationIssue]:
    """
    :param spw_context: a ValidationContext containing an SKA Mid
        CorrelationSPWConfiguration or SKA Low Correlation to be validated
    :return: a validation error if the bandwidth of the window
        is outside the frequency range of the telescope or frequency band
    """
    spw_index = spw_context.relevant_context["spw_index"]

    available_bandwidth = (
        get_subarray_specific_parameter_from_osd(
            spw_context.telescope, spw_context.array_assembly, "available_bandwidth_hz"
        )
        * u.Hz
    )

    spw_bandwidth = calculate_continuum_spw_bandwidth(spw_context)

    if spw_bandwidth > available_bandwidth:
        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message=f"Bandwidth of spectral window {spw_index + 1}, "
                f"{float(spw_bandwidth.to('MHz').value)} MHz, is outside "
                f"of available bandwidth "
                f"{float(available_bandwidth.to('MHz').value)} MHz for "
                f"{spw_context.telescope.value} {spw_context.array_assembly.value}",
            )
        ]

    return []


@validator
def validate_low_spw_window(
    spw_context: ValidationContext[Correlation],
) -> list[ValidationIssue]:
    """
    :param spw_context: a ValidationContext containing an SKA Low
        Correlation to be validated
    :return: a validation error if the combination of the central
        frequency and bandwidth of the window is outside the frequency
        range of SKA Low
    """
    centre_frequency = spw_context.primary_entity.centre_frequency * u.Hz
    spw_bandwidth = calculate_continuum_spw_bandwidth(spw_context)
    spw_index = spw_context.relevant_context["spw_index"]

    if (centre_frequency + 0.5 * spw_bandwidth) > low_maximum_frequency() or (
        centre_frequency - 0.5 * spw_bandwidth
    ) < low_minimum_frequency():

        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message=f"Spectral window {spw_index + 1} is outside allowed range",
            )
        ]

    return []


@validator
def validate_mid_spw_window(
    spw_context: ValidationContext[CorrelationSPWConfiguration],
) -> list[ValidationIssue]:
    """
    :param spw_context: a ValidationContext containing an SKA Mid
        CorrelationSPWConfiguration to be validated
    :return: a validation error if the combination of the central
        frequency and bandwidth of the window is outside the frequency
        range of the SKA Mid frequency band
    """
    centre_frequency = spw_context.primary_entity.centre_frequency * u.Hz
    spw_bandwidth = calculate_continuum_spw_bandwidth(spw_context)

    band_data = spw_context.relevant_context["band_data_from_osd"]
    spw_index = spw_context.relevant_context["spw_index"]

    if (centre_frequency + 0.5 * spw_bandwidth) > band_data.max_frequency_hz * u.Hz or (
        centre_frequency - 0.5 * spw_bandwidth
    ) < band_data.min_frequency_hz * u.Hz:

        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message=f"Spectral window {spw_index + 1} is outside allowed range",
            )
        ]

    return []


@validator
def validate_mid_fsps(
    csp_context: ValidationContext[CSPConfiguration],
) -> list[ValidationIssue]:
    """
    :param csp_context: a ValidationContext containing an SKA Mid
        CSP Configuration to be validated
    :return: a validation error if the number of FSPs required
        exceeds the number available for the array assembly being
        validated against
    """
    csp_config = csp_context.primary_entity

    available_fsps = get_subarray_specific_parameter_from_osd(
        csp_context.telescope, csp_context.array_assembly, "number_fsps"
    )

    n_fsps = 0
    for subband in csp_config.midcbf.subbands:
        frequency_offset = subband.frequency_slice_offset
        for spw in subband.correlation_spws:
            centre_frequency = spw.centre_frequency * u.Hz
            spw_bandwidth = calculate_continuum_spw_bandwidth(
                ValidationContext(primary_entity=spw, telescope=csp_context.telescope)
            )

            minimum_spw_frequency = centre_frequency - 0.5 * spw_bandwidth
            maximum_spw_frequency = centre_frequency + 0.5 * spw_bandwidth

            coarse_channel_low = math.floor(
                (
                    minimum_spw_frequency
                    - frequency_offset
                    + (0.5 * mid_frequency_slice_bandwidth())
                )
                / mid_frequency_slice_bandwidth()
            )
            coarse_channel_high = math.floor(
                (
                    maximum_spw_frequency
                    - frequency_offset
                    + (0.5 * mid_frequency_slice_bandwidth())
                )
                / mid_frequency_slice_bandwidth()
            )

            n_fsps += coarse_channel_high - coarse_channel_low + 1

    if n_fsps > available_fsps:
        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                field="$.midcbf",
                message=f"Number of FSPs required for CSP configuration, {n_fsps}, "
                f"is greater than the {available_fsps} FSPs available for "
                f"array assembly {csp_context.array_assembly}",
            )
        ]

    return []


def calculate_continuum_spw_bandwidth(
    spw_context: ValidationContext[CorrelationSPWConfiguration] | ValidationContext[Correlation],
) -> Quantity:
    """
    function to calculate the bandwidth of spectral windows
    """
    number_of_channels = spw_context.primary_entity.number_of_channels
    # this is currently always zero for both MID and LOW
    zoom_factor = spw_context.primary_entity.zoom_factor
    if zoom_factor != 0:
        raise ValueError("zoom windows are not yet supported")

    if spw_context.telescope == TelescopeType.SKA_MID:
        channel_width = mid_channel_width()
    else:
        channel_width = low_station_channel_width()

    spw_bandwidth = channel_width * number_of_channels

    return spw_bandwidth
