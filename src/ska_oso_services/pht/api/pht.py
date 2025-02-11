import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP

from fastapi.routing import APIRouter
from pydantic import ValidationError
from ska_db_oda.persistence.domain.query import MatchType, UserQuery
from ska_oso_pdm.proposal import Proposal

import ska_oso_services.common.utils.validation as validation
from ska_oso_services.common import oda
from ska_oso_services.common.transformers.pht_handler import (
    transform_create_proposal,
    transform_update_proposal,
)
from ska_oso_services.common.utils import s3_bucket
from ska_oso_services.common.utils.coordinates import (
    convert_to_galactic,
    get_coordinates,
    round_coord_to_3_decimal_places,
)
from ska_oso_services.common.error_handling import BadRequestError, NotFoundError

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="")

SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "SMTP_PASSWORD")


@router.post("/proposals", summary="Create a new proposal")
def create_proposal(proposal: dict) -> str:
    """
    Function that requests to POST /proposals are mapped to

    Stores the Proposal in the underlying data store.

    The ODA is responsible for populating the prsl_id and metadata

    :return: a tuple of an Proposal as it exists in the ODA or error
        response and a HTTP status, which the Connection will wrap in a response
    """
    LOGGER.debug("POST PROPOSAL create")

    transform_body = transform_create_proposal(proposal)
    if proposal.prsl_id is not None:
        raise BadRequestError(
            detail=(
                "prsl_id given in the body of the POST request. Identifier"
                " generation for new entities is the responsibility of the ODA,"
                " which will fetch them from SKUID, so they should not be given in"
                " this request."
            ),
        )

    try:
        # Make sure it still conforms?
        prsl = Proposal.model_validate(transform_body)
    except ValidationError as e:
        raise BadRequestError(str(e))

    with oda.uow() as uow:
        updated_prsl = uow.prsls.add(prsl)
        uow.commit()
        return updated_prsl.prsl_id
    

    
@router.get("/proposals/{proposal_id}", summary="Get the existing proposal")
def get_proposal(proposal_id: str) -> Proposal:
    """
    Function that requests to GET /proposals are mapped to

    Retrieves the Proposal for the given proposal_id from the
    underlying data store, if available

    :param proposal_id: identifier of the Proposal
    :return: a tuple of an Proposal and a
        HTTP status, which the Connection will wrap in a response
    """

    LOGGER.debug(f"GET PROPOSAL prsl_id: {proposal_id}", proposal_id)
    with oda as uow:
        try:
            return uow.prsls.get(proposal_id)
        except KeyError:
            raise NotFoundError(f"Could not find proposal: {proposal_id}")


@router.put("/proposals/{proposal_id}", summary="Update the existing proposal")
def update_proposal(proposal_id: str, body: dict) -> Proposal:
    """
    Function that requests to PUT /proposals are mapped to

    Stores the Proposal with the given identifier
    in the underlying data store.

    :param proposal_id: identifier of the Proposal
    :return: a tuple of an Proposal or error response and a HTTP status,
        which the Connection will wrap in a response
    """
    LOGGER.debug(f"PUT PROPOSAL edit prsl_id: {proposal_id}")

    transform_body = transform_update_proposal(body)

    try:
        prsl = Proposal.model_validate(transform_body)  # test transformed
    except ValidationError as e:
        raise BadRequestError(str(e))

    # Initial validation
    if prsl.prsl_id != proposal_id:
        raise BadRequestError("Proposal_id does not match the one in the body")

    # Make sure it actually exists
    with oda as uow:
        try:
            uow.prsls.get(proposal_id)
        except KeyError:
            raise NotFoundError(f"Could not find proposal: {proposal_id}")

    # Adding it will update it.
    with oda as uow:
        uow.prsls.add(prsl)
        uow.commit()
        updated_prsl = uow.prsls.get(proposal_id)

    return updated_prsl


@router.get("/proposals/list/{user_id}", summary="Get a list of proposals created by a user")
def get_proposals_for_user(user_id: str) -> list[Proposal]:
    """
    Function that requests to GET /proposals/list are mapped to

    Retrieves the Proposals for the given user ID from the
    underlying data store, if available

    :param user_id: identifier of the Proposal
    :return: a tuple of a list of Proposal and a
        HTTP status, which the Connection will wrap in a response
    """

    LOGGER.debug(f"GET PROPOSAL LIST query for the user: {user_id}")
    with oda as uow:
        query_param = UserQuery(user=user_id, match_type=MatchType.EQUALS)
        proposals = uow.prsls.query(query_param)
        return proposals


