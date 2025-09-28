import logging
from collections import OrderedDict
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
from ska_oso_pdm.proposal.investigator import Investigator
from ska_oso_pdm.proposal.proposal import ProposalStatus
from ska_oso_pdm.proposal_management.review import PanelReview
from starlette.status import HTTP_400_BAD_REQUEST

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.error_handling import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    UnprocessableEntityError,
)
from ska_oso_services.common.osdmapper import get_osd_data
from ska_oso_services.pht.models.domain import OsdDataModel, PrslRole
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
from ska_oso_services.pht.utils.constants import EXAMPLE_PROPOSAL, MS_GRAPH_URL
from ska_oso_services.pht.utils.ms_graph import get_users_by_mail, make_graph_call
from ska_oso_services.pht.utils.pht_helper import (
    generate_entity_id,
    get_latest_entity_by_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prsls", tags=["PPT API - Proposal Preparation"])


@router.get(
    "/osd/{cycle}",
    summary="Retrieve OSD data for a given cycle",
)
def get_osd_by_cycle(cycle: int) -> OsdDataModel:
    """
    This queries the OSD data by cycle id.

    This data is made available for the PHT UI.

    Returns:
        OsdDataModel: The OSD data validated against the defined schema.

    """
    # TODO: We may need to consider moving this to common
    logger.debug("GET OSD data cycle: %s", cycle)
    data = get_osd_data(cycle_id=cycle, source="car")
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
    proposal: Proposal = Body(
        ...,
        example=EXAMPLE_PROPOSAL,
    ),
) -> str:
    """
    Creates a new proposal in the ODA.
    """

    logger.debug("POST PROPOSAL create")

    try:
        # create a proposal level access when the proposal is created
        user_url = f"{MS_GRAPH_URL}/users/{auth.user_id}"
        investigator = make_graph_call(user_url, False)
        new_investigator = Investigator(
            user_id=auth.user_id,
            given_name=investigator[0]["givenName"],
            family_name=investigator[0]["surname"],
            email=investigator[0]["userPrincipalName"],
            status="Accepted",  # This needs to be updated in the datamodel
            principal_investigator=True,
        )
        with oda.uow() as uow:
            proposal.info.investigators.append(new_investigator)
            created_prsl = uow.prsls.add(proposal, auth.user_id)
            # Create permissions
            create_prslacc = ProposalAccess(
                access_id=generate_entity_id("prslacc"),
                prsl_id=created_prsl.prsl_id,
                user_id=auth.user_id,
                role=ProposalRole.PrincipalInvestigator,
                permissions=[
                    ProposalPermissions.Submit,
                    ProposalPermissions.Update,
                    ProposalPermissions.View,
                ],
            )

            uow.prslacc.add(create_prslacc, auth.user_id)
            uow.commit()
        logger.info("Proposal successfully created with ID %s", created_prsl.prsl_id)
        return created_prsl.prsl_id
    except ValueError as err:
        logger.exception("ValueError when adding proposal to the ODA: %s", err)
        raise BadRequestError(
            detail=f"Failed when attempting to create a proposal: '{err.args[0]}'",
        ) from err


@router.get(
    "/reviewable",
    summary="Get a list of proposals by status",
    dependencies=[
        Permissions(
            roles=[Role.SW_ENGINEER, PrslRole.OPS_PROPOSAL_ADMIN],
            scopes=[Scope.PHT_READ],
        )
    ],
)
def get_proposals_by_status() -> list[Proposal]:
    """
    Function that requests to GET /prsls/reviewable are mapped to.

    Retrieves the Proposals from the
    underlying data store, if available
    Return proposals, preferring UNDER_REVIEW over SUBMITTED.
    One latest proposal per prsl_id.

    Returns:
        list[Proposal]

    """
    logger.debug("GET PROPOSAL status")

    preferred_statuses = [ProposalStatus.UNDER_REVIEW, ProposalStatus.SUBMITTED]
    picked_by_id: OrderedDict[str, Proposal] = OrderedDict()

    with oda.uow() as uow:
        for status in preferred_statuses:
            rows = uow.prsls.query(CustomQuery(status=status))
            for proposal in rows:
                # only take latest status per prsl_id
                if proposal.prsl_id not in picked_by_id:
                    picked_by_id[proposal.prsl_id] = proposal

    proposals = list(picked_by_id.values())
    logger.info(
        "Retrieved %d proposals with preference of UNDER_REVIEW over SUBMITTED",
        len(proposals),
    )
    return proposals


