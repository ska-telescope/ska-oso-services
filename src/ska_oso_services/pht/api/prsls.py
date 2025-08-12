import logging
from http import HTTPStatus
from typing import Annotated

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Body, HTTPException
from pydantic import ValidationError
from ska_aaa_authhelpers import Role
from ska_aaa_authhelpers.auth_context import AuthContext
from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm.proposal import (
    Proposal,
    ProposalAccess,
    ProposalPermissions,
    ProposalRole,
)
from ska_oso_pdm.proposal_management.review import PanelReview
from ska_ost_osd.rest.api.resources import get_osd
from starlette.status import HTTP_400_BAD_REQUEST

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.error_handling import (
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)
from ska_oso_services.pht.models.domain import OsdDataModel
from ska_oso_services.pht.models.schemas import EmailRequest
from ska_oso_services.pht.service import validation
from ska_oso_services.pht.service.email_service import send_email_async
from ska_oso_services.pht.service.proposal_service import (
    assert_user_has_permission_for_proposal,
    list_accessible_proposal_ids,
    transform_update_proposal,
)
from ska_oso_services.pht.service.s3_bucket import (
    PRESIGNED_URL_EXPIRY_TIME,
    create_presigned_url_delete_pdf,
    create_presigned_url_download_pdf,
    create_presigned_url_upload_pdf,
    get_aws_client,
)
from ska_oso_services.pht.utils.constants import EXAMPLE_PROPOSAL
from ska_oso_services.pht.utils.pht_helper import (
    generate_entity_id,
    get_latest_entity_by_id,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/prsls", tags=["PPT API - Proposal Preparation"])


@router.get(
    "/osd/{cycle}",
    summary="Retrieve OSD data for a particular cycle",
)
def get_osd_by_cycle(cycle: int) -> OsdDataModel:
    LOGGER.debug("GET OSD data cycle: %s", cycle)

    data = get_osd(cycle_id=cycle, source="car")
    if type(data) is tuple and len(data) == 2:
        # Error happened at OSD
        detail = data[0]["detail"]
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=detail)

    return data


@router.post("/create", summary="Create a new proposal")
def create_proposal(
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
    proposal: Proposal = Body(..., example=EXAMPLE_PROPOSAL),
) -> str:
    """
    Creates a new proposal in the ODA
    """

    LOGGER.debug("POST PROPOSAL create")

    try:
        with oda.uow() as uow:
            created_prsl = uow.prsls.add(proposal, auth.user_id)
            prslacc: ProposalAccess = {
                "access_id": generate_entity_id("prslacc"),
                "prsl_id": created_prsl.prsl_id,
                "user_id": auth.user_id,
                "role": ProposalRole.PrincipalInvestigator,
                "permissions": [ProposalPermissions.Submit, ProposalPermissions.Update, ProposalPermissions.View],
            }
            uow.prslacc.add(prslacc, auth.user_id)
            uow.commit()
        LOGGER.info("Proposal successfully created with ID %s", created_prsl.prsl_id)
        return created_prsl.prsl_id
    except ValueError as err:
        LOGGER.exception("ValueError when adding proposal to the ODA: %s", err)
        raise BadRequestError(
            detail=f"Failed when attempting to create a proposal: '{err.args[0]}'",
        ) from err


@router.get(
    "/{prsl_id}",
    summary="Retrieve an existing proposal",
)
def get_proposal(
    prsl_id: str,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.ANY, Role.SW_ENGINEER},
            scopes={Scope.PHT_READ},
        ),
    ],
) -> Proposal:
    LOGGER.debug("GET PROPOSAL prsl_id: %s", prsl_id)
    try:
        with oda.uow() as uow:
            assert_user_has_permission_for_proposal(
                uow, auth.user_id, prsl_id, ProposalPermissions.View
            )
            proposal = uow.prsls.get(prsl_id)
        LOGGER.info("Proposal retrieved successfully: %s", prsl_id)
        return proposal

    except KeyError as err:
        LOGGER.warning("Proposal not found: %s", prsl_id)
        raise NotFoundError(f"Could not find proposal: {prsl_id}") from err


@router.post(
    "/batch",
    summary="Retrieve multiple proposals in batch",
    response_model=list[Proposal],
    dependencies=[Permissions(roles=[Role.SW_ENGINEER], scopes=[Scope.PHT_READ])],
)
def get_proposals_batch(
    prsl_ids: list[str] = Body(..., embed=True, description="List of proposal IDs"),
):
    LOGGER.debug("GET BATCH PROPOSAL(s): %s", prsl_ids)
    proposals = []
    with oda.uow() as uow:
        for prsl_id in prsl_ids:
            proposal = uow.prsls.get(prsl_id)
            if proposal is not None:
                proposals.append(proposal)
            else:
                LOGGER.warning("Proposal not found: %s", prsl_id)
    return proposals


