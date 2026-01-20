# https://stackoverflow.com/a/50099819
# pylint ignore
import math

from astropy import units as u
from astropy.cosmology import available
from astropy.units import Quantity
from ska_oso_pdm import TelescopeType
from ska_oso_pdm.sb_definition import CSPConfiguration
from ska_oso_pdm.sb_definition.csp.midcbf import Band5bSubband as pdm_Band5bSubband
from ska_oso_pdm.sb_definition.csp.midcbf import (
    CorrelationSPWConfiguration,
    ReceiverBand,
)

from ska_oso_services.common.osdmapper import (
    Band5bSubband,
    FrequencyBand,
    configuration_from_osd,
)
from ska_oso_services.common.static.constants import (
    FREQUENCY_SLICE_BANDWIDTH,
    LOW_STATION_CHANNEL_WIDTH,
    MID_CHANNEL_WIDTH,
)
from ska_oso_services.validation import OSD, get_subarray_specific_parameter_from_osd
from ska_oso_services.validation.model import (
    ValidationContext,
    ValidationIssue,
    ValidationIssueType,
    check_relevant_context_contains,
    validate,
    validator,
)
from ska_oso_services.validation.target import validate_target


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
def validate_mid_spws(
    csp_context: ValidationContext[CSPConfiguration],
) -> list[ValidationIssue]:
    midcbf = csp_context.primary_entity.midcbf

    if midcbf.band5b_subband is None:
        band_data = get_mid_frequency_band_info(midcbf.frequency_band)
    else:
        band_data = get_mid_frequency_band_info(
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
                    "subband_frequency_slice_offset": midcbf.subbands[
                        0
                    ].frequency_slice_offset,
                },
                telescope=csp_context.telescope,
                array_assembly=csp_context.array_assembly,
            )
        )
    ]

    return spws_validation_results


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
        validate_mid_spw_bandwidth,
        validate_mid_spw_window,
        validate_mid_fsps,
    ]

    return validate(spw_context, validators)


@validator
def validate_mid_spw_centre_frequency(
    spw_context: ValidationContext[CorrelationSPWConfiguration],
) -> list[ValidationIssue]:
    """
    function to validate an individual MID spectral window central frequency

    """
    centre_frequency = spw_context.primary_entity.centre_frequency
    band_data = spw_context.relevant_context["band_data_from_osd"]
    if (
        centre_frequency > band_data.max_frequency_hz
        or centre_frequency < band_data.min_frequency_hz
    ):
        if band_data.sub_bands:
            band_id = "Band5b subband " + str(band_data.sub_band)
        else:
            band_id = band_data.rx_id

        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message=f"Centre frequency of "
                        f"spectral window {centre_frequency}"
                        f" is outside of {band_id}",
            )
        ]


@validator
def validate_mid_spw_bandwidth(
    spw_context: ValidationContext[CorrelationSPWConfiguration],
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

    spw_bandwidth = _calculate_spw_bandwidth(spw_context)

    if spw_bandwidth > available_bandwidth:
        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message=f"Bandwidth of spectral window {float(spw_bandwidth.to('MHz').value)} MHz is outside "
                f"of available bandwidth {float(available_bandwidth.to('MHz').value)} Hz for array assembly "
                f"{spw_context.array_assembly.value}",
            )
        ]


@validator
def validate_mid_spw_window(
    spw_context: ValidationContext[CorrelationSPWConfiguration],
) -> list[ValidationIssue]:

    centre_frequency = spw_context.primary_entity.centre_frequency * u.Hz
    spw_bandwidth = _calculate_spw_bandwidth(spw_context)

    band_data = spw_context.relevant_context["band_data_from_osd"]

    if (centre_frequency + 0.5 * spw_bandwidth) > band_data.max_frequency_hz or (
        centre_frequency - 0.5 * spw_bandwidth
    ) < band_data.min_frequency_hz * u.Hz:

        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message="Spectral window is outside allowed range",
            )
        ]


@validator
def validate_mid_fsps(
    spw_context: ValidationContext[CorrelationSPWConfiguration],
) -> list[ValidationIssue]:
    """
    validator to check that the number of fsps required is feasible for the array assembly
    """

    centre_frequency = spw_context.primary_entity.centre_frequency * u.Hz
    spw_bandwidth = _calculate_spw_bandwidth(spw_context)

    frequency_offset = spw_context.relevant_context[
        "frequency_offset"
    ]  # should be zero

    minimum_spw_frequency = centre_frequency - 0.5 * spw_bandwidth
    maximum_spw_frequency = centre_frequency + 0.5 * spw_bandwidth

    coarse_channel_low = math.floor(
        (minimum_spw_frequency - frequency_offset + (0.5 * FREQUENCY_SLICE_BANDWIDTH))
        / FREQUENCY_SLICE_BANDWIDTH
    )
    coarse_channel_high = math.floor(
        (maximum_spw_frequency - frequency_offset + (0.5 * FREQUENCY_SLICE_BANDWIDTH))
        / FREQUENCY_SLICE_BANDWIDTH
    )

    n_fsps = coarse_channel_high - coarse_channel_low + 1

    available_fsps = get_subarray_specific_parameter_from_osd(
        spw_context.telescope, spw_context.array_assembly, "available_fsps"
    )

    if n_fsps > available_fsps:
        return [
            ValidationIssue(
                level=ValidationIssueType.ERROR,
                message="Number of FSPs required for spectral window is greater than the number of FSPs available "
                f"for array assembly {spw_context.array_assembly}",
            )
        ]


def _calculate_spw_bandwidth(
    spw_context: ValidationContext[CorrelationSPWConfiguration],
) -> tuple[Quantity, Quantity]:
    """
    private function to calculate the minimum and maximum frequencies of spectral windows
    """

    number_of_channels = spw_context.primary_entity.number_of_channels
    zoom_factor = spw_context.primary_entity.zoom_factor

    channel_bandwidth = MID_CHANNEL_WIDTH / (2**zoom_factor)
    spw_bandwidth = channel_bandwidth * number_of_channels

    return spw_bandwidth


def get_mid_frequency_band_info(
    obs_band: ReceiverBand, band5b_subband: pdm_Band5bSubband | None = None
) -> FrequencyBand | Band5bSubband:
    if obs_band != ReceiverBand.BAND_5B and band5b_subband is not None:
        raise ValueError(f"cannot specify and band 5b subband for band {obs_band}")
    elif obs_band == ReceiverBand.BAND_5B and band5b_subband is None:
        raise ValueError(f"band 5b subband must be specified for band 5b observation")

    bands = OSD["ska_mid"].frequency_band

    if band5b_subband is None:
        band_info = next(
            band for band in bands if band.rx_id == "Band_" + obs_band.value
        )

    else:
        subbands_info = next(
            band for band in bands if band.rx_id == "Band_" + obs_band.value
        ).band5b_subbands
        band_info = next(
            subband
            for subband in subbands_info
            if subband.sub_band == band5b_subband.value
        )

    return band_info