@router.get("/mine", summary="Get a list of proposals the user can access")
def get_proposals_for_user(
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.ANY, Role.SW_ENGINEER},
            scopes={Scope.PHT_READ, Scope.ODT_READ},
        ),
    ],
) -> list[Proposal]:
    """
    List all proposals accessible to the authenticated user.

    The proposals are determined from the underlying data store by:
    1.) Resolving accessible proposal IDs via, list_accessible_proposal_ids:
        - This queries the proposal_acces table to see if there is a proposal
        associated with the user_id.
        Note: Once a proposal is created, an access is created and once Co-Is are added,
        access is created as well.
    2.) Fetching each proposal by ID and
    3.) Returning the proposals as a list (empty if none are found).

    Returns:
        list[Proposal]: Proposals accessible to the current user.

    """

    logger.debug("GET PROPOSAL LIST query for the user: %s", auth.user_id)

    with oda.uow() as uow:
        proposals = [
            accessible_proposal
            for prsl_id in list_accessible_proposal_ids(uow, auth.user_id)
            if (accessible_proposal := uow.prsls.get(prsl_id)) is not None
        ]

    if not proposals:
        logger.info("No proposals found for user: %s", auth.user_id)
        return []

    logger.debug("Found %d proposals for user: %s", len(proposals), auth.user_id)
    return proposals


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
    """
    Retrieves the latest proposal by prsl_id.
    1.) Check that the authenticated user has the permission to access the proposal.

    Returns:
        Proposal: Returns the latest version of the proposal for the supplied prsl_id,
                including the metadata.

    """
    logger.debug("GET PROPOSAL prsl_id: %s", prsl_id)

    try:
        with oda.uow() as uow:
            assert_user_has_permission_for_proposal(uow, auth.user_id, prsl_id)
            proposal = uow.prsls.get(prsl_id)
        logger.info("Proposal retrieved successfully: %s", prsl_id)
        return proposal

    except KeyError as err:
        logger.warning("Proposal not found: %s", prsl_id)
        raise NotFoundError(f"Could not find proposal: {prsl_id}") from err


@router.post(
    "/batch",
    summary="Retrieve multiple proposals in batch",
    response_model=list[Proposal],
    dependencies=[
        Permissions(
            roles=[PrslRole.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER],
            scopes=[Scope.PHT_READ],
        )
    ],
)
def get_proposals_batch(
    prsl_ids: list[str] = Body(..., embed=True, description="List of proposal IDs"),
):
    """
    Batch retrieves proposals by accepting a list of proposal ids
    and returning the proposals for those ids.

    """
    logger.debug("GET BATCH PROPOSAL(s): %s", prsl_ids)
    proposals = []
    with oda.uow() as uow:
        for prsl_id in prsl_ids:
            proposal = uow.prsls.get(prsl_id)
            if proposal is not None:
                proposals.append(proposal)
            else:
                logger.warning("Proposal not found: %s", prsl_id)
    return proposals


@router.get(
    "/reviews/{prsl_id}",
    summary="Get all reviews for a particular proposal",
    dependencies=[
        Permissions(
            roles=[PrslRole.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER],
            scopes=[Scope.PHT_READ],
        )
    ],
)
def get_reviews_for_proposal(prsl_id: str) -> list[PanelReview]:
    """
    Function that requests to GET /reviews/{prsl_id} are mapped to.

    Get reviews for a given proposal ID from the
    underlying data store, if available.

    Returns:
        list[PanelReview]

    """
    logger.debug("GET reviews for a prsl_id: %s", prsl_id)
    with oda.uow() as uow:
        query = CustomQuery(prsl_id=prsl_id)
        reviews = get_latest_entity_by_id(uow.rvws.query(query), "review_id")

    return reviews


