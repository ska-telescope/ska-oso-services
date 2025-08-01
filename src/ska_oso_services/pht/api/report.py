import logging
from typing import List

from fastapi import APIRouter
from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm.proposal.proposal import ProposalStatus

from ska_oso_services.common import oda
from ska_oso_services.pht.model import ProposalReport
from ska_oso_services.pht.utils.pht_handler import (
    get_latest_entity_by_id,
    join_proposals_panels_reviews_decisions,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/report", tags=["PHT API - Report"])


@router.get(
    "/",
    summary="Create a report for admin/coordinator",
    response_model=list[ProposalReport],
)
def get_report() -> List[ProposalReport]:
    """
    Creates a new report for the PHT admin/coordinator.
    """

    LOGGER.debug("GET REPORT create")
    # TODO: get proposals using Andrey's new query so no need to pass user_id
    LOGGER.debug("GET REPORT")
    with oda.uow() as uow:
        proposal_query_param = CustomQuery(status=ProposalStatus.SUBMITTED)
        query_param = CustomQuery()
        proposals = get_latest_entity_by_id(
            uow.prsls.query(proposal_query_param), "prsl_id"
        )
        panels = get_latest_entity_by_id(
            uow.panels.query(query_param), "panel_id"  # pylint: disable=no-member
        )
        reviews = get_latest_entity_by_id(uow.rvws.query(query_param), "review_id")
        decisions = get_latest_entity_by_id(uow.pnlds.query(query_param), "prsl_id")
    report = join_proposals_panels_reviews_decisions(
        proposals, panels, reviews, decisions
    )
    return report



import msal
import requests





@router.get(
    "/role",
    summary="Create a report for admin/coordinator")
def get_role():
    """
    Creates a new report for the PHT admin/coordinator.
    """
    # Configurations
    client_id = '2445e300-54c9-470f-9578-0f54840672af'
    client_secret = 'BHY8Q~HOXyf4_jDuXjSfaRxFXS6-t05r95nDOb0s'
    tenant_id = '78887040-bad7-494b-8760-88dcacfb3805'
    authority = f'https://login.microsoftonline.com/{tenant_id}'
    scope = ['https://graph.microsoft.com/.default']
    group_id= '05883c37-b723-4b63-9216-0a789a61cb07'
    group_display_name = 'obs-oauth2role-opsreviewersci'

    # 1. Get token
    app = msal.ConfidentialClientApplication(client_id, authority=authority, client_credential=client_secret)
    result = app.acquire_token_for_client(scopes=scope)
    print(result)
    access_token = result['access_token']

    headers = {'Authorization': f'Bearer {access_token}'}

    # 3. Get group members (users assigned to "ENG" role)
    members_url = f"https://graph.microsoft.com/v1.0/groups/{group_id}/members"
    print(group_id)
    print("members_url:", members_url)
    members_resp = requests.get(members_url, headers=headers).json()
    print
    users = [m for m in members_resp['value'] if m['@odata.type'] == '#microsoft.graph.user']

    # Print user info
    result = []
    for user in users:
        print(f"{user['displayName']} | {user['mail']} | {user['id']}")
        result.append({
            "displayName": user['displayName'],
            "mail": user['mail'],
            "id": user['id']
        })
    return result