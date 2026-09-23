"""
Example of an SBD generator for some inputs for a specific use case.
Could be left as just a script function or be exposed via the API.
"""
from astropy.units import Quantity
from ska_oso_pdm import SBDefinition, Target, ValidationArrayAssembly, FivePointParameters, PointingPattern, \
    PointingKind
from ska_oso_pdm.builders import MidSBDefinitionBuilder, target_id
from ska_oso_pdm.builders.dish_builder import DishAllocationBuilder
from ska_oso_pdm.builders.utils import csp_configuration_id
from ska_oso_pdm.sb_definition import SDPConfiguration, SDPScript, CSPConfiguration, ScanDefinition
from ska_oso_pdm.sb_definition.csp import MidCBFConfiguration
from ska_oso_pdm.sb_definition.csp.midcbf import ReceiverBand, Subband, CorrelationSPWConfiguration, \
    ChannelAveragingFactor
from ska_oso_services.common.coordinateslookup import get_coordinates, ReferenceFrame


def _resolve_targets_to_five_point(target_names: list[str]) -> list[Target]:

    def resolve(target_name: str) -> Target:
        target: Target = get_coordinates(target_name, ReferenceFrame.equatorial)
        target.pointing_pattern = PointingPattern(active=PointingKind.FIVE_POINT, parameters=[FivePointParameters()])
        target.target_id = target_id()
        return target

    return [resolve(target_name) for target_name in target_names]

def generate_mid_commissioning_five_point_sbd(target_names: list[str], scan_duration_min: float  = 10, sbd_name: str | None = None) -> SBDefinition:
    if sbd_name is None:
        sbd_name = ", ".join(target_names)

    targets = _resolve_targets_to_five_point(target_names)

    csp_configuration = CSPConfiguration(
        config_id=csp_configuration_id(),
        name="CSPConfiguration",
        midcbf=MidCBFConfiguration(
            frequency_band=ReceiverBand.BAND_1,
            subbands=[
                Subband(
                    correlation_spws=[
                        CorrelationSPWConfiguration(
                            spw_id=1,
                            logical_fsp_ids=[1],
                            zoom_factor=0,
                            centre_frequency=450007040.0,
                            number_of_channels=14880,
                            channel_averaging_factor=ChannelAveragingFactor.ONE,
                            time_integration_factor=1,
                        )
                    ]
                )
            ],
        )
    )

    sbd = MidSBDefinitionBuilder(
        name=sbd_name,
        metadata=None,
        dish_allocations=DishAllocationBuilder(),
        targets=targets,
        csp_configurations=[csp_configuration],
        sdp_configurations=[
            SDPConfiguration(
                sdp_script=SDPScript.VIS_RECEIVE, script_version="latest", script_parameters={
                    "extra_helm_values": {}
                }
            )
        ],
        validate_against=ValidationArrayAssembly.AA1,
    )

    # Now add scans
    sbd.dish_allocations.scan_sequence = [ScanDefinition(target_ref=target.target_id, csp_configuration_ref=csp_configuration.config_id, scan_duration=Quantity(scan_duration_min, unit="min"), scan_intent='Calibrator') for target in targets]

    # Could add constraints like LST range here
    # sbd.observing_constraints = ...

    return sbd

