"""
This module defines validation functions which are all applied to SBDefinitions.

The functions should all return the same type - a dict of error messages with
unique keys.

Each function performs an isolated part of the validation,
though this might still result in more than one message due to the complex
nature of the validation

They are then all applied to the SBDefinition and the results combined.
"""

import logging

from ska_oso_pdm import TelescopeType
from ska_oso_pdm.sb_definition import SBDefinition
from ska_oso_pdm.sb_definition.dish.dish_configuration import ReceiverBand

LOGGER = logging.getLogger(__name__)


def _validate_csp_and_dish_combination(sbd: SBDefinition) -> dict[str, str]:
    # band_5_tuning should not be present in csp_configuration if dish_configuration
    # receiver band is not 5a or 5b
    messages = {}
    dish_configs = {dc.dish_configuration_id: dc for dc in sbd.dish_configurations}
    csp_configs = {csp.config_id: csp for csp in sbd.csp_configurations}
    for scan_def in sbd.scan_definitions:
        dish_config = None
        csp_config = None

        if scan_def.dish_configuration_ref not in dish_configs.keys():
            messages[f"dish_config_not_in_sb_{scan_def.scan_definition_id}"] = (
                f"Dish configuration '{scan_def.dish_configuration_ref}' defined "
                f"in scan definition '{scan_def.scan_definition_id}' does not "
                "exist in the SB"
            )
        else:
            dish_config = dish_configs[scan_def.dish_configuration_ref]

        if scan_def.csp_configuration_ref not in csp_configs.keys():
            messages[f"csp_config_not_in_sb_{scan_def.scan_definition_id}"] = (
                f"CSP configuration '{scan_def.csp_configuration_ref}' defined "
                f"in scan definition '{scan_def.scan_definition_id}' does not "
                "exist in the SB"
            )
        else:
            csp_config = csp_configs[scan_def.csp_configuration_ref]

        if dish_config and csp_config:
            if csp_config.common.band_5_tuning and dish_config.receiver_band not in [
                ReceiverBand.BAND_5A,
                ReceiverBand.BAND_5B,
            ]:
                messages[
                    f"csp_and_dish_band_mismatch_{scan_def.scan_definition_id}"
                ] = (
                    f"Scan definition '{scan_def.scan_definition_id}' specifies "
                    "CSP configuration with band_5_tuning but dish configuration "
                    f"with receiver band {dish_config.receiver_band}"
                )

    return messages


def _validate_csp(sbd: SBDefinition) -> dict[str, str]:
    messages = {}
    csp_configs = {csp.config_id: csp for csp in sbd.csp_configurations}
    for scan_def in sbd.scan_definitions:
        if scan_def.csp_configuration_ref not in csp_configs.keys():
            messages[f"csp_config_not_in_sb_{scan_def.scan_definition_id}"] = (
                f"CSP configuration '{scan_def.csp_configuration_ref}' defined "
                f"in scan definition '{scan_def.scan_definition_id}' does not "
                "exist in the SB"
            )

    return messages


MID_VALIDATION_FNS = [_validate_csp_and_dish_combination]
LOW_VALIDATION_FNS = [_validate_csp]
COMMON_VALIDATION_FNS = []


def validate_sbd(sbd: SBDefinition) -> dict[str, str]:
    """
    Top level validation function for an SBDefinition.

    It applies all the individual validation functions in this module and
    flattens the results into a single dictionary

    :param sbd: SBDefinition, a Pydantic model from the PDM.
    :return: a dictionary with individual validation error messages,
        each with a unique key which should identify which part of the entity is invalid
    """
    if isinstance(sbd.telescope, TelescopeType):
        validation_fns = (
            MID_VALIDATION_FNS + COMMON_VALIDATION_FNS
            if sbd.telescope == TelescopeType.SKA_MID
            else LOW_VALIDATION_FNS + COMMON_VALIDATION_FNS
        )
    else:
        validation_fns = MID_VALIDATION_FNS

    return {
        error_key: error_description
        for single_validation_result in [fn(sbd) for fn in validation_fns]
        for error_key, error_description in single_validation_result.items()
    }
