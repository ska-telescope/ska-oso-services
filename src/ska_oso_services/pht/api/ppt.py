import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP

from http import HTTPStatus

from fastapi import APIRouter, HTTPException
from ska_oso_pdm.proposal import Proposal


from ska_oso_services.common import oda
from ska_oso_services.common.error_handling import (
    BadRequestError
)
from ska_oso_services.odt.validation import validate_sbd

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/proposal")


@router.post("/create", summary="Create a new proposal")
def create_proposal(proposal: Proposal) -> str:
    """
    Creates a new proposal in the ODA
    """
    LOGGER.debug("POST PROPOSAL create")

    prsl = Proposal.model_validate(proposal)
    try:
        with oda.uow() as uow:
            created_prsl = uow.prsls.add(prsl)
            uow.commit()
        LOGGER.info(f"Proposal successfully created with ID {created_prsl.prsl_id}")
        return created_prsl.prsl_id
    except ValueError as err:
        LOGGER.exception("ValueError when adding proposal to the ODA")
        raise BadRequestError(
            detail=f"Failed when attempting to create a proposal: '{err.args[0]}'",
        ) from err


  