@router.put(
    "/{prsl_id}",
    summary="Update an existing proposal",
)
def update_proposal(
    prsl_id: str,
    prsl: Proposal,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> Proposal:
    """
    Updates a proposal in the underlying data store.

    """
    with oda.uow() as uow:
        # Check if user in propsal access - forbidden error raised inside
        rows = assert_user_has_permission_for_proposal(
            uow=uow, prsl_id=prsl_id, user_id=auth.user_id
        )
        transform_body = transform_update_proposal(prsl)

        # Assumption: status is final beyond this point
        if transform_body.status == ProposalStatus.SUBMITTED:
            if ProposalPermissions.Submit not in rows[0].permissions:
                logger.info(
                    "Forbidden submit attempt for proposal: %s by user_id: %s ",
                    prsl_id,
                    auth.user_id,
                )
                raise ForbiddenError(
                    detail=(
                        f"You do not have access to submit proposal with id:{prsl_id}"
                    )
                )
        elif ProposalPermissions.Update not in rows[0].permissions:
            logger.info(
                "Forbidden update attempt for proposal: %s by user_id: %s ",
                prsl_id,
                auth.user_id,
            )
            raise ForbiddenError(
                detail=(f"You do not have access to update proposal with id:{prsl_id}")
            )

        try:
            prsl = Proposal.model_validate(transform_body)  # test transformed
        except ValidationError as err:
            raise BadRequestError(
                detail=f"Validation error after transforming proposal: {err.args[0]}"
            ) from err

        logger.debug("PUT PROPOSAL - Attempting update for prsl_id: %s", prsl_id)

        # Ensure ID match
        if prsl.prsl_id != prsl_id:
            logger.warning(
                "Proposal ID mismatch: Proposal ID=%s in path, body ID=%s",
                prsl_id,
                prsl.prsl_id,
            )
            raise UnprocessableEntityError(
                detail="Proposal ID in path and body do not match."
            )

        # Verify proposal exists
        existing = uow.prsls.get(prsl_id)
        if not existing:
            logger.info("Proposal not found for update: %s", prsl_id)
            raise NotFoundError(detail="Proposal not found: {prsl_id}")

        try:
            updated_prsl = uow.prsls.add(prsl)  # Add is used for update
            uow.commit()
            logger.info("Proposal %s updated successfully", prsl_id)
            return updated_prsl

        except ValueError as err:
            logger.error("Validation failed for proposal %s: %s", prsl_id, err)
            raise BadRequestError(
                detail="Validation error while saving proposal: {err.args[0]}"
            ) from err


@router.post(
    "/validate",
    summary="Validate a proposal",
    dependencies=[Permissions(roles=[Role.ANY], scopes=[Scope.PHT_READ])],
)
def validate_proposal(prsl: Proposal) -> dict:
    """
    Validates a submitted proposal via POST.

    Returns:
        dict: {
            "result": bool,
            "validation_errors": list[str]}.

    """
    logger.debug("POST PROPOSAL validate")
    result = validation.validate_proposal(prsl)

    return result


@router.post(
    "/send-email/",
    summary="Send an async email",
    dependencies=[Permissions(roles=[Role.ANY], scopes=[Scope.PHT_READWRITE])],
)
async def send_email(
    request: EmailRequest,
):
    """
    Endpoint to send SKAO email asynchronously via SMTP.

    """

    await send_email_async(request.email, request.prsl_id)
    return {"message": "Email sent successfully"}


@router.post(
    "/signed-url/upload/{filename}",
    summary="Create upload PDF URL",
    dependencies=[Permissions(roles=[Role.ANY], scopes=[Scope.PHT_READWRITE])],
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

    logger.debug("POST Upload Signed URL for: %s", filename)

    try:
        s3_client = get_aws_client()
    except BotoCoreError as boto_err:
        logger.exception("S3 client initialization failed: %s", boto_err)
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
        logger.exception("S3 client failed to generate upload URL: %s", client_err)
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail="Failed to generate upload URL {client_err.args[0]}",
        ) from client_err


@router.post(
    "/signed-url/download/{filename}",
    summary="Create download PDF URL",
    dependencies=[Permissions(roles=[Role.ANY], scopes=[Scope.PHT_READWRITE])],
)
def create_download_pdf_url(filename: str) -> str:
    """
    Generate a presigned S3 download URL for the given filename.

    """

    logger.debug("POST Download Signed URL for: %s", filename)

    try:
        s3_client = get_aws_client()
    except BotoCoreError as boto_err:
        logger.exception("S3 client initialization failed: %s", boto_err)
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
        logger.exception("S3 client failed to generate download URL: %s", client_err)
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail="Failed to generate download URL {client_err.args[0]}",
        ) from client_err


@router.post(
    "/signed-url/delete/{filename}",
    summary="Create delete PDF URL",
    dependencies=[Permissions(roles=[Role.ANY], scopes=[Scope.PHT_READWRITE])],
)
def create_delete_pdf_url(filename: str) -> str:
    """
    Generate a presigned S3 delete URL for the given filename.

    """

    logger.debug("POST Delete Signed URL for: %s", filename)

    try:
        s3_client = get_aws_client()
    except BotoCoreError as boto_err:
        logger.exception("S3 client initialize failed: %s", boto_err)
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
        logger.exception("S3 client failed to generate delete URL: %s", client_err)
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail="Failed to generate delete URL {client_err.args[0]}",
        ) from client_err


@router.get(
    "/member/{email}",
    summary="Retrieve user by email",
    dependencies=[
        Permissions(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
)
def get_user_by_email(email: str) -> dict:
    """Returns an MS Entra user by email from MS Graph.

    Returns:
        dict
    """
    logger.debug("GET PROPOSAL user by email")
    result = get_users_by_mail(email)

    if result:
        return result[0]
    else:
        raise NotFoundError(detail=f"User not found with email: {email}")