@router.get(
    "/status/{status}",
    summary="Get a list of proposals by status",
    dependencies=[
        Permissions(
            roles=[Role.SW_ENGINEER, Role.OPS_PROPOSAL_ADMIN], scopes=[Scope.PHT_READ]
        )
    ],
)
def get_proposals_by_status(status: str) -> list[Proposal]:
    """
    Function that requests to GET /proposals/status are mapped to

    Retrieves the Proposals for the given status from the
    underlying data store, if available

    :param status: status of the proposal
    :return: a tuple of a list of Proposal
    """
    LOGGER.debug("GET PROPOSAL status: %s", status)

    with oda.uow() as uow:
        query_param = CustomQuery(status=status)
        proposals = get_latest_entity_by_id(uow.prsls.query(query_param), "prsl_id")
        LOGGER.info("Proposal retrieved successfully for: %s", status)

        if proposals is None:
            return []

        return get_latest_entity_by_id(proposals, "prsl_id")


@router.get(
    "/reviews/{prsl_id}",
    summary="Get all reviews for a particular proposal",
    dependencies=[Permissions(roles=[Role.SW_ENGINEER], scopes=[Scope.PHT_READ])],
)
def get_reviews_for_proposal(prsl_id: str) -> list[PanelReview]:
    """Function that requests to GET /reviews/{prsl_id} are mapped to
    Get reviews for a given proposal ID from the
    underlying data store, if available

    :param prsl_id: identifier of the Proposal
    :return: list[PanelReview]
    """
    LOGGER.debug("GET reviews for a prsl_id: %s", prsl_id)
    with oda.uow() as uow:
        query = CustomQuery(prsl_id=prsl_id)
        reviews = get_latest_entity_by_id(uow.rvws.query(query), "review_id")

    return reviews


@router.get(
    "/prsls",
    summary="Get a list of proposals created by a user",
)
def get_proposals_for_user(
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.ANY, Role.SW_ENGINEER},
            scopes={Scope.PHT_READ},
        ),
    ]
) -> list[Proposal]:
    """
    Function that requests to GET /proposals/list are mapped to

    Retrieves the Proposals for the given user ID from the
    underlying data store, if available

    :param user_id: identifier of the Proposal
    :return: a tuple of a list of Proposal
    """

    LOGGER.debug("GET PROPOSAL LIST query for the user: %s", auth.user_id)

    with oda.uow() as uow:
        prsl_ids = list_accessible_proposal_ids(
            uow, auth.user_id, ProposalPermissions.View
        )
        proposals = []
        for prsl_id in prsl_ids:
            proposal = uow.prsls.get(prsl_id)
            if proposal is not None:
                proposals.append(proposal)
            else:
                LOGGER.warning("Proposal not found: %s", prsl_id)

        if proposals is None:
            LOGGER.info("No proposals found for user: %s", auth.user_id)
            return []

        LOGGER.debug("Found %d proposals for user: %s", len(proposals), auth.user_id)
        return proposals


@router.put("/{prsl_id}", summary="Update an existing proposal")
def update_proposal(
    prsl_id: str,
    prsl: Proposal,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.ANY, Role.SW_ENGINEER},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> Proposal:
    """
    Updates a proposal in the underlying data store.

    :param prsl_id: identifier of the Proposal in the URL
    :param prsl: Proposal object payload from the request body
    :return: the updated Proposal object
    """
    transform_body = transform_update_proposal(prsl)

    try:
        prsl = Proposal.model_validate(transform_body)  # test transformed
    except ValidationError as err:
        raise BadRequestError(
            detail=f"Validation error after transforming proposal: {err.args[0]}"
        ) from err

    LOGGER.debug("PUT PROPOSAL - Attempting update for prsl_id: %s", prsl_id)

    # Ensure ID match
    if prsl.prsl_id != prsl_id:
        LOGGER.warning(
            "Proposal ID mismatch: Proposal ID=%s in path, body ID=%s",
            prsl_id,
            prsl.prsl_id,
        )
        raise UnprocessableEntityError(
            detail="Proposal ID in path and body do not match."
        )

    with oda.uow() as uow:
        if prsl.status == "draft":
            assert_user_has_permission_for_proposal(
                uow, auth.user_id, prsl_id, ProposalPermissions.Update
            )
        if prsl.status == "submitted":
            assert_user_has_permission_for_proposal(
                uow, auth.user_id, prsl_id, ProposalPermissions.Submit
            )
        # Verify proposal exists
        existing = uow.prsls.get(prsl_id)
        if not existing:
            LOGGER.info("Proposal not found for update: %s", prsl_id)
            raise NotFoundError(detail="Proposal not found: {prsl_id}")

        try:
            updated_prsl = uow.prsls.add(prsl, auth.user_id)  # Add is used for update
            uow.commit()
            LOGGER.info("Proposal %s updated successfully", prsl_id)
            return updated_prsl

        except ValueError as err:
            LOGGER.error("Validation failed for proposal %s: %s", prsl_id, err)
            raise BadRequestError(
                detail="Validation error while saving proposal: {err.args[0]}"
            ) from err


