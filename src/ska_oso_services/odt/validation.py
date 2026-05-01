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

LOGGER = logging.getLogger(__name__)


MID_VALIDATION_FNS = []
LOW_VALIDATION_FNS = []
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
