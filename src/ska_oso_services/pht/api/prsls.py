import copy
import logging
from http import HTTPStatus
from typing import Annotated, Literal
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import ValidationError
from ska_aaa_authhelpers import Role
from ska_db_oda.repository.domain import CustomQuery
from ska_oso_pdm.proposal import Proposal
from ska_oso_pdm.proposal.proposal import ProposalStatus
from ska_oso_pdm.proposal_management.review import PanelReview
from ska_ser_skuid import EntityType, ShortSkuid, int_skuid, mint_skuid
from starlette.status import HTTP_400_BAD_REQUEST

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Scope
from ska_oso_services.common.error_handling import (
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)
from ska_oso_services.common.osdmapper import get_osd_cycles, get_osd_data
from ska_oso_services.pht.models.domain import OsdDataModel
from ska_oso_services.pht.models.schemas import EmailRequest
from ska_oso_services.pht.service import validation
from ska_oso_services.pht.service.proposal_service import (
    merge_latest_with_preference,
    transform_update_proposal,
)
from ska_oso_services.pht.service.s3_bucket import (
    PRESIGNED_URL_EXPIRY_TIME,
    build_proposal_s3_key,
    create_presigned_url_delete_pdf,
    create_presigned_url_download_pdf,
    create_presigned_url_upload_pdf,
    get_aws_client,
)
from ska_oso_services.pht.service.security import Security, SecurityService
from ska_oso_services.pht.service.user_portal import UserPortalService
from ska_oso_services.pht.utils.constants import EXAMPLE_PROPOSAL
from ska_oso_services.pht.utils.pht_helper import get_latest_entity_by_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prsls", tags=["PPT API - Proposal Preparation"])

ProposalID = ShortSkuid[Literal[EntityType.PRP]]


@router.get(
    "/osd/cycles",
    summary="Retrieve OSD data for all available cycles",
)
def get_all_osd_cycles(
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READ, Scope.PHT_READWRITE},
        ),
    ],
) -> list[OsdDataModel]:
    """
    This queries the OSD data for all available cycles.

    This data is made available for the PHT UI.

    Returns:
        list[OsdDataModel]: a list of the OSD data for all cycles.

    """
    del security
    logger.debug("GET OSD data for all cycles")
    cycle_list = get_osd_cycles()

    if isinstance(cycle_list, tuple) and len(cycle_list) == 2:
        err, _ = cycle_list
        if isinstance(err, dict):
            detail = err.get("detail") or err.get("message") or str(err)
        elif isinstance(err, Exception):
            detail = str(err) or err.__class__.__name__
        else:
            detail = str(err)
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=detail)

    cycle_data = []

    for cycle in cycle_list.get("cycles", []):
        logger.debug("Cycle: %s", cycle)
        data = get_osd_data(cycle_id=cycle, source="car")
        cycle_data.append(copy.deepcopy(data))

    return cycle_data


@router.get(
    "/osd/{cycle}",
    summary="Retrieve OSD data for a given cycle",
)
def get_osd_by_cycle(
    cycle: int,
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READ, Scope.PHT_READWRITE},
        ),
    ],
) -> OsdDataModel:
    """
    This queries the OSD data by cycle id.

    This data is made available for the PHT UI.

    Returns:
        OsdDataModel: The OSD data validated against the defined schema.

    """
    del security
    # TODO: We may need to consider moving this to common
    logger.debug("GET OSD data cycle: %s", cycle)
    data = get_osd_data(cycle_id=cycle, source="car")
    if type(data) is tuple and len(data) == 2:
        # Error happened at OSD
        detail = data[0]["detail"]
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=detail)

    return data


@router.post("/create", summary="Create a new proposal")
async def create_proposal(
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
    portal: Annotated[UserPortalService, Depends(UserPortalService)],
    proposal: Proposal = Body(
        ...,
        example=EXAMPLE_PROPOSAL,
    ),
) -> Proposal:
    """
    Creates a new proposal in the ODA.
    """

    logger.debug("POST PROPOSAL create")

    # Fixup PDM typing and make this non-nullable
    if proposal.prsl_id is None:
        proposal.prsl_id = mint_skuid(EntityType.PRP)
    else:
        proposal.prsl_id = ShortSkuid[Literal[EntityType.PRP]](proposal.prsl_id)

    try:
        with oda.uow() as uow:
            groups = await portal.create_proposal_groups(proposal.prsl_id)
            # The one who created the group becomes the PI automatically:
            await portal.create_membership(groups.admin, UUID(security.auth.user_id))
            created_prsl = uow.prsls.add(proposal, security.auth.user_id)
        logger.info("Proposal successfully created with ID %s", created_prsl.prsl_id)
        return created_prsl
    except ValueError as err:
        logger.exception("ValueError when adding proposal to the ODA: %s", err)
        raise BadRequestError(
            detail=f"Failed when attempting to create a proposal: '{err.args[0]}'",
        ) from err


