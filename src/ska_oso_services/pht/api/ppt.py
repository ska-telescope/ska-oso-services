import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP

from http import HTTPStatus

from fastapi import APIRouter, HTTPException
from ska_oso_pdm.proposal import Proposal

import ska_oso_services.pht.validation as validation


from ska_oso_services.common import oda
from ska_oso_services.common.error_handling import (
    BadRequestError,
    UnprocessableEntityError,
)
from ska_oso_services.common.model import ValidationResponse
from ska_oso_services.odt.validation import validate_sbd

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/ppt")


from ska_oso_services.pht.transformers.pht_handler import (
    transform_create_proposal,
)



@router.post("/proposals", summary="Create a new proposal")
def create_proposal(proposal: Proposal) -> str:
    """
    Creates a new proposal in the ODA
    """
    LOGGER.debug("POST PROPOSAL create")

    transform_body = transform_create_proposal(proposal)
    prsl = Proposal.model_validate(transform_body)
    try:
        with oda.uow() as uow:
            updated_prsl = uow.prsls.add(prsl)
            uow.commit()
            return updated_prsl.prsl_id
    except ValueError as err:
        LOGGER.exception("ValueError when adding proposal to the ODA")
        raise BadRequestError(
            detail=f"Validation failed when uploading to the ODA: '{err.args[0]}'",
        ) from err

  