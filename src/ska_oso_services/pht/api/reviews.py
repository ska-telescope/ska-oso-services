import logging
from typing import Annotated

from fastapi import APIRouter
from ska_aaa_authhelpers.roles import Role
from ska_db_oda.postgres import TABLES
from ska_db_oda.repository.domain import ODANotFound
from ska_oso_pdm import PanelReview
from sqlalchemy import select

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Scope
from ska_oso_services.common.error_handling import (
    BadRequestError,
    DuplicateError,
    NotFoundError,
    UnprocessableEntityError,
)
from ska_oso_services.pht.service.security import Security, SecurityService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["PMT API - Reviews"])


def _refuse_moving(stored: PanelReview, review: PanelReview) -> None:
    """Permission is checked against a stored review's links, so a save must keep them."""
    for field in ("reviewer_id", "panel_id", "prsl_id"):
        if getattr(review, field) != getattr(stored, field):
            raise UnprocessableEntityError(detail=f"A review's {field} cannot be changed.")


@router.post("/create", summary="Create a new Review")
def create_review(
    reviews: PanelReview,
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> str:
    security.reviews.allowed_to_create(reviews)
    try:
        with oda.uow() as uow:
            # add() would overwrite a stored review with this ID
            # TODO: This becomes unecessary once the ODA supports explicit create() API
            if reviews.review_id is not None:
                try:
                    uow.rvws.get(reviews.review_id)
                except ODANotFound:
                    pass  # New ID, safe to continue
                else:
                    raise DuplicateError(detail=f"{reviews.review_id!r} already exists")

            stmt = select(TABLES.reviews).where(
                TABLES.reviews.c.prsl_fk == reviews.prsl_id,
                TABLES.reviews.c.kind == reviews.review_type.kind,
                TABLES.reviews.c.reviewer_id == reviews.reviewer_id,
            )
            existing_rvws = uow.rvws.query(stmt)
            existing_rvw = existing_rvws[0] if existing_rvws else None

            if existing_rvw and existing_rvw.metadata.version == 1:
                return existing_rvw.review_id
            created_review = uow.rvws.add(reviews, security.auth.user_id)
            uow.commit()
        return created_review.review_id
    except ValueError as err:
        logger.exception("ValueError when adding Review to the ODA: %s", err)
        raise BadRequestError(
            detail=f"Failed when attempting to create a Review: '{err.args[0]}'"
        ) from err


@router.get(
    "/{review_id}",
    summary="Retrieve an existing Review",
)
def get_review(
    review_id: str,
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READ, Scope.PHT_READWRITE}),
    ],
) -> PanelReview:
    logger.debug("GET Review review_id: %s", review_id)

    with oda.uow() as uow:
        review = uow.rvws.get(review_id)
    if not review:
        raise NotFoundError(detail=f"Review not found: {review_id}")
    security.reviews.allowed_to_view(review)
    return review


@router.get(
    "/users/reviews",
    summary="Get a list of Reviews created by a user",
)
def get_reviews_for_user(
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READ},
        ),
    ],
) -> list[PanelReview]:
    logger.debug("GET Review LIST query for the user: %s", security.auth.user_id)
    with oda.uow() as uow:
        stmt = select(TABLES.reviews).where(TABLES.reviews.c.reviewer_id == security.auth.user_id)
        reviews = uow.rvws.query(stmt)
    for r in reviews:
        security.reviews.allowed_to_view(r)
    return reviews


@router.put(
    "/{review_id}",
    summary="Update an existing Review",
)
def update_review(
    review_id: str,
    review: PanelReview,
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READWRITE}),
    ],
) -> PanelReview:
    logger.debug("PUT Review - Attempting update for review_id: %s", review_id)

    # Ensure ID match
    if review.review_id != review_id:
        logger.warning(
            "Review ID mismatch: Review ID=%s in path, body ID=%s",
            review_id,
            review.review_id,
        )
        raise UnprocessableEntityError(detail="Review ID in path and body do not match.")

    with oda.uow() as uow:
        # Verify Review exists
        existing = uow.rvws.get(review_id)
        if not existing:
            logger.info("Review not found for update: %s", review_id)
            raise NotFoundError(detail=f"Review not found: {review_id}")
        security.reviews.allowed_to_edit(existing)
        _refuse_moving(existing, review)
        try:
            updated_review = uow.rvws.add(review, security.auth.user_id)
            uow.commit()
            logger.info("Review %s updated successfully", review_id)
            return updated_review

        except ValueError as err:
            logger.error("Validation failed for Review %s: %s", review_id, err)
            raise BadRequestError(
                detail=f"Validation error while saving Review: {err.args[0]}"
            ) from err