@router.get("/reviewable", summary="Get a list of proposals by status")
def get_proposals_by_status(
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READ, Scope.PHT_READWRITE},
        ),
    ],
) -> list[Proposal]:
    """
    Function that requests to GET /prsls/reviewable are mapped to.

    Retrieves the Proposals from the
    underlying data store based on the role/group, if available
    Return proposals, preferring UNDER_REVIEW over SUBMITTED.
    One latest proposal per prsl_id.

    Returns:
        list[Proposal]

    """

    user_panels = security.facts.get_all_proposals_and_panels().panels

    def _latest_by_status(uow, status) -> list[Proposal]:
        return (
            get_latest_entity_by_id(uow.prsls.query(CustomQuery(status=status)), "prsl_id") or []
        )

    def _filter_by_prsl_ids(proposals: list[Proposal], ids: set[str]) -> list[Proposal]:
        if not ids:
            return []
        return [p for p in proposals if getattr(p, "prsl_id", -1) in ids]

    # TODO This querying could be a lot better.
    with oda.uow() as uow:
        under_review = _latest_by_status(uow, ProposalStatus.UNDER_REVIEW)
        submitted = _latest_by_status(uow, ProposalStatus.SUBMITTED)
        all_reviewable = merge_latest_with_preference(under_review, submitted)

        if security.facts.is_pht_admin():
            security.proposals.allowed_to_view(*(p for p in all_reviewable))
            return all_reviewable

        # Collect prsl_ids assigned to each of the user's panels
        panel_prsl_ids: set[str] = set()
        for pnl_id in user_panels:
            panel = uow.panels.get(pnl_id)
            if panel:
                panel_prsl_ids.update(p.prsl_id for p in panel.proposals)

        proposals = _filter_by_prsl_ids(all_reviewable, panel_prsl_ids)

    logger.debug("Retrieved %d reviewable proposals for %s", len(proposals), security.auth.user_id)
    # Should we extend proposal rules to understand about panel memberships so
    # it's possible to run this check as a backup?
    # security.proposals.allowed_to_view(*(p for p in proposals))
    return proposals


@router.get("/mine", summary="Get a list of proposals the user can access")
def get_proposals_for_user(
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READ, Scope.PHT_READWRITE},
        ),
    ],
) -> list[Proposal]:
    """
    List all proposals where the authenticated user is a collaborator.

    Returns:
        list[Proposal]: Proposals accessible to the current user.

    """
    my_proposals = security.facts.get_all_proposals_and_panels().proposals

    logger.debug("GET PROPOSAL LIST query for the user: %s", security.auth.user_id)

    with oda.uow() as uow:
        proposals = [
            accessible_proposal
            for prsl_id in my_proposals.keys()
            if (accessible_proposal := uow.prsls.get(prsl_id)) is not None
        ]

    if not proposals:
        logger.info("No proposals found for user: %s", security.auth.user_id)
        return []

    logger.debug("Found %d proposals for user: %s", len(proposals), security.auth.user_id)
    # Strictly speaking, this check is redundant because we fetched the list of proposal IDs
    # from the user's access token to start with, but we are double-checking here
    # so the same exact auth logic runs on all code paths that view proposals.
    security.proposals.allowed_to_view(*(p.prsl_id for p in proposals))
    return proposals


@router.get(
    "/{prsl_id}",
    summary="Retrieve an existing proposal",
)
def get_proposal(
    prsl_id: ShortSkuid[Literal[EntityType.PRP]],
    sec: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READ, Scope.PHT_READWRITE},
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
    sec.proposals.allowed_to_view(prsl_id)

    try:
        with oda.uow() as uow:
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
)
def get_proposals_batch(
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READ, Scope.PHT_READWRITE},
        ),
    ],
    prsl_ids: list[str] = Body(..., embed=True, description="List of proposal IDs"),
):
    """
    Batch retrieves proposals by accepting a list of proposal ids
    and returning the proposals for those ids.

    """
    security.proposals.allowed_to_view(*prsl_ids)

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
)
def get_reviews_for_proposal(
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READ, Scope.PHT_READWRITE},
            groups={SecurityService.PHT_ADMIN_GROUP},
        ),
    ],
    prsl_id: str,
) -> list[PanelReview]:
    """
    Function that requests to GET /reviews/{prsl_id} are mapped to.

    Get reviews for a given proposal ID from the
    underlying data store, if available.

    Returns:
        list[PanelReview]

    """
    logger.debug("GET reviews for a prsl_id: %s", prsl_id)
    with oda.uow() as uow:
        query = CustomQuery(prsl_fk=int_skuid(prsl_id).uid)
        reviews = get_latest_entity_by_id(uow.rvws.query(query), "review_id")

    security.reviews.allowed_to_view(*(r.review_id for r in reviews))
    return reviews


