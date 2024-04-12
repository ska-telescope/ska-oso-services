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
from typing import Tuple, Union

from marshmallow.exceptions import ValidationError
from ska_oso_pdm.entities.common.sb_definition import SBDefinition
from ska_oso_pdm.entities.dish.dish_configuration import ReceiverBand
from ska_oso_pdm.schemas import CODEC as MARSHMALLOW_CODEC

from ska_oso_services.common.model import ErrorResponse, ValidationResponse

Response = Tuple[Union[SBDefinition, ValidationResponse, ErrorResponse], int]

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

        if scan_def.dish_configuration_id not in dish_configs.keys():
            messages[f"dish_config_not_in_sb_{scan_def.scan_definition_id}"] = (
                f"Dish configuration '{scan_def.dish_configuration_id}' defined "
                f"in scan definition '{scan_def.scan_definition_id}' does not "
                "exist in the SB"
            )
        else:
            dish_config = dish_configs[scan_def.dish_configuration_id]

        if scan_def.csp_configuration_id not in csp_configs.keys():
            messages[f"csp_config_not_in_sb_{scan_def.scan_definition_id}"] = (
                f"CSP configuration '{scan_def.csp_configuration_id}' defined "
                f"in scan definition '{scan_def.scan_definition_id}' does not "
                "exist in the SB"
            )
        else:
            csp_config = csp_configs[scan_def.csp_configuration_id]

        if dish_config and csp_config:
            if (
                csp_config.common_config.band_5_tuning
                and dish_config.receiver_band
                not in [ReceiverBand.BAND_5A, ReceiverBand.BAND_5B]
            ):
                messages[
                    f"csp_and_dish_band_mismatch_{scan_def.scan_definition_id}"
                ] = (
                    f"Scan definition '{scan_def.scan_definition_id}' specifies "
                    "CSP configuration with band_5_tuning but dish configuration "
                    f"with receiver band {dish_config.receiver_band}"
                )

    return messages


VALIDATION_FNS = [_validate_csp_and_dish_combination]


def validate_sbd(sbd_str: str) -> dict[str, str]:
    """
    Top level validation function for an SBDefinition.

    It applies all the individual validation functions in this module and
    flattens the results into a single dictionary

    :param sbd_str: SBDefinition as a string to be deserialised and validated
    :return: a dictionary with individual validation error mesages,
        each with a unique key which should identify which part of the entity is invalid
    """
    try:
        sbd = MARSHMALLOW_CODEC.loads(SBDefinition, sbd_str)
    except (ValidationError, ValueError) as err:
        return {"deserialisation_error": str(err)}

    return {
        error_key: error_description
        for single_validation_result in [fn(sbd) for fn in VALIDATION_FNS]
        for error_key, error_description in single_validation_result.items()
    }
