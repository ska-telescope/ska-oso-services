import logging
from typing import Annotated

from fastapi import APIRouter
from ska_aaa_authhelpers.auth_context import AuthContext
from ska_aaa_authhelpers.roles import Role
from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm import PanelReview

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.error_handling import (
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)
from ska_oso_services.pht.models.domain import PrslRole
from ska_oso_services.pht.utils.pht_helper import get_latest_entity_by_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["PMT API - Reviews"])


@router.post("/create", summary="Create a new Review")
def create_review(
    reviews: PanelReview,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.SW_ENGINEER, PrslRole.OPS_PROPOSAL_ADMIN},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> str:
    """
    Creates a new Review in the ODA
    """

    logger.debug("POST REVIEW create")

    try:

        with oda.uow() as uow:
            query_param = CustomQuery(
                prsl_id=reviews.prsl_id,
                kind=reviews.review_type.kind,
                reviewer_id=reviews.reviewer_id,
            )
            existing_rvws = get_latest_entity_by_id(
                uow.rvws.query(query_param), "review_id"
            )
            existing_rvw = existing_rvws[0] if existing_rvws else None

            if existing_rvw and existing_rvw.metadata.version == 1:
                return existing_rvw.review_id
            created_review = uow.rvws.add(reviews, auth.user_id)
            uow.commit()
        return created_review.review_id
    except ValueError as err:
        logger.exception("ValueError when adding Review to the ODA: %s", err)
        raise BadRequestError(
            detail=f"Failed when attempting to create a Review: '{err.args[0]}'",
        ) from err


@router.get(
    "/{review_id}",
    summary="Retrieve an existing Review",
    dependencies=[
        Permissions(
            roles=[
                Role.SW_ENGINEER,
                Role.OPS_REVIEWER_SCIENCE,
                Role.OPS_REVIEWER_TECHNICAL,
            ],
            scopes=[Scope.PHT_READ],
        )
    ],
)
def get_review(review_id: str) -> PanelReview:
    logger.debug("GET Review review_id: %s", review_id)

    with oda.uow() as uow:
        Review = uow.rvws.get(review_id)
    return Review


@router.get(
    "/users/reviews",
    summary="Get a list of Reviews created by a user",
)
def get_reviews_for_user(
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={
                Role.SW_ENGINEER,
                PrslRole.OPS_PROPOSAL_ADMIN,
                Role.OPS_REVIEWER_SCIENCE,
                Role.OPS_REVIEWER_TECHNICAL, 
            },
            scopes={Scope.PHT_READ},
        ),
    ],
) -> list[PanelReview]:
    """
    Retrieves the Reviews for the given user ID from the
    underlying data store, if available
    """

    logger.debug("GET Review LIST query for the user: %s", auth.user_id)
    is_allowed = (Role.SW_ENGINEER in auth.roles) or (
        PrslRole.OPS_PROPOSAL_ADMIN in auth.roles
    )
    roles = PrslRole.OPS_REVIEW_CHAIR # figure out later
    with oda.uow() as uow:
        if is_allowed:
            rows = get_latest_entity_by_id(uow.rvws.query(CustomQuery()), "review_id")
        else:
            query_param = CustomQuery(reviewer_id=auth.user_id)
            rows = uow.rvws.query(query_param)
        reviews = get_latest_entity_by_id(rows, "review_id") or []
        return reviews


@router.put(
    "/{review_id}",
    summary="Update an existing Review",
)
def update_review(
    review_id: str,
    review: PanelReview,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={
                Role.SW_ENGINEER,
                Role.OPS_REVIEWER_SCIENCE,
                Role.OPS_REVIEWER_TECHNICAL,
            },
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> PanelReview:
    """
    Updates a Review in the underlying data store.

    :param review_id: identifier of the Review in the URL
    :param review: Review object payload from the request body
    :return: the updated Review object
    """
    logger.debug("PUT Review - Attempting update for review_id: %s", review_id)

    # Ensure ID match
    if review.review_id != review_id:
        logger.warning(
            "Review ID mismatch: Review ID=%s in path, body ID=%s",
            review_id,
            review.review_id,
        )
        raise UnprocessableEntityError(
            detail="Review ID in path and body do not match."
        )

    with oda.uow() as uow:
        # Verify Review exists
        existing = uow.rvws.get(review_id)
        if not existing:
            logger.info("Review not found for update: %s", review_id)
            raise NotFoundError(detail="Review not found: {review_id}")

        try:
            # check that the user is the owner of the review or has SW_ENGINEER role
            # TODO: update this with roles in 2 places
            if (
                existing.reviewer_id != auth.user_id
                and Role.SW_ENGINEER not in auth.roles
            ):
                logger.warning(
                    "User %s attempted to update review %s owned by %s. "
                    "Review not updated.",
                    auth.user_id,
                    review_id,
                    existing.reviewer_id,
                )
                raise BadRequestError(
                    detail="You do not have permission to update this review."
                )
            updated_review = uow.rvws.add(
                review, auth.user_id
            )  # Add is used for update
            uow.commit()
            logger.info("Review %s updated successfully", review_id)
            return updated_review

        except ValueError as err:
            logger.error("Validation failed for Review %s: %s", review_id, err)
            raise BadRequestError(
                detail="Validation error while saving Review: {err.args[0]}"
            ) from err