@router.put(
    "/{prsl_id}",
    summary="Update an existing proposal",
)
def update_proposal(
    prsl_id: str,
    prsl: Proposal,
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READ, Scope.PHT_READWRITE},
        ),
    ],
) -> Proposal:
    """
    Updates a proposal in the underlying data store.

    """
    # Ensure ID match
    if prsl.prsl_id != prsl_id:
        logger.warning(
            "Proposal ID mismatch: Proposal ID=%s in path, body ID=%s",
            prsl_id,
            prsl.prsl_id,
        )
        raise UnprocessableEntityError(detail="Proposal ID in path and body do not match.")

    security.proposals.allowed_to_edit(prsl_id)
    with oda.uow() as uow:
        transform_body = transform_update_proposal(prsl)
        # Assumption: status is final beyond this point
        if transform_body.status == ProposalStatus.SUBMITTED:
            security.proposals.allowed_to_submit(prsl_id)
        try:
            prsl = Proposal.model_validate(transform_body)  # test transformed
        except ValidationError as err:
            raise BadRequestError(
                detail=f"Validation error after transforming proposal: {err.args[0]}"
            ) from err

        logger.debug("PUT PROPOSAL - Attempting update for prsl_id: %s", prsl_id)

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
    dependencies=[Security(roles={Role.ANY}, scopes={Scope.PHT_READ})],
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
    summary="Send a proposal invitation email",
    deprecated=True,
    dependencies=[Security(roles={Role.ANY}, scopes={Scope.PHT_READWRITE})],
)
async def send_email(
    request: EmailRequest,
    service: Annotated[UserPortalService, Depends(UserPortalService)],
    response: Response,
) -> dict:
    """
    Deprecated. Use POST /pht/prsls/{prsl_id}/invites instead.

    Sends a proposal invitation via the user portal service.
    """
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = f'</pht/prsls/{request.prsl_id}/invites>; rel="successor-version"'

    await service.create_invite(
        prsl_id=request.prsl_id,
        invite_payload={"email": request.email},
    )
    return {"message": "Email sent successfully"}


@router.post(
    "/{prsl_id}/s3/upload/{filename}",
    summary="Create upload PDF URL",
)
def create_upload_pdf_url(
    prsl_id: ProposalID,
    filename: str,
    security: Annotated[SecurityService, Security(roles={Role.ANY}, scopes={Scope.PHT_READWRITE})],
) -> str:
    """
    Generate a presigned S3 upload URL for the given filename.

    """
    security.proposals.allowed_to_edit(prsl_id)
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
    key = build_proposal_s3_key(prsl_id, filename)

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
            key=key, client=s3_client, expiry=PRESIGNED_URL_EXPIRY_TIME
        )
    # TODO: Andrey to look into this and determine the correct code or if not needed
    except ClientError as client_err:
        logger.exception("S3 client failed to generate upload URL: %s", client_err)
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail="Failed to generate upload URL {client_err.args[0]}",
        ) from client_err


@router.post(
    "/{prsl_id}/s3/download/{filename}",
    summary="Create download PDF URL",
)
def create_download_pdf_url(
    prsl_id: ProposalID,
    filename: str,
    security: Annotated[
        SecurityService, Security(roles={Role.ANY}, scopes={Scope.PHT_READ, Scope.PHT_READWRITE})
    ],
) -> str:
    """
    Generate a presigned S3 download URL for the given filename.

    """
    security.proposals.allowed_to_view(prsl_id)
    logger.debug("POST Download Signed URL for: %s", filename)
    key = build_proposal_s3_key(prsl_id, filename)

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
            key=key, client=s3_client, expiry=PRESIGNED_URL_EXPIRY_TIME
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
    "/{prsl_id}/s3/delete/{filename}",
    summary="Create delete PDF URL",
)
def create_delete_pdf_url(
    prsl_id: ProposalID,
    filename: str,
    security: Annotated[SecurityService, Security(roles={Role.ANY}, scopes={Scope.PHT_READWRITE})],
) -> str:
    """
    Generate a presigned S3 delete URL for the given filename.

    """
    security.proposals.allowed_to_edit(prsl_id)
    logger.debug("POST Delete Signed URL for: %s", filename)
    key = build_proposal_s3_key(prsl_id, filename)

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
            key=key, client=s3_client, expiry=PRESIGNED_URL_EXPIRY_TIME
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
    deprecated=True,
    dependencies=[Security(roles={Role.ANY}, scopes={Scope.PHT_READ})],
)
async def get_user_by_email(
    email: str,
    service: Annotated[UserPortalService, Depends(UserPortalService)],
    response: Response,
) -> dict:
    """Deprecated. Use GET /pht/users/search?q=<email> instead.

    Returns:
        dict
    """
    logger.warning(
        "Deprecated endpoint GET /member/%s called. Use GET /users/search instead.", email
    )
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</pht/users/search>; rel="successor-version"'

    result = await service.search_users(query=email, limit=5)
    items = result.get("items", [])
    if items:
        return items[0]
    raise NotFoundError(detail=f"User not found with email: {email}")
