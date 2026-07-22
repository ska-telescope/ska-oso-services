import logging
from typing import Annotated

from fastapi import APIRouter, Response
from ska_aaa_authhelpers.roles import Role
from ska_db_oda.repository.domain import CustomQuery
from ska_oso_pdm import PanelReview
from ska_ser_skuid import int_skuid

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Scope
from ska_oso_services.common.error_handling import (
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)
from ska_oso_services.pht.service.security import Security, SecurityService
from ska_oso_services.pht.utils.pht_helper import get_latest_entity_by_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["PMT API - Reviews"])

_DEPRECATION_LINK = '</pht/panels/{pnl_id}/reviews/{prsl_id}>; rel="successor-version"'


# ---------------------------------------------------------------------------
# New namespaced routes  /panels/{pnl_id}/reviews/{prsl_id}/...
# ---------------------------------------------------------------------------


@router.get(
    "/panels/{pnl_id}/reviews/{prsl_id}",
    summary="List reviews for a proposal in a panel",
)
def list_reviews(
    pnl_id: str,
    prsl_id: str,
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READ, Scope.PHT_READWRITE}),
    ],
) -> list[PanelReview]:
    security.panels.allowed_to_view(pnl_id)
    with oda.uow() as uow:
        return (
            get_latest_entity_by_id(
                uow.rvws.query(CustomQuery(prsl_fk=int_skuid(prsl_id).uid)), "review_id"
            )
            or []
        )


@router.post(
    "/panels/{pnl_id}/reviews/{prsl_id}",
    summary="Create a review for a proposal in a panel",
)
def create_review(
    pnl_id: str,
    prsl_id: str,
    review: PanelReview,
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
            groups={SecurityService.PHT_ADMIN_GROUP},
        ),
    ],
) -> str:
    security.panels.allowed_to_administer(pnl_id)
    try:
        with oda.uow() as uow:
            query_param = CustomQuery(
                prsl_fk=int_skuid(prsl_id).uid,
                kind=review.review_type.kind,
                reviewer_id=review.reviewer_id,
            )
            existing_rvws = get_latest_entity_by_id(uow.rvws.query(query_param), "review_id")
            existing_rvw = existing_rvws[0] if existing_rvws else None
            if existing_rvw and existing_rvw.metadata.version == 1:
                return existing_rvw.review_id
            created = uow.rvws.add(review, security.auth.user_id)
            uow.commit()
        return created.review_id
    except ValueError as err:
        raise BadRequestError(
            detail=f"Failed when attempting to create a Review: '{err.args[0]}'"
        ) from err


@router.get(
    "/panels/{pnl_id}/reviews/{prsl_id}/{review_id}",
    summary="Retrieve a review",
)
def get_review(
    pnl_id: str,
    prsl_id: str,
    review_id: str,
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READ, Scope.PHT_READWRITE}),
    ],
) -> PanelReview:
    security.panels.allowed_to_view(pnl_id)
    with oda.uow() as uow:
        review = uow.rvws.get(review_id)
    if not review:
        raise NotFoundError(detail=f"Review not found: {review_id}")
    return review


@router.put(
    "/panels/{pnl_id}/reviews/{prsl_id}/{review_id}",
    summary="Update a review",
)
def update_review(
    pnl_id: str,
    prsl_id: str,
    review_id: str,
    review: PanelReview,
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READWRITE}),
    ],
) -> PanelReview:
    if review.review_id != review_id:
        raise UnprocessableEntityError(detail="Review ID in path and body do not match.")
    security.panels.allowed_to_view(pnl_id)
    with oda.uow() as uow:
        existing = uow.rvws.get(review_id)
        if not existing:
            raise NotFoundError(detail=f"Review not found: {review_id}")
        if existing.reviewer_id != security.auth.user_id and not security.facts.is_pht_admin():
            raise BadRequestError(detail="You do not have permission to update this review.")
        try:
            updated = uow.rvws.add(review, security.auth.user_id)
            uow.commit()
        except ValueError as err:
            raise BadRequestError(detail=f"Validation error saving review: {err.args[0]}") from err
    logger.info("Review %s updated successfully", review_id)
    return updated


# ---------------------------------------------------------------------------
# Deprecated routes  /reviews/...
# ---------------------------------------------------------------------------


@router.post("/reviews/create", summary="Create a new Review", deprecated=True)
def legacy_create_review(
    reviews: PanelReview,
    security: Annotated[
        SecurityService,
        Security(
            roles={Role.ANY},
            scopes={Scope.PHT_READWRITE},
            groups={SecurityService.PHT_ADMIN_GROUP},
        ),
    ],
    response: Response,
) -> str:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = _DEPRECATION_LINK
    return create_review(
        pnl_id=str(reviews.panel_id),
        prsl_id=reviews.prsl_id,
        review=reviews,
        security=security,
    )


@router.get(
    "/reviews/{review_id}",
    summary="Retrieve an existing Review",
    deprecated=True,
)
def legacy_get_review(
    review_id: str,
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READ, Scope.PHT_READWRITE}),
    ],
    response: Response,
) -> PanelReview:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = _DEPRECATION_LINK
    with oda.uow() as uow:
        existing = uow.rvws.get(review_id)
    if not existing:
        raise NotFoundError(detail=f"Review not found: {review_id}")
    return get_review(
        pnl_id=str(existing.panel_id),
        prsl_id=existing.prsl_id,
        review_id=review_id,
        security=security,
    )


@router.put(
    "/reviews/{review_id}",
    summary="Update an existing Review",
    deprecated=True,
)
def legacy_update_review(
    review_id: str,
    review: PanelReview,
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READWRITE}),
    ],
    response: Response,
) -> PanelReview:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = _DEPRECATION_LINK
    with oda.uow() as uow:
        existing = uow.rvws.get(review_id)
    if not existing:
        raise NotFoundError(detail=f"Review not found: {review_id}")
    return update_review(
        pnl_id=str(existing.panel_id),
        prsl_id=existing.prsl_id,
        review_id=review_id,
        review=review,
        security=security,
    )


@router.get(
    "/reviews/users/reviews",
    summary="Get a list of Reviews for the current user",
    deprecated=True,
)
def legacy_get_reviews_for_user(
    security: Annotated[
        SecurityService,
        Security(roles={Role.ANY}, scopes={Scope.PHT_READ}),
    ],
    response: Response,
) -> list[PanelReview]:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = _DEPRECATION_LINK
    with oda.uow() as uow:
        if security.facts.is_pht_admin():
            return get_latest_entity_by_id(uow.rvws.query(CustomQuery()), "review_id") or []
        query_param = CustomQuery(reviewer_id=security.auth.user_id)
        return get_latest_entity_by_id(uow.rvws.query(query_param), "review_id") or []
