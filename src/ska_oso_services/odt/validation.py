import logging
from typing import Tuple, Union

from marshmallow.exceptions import ValidationError
from ska_oso_pdm.entities.common.sb_definition import SBDefinition
from ska_oso_pdm.entities.dish.dish_configuration import ReceiverBand
from ska_oso_pdm.schemas import CODEC as MARSHMALLOW_CODEC

from ska_oso_services.odt.generated.models.error_response import ErrorResponse
from ska_oso_services.odt.generated.models.validation_response import ValidationResponse

Response = Tuple[Union[SBDefinition, ValidationResponse, ErrorResponse], int]

LOGGER = logging.getLogger(__name__)


def validate_sbd(sbd_str: str) -> dict:
    messages = []
    try:
        sbd = MARSHMALLOW_CODEC.loads(SBDefinition, sbd_str)
    except (ValidationError, ValueError) as err:
        messages.append(str(err))
        return {"validation_errors": messages}

    # band_5_tuning should not be present in csp_configuration if dish_configuration
    # receiver band is not 5a or 5b
    dish_configs = {dc.dish_configuration_id: dc for dc in sbd.dish_configurations}
    csp_configs = {csp.config_id: csp for csp in sbd.csp_configurations}
    for scan_def in sbd.scan_definitions:
        dish_config = None
        csp_config = None

        if scan_def.dish_configuration_id not in dish_configs.keys():
            messages.append(
                f"Dish configuration '{scan_def.dish_configuration_id}' defined "
                f"in scan definition '{scan_def.scan_definition_id}' does not "
                "exist in the SB"
            )
        else:
            dish_config = dish_configs[scan_def.dish_configuration_id]

        if scan_def.csp_configuration_id not in csp_configs.keys():
            messages.append(
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
                messages.append(
                    f"Scan definition '{scan_def.scan_definition_id}' specifies "
                    "CSP configuration with band_5_tuning but dish configuration "
                    f"with receiver band {dish_config.receiver_band}"
                )

    return {"validation_errors": messages}