@router.post(
    "/validate",
    summary="Validate a proposal",
    dependencies=[
        Permissions(roles=[Role.ANY, Role.SW_ENGINEER], scopes=[Scope.PHT_READWRITE])
    ],
)
def validate_proposal(prsl: Proposal) -> dict:
    """
    Validates a submitted proposal via POST.

    Returns:
        dict: {
            "result": bool,
            "validation_errors": list[str]
        }
    """
    LOGGER.debug("POST PROPOSAL validate")
    result = validation.validate_proposal(prsl)

    return result


@router.post(
    "/send-email/",
    summary="Send an async email",
    dependencies=[Permissions(roles=[Role.SW_ENGINEER], scopes=[Scope.PHT_READWRITE])],
)
async def send_email(request: EmailRequest):
    """
    Endpoint to send SKAO email asynchronously via SMTP
    """
    await send_email_async(request.email, request.prsl_id)
    return {"message": "Email sent successfully"}


@router.post(
    "/signed-url/upload/{filename}",
    summary="Create upload PDF URL",
    dependencies=[Permissions(roles=[Role.SW_ENGINEER], scopes=[Scope.PHT_READWRITE])],
)
def create_upload_pdf_url(filename: str) -> str:
    """
    Generate a presigned S3 upload URL for the given filename.
    """
    # Catch simple things someone may add to the filename
    if not filename or "/" in filename or "\\" in filename:
        validation_resp = {
            "error": "Invalid filename",
            "reason": "Filename must not contain slashes or be empty",
            "field": "filename",
            "value": filename,
        }
        raise UnprocessableEntityError(detail=validation_resp)

    LOGGER.debug("POST Upload Signed URL for: %s", filename)

    try:
        s3_client = get_aws_client()
    except BotoCoreError as boto_err:
        LOGGER.exception("S3 client initialization failed: %s", boto_err)
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail="Could not initialize S3 client {boto_err.args[0]}",
        ) from boto_err

    try:
        return create_presigned_url_upload_pdf(
            key=filename, client=s3_client, expiry=PRESIGNED_URL_EXPIRY_TIME
        )
    # TODO: Andrey to look into this and determine the correct code or if not needed
    except ClientError as client_err:
        LOGGER.exception("S3 client failed to generate upload URL: %s", client_err)
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail="Failed to generate upload URL {client_err.args[0]}",
        ) from client_err


@router.post(
    "/signed-url/download/{filename}",
    summary="Create download PDF URL",
    dependencies=[Permissions(roles=[Role.SW_ENGINEER], scopes=[Scope.PHT_READWRITE])],
)
def create_download_pdf_url(filename: str) -> str:
    """
    Generate a presigned S3 download URL for the given filename.
    """

    LOGGER.debug("POST Download Signed URL for: %s", filename)

    try:
        s3_client = get_aws_client()
    except BotoCoreError as boto_err:
        LOGGER.exception("S3 client initialization failed: %s", boto_err)
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail="Could not initialize S3 client {boto_err.args[0]}",
        ) from boto_err

    try:
        return create_presigned_url_download_pdf(
            key=filename, client=s3_client, expiry=PRESIGNED_URL_EXPIRY_TIME
        )
    # TODO: Andrey to look into this when secrets are available
    # and determine the correct code or if not needed
    except ClientError as client_err:
        LOGGER.exception("S3 client failed to generate download URL: %s", client_err)
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail="Failed to generate download URL {client_err.args[0]}",
        ) from client_err


@router.post(
    "/signed-url/delete/{filename}",
    summary="Create delete PDF URL",
    dependencies=[Permissions(roles=[Role.SW_ENGINEER], scopes=[Scope.PHT_READWRITE])],
)
def create_delete_pdf_url(filename: str) -> str:
    """
    Generate a presigned S3 delete URL for the given filename.
    """

    LOGGER.debug("POST Delete Signed URL for: %s", filename)

    try:
        s3_client = get_aws_client()
    except BotoCoreError as boto_err:
        LOGGER.exception("S3 client initialize failed: %s", boto_err)
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail="Could not initialize S3 client {boto_err.args[0]}",
        ) from boto_err

    try:
        return create_presigned_url_delete_pdf(
            key=filename, client=s3_client, expiry=PRESIGNED_URL_EXPIRY_TIME
        )
    # TODO: Andrey to look into this when secrets are available
    # and determine the correct code or if not needed
    except ClientError as client_err:
        LOGGER.exception("S3 client failed to generate delete URL: %s", client_err)
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail="Failed to generate delete URL {client_err.args[0]}",
        ) from client_err