@router.post("/proposals/validate", summary="Validate a proposal")
def validate_proposal(body: dict) -> dict:
    """
    Function that requests to dummy endpoint POST /proposals/validate are mapped to

    Input Parameters: None

    Returns:
    a tuple of a boolean of result and
        an array of message if result is False
    """
    LOGGER.debug("POST PROPOSAL validate")

    transform_body = transform_update_proposal(body)

    try:
        prsl = Proposal.model_validate(transform_body)
    except ValidationError as e:
        raise BadRequestError(str(e))

    result = validation.validate_proposal(prsl)

    return result


@router.post("/signedurl/create_upload/{filename}", summary="Create upload PDF URL")
def create_upload_pdf_url(filename: str) -> str:
    """
    Function that requests to endpoint GET /upload/signedurl/{filename}
    are mapped to

    :param filename: filename of the uploaded document
    :return: a string "/upload/signedurl/{filename}"
    """
    LOGGER.debug("GET Upload Signed URL")

    s3_client = s3_bucket.get_aws_client()
    url = s3_bucket.create_presigned_url_upload_pdf(filename,
                                                    s3_client,
                                                    60
                                                    )

    return url


@router.post("/signedurl/create_download/{filename}", summary="Create download PDF URL")
def create_download_pdf_url(filename: str) -> str:
    """
    Function that requests to endpoint GET /download/signedurl/{filename}
    are mapped to

    :param filename: filename of the uploaded document
    :return: a string "/download/signedurl/{filename}"
    """
    LOGGER.debug("GET Download Signed URL")

    s3_client = s3_bucket.get_aws_client()
    url = s3_bucket.create_presigned_url_download_pdf(filename,
                                                      s3_client,
                                                      60
                                                      )

    return url


@router.post("/signedurl/create_delete/{filename}", summary="Create delete PDF URL")
def create_delete_pdf_url(filename: str) -> str:
    """
    Function that requests to endpoint GET /delete/signedurl/{filename}
    are mapped to

    :param filename: filename of the document to be deleted
    :return: a string "/delete/signedurl/{filename}"
    """
    LOGGER.debug("GET Delete Signed URL")

    s3_client = s3_bucket.get_aws_client()
    url = s3_bucket.create_presigned_url_delete_pdf(filename,
                                                    s3_client,
                                                    60
                                                    )

    return url


@router.get("/coordinates/{object_name}/{reference_frame}", summary="Obtain sky coordinates of the object")
def get_object_coordinates(object_name: str, reference_frame: str) -> dict:
    """
    Function that requests to /coordinates are mapped to

    Query celestial coordinates for a given object name from SIMBAD and NED databases.
    If the object is not found in SIMBAD database
    it then queries the NED (NASA/IPAC Extragalactic Database).

    :param object_name: A string representing the name of the object to query.
    :param reference_frame: A string representing the reference frame
    to return the coordinates in ("galactic" or "equatorial").
    :return: A dictionary with one key "equatorial" or "galactic",
             containing a nested dictionary with galactic or equatorial coordinates:
             {"galactic":
                {"latitude": 78.7068,"longitude": 42.217}
             } or {"equatorial":
                {"right_ascension": "+28:22:38.200",
                "declination": "13:41:11.620"}
             }
             In case of an error, an error response is returned.
    :rtype: dict
    """
    LOGGER.debug("POST PROPOSAL get coordinates: %s", object_name)

    data = get_coordinates(object_name)
    if reference_frame.lower() == "galactic":
        res = convert_to_galactic(data["ra"],
                                  data["dec"],
                                  data["velocity"],
                                  data["redshift"]
                                  )
    else:
        res = round_coord_to_3_decimal_places(data["ra"],
                                              data["dec"],
                                              data["velocity"],
                                              data["redshift"]
                                              )

    return res


@router.post("/send_email", summary="Send a confirmation email")
def send_email(email: str, proposal_id: str) -> dict:
    subject = f"Invitation to participate in SKAO proposal - {proposal_id}"
    message = (
        f"You have been invited to participate in the SKAO proposal with id {proposal_id}."
        " Kindly click on attached link to accept or reject"
    )

    # SMTP configuration
    smtp_server = "eu-smtp-outbound-1.mimecast.com"
    smtp_port = 587
    smtp_user = "proposal-preparation-tool@skao.int"
    smtp_password = SMTP_PASSWORD

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = email
    msg["Subject"] = subject

    msg.attach(MIMEText(message, "plain"))

    # Connect to the SMTP server
    server = SMTP(smtp_server, smtp_port)
    server.starttls()  # Upgrade the connection to secure
    server.login(smtp_user, smtp_password)
    server.sendmail(smtp_user, email, msg.as_string())
    server.quit()

    return {"message": "Email sent successfully!"}
